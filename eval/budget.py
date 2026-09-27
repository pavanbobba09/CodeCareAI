"""Token budget for live eval runs: a local ledger of every LLM call and a pre-run check.

The ledger (eval/.usage_ledger.jsonl, gitignored) records each call's tokens as the
provider reports them. Before a live run, the check estimates the tokens the remaining
notes need and compares them with what is left of the daily limit in the last 24 hours.
Groq's free tier limits gpt-oss-120b to 200k tokens per rolling day (M4 finding).
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.llm.client import CallUsage
from eval.records import NoteRun, Setup

LEDGER = Path(__file__).resolve().parent / ".usage_ledger.jsonl"
DAILY_TOKEN_LIMIT = 200_000
# Used until saved runs with usage exist for the same setup and model (M4 estimate).
DEFAULT_NOTE_TOKENS: dict[str, int] = {"pipeline": 4_000, "baseline": 800}


def total(usage: list[CallUsage]) -> int:
    return sum(u.prompt_tokens + u.completion_tokens for u in usage)


class UsageLedger:
    """Appends every call to the ledger and keeps the calls since the last take()."""

    def __init__(self, model: str, path: Path = LEDGER) -> None:
        self._model = model
        self._path = path
        self._pending: list[CallUsage] = []

    def record(self, usage: CallUsage) -> None:
        self._pending.append(usage)
        line = {"ts": datetime.now(UTC).isoformat(), "model": self._model, **usage.model_dump()}
        with self._path.open("a") as f:
            f.write(json.dumps(line) + "\n")

    def take(self) -> list[CallUsage]:
        taken, self._pending = self._pending, []
        return taken


def used_last_day(model: str, now: datetime, path: Path = LEDGER) -> int:
    if not path.exists():
        return 0
    since = now - timedelta(days=1)
    used = 0
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["model"] == model and datetime.fromisoformat(row["ts"]) >= since:
            used += row["prompt_tokens"] + row["completion_tokens"]
    return used


def per_note_tokens(setup: Setup, model: str, runs: list[NoteRun]) -> int:
    """Mean tokens of completed notes with recorded usage, else the default estimate."""
    spent = [
        total(r.usage)
        for r in runs
        if r.setup == setup and r.model == model and r.status == "completed" and r.usage
    ]
    return round(sum(spent) / len(spent)) if spent else DEFAULT_NOTE_TOKENS[setup]


def check(
    notes: int,
    setup: Setup,
    model: str,
    runs: list[NoteRun],
    now: datetime,
    limit: int,
    ledger: Path = LEDGER,
) -> tuple[bool, str]:
    """(fits, message) for running `notes` more notes now."""
    need = notes * per_note_tokens(setup, model, runs)
    left = max(limit - used_last_day(model, now, ledger), 0)
    msg = (
        f"budget: {notes} notes x ~{need // max(notes, 1)} tokens = ~{need} needed; "
        f"~{left} of {limit} left for {model} in the last 24 h (local ledger)"
    )
    return need <= left, msg
