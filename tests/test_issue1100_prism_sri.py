"""Tests for #1100 — Prism theme CSS must never be blocked by an integrity check.

The original bug: jsdelivr edge nodes served byte-different responses for the
same pinned version, so the SRI hash on prism-tomorrow.min.css failed
intermittently and syntax highlighting silently disappeared.

Prism is vendored under static/vendor/prismjs now, which removes the root cause
outright — a same-origin asset served by our own _serve_static cannot be swapped
by a third party, and SRI/crossorigin are meaningless for it. What these tests
still guard is the invariant that mattered: nothing may reintroduce an integrity
attribute (or a CDN URL) on the Prism assets, whether in the markup or in the
runtime theme swap.
"""
import re


def _html():
    with open("static/index.html") as f:
        return f.read()


def _prism_theme_tag(src):
    m = re.search(r'<link[^>]*id="prism-theme"[^>]*>', src)
    assert m, "prism-theme link must exist"
    return m.group(0)


def test_prism_theme_link_has_no_integrity():
    """The prism theme link must not carry an integrity attribute."""
    assert "integrity=" not in _prism_theme_tag(_html()), \
        "prism-theme link must not have integrity attribute (causes intermittent failures)"


def test_prism_theme_link_is_same_origin():
    """Vendored, so no crossorigin negotiation is involved at all."""
    tag = _prism_theme_tag(_html())
    assert "cdn." not in tag and "//" not in tag.split('href="')[1].split('"')[0], \
        f"prism-theme must load from static/vendor, got: {tag}"
    assert "crossorigin" not in tag, \
        "crossorigin is meaningless for a same-origin vendored stylesheet"


def test_prism_theme_version_pinned():
    """The version must stay pinned — it is encoded in the vendored path."""
    m = re.search(r'<link[^>]*id="prism-theme"[^>]*href="([^"]*)"[^>]*>', _html())
    assert m, "prism-theme link must have href"
    href = m.group(1)
    assert "/1.29.0/" in href, \
        f"Prism CSS version must be pinned in the vendored path, found href: {href}"


def test_prism_js_has_no_integrity():
    """SRI on a same-origin script adds a failure mode and buys nothing.

    The page and the script are served by the same process from the same
    directory; an attacker able to alter static/vendor can alter index.html too.
    """
    src = _html()
    for asset in ("prism-core.min.js", "prism-autoloader.min.js"):
        m = re.search(rf'<script[^>]*{re.escape(asset)}[^>]*>', src)
        assert m, f"{asset} must be loaded by index.html"
        assert "integrity=" not in m.group(0), \
            f"{asset} is vendored same-origin; integrity= only adds a failure mode"
        assert "cdn." not in m.group(0), f"{asset} must not load from a CDN"


def test_boot_js_set_resolved_theme_no_integrity():
    """_setResolvedTheme in boot.js must not re-apply integrity on theme switch."""
    with open("static/boot.js") as f:
        src = f.read()
    assert "_setResolvedTheme" in src, "_setResolvedTheme function must exist"
    assert not re.search(r'link\.integrity\s*=\s*["\']sha', src), \
        "_setResolvedTheme must not set link.integrity to an SRI hash"
    assert "wantIntegrity" not in src, \
        "wantIntegrity variable should be removed from _setResolvedTheme"
    assert re.search(r"link\.integrity\s*=\s*['\"]", src), \
        "_setResolvedTheme should clear link.integrity on theme switch"
