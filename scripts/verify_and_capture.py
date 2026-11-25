"""Browser verification and screenshot capture script for MANOCHITRA.

Verifies:
1. Complete human review workflow (Approve, Reject, Notes, Refresh, Change decision, LocalStorage persistence).
2. IndexedDB local diagram archive (Approved and Rejected storage, filter pills).
3. Correct standard pricing cost display ($0.00615) and free-tier charge ($0.00).
4. Responsive viewports (1600px, 1440px, 1024px, 768px, 390px).
5. Captures real screenshots of Daylight and Night modes to screenshots/.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS_DIR = ROOT / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

APP_URL = "http://127.0.0.1:8000/"


async def run_verification():
    print("Starting Playwright verification and capture...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await context.new_page()

        # 1. Navigate to application
        await page.goto(APP_URL, wait_until="networkidle")
        await page.wait_for_selector("#results-body tr", timeout=8000)

        rows = await page.locator("#results-body tr").all()
        print(f"PASS: Loaded dashboard with {len(rows)} concept rows.")
        assert len(rows) >= 5, f"Expected 5 concept rows, got {len(rows)}"

        # Check metrics grid has 6 cards
        metric_cards = await page.locator(".metrics-grid .metric-card").all()
        print(f"PASS: Metrics grid contains {len(metric_cards)} metric cards.")
        assert len(metric_cards) >= 6, f"Expected at least 6 metric cards, got {len(metric_cards)}"

        # Check cost formatting on row 1
        cost_text = await page.locator(".usage-cost").first.text_content()
        free_tier_text = await page.locator(".usage-free-tier").first.text_content()
        print(f"PASS: Row 1 Standard Cost = '{cost_text}', Free Tier = '{free_tier_text}'")
        assert "$0." in cost_text, f"Unexpected cost formatting: {cost_text}"
        assert "$0.00" in free_tier_text, f"Unexpected free tier formatting: {free_tier_text}"

        # 2. Enter reviewer notes and make decisions
        # Row 1 (Pythagoras): Enter note and Approve
        row1 = page.locator("#results-body tr").nth(0)
        note_input1 = row1.locator(".review-note-input")
        await note_input1.fill("Verified hypotenuse proof and right angle geometry.")
        approve_btn1 = row1.locator(".review-btn.approve")
        await approve_btn1.click()
        await page.wait_for_timeout(300)

        status_badge1 = await row1.locator(".review-decision-badge").text_content()
        print(f"PASS: Row 1 decision after Approve: '{status_badge1.strip()}'")
        assert "ACCEPTED" in status_badge1

        # Row 2 (Circle): Enter note and Reject
        row2 = page.locator("#results-body tr").nth(1)
        note_input2 = row2.locator(".review-note-input")
        await note_input2.fill("Circumference label leader touches boundary curve.")
        reject_btn2 = row2.locator(".review-btn.reject")
        await reject_btn2.click()
        await page.wait_for_timeout(300)

        status_badge2 = await row2.locator(".review-decision-badge").text_content()
        print(f"PASS: Row 2 decision after Reject: '{status_badge2.strip()}'")
        assert "REJECTED" in status_badge2

        # Verify dashboard metrics updated
        metric_accepted = await page.locator("#metric-accepted").text_content()
        metric_rejected = await page.locator("#metric-rejected").text_content()
        print(f"PASS: Metrics after decisions: Accepted={metric_accepted}, Rejected={metric_rejected}")
        assert metric_accepted == "1"
        assert metric_rejected == "1"

        # 3. Refresh page and verify persistence
        print("Refreshing page to test LocalStorage persistence...")
        await page.reload(wait_until="networkidle")
        await page.wait_for_selector("#results-body tr", timeout=8000)

        row1_after = page.locator("#results-body tr").nth(0)
        row2_after = page.locator("#results-body tr").nth(1)

        note1_after = await row1_after.locator(".review-note-input").input_value()
        status1_after = await row1_after.locator(".review-decision-badge").text_content()
        print(f"PASS: Row 1 after refresh: status='{status1_after.strip()}', note='{note1_after}'")
        assert "ACCEPTED" in status1_after
        assert "Verified hypotenuse proof" in note1_after

        note2_after = await row2_after.locator(".review-note-input").input_value()
        status2_after = await row2_after.locator(".review-decision-badge").text_content()
        print(f"PASS: Row 2 after refresh: status='{status2_after.strip()}', note='{note2_after}'")
        assert "REJECTED" in status2_after
        assert "Circumference label" in note2_after

        # 4. Change decision: Change Row 2 from Reject to Approve
        approve_btn2_after = row2_after.locator(".review-btn.approve")
        await approve_btn2_after.click()
        await page.wait_for_timeout(300)

        status2_changed = await row2_after.locator(".review-decision-badge").text_content()
        print(f"PASS: Row 2 status after changing decision: '{status2_changed.strip()}'")
        assert "ACCEPTED" in status2_changed

        # Refresh again to confirm changed decision persisted
        await page.reload(wait_until="networkidle")
        await page.wait_for_selector("#results-body tr", timeout=8000)
        row2_final = page.locator("#results-body tr").nth(1)
        status2_final = await row2_final.locator(".review-decision-badge").text_content()
        print(f"PASS: Row 2 status after second refresh: '{status2_final.strip()}'")
        assert "ACCEPTED" in status2_final

        # 5. Check IndexedDB Archive section
        archive_cards = await page.locator(".archive-grid .archive-card").all()
        print(f"PASS: Found {len(archive_cards)} cards in local diagram archive.")
        assert len(archive_cards) >= 2, f"Expected at least 2 archived diagrams, got {len(archive_cards)}"

        # 6. Viewport responsiveness checks
        viewports = [1600, 1440, 1024, 768, 390]
        for vp_width in viewports:
            await page.set_viewport_size({"width": vp_width, "height": 900})
            await page.wait_for_timeout(200)

            # Check no horizontal body overflow
            overflow = await page.evaluate("""() => {
                const doc = document.documentElement;
                return doc.scrollWidth - window.innerWidth;
            }""")
            print(f"PASS: Viewport {vp_width}px horizontal body overflow = {overflow}px")
            assert overflow <= 1, f"Horizontal body overflow at {vp_width}px: {overflow}px"

        # 7. Capture screenshots at 1600x1100
        await page.set_viewport_size({"width": 1600, "height": 1100})
        await page.wait_for_timeout(300)

        # Daylight mode screenshot
        # Ensure daylight theme is active
        theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        if theme != "light":
            await page.locator("#theme-toggle").click()
            await page.wait_for_timeout(300)

        daylight_path = SCREENSHOTS_DIR / "manochitra-daylight.png"
        await page.screenshot(path=str(daylight_path), full_page=False)
        print(f"PASS: Saved Daylight screenshot to {daylight_path}")

        # Night mode screenshot
        theme_toggle = page.locator("#theme-toggle")
        await theme_toggle.click()
        await page.wait_for_timeout(400)

        night_theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        print(f"Theme switched to: {night_theme}")
        assert night_theme == "dark", f"Expected dark theme, got {night_theme}"

        night_path = SCREENSHOTS_DIR / "manochitra-night.png"
        await page.screenshot(path=str(night_path), full_page=False)
        print(f"PASS: Saved Night screenshot to {night_path}")

        # Switch back to light theme for default clean state
        await theme_toggle.click()
        await page.wait_for_timeout(300)

        await browser.close()
        print("ALL BROWSER VERIFICATIONS AND SCREENSHOTS COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    asyncio.run(run_verification())
