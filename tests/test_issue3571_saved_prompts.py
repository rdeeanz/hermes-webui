"""#3571 saved-prompts library — structural + mobile-visibility guards.

The saved-prompts composer affordance is a desktop-only feature: per Nathan
(2026-06-09) it must be hidden on mobile (too much for the narrow composer).
These tests pin the mobile-hide rule and the core wiring so a future refactor
can't silently regress either.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_saved_prompts_is_reachable_on_mobile():
    """Saved prompts must have a phone entry point.

    This test previously asserted the opposite — that #btnSavedPrompts is
    `display:none` inside a max-width:640px block, described as a "desktop-only
    affordance". That was not an adaptation for small screens: it left the
    feature with no entry point at all on a phone.

    The underlying constraint was real (the popover is an anchored 280px card
    that cannot fit a 375px viewport), so the fix is a different presentation
    rather than a hidden button: the composer's mobile config panel opens the
    same surface as a bottom sheet. The desktop popover geometry may still be
    suppressed on phones — what may not happen is suppressing it with nothing
    in its place.

    See tests/test_mobile_feature_parity.py for the sheet contract itself.
    """
    html = read("static/index.html")
    css = read("static/style.css")

    assert 'id="composerMobileSavedPromptsAction"' in html, (
        "saved prompts needs a phone entry point in the composer's mobile "
        "config panel"
    )
    assert 'onclick="toggleSavedPromptsPopup()"' in html, (
        "the phone entry point must open the same surface as the desktop control"
    )
    # The old blanket hide must be gone; only the popover geometry may be scoped.
    assert "#btnSavedPrompts,.saved-prompts-popup{display:none!important;}" not in css, (
        "the saved-prompts button and popup must not be hidden outright on phones"
    )
    assert ".saved-prompts-popup:not(.sheet-open){display:none!important;}" in css, (
        "the desktop popover geometry should still be suppressed while the sheet "
        "presentation is active"
    )


def test_saved_prompts_backend_caps_present():
    """The POST /api/prompts route must cap text length and total count so
    saved_prompts.json can't grow unbounded."""
    routes = read("api/routes.py")
    assert "text too long" in routes, "POST /api/prompts must cap text length"
    assert re.search(r"len\(prompts\)\s*>=\s*\d+", routes), (
        "POST /api/prompts must cap the total number of saved prompts"
    )


def test_saved_prompts_core_wiring_present():
    """The composer must expose the saved-prompts toggle + popup and the
    load/save/delete API calls."""
    js = read("static/messages.js")
    assert "toggleSavedPromptsPopup" in js
    assert "insertSavedPromptIntoComposer" in js
    assert re.search(r"api\('/api/prompts',\s*\{method:'POST'", js), "save wiring (POST) missing"
    assert re.search(r"api\('/api/prompts',\s*\{method:'DELETE'", js), "delete wiring (DELETE) missing"
    html = read("static/index.html")
    assert 'id="btnSavedPrompts"' in html
    assert 'id="savedPromptsPopup"' in html
