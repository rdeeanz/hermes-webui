"""The offline shell, the read-only API cache, and the send queue.

WHY THIS EXISTS
  The service worker registered, pre-cached the app shell, and enabled "Add to
  Home Screen" — and then, offline, produced this:

      '<h2>You are offline</h2>'

  A literal string, telling the reader something they already knew. Meanwhile
  three separate things were quietly wrong:

    1. Two files index.html loads on every cold path (outline.js,
       extension_settings.js) were simply missing from SHELL_ASSETS, so an
       offline boot came up without them.
    2. Three pre-cached entries carried `?v=<version>` while the page requested
       them WITHOUT it (smd.min.js, katex.min.css) or vice versa
       (katex.min.js) — so those cache lookups always missed and the bytes were
       downloaded on install for nothing.
    3. No API response was cached at all, so even a complete shell had no data
       to render: the session list and the transcript were both empty.

  Nothing in the suite could see any of it, because every existing assertion was
  about the presence of a rule rather than the agreement between two lists.

  Test 1 below is the generic form of the first two: it derives what index.html
  actually requests and compares it to what sw.js actually pre-caches, so a new
  <script> tag is inside the contract from the moment someone writes it.

WHAT IS DELIBERATELY NOT COVERED HERE
  Runtime behaviour of the cache strategies — that a cached list really is served
  while offline, that /api/sessions/events really is not intercepted — needs a
  browser with a live service worker, not a source read. Those were verified
  against a real Chromium; these tests pin the source-level decisions that make
  them true so a refactor cannot silently undo one.
"""

import re
from pathlib import Path

REPO = Path(__file__).parent.parent
STATIC = REPO / "static"

SW = (STATIC / "sw.js").read_text(encoding="utf-8")
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
OUTBOX = (STATIC / "outbox.js").read_text(encoding="utf-8")
OFFLINE_HTML = (STATIC / "offline.html").read_text(encoding="utf-8")
SESSIONS_JS = (STATIC / "sessions.js").read_text(encoding="utf-8")
MESSAGES_JS = (STATIC / "messages.js").read_text(encoding="utf-8")
PANELS_JS = (STATIC / "panels.js").read_text(encoding="utf-8")


def _code(src: str) -> str:
    """Drop whole-line comments.

    Necessary, not fastidious: several assertions below ban a substring
    ("localStorage", "registration.sync", "innerHTML"), and the files under test
    explain in prose WHY they avoid exactly those things. A raw substring scan
    fails on the explanation, which pressures the next person to delete the
    explanation rather than keep the property.

    Only whole-line comments are removed -- a naive `//` strip would also eat the
    tail of any line containing a URL or a regex ending in `sessions$/`.
    """
    out = []
    in_block = False
    for line in src.splitlines():
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*") or stripped.startswith("<!--"):
            if "*/" not in stripped and "-->" not in stripped:
                in_block = True
            continue
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        out.append(line)
    return "\n".join(out)


def _shell_assets() -> set[str]:
    """The SHELL_ASSETS entries, with the VQ concatenation resolved.

    Parsed rather than hardcoded for the same reason as the payload budget:
    a hardcoded copy is the thing that goes stale.
    """
    block = SW[SW.index("const SHELL_ASSETS = ["): SW.index("];", SW.index("const SHELL_ASSETS = ["))]
    entries = set()
    for raw, has_vq in re.findall(r"'(\./[^']+)'(\s*\+\s*VQ)?", block):
        entries.add(raw + ("?v=__WEBUI_VERSION__" if has_vq else ""))
    return entries


def _index_eager_requests() -> set[str]:
    """Every JS/CSS URL index.html pulls in on a cold load, as requested.

    Includes the inline `import` (smd) because that is a real cold-path request
    the service worker has to be able to match, and it is precisely the one that
    was mismatched.
    """
    refs = set(re.findall(r'<script[^>]*\ssrc="(static/[^"]+)"', INDEX))
    for tag in re.findall(r"<link\b[^>]*>", INDEX):
        if 'rel="stylesheet"' in tag:
            m = re.search(r'\shref="(static/[^"]+)"', tag)
            if m:
                refs.add(m.group(1))
    refs |= set(re.findall(r"import \* as \w+ from '\./(static/[^']+)'", INDEX))
    # The reader's own language bundle is built at runtime from localStorage, so
    # its URL contains a JS expression rather than a path. A service worker
    # cannot know which language it is; core.js is pre-cached instead.
    return {r for r in refs if "'+" not in r and "+'" not in r}


