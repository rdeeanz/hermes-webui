"""Native-feel platform integrations (roadmap P4.2).

WHAT THE ROADMAP GOT WRONG, AND WHY IT MATTERS HERE
  The plan listed nine items and asserted "zero of nine exist today —
  verified: no startViewTransition, navigator.vibrate, share_target,
  setAppBadge, or navigator.share in static/".

  That grep covered five API names and the conclusion was generalised to all
  nine. Three of the nine were already shipped, and are NOT reimplemented:

    #3 optimistic UI      messages.js pushes the user bubble and renders it
                          before the /api/chat/start POST
    #4 skeleton screen    sessions.js showSessionListSkeleton, with .skeleton-row
                          CSS and a reduced-motion variant
    #9 hands-free voice   boot.js turn-based voice mode (#1333): listen -> send
                          -> TTS -> listen, with a server-TTS fallback

  The tests below therefore split into two halves: contracts for the five that
  were genuinely built (1, 2, 5, 7, 8), and regression pins for the three that
  already existed so a future "P4.2 is unstarted" reading cannot delete them.
  #6 (pull-to-refresh) existed on the wrong element and is covered in
  tests/test_webui_external_refresh_frontend.py alongside its original tests.

WHY SO MANY "MUST NOT BREAK WHEN UNSUPPORTED" ASSERTIONS
  The support matrix is genuinely split — Badging is Chromium and
  installed-only, Vibration is Android-only, Web Share's `files` is narrower
  than Web Share itself. Every one of these has to be a no-op on the platforms
  that lack it, and the failure mode for getting that wrong is not a missing
  animation: viewTransition() owns a DOM update, so a wrong capability check
  there stops the UI responding to navigation entirely.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).parent.parent
STATIC = REPO / "static"

NATIVE = (STATIC / "native.js").read_text(encoding="utf-8")
SW = (STATIC / "sw.js").read_text(encoding="utf-8")
BOOT = (STATIC / "boot.js").read_text(encoding="utf-8")
UI = (STATIC / "ui.js").read_text(encoding="utf-8")
MESSAGES = (STATIC / "messages.js").read_text(encoding="utf-8")
PANELS = (STATIC / "panels.js").read_text(encoding="utf-8")
SESSIONS = (STATIC / "sessions.js").read_text(encoding="utf-8")
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
ROUTES = (REPO / "api" / "routes.py").read_text(encoding="utf-8")
MANIFEST = json.loads((STATIC / "manifest.json").read_text(encoding="utf-8"))


def _code(src: str) -> str:
    """Drop whole-line comments.

    Several assertions below ban a substring, and these files explain in prose
    why they avoid exactly that thing. Scanning raw text fails on the
    explanation and pressures the next reader to delete it.
    """
    out, in_block = [], False
    for line in src.splitlines():
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*") or s.startswith("<!--"):
            if "*/" not in s and "-->" not in s:
                in_block = True
            continue
        if s.startswith("//") or s.startswith("*"):
            continue
        out.append(line)
    return "\n".join(out)


# ── Load order ───────────────────────────────────────────────────────────────


def test_native_js_loads_before_the_modules_that_use_it():
    """This was a real bug, not a hypothetical.

    native.js was originally the last <script> in the file. boot.js reads
    window.HermesNative during its OWN execution to drain the Share Target
    inbox, and a deferred script's readyState is already 'interactive' when it
    runs — so the drain saw no HermesNative, took its early return, and silently
    dropped every share. Verified in a browser: composer empty before, populated
    after.
    """
    order = re.findall(r'<script src="static/([^"?]+)', INDEX)
    assert "native.js" in order, "native.js must be loaded by index.html"
    idx = order.index("native.js")
    for consumer in ("ui.js", "messages.js", "panels.js", "boot.js"):
        assert consumer in order
        assert idx < order.index(consumer), (
            f"native.js must load before {consumer}, which reaches for "
            f"window.HermesNative"
        )


def test_the_share_drain_does_not_depend_on_tag_order_either():
    """Belt and braces for the bug above: waiting for DOMContentLoaded is the
    first moment every deferred script has run, whatever the order."""
    block = BOOT[BOOT.index("// ── Share Target: deliver what another app shared"):]
    assert "readyState==='interactive'" in block, (
        "an immediate _initShareDrain() would run before later deferred scripts; "
        "the "
        "'interactive' state has to be treated as 'not ready yet' here"
    )
    assert "DOMContentLoaded" in block


def test_native_js_is_precached_for_offline_boot():
    assert "'./static/native.js' + VQ" in SW, (
        "a share can be the thing that opens the app offline, so the module "
        "that drains the share inbox has to be in the offline shell"
    )


# ── #1 Share Target ──────────────────────────────────────────────────────────


def test_manifest_declares_a_share_target():
    st = MANIFEST.get("share_target")
    assert st, "manifest.json must declare share_target"
    assert st["action"] == "share-target", (
        "the action must be manifest-relative and inside \"scope\": \"./\" — an "
        "out-of-scope share target is rejected at install time"
    )
    assert st["method"] == "POST"
    assert st["enctype"] == "multipart/form-data", (
        "only multipart can carry files; a GET share target is text-only"
    )
    params = st["params"]
    assert params["title"] == "title"
    assert params["text"] == "text"
    assert params["url"] == "url"


def test_share_target_accepts_only_what_the_composer_can_act_on():
    """A wildcard accept makes Hermes offer itself as a target for anything,
    including files it will immediately refuse."""
    accept = MANIFEST["share_target"]["params"]["files"][0]["accept"]
    assert "*/*" not in accept
    assert any(a.startswith("image/") for a in accept), "images are the point of files here"


def test_share_target_is_inside_the_manifest_scope():
    scope = MANIFEST.get("scope", "./")
    action = MANIFEST["share_target"]["action"]
    assert not action.startswith("/"), (
        f"action {action!r} must be relative to the manifest, not root-absolute, "
        f"or it escapes scope {scope!r} on a subpath mount"
    )


def test_service_worker_intercepts_the_share_post_before_the_navigation_branch():
    """A share arrives as a POST whose `mode` is 'navigate'.

    The generic navigation handler would forward it to the network, so the
    interception has to come first or the service-worker path never runs at all.
    """
    code = _code(SW)
    share_idx = code.index("SHARE_TARGET_RE.test(url.pathname)")
    nav_idx = code.index("event.request.mode === 'navigate'")
    assert share_idx < nav_idx, (
        "the share-target branch must precede the navigation branch"
    )
    assert "event.request.method === 'POST'" in code[:nav_idx]


def test_share_target_redirects_with_303():
    """303 turns the POST into a GET on the redirect.

    With a 302 the browser re-POSTs on refresh and re-delivers the same share.
    """
    assert "Response.redirect(target, 303)" in SW
    assert "303" in ROUTES[ROUTES.index("def _handle_share_target"):][:3000]
    assert "handler.send_response(303)" in ROUTES


def test_share_target_bounds_what_another_application_can_send():
    """The producer is a different app, and this writes to disk."""
    for const in ("SHARE_MAX_FILES", "SHARE_MAX_FILE_BYTES", "SHARE_MAX_TEXT_CHARS"):
        assert const in SW, f"sw.js must bound {const}"
    assert "_SHARE_TARGET_MAX_BYTES" in ROUTES
    assert "_SHARE_TARGET_MAX_TEXT" in ROUTES


def test_share_inbox_survives_a_worker_update():
    """deleteOldShellCaches runs on install, and a share can land while an
    updated worker is installing. Wiping it there swallows the share."""
    purge = SW[SW.index("function deleteOldShellCaches()"):]
    purge = purge[: purge.index("\n}")]
    assert "k !== SHARE_CACHE" in purge


def test_share_inbox_names_agree_between_the_worker_and_the_page():
    """Two files, one storage contract. A rename on one side is a share that
    vanishes with no error anywhere."""
    for name in ("'hermes-share-inbox'", "'share-inbox/meta'"):
        assert name in SW, f"sw.js must use {name}"
        assert name in NATIVE, f"native.js must use {name}"


def test_stale_shares_are_dropped_rather_than_applied():
    """The inbox is read on every boot, not only after ?shared=1 — otherwise a
    lost query string strands the payload forever. The freshness window is what
    makes reading it unconditionally safe."""
    assert "SHARE_MAX_AGE_MS" in NATIVE
    block = NATIVE[NATIVE.index("function _readShareCache"):]
    block = block[: block.index("function _clearShareCache")]
    assert "SHARE_MAX_AGE_MS" in block
    assert "cache.delete(SHARE_META_URL)" in block


def test_a_share_never_auto_sends_and_never_clobbers_a_draft():
    """Two rules that matter more than anything else in this feature.

    The share sheet is one tap. Sending a message to an agent on one accidental
    tap is not recoverable, and replacing half-typed text is data loss.
    """
    block = BOOT[BOOT.index("function _applyShared(payload)"):]
    block = block[: block.index("function _initShareDrain()")]
    code = _code(block)
    assert "send()" not in code, "a share must never trigger a send"
    assert "existing.trim() ?" in code and "+'\\n\\n'+" in code, (
        "shared text must be appended to an existing draft, not replace it"
    )
    assert "showToast" in code, (
        "the user tapped share in another app and landed in this one; say so"
    )


def test_shared_files_go_through_the_normal_staging_path():
    """addFiles() already enforces MAX_UPLOAD_BYTES and de-dupes by name; a
    second staging path would not."""
    block = BOOT[BOOT.index("function _applyShared(payload)"):]
    block = block[: block.index("function _initShareDrain()")]
    assert "addFiles(files)" in block
    assert "S.pendingFiles.push" not in block


def test_share_target_is_csrf_exempt_with_the_reason_recorded():
    """The POST is synthesised by the OS share sheet, so no session token can
    exist. Exempting it is only defensible because it writes no server state."""
    block = ROUTES[ROUTES.index("def _csrf_exempt_path"):]
    block = block[: block.index("_CSRF_FAILURE_ATTR")]
    assert '"/share-target"' in block
    assert "no server state" in block.lower() or "changes NO server state" in block


def test_the_server_fallback_always_redirects():
    """Malformed form, oversized body, no body at all: the user made a
    deliberate gesture in another app, and a browser error page reads as "this
    app is broken" rather than "try again"."""
    block = ROUTES[ROUTES.index("def _handle_share_target"):]
    block = block[: block.index("\ndef handle_post")]
    assert "except Exception:" in block
    assert block.count("handler.send_response(303)") == 1, (
        "there should be exactly one exit, so no error path can skip it"
    )
    assert "had_files = False" in block.split("try:")[0], (
        "both accumulators must be bound before the try, or an early exception "
        "leaves one unbound and the handler raises instead of redirecting"
    )


