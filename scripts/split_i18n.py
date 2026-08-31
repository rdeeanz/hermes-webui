#!/usr/bin/env python3
"""Split static/i18n.js into a core bundle plus one file per locale.

WHY
  static/i18n.js carries 16 languages in one file — 485 KiB gzipped, 32% of
  everything a phone downloads before the app is usable. A reader uses one of
  those languages. The other 15 are pure cost on every cold load.

  Splitting them means a cold load carries `en` (the fallback chain needs it)
  plus the reader's own language: ~30 KiB instead of ~485 KiB.

THE SOURCE OF TRUTH DOES NOT MOVE
  static/i18n.js stays the file you edit. It is not shipped to the browser any
  more, but it remains the single place a translation is written, and 168 test
  files read it directly.

  The generated files under static/i18n/ are build output that happens to be
  committed (this repo has no build step, so committing them is how they reach
  a deployment). tests/test_i18n_split.py regenerates and compares, so they
  cannot drift from the source: edit static/i18n.js, run this script, commit
  both.

WHAT IT EMITS
  static/i18n/core.js      prefix + LOCALES with `en` only + LOCALE_MANIFEST
                           + every shared helper and the whole t()/setLocale
                           runtime
  static/i18n/<code>.js    LOCALES['<code>'] = { … } for each other language

  Order matters at runtime: core.js declares `const LOCALES`, so a locale file
  must execute after it. index.html guarantees that — see the loader there.

WHY THE PARSING IS SAFE
  This slices text; it does not evaluate JavaScript. It relies on exactly one
  structural property of static/i18n.js: locale entries are the top-level keys
  of a `const LOCALES = { … };` object literal, each opening at two-space
  indent. Everything else is copied through verbatim. Brace counting is
  string- and comment-aware, so a `{` inside a translated string or a regex-ish
  comment cannot desynchronise it.

  The output is verified before it is written: every locale's key set must
  match the source exactly, or nothing is emitted.

USAGE
  python3 scripts/split_i18n.py            # write static/i18n/
  python3 scripts/split_i18n.py --check    # exit 1 if committed output is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "static" / "i18n.js"
OUT_DIR = REPO / "static" / "i18n"

# The fallback locale. `t()` reads `_locale[key] ?? LOCALES.en[key]`, so `en`
# has to be present on every page load and therefore lives in core.js.
FALLBACK = "en"

GENERATED_HEADER = """// ─────────────────────────────────────────────────────────────────────────────
// GENERATED FILE — DO NOT EDIT.
// Source: static/i18n.js   Generator: scripts/split_i18n.py
// Edit the source and re-run the generator; tests/test_i18n_split.py fails if
// this file and the source disagree.
// ─────────────────────────────────────────────────────────────────────────────
"""


class SplitError(RuntimeError):
    """The source did not have the shape this splitter requires."""


def _scan_forward(text: str, start: int) -> int:
    """Index just past the `}` closing the `{` at `start`.

    String- and comment-aware: a brace inside a translated string ("Use {0}
    files") or inside a comment must not move the depth counter.
    """
    depth = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                # A template literal can nest an expression that contains
                # braces and further strings; step into it rather than
                # scanning its contents as raw text.
                if quote == "`" and text[i] == "$" and text[i + 1:i + 2] == "{":
                    i = _scan_forward(text, i + 1)
                    continue
                i += 1
            i += 1
            continue
        if ch == "/" and text[i + 1:i + 2] == "/":
            nl = text.find("\n", i)
            i = n if nl == -1 else nl
            continue
        if ch == "/" and text[i + 1:i + 2] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise SplitError("unbalanced braces — reached end of file looking for '}'")


def parse_source(text: str) -> tuple[str, dict[str, str], str]:
    """Return (prefix, {code: entry_body}, suffix).

    `entry_body` is the object literal text including its braces, exactly as
    written, so re-emitting it is byte-preserving.
    """
    m = re.search(r"^const LOCALES = \{", text, re.M)
    if not m:
        raise SplitError("could not find `const LOCALES = {` at the start of a line")
    open_brace = m.end() - 1
    close = _scan_forward(text, open_brace)

    prefix = text[: m.start()]
    body = text[open_brace + 1 : close - 1]
    suffix = text[close:]
    if not suffix.startswith(";"):
        raise SplitError("`const LOCALES = { … }` is not followed by ';'")
    suffix = suffix[1:]

    entries: dict[str, str] = {}
    # Top-level keys of the object, at two-space indent: `  en: {` or
    # `  'zh-Hant': {`.
    for em in re.finditer(r"^  (?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_$][\w$-]*)): \{", body, re.M):
        code = em.group(1) or em.group(2) or em.group(3)
        entry_close = _scan_forward(body, em.end() - 1)
        entries[code] = body[em.end() - 1 : entry_close]

    if FALLBACK not in entries:
        raise SplitError(f"no `{FALLBACK}` locale found — it is the fallback chain")
    if len(entries) < 2:
        raise SplitError(f"found only {len(entries)} locale(s); source looks wrong")
    return prefix, entries, suffix


def _field(entry: str, name: str) -> str:
    """Read a simple string field (`_label`, `_speech`) out of an entry."""
    m = re.search(rf"^    {name}: '((?:[^'\\]|\\.)*)'", entry, re.M)
    return m.group(1) if m else ""


def build_manifest(entries: dict[str, str]) -> str:
    """Metadata for every locale, including ones that are not loaded.

    resolveLocale() and the language picker both have to know a language
    exists before its bundle has been fetched — otherwise a reader whose
    language is not loaded cannot find it in the list in order to pick it.
    """
    lines = []
    for code, entry in entries.items():
        label = _field(entry, "_label") or code
        speech = _field(entry, "_speech") or code
        lines.append(
            f"  {_js_key(code)}: {{ label: '{label}', speech: '{speech}' }},"
        )
    return "const LOCALE_MANIFEST = {\n" + "\n".join(lines) + "\n};\n"


def _js_key(code: str) -> str:
    """A locale code as an object-literal KEY.

    `it:` is valid unquoted; `'zh-Hant':` is not.
    """
    return code if re.fullmatch(r"[A-Za-z_$][\w$]*", code) else f"'{code}'"


def _js_index(code: str) -> str:
    """A locale code as a bracket SUBSCRIPT — always a quoted string.

    Not the same as `_js_key`: unquoted inside brackets, `LOCALES[it]` reads a
    variable named `it` and throws ReferenceError. The two contexts look alike
    and one of them silently is not a string.
    """
    escaped = code.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def render(text: str) -> dict[str, str]:
    """Return {relative filename: file contents} for the whole split."""
    prefix, entries, suffix = parse_source(text)

    # The source declares `const LOCALE_MANIFEST = null;` as a seam, so it
    # still runs standalone (falling back to Object.keys(LOCALES)). Here it is
    # replaced with the real thing.
    seam = "const LOCALE_MANIFEST = null;\n"
    if seam not in suffix:
        raise SplitError(
            "static/i18n.js must contain the line `const LOCALE_MANIFEST = null;` "
            "for the generator to replace"
        )
    suffix = suffix.replace(seam, build_manifest(entries), 1)

    out = {
        "core.js": (
            GENERATED_HEADER
            + prefix
            + "const LOCALES = {\n"
            + f"  {FALLBACK}: {entries[FALLBACK]},\n"
            + "};"
            + suffix
        )
    }
    for code, entry in entries.items():
        if code == FALLBACK:
            continue
        out[f"{code}.js"] = (
            GENERATED_HEADER
            + f"// {code} — loaded on demand by the loader in index.html.\n"
            + f"LOCALES[{_js_index(code)}] = {entry};\n"
        )
    return out


def _keys_of(entry: str) -> set[str]:
    return set(re.findall(r"^    ([A-Za-z_$][\w$]*):", entry, re.M))


def verify(text: str, rendered: dict[str, str]) -> None:
    """Refuse to emit output that does not carry every key of the source.

    A silent key loss here would surface as English text appearing in a
    translated UI — the kind of bug nobody files and everybody notices.
    """
    _, entries, _ = parse_source(text)
    for code, entry in entries.items():
        want = _keys_of(entry)
        name = "core.js" if code == FALLBACK else f"{code}.js"
        got = _keys_of(rendered[name])
        missing = want - got
        if missing:
            raise SplitError(
                f"{name} lost {len(missing)} key(s) from `{code}`: "
                f"{sorted(missing)[:5]}"
            )
    if len(rendered) != len(entries):
        raise SplitError(
            f"expected {len(entries)} output files, produced {len(rendered)}"
        )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the committed output is stale",
    )
    args = ap.parse_args(argv)

    text = SOURCE.read_text(encoding="utf-8")
    try:
        rendered = render(text)
        verify(text, rendered)
    except SplitError as exc:
        print(f"split_i18n: {exc}", file=sys.stderr)
        return 2

    if args.check:
        stale = []
        for name, content in sorted(rendered.items()):
            path = OUT_DIR / name
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(name)
        extra = sorted(
            p.name for p in OUT_DIR.glob("*.js") if p.name not in rendered
        ) if OUT_DIR.is_dir() else []
        if stale or extra:
            print(
                "split_i18n: static/i18n/ is out of date with static/i18n.js\n"
                f"  stale/missing: {stale or 'none'}\n"
                f"  no longer generated: {extra or 'none'}\n"
                "  fix: python3 scripts/split_i18n.py",
                file=sys.stderr,
            )
            return 1
        print(f"split_i18n --check: {len(rendered)} file(s) up to date.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(rendered.items()):
        (OUT_DIR / name).write_text(content, encoding="utf-8")
    for path in sorted(OUT_DIR.glob("*.js")):
        if path.name not in rendered:
            path.unlink()
            print(f"  removed stale {path.name}")
    print(f"split_i18n: wrote {len(rendered)} file(s) to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
