from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.llm.client import CallUsage
from eval.budget import UsageLedger, check, per_note_tokens, used_last_day
from eval.records import NoteRun

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _usage(prompt: int, completion: int) -> CallUsage:
    return CallUsage(
        step="s", prompt_tokens=prompt, completion_tokens=completion, reasoning_tokens=None
    )


def _run(setup: str, usage: list[CallUsage], status: str = "completed") -> NoteRun:
    return NoteRun.model_validate(
        {
            "note_id": "n001",
            "setup": setup,
            "model": "m",
            "prompt_version": "v",
            "status": status,
            "error": None,
            "attempts": 1,
            "n_sentences": 1,
            "predicted": [],
            "gap_rules": [],
            "em_code": None,
            "model_errors": 0,
            "latency_ms": 1,
            "usage": [u.model_dump() for u in usage],
        }
    )


def test_ledger_records_calls_and_hands_them_out_once(tmp_path: Path) -> None:
    ledger = UsageLedger("m", tmp_path / "ledger.jsonl")
    ledger.record(_usage(100, 20))
    ledger.record(_usage(50, 5))

    assert len(ledger.take()) == 2
    assert ledger.take() == []
    assert (
        used_last_day("m", datetime.now(UTC) + timedelta(minutes=1), tmp_path / "ledger.jsonl")
        == 175
    )
    assert used_last_day("other", datetime.now(UTC), tmp_path / "ledger.jsonl") == 0


def test_ledger_ignores_calls_older_than_a_day(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    UsageLedger("m", path).record(_usage(100, 0))

    assert used_last_day("m", datetime.now(UTC) + timedelta(days=1, minutes=1), path) == 0


def test_per_note_estimate_uses_saved_usage_else_default() -> None:
    runs = [_run("pipeline", [_usage(3000, 500)]), _run("pipeline", [_usage(4000, 500)])]

    assert per_note_tokens("pipeline", "m", runs) == 4000
    assert per_note_tokens("baseline", "m", runs) == 800  # default, no saved baseline usage
    assert per_note_tokens("pipeline", "m", [_run("pipeline", [_usage(9, 9)], "failed")]) == 4000


def test_check_warns_when_the_run_does_not_fit(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    fits, message = check(20, "pipeline", "m", [], NOW, limit=50_000, ledger=ledger)

    assert not fits
    assert "80000 needed" in message and "50000 left" in message
    assert check(10, "pipeline", "m", [], NOW, limit=50_000, ledger=ledger)[0]
