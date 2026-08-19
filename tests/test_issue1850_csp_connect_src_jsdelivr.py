"""Regression test for #1850 — CSP connect-src must allow the lazy CDN libraries.

Originally this covered xterm.js, whose bundled source map was fetched from
cdn.jsdelivr.net at runtime. xterm and Prism are vendored under static/vendor now
(with sourceMappingURL stripped), so the remaining consumers are the two modules
ui.js still imports lazily from the CDN: PDF.js (workspace PDF preview) and
Mermaid (diagram rendering). Their fetches are subject to connect-src, so the
policy must keep allowing them or the browser blocks the import and emits CSP
violations.

The grant is now path-scoped rather than whole-origin — see _CSP_JSDELIVR_LAZY_LIBS
in api/helpers.py.
"""
import re

from api.helpers import _build_csp_enforced_policy


def _policy() -> str:
    return _build_csp_enforced_policy("")


class TestCSPConnectSrcJsdelivr:
    """connect-src must allow cdn.jsdelivr.net for xterm source map fetches."""

    def test_connect_src_includes_jsdelivr(self):
        """connect-src must include https://cdn.jsdelivr.net."""
        policy = _policy()
        connect_match = re.search(r"connect-src\s+([^;]+);", policy)
        assert connect_match, "connect-src directive must exist in CSP"
        assert "https://cdn.jsdelivr.net" in connect_match.group(1), (
            "connect-src must allow cdn.jsdelivr.net — xterm.js source maps are "
            "fetched from that origin and the CSP blocks them without this entry"
        )

    def test_connect_src_still_includes_self(self):
        """connect-src must still include 'self' alongside the new jsdelivr entry."""
        policy = _policy()
        connect_match = re.search(r"connect-src\s+([^;]+);", policy)
        assert connect_match, "connect-src directive must exist in CSP"
        assert "'self'" in connect_match.group(1), (
            "connect-src must retain 'self' after adding cdn.jsdelivr.net"
        )
