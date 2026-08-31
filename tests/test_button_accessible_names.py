"""Icon-only controls must have a name a screen reader can read.

WHY THIS EXISTS
  index.html has 206 `<button>` elements and had 87 `aria-label` attributes.
  Measured in a real browser, 40 of those buttons had no accessible name at all —
  including every tab in the left rail, every action in every panel header, the
  dictation button and the voice-mode button. On VoiceOver or TalkBack each one
  announced as, roughly, "button".

  The cause was one line of well-intentioned code. Icon-only buttons carried
  `data-tooltip` + `data-i18n-title`, and applyLocaleToDOM() did this:

      el.setAttribute('data-tooltip', val);
      if (el.hasAttribute('title')) el.removeAttribute('title');

  `data-tooltip` is a CSS tooltip — a `::after` with a `content` property. No
  assistive technology reads it. And the branch strips `title`, the one attribute
  that WAS readable, to stop the slow native tooltip co-firing (#1775). So
  localizing the page was what removed the last accessible name.

  This file is the static gate the plan asked for ("every <button> without text
  must have an aria-label"), plus the contracts behind the three other things
  that were missing: modal semantics on overlays, a throttled live region, and an
  approval card that can be answered without seeing it.

HOW THE NAME IS COMPUTED HERE
  A deliberately conservative subset of the real algorithm: aria-labelledby,
  aria-label, visible text (aria-hidden subtrees and <svg> removed), title. Plus
  the two attributes this app resolves into those at runtime, `data-i18n` (text)
  and `data-i18n-aria-label` (aria-label).

  `data-tooltip` and `data-i18n-title` are NOT in that list, which is the whole
  point of the file.
"""

import html
import re
from pathlib import Path

REPO = Path(__file__).parent.parent
STATIC = REPO / "static"

INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
BOOT = (STATIC / "boot.js").read_text(encoding="utf-8")
UI = (STATIC / "ui.js").read_text(encoding="utf-8")
MESSAGES = (STATIC / "messages.js").read_text(encoding="utf-8")
I18N = (STATIC / "i18n.js").read_text(encoding="utf-8")
I18N_CORE = (STATIC / "i18n" / "core.js").read_text(encoding="utf-8")

# Buttons whose LABEL IS THEIR CONTENT, written in by JS the moment they become
# visible, and which are display:none until then.
#
# A static aria-label on one of these would be a regression, not a fix: aria-label
# WINS over text content, so it would permanently shadow the live value ("Compress
# context", "78% used · $0.04", the current model name) with a stale generic
# string. Verified in a browser: all of them are unrendered while unnamed, and
# named the moment they render.
DYNAMIC_TEXT_BUTTONS = {
    "providerQuotaChip",             # renderProviderQuotaIndicator: label span + title
    "composerModelChip",             # syncModelChip: current model name
    "composerReasoningChip",         # current reasoning effort
    "ctxCompressBtn",                # _setCtxCompressButton: '' when hidden
    "composerMobileCtxCompressBtn",  # same, mobile composer
}

ATTR_RE = re.compile(r'([a-zA-Z0-9_:.-]+)(?:\s*=\s*("([^"]*)"|\'([^\']*)\'))?')


def _attrs(open_tag: str) -> dict:
    inner = open_tag[len("<button"):].rstrip(">").rstrip("/")
    out = {}
    for m in ATTR_RE.finditer(inner):
        val = m.group(3) if m.group(3) is not None else (m.group(4) or "")
        out[m.group(1).lower()] = val
    return out


