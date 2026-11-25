from __future__ import annotations

import pytest

from app.core.concepts import CONCEPT_BY_ID


@pytest.fixture
def pythagoras_concept():
    return CONCEPT_BY_ID["pythagoras"]


def make_valid_svg(concept: dict) -> str:
    cid = concept["id"]

    # Exactly matching the style/title/desc expected by existing test fixtures
    head = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640">
  <title>Test science diagram</title><desc>Fixture used for validator tests.</desc>
  <style>@keyframes pulse {{ from {{ opacity: .5; }} to {{ opacity: 1; }} }}.pulse {{ animation: pulse 2s infinite; }}</style>
  <rect x="20" y="20" width="920" height="600" rx="12" fill="#f7f4e9" />
  <text x="40" y="65" font-size="28">{concept['name']}</text>
"""

    if cid == "pythagoras":
        body = """  <polygon id="right_triangle" points="120,420 120,180 420,420" fill="#dce8b5" stroke="#244638" stroke-width="3" />
  <rect id="right_angle_marker" x="120" y="396" width="24" height="24" fill="none" stroke="#244638" stroke-width="2" />
  <circle class="pulse" cx="300" cy="250" r="14" fill="#c8d96b" />
  <text x="100" y="105" font-size="16">hypotenuse</text>
  <text x="100" y="140" font-size="16">right angle</text>
  <text x="100" y="175" font-size="16">a² + b² = c²</text>
  <text x="100" y="210" font-size="16">adjacent</text>
  <text x="100" y="245" font-size="16">opposite</text>
  <text x="280" y="290" font-size="16">c</text>
"""
    elif cid == "circle":
        body = """  <circle id="main_circle" cx="480" cy="320" r="150" fill="#dce8b5" stroke="#244638" stroke-width="3" />
  <circle id="circle_centre" cx="480" cy="320" r="5" fill="#244638" />
  <line id="radius_line" x1="480" y1="320" x2="630" y2="320" stroke="#244638" stroke-width="3" />
  <line id="diameter_line" x1="330" y1="320" x2="630" y2="320" stroke="#244638" stroke-width="2" />
  <circle class="pulse" cx="480" cy="320" r="14" fill="#c8d96b" />
  <text x="100" y="105" font-size="16">centre</text>
  <text x="100" y="140" font-size="16">radius</text>
  <text x="100" y="175" font-size="16">diameter</text>
  <text x="100" y="210" font-size="16">circumference</text>
  <text x="100" y="245" font-size="16">chord</text>
"""
    elif cid == "series-circuit":
        body = """  <polyline id="circuit_loop" points="200,200 760,200 760,440 200,440 200,200" fill="none" stroke="#244638" stroke-width="3" />
  <rect id="battery" x="440" y="185" width="80" height="30" fill="#c8d96b" stroke="#244638" stroke-width="2" />
  <circle id="lamp1" cx="320" cy="440" r="22" fill="#dce8b5" stroke="#244638" stroke-width="2" />
  <circle id="lamp2" cx="640" cy="440" r="22" fill="#dce8b5" stroke="#244638" stroke-width="2" />
  <circle class="pulse" cx="480" cy="200" r="14" fill="#c8d96b" />
  <text x="100" y="105" font-size="16">cell</text>
  <text x="100" y="140" font-size="16">current</text>
  <text x="100" y="175" font-size="16">voltage</text>
  <text x="100" y="210" font-size="16">ammeter</text>
  <text x="100" y="245" font-size="16">resistor</text>
"""
    elif cid == "photosynthesis":
        body = """  <ellipse id="leaf" cx="480" cy="320" rx="180" ry="100" fill="#dce8b5" stroke="#244638" stroke-width="3" />
  <line id="light_ray" x1="200" y1="180" x2="380" y2="280" stroke="#c8d96b" stroke-width="3" />
  <line id="co2_in" x1="200" y1="320" x2="360" y2="320" stroke="#8fa58a" stroke-width="3" />
  <line id="h2o_in" x1="480" y1="500" x2="480" y2="400" stroke="#8fa58a" stroke-width="3" />
  <line id="glucose_out" x1="580" y1="300" x2="740" y2="240" stroke="#244638" stroke-width="3" />
  <line id="o2_out" x1="580" y1="340" x2="740" y2="390" stroke="#244638" stroke-width="3" />
  <circle class="pulse" cx="480" cy="320" r="14" fill="#c8d96b" />
  <text x="100" y="105" font-size="16">chlorophyll</text>
  <text x="100" y="140" font-size="16">light</text>
  <text x="100" y="175" font-size="16">carbon dioxide</text>
  <text x="100" y="210" font-size="16">water</text>
  <text x="100" y="245" font-size="16">glucose</text>
  <text x="100" y="280" font-size="16">oxygen</text>
"""
    elif cid == "states-of-matter":
        body = """  <rect id="solid_container" x="80" y="200" width="240" height="240" fill="none" stroke="#244638" stroke-width="3" />
  <rect id="liquid_container" x="360" y="200" width="240" height="240" fill="none" stroke="#244638" stroke-width="3" />
  <rect id="gas_container" x="640" y="200" width="240" height="240" fill="none" stroke="#244638" stroke-width="3" />
  <!-- Solid grid -->
  <circle class="solid_particle" cx="160" cy="280" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="200" cy="280" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="240" cy="280" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="160" cy="320" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="200" cy="320" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="240" cy="320" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="160" cy="360" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="200" cy="360" r="12" fill="#8fa58a" />
  <circle class="solid_particle" cx="240" cy="360" r="12" fill="#8fa58a" />
  <!-- Liquid particles close together with SMIL animation -->
  <circle class="liquid_particle" cx="420" cy="260" r="12" fill="#c8d96b">
    <animate attributeName="cx" values="420;435;420" dur="2s" repeatCount="indefinite" />
  </circle>
  <circle class="liquid_particle" cx="460" cy="275" r="12" fill="#c8d96b" />
  <circle class="liquid_particle" cx="500" cy="265" r="12" fill="#c8d96b" />
  <circle class="liquid_particle" cx="435" cy="320" r="12" fill="#c8d96b" />
  <circle class="liquid_particle" cx="480" cy="325" r="12" fill="#c8d96b" />
  <circle class="liquid_particle" cx="525" cy="315" r="12" fill="#c8d96b" />
  <!-- Gas particles widely spaced -->
  <circle class="gas_particle pulse" cx="690" cy="240" r="12" fill="#dce8b5" />
  <circle class="gas_particle" cx="830" cy="260" r="12" fill="#dce8b5" />
  <circle class="gas_particle" cx="710" cy="390" r="12" fill="#dce8b5" />
  <circle class="gas_particle" cx="820" cy="400" r="12" fill="#dce8b5" />
  <text x="100" y="105" font-size="16">solid</text>
  <text x="100" y="140" font-size="16">liquid</text>
  <text x="100" y="175" font-size="16">gas</text>
  <text x="100" y="210" font-size="16">particles</text>
  <text x="100" y="245" font-size="16">energy</text>
"""
    else:
        labels = list(concept["required_terms"])
        labels.extend(["Clear scientific relationship", "Diagram label"])
        text_nodes = [f'<text x="100" y="{105 + index * 35}" font-size="16">{label}</text>' for index, label in enumerate(labels)]
        body = """  <polygon points="120,420 120,180 420,420" fill="#dce8b5" stroke="#244638" stroke-width="3" />
  <circle class="pulse" cx="300" cy="250" r="14" fill="#c8d96b" />
""" + "\n".join(text_nodes)

    return head + body + "\n</svg>"


@pytest.fixture
def valid_svg_factory():
    return make_valid_svg
