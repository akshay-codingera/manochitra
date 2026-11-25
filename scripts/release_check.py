"""Fail-closed pre-deployment audit for the five required generated diagrams.

Run from the repository root after generating the initial batch:
    python scripts/release_check.py

This script does not call Gemini. It re-runs the deterministic SVG validators
and the concept structure validator against the committed results.json and checks
deployment prerequisites.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.concepts import CONCEPTS
from app.core.config import GEMINI_API_KEY, RESULTS_PATH
from app.validators.concept_structure_validator import validate_concept_structure
from app.validators.svg_validator import validate_svg


from app.core.models import ALLOWED_MODEL_IDS


def main() -> int:
    issues: list[str] = []
    try:
        payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("results.json must contain a 'results' array.")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL  Cannot read valid results.json: {exc}")
        return 1

    by_id: dict[str, list[dict]] = {}
    for result in results:
        by_id.setdefault(result.get("concept_id", ""), []).append(result)

    for concept in CONCEPTS:
        concept_id = concept["id"]
        matches = by_id.get(concept_id, [])
        if len(matches) != 1:
            issues.append(f"{concept['name']}: expected exactly one saved result; found {len(matches)}.")
            print(f"FAIL  {concept['name']}: missing or duplicate result")
            continue

        result = matches[0]
        if result.get("status") != "PASS":
            issues.append(f"{concept['name']}: saved status is {result.get('status')!r}, not PASS.")
        svg = result.get("svg", "")
        report = validate_svg(svg, concept)
        cs_result = validate_concept_structure(report.parsed_root, concept)
        report.checks["concept_structure"] = cs_result

        if not report.passed:
            issues.append(f"{concept['name']}: SVG failed fresh validation: {'; '.join(report.failures)}")
        if result.get("checks") != report.as_dict():
            issues.append(f"{concept['name']}: stored checks do not match a fresh validation run.")
        model = result.get("model")
        if not model:
            issues.append(f"{concept['name']}: model name is missing.")
        elif model not in ALLOWED_MODEL_IDS:
            issues.append(f"{concept['name']}: model {model!r} is not an allowed model ({', '.join(sorted(ALLOWED_MODEL_IDS))}).")
        usage = result.get("usage") or {}
        if (
            usage.get("metadata_available") is not True
            or not isinstance(usage.get("input_tokens"), int)
            or not isinstance(usage.get("output_tokens"), int)
        ):
            issues.append(f"{concept['name']}: model token usage metadata is missing or malformed.")
        if not isinstance(result.get("retries", {}).get("total_retries"), int):
            issues.append(f"{concept['name']}: retry accounting is missing.")
        
        passed_checks_count = sum(c.passed for c in report.checks.values())
        total_checks_count = len(report.checks)
        print(f"{'PASS' if report.passed and result.get('status') == 'PASS' else 'FAIL'}  {concept['name']}: {passed_checks_count}/{total_checks_count} code checks")

    extras = sorted(set(by_id) - {concept["id"] for concept in CONCEPTS})
    if extras:
        issues.append(f"Unexpected concept IDs in results.json: {', '.join(extras)}.")

    if not GEMINI_API_KEY:
        issues.append("GEMINI_API_KEY is not configured; the deployed live Generate action cannot work.")
        print("FAIL  GEMINI_API_KEY is not configured for live generation")
    else:
        print("PASS  GEMINI_API_KEY is configured (the secret value is never printed)")

    if issues:
        print(f"\nRELEASE BLOCKED: {len(issues)} issue(s)")
        for issue in issues:
            print(f" - {issue}")
        return 1

    print("\nRELEASE CHECK PASSED: five unique results, fresh 6-gate validation, usage metadata and live API key are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
