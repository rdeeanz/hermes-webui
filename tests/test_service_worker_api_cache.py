"""Regression tests for service worker API cache exclusion under subpath mounts.

The WebUI can be served at /hermes/. In that deployment API requests look like
/hermes/api/sessions, not /api/sessions. The service worker must treat those as
network-only; otherwise cache-first handling can serve a stale sidebar session
list until the browser cache/service-worker cache is cleared.

SCOPE CHANGE
  "No API response is ever cached" was the rule when this file was written, and
  it was also why the offline shell had nothing to show: a complete app shell
  with no data renders an empty sidebar and an empty chat.

  Exactly two pure-read endpoints are cached now — GET …/api/sessions and
  GET …/api/session — in a separate `hermes-data-v1` cache, and the contracts
  around that live in tests/test_offline_shell_and_outbox.py. The rule this file
  still enforces is the boundary: EVERY OTHER API path, plus /stream and
  /health, is network-only under both root and subpath mounts.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SW_SRC = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    """Drop whole-line comments.

    Several assertions here ban a substring, and sw.js now explains in prose why
    it does the thing being banned. Scanning raw text would fail on the
    explanation and push someone to delete it rather than keep the property.
    """
    out, in_block = [], False
    for line in src.splitlines():
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*"):
            if "*/" not in s:
                in_block = True
            continue
        if s.startswith("//") or s.startswith("*"):
            continue
        out.append(line)
    return "\n".join(out)


def test_service_worker_excludes_subpath_mounted_api_routes_from_cache():
    assert "url.pathname.includes('/api/')" in SW_SRC, (
        "service worker must bypass cache for subpath-mounted API routes like "
        "/hermes/api/sessions, not only root-mounted /api/*"
    )


def test_service_worker_excludes_subpath_mounted_health_routes_from_cache():
    assert "url.pathname.includes('/health')" in SW_SRC, (
        "service worker must bypass cache for subpath-mounted health routes like "
        "/hermes/health, not only root-mounted /health"
    )


def test_service_worker_documents_which_api_routes_bypass_the_cache():
    assert "Every other API and streaming endpoint" in SW_SRC
    assert "always go to network" in SW_SRC


def test_only_the_two_named_read_endpoints_are_ever_answered_from_cache():
    """The boundary, stated as code rather than as a comment.

    A third endpoint appearing here would be a real decision — it means shipping
    someone a stale answer — so it should not be possible to add one by accident.
    """
    code = _code_only(SW_SRC)
    patterns = re.findall(r"^const (API_\w+_RE) = (/.*/);$", code, re.MULTILINE)
    assert sorted(name for name, _ in patterns) == [
        "API_SESSION_DETAIL_RE",
        "API_SESSION_LIST_RE",
    ], f"the set of cached API endpoints changed: {patterns}"
    for _name, pattern in patterns:
        assert pattern.endswith("$/"), (
            f"{pattern} must be anchored to the end of the path, or it also "
            f"matches the SSE siblings (/api/sessions/events, "
            f"/api/sessions/gateway/stream) and hands an EventSource a cached body"
        )


def test_a_cached_api_response_is_only_ever_served_for_a_get():
    code = _code_only(SW_SRC)
    dispatch = code[code.index("API_SESSION_LIST_RE.test") - 400: code.index("API_SESSION_LIST_RE.test")]
    assert "method === 'GET'" in dispatch, (
        "the cached-endpoint branch must be gated on GET; a cached response for a "
        "POST would silently swallow a write"
    )


def test_service_worker_does_not_intercept_its_own_script():
    assert "url.pathname.endsWith('/sw.js')" in SW_SRC, (
        "service worker must bypass /sw.js so a stale cached worker cannot block cache-version updates"
    )


def test_service_worker_uses_network_first_for_page_navigation():
    """Page navigations must hit the server before cache so expired auth redirects work."""
    navigate_idx = SW_SRC.find("event.request.mode === 'navigate'")
    assert navigate_idx != -1, "service worker must special-case page navigations"
    fetch_idx = SW_SRC.find("fetch(new Request(event.request, { cache: 'no-store' }))", navigate_idx)
    cache_idx = SW_SRC.find("caches.match", navigate_idx)
    assert fetch_idx != -1, "navigation branch must try the live server first while bypassing HTTP cache"
    assert cache_idx != -1, "navigation branch may use cached shell only as offline fallback"
    assert fetch_idx < cache_idx, (
        "navigation requests must be network-first, not cache-first, so auth redirects "
        "and freshly set login cookies are honored without a manual refresh"
    )


def test_service_worker_does_not_precache_page_shell_under_auth():
    """Do not cache './' during install; it may be the authenticated app or login redirect."""
    shell_block = SW_SRC[SW_SRC.find("const SHELL_ASSETS"):SW_SRC.find("];", SW_SRC.find("const SHELL_ASSETS"))]
    shell_block = _code_only(shell_block)
    assert "'./'" not in shell_block and '"./"' not in shell_block, (
        "pre-caching './' can serve a stale authenticated app shell while logged out; "
        "navigation should populate shell cache only after a successful non-redirect network load"
    )


def test_service_worker_never_caches_login_page_or_login_script():
    assert "url.pathname.endsWith('/login')" in SW_SRC or "url.pathname.includes('/login')" in SW_SRC, (
        "service worker must bypass the login page so stale auth UI cannot survive until cache clear"
    )
    assert "url.pathname.endsWith('/static/login.js')" in SW_SRC, (
        "service worker must bypass static/login.js so stale login handlers cannot block password submit"
    )


def test_service_worker_only_cache_puts_shell_assets_or_valid_navigation_shell():
    assert "SHELL_ASSETS.includes(shellPath)" in SW_SRC, (
        "non-navigation cache puts must be limited to the explicit app shell asset allowlist; "
        "a generic cache-first handler can trap stale login.js until users clear cache"
    )
