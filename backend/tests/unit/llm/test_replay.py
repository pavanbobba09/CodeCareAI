from pathlib import Path

from pydantic import BaseModel

from app.llm.replay import RecordingLlm, ReplayLlm
from tests.fakes import ScriptedLlm


class Out(BaseModel):
    answer: str


def test_recorder_writes_nothing_until_save(tmp_path: Path) -> None:
    rec = RecordingLlm(ScriptedLlm(extract=Out(answer="a")), tmp_path)

    rec.complete_json("extract", "sys", "user", Out, deadline=1e9)
    assert list(tmp_path.iterdir()) == []

    [path] = rec.save()
    assert path == tmp_path / "extract.json"


def test_replay_returns_recording_and_flags_prompt_drift(tmp_path: Path) -> None:
    rec = RecordingLlm(ScriptedLlm(extract=Out(answer="a")), tmp_path)
    rec.complete_json("extract", "sys", "user", Out, deadline=1e9)
    rec.save()
    replay = ReplayLlm(tmp_path)

    assert replay.model == "scripted-model"
    assert replay.complete_json("extract", "sys", "user", Out, 1e9) == Out(answer="a")
    assert replay.prompt_drift == []

    replay.complete_json("extract", "sys", "changed user", Out, 1e9)
    assert replay.prompt_drift == ["extract"]
