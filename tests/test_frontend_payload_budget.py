"""Frontend cold-load payload budget.

WHY THIS EXISTS
  Every asset `index.html` references is fetched before the app is usable. As of
  the 2026-08-31 audit that came to ~1.46 MB gzipped, and nothing in a 1,398-file
  test suite had an opinion about it. The suite has several tests named "budget",
  but every one of them bounds a runtime cost — query counts, redirect hops,
  model-discovery fallbacks. Not one bounds a byte.

  The consequence was measurable rather than theoretical: a 16th locale and nine
  more skins landed between two audits, each adding weight to every cold load on
  every device, and no test noticed either. That is the regression class this
  file exists to catch — not a bug, but a slow accumulation that nobody is
  individually responsible for.

  It is deliberately the FIRST piece of the payload work rather than the last.
  Splitting i18n.js and lazy-loading panels.js are worth ~580 KiB between them,
  and without a gate holding the line those savings erode the same way the
  originals accumulated.

HOW IT WORKS
  The asset list is PARSED OUT OF index.html, never hardcoded. A hardcoded list
  is the failure mode this test is supposed to prevent: someone adds
  `<script src="static/new-thing.js">`, the list does not know about it, and the
  budget silently stops describing the real page. Parsing means a new script tag
  is counted the moment it is added.

  Sizes are gzip level 6 — matching `_serve_static` in api/routes.py, which is
  what the browser actually receives. Level 9 would understate the payload and
  the default level 9 in `gzip.compress` is an easy mistake to make here.

WHEN THIS FAILS
  The failure message names the file and the byte delta. Two legitimate
  responses:

  1. The growth is justified (a real feature). Raise the budget in the same
     commit, so the increase is reviewed rather than absorbed.
  2. The growth is incidental. Find it and stop it.

  What is NOT a legitimate response is raising the budget in a follow-up "fix
  CI" commit. That converts the gate into a ratchet that only ever loosens.
"""

import gzip
import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
STATIC = REPO / "static"
INDEX = STATIC / "index.html"

# ── Budgets ──────────────────────────────────────────────────────────────────
# Set at the 2026-08-31 measurement + 2% headroom, so ordinary churn does not
# trip the gate but a new bundle does.
#
# These come DOWN as each payload item lands. The plan and the numbers behind
# them are in MOBILE-WEB-DEVELOPMENT.md §12 P1:
#
#   P1.1  split i18n.js per locale     -408.4 KiB  DONE -> 1089.1 KiB
#   P1.3  lazy-load xterm               -67.0 KiB   DONE -> 1022.1 KiB
#   P1.4  split CSS core vs skins       -18.4 KiB   next
#   P1.2  lazy-load panels.js          -154.1 KiB   blocked, see §12 P1.2
#
# Lowering a budget after a split is part of that split's commit. Leaving it
# high afterwards re-opens exactly the room the split just reclaimed.
#
# ── Raised once, 2026-08-31, for P4.2 ────────────────────────────────────────
#   1_067_000 -> 1_083_000 (+15.6 KiB)
#
#   `static/native.js` (5.1 KiB gzip) put the total 5,251 bytes over, and this
#   gate caught it — which is the gate working, so the increase is recorded here
#   rather than absorbed. It buys five OS integrations: Share Target, Web Share,
#   App Badging, View Transitions and haptics.
#
#   Why eager rather than lazy: four of the five are only ever called from a user
#   gesture and would lazy-load happily, but the Share Target inbox is drained at
#   BOOT — the app can be opened *by* a share — and deferring that behind a fetch
#   would mean the shared text arrives after the composer is already on screen.
#   Measured cost of carrying it: no resolvable change in Lighthouse mobile
#   (75-77 before and after, LCP variance ±1.1 s swamps it) and ~5 ms of parse.
#
#   Headroom is +1%, NOT the +2% used for the original figure. 2% of the new
#   total is 21 KiB — enough for another native.js-sized module to land
#   unnoticed, which defeats the purpose. 1% absorbs comment churn and trips on
#   the second new bundle.
TOTAL_COLD_BUDGET_BYTES = 1_083_000

