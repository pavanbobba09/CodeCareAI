"""What produced a run: code commit, prompts, and code sets (recorded in meta.json).

The resume guard compares what must not change inside one run (setup, model, prompt version,
gold scope, replay source). A live run also cannot cross code commits. A replay may resume
on a newer commit because replay exists specifically to run new deterministic code on saved
LLM outputs; those commits are recorded in `resumed_at_commits`.
"""

import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.eval import GoldNote
from app.terminology.code_sets import resolve_code_sets

REPO = Path(__file__).resolve().parents[1]
GUARDED = ("run_id", "setup", "model", "prompt_version", "gold", "replay_of")


def git_commit(repo: Path = REPO) -> str:
    """HEAD's hash, with "-dirty" when tracked files have uncommitted changes."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=repo).returncode != 0
    return f"{head}-dirty" if dirty else head


def code_set_ids(session: Session, golds: list[GoldNote]) -> list[str]:
    """Code sets the scoped notes' visit dates resolve to (ICD-10-CM, and CPT when loaded)."""
    ids: set[str] = set()
    with session.begin():
        for g in golds:
            sets = resolve_code_sets(session, g.visit_date)
            ids |= {sets.icd10cm, *([sets.cpt] if sets.cpt else [])}
    return sorted(ids)


def resume_meta(saved: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """The meta.json to keep when a run is started again. Raises ValueError when a guarded
    field differs; otherwise keeps the original record and notes a newer commit."""
    changed = [k for k in GUARDED if saved.get(k) != new.get(k)]
    if not saved.get("replay_of") and saved.get("git_commit") != new.get("git_commit"):
        changed.append("git_commit")
    if changed:
        raise ValueError(
            f"run {new['run_id']} was started with different {', '.join(changed)}: "
            f"{ {k: saved.get(k) for k in changed} } vs { {k: new.get(k) for k in changed} }"
        )
    merged = dict(saved)
    commit = new.get("git_commit")
    if commit and commit != saved.get("git_commit"):
        seen = merged.get("resumed_at_commits", [])
        merged["resumed_at_commits"] = [*seen, commit] if commit not in seen else seen
    return merged
