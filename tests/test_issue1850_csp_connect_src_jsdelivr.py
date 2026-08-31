"""Regression test for #1850 — connect-src and the CDN that no longer exists.

HISTORY
  #1850 was the opposite of what this file now asserts. xterm.js was loaded from
  cdn.jsdelivr.net, DevTools fetched its bundled source map over `connect`, and
  `connect-src 'self'` blocked it — so the fix was to ADD the CDN origin here.
  Later, Prism and xterm were vendored (with sourceMappingURL stripped) and the
  grant narrowed to two paths for the libraries ui.js still imported lazily:
  PDF.js and Mermaid.

  Both of those are vendored under static/vendor/ now, so no directive in the
  policy names a CDN. This test is kept, and inverted, because "put jsdelivr
  back in connect-src" is exactly the shape of the change someone would make
  while chasing a broken lazy import — and doing that would quietly restore
  outbound egress as a requirement for a feature that no longer needs it.

  The whole-file ban lives in tests/test_vendored_frontend_assets.py; this file
  keeps the directive-level assertion that #1850 originally introduced.
"""
import re

from api.helpers import _build_csp_enforced_policy


def _policy() -> str:
    return _build_csp_enforced_policy("")


def _directive(policy: str, name: str) -> str:
    match = re.search(rf"{name}\s+([^;]+)", policy)
    assert match, f"{name} directive must exist in CSP"
    return match.group(1)


class TestCSPConnectSrcJsdelivr:
    """connect-src must no longer name cdn.jsdelivr.net, and must keep 'self'."""

    def test_connect_src_excludes_jsdelivr(self):
        connect_src = _directive(_policy(), "connect-src")
        assert "jsdelivr" not in connect_src, (
            "connect-src names cdn.jsdelivr.net again. Every library the page "
            "loads is vendored under static/vendor/ — if a lazy import is "
            "failing, vendor it too rather than reopening egress to a CDN"
        )

    def test_connect_src_still_includes_self(self):
        connect_src = _directive(_policy(), "connect-src")
        assert "'self'" in connect_src, (
            "connect-src must retain 'self' — every API call the page makes is "
            "same-origin"
        )

    def test_no_directive_in_the_policy_names_a_cdn(self):
        """script-src and worker-src were the last two holdouts."""
        policy = _policy()
        assert "jsdelivr" not in policy, (
            f"the enforced CSP names jsdelivr again: {policy}"
        )
