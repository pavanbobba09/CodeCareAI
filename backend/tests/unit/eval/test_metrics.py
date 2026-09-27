from datetime import date

from app.models.eval import ExpectedCode, GoldNote
from eval.metrics import meets, summarize
from eval.records import NoteRun, PredictedCode


def _gold(note_id: str, codes: list[str], gaps: list[str] | None = None) -> GoldNote:
    return GoldNote(
        note_id=note_id,
        visit_date=date(2026, 10, 5),
        patient_type="established",
        text="t",
        expected_codes=[ExpectedCode(code=c, system="ICD-10-CM", reason="r") for c in codes],
        expected_gap_rules=gaps or [],
        expected_em=None,
        tags=[],
    )


def _p(
    code: str, evidence: list[int] | None = None, real: bool = True, billable: bool | None = None
) -> PredictedCode:
    return PredictedCode(
        code=code,
        evidence=[1] if evidence is None else evidence,
        in_code_set=real,
        billable=real if billable is None else billable,
    )


def _run(note_id: str, predicted: list[PredictedCode], **kw: object) -> NoteRun:
    base: dict[str, object] = {
        "note_id": note_id,
        "setup": "pipeline",
        "model": "m",
        "prompt_version": "v",
        "status": "completed",
        "error": None,
        "attempts": 1,
        "n_sentences": 3,
        "predicted": predicted,
        "gap_rules": [],
        "em_code": None,
        "model_errors": 0,
        "latency_ms": 100,
    }
    return NoteRun.model_validate({**base, **kw})


def test_precision_recall_are_micro_averaged_on_exact_codes() -> None:
    golds = [_gold("n001", ["E11.22", "N18.30"]), _gold("n002", ["I10"])]
    runs = {
        "n001": _run("n001", [_p("E11.22"), _p("N18.3")]),  # N18.3 != N18.30
        "n002": _run("n002", [_p("I10"), _p("R06.02")]),
    }
    s = summarize(golds, runs)
    assert (s.precision, s.recall) == (0.5, round(2 / 3, 4))
    assert s.per_note[0].missed == ["N18.30"]
    assert s.per_note[0].extra == ["N18.3"]


def test_invented_and_unsupported_rates() -> None:
    golds = [_gold("n001", ["I10"])]
    runs = {
        "n001": _run(
            "n001",
            [_p("I10"), _p("X99.9", real=False), _p("E11.9", evidence=[]), _p("N18.9", [7])],
        )
    }
    s = summarize(golds, runs)
    assert s.invented_rate == 0.25
    assert s.unsupported_rate == 0.5  # no evidence, and sentence 7 of a 3-sentence note
    assert s.per_note[0].invented == ["X99.9"]


def test_invalid_counts_invented_and_non_billable_but_invented_stays_narrow() -> None:
    golds = [_gold("n001", ["N18.30"])]
    runs = {
        "n001": _run(
            "n001",
            [_p("N18.30"), _p("N18.3", billable=False), _p("X99.9", real=False)],
        )
    }
    s = summarize(golds, runs)
    assert s.per_note[0].invented == ["X99.9"]
    assert s.per_note[0].invalid == ["N18.3", "X99.9"]
    assert (s.invented_rate, s.invalid_rate) == (round(1 / 3, 4), round(2 / 3, 4))


def test_failed_note_counts_as_nothing_predicted() -> None:
    golds = [_gold("n001", ["I10"]), _gold("n002", ["I10"])]
    runs = {
        "n001": _run("n001", [_p("I10")]),
        "n002": _run("n002", [], status="failed", error="LLM_UNAVAILABLE"),
    }
    s = summarize(golds, runs)
    assert (s.failed_notes, s.recall, s.precision) == (1, 0.5, 1.0)


def test_gap_recall_and_unmeasured_metrics() -> None:
    golds = [_gold("n001", ["N18.9"], ["R9"]), _gold("n002", ["I50.9"], ["R10"])]
    runs = {
        "n001": _run("n001", [_p("N18.9")], gap_rules=["R9"]),
        "n002": _run("n002", [_p("I50.9")]),
    }
    s = summarize(golds, runs)
    assert s.gap_recall == 0.5
    assert s.em_match is None


def test_no_predictions_means_rates_are_not_measured() -> None:
    s = summarize([_gold("n001", ["I10"])], {"n001": _run("n001", [])})
    assert (s.precision, s.invented_rate, s.recall) == (None, None, 0.0)


def test_thresholds() -> None:
    assert meets("invented_rate", 0.0) is True
    assert meets("invented_rate", 0.01) is False
    assert meets("invalid_rate", 0.0) is True
    assert meets("invalid_rate", 0.01) is False
    assert meets("recall", 0.8) is True
    assert meets("unsupported_rate", 0.06) is False
    assert meets("em_match", None) is None
