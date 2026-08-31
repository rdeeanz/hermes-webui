"""Web Push — RFC conformance, subscription store, and the delivery contract.

WHY THIS EXISTS
  api/push.py implements RFC 8291 (payload encryption) and RFC 8292 (VAPID) on
  top of `cryptography` rather than taking a dependency on pywebpush. That is the
  right call for a project whose requirements.txt is deliberately two packages,
  but it means the correctness of the crypto is now this repo's problem.

  The load-bearing test is test_matches_rfc8291_published_vector: RFC 8291 §5
  publishes a complete worked example — inputs, intermediate keys, and the exact
  expected ciphertext. If the implementation reproduces it byte for byte, every
  step (ECDH, both HKDF stages, the AES-GCM nonce, the record header) is right.
  It already caught a real bug: the `rs` header field is the receiver's MAXIMUM
  record size, not this record's length, and the wrong value decrypts fine in a
  hand-rolled round-trip while being rejected by real clients.

  The rest pin the things that are easy to get subtly wrong and impossible to
  notice: that payloads are actually opaque to the push service, that dead
  subscriptions get pruned instead of retried forever, that key material is
  written 0600, and that a push failure can never break an agent turn.
"""

import json
import os
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF  # noqa: E402

# A real subscription's key material, taken from the RFC 8291 §5 example so the
# same values serve both the vector test and the store/delivery tests.
UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
UA_PRIVATE = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"
AUTH_SECRET = "BTBZMqHH6r4Tts7J_aSIgg"


@pytest.fixture()
def push(tmp_path, monkeypatch):
    """api.push bound to an isolated STATE_DIR.

    The module caches the VAPID key in process, so the cache is dropped on the
    way in and out — otherwise one test's key leaks into the next test's
    tmp_path and the persistence assertions become meaningless.
    """
    monkeypatch.setenv("HERMES_WEBUI_STATE_DIR", str(tmp_path))
    from api import config as api_config
    from api import push as push_module

    monkeypatch.setattr(api_config, "STATE_DIR", tmp_path, raising=False)
    push_module.reset_vapid_key_cache()
    yield push_module
    push_module.reset_vapid_key_cache()


def _subscription(endpoint):
    return {"endpoint": endpoint, "keys": {"p256dh": UA_PUBLIC, "auth": AUTH_SECRET}}


class _PushService:
    """A stand-in for a browser vendor's push endpoint."""

    def __init__(self, status_by_path=None):
        self.requests = []
        status_by_path = status_by_path or {}
        received = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                received.append({
                    "path": self.path,
                    "body": self.rfile.read(length),
                    # Lower-cased: HTTP header names are case-insensitive and
                    # urllib normalises them on the way out (TTL -> Ttl), so a
                    # case-sensitive lookup here tests urllib, not us.
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                })
                self.send_response(status_by_path.get(self.path, 201))
                self.end_headers()

            def log_message(self, *args):
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self):
        self._server.shutdown()


@pytest.fixture()
def service():
    svc = _PushService({"/gone": 410, "/missing": 404, "/boom": 500})
    yield svc
    svc.stop()


# ── RFC conformance ──────────────────────────────────────────────────────────

def test_matches_rfc8291_published_vector(push):
    """Byte-for-byte reproduction of the RFC 8291 §5 worked example.

    Every step of the derivation is covered by this one assertion: a mistake in
    the ECDH exchange, either HKDF stage, the info strings, the nonce, the
    padding delimiter, or the record header all change the output.
    """
    as_private = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
    salt = "DGv6ra1nlYgDCS1FRnbzlw"
    expected = (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
        "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
        "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
    )
    server_key = ec.derive_private_key(
        int.from_bytes(push.b64url_decode(as_private), "big"), ec.SECP256R1()
    )
    out = push.encrypt_payload(
        b"When I grow up, I want to be a watermelon",
        UA_PUBLIC, AUTH_SECRET,
        _salt=push.b64url_decode(salt), _server_key=server_key,
    )
    assert push.b64url_encode(out) == expected


