"""Unit and regression tests for the Visual Quality Validator.

Verifies deterministic visual-quality checks:
1. Pythagoras viewBox overflow and boundary enforcement.
2. Circle callout anchor termination and leader line validity.
3. Series circuit animation visibility and dynamic property delta.
4. Photosynthesis leaf reaction site and arrow flow integration.
5. States of matter gas particle separation threshold (>= 2.2x solid spacing).
6. Text margin encroachment (>= 24px) and overlapping label collision detection.
7. Canvas geometry balance and spatial distribution.
8. End-to-end visual quality report generation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import pytest

from app.core.concepts import CONCEPT_BY_ID
from app.validators.svg_validator import validate_svg
from app.validators.concept_structure_validator import validate_concept_structure
from app.validators.visual_quality_validator import (
    TextBBox,
    check_animation_visibility_and_dynamics,
    check_diagram_canvas_balance,
    check_labels_obscuring_geometry,
    check_leader_lines,
    check_overlapping_labels,
    check_text_bounds_and_margins,
    validate_visual_quality,
)
from conftest import make_valid_svg


def _parse_svg(svg_text: str) -> ET.Element:
    return ET.fromstring(svg_text)


# ==============================================================================
# 1. Pythagoras earlier overflow regression test
# ==============================================================================

def test_pythagoras_viewbox_overflow_regression():
    """Verify that a rectangle extending past bottom coordinate 640 is caught."""
    overflow_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640" width="960" height="640">'
        '<title>Pythagoras Theorem</title>'
        '<rect x="0" y="0" width="960" height="640" fill="#f7f4e9" />'
        '<polygon points="120,420 120,180 420,420" fill="#e2ecd8" stroke="#244638" />'
        # Overflowing square: y=420, height=240 -> bottom coordinate 660 > 640
        '<rect x="360" y="420" width="600" height="240" fill="#c8d96b" stroke="#244638" />'
        '<text x="50" y="50" font-size="16">Hypotenuse</text>'
        '</svg>'
    )
    concept = CONCEPT_BY_ID["pythagoras"]
    result = validate_svg(overflow_svg, concept)
    assert not result.passed, "Overflowing SVG must fail validation"
    assert not result.checks["within_viewbox"].passed, "within_viewbox gate must fail"
    assert "660" in result.checks["within_viewbox"].detail or "exceeds" in result.checks["within_viewbox"].detail.lower()


# ==============================================================================
# 2. Text margin encroachment & overlapping labels
# ==============================================================================

def test_text_margins_encroachment_detected():
    boxes = [
        TextBBox(element=ET.Element("text"), text="Safe Label", x1=50, y1=50, x2=150, y2=70, font_size=14),
        # Label encroaching on left margin (x1=10 < 24)
        TextBBox(element=ET.Element("text"), text="Clipped Label", x1=10, y1=100, x2=100, y2=120, font_size=14),
    ]
    res = check_text_bounds_and_margins(boxes, margin=24.0, width=960.0, height=640.0)
    assert not res.passed
    assert "encroaching" in res.detail.lower()
    assert res.metrics["violation_count"] == 1


def test_text_margins_safe_passes():
    boxes = [
        TextBBox(element=ET.Element("text"), text="Title", x1=40, y1=30, x2=200, y2=60, font_size=18),
        TextBBox(element=ET.Element("text"), text="Footer Note", x1=40, y1=600, x2=300, y2=615, font_size=12),
    ]
    res = check_text_bounds_and_margins(boxes, margin=24.0, width=960.0, height=640.0)
    assert res.passed
    assert "safely within" in res.detail


def test_overlapping_labels_collision_detected():
    boxes = [
        TextBBox(element=ET.Element("text"), text="Radius r", x1=300, y1=250, x2=380, y2=270, font_size=14),
        # Second label overlapping first label significantly
        TextBBox(element=ET.Element("text"), text="Diameter d", x1=320, y1=255, x2=410, y2=275, font_size=14),
    ]
    res = check_overlapping_labels(boxes)
    assert not res.passed
    assert "overlapping" in res.detail.lower()
    assert "Radius r" in res.detail and "Diameter d" in res.detail


def test_non_overlapping_labels_pass():
    boxes = [
        TextBBox(element=ET.Element("text"), text="Radius r", x1=300, y1=250, x2=380, y2=270, font_size=14),
        TextBBox(element=ET.Element("text"), text="Diameter d", x1=500, y1=250, x2=590, y2=270, font_size=14),
    ]
    res = check_overlapping_labels(boxes)
    assert res.passed
    assert res.metrics["overlap_count"] == 0


# ==============================================================================
# 3. Leader-line anchor accuracy
# ==============================================================================

def test_leader_line_accuracy_valid():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<line class="callout-line" x1="480" y1="160" x2="420" y2="100" stroke="#244638" />'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_leader_lines(root, [])
    assert res.passed
    assert res.metrics["leader_line_count"] == 1


def test_leader_line_degenerate_fails():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<line class="callout-line" x1="480" y1="160" x2="481" y2="161" stroke="#244638" />'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_leader_lines(root, [])
    assert not res.passed
    assert "degenerate" in res.detail.lower()


# ==============================================================================
# 4. Focal point clearance (no text obscuring geometry)
# ==============================================================================

def test_circle_centre_not_obscured():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<circle cx="480" cy="320" r="4" fill="#244638" />'
        '</svg>'
    )
    root = _parse_svg(svg)
    # Label beside the center dot (e.g. x=495, y=320)
    boxes = [
        TextBBox(element=ET.Element("text"), text="Centre O", x1=495, y1=310, x2=560, y2=330, font_size=14)
    ]
    res = check_labels_obscuring_geometry(root, boxes, "circle")
    assert res.passed

    # Label right on top of center dot
    obscuring_boxes = [
        TextBBox(element=ET.Element("text"), text="Centre O", x1=450, y1=310, x2=510, y2=330, font_size=14)
    ]
    res_obscured = check_labels_obscuring_geometry(root, obscuring_boxes, "circle")
    assert not res_obscured.passed
    assert "obscures focal geometry" in res_obscured.detail.lower()


# ==============================================================================
# 5. Animation dynamics and visibility
# ==============================================================================

def test_animation_dynamics_subtle_opacity_fails():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<circle cx="200" cy="200" r="20" fill="#244638">'
        '  <animate attributeName="opacity" values="0.95; 1.0; 0.95" dur="2s" repeatCount="indefinite" />'
        '</circle>'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_animation_visibility_and_dynamics(root)
    assert not res.passed
    assert "too subtle" in res.detail.lower()


def test_animation_dynamics_meaningful_motion_passes():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<circle cx="200" cy="200" r="20" fill="#244638">'
        '  <animate attributeName="cx" values="200; 260; 200" dur="2s" repeatCount="indefinite" />'
        '</circle>'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_animation_visibility_and_dynamics(root)
    assert res.passed
    assert res.metrics["smil_animated_count"] >= 1


def test_animation_dynamics_css_keyframes_passes():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<style>@keyframes dashFlow { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -40; } }</style>'
        '<rect x="100" y="100" width="200" height="200" fill="none" stroke="#244638" style="animation: dashFlow 2s linear infinite;" />'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_animation_visibility_and_dynamics(root)
    assert res.passed
    assert res.metrics["has_css_keyframes"]


# ==============================================================================
# 6. Diagram canvas balance
# ==============================================================================

def test_canvas_balance_cramped_geometry_fails():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<rect x="0" y="0" width="960" height="640" fill="#f7f4e9" />'
        # Tiny circle in the corner spanning only 40x40px
        '<circle cx="100" cy="100" r="20" fill="#244638" />'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_diagram_canvas_balance(root, 960.0, 640.0)
    assert not res.passed
    assert "cramped" in res.detail.lower()


def test_canvas_balance_well_distributed_passes():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">'
        '<rect x="0" y="0" width="960" height="640" fill="#f7f4e9" />'
        '<circle cx="480" cy="320" r="160" fill="none" stroke="#244638" stroke-width="3" />'
        '<rect x="180" y="140" width="600" height="360" fill="none" stroke="#8fa58a" />'
        '</svg>'
    )
    root = _parse_svg(svg)
    res = check_diagram_canvas_balance(root, 960.0, 640.0)
    assert res.passed
    assert "well-balanced" in res.detail.lower()


# ==============================================================================
# 7. States of matter gas particle separation threshold (>= 2.2x solid)
# ==============================================================================

def test_states_of_matter_gas_spacing_threshold_passes():
    concept = CONCEPT_BY_ID["states-of-matter"]
    # 9 solid particles (3x3 grid, spacing 30px: 150..210) -> avg_solid = 30px
    # 4 gas particles at (720, 240), (840, 240), (720, 380), (840, 380) -> dist = 120px -> ratio = 4.0 >= 2.2x
    svg = make_valid_svg(concept)
    root = _parse_svg(svg)
    res = validate_concept_structure(root, concept)
    assert res.passed
    assert "widely separated" in res.detail.lower() and "x solid" in res.detail.lower()


# ==============================================================================
# 8. Full visual quality report integration
# ==============================================================================

def test_full_visual_quality_report_structure():
    concept = CONCEPT_BY_ID["pythagoras"]
    svg = make_valid_svg(concept)
    root = _parse_svg(svg)
    report = validate_visual_quality(root, concept)
    assert report.passed
    assert len(report.checks) == 6
    assert all(c.passed for c in report.checks.values())
    assert len(report.review_requirements) >= 4
    report_dict = report.to_dict()
    assert report_dict["passed"] is True
    assert "checks" in report_dict
    assert "review_requirements" in report_dict
