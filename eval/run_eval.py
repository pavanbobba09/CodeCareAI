"""Run the eval against the real LLM and code tables (local only; needs backend/.env).

Usage:
  python eval/run_eval.py --setup pipeline --limit 10 [--model M] [--run-id ID] [--interval 4]
      [--extract-prompt extract_v1] [--ignore-budget]
  python eval/run_eval.py --replay-of RUN_ID [--run-id ID]   # rules only, no LLM calls
Reruns with the same run id skip notes already completed, so a failed run resumes.
Before a live run, a budget check compares the tokens needed with what is left today.
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_engine
from app.llm.client import LlmClient
from app.models.eval import GoldNote
from app.pipeline.state import EXTRACT_PROMPT, prompt_version
from app.terminology.embedder import get_embedder
from eval import budget
from eval.budget import UsageLedger
from eval.gold import changed_notes, gold_hash, load_gold
from eval.records import NoteRun
from eval.report import RUNS, markdown, score_run, write_report
from eval.runner import DEFAULT_CALL_INTERVAL_S, PacedLlm, load_runs, run_notes
from eval.setups import (
    BASELINE_PROMPT_VERSION,
    predict_baseline,
    predict_pipeline,
    predict_replay,
)


def _start_run(run_dir: Path, meta: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        # Resuming: a run must not mix setups, models, prompt versions or replay sources.
        saved = json.loads(meta_path.read_text())
        if saved != meta:
            sys.exit(f"run {meta['run_id']} was started with {saved}; this run would use {meta}")
    meta_path.write_text(json.dumps(meta) + "\n")


def _replay(source_id: str, run_id: str | None, limit: int | None) -> Path:
    source_dir = RUNS / source_id
    source_meta = json.loads((source_dir / "meta.json").read_text())
    if source_meta["setup"] != "pipeline":
        sys.exit("only pipeline runs can be replayed")
    run_id = run_id or f"{date.today().isoformat()}-replay-{source_id}"
    run_dir = RUNS / run_id
    if "gold" not in source_meta:
        sys.exit(f"{source_id} has no gold note hashes (saved before M4); rerun it live")
    current = {g.note_id: g for g in load_gold()}
    changed = changed_notes(source_meta["gold"], list(current.values()))
    if changed:
        sys.exit(f"gold notes changed since {source_id} ran: {', '.join(changed)}; rerun it live")
    meta = {**source_meta, "run_id": run_id, "replay_of": source_id}
    _start_run(run_dir, meta)
    sources = load_runs(source_dir)
    golds = [current[n] for n in sorted(source_meta["gold"]) if n in sources]
    golds = golds[:limit] if limit else golds
    engine = get_engine()

    def predict(gold: GoldNote) -> NoteRun:
        with Session(engine) as session:
            return predict_replay(session, sources[gold.note_id], gold)

    run_notes(golds, predict, run_dir, retry_waits=())
    return run_dir


def _live(args: argparse.Namespace) -> Path:
    if args.model:
        os.environ["LLM_MODEL"] = args.model
        get_settings.cache_clear()
    s = get_settings()
    ledger = UsageLedger(s.llm_model)
    llm = PacedLlm(
        LlmClient(s.llm_base_url, s.llm_api_key, s.llm_model, on_usage=ledger.record),
        args.interval,
    )
    model_slug = llm.model.replace("/", "_")
    run_id = args.run_id or f"{date.today().isoformat()}-{args.setup}-{model_slug}"
    run_dir = RUNS / run_id
    version = (
        prompt_version(args.extract_prompt) if args.setup == "pipeline" else BASELINE_PROMPT_VERSION
    )
    golds = load_gold()[: args.limit] if args.limit else load_gold()
    meta = {
        "run_id": run_id,
        "setup": args.setup,
        "model": llm.model,
        "prompt_version": version,
        "gold": {g.note_id: gold_hash(g) for g in golds},  # scope + change detection
    }
    done = load_runs(run_dir) if run_dir.exists() else {}
    todo = [
        g for g in golds if done.get(g.note_id) is None or done[g.note_id].status != "completed"
    ]
    history = [r for d in RUNS.iterdir() if d.is_dir() for r in load_runs(d).values()]
    fits, message = budget.check(
        len(todo), args.setup, llm.model, history, datetime.now(UTC), args.daily_token_limit
    )
    print(message)
    if not fits and not args.ignore_budget:
        sys.exit("not enough token budget left today; run fewer notes (--limit) or wait")
    _start_run(run_dir, meta)

    engine = get_engine()
    embedder = get_embedder() if args.setup == "pipeline" else None

    def predict(gold: GoldNote) -> NoteRun:
        with Session(engine) as session:
            if embedder is not None:
                run = predict_pipeline(session, llm, embedder, gold, args.extract_prompt)
            else:
                run = predict_baseline(session, llm, gold)
        return run.model_copy(update={"usage": ledger.take()})

    run_notes(golds, predict, run_dir)
    return run_dir


def main(default_setup: str | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", choices=["pipeline", "baseline"], default=default_setup)
    parser.add_argument("--limit", type=int, default=None, help="first N gold notes")
    parser.add_argument("--model", help="overrides LLM_MODEL for this run only")
    parser.add_argument("--run-id", help="default: <date>-<setup>-<model>")
    parser.add_argument("--interval", type=float, default=DEFAULT_CALL_INTERVAL_S)
    parser.add_argument("--extract-prompt", default=EXTRACT_PROMPT, help="pipeline only")
    parser.add_argument("--replay-of", help="rerun rules on this run's saved LLM outputs")
    parser.add_argument("--daily-token-limit", type=int, default=budget.DAILY_TOKEN_LIMIT)
    parser.add_argument("--ignore-budget", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.replay_of:
        run_dir = _replay(args.replay_of, args.run_id, args.limit)
    else:
        if args.setup is None:
            parser.error("--setup is required")
        run_dir = _live(args)
    write_report(run_dir)
    meta, summary = score_run(run_dir, args.limit)
    print(markdown(meta, summary))


if __name__ == "__main__":
    main()
