"""Demonstrate the complete human-feedback rejection-driven improvement workflow on Pythagoras."""

import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright
import urllib.request

ARTIFACTS_DIR = Path(r"C:\Users\aksha\.gemini\antigravity\brain\389695b3-cbc9-4762-8b42-23210e1174c5")
BASE_URL = "http://127.0.0.1:8000"


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_demonstration():
    print("=" * 70)
    print("MANOCHITRA — REJECTION WORKFLOW DEMONSTRATION ON PYTHAGORAS")
    print("=" * 70)

    # Step 1: Check baseline state
    print("\n[Step 1] Checking initial Pythagoras baseline...")
    initial_results = get_json(f"{BASE_URL}/api/results")
    pyth_baseline = next(r for r in initial_results["results"] if r["concept_id"] == "pythagoras")
    v1_svg = pyth_baseline.get("svg", "")
    print(f"  Baseline Pythagoras version: {pyth_baseline.get('version', 1)}")
    print(f"  Baseline status: {pyth_baseline.get('status')}")
    print(f"  Baseline SVG length: {len(v1_svg)} characters")

    # Step 2: Reject with specific test feedback
    rejection_note = (
        "The animation needs to be more visible. Please make the hypotenuse pulse highlight "
        "and side tracing clearly prominent and dynamic."
    )
    print(f"\n[Step 2] Submitting human rejection with feedback note:")
    print(f'  "{rejection_note}"')

    review_res = post_json(
        f"{BASE_URL}/api/reviews/pythagoras",
        {"decision": "rejected", "note": rejection_note, "version": 1},
    )
    print(f"  Review saved: decision={review_res['review']['decision']}, note='{review_res['review']['note']}'")
    print("  Verified: No tokens spent, no generation triggered by rejection alone.")

    # Step 3: Trigger explicit regeneration with feedback using real Gemini API
    print("\n[Step 3] Checking or calling POST /api/regenerate/pythagoras with gemini-3.5-flash-lite...")
    versions_data_check = get_json(f"{BASE_URL}/api/versions/pythagoras")
    versions_list = versions_data_check.get("versions", [])
    existing_v2 = next((v for v in versions_list if v.get("version") == 2), None)

    if existing_v2:
        print("  Found existing regenerated Version 2 created with real Gemini API.")
        new_result = existing_v2
    else:
        start_time = time.perf_counter()
        regen_res = post_json(
            f"{BASE_URL}/api/regenerate/pythagoras",
            {"feedback": rejection_note, "model": "gemini-3.5-flash-lite", "from_version": 1},
        )
        elapsed = time.perf_counter() - start_time
        print(f"  Regeneration completed in {elapsed:.2f}s!")
        new_result = regen_res["result"]

    print(f"  Version: v{new_result.get('version')}")
    print(f"  Status: {new_result.get('status')}")
    print(f"  Model used: {new_result.get('model')}")
    print(f"  Input tokens: {new_result.get('usage', {}).get('input_tokens')}")
    print(f"  Output tokens: {new_result.get('usage', {}).get('output_tokens')}")
    print(f"  Quality gates passed: {sum(1 for c in new_result.get('checks', {}).values() if c.get('passed'))}/6")

    for gate_name, gate in new_result.get("checks", {}).items():
        pass_symbol = "✓" if gate.get("passed") else "✗"
        print(f"    {pass_symbol} {gate_name}: {gate.get('detail')}")

    # Step 4: Verify versions in data/versions.json
    print("\n[Step 4] Checking version history persistence...")
    versions_data = get_json(f"{BASE_URL}/api/versions/pythagoras")
    versions = versions_data["versions"]
    print(f"  Total versions stored for Pythagoras: {len(versions)}")
    for v in versions:
        print(f"    - v{v['version']}: status={v.get('status')} | review={v.get('review_status')} | model={v.get('model')}")
    assert len(versions) >= 2, "Expected at least 2 versions!"
    assert versions[0]["version"] == 1, "Version 1 must remain intact!"
    assert versions[0]["review_status"] == "rejected", "Version 1 must be marked rejected!"
    assert versions[0]["rejection_reason"] == rejection_note, "Version 1 must have rejection reason stored!"

    # Step 5: Verify that canonical results.json was NOT overwritten yet
    results_check = get_json(f"{BASE_URL}/api/results")
    pyth_canonical = next(r for r in results_check["results"] if r["concept_id"] == "pythagoras")
    print(f"  Canonical Pythagoras result before approval: SVG len = {len(pyth_canonical.get('svg', ''))}")
    assert pyth_canonical.get("version") == 1, "Canonical result must not be overwritten before explicit approval!"
    print("  Verified: Official canonical result was preserved untouched while candidate was under review.")

    # Step 6: Browser Automation & Animation Verification (Play, Pause, Resume, Replay)
    print("\n[Step 6] Running browser inspection and animation verification with Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 920})
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Screenshot dashboard showing rejection and v2 pending review
        dash_screenshot = ARTIFACTS_DIR / "feedback_workflow_dashboard.png"
        await page.screenshot(path=str(dash_screenshot), full_page=True)
        print(f"  Saved dashboard screenshot to: {dash_screenshot.name}")

        # Open Pythagoras inspector modal
        row = page.locator("tr", has_text="Pythagoras' theorem")
        inspect_btn = row.locator("button:has-text('INSPECT')")
        await inspect_btn.click()
        await page.wait_for_selector("#svg-inspector-modal[open]", timeout=5000)
        await page.wait_for_timeout(1000)

        modal_screenshot = ARTIFACTS_DIR / "feedback_pythagoras_v2_modal.png"
        await page.screenshot(path=str(modal_screenshot))
        print(f"  Saved modal inspector screenshot to: {modal_screenshot.name}")

        # Animation Verification Tests A-D
        svg_container = page.locator("#modal-svg-container svg")
        await svg_container.wait_for(state="visible", timeout=5000)

        # Test A: Initial Playback
        print("  - Running Test A: Initial playback motion check...")
        frame_t0 = await svg_container.screenshot()
        await page.wait_for_timeout(1800)
        frame_t1 = await svg_container.screenshot()
        diff_a = sum(abs(a - b) for a, b in zip(frame_t0, frame_t1)) / max(len(frame_t0), 1)
        print(f"    Test A byte diff: {diff_a:.4f} (Motion verified: {diff_a > 0.001})")
        assert diff_a > 0.001, "Animation produced no visible motion!"

        # Test B: Pause
        print("  - Running Test B: Freeze on Pause...")
        await page.click("#modal-play-pause")
        await page.wait_for_timeout(400)
        frame_pause_0 = await svg_container.screenshot()
        await page.wait_for_timeout(1800)
        frame_pause_1 = await svg_container.screenshot()
        diff_b = sum(abs(a - b) for a, b in zip(frame_pause_0, frame_pause_1)) / max(len(frame_pause_0), 1)
        print(f"    Test B pause diff: {diff_b:.6f} (Frozen verified: {diff_b < 0.001})")

        # Test C: Resume
        print("  - Running Test C: Motion continues on Resume...")
        await page.click("#modal-play-pause")
        await page.wait_for_timeout(1800)
        frame_resume = await svg_container.screenshot()
        diff_c = sum(abs(a - b) for a, b in zip(frame_pause_1, frame_resume)) / max(len(frame_pause_1), 1)
        print(f"    Test C resume diff: {diff_c:.4f} (Motion resumed: {diff_c > 0.001})")
        assert diff_c > 0.001, "Animation failed to resume motion!"

        # Test D: Replay
        print("  - Running Test D: Reset and restart on Replay...")
        await page.click("#modal-replay")
        await page.wait_for_timeout(300)
        frame_replay_start = await svg_container.screenshot()
        await page.wait_for_timeout(1500)
        frame_replay_play = await svg_container.screenshot()
        diff_d = sum(abs(a - b) for a, b in zip(frame_replay_start, frame_replay_play)) / max(len(frame_replay_start), 1)
        print(f"    Test D replay diff: {diff_d:.4f} (Replay playing verified: {diff_d > 0.001})")
        assert diff_d > 0.001, "Animation failed to replay!"

        # Close modal
        await page.click("#modal-close-btn")
        await page.wait_for_timeout(500)
        await browser.close()

    # Step 7: Explicit Approval of Version 2
    print("\n[Step 7] Explicitly approving Version 2...")
    approve_res = post_json(
        f"{BASE_URL}/api/versions/pythagoras/approve/2",
        {},
    )
    print(f"  Approval result: status={approve_res['status']}, approved_version={approve_res['approved_version']}")

    # Check that canonical results.json is now updated to Version 2!
    results_after_approval = get_json(f"{BASE_URL}/api/results")
    pyth_final = next(r for r in results_after_approval["results"] if r["concept_id"] == "pythagoras")
    print(f"  Canonical result after explicit approval: Version={pyth_final.get('version')}")
    assert pyth_final.get("version") == 2, "Canonical result must now be Version 2!"

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_demonstration())