# Per-file ceilings for the heaviest, so one file cannot quietly consume the
# whole shared allowance while the total still passes.
PER_FILE_BUDGET_BYTES = {
    "static/ui.js": 287_000,
    "static/panels.js": 161_000,
    "static/style.css": 104_000,
    # Post-split: runtime + the English fallback chain + the manifest of all 16
    # languages. A new language adds ~30 KiB to its OWN bundle and only its
    # manifest row here, which is the property the split bought.
    "static/i18n/core.js": 41_000,
}

# One locale bundle is fetched per reader, by the loader in index.html rather
# than a <script> tag, so cold_path_assets() cannot see it. Budget the LARGEST
# of them: the gate should describe the worst-off reader, not the luckiest.
LOCALE_DIR = STATIC / "i18n"
PER_LOCALE_BUDGET_BYTES = 40_000

# Referenced by index.html but not part of the JS/CSS payload this gate governs.
# Icons are small, cached hard, and not render-blocking.
_NON_PAYLOAD_SUFFIXES = (".png", ".svg", ".ico", ".webmanifest", ".json")


def _gzip6(path: Path) -> int:
    """Transfer size as `_serve_static` produces it (api/routes.py)."""
    return len(gzip.compress(path.read_bytes(), 6))


def cold_path_assets() -> list[Path]:
    """Every script and stylesheet index.html pulls in on a cold load.

    Parsed rather than listed, so a newly added tag is inside the budget from
    the moment someone writes it.
    """
    html = INDEX.read_text(encoding="utf-8")
    refs: list[str] = []
    refs += re.findall(r'<script[^>]*\ssrc="([^"]+)"', html)
    for tag in re.findall(r"<link\b[^>]*>", html):
        if 'rel="stylesheet"' in tag:
            m = re.search(r'\shref="([^"]+)"', tag)
            if m:
                refs.append(m.group(1))

    assets, seen = [], set()
    for ref in refs:
        # Strip the cache-buster; the file on disk has no ?v=.
        rel = ref.split("?", 1)[0]
        if rel.startswith(("http://", "https://", "//", "data:")):
            # Vendored-assets policy is enforced by
            # tests/test_vendored_frontend_assets.py; not this gate's job.
            continue
        if rel.lower().endswith(_NON_PAYLOAD_SUFFIXES):
            continue
        path = REPO / rel
        if path.is_file() and path not in seen:
            seen.add(path)
            assets.append(path)
    return assets


def _report(sizes: dict[str, int]) -> str:
    lines = [
        f"  {name:<62} {size / 1024:8.1f} KiB"
        for name, size in sorted(sizes.items(), key=lambda kv: -kv[1])
    ]
    return "\n".join(lines)


def test_index_html_reference_parsing_still_works():
    """A guard on the guard.

    Every assertion below is derived from this parse. If a markup change makes
    it return nothing, the budget would pass trivially and the gate would be
    silently dead — the same silence it was written to end.
    """
    assets = cold_path_assets()
    names = {a.relative_to(REPO).as_posix() for a in assets}

    assert len(assets) >= 15, f"suspiciously few cold-path assets: {sorted(names)}"
    # Anchors: the i18n core, the stylesheet, and a vendored asset. If the parse
    # stops seeing these, it has broken rather than the page having slimmed.
    assert "static/i18n/core.js" in names
    assert "static/style.css" in names
    assert any("vendor/" in n for n in names)
    assert not any(n.endswith((".png", ".svg", ".ico")) for n in names)
    # The monolith is the authored source, not a shipped asset. If it comes back
    # onto the cold path the split has been undone and 485 KiB is back.
    assert "static/i18n.js" not in names, (
        "index.html is loading the whole 16-language i18n.js again — "
        "it should load static/i18n/core.js plus one locale bundle"
    )


def _worst_case_locale_bundle() -> Path:
    """The largest single-language bundle — the reader who pays the most."""
    bundles = [p for p in LOCALE_DIR.glob("*.js") if p.name != "core.js"]
    assert bundles, "no locale bundles found — run scripts/split_i18n.py"
    return max(bundles, key=_gzip6)