# ── 1. The two lists must agree ──────────────────────────────────────────────


def test_every_eager_cold_path_asset_is_precached():
    """The gap that left outline.js and extension_settings.js out of the shell."""
    shell = _shell_assets()
    missing = sorted(
        rel for rel in _index_eager_requests() if "./" + rel not in shell
    )
    assert not missing, (
        f"index.html loads {missing} on every cold path, but sw.js does not "
        f"pre-cache them — so an offline boot comes up without them. Add "
        f"'./{missing[0]}' to SHELL_ASSETS (with + VQ if the URL carries ?v=)."
    )


def test_precached_urls_match_the_urls_the_page_requests():
    """A pre-cache entry whose query differs from the request never serves.

    It is worse than not pre-caching: the bytes are downloaded at install time
    and then every lookup misses anyway.
    """
    shell = _shell_assets()
    for rel in sorted(_index_eager_requests()):
        entry = "./" + rel
        if entry not in shell:
            continue  # covered by the test above
        page_has_query = "?v=__WEBUI_VERSION__" in rel
        cache_has_query = "?v=__WEBUI_VERSION__" in entry
        assert page_has_query == cache_has_query, (
            f"static/{rel.split('?')[0]}: index.html requests it "
            f"{'with' if page_has_query else 'without'} ?v= but sw.js pre-caches it "
            f"{'with' if cache_has_query else 'without'} it — the lookup can never match"
        )


def test_lazy_vendor_that_renders_cached_content_is_precached():
    """The criterion is 'can it read cached content without a server?'.

    KaTeX and js-yaml can (math and YAML blocks inside an already-cached
    transcript). xterm cannot — a terminal is a live PTY — and PDF.js/Mermaid are
    too heavy to spend on every install for a fallback that already degrades
    gracefully.
    """
    shell = _shell_assets()
    for rel in (
        "./static/vendor/katex/0.16.22/katex.min.js",
        "./static/vendor/katex/0.16.22/katex.min.css",
        "./static/vendor/js-yaml/4.1.0/js-yaml.min.js",
    ):
        assert rel + "?v=__WEBUI_VERSION__" in shell, f"{rel} must be pre-cached"
    for rel in (
        "./static/vendor/xterm/5.3.0/xterm.js",
        "./static/vendor/pdfjs/4.9.155/pdf.min.mjs",
        "./static/vendor/mermaid/10.9.3/mermaid.min.js",
    ):
        assert not any(e.startswith(rel) for e in shell), (
            f"{rel} must NOT be pre-cached — it needs a live backend or is too "
            f"heavy to spend on every install"
        )


def test_mjs_is_a_known_static_mime_type():
    """PDF.js ships as .mjs, and a browser refuses an ES module served as text/plain.

    There is no override for this and no console message that names the cause:
    the import just fails and the preview silently degrades to a download link.
    """
    routes = (REPO / "api" / "routes.py").read_text(encoding="utf-8")
    block = routes[routes.index("_STATIC_MIME = {"):]
    block = block[: block.index("}")]
    assert '"mjs": "application/javascript"' in block, (
        "api/routes.py _STATIC_MIME must map mjs, or static/vendor/pdfjs/*.mjs is "
        "served as text/plain and the browser refuses to execute it"
    )


# ── 2. The read-only API cache ───────────────────────────────────────────────


def test_data_cache_is_not_version_keyed_and_survives_the_shell_purge():
    """A deploy must not cost the user the sessions they can read offline."""
    assert "const DATA_CACHE = 'hermes-data-v1';" in SW
    assert "'hermes-data-__WEBUI_VERSION__'" not in SW, (
        "the data cache must not be version-keyed, or every deploy empties the "
        "offline shell for exactly the people who update most often"
    )
    purge = SW[SW.index("function deleteOldShellCaches()"):]
    purge = purge[: purge.index("\n}")]
    assert "k !== DATA_CACHE" in purge, (
        "deleteOldShellCaches() drops every cache that is not the current shell; "
        "without an explicit exemption it wipes the data cache on every bump"
    )