def test_record_size_header_is_the_maximum_not_the_length(push):
    """RFC 8188 §2.1 `rs`. Writing the actual length here decrypts fine locally
    and is rejected by real clients — the exact bug the vector test caught."""
    import struct

    body = push.encrypt_payload(b"x", UA_PUBLIC, AUTH_SECRET)
    assert struct.unpack("!I", body[16:20])[0] == push.RECORD_SIZE == 4096


def test_a_browser_can_decrypt_what_we_send(push):
    """Round-trip as the receiving user agent, using its private key."""
    ua_key = ec.derive_private_key(
        int.from_bytes(push.b64url_decode(UA_PRIVATE), "big"), ec.SECP256R1()
    )
    import struct

    plaintext = json.dumps({"title": "Hermes", "body": "selesai"}).encode()
    body = push.encrypt_payload(plaintext, UA_PUBLIC, AUTH_SECRET)

    salt = body[:16]
    key_id_len = body[20]
    as_public_raw = body[21:21 + key_id_len]
    ciphertext = body[21 + key_id_len:]
    assert struct.unpack("!I", body[16:20])[0] == 4096

    shared = ua_key.exchange(
        ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public_raw)
    )
    ua_public_raw = ua_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    ikm = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=push.b64url_decode(AUTH_SECRET),
        info=b"WebPush: info\x00" + ua_public_raw + as_public_raw,
    ).derive(shared)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt,
               info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt,
                 info=b"Content-Encoding: nonce\x00").derive(ikm)

    decrypted = AESGCM(cek).decrypt(nonce, ciphertext, None)
    # The trailing 0x02 marks the last record; the browser strips it.
    assert decrypted.endswith(b"\x02")
    assert json.loads(decrypted[:-1])["body"] == "selesai"


def test_each_message_uses_a_fresh_salt_and_ephemeral_key(push):
    """Reusing either would leak plaintext relationships to the relay."""
    a = push.encrypt_payload(b"same", UA_PUBLIC, AUTH_SECRET)
    b = push.encrypt_payload(b"same", UA_PUBLIC, AUTH_SECRET)
    assert a[:16] != b[:16], "salt must be random per message"
    assert a[21:86] != b[21:86], "server ephemeral key must be random per message"
    assert a != b


def test_vapid_header_is_a_signed_es256_jwt_for_the_endpoint_origin(push):
    header = push.vapid_headers("https://fcm.googleapis.com/fcm/send/abc123")["Authorization"]
    assert header.startswith("vapid t=")
    token, key = header[len("vapid t="):].split(", k=")
    head_b64, claims_b64, sig_b64 = token.split(".")

    assert json.loads(push.b64url_decode(head_b64)) == {"typ": "JWT", "alg": "ES256"}
    claims = json.loads(push.b64url_decode(claims_b64))
    # `aud` must be the endpoint's ORIGIN, not the full URL — push services
    # reject a token scoped to the path.
    assert claims["aud"] == "https://fcm.googleapis.com"
    assert claims["exp"] > time.time()
    assert claims["exp"] - time.time() <= 24 * 3600, "RFC 8292 caps VAPID JWT lifetime at 24h"
    assert claims["sub"]

    # JWS wants raw r||s, 32 bytes each — not the DER `cryptography` produces.
    assert len(push.b64url_decode(sig_b64)) == 64
    assert key == push.vapid_public_key_b64()

    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    raw = push.b64url_decode(sig_b64)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    push.vapid_private_key().public_key().verify(
        der, f"{head_b64}.{claims_b64}".encode(), ec.ECDSA(hashes.SHA256())
    )


def test_vapid_key_survives_a_restart(push, tmp_path):
    """It must: the public key is baked into every existing subscription, so
    regenerating it silently breaks them all with no visible symptom."""
    first = push.vapid_public_key_b64()
    push.reset_vapid_key_cache()
    assert push.vapid_public_key_b64() == first
    assert (tmp_path / ".vapid_key").exists()


