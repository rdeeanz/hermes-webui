"""The generated per-locale i18n bundles, and their contract with the source.

WHY THIS EXISTS
  static/i18n.js is still the file translators edit, but it is no longer the
  file browsers download. scripts/split_i18n.py turns it into static/i18n/ —
  a core bundle plus one file per language — and index.html loads the core plus
  whichever single language the reader uses.

  That buys ~410 KiB off every cold load and introduces exactly one new way to
  be wrong: the committed output drifting from the source. Someone adds a key
  to static/i18n.js, forgets to regenerate, and the string is missing in every
  language in the browser while every existing test — all 168 of which read the
  SOURCE — still passes.

  test_generated_bundles_match_the_source is the whole answer to that. The rest
  pin the properties that make the split safe to load in pieces.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SOURCE = REPO / "static" / "i18n.js"
OUT_DIR = REPO / "static" / "i18n"
SPLITTER = REPO / "scripts" / "split_i18n.py"

sys.path.insert(0, str(REPO / "scripts"))
import split_i18n  # noqa: E402


@pytest.fixture(scope="module")
def source_text():
    return SOURCE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def entries(source_text):
    _prefix, entries, _suffix = split_i18n.parse_source(source_text)
    return entries


# ── The drift guard ──────────────────────────────────────────────────────────

def test_generated_bundles_match_the_source():
    """The one that matters.

    Everything else in the suite reads static/i18n.js, so a stale static/i18n/
    would be invisible to all of it — and completely visible to users, as
    English text in a translated UI.
    """
    result = subprocess.run(
        [sys.executable, str(SPLITTER), "--check"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert result.returncode == 0, (
        f"\nstatic/i18n/ is out of date with static/i18n.js.\n"
        f"Run: python3 scripts/split_i18n.py\n\n{result.stdout}{result.stderr}"
    )


def test_generated_files_say_they_are_generated():
    """So nobody edits one and loses the change on the next regeneration."""
    for path in OUT_DIR.glob("*.js"):
        head = path.read_text(encoding="utf-8")[:400]
        assert "DO NOT EDIT" in head, f"{path.name} lacks a generated-file banner"
        assert "scripts/split_i18n.py" in head, f"{path.name} does not name its generator"


# ── Structure ────────────────────────────────────────────────────────────────

def test_there_is_one_bundle_per_language(entries):
    on_disk = {p.stem for p in OUT_DIR.glob("*.js")}
    expected = {"core"} | (set(entries) - {"en"})
    assert on_disk == expected, (
        f"missing: {sorted(expected - on_disk)}  unexpected: {sorted(on_disk - expected)}"
    )


def test_english_ships_in_core_not_as_its_own_bundle():
    """`t()` reads `_locale[key] ?? LOCALES.en[key]`, so English is not optional.

    Splitting it out would mean either shipping it twice or breaking the
    fallback for every untranslated key — which is most of `id`.
    """
    assert not (OUT_DIR / "en.js").exists()
    core = (OUT_DIR / "core.js").read_text(encoding="utf-8")
    assert re.search(r"^  en: \{", core, re.M), "core.js must carry the en bundle"


def test_core_knows_every_language_even_the_ones_it_does_not_carry(entries):
    """The manifest is what lets a reader FIND a language in order to load it.

    Without it the picker could only offer the languages already downloaded,
    which is a bootstrap problem: you cannot select the bundle that selecting it
    would fetch.
    """
    core = (OUT_DIR / "core.js").read_text(encoding="utf-8")
    m = re.search(r"const LOCALE_MANIFEST = \{(.*?)\n\};", core, re.S)
    assert m, "core.js has no LOCALE_MANIFEST"
    listed = set(re.findall(r"^  '?([\w-]+)'?: \{ label:", m.group(1), re.M))
    assert listed == set(entries), (
        f"manifest missing {sorted(set(entries) - listed)}, "
        f"extra {sorted(listed - set(entries))}"
    )


def test_every_language_keeps_all_of_its_keys(entries):
    """A dropped key is silent: the UI just shows English there."""
    for code, entry in entries.items():
        name = "core.js" if code == "en" else f"{code}.js"
        want = split_i18n._keys_of(entry)
        got = split_i18n._keys_of((OUT_DIR / name).read_text(encoding="utf-8"))
        assert want <= got, f"{name} lost keys from `{code}`: {sorted(want - got)[:5]}"


def test_locale_bundles_subscript_with_a_quoted_string():
    """`LOCALES[it] = …` reads a VARIABLE named `it` and throws.

    Unquoted is correct for an object-literal key and wrong for a subscript;
    the two read almost identically, and this caught it once already.
    """
    for path in OUT_DIR.glob("*.js"):
        if path.name == "core.js":
            continue
        body = path.read_text(encoding="utf-8")
        assert re.search(r"^LOCALES\['[\w-]+'\] = \{", body, re.M), (
            f"{path.name} must assign via a quoted subscript"
        )


# ── The runtime contract the split depends on ────────────────────────────────

def test_source_keeps_the_manifest_seam():
    """The generator rewrites this exact line; the source stays runnable alone.

    With every locale present, LOCALES is itself a complete manifest — which is
    why the seam is `null` here rather than a duplicated list that could drift.
    """
    src = SOURCE.read_text(encoding="utf-8")
    assert "const LOCALE_MANIFEST = null;\n" in src


def test_nothing_enumerates_LOCALES_to_discover_languages():
    """Since the split, `Object.keys(LOCALES)` is "what is downloaded", not
    "what exists". Anything asking the second question must use the manifest."""
    i18n = SOURCE.read_text(encoding="utf-8")
    runtime = i18n[i18n.index("const LOCALE_MANIFEST"):]
    assert "Object.keys(LOCALES)" not in runtime.replace(
        "Object.keys(LOCALE_MANIFEST || LOCALES)", ""
    ), "resolveLocale and friends must go through knownLocaleCodes()"

    # `settingsLanguage` is referenced three times in panels.js; the one that
    # BUILDS the list is the only one this contract is about, so anchor on the
    # option-building code rather than on the first mention of the element.
    panels = (REPO / "static" / "panels.js").read_text(encoding="utf-8")
    at = panels.index("langSel.innerHTML=''")
    picker = panels[at:at + 900]
    assert "knownLocaleCodes" in picker, (
        "the language picker must list every language, not only the loaded ones"
    )
    assert "Object.entries(LOCALES)" not in picker, (
        "enumerating LOCALES here shows only the downloaded languages"
    )


def test_index_html_loads_core_then_the_readers_language():
    html = (REPO / "static" / "index.html").read_text(encoding="utf-8")
    assert 'src="static/i18n/core.js?v=__WEBUI_VERSION__" defer' in html
    assert '"static/i18n.js' not in html, "the 16-language monolith must not ship"

    core_at = html.index("static/i18n/core.js")
    loader_at = html.index("localStorage.getItem('hermes-lang')", core_at)
    assert core_at < loader_at, (
        "core.js declares `const LOCALES`; a locale bundle that executes first "
        "would throw. Document order is what guarantees it does not."
    )
    # document.write during parsing is what puts the injected tag in document
    # order. An async append would race the deferred scripts that call t().
    loader = html[loader_at - 300:loader_at + 400]
    assert "document.write" in loader


def test_service_worker_precaches_core_but_not_a_guessed_language():
    """A service worker cannot read localStorage, so it cannot know which
    language to pre-cache. Guessing would waste a download on most readers."""
    sw = (REPO / "static" / "sw.js").read_text(encoding="utf-8")
    assert "'./static/i18n/core.js' + VQ," in sw
    assert "'./static/i18n.js' + VQ," not in sw
    assert not re.search(r"'\./static/i18n/(?!core)[\w-]+\.js'", sw)


def test_splitter_refuses_to_emit_a_bundle_that_lost_keys():
    """The generator's own safety net, exercised rather than assumed."""
    text = SOURCE.read_text(encoding="utf-8")
    rendered = split_i18n.render(text)
    victim = next(n for n in rendered if n != "core.js")
    key = re.search(r"^    (\w+):", rendered[victim], re.M).group(1)
    rendered[victim] = re.sub(rf"^    {key}:.*$", "", rendered[victim], count=1, flags=re.M)

    with pytest.raises(split_i18n.SplitError, match="lost"):
        split_i18n.verify(text, rendered)


def test_brace_scanner_is_not_confused_by_braces_inside_strings():
    """Locale strings contain `{0}` placeholders, and one miscount would slice a
    bundle in half."""
    sample = "{ a: 'has { brace', b: `tpl ${x ? '{' : '}'} end`, c: { d: 1 } }"
    assert split_i18n._scan_forward(sample, 0) == len(sample)
    commented = "{ /* } */ a: 1, // }\n b: 2 }"
    assert split_i18n._scan_forward(commented, 0) == len(commented)
