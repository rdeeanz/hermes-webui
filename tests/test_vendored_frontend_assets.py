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

WHAT IS STILL ALLOWED
  ui.js lazily imports PDF.js and Mermaid from the CDN when the user opens a PDF
  or renders a diagram. Those are not page-load assets, and the CSP grant for
  them is path-scoped rather than whole-origin. If they are ever vendored too,
  jsdelivr can leave the policy entirely.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).parent.parent
STATIC = REPO / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
BOOT = (STATIC / "boot.js").read_text(encoding="utf-8")
SW = (STATIC / "sw.js").read_text(encoding="utf-8")

VENDORED = [
    "vendor/prismjs/1.29.0/components/prism-core.min.js",
    "vendor/prismjs/1.29.0/plugins/autoloader/prism-autoloader.min.js",
    "vendor/prismjs/1.29.0/themes/prism-tomorrow.min.css",
    "vendor/prismjs/1.29.0/themes/prism.min.css",
    "vendor/xterm/5.3.0/xterm.js",
    "vendor/xterm/5.3.0/xterm.css",
    "vendor/xterm/5.3.0/xterm-addon-fit.js",
    "vendor/xterm/5.3.0/xterm-addon-web-links.js",
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


def test_every_vendored_asset_is_referenced_with_a_cache_buster():
    """?v= is what buys the immutable far-future Cache-Control in _serve_static."""
    for rel in VENDORED:
        if rel.endswith("prism.min.css"):
            continue  # swapped in at runtime by boot.js, not present in the HTML
        assert f'"static/{rel}?v=__WEBUI_VERSION__"' in HTML, (
            f"static/{rel} must be referenced with ?v=__WEBUI_VERSION__ in index.html"
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


def test_service_worker_precaches_the_vendored_assets():
    """This is the point of vendoring: the offline shell can finally hold them."""
    for rel in VENDORED:
        assert f"'./static/{rel}'" in SW, (
            f"static/{rel} must be in sw.js SHELL_ASSETS so the offline shell is "
            f"complete"
        )


def test_terminal_failure_message_does_not_blame_the_cdn():
    terminal_js = (STATIC / "terminal.js").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in terminal_js, (
        "terminal.js still tells users to check network access to a CDN it no "
        "longer uses"
    )
