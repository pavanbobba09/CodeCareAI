"""Paced, retrying, resumable eval loop. Setup-agnostic: it only calls `predict`."""

import json
import logging
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.llm.client import JsonLlm
from app.models.eval import GoldNote
from eval.records import NoteRun

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Failures worth retrying later: the provider was busy or slow. LLM_BAD_OUTPUT is a
# model-quality result and is kept as the answer.
RETRYABLE = {"LLM_UNAVAILABLE", "TIMEOUT"}
NOTE_RETRY_WAITS_S: Sequence[float] = (30.0, 60.0, 120.0)
DEFAULT_CALL_INTERVAL_S = 4.0


class PacedLlm:
    """Keeps at least `interval_s` between the starts of consecutive LLM calls."""

    def __init__(
        self,
        inner: JsonLlm,
        interval_s: float,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._interval = interval_s
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    @property
    def model(self) -> str:
        return self._inner.model

    def complete_json(
        self, step: str, system: str, user: str, schema: type[T], deadline: float
    ) -> T:
        if self._last is not None:
            wait = self._interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        return self._inner.complete_json(step, system, user, schema, deadline)


def load_runs(run_dir: Path) -> dict[str, NoteRun]:
    return {
        p.stem: NoteRun.model_validate(json.loads(p.read_text()))
        for p in sorted(run_dir.glob("n*.json"))
    }


def run_notes(
    golds: list[GoldNote],
    predict: Callable[[GoldNote], NoteRun],
    run_dir: Path,
    sleep: Callable[[float], None] = time.sleep,
    retry_waits: Sequence[float] = NOTE_RETRY_WAITS_S,
) -> dict[str, NoteRun]:
    """Run each note once; skip notes already completed in run_dir; save as we go."""
    run_dir.mkdir(parents=True, exist_ok=True)
    done = load_runs(run_dir)
    for gold in golds:
        previous = done.get(gold.note_id)
        if previous is not None and previous.status == "completed":
            log.info("%s: already completed, skipping", gold.note_id)
            continue
        result = predict(gold)
        attempts = 1
        for wait in retry_waits:
            if result.status == "completed" or result.error not in RETRYABLE:
                break
            log.warning("%s: %s; retrying in %.0f s", gold.note_id, result.error, wait)
            sleep(wait)
            result = predict(gold)
            attempts += 1
        result = result.model_copy(update={"attempts": attempts})
        (run_dir / f"{gold.note_id}.json").write_text(result.model_dump_json(indent=2) + "\n")
        done[gold.note_id] = result
        log.info("%s: %s %s", gold.note_id, result.status, [p.code for p in result.predicted])
    return done