def test_only_the_two_read_endpoints_are_cached():
    assert "const API_SESSION_LIST_RE = /(?:^|\\/)api\\/sessions$/;" in SW
    assert "const API_SESSION_DETAIL_RE = /(?:^|\\/)api\\/session$/;" in SW


def test_endpoint_patterns_are_anchored_so_sse_siblings_fall_through():
    """/api/sessions/events and /api/sessions/gateway/stream are EventSource.

    An unanchored pattern would match them, and handing a cached body to an
    EventSource breaks real-time sync in a way that looks like a server bug.
    """
    for name in ("API_SESSION_LIST_RE", "API_SESSION_DETAIL_RE"):
        line = next(ln for ln in SW.splitlines() if ln.startswith(f"const {name}"))
        assert line.rstrip().endswith("$/;"), (
            f"{name} must be anchored to the end of the path, or it matches the "
            f"streaming siblings under the same prefix"
        )


def test_only_get_is_ever_answered_from_the_cache():
    block = SW[SW.index("// The two read endpoints that back the offline shell"):]
    block = block[: block.index("// Every other API and streaming endpoint")]
    assert "event.request.method === 'GET'" in block, (
        "a cached response must never be served for a POST/PUT/DELETE"
    )


def test_nothing_but_a_real_200_json_response_is_stored():
    """A 302 to /login arrives as a redirected HTML 200.

    Storing that as "your session list" means an offline shell that shows a login
    form forever, with no way for the user to tell why.
    """
    guard = SW[SW.index("function _isCacheableApiResponse"):]
    guard = guard[: guard.index("\n}")]
    for required in (
        "response.status === 200",
        "!response.redirected",
        "opaqueredirect",
        "application/json",
    ):
        assert required in guard, f"_isCacheableApiResponse must check {required}"


def test_expired_auth_purges_the_data_cache():
    assert "response.status === 401 || response.status === 403" in SW
    assert "_purgeDataCache()" in SW
    assert "function _purgeDataCache" in SW
    assert "caches.delete(DATA_CACHE)" in SW


def test_logout_purges_the_data_cache_and_the_outbox():
    """The data cache outlives version bumps, so sign-out has to be explicit.

    Otherwise the next person to open the app on a shared device boots offline
    into the previous reader's session list.
    """
    sign_out = PANELS_JS[PANELS_JS.index("async function signOut()"):]
    sign_out = sign_out[: sign_out.index("\n}")]
    assert "_purgeOfflineDataCache()" in sign_out
    assert "HermesOutbox" in sign_out and "clear()" in sign_out, (
        "unsent messages belong to the account that queued them, not the device"
    )
    assert "'hermes:purge-data-cache'" in SW, "sw.js must handle the purge message"
    assert "'hermes:purge-data-cache'" in PANELS_JS


# ── 3. Stale-while-revalidate is opt-in ──────────────────────────────────────


def test_swr_requires_an_explicit_request_header():
    """Applying SWR to every /api/sessions call would be wrong.

    A profile switch refetches the list; served from cache, it would flash the
    previous profile's sessions. Opting in per request confines the stale read to
    the one place the alternative is a skeleton — the cold boot.
    """
    assert "event.request.headers.get('X-Hermes-Cache') === 'swr'" in SW
    dispatch = SW[SW.index("const wantsSwr"):]
    dispatch = dispatch[: dispatch.index("return;")]
    assert "_staleWhileRevalidate(event)" in dispatch
    assert "_networkFirstApi(event)" in dispatch, (
        "without the header the request must stay network-first"
    )


def test_the_page_only_asks_for_swr_on_the_cold_sidebar_load():
    block = SESSIONS_JS[SESSIONS_JS.index("if(!_sessionListHasLoadedOnce){"):]
    block = block[: block.index("\n    }")]
    assert "'X-Hermes-Cache':'swr'" in block, (
        "the cold sidebar load should ask for stale-while-revalidate"
    )
    assert SESSIONS_JS.count("'X-Hermes-Cache':'swr'") == 1, (
        "only the cold load may opt into SWR; a later poll served from cache can "
        "show the wrong profile's sessions"
    )


