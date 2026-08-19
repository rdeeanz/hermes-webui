"""
Issue #5545 three-panel desktop layout regression checks.

These tests stay source-level so they can verify the declared CSS contract
without needing a browser or rendered layout.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).parent.parent
CSS = (REPO / "static" / "style.css").read_text(encoding="utf-8")
BOOT_JS = (REPO / "static" / "boot.js").read_text(encoding="utf-8")


def _media_blocks(kind):
    pattern = re.compile(rf"@media\s*\(\s*{kind}\s*:\s*(\d+)px\s*\)\s*\{{")
    blocks = []
    for match in pattern.finditer(CSS):
        width_px = int(match.group(1))
        open_brace = match.end() - 1
        depth = 0
        for idx in range(open_brace, len(CSS)):
            if CSS[idx] == "{":
                depth += 1
            elif CSS[idx] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append((width_px, CSS[open_brace + 1:idx]))
                    break
    return blocks


def _normalize_css(css):
    return re.sub(r"\s+", "", css)


def _media_block(kind, width_px, needle):
    normalized_needle = _normalize_css(needle)
    for current_width, block in _media_blocks(kind):
        if current_width == width_px and normalized_needle in _normalize_css(block):
            return block
    raise AssertionError(f"Missing @media({kind}:{width_px}px) block containing {needle!r}")


def _strip_css_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _rule_body(css, selector):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", _strip_css_comments(css)):
        selectors = {part.strip() for part in match.group(1).split(",")}
        if selector in selectors:
            return match.group(2)
    raise AssertionError(f"Missing CSS rule for {selector}")


def _declarations(rule_body):
    declarations = {}
    for item in rule_body.split(";"):
        if ":" not in item:
            continue
        prop, value = item.split(":", 1)
        declarations[prop.strip()] = re.sub(r"\s+", " ", value.strip())
    return declarations


def test_desktop_three_panel_contract_gives_main_readable_floor():
    desktop = _media_block("min-width", 1025, ".main{flex:1 1 420px;min-width:420px;}")
    main = _declarations(_rule_body(desktop, ".main"))

    assert main.get("flex") == "1 1 420px"
    assert main.get("min-width") == "420px"


def test_desktop_side_rails_can_shrink_to_resize_minima():
    desktop = _media_block("min-width", 1025, ".sidebar{flex-shrink:1;min-width:180px;}")
    sidebar = _declarations(_rule_body(desktop, ".sidebar"))
    rightpanel = _declarations(_rule_body(desktop, ".rightpanel"))
    closed_rightpanel = _declarations(
        _rule_body(desktop, 'html[data-workspace-panel="closed"] .rightpanel')
    )
    collapsed_rightpanel = _declarations(
        _rule_body(desktop, ".layout.workspace-panel-collapsed .rightpanel")
    )

    assert re.search(r"\bSIDEBAR_MIN\s*=\s*180\b", BOOT_JS)
    assert re.search(r"\bPANEL_MIN\s*=\s*180\b", BOOT_JS)
    assert sidebar.get("flex-shrink") == "1"
    assert sidebar.get("min-width") == "180px"
    assert rightpanel.get("flex-shrink") == "1"
    assert rightpanel.get("min-width") == "180px"
    assert closed_rightpanel.get("width") == "0 !important"
    assert closed_rightpanel.get("min-width") == "0 !important"
    assert collapsed_rightpanel.get("width") == "0 !important"
    assert collapsed_rightpanel.get("min-width") == "0 !important"


def test_compact_breakpoint_shows_the_panel_toggle():
    """Compact chrome exposes the Files button across phone AND tablet.

    Previously this block also carried `.rightpanel{display:none}` at 900px while
    the slide-over rules stopped at 640px, so between 641 and 900px the button was
    visible, its handler ran, and nothing appeared. The panel is now an overlay
    across the whole compact band instead of being hidden — see
    test_compact_band_turns_right_panel_into_a_slide_over below.
    """
    assert "@media(max-width:1024px)" in CSS or "@media (max-width: 1024px)" in CSS

    compact = _media_block("max-width", 1024, ".workspace-panel-edge-toggle")
    workspace_toggle = _declarations(_rule_body(compact, ".workspace-toggle-btn"))
    mobile_files = _declarations(_rule_body(compact, ".mobile-files-btn"))

    assert workspace_toggle.get("display") == "inline-flex!important"
    assert mobile_files.get("display") == "inline-flex!important"


def test_compact_band_turns_right_panel_into_a_slide_over():
    """The slide-over must cover the whole compact band, not just phones."""
    compact = _media_block("max-width", 1024, ".rightpanel.mobile-open")
    rightpanel = _declarations(_rule_body(compact, ".rightpanel"))
    rightpanel_open = _declarations(_rule_body(compact, ".rightpanel.mobile-open"))

    assert rightpanel.get("display") == "flex!important"
    assert rightpanel.get("position") == "fixed"
    assert rightpanel.get("right") == "calc(-1 * var(--overlay-w))!important"
    assert rightpanel.get("width") == "var(--overlay-w)!important"
    assert rightpanel.get("box-shadow") == "none!important"
    assert rightpanel_open.get("right") == "0!important"


def test_phone_only_narrows_the_slide_over():
    """A phone overrides the width token and inherits all the positioning."""
    mobile = _media_block("max-width", 640, ".rightpanel{--overlay-w")
    rightpanel = _declarations(_rule_body(mobile, ".rightpanel"))

    assert rightpanel.get("--overlay-w") in ("min(300px, 100vw)", "min(300px,100vw)")
    # Positioning must NOT be restated here — that duplication is what let the
    # two bands drift apart in the first place.
    assert "position" not in rightpanel
    assert "right" not in rightpanel


def test_right_panel_is_never_hidden_outright_on_any_narrow_viewport():
    """Regression guard for the original defect.

    No max-width media query may hide `.rightpanel`. Below the desktop boundary
    it becomes an overlay; above it, it is in-flow and collapses to zero width.
    Hiding it is what made the panel unreachable on tablets.
    """
    hidden_widths = [
        width_px
        for width_px, block in _media_blocks("max-width")
        if re.search(r"\.rightpanel\s*\{\s*display\s*:\s*none", block)
    ]

    assert not hidden_widths, (
        f".rightpanel is hidden outright at max-width {hidden_widths} — it must "
        f"become a slide-over instead so the Files button always does something"
    )
