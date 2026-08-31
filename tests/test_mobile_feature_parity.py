"""Features must be re-homed on phones, not hidden.

WHY THIS EXISTS
  Several composer affordances were `display:none` below 640px with no
  alternative entry point, which does not make them "mobile-adapted" — it makes
  them unreachable. An audit of `display:none` inside max-width media queries
  found:

    #btnSavedPrompts        hidden <=640px, no alternative  ("desktop-only")
    #outlinePanelWrapper    hidden <=900px, no alternative
    .markdown-table-filter  hidden <=640px, no alternative

  The first two are now reached through the composer's mobile config panel and
  presented as bottom sheets. The third is still desktop-only and deliberately
  so — see test_markdown_table_filter_is_still_desktop_only.

  These tests pin the *reachability* contract at the source level. The rendered
  behaviour (sheet geometry, backdrop, focus, dismissal) is covered by
  tests/browser_responsive.py and was verified in a real browser.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).parent.parent
STATIC = REPO / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
BOOT = (STATIC / "boot.js").read_text(encoding="utf-8")
OUTLINE = (STATIC / "outline.js").read_text(encoding="utf-8")
MESSAGES = (STATIC / "messages.js").read_text(encoding="utf-8")


# ── Bottom sheet primitive ────────────────────────────────────────────────────

def test_sheet_api_is_exposed():
    assert "window.HermesSheet" in BOOT, "boot.js must expose the sheet controller"
    for fn in ("present:", "dismiss:", "isOpen:", "isSheetMode:"):
        assert fn in BOOT, f"HermesSheet must expose {fn.rstrip(':')}()"


def test_sheet_mode_follows_the_breakpoint_contract():
    """The sheet must flip at the same width the CSS does."""
    m = re.search(r"function _sheetMode\(\)\{(?P<body>.*?)\n  \}", BOOT, re.S)
    assert m, "boot.js must define _sheetMode()"
    assert "_isPhoneWidthViewport" in m.group("body"), (
        "sheet mode must derive from the BP contract, not its own literal width"
    )
    assert not re.search(r"\d{3}", m.group("body")), (
        "_sheetMode() must not hardcode a pixel width"
    )


def test_sheet_is_dismissible_every_expected_way():
    for needle, why in [
        ("mobile-sheet-backdrop", "tap-outside needs a backdrop"),
        ("'Escape'", "Escape must dismiss"),
        ("touchstart", "swipe-down must dismiss"),
    ]:
        assert needle in BOOT, f"{why} (missing {needle!r})"


def test_sheet_traps_and_restores_focus():
    """The sheet no longer owns this; HermesA11y.isolate() does.

    The sheet had a private Tab trap. The sidebar drawer and the workspace
    slide-over — the same kind of overlay — had nothing, so all three now go
    through one implementation. The property under test is unchanged; only its
    address moved, and the delegation is asserted so it cannot be quietly
    replaced by a second copy that drifts.
    """
    assert "window.HermesA11y.isolate(el," in BOOT, (
        "the sheet must delegate focus handling to HermesA11y.isolate()"
    )
    assert "e.key !== 'Tab'" in BOOT, "focus must be trapped inside an open sheet"
    assert "opener.focus()" in BOOT, (
        "focus must return to the opener on dismiss, or keyboard and screen-reader "
        "users are dumped at the top of the document"
    )
    assert "function _trap(" not in BOOT, (
        "two implementations of one focus contract will drift; isolate() owns it"
    )


def test_sheet_is_modal_to_a_screen_reader_not_only_to_the_tab_key():
    """A Tab trap does nothing on the device this sheet exists for.

    VoiceOver and TalkBack navigate by swipe. Without aria-modal plus aria-hidden
    on everything outside, a screen-reader user swipes straight out of an open
    sheet into the chat behind it and activates a control they cannot see.
    """
    assert "'aria-modal', 'true'" in BOOT
    assert "setAttribute('aria-hidden', 'true')" in BOOT
    assert "setAttribute('inert', '')" in BOOT


def test_sheet_swipe_only_starts_at_the_top_of_the_scroll():
    """Otherwise a downward drag in a scrolled list fights the list for the gesture."""
    assert "el.scrollTop > 0" in BOOT, (
        "swipe-to-dismiss must not start while the sheet content is scrolled"
    )


def test_sheet_respects_keyboard_and_home_indicator_insets():
    sheet_css = CSS[CSS.index("[data-mobile-sheet].sheet-open{"):]
    sheet_css = sheet_css[: sheet_css.index("}")]
    assert "--keyboard-bottom-inset" in sheet_css
    assert "env(safe-area-inset-bottom" in sheet_css


def test_sheet_height_is_capped_not_fixed():
    """A two-item sheet should be short; a long one should scroll internally."""
    sheet_css = CSS[CSS.index("[data-mobile-sheet].sheet-open{"):]
    sheet_css = sheet_css[: sheet_css.index("}")]
    assert "max-height:min(85dvh" in sheet_css
    assert "overflow-y:auto" in sheet_css


def test_sheet_closes_when_a_resize_leaves_phone_width():
    """A rotation must not strand a backdrop over a desktop popover."""
    assert re.search(r"resize.*?_sheetMode\(\)", BOOT, re.S), (
        "a resize crossing the phone boundary must dismiss any open sheet"
    )


# ── Saved prompts ─────────────────────────────────────────────────────────────

def test_saved_prompts_has_a_phone_entry_point():
    assert 'id="composerMobileSavedPromptsAction"' in HTML, (
        "saved prompts must be reachable from the composer's mobile config panel"
    )
    assert 'onclick="toggleSavedPromptsPopup()"' in HTML


def test_saved_prompts_popover_is_not_hidden_when_presented_as_a_sheet():
    """The old rule hid the element outright, which is what made it unreachable."""
    assert "#btnSavedPrompts,.saved-prompts-popup{display:none!important;}" not in CSS, (
        "saved prompts must no longer be hidden outright on phones"
    )
    assert ".saved-prompts-popup:not(.sheet-open){display:none!important;}" in CSS, (
        "only the desktop popover geometry may be suppressed on phones"
    )


def test_saved_prompts_uses_the_sheet_api():
    for fn in ("_showSavedPromptsSurface", "_hideSavedPromptsSurface", "_savedPromptsSurfaceOpen"):
        assert fn in MESSAGES, f"messages.js must route saved prompts through {fn}()"
    assert "window.HermesSheet" in MESSAGES
    assert "popup.style.display='flex'" in MESSAGES, (
        "the non-sheet fallback must remain, since boot.js evaluates last"
    )


def test_saved_prompts_outside_click_defers_to_the_backdrop():
    """Two dismiss paths racing each other reopens the sheet on the same tap."""
    assert "window.HermesSheet.isOpen(popup))return;" in MESSAGES.replace(" ", ""), (
        "the document click handler must not also dismiss while a sheet is open"
    )


# ── Outline ───────────────────────────────────────────────────────────────────

def test_outline_has_a_phone_entry_point():
    assert 'id="composerMobileOutlineAction"' in HTML
    assert 'onclick="toggleOutlinePanel()"' in HTML


def test_outline_is_no_longer_gated_on_viewport_width():
    m = re.search(r"function _outlineAllowed\(\) \{(?P<body>.*?)\n\}", OUTLINE, re.S)
    assert m, "outline.js must define _outlineAllowed()"
    body = m.group("body")
    assert "matchMedia" not in body, (
        "_outlineAllowed() must not exclude narrow viewports — that made the "
        "outline unreachable on phones and tablets rather than merely restyled"
    )


def test_outline_wrapper_is_not_hidden_when_presented_as_a_sheet():
    assert "#outlineToggleBtn,#outlinePanelWrapper{display:none!important;}" not in CSS
    assert "#outlinePanelWrapper:not(.sheet-open){display:none!important;}" in CSS


def test_outline_phone_entry_follows_the_same_preference_as_the_desktop_rail():
    """Otherwise tapping it silently does nothing when the outline is switched off."""
    m = re.search(
        r"function applyConversationOutlinePreference\(\) \{(?P<body>.*?)\n\}",
        OUTLINE, re.S,
    )
    assert m
    assert "composerMobileOutlineAction" in m.group("body")


def test_outline_panel_state_resyncs_when_the_sheet_self_dismisses():
    """Backdrop / swipe / Escape bypass toggleOutlinePanel()."""
    assert "MutationObserver" in OUTLINE, (
        "_panelOpen must be resynced when the sheet is dismissed outside the "
        "toggle, or the next tap toggles stale state and appears to do nothing"
    )


# ── Markdown tables ───────────────────────────────────────────────────────────

def test_sorted_column_shows_its_direction_on_phones():
    """Sorting always worked on mobile; only the direction glyph was hidden."""
    assert '.msg-body th[aria-sort="ascending"] .markdown-table-sort-indicator' in CSS
    assert '.msg-body th[aria-sort="descending"] .markdown-table-sort-indicator' in CSS


def test_markdown_table_filter_is_still_desktop_only():
    """Recorded as a deliberate gap, not an oversight.

    The filter is a text input rendered into the header area, which is exactly
    what made narrow headers wrap. Giving it a phone home needs a new surface
    (a per-table sheet), which is a design change rather than a fix.
    """
    assert ".markdown-table-filter{display:none;}" in CSS


# ── The audit that started this ───────────────────────────────────────────────

def test_no_feature_is_hidden_on_phones_without_an_alternative():
    """Guard the class of defect, not just the three known instances.

    Any NEW `display:none` on a feature entry point inside a max-width query has
    to be justified here, which forces the question "where does a phone user
    reach this instead?" at review time rather than after release.
    """
    known_and_justified = {
        # selector fragment -> why it is acceptable
        ".markdown-table-filter",       # see test above
        ".markdown-table-sort-indicator",  # shown for the sorted column
        "#outlineToggleBtn",           # rail geometry; reached via config panel
        ".approval-kbd",               # keyboard hint, meaningless without a keyboard
        ".ctx-indicator-wrap",         # mirrored into the mobile config panel
        ".topbar-meta",                # mirrored into the sidebar drawer
        ".composer-workspace-chip",    # mirrored by the icon-only Files button
        ".composer-divider",           # pure separator
        ".mobile-overlay",             # only shown while the drawer is open
        ".resize-handle",              # dragging is meaningless on a touch overlay
        ".workspace-panel-edge-toggle",  # replaced by the Files button
        ".transparent-event-time",     # timestamp detail
        ".msg-question-jump-btn",      # label text only, button remains
        ".dashboard-link",             # mirrored into the rail
        ".sidebar-nav",                # rail vs drawer presentation
        ".rightpanel",                 # slide-over; asserted elsewhere
        ".saved-prompts-popup",        # presented as a sheet
        "#outlinePanelWrapper",        # presented as a sheet
        ".workspace-artifacts",        # tab switching, not a breakpoint rule
        "-label,",                     # chip TEXT only; the chip itself stays
        "-chevron,",                   # dropdown affordance on an icon-only chip
        "Label,",                      # #composerModelLabel etc — text only
        ".composer-model-wrap",        # mirrored into the mobile config panel
        ".composer-reasoning-wrap",    # mirrored into the mobile config panel
        ".composer-toolsets-wrap",     # mirrored into the mobile config panel
    }
    offenders = []
    for m in re.finditer(r"@media[^{]*max-width[^{]*\{", CSS):
        start = m.end() - 1
        depth = 0
        for i in range(start, len(CSS)):
            if CSS[i] == "{":
                depth += 1
            elif CSS[i] == "}":
                depth -= 1
                if depth == 0:
                    body = CSS[start + 1:i]
                    break
        for rule in re.finditer(r"([^{}]+)\{([^{}]*display\s*:\s*none[^{}]*)\}", body):
            selectors = rule.group(1)
            if not any(known in selectors for known in known_and_justified):
                offenders.append(selectors.strip()[:90])

    assert not offenders, (
        "new selector(s) hidden on narrow viewports without a documented "
        f"alternative entry point: {offenders}. Either re-home the feature (a "
        f"bottom sheet or the composer's mobile config panel) or add it to "
        f"known_and_justified with a reason."
    )