def test_the_page_is_told_to_re_render_only_when_the_data_actually_changed():
    """This is what stops SWR from looping.

    Serve cache -> notify -> page refetches -> serve cache -> notify -> ... is a
    live-lock. Comparing bodies makes the second pass find them equal, so the
    notification stops on its own.
    """
    swr = SW[SW.index("function _staleWhileRevalidate"):]
    swr = swr[: swr.index("\n}")]
    assert "body !== oldBody" in swr, (
        "the client notification must be gated on the fresh body differing from "
        "the one that was served, or every cold boot triggers an endless refresh"
    )
    assert "'hermes:sessions-updated'" in swr
    assert "'hermes:sessions-updated'" in PANELS_JS, (
        "nothing listens for the message, so the stale render is never corrected"
    )


# ── 4. The offline shell ─────────────────────────────────────────────────────


def test_the_offline_literal_is_the_last_resort_not_the_first():
    fallback = SW[SW.index("      }).catch(() => {"):]
    fallback = _code(fallback[: fallback.index("\n    );")])
    order = [
        fallback.index("caches.match('./')"),
        fallback.index("offline.html"),
        fallback.index("You are offline"),
    ]
    assert order == sorted(order), (
        "the offline navigation fallback must try the cached app shell first, "
        f"then static/offline.html, and only then the inline string: {order}"
    )


def test_offline_page_makes_no_external_requests():
    """It is the page you get when there is no network."""
    remote = re.findall(r'(?:src|href)="((?:https?:)?//[^"]+)"', OFFLINE_HTML)
    assert not remote, f"static/offline.html references remote resources: {remote}"
    assert "<img" not in OFFLINE_HTML, (
        "an image in the offline page is a request that cannot succeed"
    )


def test_offline_page_does_not_depend_on_the_app_bundles():
    """They may not be cached — that is the case this page exists for."""
    for module in ("ui.js", "sessions.js", "i18n", "boot.js"):
        assert f"static/{module}" not in OFFLINE_HTML


def test_offline_page_is_read_only():
    """Every write needs a server. A control that silently does nothing is worse
    than no control, so the page offers none."""
    assert "method: 'POST'" not in OFFLINE_HTML and 'method:"POST"' not in OFFLINE_HTML
    assert "api/chat/start" not in OFFLINE_HTML
    assert "HermesOutbox" not in OFFLINE_HTML, (
        "the offline page must only READ the queue; flushing needs the network "
        "and the app already does it on 'online'"
    )
    assert "Read-only" in OFFLINE_HTML, "say so, rather than leaving it implied"


def test_offline_page_renders_transcript_content_as_text():
    """It renders session content, which is attacker-influenced in the general
    case, and the app's sanitising markdown pipeline is not available here."""
    assert "innerHTML" in OFFLINE_HTML  # used once, for a static literal
    assert re.search(r"innerHTML\s*=\s*['\"`]<div class=\"mermaid", OFFLINE_HTML) is None
    body = OFFLINE_HTML[OFFLINE_HTML.index("function loadTranscript"):]
    body = _code(body[: body.index("// ── The send queue")])
    assert "innerHTML" not in body, (
        "transcript rendering must use textContent, not innerHTML"
    )
    assert "body.textContent" in body


def test_offline_page_reads_the_same_caches_and_store_the_app_writes():
    assert "'hermes-data-v1'" in OFFLINE_HTML
    assert "'hermes-outbox'" in OFFLINE_HTML
    assert "'sends'" in OFFLINE_HTML
    # Both names must agree with the writers, or the page renders empty forever.
    assert "var DB_NAME = 'hermes-outbox';" in OUTBOX
    assert "var STORE = 'sends';" in OUTBOX


def test_offline_page_announces_its_state_to_a_screen_reader():
    assert 'aria-live="polite"' in OFFLINE_HTML
    assert 'role="status"' in OFFLINE_HTML


# ── 5. The send queue ────────────────────────────────────────────────────────


def test_outbox_uses_indexeddb_and_not_localstorage():
    """localStorage is synchronous, ~5 MB, and the first thing a 'clear site
    data' removes. This store holds the only copy of unsent work."""
    code = _code(OUTBOX)
    assert "indexedDB.open" in code
    assert "localStorage" not in code and "sessionStorage" not in code