def _visible_text(content: str) -> str:
    """Text a screen reader would read from the button's subtree."""
    s = re.sub(r"<svg\b.*?</svg>", " ", content, flags=re.S | re.I)
    s = re.sub(r'<(\w+)[^>]*aria-hidden="true"[^>]*>.*?</\1>', " ", s, flags=re.S | re.I)
    s = re.sub(r'<[^>]*aria-hidden="true"[^>]*/?>', " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s).strip()


def buttons():
    """(attrs, inner_html, line_number) for every <button> in index.html.

    A regex walk rather than a parser because this file interleaves markup with
    inline handlers containing '>' and quotes; verified against the DOM the
    browser actually builds (206 open tags, 206 closers, no nesting).
    """
    out = []
    for m in re.finditer(r"<button\b[^>]*>", INDEX):
        close = INDEX.find("</button>", m.end())
        out.append((
            _attrs(m.group(0)),
            INDEX[m.end():close],
            INDEX.count("\n", 0, m.start()) + 1,
        ))
    return out


def _name_sources(a: dict, content: str) -> list[str]:
    src = []
    if _visible_text(content):
        src.append("text")
    if a.get("aria-label", "").strip():
        src.append("aria-label")
    if a.get("aria-labelledby", "").strip():
        src.append("aria-labelledby")
    if a.get("data-i18n-aria-label", "").strip():
        src.append("data-i18n-aria-label")
    if a.get("data-i18n", "").strip():
        src.append("data-i18n")
    if a.get("title", "").strip():
        src.append("title")
    return src


# ── The gate ─────────────────────────────────────────────────────────────────


def test_the_parser_still_sees_the_whole_button_set():
    """A guard on the guard: a silently-empty list would pass every test below."""
    rows = buttons()
    assert len(rows) > 190, f"expected ~206 buttons in index.html, found {len(rows)}"
    assert INDEX.count("<button") == INDEX.count("</button>"), (
        "unbalanced <button> tags — the scan below cannot be trusted"
    )


def test_every_button_without_text_has_a_readable_name():
    unnamed = []
    for a, content, line in buttons():
        if _name_sources(a, content):
            continue
        if a.get("id") in DYNAMIC_TEXT_BUTTONS:
            continue
        unnamed.append(f"L{line} id={a.get('id') or '(none)'} class={a.get('class', '')[:40]!r}")
    assert not unnamed, (
        "these buttons announce as just \"button\" to VoiceOver and TalkBack:\n  "
        + "\n  ".join(unnamed)
        + "\n\nAdd aria-label (the English text) plus data-i18n-aria-label (the "
        "translation key). data-tooltip does NOT count — see this file's docstring."
    )


def test_data_tooltip_is_not_accepted_as_a_name():
    """The specific mistake this file exists to prevent.

    38 buttons were labelled only by `data-tooltip`. If someone widens
    _name_sources() to accept it, every one of them silently passes again while
    remaining unreadable.
    """
    assert "data-tooltip" not in str(_name_sources({"data-tooltip": "Chat"}, ""))
    assert _name_sources({"data-tooltip": "Chat", "data-i18n-title": "tab_chat"}, "") == [], (
        "a CSS tooltip is not an accessible name; no assistive technology reads it"
    )


def test_tooltip_buttons_carry_both_an_aria_label_and_its_translation_key():
    """An English-only aria-label is a regression for 15 of the 16 languages.

    It is also worse than the tooltip it replaced, because the tooltip at least
    localized — so a fix that stops at aria-label makes the visible and the
    spoken label disagree.
    """
    unnamed, unlocalized = [], []
    for a, content, line in buttons():
        if not a.get("data-i18n-title"):
            continue
        if _visible_text(content) or a.get("data-i18n"):
            continue  # labelled by its own text; the tooltip is supplementary
        where = f"L{line} id={a.get('id') or '(none)'}"
        has_static = bool(a.get("aria-label"))
        has_key = bool(a.get("data-i18n-aria-label"))
        if not has_static and not has_key:
            unnamed.append(where)
        elif has_static and not has_key:
            # The reverse (key but no static label) is fine: applyLocaleToDOM
            # writes aria-label from the key on the first pass, and btnSend
            # additionally has it rewritten by updateSendBtn on every state
            # change. A static label with no key is the broken direction —
            # English-only speech under a localized tooltip.
            unlocalized.append(where)
    assert not unnamed, f"icon-only tooltip buttons with no accessible name: {unnamed}"
    assert not unlocalized, (
        f"aria-label present but not localized (add data-i18n-aria-label): {unlocalized}"
    )


def test_every_referenced_translation_key_exists():
    """A missing key makes t() return the key, so the button would announce as
    'tab_kanban' — which is worse than no label, because it sounds deliberate."""
    en_block = I18N_CORE[I18N_CORE.index("  en: {"):]
    # 4-to-8 spaces, not exactly 4: the `en` bundle is flat but its indentation
    # is not — a few hundred keys sit at six spaces from an old edit. Widening
    # the scan is right here because the question is only "does the key exist".
    en_keys = set(re.findall(r"^ {4,8}([a-zA-Z0-9_]+):", en_block, re.MULTILINE))
    referenced = set()
    for a, _content, _line in buttons():
        for attr in ("data-i18n", "data-i18n-aria-label", "data-i18n-title"):
            if a.get(attr):
                referenced.add(a[attr])
    missing = sorted(referenced - en_keys)
    assert not missing, f"buttons reference translation keys that do not exist: {missing}"


def test_aria_label_matches_the_tooltip_text():
    """They describe the same control, so they must not drift.

    Not a style rule: a spoken label that disagrees with the visible tooltip is a
    bug report waiting to happen, and the mismatch is invisible to whoever edits
    only one of them.
    """
    mismatched = []
    for a, _content, line in buttons():
        label, tooltip = a.get("aria-label"), a.get("data-tooltip")
        if not label or not tooltip:
            continue
        if a.get("data-i18n-aria-label") != a.get("data-i18n-title"):
            mismatched.append(
                f"L{line} id={a.get('id') or '(none)'}: key "
                f"{a.get('data-i18n-aria-label')!r} != {a.get('data-i18n-title')!r}"
            )
    assert not mismatched, "aria-label and tooltip use different keys:\n  " + "\n  ".join(mismatched)


# ── The runtime fallback ─────────────────────────────────────────────────────


def test_localizing_the_page_supplies_a_name_when_there_is_none():
    """The line that removed accessible names now restores one.

    Buttons built in JS carry data-tooltip too, and no static test sees those.
    """
    block = I18N[I18N.index("document.querySelectorAll('[data-i18n-title]')"):]
    block = block[: block.index("data-i18n-placeholder")]
    assert "el.setAttribute('aria-label', val)" in block, (
        "applyLocaleToDOM strips `title` from tooltip buttons; it must supply "
        "aria-label in its place or the control loses its only readable name"
    )


def test_the_fallback_never_shadows_a_real_label():
    """aria-label beats text content, so an unconditional write would freeze a
    dynamic label ('78% used', the current model) at a stale generic string."""
    block = I18N[I18N.index("document.querySelectorAll('[data-i18n-title]')"):]
    block = block[: block.index("data-i18n-placeholder")]
    for guard in ("aria-label", "aria-labelledby", "data-i18n-aria-label", "textContent"):
        assert guard in block, (
            f"the aria-label fallback must check {guard} first, or it overrides a "
            f"label the element already had"
        )


def test_the_generated_bundle_carries_the_fallback_too():
    """static/i18n.js is the source; static/i18n/core.js is what ships."""
    assert "el.setAttribute('aria-label', val)" in I18N_CORE, (
        "run scripts/split_i18n.py — the shipped bundle is behind the source"
    )


# ── Modal semantics for overlays ─────────────────────────────────────────────


def _isolate_body() -> str:
    start = BOOT.index("function isolate(el, opts)")
    return BOOT[start: BOOT.index("\n  var MIN_GAP_MS", start)]


def test_isolate_sets_modal_semantics_not_just_a_tab_trap():
    """A Tab trap does nothing on a phone.

    VoiceOver and TalkBack navigate by swipe, not by Tab, so the only thing that
    confines them to an open sheet is aria-modal plus aria-hidden on everything
    outside it.
    """
    body = _isolate_body()
    assert "'aria-modal', 'true'" in body
    assert "'role'" in body
    assert "setAttribute('aria-hidden', 'true')" in body
    assert "setAttribute('inert', '')" in body, (
        "inert is what makes the same statement to pointer and keyboard, and "
        "makes the Tab fallback redundant where it is supported"
    )


def test_isolate_hides_siblings_and_not_ancestors():
    """aria-hidden on an ancestor of the focused element is invalid ARIA and
    browsers disagree about what it means."""
    body = _isolate_body()
    assert "node.parentElement" in body and "parent.children" in body
    assert "if(sib === node) continue;" in body, (
        "the walk must skip the node on the path to the dialog at every level"
    )


def test_isolate_leaves_already_hidden_elements_alone():
    """release() must not reveal something that was hidden by its own logic — a
    closed dialog, a decorative scrim."""
    body = _isolate_body()
    assert "sib.hasAttribute('aria-hidden') || sib.hasAttribute('inert')" in body


def test_isolate_moves_focus_in_and_returns_it():
    body = _isolate_body()
    assert "focusFirst(el)" in body
    assert "opener.focus()" in body, (
        "without this a keyboard user is dropped at the top of the document and a "
        "screen-reader user loses their place entirely"
    )


def test_isolate_handles_escape():
    assert "e.key === 'Escape'" in _isolate_body()


def test_focus_first_falls_back_to_the_container():
    """An overlay with nothing focusable inside must still receive focus, or the
    screen reader stays on a control that is now behind it."""
    body = BOOT[BOOT.index("function focusFirst(root)"):]
    body = body[: body.index("\n  /**")]
    assert "setAttribute('tabindex', '-1')" in body and "root.focus()" in body


def test_the_bottom_sheet_delegates_focus_to_isolate():
    """It had its own trap. Two implementations of the same contract drift."""
    assert "window.HermesA11y.isolate(el," in BOOT
    sheet = BOOT[BOOT.index("// ── Bottom sheet controller"):]
    assert "function _trap(" not in sheet, (
        "the sheet's private Tab trap should be gone — isolate() owns focus now"
    )
    assert sheet.count("var FOCUSABLE") == 0, (
        "one definition of what counts as focusable, not two"
    )


def test_the_sheet_backdrop_never_becomes_inert():
    """It is the tap-to-dismiss target. inert would swallow the tap and leave the
    sheet with no way out on a touch device."""
    assert "_backdrop.setAttribute('aria-hidden', 'true')" in BOOT, (
        "marking the backdrop aria-hidden is what makes isolate() skip it"
    )
    assert "skip: [backdrop]" in BOOT


def test_the_drawer_and_slide_over_are_isolated_too():
    """They are the same kind of overlay as the sheet and had none of this."""
    block = BOOT[BOOT.index("// ── Drawer + slide-over a11y"):]
    block = block[: block.index("// ── Bottom sheet controller")]
    assert "'.sidebar'" in block and "'.rightpanel'" in block
    assert "HermesA11y.isolate(el," in block
    assert "closeMobileSidebar" in block and "closeWorkspacePanel" in block, (
        "Escape must close whichever overlay is open"
    )


def test_the_drawer_isolation_keys_on_the_class_css_already_uses():
    """`mobile-open` is added in five places and removed in two.

    Watching the class covers every call site, including ones nobody has written
    yet — which is the failure mode that produced an inaccessible drawer in the
    first place. It also means the tablet layout, where the sidebar is in-flow
    and must not be isolated, is handled by construction.
    """
    block = BOOT[BOOT.index("// ── Drawer + slide-over a11y"):]
    block = block[: block.index("// ── Bottom sheet controller")]
    assert "MutationObserver" in block
    assert "attributeFilter: ['class']" in block
    assert "classList.contains('mobile-open')" in block


# ── The live region ──────────────────────────────────────────────────────────


def _announce_body() -> str:
    start = BOOT.index("function announce(text, opts)")
    return BOOT[start: BOOT.index("\n  window.HermesA11y", start)]


def test_the_live_region_cannot_flood():
    """A live region fed on every state change is worse than none: the speech
    queue backs up and the user cannot hear what they are typing."""
    body = _announce_body()
    assert "text === _lastText" in body, "identical text must never repeat"
    assert "MIN_GAP_MS" in body and "setTimeout" in body, (
        "there must be a floor between utterances"
    )
    assert "_pending = {" in body and "if(_timer) return;" in body, (
        "a burst inside the floor should collapse to one utterance carrying the "
        "NEWEST text, not queue five"
    )


def test_progress_is_polite_and_only_approvals_interrupt():
    body = _announce_body()
    assert "p.assertive ? 'assertive' : 'polite'" in body
    assert "a11y.announce(text)" in UI, "the busy transition must not be assertive"
    assert "{assertive: true}" in MESSAGES, "an approval blocks the agent; it may interrupt"


def test_streaming_is_announced_on_transition_not_on_every_call():
    """setBusy is called several times per turn. Two utterances per turn is the
    entire feature."""
    block = UI[UI.index("function setBusy(v){"):]
    block = block[: block.index("\n  updateSendBtn();")]
    assert "const wasBusy=!!S.busy;" in block
    assert "if(wasBusy!==!!v)" in block, (
        "announcing unconditionally would speak on every internal setBusy call"
    )


def test_the_announcer_element_exists_and_is_a_status_region():
    assert 'id="a11yAnnouncer"' in INDEX
    region = INDEX[INDEX.index('id="a11yAnnouncer"') - 40: INDEX.index('id="a11yAnnouncer"') + 140]
    assert 'role="status"' in region
    assert 'aria-live="polite"' in region
    assert 'aria-atomic="true"' in region, (
        "without aria-atomic some screen readers read only the changed words"
    )
    assert "sr-only" in region, "it must not be visible"


def test_the_announcement_strings_are_translatable():
    for key in ("a11y_agent_working", "a11y_agent_finished", "a11y_approval_pending"):
        assert f"{key}:" in I18N_CORE, f"{key} missing from the English bundle"
    for key in ("sidebar_drawer_label", "workspace_panel_label"):
        assert f"{key}:" in I18N_CORE, f"{key} missing from the English bundle"


# ── The approval card ────────────────────────────────────────────────────────


def test_the_approval_card_is_an_alert_dialog_that_names_its_command():
    card = INDEX[INDEX.index('id="approvalCard"'):]
    card_tag = card[: card.index(">")]
    assert 'role="alertdialog"' in card_tag
    assert 'aria-labelledby="approvalHeading"' in card_tag
    described = re.search(r'aria-describedby="([^"]+)"', card_tag).group(1).split()
    assert "approvalDesc" in described
    assert "approvalCmd" in described, (
        "the command about to run is the single most important thing to hear "
        "before answering, and it was not in aria-describedby"
    )


def test_the_closed_approval_card_is_out_of_the_accessibility_tree():
    card_tag = INDEX[INDEX.index('id="approvalCard"'):]
    card_tag = card_tag[: card_tag.index(">")]
    for attr in ("hidden", "aria-hidden", "inert"):
        assert attr in card_tag, f"the closed approval card must carry {attr}"


def test_every_approval_action_has_a_name():
    start = INDEX.index('id="approvalCard"')
    end = INDEX.index('id="clarifyCard"')
    for a, content, line in buttons():
        offset = INDEX.find(f'id="{a.get("id")}"') if a.get("id") else -1
        if not (start < offset < end):
            continue
        assert _name_sources(a, content), (
            f"approval action at L{line} (id={a.get('id')}) has no accessible name — "
            f"it cannot be answered without seeing the screen"
        )


def test_an_approval_that_does_not_steal_focus_is_announced_instead():
    """Focus is left alone when the user is typing — yanking it mid-sentence is
    its own accessibility failure — but an approval blocks the agent, so silence
    is not the alternative."""
    block = MESSAGES[MESSAGES.index('const onceBtn = $("approvalBtnOnce");'):]
    block = block[: block.index("if (typeof syncTopbar")]
    assert "onceBtn.focus({preventScroll: true})" in block
    assert "a11y.announce(" in block
    assert "!sameApproval" in block, (
        "the approval poller re-renders the same approval every few seconds; "
        "without this guard the announcement repeats forever"
    )
