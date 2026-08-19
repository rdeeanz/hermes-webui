#!/usr/bin/env python3
"""Responsive layout gate — the invariants a real browser can see and source text cannot.

WHY THIS EXISTS
  The workspace panel was completely unopenable between 641px and 900px, and the
  existing test suite could not see it. Every individual CSS rule involved was
  present and syntactically valid; the mobile tests assert things like

      assert re.search(r'\\.messages\\{[^}]*touch-action:\\s*pan-y', CSS)

  which proves a declaration is written, not that the resulting layout works. The
  defect lived in the *interaction* between two correct rules at one width — a
  cascade outcome, which only a rendering engine computes. tests/browser_smoke.py
  does run a real browser, but only at the default desktop viewport.

  This closes that gap: it renders the real page at real device widths and asserts
  outcomes rather than source text.

SCOPE
  Agent-free, like browser_smoke.py, so it runs in CI where hermes-agent is not
  installed. It checks layout reachability and geometry, not conversation flow.

USAGE
  python tests/browser_responsive.py
  (Requires: playwright + chromium. Boots server.py on an ephemeral port with an
  isolated temp state dir and no agent.)

EXIT CODES
  0 — every viewport satisfied every invariant
  1 — at least one invariant failed (regression)
  2 — environment/setup failure (server didn't boot, playwright missing, etc.)
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (label, width, height, emulate a touch device)
#
# Chosen to straddle every boundary in the breakpoint contract rather than to
# enumerate popular handsets: one narrow phone, one tall phone, both sides of
# --bp-phone, both sides of --bp-tablet, and one ordinary desktop.
VIEWPORTS = [
    ("phone-375", 375, 667, True),
    ("phone-393", 393, 852, True),
    ("phone-max-640", 640, 800, True),
    ("tablet-641", 641, 900, True),
    ("tablet-768", 768, 1024, True),
    ("tablet-820", 820, 1180, True),
    ("tablet-max-1024", 1024, 768, True),
    ("desktop-1025", 1025, 800, False),
    ("desktop-1440", 1440, 900, False),
]

# Interactive controls below this box are hard to hit with a thumb. The repo
# already commits to 44px in style.css; 40 leaves room for borders/rounding
# while still catching genuinely tiny targets.
MIN_TOUCH_PX = 40


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url, proc, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


# Evaluated in the page. Returns the facts each invariant is checked against.
PROBE = """() => {
  const de = document.documentElement;
  const W = de.clientWidth;

  const state = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return { present: false };
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      present: true,
      hidden: cs.display === 'none' || cs.visibility === 'hidden',
      onScreen: r.width > 0 && r.height > 0 && r.right > 0 && r.left < W,
      left: Math.round(r.left), right: Math.round(r.right),
      width: Math.round(r.width),
      position: cs.position,
    };
  };

  // Only count elements that actually contribute scrollable overflow. A
  // position:fixed element parked off-canvas does not, and neither does anything
  // inside a clipping ancestor.
  const overflowing = [...document.querySelectorAll('body *')].filter((el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.right > W + 1;
  }).slice(0, 5).map((el) =>
    el.tagName + (el.id ? '#' + el.id : '') + '.' + String(el.className || '').slice(0, 40)
  );

  const tiny = [...document.querySelectorAll('button, a[href], [role="button"], input, select')]
    .filter((el) => {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return false;
      if (r.right < 0 || r.left > W) return false;   // off-canvas drawer contents
      return r.width < MIN_TOUCH || r.height < MIN_TOUCH;
    })
    .slice(0, 8)
    .map((el) => {
      const r = el.getBoundingClientRect();
      return (el.id ? '#' + el.id : el.tagName) + '.' +
        String(el.className || '').slice(0, 32) +
        ` ${Math.round(r.width)}x${Math.round(r.height)}`;
    });

  return {
    viewportWidth: W,
    scrollWidth: de.scrollWidth,
    horizontalOverflow: de.scrollWidth > W + 1,
    overflowing,
    sidebar: state('.sidebar'),
    rightpanel: state('.rightpanel'),
    composer: state('.composer-wrap'),
    hamburger: state('.app-titlebar-hamburger'),
    filesBtn: state('.composer-workspace-files-btn'),
    tinyTargets: tiny,
  };
}"""

# Evaluated after clicking the Files button.
PANEL_PROBE = """() => {
  const el = document.querySelector('.rightpanel');
  if (!el) return { present: false, onScreen: false };
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const W = document.documentElement.clientWidth;
  return {
    present: true,
    hidden: cs.display === 'none' || cs.visibility === 'hidden',
    onScreen: cs.display !== 'none' && r.width > 0 && r.right > 0 && r.left < W,
    left: Math.round(r.left), width: Math.round(r.width),
  };
}"""


def _check(label, width, before, after_files_click, failures):
    """Assert the invariants for one viewport."""

    def fail(msg):
        failures.append(f"[{label} @{width}px] {msg}")

    # 1. The page must never scroll sideways. This is the single most visible
    #    mobile defect and the easiest to regress.
    if before["horizontalOverflow"]:
        fail(
            f"horizontal overflow: scrollWidth={before['scrollWidth']} > "
            f"clientWidth={before['viewportWidth']}; widest: {before['overflowing']}"
        )

    # 2. The composer is the whole point of the app. It must be on screen.
    if not before["composer"]["present"] or before["composer"]["hidden"]:
        fail("composer is missing or hidden")

    # 3. The workspace panel must be reachable at every width. Below the desktop
    #    boundary that means the Files button opens a slide-over; at desktop it
    #    means the panel is in-flow. This is the invariant the tablet bug broke:
    #    the button was visible, the handler ran, and nothing appeared.
    if before["filesBtn"]["present"] and not before["filesBtn"]["hidden"]:
        if after_files_click is None:
            fail("Files button is visible but could not be clicked")
        elif not after_files_click["onScreen"]:
            fail(
                "Files button is visible but toggling it does not bring the "
                f"workspace panel on screen (left={after_files_click.get('left')}, "
                f"width={after_files_click.get('width')}, "
                f"hidden={after_files_click.get('hidden')})"
            )
    elif before["rightpanel"]["hidden"]:
        fail("workspace panel is hidden and there is no visible Files button to open it")

    # 4. Sidebar navigation must be reachable: either in-flow, or via a hamburger.
    sidebar_inflow = before["sidebar"]["present"] and before["sidebar"]["onScreen"]
    hamburger_visible = before["hamburger"]["present"] and not before["hamburger"]["hidden"]
    if not sidebar_inflow and not hamburger_visible:
        fail("sidebar is off-screen and no hamburger is shown to open it")

    # 5. Touch targets — phone widths only. Desktop legitimately uses denser
    #    controls because a mouse is precise.
    if width <= 640 and before["tinyTargets"]:
        fail(
            f"{len(before['tinyTargets'])} interactive element(s) below "
            f"{MIN_TOUCH_PX}px: {before['tinyTargets']}"
        )


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SETUP: playwright is not installed (pip install playwright)", file=sys.stderr)
        return 2

    port = _free_port()
    base = f"http://127.0.0.1:{port}/"

    with tempfile.TemporaryDirectory() as state_dir:
        env = {
            **os.environ,
            "HERMES_WEBUI_STATE_DIR": state_dir,
            "HERMES_WEBUI_HOST": "127.0.0.1",
            "HERMES_WEBUI_PORT": str(port),
            "HERMES_WEBUI_SKIP_ONBOARDING": "1",
        }
        proc = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=REPO, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            if not _wait_for_server(base, proc):
                print("SETUP: server.py did not come up", file=sys.stderr)
                if proc.poll() is not None:
                    print((proc.stdout.read() or "")[-4000:], file=sys.stderr)
                return 2

            failures = []
            # Honour an explicit Chromium path when one is provided. CI resolves the
            # browser that matches its pinned playwright version, but sandboxes and
            # dev machines often ship a single prebuilt Chromium under a different
            # build number, and the default resolver hard-fails on that mismatch.
            launch_kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            chromium_path = os.environ.get("HERMES_WEBUI_CHROMIUM", "").strip()
            if chromium_path and os.path.exists(chromium_path):
                launch_kwargs["executable_path"] = chromium_path

            with sync_playwright() as p:
                browser = p.chromium.launch(**launch_kwargs)

                # One context per input mode, resized per viewport, rather than a
                # context per viewport. Nine live contexts starve Chromium's
                # per-host socket pool once each page holds its SSE streams open,
                # and the run stalls partway through. (The server itself is fine:
                # measured separately, it serves the index instantly with 40
                # concurrent SSE streams held open.) Touch emulation is fixed at
                # context creation, so the two modes still need separate contexts.
                for touch in (True, False):
                    widths = [v for v in VIEWPORTS if v[3] is touch]
                    if not widths:
                        continue
                    ctx = browser.new_context(
                        viewport={"width": widths[0][1], "height": widths[0][2]},
                        is_mobile=touch, has_touch=touch,
                    )
                    page = ctx.new_page()
                    console_errors = []
                    page.on("console", lambda m: console_errors.append(m.text[:200])
                            if m.type == "error" else None)
                    page.on("pageerror", lambda e: console_errors.append("uncaught: " + str(e)[:200]))
                    # A navigation aborts whatever SSE streams the previous page had
                    # open, which surfaces as ERR_ABORTED on /api/sessions/events and
                    # friends. That is the browser doing the right thing, not a defect,
                    # so only genuine transport failures count here.
                    page.on("requestfailed", lambda r: console_errors.append(
                        f"failed request: {r.url[:120]} ({r.failure})"
                    ) if "ERR_ABORTED" not in (r.failure or "") else None)

                    for label, width, height, _ in widths:
                        console_errors.clear()
                        page.set_viewport_size({"width": width, "height": height})
                        page.goto(base, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(2500)

                        before = page.evaluate(PROBE.replace("MIN_TOUCH", str(MIN_TOUCH_PX)))

                        # The Files button toggles. On desktop the panel is already
                        # in-flow and open, so the first click closes it; what we are
                        # asserting is that the control visibly opens the panel, so
                        # click again when the first click closed it.
                        after = None
                        btn = page.query_selector(".composer-workspace-files-btn")
                        if btn and btn.is_visible():
                            try:
                                for _attempt in range(2):
                                    btn.click(timeout=3000)
                                    page.wait_for_timeout(600)
                                    after = page.evaluate(PANEL_PROBE)
                                    if after.get("onScreen"):
                                        break
                            except Exception as exc:  # click intercepted / not actionable
                                failures.append(f"[{label} @{width}px] Files button click failed: {exc}")

                        _check(label, width, before, after, failures)

                        if console_errors:
                            failures.append(f"[{label} @{width}px] console: {console_errors[:4]}")

                        mine = [f for f in failures if f.startswith(f"[{label} ")]
                        status = "ok" if not mine else "FAIL"
                        print(f"  {label:16s} {width:>4}px  scrollW={before['scrollWidth']:<5} {status}")
                        for m in mine:
                            print(f"      {m.split('] ', 1)[-1]}")

                    ctx.close()
                browser.close()

            if failures:
                print("\nFAILED responsive invariants:\n", file=sys.stderr)
                for f in failures:
                    print(f"  - {f}", file=sys.stderr)
                return 1

            print(f"\nAll {len(VIEWPORTS)} viewports satisfied every invariant.")
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
