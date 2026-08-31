"""The page must not load runtime assets from a CDN.

WHY THIS EXISTS
  index.html used to pull seven assets from cdn.jsdelivr.net at page load:
  Prism core, the Prism autoloader, the Prism theme, xterm.js, its two addons,
  and xterm's stylesheet. Measured in a headless browser with egress blocked,
  all seven failed on every viewport, which meant:

    - no syntax highlighting and no embedded terminal on a VPS behind a strict
      outbound firewall (a normal, security-conscious self-host setup),
    - the service worker could not pre-cache them, because a cross-origin
      opaque response is not something it can serve back, so the "offline app
      shell" was never actually complete,
    - an extra third-party TLS round-trip on mobile networks,
    - and a blanket `https://cdn.jsdelivr.net` grant in script-src, meaning any
      script on that CDN was executable inside an authenticated page.

  They are vendored under static/vendor now. This test keeps them there.

NOTHING IS ALLOWED FROM A CDN ANY MORE
  PDF.js and Mermaid were the last two holdouts: lazily imported from jsdelivr
  the first time a PDF or a diagram was opened, and the only reason the CSP
  still named a third-party script origin. They are vendored too, so the ban
  below is now total rather than "eager assets only".

  The ban targets the URL form (`https://cdn.jsdelivr.net`, `//cdn.jsdelivr.net`)
  rather than the bare hostname, deliberately: several files explain in prose
  WHY the CDN is gone, and a test that forbids saying its name would push
  someone to delete the explanation instead of keeping the property.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).parent.parent
STATIC = REPO / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
BOOT = (STATIC / "boot.js").read_text(encoding="utf-8")
SW = (STATIC / "sw.js").read_text(encoding="utf-8")

# Any way of actually writing a jsdelivr URL. Prose mentioning the bare hostname
# is fine; a fetchable URL is not.
CDN_URL_RE = re.compile(r"(?:https?:)?//cdn\.jsdelivr\.net", re.IGNORECASE)

# Vendored assets the page pulls in up front. These are referenced by
# index.html and pre-cached by the service worker.
VENDORED_EAGER = [
    "vendor/prismjs/1.29.0/components/prism-core.min.js",
    "vendor/prismjs/1.29.0/plugins/autoloader/prism-autoloader.min.js",
    "vendor/prismjs/1.29.0/themes/prism-tomorrow.min.css",
    "vendor/prismjs/1.29.0/themes/prism.min.css",
]

# Vendored assets fetched at runtime, the first time the feature is used.
# Still local and still cache-busted — only the TIMING differs — so the
# no-CDN and immutable-caching contracts apply to them unchanged. They are
# deliberately NOT pre-cached: xterm is ~68 KiB gzipped, and pre-caching it
# would re-spend exactly what loading it lazily saves.
VENDORED_LAZY = {
    "vendor/xterm/5.3.0/xterm.js": "terminal.js",
    "vendor/xterm/5.3.0/xterm.css": "terminal.js",
    "vendor/xterm/5.3.0/xterm-addon-fit.js": "terminal.js",
    "vendor/xterm/5.3.0/xterm-addon-web-links.js": "terminal.js",
    # ~4.7 MB between them, which is exactly why they load on demand: opening a
    # PDF or rendering a diagram pays for them, a page load never does.
    "vendor/pdfjs/4.9.155/pdf.min.mjs": "ui.js",
    "vendor/pdfjs/4.9.155/pdf.worker.min.mjs": "ui.js",
    "vendor/mermaid/10.9.3/mermaid.min.js": "ui.js",
}

VENDORED = VENDORED_EAGER + list(VENDORED_LAZY)

# Files that must never contain a fetchable CDN URL. Every asset the frontend
# loads is under static/vendor/, and the CSP is built from api/helpers.py.
NO_CDN_URL_FILES = [
    STATIC / "index.html",
    STATIC / "boot.js",
    STATIC / "ui.js",
    STATIC / "terminal.js",
    STATIC / "sw.js",
    STATIC / "panels.js",
    STATIC / "messages.js",
    STATIC / "workspace.js",
    REPO / "api" / "helpers.py",
]


def test_vendored_files_are_present():
    missing = [rel for rel in VENDORED if not (STATIC / rel).is_file()]
    assert not missing, f"vendored asset(s) missing from static/: {missing}"


def test_prism_grammars_are_vendored():
    """The autoloader fetches one file per language on demand."""
    components = STATIC / "vendor" / "prismjs" / "1.29.0" / "components"
    grammars = list(components.glob("prism-*.min.js"))
    assert len(grammars) > 100, (
        f"expected the full Prism grammar set under {components}, found {len(grammars)}"
    )


def test_no_cdn_script_or_stylesheet_in_page():
    """No <script src> or <link href> may point at a CDN."""
    urls = re.findall(r'<(?:script|link)[^>]*?(?:src|href)="([^"]+)"', HTML)
    remote = [u for u in urls if u.startswith(("http://", "https://"))]
    assert not remote, (
        f"index.html loads {remote} from a remote origin — vendor it under "
        f"static/vendor/ instead so air-gapped deployments and the service "
        f"worker's offline shell keep working"
    )


def test_every_eager_vendored_asset_is_referenced_with_a_cache_buster():
    """?v= is what buys the immutable far-future Cache-Control in _serve_static."""
    for rel in VENDORED_EAGER:
        if rel.endswith("prism.min.css"):
            continue  # swapped in at runtime by boot.js, not present in the HTML
        assert f'"static/{rel}?v=__WEBUI_VERSION__"' in HTML, (
            f"static/{rel} must be referenced with ?v=__WEBUI_VERSION__ in index.html"
        )


def test_lazy_vendored_assets_are_loaded_locally_and_cache_busted():
    """Loading late must not mean losing the vendoring or the caching.

    A runtime loader is the easy place to reintroduce a CDN URL, or to drop the
    ?v= and silently downgrade the asset to max-age=300.
    """
    for rel, loader_name in sorted(VENDORED_LAZY.items()):
        loader = (STATIC / loader_name).read_text(encoding="utf-8")
        assert f"static/{rel}" in loader, (
            f"static/{rel} is not referenced by {loader_name}; if it moved, this "
            f"list is stale"
        )
        assert not CDN_URL_RE.search(loader), (
            f"{loader_name} must resolve vendored assets locally, not from a CDN"
        )
        assert "__HERMES_WEBUI_BUNDLE_VERSION__" in loader, (
            f"{loader_name} must append the ?v= cache-buster, or the lazy assets "
            f"lose immutable caching and are refetched every 5 minutes"
        )


def test_lazy_vendored_assets_are_not_in_the_page_head():
    """The whole point: they must not be paid for on every page load."""
    for rel in VENDORED_LAZY:
        assert f'"static/{rel}?v=__WEBUI_VERSION__"' not in HTML, (
            f"static/{rel} is eagerly referenced by index.html again — that undoes "
            f"the lazy load"
        )


def test_autoloader_points_at_the_vendored_grammars():
    assert "Prism.plugins.autoloader.languages_path" in HTML, (
        "the autoloader must be told where the vendored grammars live, otherwise "
        "it resolves language files against its built-in CDN path"
    )
    assert "static/vendor/prismjs/1.29.0/components/" in HTML


def test_boot_swaps_prism_theme_to_vendored_paths():
    assert "cdn.jsdelivr.net" not in BOOT, (
        "boot.js must not reference a CDN — it swaps the Prism theme on every "
        "light/dark change"
    )
    assert "static/vendor/prismjs/1.29.0/themes/" in BOOT


def test_theme_swap_preserves_the_cache_buster():
    """Dropping ?v= on swap would downgrade the stylesheet to max-age=300."""
    assert "_prismVersionQuery" in BOOT, (
        "the theme swap must carry the existing ?v= query across to the new href"
    )


def test_theme_swap_compares_resolved_urls():
    """link.href is absolute; comparing it to a relative string never matches."""
    assert "document.baseURI" in BOOT and "_wantAbs" in BOOT, (
        "the theme swap must compare the resolved absolute URL, or it re-assigns "
        "(and re-fetches) the stylesheet on every theme sync"
    )


def test_service_worker_precaches_the_eager_vendored_assets():
    """This is the point of vendoring: the offline shell can finally hold them."""
    for rel in VENDORED_EAGER:
        assert f"'./static/{rel}'" in SW, (
            f"static/{rel} must be in sw.js SHELL_ASSETS so the offline shell is "
            f"complete"
        )


def test_service_worker_does_not_precache_the_lazy_vendored_assets():
    """Pre-caching downloads it anyway, just on a different schedule.

    Nothing is lost offline: a terminal is a live PTY on the server, so having
    xterm cached without a backend to talk to buys nothing.
    """
    for rel in VENDORED_LAZY:
        assert f"'./static/{rel}'" not in SW, (
            f"static/{rel} is pre-cached again, which re-spends the bytes the "
            f"lazy load saves"
        )


def test_terminal_failure_message_does_not_blame_the_cdn():
    terminal_js = (STATIC / "terminal.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in terminal_js, (
        "terminal.js still tells users to check network access to a CDN it no "
        "longer uses"
    )


# ── The total jsdelivr ban ───────────────────────────────────────────────────


def test_no_frontend_file_contains_a_fetchable_cdn_url():
    """The whole point of vendoring PDF.js and Mermaid.

    Before this, `cdn.jsdelivr.net` was still reachable from three places in
    ui.js and three CSP directives, so "air-gapped deployment" was true for the
    page load and false the moment someone opened a PDF.
    """
    offenders = {}
    for path in NO_CDN_URL_FILES:
        hits = CDN_URL_RE.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders[path.relative_to(REPO).as_posix()] = len(hits)
    assert not offenders, (
        f"fetchable jsdelivr URL(s) reintroduced: {offenders}. Vendor the asset "
        f"under static/vendor/ and load it through the existing lazy loaders "
        f"instead — the CSP no longer allows that origin, so the fetch would be "
        f"blocked in production even though it works in a permissive dev setup"
    )


def test_csp_names_no_cdn_origin():
    """The policy side of the same property."""
    from api.helpers import _build_csp_enforced_policy

    policy = _build_csp_enforced_policy("")
    assert "jsdelivr" not in policy, f"CSP names jsdelivr again: {policy}"
    for directive in ("script-src", "worker-src", "connect-src"):
        match = re.search(rf"{directive}\s+([^;]+)", policy)
        assert match, f"{directive} must exist in the CSP"
        assert "jsdelivr" not in match.group(1)


def test_pdfjs_worker_is_resolved_to_an_absolute_url():
    """A blob: module resolves relative specifiers against the blob URL.

    ui.js bootstraps PDF.js through a blob module script. If the vendored paths
    were passed through as relative strings, the import would resolve against
    `blob:https://host/<uuid>` and 404 — which is why _vendorAssetUrl runs them
    through `new URL(..., document.baseURI)`.
    """
    ui_js = (STATIC / "ui.js").read_text(encoding="utf-8")
    assert "function _vendorAssetUrl(" in ui_js
    assert "document.baseURI" in ui_js
    for rel in ("vendor/pdfjs/4.9.155/pdf.min.mjs", "vendor/pdfjs/4.9.155/pdf.worker.min.mjs"):
        assert f"_vendorAssetUrl('static/{rel}')" in ui_js, (
            f"static/{rel} must be resolved through _vendorAssetUrl, or the "
            f"blob module import cannot find it"
        )


def test_every_pinned_sri_hash_matches_the_vendored_file():
    """A stale SRI hash fails closed and silently.

    ui.js pins a sha384 for each vendored library it loads at runtime. Nothing
    checked those hashes against the bytes on disk, so bumping a vendored file
    without regenerating its hash would make the feature stop working with no
    error anyone would connect to the change — diagrams simply never render.

    Every hash below was verified against its file at vendoring time; this keeps
    them verified.
    """
    import base64
    import hashlib

    ui_js = (STATIC / "ui.js").read_text(encoding="utf-8")
    pinned = dict(
        re.findall(
            r"_vendorAssetUrl\('static/([^']+)'\);\s*\n\s*\w+\.integrity='sha384-([^']+)'",
            ui_js,
        )
    )
    assert pinned, "no pinned SRI hashes found in ui.js — has the loader shape changed?"

    for rel, expected in sorted(pinned.items()):
        path = STATIC / rel
        assert path.is_file(), f"ui.js pins a hash for static/{rel}, which does not exist"
        actual = base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()
        assert actual == expected, (
            f"static/{rel} does not match the sha384 pinned in ui.js.\n"
            f"  pinned: sha384-{expected}\n"
            f"  actual: sha384-{actual}\n"
            f"The browser will refuse to execute it. Update the integrity= value "
            f"in the same commit as the vendored file."
        )


def test_the_three_lazily_loaded_libraries_all_pin_a_hash():
    """A guard on the guard above: it can only check hashes that exist."""
    ui_js = (STATIC / "ui.js").read_text(encoding="utf-8")
    for rel in (
        "vendor/mermaid/10.9.3/mermaid.min.js",
        "vendor/katex/0.16.22/katex.min.js",
        "vendor/js-yaml/4.1.0/js-yaml.min.js",
    ):
        start = ui_js.index(f"_vendorAssetUrl('static/{rel}')")
        assert "integrity='sha384-" in ui_js[start:start + 250], (
            f"the loader for static/{rel} no longer pins an SRI hash"
        )


def test_vendored_libraries_ship_their_licenses():
    for rel in ("vendor/mermaid/10.9.3", "vendor/pdfjs/4.9.155"):
        assert (STATIC / rel / "LICENSE").is_file(), (
            f"static/{rel}/LICENSE is missing — vendoring a dependency means "
            f"redistributing it, and its license has to travel with it"
        )
