"""Dev-only Playwright screenshot capture for all ten dashboard pages.

Usage::

    poetry run python scripts/dashboard_screenshots.py
    poetry run python scripts/dashboard_screenshots.py --base-url http://localhost:8501 --out-dir /tmp/screens
    poetry run python scripts/dashboard_screenshots.py --full-height --out-dir docs/phase-7.2/wave-h-assets/audit

The script navigates through the sidebar (not by guessing URLs) so it works
regardless of Streamlit's URL-slug behaviour. It is intentionally **not**
invoked by ``make check``.

A capture is taken only once the page has **fully settled**: the running
indicator (the toolbar's "Stop" button) and the spinner/skeleton are asserted
absent immediately before every screenshot, retried a bounded number of times,
and the page fails loudly rather than writing a mid-run image (Step 0f — a Wave B
``welfare.png`` froze the transient "Stop" widget into the frame).

``--full-height`` (Wave H P4) captures the whole page: the viewport height is set
from the main scroll container's ``scrollHeight`` (bounded to
:data:`_MAX_FULL_HEIGHT` px) before each shot, so a tall page is captured
completely instead of clipped to 900 px. It defaults off, so the shipped
1440x900 viewport set is unchanged.
"""

import argparse
import sys
from pathlib import Path
from typing import Final

from playwright.sync_api import Page, sync_playwright

from dashboard.i18n import t
from dashboard.navigation import PAGES

DEFAULT_BASE_URL: Final[str] = "http://localhost:8501"
DEFAULT_OUT_DIR: Final[Path] = Path("docs/phase-7.2/wave-a-assets/after-global-look")

_VIEWPORT_WIDTH: Final[int] = 1440
_VIEWPORT_HEIGHT: Final[int] = 900

#: Streamlit scrolls an inner container (``stMain``), **not**
#: ``stMainBlockContainer`` — the latter is the padded content block. Scrolling
#: the block container is a no-op (a Wave D observation, fixed in P4).
_MAIN_SCROLL_SELECTOR: Final[str] = '[data-testid="stMain"]'

#: Upper bound for ``--full-height``: a pathological page must not ask Chromium
#: for an unbounded surface.
_MAX_FULL_HEIGHT: Final[int] = 12_000

#: Quiet delay after a viewport resize so the reflow completes before the content
#: height is measured (``--full-height``).
_REFLOW_MS: Final[int] = 200

#: Elements that mean the app is still running or has not finished painting.
#: ``stStatusWidget`` is the transient running indicator (the toolbar's "Stop"
#: button) that a Wave B capture froze into ``welfare.png`` mid-run; the spinner
#: and skeleton are the other two transient paint states. A capture is only
#: taken once every one of them is absent from the DOM.
_TRANSIENT_SELECTORS: Final[tuple[str, ...]] = (
    '[data-testid="stStatusWidget"]',
    '[data-testid="stSpinner"]',
    '[data-testid="stSkeleton"]',
)

#: Bounded settle loop: poll for the transients to clear, re-check after a short
#: quiet delay, and give up loudly rather than saving a mid-run image.
_SETTLE_RETRIES: Final[int] = 20
_SETTLE_POLL_MS: Final[int] = 250
_SETTLE_QUIET_MS: Final[int] = 500


class ScreenshotNotReadyError(RuntimeError):
    """Raised when a page still shows transient elements at capture time."""


def transient_selectors(page: Page) -> list[str]:
    """Return the transient selectors currently present in the DOM."""
    return [selector for selector in _TRANSIENT_SELECTORS if page.locator(selector).count() > 0]


def wait_until_settled(page: Page, page_key: str) -> None:
    """Block until no transient element is present, then let the paint settle.

    The running indicator and the spinner/skeleton are asserted absent
    **immediately before** the capture. A run that is still in flight is waited
    for (bounded), then the check is repeated once more after a short quiet
    delay, because a rerun can start a new run during that delay.

    Args:
        page: The Playwright page holding the rendered dashboard
        page_key: Registry key of the page, used in the failure message

    Raises:
        ScreenshotNotReadyError: When a transient element is still present after
            the bounded retries, so a bad image is never written.
    """
    for _ in range(_SETTLE_RETRIES):
        if not transient_selectors(page):
            page.wait_for_timeout(_SETTLE_QUIET_MS)
            if not transient_selectors(page):
                return
        page.wait_for_timeout(_SETTLE_POLL_MS)
    present = transient_selectors(page)
    message = (
        f"page {page_key!r} still shows transient elements after "
        f"{_SETTLE_RETRIES} retries: {present}; refusing to save a mid-run image"
    )
    raise ScreenshotNotReadyError(message)