def test_key_material_is_not_world_readable(push, tmp_path):
    push.vapid_public_key_b64()
    push.add_subscription(_subscription("https://push.example/abc"))
    for name in (".vapid_key", "push_subscriptions.json"):
        mode = stat.S_IMODE((tmp_path / name).stat().st_mode)
        assert mode == 0o600, f"{name} is {oct(mode)}; it grants the ability to notify a device"


# ── Subscription store ───────────────────────────────────────────────────────

def test_resubscribing_replaces_rather_than_duplicates(push):
    """Browsers return the same endpoint on every subscribe() for a registration,
    so without dedup the store would grow on every page load."""
    for _ in range(3):
        assert push.add_subscription(_subscription("https://push.example/abc"))
    assert len(push.list_subscriptions()) == 1


def test_malformed_subscriptions_are_rejected_at_the_door(push):
    """Validating on write, not on send: a bad key stored here would otherwise
    fail on every future notification with no obvious cause."""
    base = _subscription("https://push.example/abc")
    assert not push.add_subscription({})
    assert not push.add_subscription({"endpoint": "https://push.example/x"})
    assert not push.add_subscription({**base, "keys": {"p256dh": "not-a-point", "auth": AUTH_SECRET}})
    assert not push.add_subscription({**base, "keys": {"p256dh": UA_PUBLIC, "auth": "AAAA"}})
    assert push.list_subscriptions() == []


def test_plaintext_endpoints_are_refused_except_on_loopback(push):
    """Posting an encrypted payload and a VAPID token over plaintext to an
    arbitrary host is not something to permit; loopback is exempt so a local
    relay (and this test file) can work without a TLS setup."""
    assert not push.add_subscription(_subscription("http://push.example/abc"))
    assert not push.add_subscription(_subscription("ftp://push.example/abc"))
    assert push.add_subscription(_subscription("http://127.0.0.1:9/abc"))
    assert push.add_subscription(_subscription("https://push.example/abc"))


def test_subscriptions_are_scoped_per_profile(push):
    push.add_subscription(_subscription("https://push.example/a"), profile="work")
    push.add_subscription(_subscription("https://push.example/b"), profile="personal")
    assert len(push.list_subscriptions("work")) == 1
    assert len(push.list_subscriptions("personal")) == 1
    assert push.list_subscriptions("other") == []


def test_store_is_bounded(push):
    for i in range(push.MAX_SUBSCRIPTIONS_PER_PROFILE + 10):
        push.add_subscription(_subscription(f"https://push.example/{i}"))
    assert len(push.list_subscriptions()) == push.MAX_SUBSCRIPTIONS_PER_PROFILE


def test_unreadable_store_is_treated_as_empty_not_fatal(push, tmp_path):
    (tmp_path / "push_subscriptions.json").write_text("{ this is not json", encoding="utf-8")
    assert push.list_subscriptions() == []
    assert push.add_subscription(_subscription("https://push.example/abc"))


# ── Delivery ─────────────────────────────────────────────────────────────────

def test_delivery_sends_an_opaque_body_with_the_expected_headers(push, service):
    push.add_subscription(_subscription(service.base + "/ok"))
    result = push.notify({"title": "Hermes", "body": "rahasia", "url": "/session/x"})

    assert result == {"sent": 1, "failed": 0, "pruned": 0}
    request = service.requests[-1]
    assert request["headers"]["content-encoding"] == "aes128gcm"
    assert int(request["headers"]["ttl"]) == push.DEFAULT_TTL_SECONDS
    assert request["headers"]["authorization"].startswith("vapid t=")
    # The push service is an untrusted relay and must not be able to read this.
    assert b"rahasia" not in request["body"]
    assert b"session" not in request["body"]


