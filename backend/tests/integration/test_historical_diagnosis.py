"""Full pipeline, historical diagnosis: "history of heart failure" must produce no I50 code.

Two ways an I50 code could appear: a selection for the history fact itself (it gets no
candidates, so validation drops it), and the model attaching an I50 code to another,
active fact whose candidates happen to include it. R10 keeps an I50 code without a
documented active heart failure fact as not suggested, so it is never reported.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import ExtractionOutput, Note, SelectionOutput
from app.pipeline.graph import run_pipeline
from app.pipeline.state import PipelineDeps
from app.segment.segmenter import segment_note
from app.terminology.code_sets import resolve_code_sets
from tests.fakes import ScriptedLlm
from tests.integration.conftest import FakeEmbedder

TEXT = (  # synthetic
    "HPI: History of heart failure. Blood pressure check today.\n"
    "Assessment: Essential hypertension.\n"
    "Plan: Continue lisinopril.\n"
)


def test_history_of_heart_failure_is_never_reported(seeded: Engine) -> None:
    sentences = segment_note(TEXT)
    texts = [s.text for s in sentences]
    history, htn = (
        texts.index("History of heart failure.") + 1,
        texts.index("Essential hypertension.") + 1,
    )
    extract = ExtractionOutput.model_validate(
        {
            "facts": [
                {"fact_id": "f1", "kind": "condition", "concept": "heart failure",
                 "status": "history", "details": {}, "links": [], "evidence": [history]},
                {"fact_id": "f2", "kind": "condition", "concept": "essential hypertension",
                 "status": "active", "details": {}, "links": [], "evidence": [htn]},
            ],
            "mdm": {"problems": None, "data": None, "risk": None, "evidence": []},
        }
    )  # fmt: skip
    select = SelectionOutput.model_validate(
        {
            "selections": [
                {"fact_id": "f1", "code": "I50.9", "evidence": [history], "rationale": "r"},
                {"fact_id": "f2", "code": "I10", "evidence": [htn], "rationale": "r"},
                # Wrong but valid: I50.20 is among the hypertension fact's candidates.
                {"fact_id": "f2", "code": "I50.20", "evidence": [htn], "rationale": "r"},
            ]
        }
    )
    note = Note(
        id=str(uuid.uuid4()),
        visit_date=date(2026, 10, 20),
        patient_type="established",
        text=TEXT,
        sentences=sentences,
        parent_note_id=None,
        created_at=datetime.now(UTC),
    )
    with Session(seeded) as s:
        deps = PipelineDeps(s, ScriptedLlm(extract=extract, select=select), FakeEmbedder())
        result = run_pipeline(deps, note, resolve_code_sets(s, note.visit_date))

    assert result.status == "completed"
    reported = sorted(x.code for x in result.suggestions if x.confidence != "not_suggested")
    assert reported == ["I10"]
    for x in result.suggestions:
        if x.code.startswith("I50"):
            assert [r.outcome for r in x.rule_results if r.rule_id == "R10"] == ["fail"]


TEXT_DM_HTN = (  # synthetic
    "HPI: History of diabetes. History of hypertension. Reports fatigue.\n"
    "Assessment: Chronic kidney disease stage 3a.\n"
    "Plan: Recheck renal function in 3 months.\n"
)


def test_history_of_diabetes_and_hypertension_codes_are_never_reported(seeded: Engine) -> None:
    sentences = segment_note(TEXT_DM_HTN)
    texts = [s.text for s in sentences]
    dm, htn = texts.index("History of diabetes.") + 1, texts.index("History of hypertension.") + 1
    ckd = texts.index("Chronic kidney disease stage 3a.") + 1
    tired = texts.index("Reports fatigue.") + 1
    extract = ExtractionOutput.model_validate(
        {
            "facts": [
                {"fact_id": "f1", "kind": "condition", "concept": "diabetes mellitus",
                 "status": "history", "details": {}, "links": [], "evidence": [dm]},
                {"fact_id": "f2", "kind": "condition", "concept": "hypertension",
                 "status": "history", "details": {}, "links": [], "evidence": [htn]},
                {"fact_id": "f3", "kind": "condition", "concept": "chronic kidney disease",
                 "status": "active", "details": {"stage": "3a"}, "links": [], "evidence": [ckd]},
                {"fact_id": "f4", "kind": "condition", "concept": "fatigue",
                 "status": "active", "details": {}, "links": [], "evidence": [tired]},
            ],
            "mdm": {"problems": None, "data": None, "risk": None, "evidence": []},
        }
    )  # fmt: skip
    select = SelectionOutput.model_validate(
        {
            "selections": [
                {"fact_id": "f3", "code": "N18.31", "evidence": [ckd], "rationale": "r"},
                # Wrong but valid: both are among the fatigue fact's candidates in the small
                # test db, so validation accepts them and only the rules can catch them.
                {"fact_id": "f4", "code": "E11.9", "evidence": [tired], "rationale": "r"},
                {"fact_id": "f4", "code": "I10", "evidence": [tired], "rationale": "r"},
            ]
        }
    )
    note = Note(
        id=str(uuid.uuid4()),
        visit_date=date(2026, 10, 20),
        patient_type="established",
        text=TEXT_DM_HTN,
        sentences=sentences,
        parent_note_id=None,
        created_at=datetime.now(UTC),
    )
    with Session(seeded) as s:
        deps = PipelineDeps(s, ScriptedLlm(extract=extract, select=select), FakeEmbedder())
        result = run_pipeline(deps, note, resolve_code_sets(s, note.visit_date))

    assert result.status == "completed"
    # The selections were accepted (they are real candidates), so the rules must catch them.
    assert {"E11.9", "I10"} <= {x.code for x in result.suggestions}
    reported = sorted(x.code for x in result.suggestions if x.confidence != "not_suggested")
    assert reported == ["N18.31"]
