from pathlib import Path

import pytest

from eval import rescore
from eval.metrics import Summary


def _unmeasured_incomplete_summary() -> Summary:
    return Summary(
        notes=0,
        failed_notes=0,
        missing_notes=["n001"],
        complete=False,
        predicted_codes=0,
        precision=None,
        recall=None,
        invented_rate=None,
        invalid_rate=None,
        evidence_ref_invalid_rate=None,
        unsupported_rate=None,
        gap_recall=None,
        em_match=None,
        mean_latency_ms=0,
        per_note=[],
    )


def test_pipeline_gates_fail_for_incomplete_and_unmeasured_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "r1"
    run_dir.mkdir()
    (run_dir / "meta.json").write_text("{}")
    monkeypatch.setattr(rescore, "RUNS", tmp_path)
    monkeypatch.setattr(
        rescore,
        "score_run",
        lambda _: ({"run_id": "r1", "setup": "pipeline"}, _unmeasured_incomplete_summary()),
    )

    with pytest.raises(SystemExit) as exc:
        rescore.main()

    message = str(exc.value)
    assert "incomplete run" in message
    assert "invented_rate is unmeasured" in message
    assert "invalid_rate is unmeasured" in message
