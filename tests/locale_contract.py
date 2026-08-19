"""Which locale bundles are held to full key parity, and which are partial.

WHY THIS EXISTS
  A large family of tests asserts that EVERY bundle in `static/i18n.js` carries
  some set of keys — auth-safety strings, kanban labels, provider quota copy, and
  so on. That contract is worth keeping: it is what stops a shipped locale from
  silently losing a label when a feature adds one.

  It also made it impossible to land a locale incrementally. A new language had to
  arrive with all ~1,600 keys translated or not at all, and "all at once" in
  practice means machine-translating strings nobody reviews — including the
  confirmation text on destructive settings flows, where a wrong translation is
  worse than an untranslated one.

  `t()` already degrades correctly:

      const val = _locale[key] ?? LOCALES.en[key];

  so a missing key falls back to English per-key, not per-locale. The runtime was
  never the obstacle; only the test contract was.

HOW IT WORKS
  A locale listed in PARTIAL_LOCALES is exempt from per-key-family parity checks.
  Everything else is still held to the full contract, so this cannot quietly
  become a way to stop maintaining the shipped languages. Moving a locale out of
  this dict — once a speaker has reviewed the full bundle — is what "promotes" it.

  Tests consult this module rather than hardcoding a locale code, so promoting or
  adding a partial locale is a one-line change here instead of an edit across
  two dozen test files.

WHAT A PARTIAL LOCALE STILL OWES
  The identity keys every bundle needs to be selectable and announced correctly:
  `_lang`, `_label`, `_speech`. Those are enforced below, not exempted.
"""

# code -> why it is partial. Keep the reason specific; it is the thing a reviewer
# reads when deciding whether the exemption still deserves to be here.
PARTIAL_LOCALES = {
    "id": (
        "Bahasa Indonesia — core UI chrome only (composer, navigation, sessions, "
        "voice, model picker, login, connection states, mobile sheets). The long "
        "tail (cron, onboarding, extensions, settings) intentionally falls back "
        "to English until a speaker reviews it, rather than being machine "
        "translated into destructive settings flows."
    ),
}

# Every bundle, partial or not, must carry these so it can be selected from the
# language picker and announced correctly by speech synthesis.
REQUIRED_IDENTITY_KEYS = ("_lang", "_label", "_speech")


def is_partial(code: str) -> bool:
    """True if `code` is exempt from per-key-family parity checks."""
    return code in PARTIAL_LOCALES


def complete_codes(codes):
    """Filter an iterable of locale codes down to the fully-translated ones."""
    return [code for code in codes if not is_partial(code)]


def complete_blocks(blocks: dict) -> dict:
    """Filter a {code: source_block} mapping down to fully-translated locales.

    The common shape in these tests is::

        for locale, block in _i18n_locale_blocks(src).items():
            assert every_key_present(block)

    which becomes::

        for locale, block in complete_blocks(_i18n_locale_blocks(src)).items():
    """
    return {code: block for code, block in blocks.items() if not is_partial(code)}


def expected_locale_count(total_locales: int) -> int:
    """How many bundles a per-key-family occurrence count should expect.

    Some tests count how often a key appears across the whole file and compare
    that to the number of locales. Partial bundles do not carry those keys, so
    they must not be counted.
    """
    return total_locales - len(PARTIAL_LOCALES)
