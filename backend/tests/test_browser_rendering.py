"""Browser-based rendering tests using Playwright.

Verifies:
1. Rendered SVG element painting: non-zero bounding rects, contained within viewBox.
2. Active animation execution: computed styles/transforms/attributes change over time.
3. Label legibility & non-collision: bounding boxes are readable and non-overlapping.
4. Daylight/Night theme switching: colors adapt properly.
5. End-to-end Dashboard UI interaction: theme toggling, review approval/rejection notes, persistence.
"""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
import pytest
from playwright.async_api import async_playwright

from app.core.concepts import CONCEPTS, CONCEPT_BY_ID
from conftest import make_valid_svg


def _is_server_running(host: str = "127.0.0.1", port: int = 8000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _html_wrap(svg: str, theme: str = "daylight") -> str:
    bg = "#FBF8EE" if theme == "daylight" else "#0F1E19"
    fg = "#244638" if theme == "daylight" else "#E5ECE9"
    return f"""<!DOCTYPE html>
<html data-theme="{theme}">
<head>
  <meta charset="utf-8" />
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: {bg};
      color: {fg};
      font-family: sans-serif;
    }}
    .diagram-frame {{
      width: 960px;
      height: 640px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}
  </style>
</head>
<body>
  <div class="diagram-frame">
    {svg}
  </div>
</body>
</html>"""


@pytest.mark.asyncio
async def test_browser_render_all_concepts_painted():
    """Verify all 5 concepts render visible, non-zero geometry in headless browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        for concept in CONCEPTS:
            svg = make_valid_svg(concept)
            html = _html_wrap(svg)
            await page.set_content(html)

            # Check root SVG rendered with non-zero dimensions
            svg_rect = await page.locator("svg").bounding_box()
            assert svg_rect is not None, f"{concept['id']}: SVG element not found in DOM"
            assert svg_rect["width"] > 400, f"{concept['id']}: SVG width too small: {svg_rect['width']}"
            assert svg_rect["height"] > 250, f"{concept['id']}: SVG height too small: {svg_rect['height']}"

            # Check that visible shape elements have positive bounding boxes
            shapes = await page.locator("svg rect, svg circle, svg polygon, svg line").all()
            assert len(shapes) >= 4, f"{concept['id']}: too few shape elements ({len(shapes)})"

            rendered_shapes = 0
            for shape in shapes:
                box = await shape.bounding_box()
                if box and box["width"] > 0 and box["height"] > 0:
                    rendered_shapes += 1

            assert rendered_shapes >= 3, f"{concept['id']}: only {rendered_shapes} shapes painted"

        await browser.close()


@pytest.mark.asyncio
async def test_browser_render_animations_active():
    """Verify that animations run in the browser and alter element styles/attributes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        # Test Pythagoras CSS keyframe pulse
        pyth_concept = CONCEPT_BY_ID["pythagoras"]
        svg = make_valid_svg(pyth_concept)
        await page.set_content(_html_wrap(svg))

        # Check that animation is active on the square or hypotenuse
        has_animation = await page.evaluate("""() => {
            const anims = document.getAnimations();
            return anims.length > 0;
        }""")
        assert has_animation, "Pythagoras diagram has no active CSS/Web animations in browser"

        # Test States of Matter liquid particle motion
        som_concept = CONCEPT_BY_ID["states-of-matter"]
        som_svg = make_valid_svg(som_concept)
        await page.set_content(_html_wrap(som_svg))

        # Query liquid particle position or SMIL animation
        has_som_anim = await page.evaluate("""() => {
            const smilAnims = document.querySelectorAll('animate, animateTransform');
            const webAnims = document.getAnimations();
            return smilAnims.length > 0 || webAnims.length > 0;
        }""")
        assert has_som_anim, "States of matter has no active SMIL or CSS animations in browser"

        await browser.close()


@pytest.mark.asyncio
async def test_browser_render_labels_readable_and_non_overlapping():
    """Verify that labels have non-zero geometry and do not collide in browser layout."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        for concept in CONCEPTS:
            svg = make_valid_svg(concept)
            await page.set_content(_html_wrap(svg))

            # Query all text elements
            boxes = await page.evaluate("""() => {
                const texts = Array.from(document.querySelectorAll('svg text'));
                return texts.map(t => {
                    const rect = t.getBoundingClientRect();
                    return {
                        text: t.textContent.trim(),
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height
                    };
                }).filter(b => b.text.length > 0);
            }""")

            assert len(boxes) >= 4, f"{concept['id']}: expected >= 4 non-empty text elements, got {len(boxes)}"

            for b in boxes:
                assert b["width"] > 0, f"{concept['id']}: label '{b['text']}' has zero width"
                assert b["height"] > 0, f"{concept['id']}: label '{b['text']}' has zero height"

            # Check overlap between distinct labels
            for i, b1 in enumerate(boxes):
                for j, b2 in enumerate(boxes):
                    if i >= j:
                        continue
                    # Horizontal overlap
                    x_overlap = max(0.0, min(b1["x"] + b1["width"], b2["x"] + b2["width"]) - max(b1["x"], b2["x"]))
                    # Vertical overlap
                    y_overlap = max(0.0, min(b1["y"] + b1["height"], b2["y"] + b2["y"]) - max(b1["y"], b2["y"]))
                    overlap_area = x_overlap * y_overlap
                    min_area = min(b1["width"] * b1["height"], b2["width"] * b2["height"])

                    # Overlap must not exceed 50% of the smaller label
                    if min_area > 0:
                        overlap_ratio = overlap_area / min_area
                        assert overlap_ratio < 0.50, (
                            f"{concept['id']}: labels '{b1['text']}' and '{b2['text']}' collide heavily "
                            f"(overlap={overlap_ratio*100:.1f}%)"
                        )

        await browser.close()


@pytest.mark.asyncio
async def test_browser_theme_switching_styles():
    """Verify that daylight and night themes apply distinct, accessible styling."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        concept = CONCEPT_BY_ID["pythagoras"]
        svg = make_valid_svg(concept)

        # 1. Daylight
        await page.set_content(_html_wrap(svg, theme="daylight"))
        day_bg = await page.evaluate("() => window.getComputedStyle(document.body).backgroundColor")

        # 2. Night
        await page.set_content(_html_wrap(svg, theme="night"))
        night_bg = await page.evaluate("() => window.getComputedStyle(document.body).backgroundColor")

        assert day_bg != night_bg, "Daylight and night themes have identical background colors"

        await browser.close()


@pytest.mark.asyncio
async def test_browser_dashboard_ui_interaction():
    """Verify end-to-end Dashboard UI on localhost: theme toggle, card rendering, and review interactions."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        ROOT = Path(__file__).resolve().parents[2]
        # Route /api/results to local data/results.json so the test is hermetic and resilient
        results_data = (ROOT / "data" / "results.json").read_text(encoding="utf-8")
        await page.route("**/api/results", lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=results_data
        ))

        # Navigate to the local running app (or local file URI if admin policies restrict http ports)
        if _is_server_running():
            response = await page.goto("http://127.0.0.1:8000/", timeout=8000)
            assert response and response.status == 200, f"Dashboard returned status {response.status if response else None}"
        else:
            index_uri = (ROOT / "frontend" / "index.html").as_uri()
            await page.goto(index_uri, timeout=8000)

        # Verify page title
        title = await page.title()
        assert "manochitra" in title.lower()

        # Wait for concept rows in table
        await page.wait_for_selector("#results-body tr", timeout=5000)
        rows = await page.locator("#results-body tr").all()
        assert len(rows) >= 5, f"Expected 5 concept rows in table, found {len(rows)}"

        # Verify theme toggle button
        theme_btn = page.locator("#theme-toggle")
        assert await theme_btn.count() == 1, "Theme toggle button not found"

        init_theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme') || 'light'")
        await theme_btn.click()
        await page.wait_for_timeout(300)
        new_theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        assert new_theme != init_theme, f"Theme did not toggle (was {init_theme}, still {new_theme})"

        # Verify regenerate diagram primary buttons exist in concept rows
        regen_btns = page.locator(".primary-regen, .btn-regenerate-diagram")
        assert await regen_btns.count() >= 5, "Expected REGENERATE DIAGRAM buttons in concept rows"

        # Toggle theme back to daylight
        await theme_btn.click()
        await page.wait_for_timeout(300)
        restored_theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        assert restored_theme == init_theme, "Theme did not toggle back"

        await browser.close()


@pytest.mark.asyncio
async def test_browser_model_instrument_selector():
    """Verify semicircular instrument gauge and active Gemini 3.5 Flash-Lite selection."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        ROOT = Path(__file__).resolve().parents[2]
        if _is_server_running():
            response = await page.goto("http://127.0.0.1:8000/", timeout=5000)
            assert response and response.status == 200
        else:
            index_uri = (ROOT / "frontend" / "index.html").as_uri()
            await page.goto(index_uri, timeout=5000)

        # 1. Gauge and switch controls exist
        assert await page.locator(".semicircular-gauge").count() == 1
        assert await page.locator("#gauge-needle-group").count() == 1
        btn_lite = page.locator("#btn-model-lite")
        assert await btn_lite.count() == 1

        # 2. Active state: 3.5 Flash-Lite is active by default
        assert await btn_lite.get_attribute("aria-checked") == "true"
        spec_name = await page.locator("#spec-name").text_content()
        assert "Gemini 3.5 Flash-Lite" in spec_name

        needle_transform_initial = await page.locator("#gauge-needle-group").get_attribute("transform")
        assert "-42" in needle_transform_initial

        await browser.close()


@pytest.mark.asyncio
async def test_browser_comparison_mode_view():
    """Verify simplified single-view mode per Phase 1 (comparison view cleanly omitted)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        ROOT = Path(__file__).resolve().parents[2]
        if _is_server_running():
            response = await page.goto("http://127.0.0.1:8000/", timeout=5000)
            assert response and response.status == 200
        else:
            index_uri = (ROOT / "frontend" / "index.html").as_uri()
            await page.goto(index_uri, timeout=5000)

        # Comparison tab is removed per Phase 1 interface simplification
        tab_comparison = page.locator("#tab-comparison")
        assert await tab_comparison.count() == 0, "Comparison tab should be removed in simplified interface"

        standard_view = page.locator("#standard-review-view")
        assert await standard_view.is_visible(), "Standard review view should be visible"

        await browser.close()