def test_the_server_fallback_flags_dropped_files_instead_of_hiding_them():
    assert "share_files_dropped" in ROUTES
    assert "share_files_dropped" in BOOT, "the UI must explain the flag"
    assert "share_files_dropped" in NATIVE, (
        "and strip it, or a reload re-shows the note forever"
    )


# ── #2 Web Share ─────────────────────────────────────────────────────────────


def test_share_distinguishes_cancelled_from_failed():
    """Dismissing the OS sheet is the commonest outcome of opening one. Showing
    an error toast for it would be wrong, and falling through to "copied + opened
    a tab" does two things the user just declined."""
    block = NATIVE[NATIVE.index("function share(data)"):]
    block = block[: block.index("// ── View transitions")]
    assert "'cancelled'" in block and "'failed'" in block and "'unsupported'" in block
    assert "AbortError" in block


def test_callers_keep_their_clipboard_fallback():
    helper = BOOT[BOOT.index("async function _offerNativeShareOfLink"):]
    helper = helper[: helper.index("function _buildSessionExportUrl")]
    assert "shareSupported()" in helper
    assert "return outcome==='cancelled';" in helper, (
        "a cancelled share is handled, not retried through the copy path"
    )
    assert "_copyText" in BOOT, "the clipboard path must still exist"