@pytest.mark.parametrize("path,expect_pruned", [("/gone", True), ("/missing", True), ("/boom", False)])
def test_dead_subscriptions_are_pruned_but_transient_errors_are_not(push, service, path, expect_pruned):
    """404/410 mean the subscription no longer exists — retrying it forever is
    noise. A 5xx is the service having a bad day and must not lose the device."""
    push.add_subscription(_subscription(service.base + path))
    result = push.notify({"title": "x", "body": "y"})
    assert bool(result["pruned"]) is expect_pruned
    assert len(push.list_subscriptions()) == (0 if expect_pruned else 1)


def test_one_bad_subscription_does_not_stop_the_others(push, service):
    push.add_subscription(_subscription(service.base + "/gone"))
    push.add_subscription(_subscription(service.base + "/ok"))
    result = push.notify({"title": "x", "body": "y"})
    assert result["sent"] == 1 and result["pruned"] == 1


def test_notify_with_no_subscriptions_is_a_no_op(push):
    assert push.notify({"title": "x"}) == {"sent": 0, "failed": 0, "pruned": 0}


def test_oversized_payloads_are_trimmed_rather_than_dropped(push, service):
    """Knowing the turn finished matters more than reading the whole preview."""
    push.add_subscription(_subscription(service.base + "/ok"))
    result = push.notify({"title": "Hermes", "body": "x" * (push.MAX_PAYLOAD_BYTES + 500)})
    assert result["sent"] == 1


def test_notify_never_raises_at_an_unreachable_endpoint(push):
    """It runs on the agent's turn-completion path; an exception there would
    surface as a failed turn."""
    push.add_subscription(_subscription("http://127.0.0.1:1/nothing-listening"))
    assert push.notify({"title": "x", "body": "y"})["failed"] == 1


def test_notify_async_returns_immediately(push, service):
    """The agent must not wait on a third-party push service."""
    push.add_subscription(_subscription(service.base + "/ok"))
    started = time.time()
    push.notify_async({"title": "x", "body": "y"})
    assert time.time() - started < 0.25

    deadline = time.time() + 5
    while not service.requests and time.time() < deadline:
        time.sleep(0.02)
    assert service.requests, "the background thread should still deliver"


# ── Trigger call sites ───────────────────────────────────────────────────────

def test_approval_trigger_is_wired_and_cannot_break_the_agent():
    """submit_pending() runs on the tool-guard path, so its push must be
    fire-and-forget and swallow everything."""
    source = (REPO / "api" / "route_approvals.py").read_text(encoding="utf-8")
    assert "_push_approval_waiting(session_key, entry, total)" in source
    assert "notify_async" in source, "the approval path must not block on delivery"
    assert '"kind": "approval"' in source, (
        "the kind drives requireInteraction in sw.js — an approval must stay on "
        "screen, since the agent is blocked until it is answered"
    )


def test_turn_complete_trigger_is_wired_and_cannot_break_the_turn():
    source = (REPO / "api" / "streaming.py").read_text(encoding="utf-8")
    assert "_push.notify_async(" in source
    assert "'kind': 'turn_complete'" in source
    # Distinct tags, or an approval would collapse into a "response ready".
    assert "'tag': f'hermes-{session_id}'" in source


def test_turn_summary_is_one_short_line_with_a_fallback():
    import api.streaming as streaming

    class Session:
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Line one.\nLine two.\n\nLine three."},
        ]

    summary = streaming._push_turn_summary(Session())
    assert "\n" not in summary, "a lock-screen body is a single line"
    assert summary.startswith("Line one.")

    class Empty:
        messages = []

    # An empty body renders as a notification that says nothing at all.
    assert streaming._push_turn_summary(Empty())


# ── Service worker ───────────────────────────────────────────────────────────

def test_service_worker_handles_push_and_subscription_rotation():
    sw = (REPO / "static" / "sw.js").read_text(encoding="utf-8")
    assert "addEventListener('push'" in sw
    assert "addEventListener('pushsubscriptionchange'" in sw, (
        "a push service can rotate a subscription on its own; without this the "
        "old endpoint silently stops working"
    )
    assert "showNotification" in sw


