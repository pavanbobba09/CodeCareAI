import re

import pytest

from eval.provenance import git_commit, resume_meta
from eval.report import provenance_line

BASE = {
    "run_id": "r1",
    "setup": "pipeline",
    "model": "m",
    "prompt_version": "extract_v1+select_v1",
    "gold": {"n001": "h1"},
    "git_commit": "aaa",
    "code_sets": ["ICD10CM-FY2027"],
}


def test_resume_keeps_the_original_record() -> None:
    assert resume_meta(BASE, dict(BASE)) == BASE


def test_resume_on_a_newer_commit_is_recorded_not_refused() -> None:
    merged = resume_meta(BASE, {**BASE, "git_commit": "bbb"})

    assert merged["git_commit"] == "aaa"  # the run started here
    assert merged["resumed_at_commits"] == ["bbb"]


@pytest.mark.parametrize(
    "change",
    [
        {"prompt_version": "extract_v2+select_v1"},
        {"model": "other"},
        {"setup": "baseline"},
        {"gold": {"n001": "changed"}},
    ],
)
def test_resume_guard_still_refuses_guarded_changes(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=next(iter(change))):
        resume_meta(BASE, {**BASE, **change})


def test_git_commit_is_a_full_hash() -> None:
    assert re.fullmatch(r"[0-9a-f]{40}(-dirty)?", git_commit())


def test_report_header_shows_commit_code_sets_and_replay_source() -> None:
    assert provenance_line(BASE) == "Code commit `aaa`, code sets ICD10CM-FY2027."
    replay = {**BASE, "replay_of": "r0", "source_git_commit": "zzz", "git_commit": "ccc"}
    assert provenance_line(replay) == (
        "Code commit `ccc`, code sets ICD10CM-FY2027. "
        "Replay of `r0` (LLM outputs from commit `zzz`)."
    )
    legacy = {"run_id": "old", "setup": "pipeline", "model": "m", "prompt_version": "v"}
    assert provenance_line(legacy) == "Code commit `not recorded`, code sets not recorded."
