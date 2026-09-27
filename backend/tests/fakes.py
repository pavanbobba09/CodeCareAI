"""Test doubles. Tests never call a real LLM (CLAUDE.md rule 9)."""

from typing import TypeVar

from pydantic import BaseModel

from app.llm.client import LlmError

T = TypeVar("T", bound=BaseModel)


class ScriptedLlm:
    """Returns a scripted response per step, or raises the scripted LlmError."""

    def __init__(self, **steps: BaseModel | LlmError) -> None:
        self.steps = steps
        self.calls: list[tuple[str, str]] = []  # (step, user message)

    @property
    def model(self) -> str:
        return "scripted-model"

    def complete_json(
        self, step: str, system: str, user: str, schema: type[T], deadline: float
    ) -> T:
        self.calls.append((step, user))
        scripted = self.steps[step]
        if isinstance(scripted, LlmError):
            raise scripted
        return schema.model_validate(scripted.model_dump())
