"""Comprehensive test suite for the 6th advanced concept-structure quality gate.

Verifies deterministic geometric and topological relationships for all five concepts:
1. Pythagoras' theorem
2. Circle geometry
3. Series circuit
4. Photosynthesis
5. States of matter
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import pytest

from app.core.concepts import CONCEPT_BY_ID
from app.validators.concept_structure_validator import validate_concept_structure
from conftest import make_valid_svg


def _parse_svg(svg_text: str) -> ET.Element:
    return ET.fromstring(svg_text)


# ==============================================================================
# 1. Pythagoras' theorem tests
# ==============================================================================

def test_pythagoras_valid_structure_passes():
    concept = CONCEPT_BY_ID["pythagoras"]
    root = _parse_svg(make_valid_svg(concept))
    result = validate_concept_structure(root, concept)
    assert result.passed
    assert "right-angle" in result.detail.lower()


def test_pythagoras_equilateral_triangle_fails():
    concept = CONCEPT_BY_ID["pythagoras"]
    # Equilateral triangle points (no right angle)
    svg = make_valid_svg(concept).replace(
        'points="120,420 120,180 420,420"',
        'points="120,420 270,160 420,420"',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "not a right angle" in result.detail or "violate pythagoras" in result.detail.lower()


def test_pythagoras_missing_marker_fails():
    concept = CONCEPT_BY_ID["pythagoras"]
    svg = make_valid_svg(concept).replace(
        '<rect id="right_angle_marker" x="120" y="396" width="24" height="24" fill="none" stroke="#244638" stroke-width="2" />',
        "",
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "marker" in result.detail.lower()


def test_pythagoras_missing_formula_fails():
    concept = CONCEPT_BY_ID["pythagoras"]
    svg = make_valid_svg(concept).replace(
        '<text x="100" y="175" font-size="16">a² + b² = c²</text>',
        '<text x="100" y="175" font-size="16">formula omitted</text>',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "formula" in result.detail.lower()


def test_pythagoras_hypotenuse_label_misplaced_fails():
    concept = CONCEPT_BY_ID["pythagoras"]
    # Move hypotenuse text far away from hypotenuse
    svg = make_valid_svg(concept).replace(
        '<text x="100" y="105" font-size="16">hypotenuse</text>',
        '<text x="800" y="500" font-size="16">hypotenuse</text>',
    ).replace(
        '<text x="280" y="290" font-size="16">c</text>',
        "",
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "hypotenuse label" in result.detail.lower()


# ==============================================================================
# 2. Circle geometry tests
# ==============================================================================

def test_circle_geometry_valid_structure_passes():
    concept = CONCEPT_BY_ID["circle"]
    root = _parse_svg(make_valid_svg(concept))
    result = validate_concept_structure(root, concept)
    assert result.passed
    assert "diameter line" in result.detail.lower() and "radius line" in result.detail.lower()


def test_circle_geometry_missing_centre_fails():
    concept = CONCEPT_BY_ID["circle"]
    svg = make_valid_svg(concept).replace(
        '<circle id="circle_centre" cx="480" cy="320" r="5" fill="#244638" />',
        "",
    ).replace(
        '<text x="100" y="105" font-size="16">centre</text>',
        "",
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "centre" in result.detail.lower()


def test_circle_geometry_diameter_not_collinear_fails():
    concept = CONCEPT_BY_ID["circle"]
    # Offset diameter line so it doesn't pass through centre (480, 320)
    svg = make_valid_svg(concept).replace(
        '<line id="diameter_line" x1="330" y1="320" x2="630" y2="320" stroke="#244638" stroke-width="2" />',
        '<line id="diameter_line" x1="330" y1="260" x2="630" y2="260" stroke="#244638" stroke-width="2" />',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "collinear" in result.detail.lower() or "diameter" in result.detail.lower()


def test_circle_geometry_diameter_not_double_radius_fails():
    concept = CONCEPT_BY_ID["circle"]
    # Diameter length is 100, but radius is 150 (2*R = 300)
    svg = make_valid_svg(concept).replace(
        '<line id="diameter_line" x1="330" y1="320" x2="630" y2="320" stroke="#244638" stroke-width="2" />',
        '<line id="diameter_line" x1="430" y1="320" x2="530" y2="320" stroke="#244638" stroke-width="2" />',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "diameter" in result.detail.lower()


# ==============================================================================
# 3. Series circuit tests
# ==============================================================================

def test_series_circuit_valid_structure_passes():
    concept = CONCEPT_BY_ID["series-circuit"]
    root = _parse_svg(make_valid_svg(concept))
    result = validate_concept_structure(root, concept)
    assert result.passed
    assert "single continuous loop" in result.detail.lower()


def test_series_circuit_parallel_branch_rejected():
    concept = CONCEPT_BY_ID["series-circuit"]
    # Add parallel branch bridging top and bottom wires
    svg = make_valid_svg(concept).replace(
        '</svg>',
        '<line class="parallel_wire" x1="500" y1="200" x2="500" y2="440" stroke="#244638" stroke-width="3" /></svg>',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "parallel" in result.detail.lower() or "junction" in result.detail.lower() or "branch" in result.detail.lower()


def test_series_circuit_missing_cell_fails():
    concept = CONCEPT_BY_ID["series-circuit"]
    svg = make_valid_svg(concept).replace(
        '<rect id="battery" x="440" y="185" width="80" height="30" fill="#c8d96b" stroke="#244638" stroke-width="2" />',
        "",
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "power source" in result.detail.lower() or "cell" in result.detail.lower() or "battery" in result.detail.lower()


# ==============================================================================
# 4. Photosynthesis tests
# ==============================================================================

def test_photosynthesis_valid_structure_passes():
    concept = CONCEPT_BY_ID["photosynthesis"]
    root = _parse_svg(make_valid_svg(concept))
    result = validate_concept_structure(root, concept)
    assert result.passed
    assert "photosynthesis" in result.detail.lower()


def test_photosynthesis_missing_chlorophyll_fails():
    concept = CONCEPT_BY_ID["photosynthesis"]
    svg = make_valid_svg(concept).replace(
        '<text x="100" y="105" font-size="16">chlorophyll</text>',
        '<text x="100" y="105" font-size="16">green substance</text>',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "chlorophyll" in result.detail.lower()


def test_photosynthesis_inverted_inputs_fails():
    concept = CONCEPT_BY_ID["photosynthesis"]
    # Point light arrow away from leaf site (x1=380, x2=200 instead of into leaf)
    svg = make_valid_svg(concept).replace(
        '<line id="light_ray" x1="200" y1="180" x2="380" y2="280" stroke="#c8d96b" stroke-width="3" />',
        '<line id="light_ray" x1="480" y1="320" x2="200" y2="180" stroke="#c8d96b" stroke-width="3" />',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "light" in result.detail.lower() or "input" in result.detail.lower()


# ==============================================================================
# 5. States of matter tests
# ==============================================================================

def test_states_of_matter_valid_structure_passes():
    concept = CONCEPT_BY_ID["states-of-matter"]
    root = _parse_svg(make_valid_svg(concept))
    result = validate_concept_structure(root, concept)
    assert result.passed
    assert "ordered lattice" in result.detail.lower()


def test_states_of_matter_overlapping_containers_fails():
    concept = CONCEPT_BY_ID["states-of-matter"]
    # Solid and liquid containers overlapping at x=80 and x=100
    svg = make_valid_svg(concept).replace(
        '<rect id="liquid_container" x="360" y="200" width="240" height="240" fill="none" stroke="#244638" stroke-width="3" />',
        '<rect id="liquid_container" x="100" y="200" width="240" height="240" fill="none" stroke="#244638" stroke-width="3" />',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "overlap" in result.detail.lower()


def test_states_of_matter_liquid_particles_not_required_at_bottom():
    concept = CONCEPT_BY_ID["states-of-matter"]
    # Place liquid particles at top/mid of container (y=220..280 in container y=200..440)
    svg = make_valid_svg(concept).replace('cy="320"', 'cy="240"').replace('cy="325"', 'cy="250"').replace('cy="315"', 'cy="245"')
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert result.passed


def test_states_of_matter_liquid_without_motion_fails():
    concept = CONCEPT_BY_ID["states-of-matter"]
    # Remove SMIL animate and any drift animation on liquid particles
    svg = make_valid_svg(concept).replace(
        '<animate attributeName="cx" values="420;435;420" dur="2s" repeatCount="indefinite" />',
        "",
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "motion" in result.detail.lower() or "mobility" in result.detail.lower() or "animation" in result.detail.lower()


def test_states_of_matter_disordered_solid_fails():
    concept = CONCEPT_BY_ID["states-of-matter"]
    # Jumble solid particle positions into random clump
    svg = make_valid_svg(concept).replace(
        '<circle class="solid_particle" cx="160" cy="280" r="12" fill="#8fa58a" />',
        '<circle class="solid_particle" cx="100" cy="210" r="12" fill="#8fa58a" />',
    ).replace(
        '<circle class="solid_particle" cx="240" cy="360" r="12" fill="#8fa58a" />',
        '<circle class="solid_particle" cx="300" cy="420" r="12" fill="#8fa58a" />',
    )
    root = _parse_svg(svg)
    result = validate_concept_structure(root, concept)
    assert not result.passed
    assert "solid" in result.detail.lower() or "regular" in result.detail.lower() or "variance" in result.detail.lower()
