from datetime import date
from pathlib import Path

from pydantic import BaseModel

from app.models.eval import ExpectedCode, GoldNote
from eval.records import NoteRun
from eval.runner import PacedLlm, load_runs, run_notes
from eval.setups import normalize_code
from tests.fakes import ScriptedLlm


class Out(BaseModel):
    answer: str


def _gold(note_id: str) -> GoldNote:
    return GoldNote(
        note_id=note_id,
        visit_date=date(2026, 10, 5),
        patient_type="established",
        text="t",
        expected_codes=[ExpectedCode(code="I10", system="ICD-10-CM", reason="r")],
        expected_gap_rules=[],
        expected_em=None,
        tags=[],
    )


def _run(note_id: str, status: str = "completed", error: str | None = None) -> NoteRun:
    return NoteRun(
        note_id=note_id,
        setup="pipeline",
        model="m",
        prompt_version="v",
        status="completed" if status == "completed" else "failed",
        error=error,
        attempts=1,
        n_sentences=1,
        predicted=[],
        gap_rules=[],
        em_code=None,
        model_errors=0,
        latency_ms=1,
    )


def test_paced_llm_spaces_call_starts() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def sleep(s: float) -> None:
        sleeps.append(s)
        now[0] += s

    llm = PacedLlm(ScriptedLlm(x=Out(answer="a")), 4.0, sleep=sleep, clock=lambda: now[0])
    llm.complete_json("x", "s", "u", Out, 1e9)
    now[0] += 1.5  # the call itself took 1.5 s
    llm.complete_json("x", "s", "u", Out, 1e9)
    now[0] += 10.0  # already past the interval
    llm.complete_json("x", "s", "u", Out, 1e9)
    assert sleeps == [2.5]


def test_run_notes_retries_busy_provider_with_backoff(tmp_path: Path) -> None:
    results = iter([_run("n001", "failed", "LLM_UNAVAILABLE"), _run("n001")])
    sleeps: list[float] = []

    runs = run_notes([_gold("n001")], lambda g: next(results), tmp_path, sleep=sleeps.append)

    assert runs["n001"].status == "completed"
    assert runs["n001"].attempts == 2
    assert sleeps == [30.0]


def test_run_notes_gives_up_after_all_waits(tmp_path: Path) -> None:
    calls = []

    def predict(g: GoldNote) -> NoteRun:
        calls.append(g.note_id)
        return _run(g.note_id, "failed", "TIMEOUT")

    runs = run_notes([_gold("n001")], predict, tmp_path, sleep=lambda s: None)
    assert (runs["n001"].status, runs["n001"].attempts, len(calls)) == ("failed", 4, 4)


def test_bad_output_is_not_retried(tmp_path: Path) -> None:
    calls = []

    def predict(g: GoldNote) -> NoteRun:
        calls.append(1)
        return _run(g.note_id, "failed", "LLM_BAD_OUTPUT")

    run_notes([_gold("n001")], predict, tmp_path, sleep=lambda s: None)
    assert len(calls) == 1


def test_resume_skips_completed_and_reruns_failed(tmp_path: Path) -> None:
    first = {"n001": _run("n001"), "n002": _run("n002", "failed", "LLM_BAD_OUTPUT")}
    run_notes([_gold("n001"), _gold("n002")], lambda g: first[g.note_id], tmp_path)

    calls: list[str] = []

    def predict(g: GoldNote) -> NoteRun:
        calls.append(g.note_id)
        return _run(g.note_id)

    runs = run_notes([_gold("n001"), _gold("n002"), _gold("n003")], predict, tmp_path)

    assert calls == ["n002", "n003"]
    assert all(r.status == "completed" for r in runs.values())
    assert set(load_runs(tmp_path)) == {"n001", "n002", "n003"}


def test_normalize_code_adds_missing_dot() -> None:
    assert normalize_code(" e1122 ") == "E11.22"
    assert normalize_code("I10") == "I10"
    assert normalize_code("N18.30") == "N18.30"
