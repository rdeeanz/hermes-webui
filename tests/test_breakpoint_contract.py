"""Breakpoint contract — CSS and JS must agree on what "phone" and "tablet" mean.

WHY THIS EXISTS
  The workspace panel used to be completely unopenable between 641px and 900px.
  Both halves of the code were individually correct:

    static/boot.js    _isCompactWorkspaceViewport() -> matchMedia('(max-width: 900px)')
    static/style.css  .rightpanel.mobile-open       -> only inside @media(max-width:640px)

  JS therefore added the `mobile-open` class across the whole 641-900px band while
  CSS had no rule that responded to it there, and `.rightpanel{display:none}` from
  the 900px block hid the panel outright. Nothing failed loudly — the button was
  visible, the click handler ran, and nothing happened on screen.

  Static CSS/JS source assertions could not catch that: every individual rule was
  present and valid. What was missing was a shared definition. This test supplies
  it: the layout breakpoints are declared once per language and pinned together.

WHAT IT ENFORCES
  1. style.css declares --bp-phone / --bp-tablet in :root.
  2. boot.js declares BP.PHONE / BP.TABLET with the same numbers.
  3. No stylesheet or script introduces a THIRD layout breakpoint. Cosmetic
     breakpoints (small type/padding tweaks) are allowed from an explicit
     allowlist so this stays a layout guard rather than a style freeze.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).parent.parent
CSS = (REPO / "static" / "style.css").read_text(encoding="utf-8")
BOOT = (REPO / "static" / "boot.js").read_text(encoding="utf-8")

# The two sanctioned layout breakpoints. Everything that decides whether a panel
# is in-flow, an overlay, or absent must key off one of these.
PHONE = 640
TABLET = 1024

# Cosmetic-only widths: font sizes, paddings, label truncation, grid columns
# inside an already-placed panel. These never move a panel between layout modes.
# Adding a width here is a deliberate statement that it does not change layout.
COSMETIC_WIDTHS = {340, 420, 520, 560, 600, 700, 768, 900, 1400, 1600, 1800}


def _css_token(name):
    m = re.search(rf"--{name}\s*:\s*(\d+)px", CSS)
    assert m, f"style.css :root must declare --{name}"
    return int(m.group(1))


def _boot_constant(name):
    m = re.search(rf"\b{name}\s*:\s*(\d+)", BOOT)
    assert m, f"boot.js must declare BP.{name}"
    return int(m.group(1))


def test_css_declares_breakpoint_tokens():
    assert _css_token("bp-phone") == PHONE
    assert _css_token("bp-tablet") == TABLET


def test_boot_declares_breakpoint_constants():
    assert "const BP = Object.freeze(" in BOOT, (
        "boot.js must declare the frozen BP contract object"
    )
    assert _boot_constant("PHONE") == PHONE
    assert _boot_constant("TABLET") == TABLET


def test_css_and_js_breakpoints_are_identical():
    """The whole point: the two languages must not drift apart."""
    assert _css_token("bp-phone") == _boot_constant("PHONE"), (
        "--bp-phone in style.css and BP.PHONE in boot.js have diverged. "
        "They describe the same boundary and must be changed together."
    )
    assert _css_token("bp-tablet") == _boot_constant("TABLET"), (
        "--bp-tablet in style.css and BP.TABLET in boot.js have diverged. "
        "They describe the same boundary and must be changed together."
    )


def test_boot_derives_viewport_helpers_from_the_contract():
    """The helpers must interpolate BP, not re-hardcode the numbers."""
    for helper in (
        "_isPhoneWidthViewport",
        "_isTabletWidthViewport",
        "_isDesktopWidthViewport",
    ):
        assert f"function {helper}(" in BOOT, f"boot.js must define {helper}()"

    # _isCompactWorkspaceViewport is the predicate that caused the original bug.
    # It must be expressed in terms of the desktop boundary rather than its own
    # literal, so it can never again disagree with the slide-over CSS.
    m = re.search(
        r"function _isCompactWorkspaceViewport\(\)\{(?P<body>.*?)\n\}", BOOT, re.S
    )
    assert m, "boot.js must define _isCompactWorkspaceViewport()"
    body = m.group("body")
    assert "_isDesktopWidthViewport()" in body, (
        "_isCompactWorkspaceViewport() must derive from _isDesktopWidthViewport() "
        "so it cannot drift from the slide-over CSS boundary again"
    )
    assert not re.search(r"\d{3}", body), (
        "_isCompactWorkspaceViewport() must not hardcode a pixel width"
    )


def _media_widths(text):
    """Every width mentioned in a min-width/max-width media query."""
    return {
        int(w)
        for w in re.findall(r"@media[^{]*?(?:min|max)-width\s*:\s*(\d+)px", text)
    }


def _js_media_widths(text):
    """Every width mentioned in a matchMedia() call, ignoring template literals."""
    return {
        int(w)
        for w in re.findall(r"matchMedia\(\s*['\"][^'\"]*?(?:min|max)-width\s*:\s*(\d+)px", text)
    }


def test_no_unsanctioned_layout_breakpoint_in_css():
    allowed = {PHONE, PHONE + 1, TABLET, TABLET + 1} | COSMETIC_WIDTHS
    stray = _media_widths(CSS) - allowed
    assert not stray, (
        f"style.css introduces unsanctioned breakpoint(s): {sorted(stray)}. "
        f"Reuse --bp-phone ({PHONE}) or --bp-tablet ({TABLET}), or add the width "
        f"to COSMETIC_WIDTHS in this test if it genuinely changes no layout."
    )


def test_no_unsanctioned_layout_breakpoint_in_js():
    allowed = {PHONE, PHONE + 1, TABLET, TABLET + 1} | COSMETIC_WIDTHS
    offenders = {}
    for js in sorted((REPO / "static").glob("*.js")):
        stray = _js_media_widths(js.read_text(encoding="utf-8")) - allowed
        if stray:
            offenders[js.name] = sorted(stray)
    assert not offenders, (
        f"unsanctioned matchMedia breakpoint(s): {offenders}. "
        f"Derive the width from the BP contract in boot.js instead."
    )
