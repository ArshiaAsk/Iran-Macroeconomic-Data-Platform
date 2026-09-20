"""Dev-only Playwright screenshot capture for all ten dashboard pages.

Usage::

    poetry run python scripts/dashboard_screenshots.py
    poetry run python scripts/dashboard_screenshots.py --base-url http://localhost:8501 --out-dir /tmp/screens

The script navigates through the sidebar (not by guessing URLs) so it works
regardless of Streamlit's URL-slug behaviour. It is intentionally **not**
invoked by ``make check``.
"""

import argparse
import contextlib
import sys
from pathlib import Path
from typing import Final

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from dashboard.i18n import t
from dashboard.navigation import PAGES

DEFAULT_BASE_URL: Final[str] = "http://localhost:8501"
DEFAULT_OUT_DIR: Final[Path] = Path("docs/phase-7.2/wave-a-assets/after-global-look")

_VIEWPORT_WIDTH: Final[int] = 1440
_VIEWPORT_HEIGHT: Final[int] = 900


def wait_ready(page: Page, timeout_ms: int = 30000) -> None:
    """Wait for the app root, main block and spinners/skeletons to settle."""
    page.wait_for_selector('[data-testid="stApp"]', timeout=timeout_ms)
    page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=timeout_ms)
    # Wait for any transient spinners/skeletons to disappear. If none are
    # present, the "detached" state resolves immediately.
    with contextlib.suppress(PlaywrightTimeoutError):
        page.wait_for_selector('[data-testid="stSpinner"]', state="detached", timeout=timeout_ms)
    with contextlib.suppress(PlaywrightTimeoutError):
        page.wait_for_selector('[data-testid="stSkeleton"]', state="detached", timeout=timeout_ms)
    # Wait for the running indicator (the "Stop" status widget) to be gone
    # so the capture does not freeze mid-run or include a stale toolbar state.
    with contextlib.suppress(PlaywrightTimeoutError):
        page.wait_for_selector(
            '[data-testid="stStatusWidget"]', state="detached", timeout=timeout_ms
        )
    # A small extra settle helps charts/tables finish rendering.
    page.wait_for_timeout(500)


def neutralise(page: Page) -> None:
    """Close open dropdowns and reset scroll/pointer state before a capture.

    Pressing Escape dismisses any expanded ``st.multiselect`` / dropdown menus
    so they do not occlude the screenshot. Moving the mouse to a neutral spot
    (the sidebar top) avoids hover-highlight artifacts, and scrolling the main
    container to the top ensures a consistent capture starting point.
    """
    page.keyboard.press("Escape")
    # Move the mouse to the sidebar so no chart/table row is accidentally hovered.
    page.mouse.move(10, 10)
    # Scroll the main container to the top so each capture starts at the same
    # vertical position regardless of where the previous page left the scroll.
    page.evaluate(
        """document.querySelector('[data-testid="stMainBlockContainer"]')?.scrollTo(0, 0)"""
    )


def capture(base_url: str, out_dir: Path) -> dict[str, Path]:
    """Capture one 1440x900 screenshot per registered page.

    Returns:
        Mapping of page key to the written PNG path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT})
        page.goto(base_url, wait_until="networkidle", timeout=60000)

        # The first registered page is the default; capture it first, then
        # click through the rest in registry order.
        page_keys: list[str] = [spec.key for spec in PAGES]
        for spec in PAGES:
            label = t(f"nav.{spec.key}")
            if spec.key != page_keys[0]:
                nav_link = page.locator(f'[data-testid="stSidebarNavLink"]:has-text("{label}")')
                nav_link.click(timeout=10000)

            wait_ready(page)
            neutralise(page)
            out_path = out_dir / f"{spec.key}.png"
            page.screenshot(path=str(out_path), full_page=False)
            results[spec.key] = out_path
            print(f"captured {spec.key}: {out_path}")

        browser.close()

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture 1440x900 screenshots of every dashboard page."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the running Streamlit app (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for PNGs (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args(argv)

    try:
        results = capture(args.base_url, args.out_dir)
    except Exception as exc:
        print(f"error: screenshot capture failed: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(results)} screenshots to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
