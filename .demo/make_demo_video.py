"""Record a demo video of the VibeRank dashboard running one live evaluation.

Requires the viberank server on http://127.0.0.1:8000 and Playwright
(uses the system Edge/Chrome, no browser download). Prints the click/done
timestamps so the grading wait can be time-compressed in post.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
TARGET_MODEL = "mistral-small-latest"
RAW_DIR = Path(__file__).parent / "raw"
VIEWPORT = {"width": 1440, "height": 900}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        for launch in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
            try:
                browser = pw.chromium.launch(headless=True, **launch)
                break
            except Exception:
                continue
        else:
            raise RuntimeError("No usable Chromium/Edge/Chrome browser found")

        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(RAW_DIR),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()
        t0 = time.monotonic()

        page.goto(BASE_URL, wait_until="networkidle")

        # Wait until leaderboard Elos are loaded into the model picker.
        page.wait_for_function(
            "() => document.querySelector('#model option')?.textContent.includes('true Elo')",
            timeout=60_000,
        )
        page.wait_for_timeout(1200)

        page.select_option("#model", TARGET_MODEL)
        page.wait_for_timeout(1000)

        run_button = page.locator("#run-evaluation")
        run_button.scroll_into_view_if_needed()
        run_button.hover()
        page.wait_for_timeout(700)
        run_button.click()
        t_click = time.monotonic() - t0

        page.wait_for_function(
            """() => {
                const el = document.querySelector('#result-content');
                return el && !el.classList.contains('hidden') && el.innerHTML.length > 0;
            }""",
            timeout=600_000,
        )
        t_done = time.monotonic() - t0
        page.wait_for_timeout(3000)  # viewer reads the headline estimate

        # Scroll through the trace cards.
        for _ in range(6):
            page.mouse.wheel(0, 620)
            page.wait_for_timeout(1400)

        # Open the first "Exact grader context" block.
        first_context = page.locator(".grader-context summary").first
        if first_context.count():
            first_context.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
            first_context.click()
            page.wait_for_timeout(2500)

        for _ in range(4):
            page.mouse.wheel(0, 620)
            page.wait_for_timeout(1200)

        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        page.wait_for_timeout(3000)

        video_path = page.video.path()
        context.close()
        browser.close()

    print(json.dumps({"video": str(video_path), "t_click": t_click, "t_done": t_done}))


if __name__ == "__main__":
    main()
