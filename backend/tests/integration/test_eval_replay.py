"""Eval replay: rerun only the rules on saved LLM outputs, with no LLM or embedder calls."""

from datetime import date

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models.eval import ExpectedCode, GoldNote
from eval.setups import predict_pipeline, predict_replay
from tests.fakes import ScriptedLlm
from tests.integration.conftest import FakeEmbedder
from tests.integration.test_pipeline_api import EXTRACT, SELECT, WORKED

GOLD = GoldNote(
    note_id="n900",
    visit_date=date.fromisoformat(WORKED["note"]["visit_date"]),
    patient_type=WORKED["note"]["patient_type"],
    text=WORKED["note"]["text"],
    expected_codes=[
        ExpectedCode(code=e["code"], system="ICD-10-CM", reason="worked example")
        for e in WORKED["expected"]
    ],
    expected_gap_rules=[],
    expected_em=None,
    tags=[],
)


def test_replay_reproduces_the_live_run_from_saved_outputs(seeded: Engine) -> None:
    llm = ScriptedLlm(extract=EXTRACT, select=SELECT)
    with Session(seeded) as session:
        live = predict_pipeline(session, llm, FakeEmbedder(), GOLD, "extract_v1")
    assert live.llm_outputs is not None
    assert [f.fact_id for f in live.llm_outputs.facts] == ["f1", "f2"]
    assert live.llm_outputs.candidate_sets and live.llm_outputs.selections
    assert live.prompt_version == "extract_v1+select_v1"
    # The support check ran: sentence 1 names diabetes with CKD and the stage "3".
    assert {(p.code, p.supported) for p in live.predicted} == {("E11.22", True), ("N18.30", True)}

    with Session(seeded) as session:
        replay = predict_replay(session, live, GOLD)  # raises if it reaches the LLM

    assert replay.status == "completed"
    assert [p.code for p in replay.predicted] == [p.code for p in live.predicted]
    assert replay.gap_rules == live.gap_rules == ["R9"]
    assert (replay.usage, replay.prompt_version) == ([], live.prompt_version)


def test_replay_of_a_failed_note_stays_failed(seeded: Engine) -> None:
    with Session(seeded) as session:
        live = predict_pipeline(
            session, ScriptedLlm(extract=EXTRACT, select=SELECT), FakeEmbedder(), GOLD
        )
    failed = live.model_copy(
        update={"status": "failed", "error": "LLM_UNAVAILABLE", "llm_outputs": None}
    )

    with Session(seeded) as session:
        replay = predict_replay(session, failed, GOLD)

    assert (replay.status, replay.error) == ("failed", "LLM_UNAVAILABLE")


def test_completed_note_without_saved_outputs_replays_as_failed_with_no_codes(
    seeded: Engine,
) -> None:
    with Session(seeded) as session:
        live = predict_pipeline(
            session, ScriptedLlm(extract=EXTRACT, select=SELECT), FakeEmbedder(), GOLD
        )
    old_style = live.model_copy(update={"llm_outputs": None})  # runs saved before M4

    with Session(seeded) as session:
        replay = predict_replay(session, old_style, GOLD)

    assert (replay.status, replay.error, replay.predicted) == ("failed", "NO_SAVED_OUTPUTS", [])
