"""Upgrade all 5 concept diagrams to the enhanced dual-animation standard and validate them."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import json
import xml.etree.ElementTree as ET
from app.core.concepts import CONCEPT_BY_ID
from app.validators.svg_validator import validate_svg
from app.validators.concept_structure_validator import validate_concept_structure
from app.validators.visual_quality_validator import validate_visual_quality

RESULTS_PATH = ROOT / "data" / "results.json"
VERSIONS_PATH = ROOT / "data" / "versions.json"


def upgrade_pythagoras(svg: str) -> str:
    # Ensure dual animation: major hypotenuse pulse + secondary formula/right-angle pulse
    if 'animate attributeName="stroke"' not in svg:
        svg = svg.replace(
            '<polyline points="360,395 385,395 385,420" stroke="#244638" stroke-width="2.5" fill="none" />',
            '<polyline points="360,395 385,395 385,420" stroke="#244638" stroke-width="2.5" fill="none">\n    <animate attributeName="stroke" values="#244638;#C8D96B;#244638" dur="3s" repeatCount="indefinite" />\n  </polyline>'
        )
    return svg


def upgrade_circle(svg: str) -> str:
    # Ensure dual animation: major circumference tracing (stroke-dashoffset) + secondary radius pulse
    if '1131' not in svg:
        # Insert animated circumference tracing circle right after main_circle
        target = '<circle id="main_circle" cx="480" cy="340" r="180" fill="#C8D96B" fill-opacity="0.12" stroke="#244638" stroke-width="3" />'
        addition = (
            target + '\n\n  <!-- Major Animation: Progressive Circumference Tracing (Perimeter 2*pi*180 ≈ 1131) -->\n'
            '  <circle cx="480" cy="340" r="180" fill="none" stroke="#C8D96B" stroke-width="4.5" stroke-dasharray="1131" stroke-dashoffset="1131">\n'
            '    <animate attributeName="stroke-dashoffset" values="1131;0;1131" dur="4s" repeatCount="indefinite" />\n'
            '  </circle>'
        )
        svg = svg.replace(target, addition)
    return svg


def upgrade_series_circuit(svg: str) -> str:
    # Ensure dual animation: major wire current flow + secondary simultaneous bulb illumination glow
    if 'cx="380" cy="160" r="26"' not in svg:
        target1 = '<circle cx="380" cy="160" r="18" fill="#F7F4E9" stroke="#244638" stroke-width="3" />'
        addition1 = (
            '<circle cx="380" cy="160" r="26" fill="#C8D96B" opacity="0.3">\n'
            '      <animate attributeName="opacity" values="0.1;0.65;0.1" dur="2s" repeatCount="indefinite" />\n'
            '    </circle>\n    ' + target1
        )
        svg = svg.replace(target1, addition1)

        target2 = '<circle cx="580" cy="160" r="18" fill="#F7F4E9" stroke="#244638" stroke-width="3" />'
        addition2 = (
            '<circle cx="580" cy="160" r="26" fill="#C8D96B" opacity="0.3">\n'
            '      <animate attributeName="opacity" values="0.1;0.65;0.1" dur="2s" repeatCount="indefinite" />\n'
            '    </circle>\n    ' + target2
        )
        svg = svg.replace(target2, addition2)
    return svg


def upgrade_photosynthesis(svg: str) -> str:
    # Ensure dual animation: major moving photon particles + secondary sun glow
    if 'cx="280" cy="215"' not in svg:
        target = '<line x1="205" y1="170" x2="380" y2="270" stroke="#C8D96B" stroke-width="3" class="flow-line" />'
        addition = (
            target + '\n    <!-- Major Animation: Moving Photon Particle -->\n'
            '    <circle cx="280" cy="215" r="4.5" fill="#C8D96B">\n'
            '      <animate attributeName="cx" values="215;365;215" dur="2s" repeatCount="indefinite" />\n'
            '      <animate attributeName="cy" values="175;262;175" dur="2s" repeatCount="indefinite" />\n'
            '    </circle>'
        )
        svg = svg.replace(target, addition)
    return svg


def upgrade_states_of_matter(svg: str) -> str:
    # Ensure dual animation: major 3-state particle dynamics + secondary temperature flow arrow
    if 'Increasing Thermal Energy' not in svg:
        target = '</svg>'
        addition = (
            '  <!-- Secondary Animation: Thermal Transition Arrow -->\n'
            '  <line x1="100" y1="520" x2="860" y2="520" stroke="#244638" stroke-width="2.5" stroke-dasharray="14, 10">\n'
            '    <animate attributeName="stroke-dashoffset" from="48" to="0" dur="2s" repeatCount="indefinite" />\n'
            '  </line>\n'
            '  <polygon points="860,514 876,520 860,526" fill="#244638" />\n'
            '  <text x="480" y="555" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#244638">\n'
            '    <animate attributeName="fill" values="#8FA58A;#244638;#8FA58A" dur="2s" repeatCount="indefinite" />\n'
            '    Increasing Thermal Energy &amp; Particle Motion →\n'
            '  </text>\n\n</svg>'
        )
        svg = svg.replace(target, addition)
    return svg


UPGRADERS = {
    "pythagoras": upgrade_pythagoras,
    "circle": upgrade_circle,
    "series-circuit": upgrade_series_circuit,
    "photosynthesis": upgrade_photosynthesis,
    "states-of-matter": upgrade_states_of_matter,
}


def main():
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    versions_data = json.loads(VERSIONS_PATH.read_text(encoding="utf-8")) if VERSIONS_PATH.exists() else {}

    all_passed = True

    for result in data["results"]:
        cid = result["concept_id"]
        concept = CONCEPT_BY_ID[cid]
        upgrader = UPGRADERS.get(cid)
        if upgrader:
            new_svg = upgrader(result["svg"])
        else:
            new_svg = result["svg"]

        # Validate with all 6 gates + visual quality
        svg_report = validate_svg(new_svg, concept)
        root = svg_report.parsed_root
        cs_result = validate_concept_structure(root, concept)
        svg_report.checks["concept_structure"] = cs_result
        vq_report = validate_visual_quality(root, concept)

        is_ok = svg_report.passed and cs_result.passed and vq_report.passed
        print(f"[{cid}] Validations: SVG={svg_report.passed}, CS={cs_result.passed}, VQ={vq_report.passed} -> OK={is_ok}")

        if not is_ok:
            all_passed = False
            for k, v in svg_report.checks.items():
                if not v.passed:
                    print(f"  Fail: {k}: {v.detail}")
            for k, v in vq_report.checks.items():
                if not v.passed:
                    print(f"  VQ Fail: {k}: {v.detail}")
            continue

        # Update result record
        result["svg"] = new_svg
        result["checks"] = svg_report.as_dict()
        result["visual_quality"] = vq_report.to_dict()
        result["status"] = "PASS"

        # Update in versions
        c_versions = versions_data.setdefault(cid, [])
        if c_versions:
            latest = max(c_versions, key=lambda v: v.get("version", 0))
            latest["svg"] = new_svg
            latest["checks"] = svg_report.as_dict()
            latest["visual_quality"] = vq_report.to_dict()
            latest["status"] = "PASS"

    if all_passed:
        RESULTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        VERSIONS_PATH.write_text(json.dumps(versions_data, indent=2), encoding="utf-8")
        print("\nAll 5 diagrams successfully upgraded and verified! results.json and versions.json updated.")
    else:
        print("\nSome diagrams failed verification. Aborting write.")
        sys.exit(1)


if __name__ == "__main__":
    main()
