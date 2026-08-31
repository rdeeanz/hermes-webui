"""Web Push (RFC 8030 / 8291 / 8292) — VAPID auth, payload encryption, delivery.

WHY THIS EXISTS
  The WebUI already raises notifications, but only from a live page: messages.js
  calls `registration.showNotification()` when a stream finishes while the tab is
  backgrounded. That covers "app is open behind another tab" and nothing else. If
  you send a long task to the agent, lock your phone, and the browser is evicted
  — which phones do aggressively — nothing tells you when it finishes, and an
  approval prompt can leave the agent hanging on a tap that never comes.

  Web Push is the only mechanism that reaches a closed browser, and it needs a
  server that can encrypt to a subscription and authenticate itself to a push
  service.

NO NEW DEPENDENCIES
  The obvious route is `pywebpush`. This module implements the three relevant
  RFCs directly on `cryptography`, which is already a hard dependency, because
  requirements.txt is deliberately two packages and the alternative is either a
  third hard dependency or an optional one that silently disables the feature on
  most installs. The primitives involved — ECDH on P-256, HKDF-SHA256,
  AES-128-GCM, and an ES256 JWT — are all first-class in `cryptography`, so this
  is assembly rather than cryptography engineering.

THE SHAPE OF IT

  Subscription (from PushManager.subscribe in the browser):
      endpoint  the push service URL to POST to
      keys.p256dh  the client's ECDH public key (uncompressed P-256 point)
      keys.auth    a 16-byte client secret

  Sending one message means:
      1. VAPID (RFC 8292): an ES256 JWT over {aud, exp, sub}, sent as
         `Authorization: vapid t=<jwt>, k=<server public key>`. This is how the
         push service knows which application server is talking to it.
      2. Encryption (RFC 8291): derive a shared secret with ECDH between an
         ephemeral server key and the client's p256dh, run it through HKDF with
         the client's auth secret, and seal the payload with AES-128-GCM. The
         push service is an untrusted relay and never sees the plaintext.
      3. POST the aes128gcm body with a TTL.

  A push service replies 404 or 410 for a subscription that no longer exists.
  Those are pruned, since a stale subscription is not an error to retry.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import struct
import threading
import time
import urllib.error
import urllib.request
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

# A push service must accept a message this large after encryption overhead.
# RFC 8291 guarantees 4096 octets of plaintext; we stay well under it because a
# notification body is short and an oversized payload is silently dropped by some
# services rather than rejected.
MAX_PAYLOAD_BYTES = 3000

# Declared record size. We always send exactly one record, so this is simply the
# ceiling RFC 8291 guarantees receivers accept.
RECORD_SIZE = 4096

# How long the push service should retain an undelivered message. Six hours is
# long enough to survive a phone being off overnight-ish without accumulating a
# backlog of stale "your turn finished" notices.
DEFAULT_TTL_SECONDS = 6 * 3600

# VAPID JWTs must not exceed 24h per RFC 8292; 12h leaves room for clock skew.
_VAPID_JWT_TTL = 12 * 3600

_VAPID_KEY_FILE = ".vapid_key"
_SUBSCRIPTIONS_FILE = "push_subscriptions.json"

# One subscription per browser, and a handful of browsers per user, is the real
# shape. The cap exists so a bug in the client cannot grow the file unboundedly.
MAX_SUBSCRIPTIONS_PER_PROFILE = 50

_lock = threading.Lock()
_vapid_private_key: ec.EllipticCurvePrivateKey | None = None


# ── base64url helpers ────────────────────────────────────────────────────────
# Web Push uses unpadded base64url everywhere. Browsers omit the padding; Python
# insists on it.

def b64url_encode(raw: bytes) -> str:
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("expected a base64url string")
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(value + padding)


# ── VAPID application-server key ─────────────────────────────────────────────

def _state_dir() -> Path:
    from api.config import STATE_DIR

    return Path(STATE_DIR)


def _load_or_create_vapid_key() -> ec.EllipticCurvePrivateKey:
    """The application server's identity, stable across restarts.

    It must be stable: the public key is baked into every subscription the
    browser creates, so regenerating it silently invalidates every existing
    subscription — the pushes keep returning 403 and nobody finds out until they
    notice notifications stopped.
    """
    key_file = _state_dir() / _VAPID_KEY_FILE
    try:
        if key_file.exists():
            return serialization.load_pem_private_key(key_file.read_bytes(), password=None)
    except Exception:
        logger.warning(
            "VAPID key at %s could not be loaded; generating a new one. Existing "
            "push subscriptions will stop working and must be re-created.",
            key_file, exc_info=True,
        )

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-chmod leaves a window where the key is world-readable, so
        # create with the right mode from the start.
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, pem)
        finally:
            os.close(fd)
        os.chmod(key_file, 0o600)
    except OSError:
        logger.warning(
            "Could not persist the VAPID key to %s; push will work until restart "
            "and then every existing subscription will need re-creating.",
            key_file, exc_info=True,
        )
    return key


def vapid_private_key() -> ec.EllipticCurvePrivateKey:
    global _vapid_private_key
    with _lock:
        if _vapid_private_key is None:
            _vapid_private_key = _load_or_create_vapid_key()
        return _vapid_private_key


def reset_vapid_key_cache() -> None:
    """Test seam — drops the in-process cache so a new STATE_DIR is picked up."""
    global _vapid_private_key
    with _lock:
        _vapid_private_key = None


def vapid_public_key_b64() -> str:
    """The `applicationServerKey` the browser passes to PushManager.subscribe."""
    raw = vapid_private_key().public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return b64url_encode(raw)


def _vapid_subject() -> str:
    """Contact for the push service operator, per RFC 8292.

    Push services want a way to reach whoever is sending. A self-hosted install
    has no meaningful public contact, so this is configurable and falls back to a
    mailto: that at least identifies the software.
    """
    configured = os.getenv("HERMES_WEBUI_VAPID_SUBJECT", "").strip()
    if configured.startswith("mailto:") or configured.startswith("https://"):
        return configured
    return "mailto:hermes-webui@localhost"


def _es256_jwt(claims: dict) -> str:
    """Sign a JWT with ES256.

    `cryptography` emits ECDSA signatures as DER; JWS wants the raw r||s pair,
    each left-padded to 32 bytes. Getting that wrong produces a token the push
    service rejects with an opaque 401.
    """
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    header = {"typ": "JWT", "alg": "ES256"}
    signing_input = (
        b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    ).encode("ascii")

    der = vapid_private_key().sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return signing_input.decode("ascii") + "." + b64url_encode(raw_sig)


def vapid_headers(endpoint: str) -> dict:
    """Authorization header proving this server owns the application key."""
    parsed = urlparse(endpoint)
    audience = f"{parsed.scheme}://{parsed.netloc}"
    token = _es256_jwt({
        "aud": audience,
        "exp": int(time.time()) + _VAPID_JWT_TTL,
        "sub": _vapid_subject(),
    })
    return {"Authorization": f"vapid t={token}, k={vapid_public_key_b64()}"}


# ── RFC 8291 payload encryption (aes128gcm) ──────────────────────────────────

def encrypt_payload(plaintext: bytes, p256dh_b64: str, auth_b64: str,
                    *, _salt: bytes | None = None,
                    _server_key: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """Seal `plaintext` so only the holder of the subscription can read it.

    The push service is an untrusted relay: it stores and forwards this blob and
    cannot decrypt it. `_salt` and `_server_key` are test seams for reproducing
    the RFC's published vector; production always randomises both.

    Body layout (RFC 8188 §2.1):

        salt (16) | record size (4, big-endian) | key id length (1) |
        key id (65 = server public key) | AES-128-GCM ciphertext

    The plaintext is padded with a single 0x02 delimiter, which marks it as the
    last record. Omitting the delimiter yields a body the browser silently drops.
    """
    client_public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), b64url_decode(p256dh_b64)
    )
    auth_secret = b64url_decode(auth_b64)

    salt = _salt if _salt is not None else secrets.token_bytes(16)
    server_key = _server_key if _server_key is not None else ec.generate_private_key(ec.SECP256R1())
    server_public_raw = server_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    client_public_raw = client_public.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    shared = server_key.exchange(ec.ECDH(), client_public)

    # Step 1: mix the ECDH secret with the subscription's auth secret. The info
    # string binds the result to both public keys, so a shared secret captured
    # from one exchange cannot be replayed against another subscription.
    key_info = b"WebPush: info\x00" + client_public_raw + server_public_raw
    ikm = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=auth_secret, info=key_info
    ).derive(shared)

    # Step 2: derive the content encryption key and nonce from that IKM.
    cek = HKDF(
        algorithm=hashes.SHA256(), length=16, salt=salt,
        info=b"Content-Encoding: aes128gcm\x00",
    ).derive(ikm)
    nonce = HKDF(
        algorithm=hashes.SHA256(), length=12, salt=salt,
        info=b"Content-Encoding: nonce\x00",
    ).derive(ikm)

    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)

    # `rs` is the receiver's maximum record size, NOT the length of this record
    # (RFC 8188 §2.1). Writing the actual length here produces a body that
    # decrypts correctly in a hand-rolled test yet is rejected by real clients,
    # and it is the one field the RFC 8291 vector catches.
    header = salt + struct.pack("!I", RECORD_SIZE) + bytes([len(server_public_raw)]) + server_public_raw
    return header + ciphertext


# ── Subscription store ───────────────────────────────────────────────────────

def _subscriptions_path() -> Path:
    return _state_dir() / _SUBSCRIPTIONS_FILE


def _read_all() -> dict:
    path = _subscriptions_path()
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.warning("Push subscription store at %s is unreadable; treating it "
                       "as empty", path, exc_info=True)
        return {}


def _write_all(data: dict) -> None:
    path = _subscriptions_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        # Same create-with-mode reasoning as the VAPID key: these entries are
        # capabilities to send notifications to someone's device.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps(data, indent=2).encode("utf-8"))
        finally:
            os.close(fd)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not persist push subscriptions to %s", path, exc_info=True)


def _profile_key(profile: str | None) -> str:
    return (profile or "default").strip() or "default"


def _endpoint_allowed(endpoint: str) -> bool:
    """Push endpoints must be https, except on loopback.

    Real push services are always https, and posting an encrypted payload plus a
    VAPID token over plaintext to an arbitrary host is not something to permit.
    Loopback is exempt so a local push relay — and this module's own tests —
    can be exercised without inventing a TLS setup; the same exemption the CSP
    already makes for `http://127.0.0.1:*` and `http://localhost:*`.
    """
    try:
        parsed = urlparse(endpoint)
    except Exception:
        return False
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    if parsed.scheme != "http":
        return False
    host = (parsed.hostname or "").lower()
    return host in ("127.0.0.1", "::1", "localhost")


def list_subscriptions(profile: str | None = None) -> list:
    with _lock:
        return list(_read_all().get(_profile_key(profile), []))


def add_subscription(subscription: dict, profile: str | None = None) -> bool:
    """Store a subscription. Returns False if it is malformed.

    Re-subscribing with the same endpoint replaces the entry rather than adding a
    duplicate — browsers hand back the same endpoint on every subscribe() for a
    given registration, so without this the file would grow on every page load
    that re-checks the subscription.
    """
    endpoint = (subscription or {}).get("endpoint")
    keys = (subscription or {}).get("keys") or {}
    if not isinstance(endpoint, str) or not _endpoint_allowed(endpoint):
        return False
    if not isinstance(keys.get("p256dh"), str) or not isinstance(keys.get("auth"), str):
        return False
    try:
        # Validate now rather than at send time: a malformed key stored here
        # would fail on every future notification with no obvious cause.
        ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), b64url_decode(keys["p256dh"])
        )
        if len(b64url_decode(keys["auth"])) != 16:
            return False
    except Exception:
        return False

    entry = {
        "endpoint": endpoint,
        "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]},
        "created_at": time.time(),
    }
    key = _profile_key(profile)
    with _lock:
        data = _read_all()
        existing = [s for s in data.get(key, []) if s.get("endpoint") != endpoint]
        existing.append(entry)
        data[key] = existing[-MAX_SUBSCRIPTIONS_PER_PROFILE:]
        _write_all(data)
    return True


def remove_subscription(endpoint: str, profile: str | None = None) -> bool:
    key = _profile_key(profile)
    with _lock:
        data = _read_all()
        before = data.get(key, [])
        after = [s for s in before if s.get("endpoint") != endpoint]
        if len(after) == len(before):
            return False
        data[key] = after
        _write_all(data)
    return True


# ── Delivery ─────────────────────────────────────────────────────────────────

def _post(endpoint: str, body: bytes, ttl: int) -> int:
    headers = {
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Content-Length": str(len(body)),
    }
    headers.update(vapid_headers(endpoint))
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        logger.debug("Push delivery to %s failed", endpoint, exc_info=True)
        return 0


def send_to_subscription(subscription: dict, payload: dict,
                         ttl: int = DEFAULT_TTL_SECONDS) -> int:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_PAYLOAD_BYTES:
        # Truncate the body text rather than dropping the notification: knowing
        # the turn finished matters more than reading the whole preview.
        trimmed = dict(payload)
        trimmed["body"] = str(trimmed.get("body", ""))[:200]
        body = json.dumps(trimmed, separators=(",", ":")).encode("utf-8")
    encrypted = encrypt_payload(body, subscription["keys"]["p256dh"], subscription["keys"]["auth"])
    return _post(subscription["endpoint"], encrypted, ttl)


def notify(payload: dict, profile: str | None = None,
           ttl: int = DEFAULT_TTL_SECONDS) -> dict:
    """Send `payload` to every subscription for `profile`.

    Never raises: this is called from streaming and approval paths where a push
    failure must not affect the agent run. Subscriptions the push service reports
    as gone (404/410) are pruned, since retrying them forever is pure noise.
    """
    subs = list_subscriptions(profile)
    if not subs:
        return {"sent": 0, "failed": 0, "pruned": 0}

    sent = failed = pruned = 0
    for sub in subs:
        try:
            status = send_to_subscription(sub, payload, ttl)
        except Exception:
            logger.debug("Push encryption failed for one subscription", exc_info=True)
            failed += 1
            continue
        if 200 <= status < 300:
            sent += 1
        elif status in (404, 410):
            remove_subscription(sub.get("endpoint", ""), profile)
            pruned += 1
        else:
            failed += 1
    if failed:
        logger.info("Web push: %d sent, %d failed, %d pruned", sent, failed, pruned)
    return {"sent": sent, "failed": failed, "pruned": pruned}


def notify_async(payload: dict, profile: str | None = None) -> threading.Thread | None:
    """Fire-and-forget wrapper for call sites on the agent's critical path.

    Delivery involves network I/O to a third-party push service, which can be
    slow or hang. Nothing about a notification justifies blocking a turn, so it
    runs on a daemon thread and its failures stay inside `notify`.

    Returns the thread so a caller that is about to die can give delivery a
    bounded window (see `notify_crash`). Callers on a live path ignore it — a
    daemon thread needs no supervision while the process keeps running.
    """
    if not list_subscriptions(profile):
        return None
    try:
        thread = threading.Thread(
            target=notify, args=(payload, profile), name="push-notify", daemon=True
        )
        thread.start()
        return thread
    except Exception:
        logger.debug("Could not start push notify thread", exc_info=True)
        return None


# ── Payload builders for the remaining triggers ──────────────────────────────
# Approvals (api/route_approvals.py) and turn-completion (api/streaming.py) each
# build their payload inline, because each has exactly one call site. The two
# below have more than one, so they live here instead of being duplicated:
# a cron job can finish on either the manual-run path or the in-process
# scheduler, and a crash can surface from either excepthook.


def _bot_name() -> str:
    """The configured assistant name, for the notification title."""
    try:
        from api.config import load_settings

        return str((load_settings() or {}).get("bot_name") or "").strip() or "Hermes"
    except Exception:
        return "Hermes"


def notify_cron_complete(job: dict, success: bool, error: str | None = None,
                         profile: str | None = None) -> None:
    """Push that a scheduled job finished.

    This is the trigger with the strongest claim on push. A cron job runs on a
    schedule you are not watching — by definition nobody has the page open, so
    the in-page notification path can never fire for it.

    Never raises: both call sites are in a `finally` that must complete.
    """
    try:
        job = job or {}
        job_id = str(job.get("id") or "").strip()
        name = str(job.get("name") or "").strip() or job_id or "Cron job"
        if success:
            body = f"Cron job '{name}' finished."
        else:
            detail = " ".join(str(error or "").split())[:120]
            body = f"Cron job '{name}' failed." + (f" {detail}" if detail else "")
        notify_async({
            "title": _bot_name(),
            "body": body,
            # Keyed on the job, so a job that runs often replaces its own
            # previous notification instead of stacking one per run — and never
            # collides with an approval or turn-complete tag.
            "tag": f"hermes-cron-{job_id or name}",
            "kind": "cron_failed" if not success else "cron",
            "url": "./",
        }, profile)
    except Exception:
        logger.debug("Web push (cron complete) failed to dispatch", exc_info=True)


# A crashing process can crash repeatedly — an exception raised inside a hot
# loop would otherwise turn one bug into a notification flood on someone's lock
# screen. One crash push per cooldown window is enough to make the point.
_CRASH_PUSH_COOLDOWN_SECONDS = 300
_last_crash_push = 0.0
_crash_push_lock = threading.Lock()


def notify_crash(where: str, exc_type_name: str, detail: str = "",
                 profile: str | None = None, wait_seconds: float = 0.0) -> None:
    """Push that the WebUI hit an uncaught exception.

    `wait_seconds` gives delivery a bounded window before returning. The main
    thread's excepthook runs as the interpreter is tearing down, and a daemon
    thread does not survive that — without a short join the notification is
    started and then killed mid-flight. Bounded, because a hung push service
    must not be what stops the process from exiting.

    Never raises: an excepthook that raises re-creates the silent-death class of
    bug this module exists to prevent.
    """
    try:
        global _last_crash_push
        now = time.time()
        with _crash_push_lock:
            if now - _last_crash_push < _CRASH_PUSH_COOLDOWN_SECONDS:
                return
            _last_crash_push = now

        summary = " ".join(str(detail or "").split())[:120]
        body = f"Hermes hit an error in {where} ({exc_type_name})."
        if summary:
            body += f" {summary}"
        thread = notify_async({
            "title": _bot_name(),
            "body": body,
            # Its own tag: a crash must never be collapsed into a turn-complete
            # or approval notification for some session.
            "tag": "hermes-crash",
            "kind": "crash",
            "url": "./",
        }, profile)
        if thread is not None and wait_seconds > 0:
            thread.join(timeout=wait_seconds)
    except Exception:
        logger.debug("Web push (crash) failed to dispatch", exc_info=True)


def reset_crash_push_cooldown() -> None:
    """Clear the crash-push rate limit. For tests."""
    global _last_crash_push
    with _crash_push_lock:
        _last_crash_push = 0.0