def test_file_sharing_asks_canshare_before_building_a_file():
    """navigator.canShare({files}) is a separate question from navigator.share
    existing. Sharing a transcript as `text:` instead would truncate it."""
    block = BOOT[BOOT.index("$('btnDownload').onclick"):]
    block = block[: block.index("// Hand a share link")]
    assert "canShareFiles([file])" in block
    assert "new File([md],name" in block
    assert "a.download=name" in block, "the download fallback must remain"


# ── #5 App Badging ───────────────────────────────────────────────────────────


def test_badge_is_driven_from_the_one_pending_approvals_map():
    """Both the set and the clear path go through _approvalPendingBySession, so
    the badge cannot drift from what the app believes is pending."""
    assert "function _syncApprovalAppBadge()" in MESSAGES
    remember = MESSAGES[MESSAGES.index("function _rememberApprovalPending"):]
    remember = remember[: remember.index("function _clearApprovalPendingForSession")]
    assert "_syncApprovalAppBadge()" in remember
    clear = MESSAGES[MESSAGES.index("function _clearApprovalPendingForSession"):]
    clear = clear[: clear.index("\n}")]
    assert "_syncApprovalAppBadge()" in clear


def test_badge_sync_is_typeof_guarded():
    """Several tests extract these functions alone into a bare vm context, where
    a hard reference to a sibling is a ReferenceError — and the badge really is
    optional, so the guard states the truth."""
    assert "typeof _syncApprovalAppBadge === 'function'" in MESSAGES