def test_service_worker_suppresses_a_push_for_a_page_already_on_screen():
    """The page raises its own notification, so both firing is duplicate noise."""
    sw = (REPO / "static" / "sw.js").read_text(encoding="utf-8")
    assert "visibilityState !== 'visible'" in sw or "visibilityState === 'visible'" in sw
    assert "alreadyVisible" in sw


def _require_interaction_expression():
    """The body of the `requireInteraction:` option in sw.js.

    Read as an expression rather than matched as a literal: the set of kinds
    that interrupt is the contract, and it is expected to grow. Pinning the
    exact source text made adding a kind look like a regression.
    """
    sw = (REPO / "static" / "sw.js").read_text(encoding="utf-8")
    start = sw.index("requireInteraction:")
    # Ends at the option separator — either a `,` at paren depth 0 or the end
    # of the options object.
    depth = 0
    for i in range(start, len(sw)):
        ch = sw[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            return sw[start:i]
    raise AssertionError("could not find the end of the requireInteraction option")


@pytest.mark.parametrize("kind", ["approval", "crash", "cron_failed"])
def test_work_stopping_notifications_require_interaction(kind):
    """These three mean progress has halted and will not resume on its own.

    An approval blocks the agent on a tap. A crash means the server died. A
    failed cron job means scheduled work silently did not happen. A notification
    that auto-dismisses while the phone is face-down is no notification at all.
    """
    assert f"'{kind}'" in _require_interaction_expression()


def test_a_finished_turn_does_not_require_interaction():
    """The counter-case: if everything interrupted, nothing would."""
    assert "turn_complete" not in _require_interaction_expression()


# ── Cron + crash triggers ────────────────────────────────────────────────────

def _capture(push, monkeypatch):
    """Collect payloads instead of sending them.

    Via monkeypatch so the stub is undone at teardown: these helpers reach for
    `notify_async` as a module global, so a raw assignment would stay patched
    for every later test in the session.
    """
    sent = []
    monkeypatch.setattr(
        push, "notify_async", lambda payload, profile=None: sent.append(payload)
    )
    push.reset_crash_push_cooldown()
    return sent


def test_cron_push_reports_success_and_failure_differently(push, monkeypatch):
    sent = _capture(push, monkeypatch)

    push.notify_cron_complete({"id": "j1", "name": "Nightly digest"}, True)
    push.notify_cron_complete({"id": "j2", "name": "Backup"}, False, "disk full")

    assert "Nightly digest" in sent[0]["body"] and "failed" not in sent[0]["body"]
    assert "Backup" in sent[1]["body"] and "failed" in sent[1]["body"]
    assert "disk full" in sent[1]["body"], "the reason is the useful part"
    # Only the failure interrupts; a job that worked can wait until you look.
    assert sent[0]["kind"] == "cron" and sent[1]["kind"] == "cron_failed"


def test_cron_push_tags_per_job_so_runs_do_not_stack(push, monkeypatch):
    sent = _capture(push, monkeypatch)

    push.notify_cron_complete({"id": "j1", "name": "Hourly"}, True)
    push.notify_cron_complete({"id": "j1", "name": "Hourly"}, True)
    push.notify_cron_complete({"id": "j2", "name": "Other"}, True)

    assert sent[0]["tag"] == sent[1]["tag"], (
        "an hourly job must replace its own notification, not stack 24 a day"
    )
    assert sent[2]["tag"] != sent[0]["tag"]
    # And never collide with the approval / turn-complete namespaces.
    assert all(p["tag"].startswith("hermes-cron-") for p in sent)


def test_cron_push_survives_a_malformed_job(push, monkeypatch):
    """Both call sites are in a `finally` — this must never raise."""
    sent = _capture(push, monkeypatch)

    push.notify_cron_complete({}, True)
    push.notify_cron_complete(None, False, None)
    assert len(sent) == 2 and all(p["body"] for p in sent)


def test_crash_push_is_rate_limited(push, monkeypatch):
    """An exception in a hot loop must not become a notification flood."""
    sent = _capture(push, monkeypatch)

    for _ in range(5):
        push.notify_crash("thread worker-1", "ValueError", "boom")
    assert len(sent) == 1, "only the first crash in the window notifies"

    push.reset_crash_push_cooldown()
    push.notify_crash("thread worker-1", "ValueError", "boom")
    assert len(sent) == 2, "a later window notifies again"


def test_crash_push_carries_the_location_and_type(push, monkeypatch):
    sent = _capture(push, monkeypatch)

    push.notify_crash("thread sse-writer", "KeyError", "'session_id'")
    body = sent[0]["body"]
    assert "sse-writer" in body and "KeyError" in body
    assert sent[0]["tag"] == "hermes-crash", "must not collapse into a session tag"


def test_crash_push_never_raises_even_if_delivery_explodes(push, monkeypatch):
    """It runs inside an excepthook. A raising hook re-creates the silent-death
    bug that api/crash_visibility.py exists to prevent."""
    def boom(payload, profile=None):
        raise RuntimeError("delivery is broken")

    monkeypatch.setattr(push, "notify_async", boom)
    push.reset_crash_push_cooldown()
    push.notify_crash("the server", "SystemError", "")  # must not raise


def test_cron_triggers_are_wired_at_both_completion_points():
    """A cron job can finish on either path, and both are in a `finally`."""
    routes = (REPO / "api" / "routes.py").read_text(encoding="utf-8")
    profiles = (REPO / "api" / "profiles.py").read_text(encoding="utf-8")
    assert "_push.notify_cron_complete(" in routes, "manual /api/crons/run path"
    assert "_push.notify_cron_complete(" in profiles, "in-process scheduler path"
    # Failure is the default, so an exception before the verdict is known is not
    # reported to the operator as a successful run.
    assert '"success": False' in routes
    assert "job_ok, job_err = False" in profiles


def test_crash_triggers_are_wired_to_both_excepthooks():
    source = (REPO / "api" / "crash_visibility.py").read_text(encoding="utf-8")
    assert source.count("_push_crash(") >= 3, "helper + both hooks"
    # The main-thread hook runs as the interpreter tears down, where a daemon
    # thread does not survive; without a bounded wait the push is killed
    # mid-flight. The thread hook needs no wait — the process keeps running.
    assert "wait_seconds=3.0" in source
    assert "_push_crash(f\"thread {thread_name}\", exc_type, exc_value)" in source


# ── Client ───────────────────────────────────────────────────────────────────

def test_client_subscribes_only_on_an_explicit_opt_in():
    """Requesting notification permission on page load is an anti-pattern, and a
    denial is sticky."""
    panels = (REPO / "static" / "panels.js").read_text(encoding="utf-8")
    assert "function onPushToggleChanged" in panels
    assert "requestPermission" in panels
    # The permission request must live in the subscribe path, not at load time.
    subscribe = panels[panels.index("async function subscribeToPush"):]
    subscribe = subscribe[:subscribe.index("\nasync function unsubscribeFromPush")]
    assert "Notification.requestPermission()" in subscribe
    assert "userVisibleOnly:true" in subscribe


def test_client_warns_ios_users_that_a_tab_cannot_receive_push():
    html = (REPO / "static" / "index.html").read_text(encoding="utf-8")
    panels = (REPO / "static" / "panels.js").read_text(encoding="utf-8")
    assert 'id="pushIosHint"' in html
    assert "_isInstalledPwa" in panels and "_isIOSLike" in panels


def test_unsubscribe_tells_the_server_even_if_the_browser_call_fails():
    """A subscription the server keeps pushing to after the user opted out is
    the worse failure."""
    panels = (REPO / "static" / "panels.js").read_text(encoding="utf-8")
    body = panels[panels.index("async function unsubscribeFromPush"):]
    body = body[:body.index("\nasync function sendTestPush")]
    assert "method:'DELETE'" in body.replace(" ", "")
    assert body.index("sub.unsubscribe()") < body.index("/api/push/subscribe")
