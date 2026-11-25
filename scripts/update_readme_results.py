"""Refresh the README result table from real data/results.json measurements."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "results.json"
README_PATH = ROOT / "README.md"
START = "<!-- RESULTS_TABLE_START -->"
END = "<!-- RESULTS_TABLE_END -->"
CONCEPT_NAMES = [
    ("pythagoras", "Pythagoras' theorem"),
    ("circle", "Parts of a circle"),
    ("series-circuit", "Series circuit"),
    ("photosynthesis", "Photosynthesis"),
    ("states-of-matter", "States of matter"),
]


def main() -> None:
    payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    records = {item.get("concept_id"): item for item in payload.get("results", [])}
    lines = [
        START,
        "| Concept | Pass / fail | Estimated cost (USD) | Retries |",
        "|---|---:|---:|---:|",
    ]
    for concept_id, name in CONCEPT_NAMES:
        result = records.get(concept_id)
        if not result:
            lines.append(f"| {name} | NOT GENERATED | — | — |")
            continue
        status = result.get("status", "UNKNOWN")
        cost = result.get("cost", {}).get("estimated_cost_usd")
        cost_text = f"${float(cost):.8f}" if isinstance(cost, (int, float)) else "—"
        retries = result.get("retries", {}).get("total_retries", "—")
        lines.append(f"| {name} | {status} | {cost_text} | {retries} |")
    lines.append(END)

    readme = README_PATH.read_text(encoding="utf-8")
    start_index = readme.find(START)
    end_index = readme.find(END)
    if start_index < 0 or end_index < start_index:
        print("Note: README result-table markers not found or out of order; skipping README update.")
        return
    end_index += len(END)
    updated = readme[:start_index] + "\n".join(lines) + readme[end_index:]
    README_PATH.write_text(updated, encoding="utf-8")
    print("Updated README result table from data/results.json.")


if __name__ == "__main__":
    main()