def test_badge_counts_every_waiting_session_not_just_the_open_one():
    block = MESSAGES[MESSAGES.index("function _syncApprovalAppBadge()"):]
    block = block[: block.index("function _rememberApprovalPending")]
    assert "_approvalPendingBySession.forEach" in block, (
        "three sessions each waiting on an approval is three things to answer"
    )


def test_badge_skips_no_op_writes():
    """The approval poller runs every couple of seconds and each call is an IPC
    hop to the OS shell."""
    block = NATIVE[NATIVE.index("function setBadge(count)"):]
    block = block[: block.index("function clearBadge")]
    assert "_lastBadge" in block
    assert "return Promise.resolve(true)" in block


def test_badge_calls_are_caught_not_feature_detected_alone():
    """`'setAppBadge' in navigator` is true in a plain tab, where the call still
    rejects — the API is installed-only."""
    block = NATIVE[NATIVE.index("function setBadge(count)"):]
    block = block[: block.index("function clearBadge")]
    assert "function () { return false; }" in block or "catch" in block


def test_the_push_handler_sets_a_badge_without_inventing_a_count():
    """The payload carries no count. setAppBadge() with no argument is the spec's
    "unspecified number" — a dot, rather than a number that is wrong."""
    block = SW[SW.index("if (payload.kind === 'approval')"):]
    block = block[: block.index("event.waitUntil(\n    self.clients.matchAll")]
    assert "self.navigator.setAppBadge()" in block
    assert "setAppBadge(1)" not in block


# ── #7 View Transitions ──────────────────────────────────────────────────────


def test_view_transition_always_runs_its_callback():
    """The single most important property in this file.

    viewTransition() wraps a load-bearing DOM update. If an unsupported browser,
    reduced-motion, an in-flight transition or a hidden tab caused the callback
    to be skipped, the UI would stop responding to navigation — a spectacular
    failure for a cosmetic feature.
    """
    block = NATIVE[NATIVE.index("function viewTransition(update, opts)"):]
    block = block[: block.index("// ── Share Target inbox")]
    guard = block[: block.index("var name =")]
    assert "update();" in guard, "the early-return path must still run the update"
    for condition in (
        "!viewTransitionsSupported()",
        "_prefersReducedMotion()",
        "_transitionActive",
        "document.visibilityState === 'hidden'",
    ):
        assert condition in guard, f"viewTransition must bail out on {condition}"
    # And the throwing path.
    assert "catch (_e)" in block and block.count("update();") >= 3


def test_view_transition_handles_the_rejected_finished_promise():
    """`.finished` rejects when a transition is skipped. Unhandled, that is a
    console error on an ordinary double-tap."""
    block = NATIVE[NATIVE.index("function viewTransition(update, opts)"):]
    block = block[: block.index("// ── Share Target inbox")]
    assert "Promise.resolve(tr.finished).then(done, done)" in block, (
        "both handlers must clean up, or _transitionActive latches true and "
        "every later transition is skipped"
    )


def test_panel_switch_keeps_network_work_outside_the_transition():
    """A transition holds a visual snapshot until its callback settles. An
    `await loadX()` inside would freeze the UI for the length of a request."""
    fn = PANELS[PANELS.index("const _applyPanelViewSwap = () => {"):]
    callback = fn[: fn.index("\n  };")]
    assert "await" not in callback, "no awaits inside the transition callback"
    assert "loadCrons" not in callback and "loadKanban" not in callback
    after = fn[fn.index("\n  };"):]
    assert "await loadCrons()" in after, "the lazy loads must follow the swap"


def test_panel_switch_does_not_animate_a_switch_to_the_same_panel():
    fn = PANELS[PANELS.index("const _applyPanelViewSwap = () => {"):]
    assert "prevPanel !== nextPanel" in fn, (
        "re-selecting the current panel would cross-fade the screen with itself"
    )
    assert "_applyPanelViewSwap();" in fn, "and must still apply the swap"


def test_view_transition_css_is_entirely_inside_supports():
    """Progressive enhancement means the stylesheet cannot assume the feature."""
    block = CSS[CSS.index("/* ── View Transitions (P4.2 #7)"):]
    assert "@supports (view-transition-name: none)" in block
    supports_idx = block.index("@supports (view-transition-name: none)")
    for selector in ("::view-transition-old", "view-transition-name: hermes-main"):
        assert block.index(selector) > supports_idx