def wait_ready(page: Page, page_key: str, timeout_ms: int = 30000) -> None:
    """Wait for the app root and main block, then for a fully settled page."""
    page.wait_for_selector('[data-testid="stApp"]', timeout=timeout_ms)
    page.wait_for_selector('[data-testid="stMainBlockContainer"]', timeout=timeout_ms)
    wait_until_settled(page, page_key)


def neutralise(page: Page) -> None:
    """Close open dropdowns and reset scroll/pointer state before a capture.

    Pressing Escape dismisses any expanded ``st.multiselect`` / dropdown menus
    so they do not occlude the screenshot. Moving the mouse to a neutral spot
    (the sidebar top) avoids hover-highlight artifacts, and scrolling the main
    scroll container to the top ensures a consistent capture starting point.

    The scroll targets ``[data-testid="stMain"]`` — Streamlit's real scroll
    container. ``stMainBlockContainer`` (which the script scrolled before P4) is
    the padded content block and is **not** scrollable, so its ``scrollTo`` was a
    no-op.
    """
    page.keyboard.press("Escape")
    # Move the mouse to the sidebar so no chart/table row is accidentally hovered.
    page.mouse.move(10, 10)
    # Scroll the real scroll container to the top so each capture starts at the
    # same vertical position regardless of where the previous page left the scroll.
    page.evaluate(f"document.querySelector({_MAIN_SCROLL_SELECTOR!r})?.scrollTo(0, 0)")


def main_scroll_height(page: Page) -> int:
    """Return the main scroll container's content height in CSS pixels.

    ``0`` when the container is absent, so a caller can fall back to the default
    viewport height instead of asking Chromium for a zero-height surface.
    """
    value = page.evaluate(
        f"() => {{ const m = document.querySelector({_MAIN_SCROLL_SELECTOR!r});"
        " return m ? m.scrollHeight : 0; }"
    )
    return int(value) if value else 0


def full_height_viewport(page: Page) -> int:
    """Set the viewport tall enough for the whole page, and return its height.

    The viewport is first reset to the default height so the measurement is
    independent of the previous page: ``scrollHeight`` never reports less than
    the current viewport height, so a page measured while the viewport is still
    grown from the previous shot would inherit that floor. After the reset the
    height is the main scroll container's ``scrollHeight`` bounded by
    :data:`_MAX_FULL_HEIGHT`, so a tall page is captured completely and a
    pathological one cannot request an unbounded surface. The width is unchanged.
    """
    page.set_viewport_size({"width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT})
    page.wait_for_timeout(_REFLOW_MS)
    height = min(max(main_scroll_height(page), _VIEWPORT_HEIGHT), _MAX_FULL_HEIGHT)
    page.set_viewport_size({"width": _VIEWPORT_WIDTH, "height": height})
    return height


def capture(base_url: str, out_dir: Path, *, full_height: bool = False) -> dict[str, Path]:
    """Capture one screenshot per registered page.

    Without ``full_height`` each shot is the 1440x900 viewport (unchanged from
    before P4). With it, the viewport height is raised to the page's full content
    height (bounded) before each shot.

    Returns:
        Mapping of page key to the written PNG path.

    Raises:
        ScreenshotNotReadyError: When a page is still running at capture time, so
            no bad image is written for it.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT})
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)

        # The first registered page is the default; capture it first, then
        # click through the rest in registry order.
        page_keys: list[str] = [spec.key for spec in PAGES]
        for spec in PAGES:
            label = t(f"nav.{spec.key}")
            if spec.key != page_keys[0]:
                nav_link = page.locator(f'[data-testid="stSidebarNavLink"]:has-text("{label}")')
                nav_link.click(timeout=10000)

            wait_ready(page, spec.key)
            neutralise(page)
            # Re-assert immediately before the capture: `neutralise` can trigger
            # a rerun, and a rerun that is still in flight must not be frozen
            # into the frame.
            wait_until_settled(page, spec.key)
            if full_height:
                # Growing the viewport can reflow the page, so settle and
                # re-anchor to the top before the shot.
                full_height_viewport(page)
                neutralise(page)
                wait_until_settled(page, spec.key)
            out_path = out_dir / f"{spec.key}.png"
            page.screenshot(path=str(out_path), full_page=False)
            results[spec.key] = out_path
            print(f"captured {spec.key}: {out_path}")

        browser.close()

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture screenshots of every dashboard page.")
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
    parser.add_argument(
        "--full-height",
        action="store_true",
        help=(
            "Capture each page at its full content height (the main scroll "
            f"container's scrollHeight, bounded to {_MAX_FULL_HEIGHT} px) instead "
            "of the default 1440x900 viewport"
        ),
    )
    args = parser.parse_args(argv)

    try:
        results = capture(args.base_url, args.out_dir, full_height=args.full_height)
    except Exception as exc:
        print(f"error: screenshot capture failed: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(results)} screenshots to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