def test_cold_load_payload_is_within_budget():
    """The whole point: bound what a phone downloads before the app works."""
    sizes = {
        asset.relative_to(REPO).as_posix(): _gzip6(asset)
        for asset in cold_path_assets()
    }
    sizes["static/index.html"] = _gzip6(INDEX)
    # Fetched by the loader in index.html rather than by a tag, so it is part of
    # the cold load even though the HTML parse cannot see it.
    worst_locale = _worst_case_locale_bundle()
    sizes[worst_locale.relative_to(REPO).as_posix() + "  (worst-case locale)"] = _gzip6(
        worst_locale
    )
    total = sum(sizes.values())

    assert total <= TOTAL_COLD_BUDGET_BYTES, (
        f"\nCold-load payload is over budget.\n"
        f"  now:    {total:>9,} bytes ({total / 1024:.1f} KiB)\n"
        f"  budget: {TOTAL_COLD_BUDGET_BYTES:>9,} bytes "
        f"({TOTAL_COLD_BUDGET_BYTES / 1024:.1f} KiB)\n"
        f"  over by:{total - TOTAL_COLD_BUDGET_BYTES:>9,} bytes "
        f"({(total - TOTAL_COLD_BUDGET_BYTES) / 1024:.1f} KiB)\n\n"
        f"Every byte here is downloaded before the app is usable.\n"
        f"Current breakdown (gzip -6):\n{_report(sizes)}\n\n"
        f"If the growth is a real feature, raise TOTAL_COLD_BUDGET_BYTES in this\n"
        f"file IN THE SAME COMMIT so the increase gets reviewed. If it is not,\n"
        f"the list above shows where it went.\n"
    )


@pytest.mark.parametrize("rel,budget", sorted(PER_FILE_BUDGET_BYTES.items()))
def test_individual_heavy_files_stay_within_their_own_budget(rel, budget):
    """A shared total lets one file absorb everyone else's headroom.

    These four are 68% of the payload, so they get named ceilings: growth in
    them should be a decision, not a side effect.
    """
    path = REPO / rel
    assert path.is_file(), f"{rel} is gone — update PER_FILE_BUDGET_BYTES"
    size = _gzip6(path)

    assert size <= budget, (
        f"\n{rel} is over its own budget.\n"
        f"  now:    {size:>9,} bytes ({size / 1024:.1f} KiB)\n"
        f"  budget: {budget:>9,} bytes ({budget / 1024:.1f} KiB)\n"
        f"  over by:{size - budget:>9,} bytes ({(size - budget) / 1024:.1f} KiB)\n"
    )


def test_no_single_language_bundle_is_oversized():
    """Every reader downloads exactly one of these, so the ceiling is per-file.

    A language that grows past the others is not a shared cost — it is a cost
    borne entirely by the people who read that language, which makes it easy to
    miss for everyone reviewing in English.
    """
    oversized = {
        p.name: _gzip6(p)
        for p in LOCALE_DIR.glob("*.js")
        if p.name != "core.js" and _gzip6(p) > PER_LOCALE_BUDGET_BYTES
    }
    assert not oversized, (
        f"locale bundles over {PER_LOCALE_BUDGET_BYTES / 1024:.1f} KiB: "
        + ", ".join(f"{n} ({s / 1024:.1f} KiB)" for n, s in sorted(oversized.items()))
    )


def test_every_budgeted_file_is_actually_on_the_cold_path():
    """Keeps the per-file budgets honest.

    Once a file is lazy-loaded it is no longer part of the cold payload, and a
    ceiling left behind here would go on constraining a file that costs the
    first load nothing. Splits are supposed to REMOVE entries from this dict.
    """
    on_cold_path = {a.relative_to(REPO).as_posix() for a in cold_path_assets()}
    stale = set(PER_FILE_BUDGET_BYTES) - on_cold_path
    assert not stale, (
        f"{sorted(stale)} have per-file budgets but are no longer loaded by "
        f"index.html. If they were made lazy, drop them from "
        f"PER_FILE_BUDGET_BYTES and lower TOTAL_COLD_BUDGET_BYTES by their size."
    )


def test_the_gzip_level_matches_what_the_server_sends():
    """Level 6, not gzip.compress's default 9.

    Measuring at 9 would understate every number in this file and make the
    budget describe a payload no browser ever receives.
    """
    routes = (REPO / "api" / "routes.py").read_text(encoding="utf-8")
    assert "compresslevel=6" in routes, (
        "api/routes.py no longer gzips static assets at level 6 — _gzip6() in "
        "this file must be changed to match, and every budget re-measured."
    )
