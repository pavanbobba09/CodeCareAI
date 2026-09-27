"""Write the frontend's generated inputs: the OpenAPI schema and the sample notes.

Usage (backend venv active): python scripts/export_frontend.py
Writes frontend/openapi.json (from the FastAPI app, no server needed) and
frontend/lib/samples.json (synthetic notes for the form's "Load sample note" menu).
`npm run gen:types` runs this, then builds frontend/lib/types.ts from openapi.json.
"""

import json
from pathlib import Path

from _common import DATA, REPO
from app.main import app

FRONTEND = REPO / "frontend"

# (label, source). All synthetic; chosen to show evidence, a gap, and combination codes.
SAMPLES = [
    ("Worked example: diabetes with CKD stage 3", DATA / "examples" / "worked_example.json"),
    ("Gap: heart failure without a type", DATA / "gold_notes" / "n009.json"),
    ("Combination: hypertension, heart failure and CKD", DATA / "gold_notes" / "n010.json"),
    ("Abbreviations: DM2, HTN, CKD 3b", DATA / "gold_notes" / "n013.json"),
]


def _sample(label: str, path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text())
    note = raw.get("note", raw)  # the worked example wraps the note; gold notes do not
    return {
        "label": label,
        "visit_date": note["visit_date"],
        "patient_type": note["patient_type"],
        "text": note["text"],
    }


def main() -> None:
    schema = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    (FRONTEND / "openapi.json").write_text(schema)
    samples = [_sample(label, path) for label, path in SAMPLES]
    (FRONTEND / "lib" / "samples.json").write_text(json.dumps(samples, indent=2) + "\n")
    print(f"wrote openapi.json and {len(samples)} samples")


if __name__ == "__main__":
    main()