def test_outbox_does_not_rely_on_background_sync():
    """Safari does not implement it, and iOS Safari is the likeliest place for a
    Hermes tab to be offline. A queue that only drains on Chrome fails where it
    was needed."""
    code = _code(OUTBOX)
    assert "registration.sync" not in code and "SyncManager" not in code
    assert "'sync'" not in code
    assert "addEventListener('online'" in code, (
        "the flush has to be driven by the page, so it must listen for 'online'"
    )
    assert "visibilitychange" in code, (
        "iOS does not reliably fire 'online' when a PWA is resumed from the app "
        "switcher; a visibility check covers it"
    )


def test_outbox_flush_is_serial():
    """Two sends racing into one session hit the server's active-stream conflict,
    and the queue exists so messages arrive in the order they were written."""
    assert "return step(i + 1)" in OUTBOX
    assert "Promise.all" not in OUTBOX.split("function flush()")[1]


def test_outbox_stops_on_a_network_failure_and_keeps_everything_queued():
    flush = OUTBOX[OUTBOX.index("function flush()"):]
    assert "stopped = 'offline'" in flush
    assert "stopped = 'unauthorized'" in flush, (
        "a 401 mid-flush is not the message's fault; the queue must survive "
        "until the user logs back in"
    )


def test_outbox_drops_a_permanently_rejected_send_rather_than_replaying_it():
    guard = OUTBOX[OUTBOX.index("function _isPermanentRejection"):]
    guard = guard[: guard.index("\n}")]
    assert "status !== 408" in guard and "status !== 429" in guard, (
        "a timeout or a rate limit is retryable; other 4xx are not"
    )
    assert "MAX_ATTEMPTS" in OUTBOX, "a 5xx must not be retried forever either"


def test_rejected_sends_are_surfaced_and_not_dropped_silently():
    assert "reason:'rejected'" in MESSAGES_JS or "'rejected'" in MESSAGES_JS
    listener = MESSAGES_JS[MESSAGES_JS.index("window.HermesOutbox.onChange"):]
    assert "rejected" in listener and "showToast" in listener, (
        "the user believed a queued message was on its way; if the server "
        "refuses it, say so"
    )


# ── 6. The send path that feeds the queue ────────────────────────────────────


def test_send_queues_on_a_network_failure_instead_of_erroring():
    block = MESSAGES_JS[MESSAGES_JS.index("// ── Offline: queue it, do not lose it"):]
    block = block[: block.index("// If /api/chat/start returns 404")]
    assert "e instanceof TypeError" in block, (
        "api() throws the raw fetch TypeError when nothing was reachable, and "
        "every HTTP error it raises carries a numeric .status — that pair is the "
        "signal, not a guess about connectivity"
    )
    assert "window.HermesOutbox.enqueue" in block
    assert "_restoreComposerDraftAfterFailedSend" not in block, (
        "the message is queued, so putting the draft back in the composer invites "
        "sending it twice"
    )
    assert "setBusy(false)" in block, (
        "the spinner must go, or the pane claims an agent is working when the "
        "turn has not reached a server"
    )


def test_a_refused_queue_falls_back_to_the_old_error_path():
    """Private browsing, no IndexedDB, quota exhausted. The user's text must
    survive one way or the other."""
    block = MESSAGES_JS[MESSAGES_JS.index("// ── Offline: queue it, do not lose it"):]
    block = block[: block.index("// If /api/chat/start returns 404")]
    assert "if(queuedId!==null){" in block, (
        "enqueue() resolving null means the queue did not take the message; the "
        "code must fall through to the path that restores the draft"
    )


def test_a_drained_queue_reattaches_the_running_turn():
    """The turn is running on the server but this tab has no stream attached, so
    the answer would arrive nowhere until a manual refresh."""
    listener = MESSAGES_JS[MESSAGES_JS.index("window.HermesOutbox.onChange"):]
    assert "loadSession(sid)" in listener
    assert "renderSessionList()" in listener


def test_the_queued_status_string_is_translatable():
    assert "t('offline_send_queued')" in MESSAGES_JS
    core = (STATIC / "i18n" / "core.js").read_text(encoding="utf-8")
    assert "offline_send_queued:" in core, (
        "the English fallback must exist, or t() returns the raw key"
    )
