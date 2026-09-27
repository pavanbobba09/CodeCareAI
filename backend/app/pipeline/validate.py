"""Checks on model output (DESIGN.md §4.4). Invalid items are dropped and counted."""

import logging

from app.models import CandidateSet, ClinicalFact, CodeSelection

log = logging.getLogger(__name__)


def _evidence_ok(evidence: list[int], valid: set[int]) -> bool:
    return bool(evidence) and all(n in valid for n in evidence)


def validate_facts(facts: list[ClinicalFact], valid: set[int]) -> tuple[list[ClinicalFact], int]:
    """Drop facts with missing/unknown evidence or duplicate ids; drop dangling links."""
    kept: list[ClinicalFact] = []
    errors = 0
    seen: set[str] = set()
    for fact in facts:
        if fact.fact_id in seen or not _evidence_ok(fact.evidence, valid):
            log.warning("dropped fact %s: bad evidence or duplicate id", fact.fact_id)
            errors += 1
            continue
        seen.add(fact.fact_id)
        kept.append(fact.model_copy(update={"evidence": sorted(set(fact.evidence))}))

    cleaned: list[ClinicalFact] = []
    for fact in kept:
        links = [link for link in fact.links if link.target_fact_id in seen]
        if len(links) != len(fact.links):
            log.warning(
                "dropped %d dangling link(s) on fact %s", len(fact.links) - len(links), fact.fact_id
            )
            errors += 1
        cleaned.append(fact.model_copy(update={"links": links}))
    return cleaned, errors


def validate_selections(
    selections: list[CodeSelection],
    candidate_sets: list[CandidateSet],
    fact_evidence: dict[str, set[int]],
) -> tuple[list[CodeSelection], int]:
    """Keep selections whose code is in that fact's candidates and whose evidence is a
    non-empty subset of that fact's evidence (a code can only cite what its fact cites)."""
    allowed = {cs.fact_id: {c.code for c in cs.candidates} for cs in candidate_sets}
    kept: list[CodeSelection] = []
    errors = 0
    seen: set[tuple[str, str]] = set()
    for sel in selections:
        if sel.code is None:
            continue  # the model found no fitting candidate; not an error
        if sel.fact_id not in allowed or sel.code not in allowed[sel.fact_id]:
            log.warning("dropped selection %s for fact %s: not a candidate", sel.code, sel.fact_id)
            errors += 1
            continue
        if not _evidence_ok(sel.evidence, fact_evidence.get(sel.fact_id, set())):
            log.warning(
                "dropped selection %s for fact %s: evidence %s not in the fact's evidence",
                sel.code,
                sel.fact_id,
                sel.evidence,
            )
            errors += 1
            continue
        key = (sel.fact_id, sel.code)
        if key in seen:
            continue
        seen.add(key)
        kept.append(sel.model_copy(update={"evidence": sorted(set(sel.evidence))}))
    return kept, errors
