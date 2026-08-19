"""Guards on the partial-locale exemption itself.

`tests/locale_contract.py` lets a locale ship incrementally by exempting it from
the per-key-family parity checks. That exemption is useful and it is also exactly
the kind of thing that rots: without guards it becomes a place to quietly park a
language that is missing keys nobody is tracking, or worse, a way to stop
maintaining a shipped one.

So the exemption carries obligations, and this file enforces them:

  1. Every code in PARTIAL_LOCALES actually exists in static/i18n.js. A stale
     entry silently weakens nothing, but it does mislead the next reader.
  2. Every locale — partial included — carries the identity keys, or it cannot be
     selected from the language picker or announced correctly by speech.
  3. A partial locale is a real bundle, not a stub: it must translate the surface
     a user reads first.
  4. Every key a partial locale defines also exists in English, so the fallback
     chain is intact and a typo'd key name cannot masquerade as a translation.
  5. Each exemption states why. The reason is what a reviewer reads when deciding
     whether it still deserves to be there.
"""

import pathlib
import re

from tests.locale_contract import (
    PARTIAL_LOCALES,
    REQUIRED_IDENTITY_KEYS,
    expected_locale_count,
    is_partial,
)

REPO = pathlib.Path(__file__).parent.parent
I18N = (REPO / "static" / "i18n.js").read_text(encoding="utf-8")

# Surfaces a user meets immediately. A bundle that cannot cover these is a stub,
# not a language, and shipping it would make the app look half-translated rather
# than partially translated.
CORE_SURFACE_KEYS = (
    "composer_send",
    "composer_stop",
    "tab_chat",
    "tab_settings",
    "empty_title",
    "login_title",
    "login_placeholder",
    "save",
    "cancel",
    "offline_title",
)


def _locale_blocks():
    """{code: block_source} for every bundle in i18n.js, partial ones included."""
    heads = list(
        re.finditer(
            r"^  (?:'(?P<quoted>[A-Za-z0-9-]+)'|(?P<plain>[A-Za-z][A-Za-z0-9_]*))\s*:\s*\{",
            I18N,
            re.MULTILINE,
        )
    )
    assert heads, "could not find any locale blocks in i18n.js"
    blocks = {}
    for idx, head in enumerate(heads):
        code = head.group("quoted") or head.group("plain")
        end = heads[idx + 1].start() if idx + 1 < len(heads) else I18N.find("\n};", head.end())
        assert end != -1, f"could not find end of locale block {code}"
        blocks[code] = I18N[head.end():end]
    return blocks


def _keys(block):
    return set(re.findall(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:", block, re.MULTILINE))


def test_every_partial_locale_actually_exists():
    blocks = _locale_blocks()
    missing = sorted(code for code in PARTIAL_LOCALES if code not in blocks)
    assert not missing, (
        f"PARTIAL_LOCALES names locale(s) that are not in i18n.js: {missing}. "
        f"Remove the stale entry, or the exemption list stops describing reality."
    )


def test_every_locale_carries_the_identity_keys():
    """Partial bundles are exempt from key families, never from identity."""
    for code, block in _locale_blocks().items():
        keys = _keys(block)
        missing = [k for k in REQUIRED_IDENTITY_KEYS if k not in keys]
        assert not missing, (
            f"locale '{code}' is missing identity key(s) {missing} — without them "
            f"it cannot be listed in the language picker or announced by speech "
            f"synthesis, and that is true for partial locales too"
        )


def test_partial_locales_translate_the_core_surface():
    blocks = _locale_blocks()
    for code in PARTIAL_LOCALES:
        keys = _keys(blocks[code])
        missing = sorted(k for k in CORE_SURFACE_KEYS if k not in keys)
        assert not missing, (
            f"partial locale '{code}' does not translate the core surface: "
            f"{missing}. A partial locale may skip the long tail, but a bundle "
            f"that cannot cover the composer, navigation and login is a stub."
        )


def test_partial_locale_keys_all_exist_in_english():
    """Guards the fallback chain and catches typo'd key names."""
    blocks = _locale_blocks()
    english = _keys(blocks["en"])
    for code in PARTIAL_LOCALES:
        unknown = sorted(_keys(blocks[code]) - english)
        assert not unknown, (
            f"partial locale '{code}' defines key(s) English does not have: "
            f"{unknown}. Either the key is misspelled — in which case it silently "
            f"never renders — or English is missing it and every other locale "
            f"would fall back to the key name."
        )


def test_every_exemption_states_a_reason():
    for code, reason in PARTIAL_LOCALES.items():
        assert isinstance(reason, str) and len(reason.strip()) >= 40, (
            f"partial locale '{code}' needs a substantive reason; the reason is "
            f"what a reviewer reads when deciding whether to keep the exemption"
        )


def test_expected_locale_count_excludes_partials():
    total = len(_locale_blocks())
    assert expected_locale_count(total) == total - len(PARTIAL_LOCALES)
    assert expected_locale_count(total) >= 1


def test_complete_locales_are_still_held_to_the_contract():
    """The exemption must not have quietly widened to everything."""
    blocks = _locale_blocks()
    complete = [c for c in blocks if not is_partial(c)]
    assert len(complete) >= 10, (
        f"only {len(complete)} locale(s) are held to full key parity. The partial "
        f"exemption is for landing a language incrementally, not for retiring the "
        f"parity contract."
    )
    # English is the fallback target; it can never be partial.
    assert not is_partial("en"), (
        "English is the fallback every other locale resolves against and must "
        "always be complete"
    )
