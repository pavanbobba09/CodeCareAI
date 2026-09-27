import logging
from typing import Any

from app.models import CodeSystem, RuleInput, Suggestion
from app.pipeline.nodes import Node
from app.pipeline.state import PipelineDeps, PipelineState
from app.rules import run_all
from app.terminology.lookup import preload_lookup

log = logging.getLogger(__name__)


def _draft_suggestions(state: PipelineState) -> list[Suggestion]:
    """One suggestion per selected code, merging facts and evidence that share it."""
    info = {
        (cs.fact_id, c.code): (c.system, c.description)
        for cs in state.candidate_sets
        for c in cs.candidates
    }
    by_code: dict[str, Suggestion] = {}
    for sel in state.selections:
        assert sel.code is not None  # validate_selections drops null codes
        system, description = info[(sel.fact_id, sel.code)]
        existing = by_code.get(sel.code)
        if existing is None:
            by_code[sel.code] = Suggestion(
                suggestion_id=f"s{len(by_code) + 1}",
                code=sel.code,
                system=system,
                description=description,
                fact_ids=[sel.fact_id],
                evidence=sel.evidence,
                rule_results=[],
                gap_ids=[],
                confidence="review",
            )
        else:
            by_code[sel.code] = existing.model_copy(
                update={
                    "fact_ids": [*existing.fact_ids, sel.fact_id],
                    "evidence": sorted({*existing.evidence, *sel.evidence}),
                }
            )
    return list(by_code.values())


def make(deps: PipelineDeps) -> Node:
    def run_rules(state: PipelineState) -> dict[str, Any]:
        drafts = _draft_suggestions(state)
        wanted: dict[str, set[str]] = {}
        for s in drafts:
            system: CodeSystem = s.system
            code_set_id = state.code_sets.cpt if system == "CPT" else state.code_sets.icd10cm
            if code_set_id is not None:
                wanted.setdefault(code_set_id, set()).add(s.code)
        out = run_all(
            RuleInput(
                visit_date=state.note.visit_date,
                code_sets=state.code_sets,
                facts=state.facts,
                suggestions=drafts,
            ),
            preload_lookup(deps.session, wanted),
        )
        for d in out.dropped:
            log.warning(
                "%s dropped code %s for facts %s: %s", d.rule_id, d.code, d.fact_ids, d.reason
            )
        return {
            "suggestions": out.suggestions,
            "gaps": out.gaps,
            "model_errors": state.model_errors + len(out.dropped),
        }

    return run_rules
