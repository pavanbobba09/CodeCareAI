"""Recorded LLM responses for tests (CLAUDE.md rule 9) and the recorder that makes them.

Files live at <dir>/<step>.json:
{"step", "model", "prompt_sha256", "response"}
"""

import json
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.llm.client import JsonLlm
from app.llm.prompts import prompt_hash

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class ReplayLlm:
    """Serves recorded responses. Warns, but still replays, when the prompt changed."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory
        self._model = json.loads((directory / "extract.json").read_text())["model"]
        self.prompt_drift: list[str] = []

    @property
    def model(self) -> str:
        return str(self._model)

    def complete_json(
        self, step: str, system: str, user: str, schema: type[T], deadline: float
    ) -> T:
        record = json.loads((self._dir / f"{step}.json").read_text())
        if record["prompt_sha256"] != prompt_hash(system, user):
            self.prompt_drift.append(step)
            log.warning("replay %s: prompt differs from the recording", step)
        return schema.model_validate(record["response"])


class RecordingLlm:
    """Wraps a real client and keeps each step's validated response in memory.

    Nothing is written until save(), so a run that fails part-way never leaves
    fixture files from two different runs.
    """

    def __init__(self, inner: JsonLlm, directory: Path) -> None:
        self._inner = inner
        self._dir = directory
        self._records: dict[str, dict[str, object]] = {}

    @property
    def model(self) -> str:
        return self._inner.model

    def complete_json(
        self, step: str, system: str, user: str, schema: type[T], deadline: float
    ) -> T:
        result = self._inner.complete_json(step, system, user, schema, deadline)
        self._records[step] = {
            "step": step,
            "model": self._inner.model,
            "prompt_sha256": prompt_hash(system, user),
            "response": result.model_dump(mode="json"),
        }
        return result

    def save(self) -> list[Path]:
        """Write every recorded step of this run, replacing older files."""
        self._dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for step, record in self._records.items():
            path = self._dir / f"{step}.json"
            path.write_text(json.dumps(record, indent=2) + "\n")
            paths.append(path)
        return paths