def test_view_transition_css_respects_reduced_motion():
    """viewTransition() already refuses to start one, but a UA-initiated
    transition would not go through that check."""
    block = CSS[CSS.index("/* ── View Transitions (P4.2 #7)"):]
    assert "prefers-reduced-motion: reduce" in block
    assert "animation: none !important" in block


# ── #8 Haptics ───────────────────────────────────────────────────────────────


def test_haptics_are_gated_on_user_activation():
    """Not defensive coding: Chromium logs "Blocked call to navigator.vibrate
    because user hasn't tapped on the frame" to the console, and this repo has a
    smoke test asserting zero console output."""
    assert "_hasUserActivation()" in NATIVE
    assert "navigator.userActivation" in NATIVE


def test_haptics_have_an_off_switch_that_defaults_on():
    block = NATIVE[NATIVE.index("function hapticsEnabled()"):]
    block = block[: block.index("function _hasUserActivation")]
    assert "!== 'false'" in block, "default on; only an explicit 'false' disables"
    assert "HAPTIC_PREF_KEY" in NATIVE


def test_haptics_fire_on_the_taps_that_change_something():
    """Send and approval — the two irreversible taps. A buzz on navigation would
    be noise."""
    assert "window.HermesNative.haptic('tap')" in MESSAGES, "send"
    assert "haptic(choice === 'deny' ? 'warn' : 'confirm')" in MESSAGES, "approval"


def test_the_approval_haptic_fires_on_the_tap_not_after_the_round_trip():
    """A buzz that arrives 400 ms later reads as a glitch, not as confirmation."""
    block = MESSAGES[MESSAGES.index("async function respondApproval(choice"):]
    haptic_idx = block.index("window.HermesNative.haptic(")
    post_idx = block.index('api("/api/approval/respond"')
    assert haptic_idx < post_idx, "the haptic must precede the POST"


def test_haptic_durations_stay_short():
    """Past ~30 ms a buzz reads as an error, and a long pattern as an alarm."""
    block = NATIVE[NATIVE.index("function haptic(kind)"):]
    block = block[: block.index("// ── App badge")]
    numbers = [int(n) for n in re.findall(r"\b(\d+)\b", block.split("var ms =")[1].split(";")[0])]
    assert numbers and max(numbers) <= 40, f"haptic durations too long: {numbers}"


# ── Already shipped: regression pins for #3, #4, #9 ──────────────────────────


def test_optimistic_ui_renders_the_user_turn_before_the_post():
    """P4.2 #3, already present. This is what makes a send feel committed on a
    slow mobile connection."""
    push_idx = MESSAGES.index("S.messages.push(userMsg);renderMessages();setBusy(true);")
    post_idx = MESSAGES.index("api('/api/chat/start'")
    assert push_idx < post_idx, (
        "the user bubble must render before the network call, not after it"
    )


def test_the_session_list_has_a_skeleton_not_a_spinner():
    """P4.2 #4, already present — including an "honest skeleton" path that shows
    an empty-state placeholder for profiles known to have no sessions, rather
    than implying data that never arrives."""
    assert "showSessionListSkeleton" in SESSIONS
    assert ".skeleton-row{" in CSS
    assert ".skeleton-bar{" in CSS
    skeleton_css = CSS[CSS.index(".skeleton-row{"):]
    assert "prefers-reduced-motion" in skeleton_css[:4000], (
        "the shimmer must be suppressible"
    )


def test_hands_free_voice_mode_exists_with_tts():
    """P4.2 #9, already present: turn-based voice mode (#1333) chains
    listen -> send -> TTS -> listen."""
    assert "Turn-based voice mode" in BOOT
    assert "speechSynthesis" in BOOT
    assert "SpeechSynthesisUtterance" in BOOT
    assert "hermes-tts-voice" in BOOT, "voice preference"
    assert "_startListening" in BOOT, "the loop back to listening is the feature"


def test_the_roadmap_claim_of_zero_of_nine_is_recorded_as_wrong():
    """A guard against re-deleting the three that already shipped.

    If someone reads "zero of nine exist" and rebuilds #3, #4 or #9, they get
    two implementations of the same behaviour. The correction lives in this
    file's docstring and in MOBILE-WEB-DEVELOPMENT.md §0.12.
    """
    doc = (REPO / "MOBILE-WEB-DEVELOPMENT.md").read_text(encoding="utf-8")
    assert "0.12" in doc, "the P4 execution notes must exist"
    assert __doc__ and "Three of the nine were already shipped" in __doc__
