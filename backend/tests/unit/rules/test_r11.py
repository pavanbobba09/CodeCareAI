from app.rules import r11_uncertain_diagnosis
from tests.unit.rules.helpers import by_code, fact, outcomes, run, sug


def test_suspected_only_is_kept_as_not_suggested() -> None:
    out = run(
        r11_uncertain_diagnosis.apply,
        [sug("s1", "I50.9", ["f1"])],
        [fact("f1", "heart failure", [1], status="suspected")],
    )

    assert outcomes(by_code(out, "I50.9"), "R11") == ["fail"]


def test_confirmed_condition_is_untouched() -> None:
    out = run(
        r11_uncertain_diagnosis.apply, [sug("s1", "I10", ["f1"])], [fact("f1", "hypertension", [1])]
    )

    assert by_code(out, "I10").rule_results == []


def test_one_confirmed_fact_is_enough() -> None:
    facts = [fact("f1", "heart failure", [1], status="suspected"), fact("f2", "heart failure", [2])]
    out = run(r11_uncertain_diagnosis.apply, [sug("s1", "I50.9", ["f1", "f2"])], facts)

    assert by_code(out, "I50.9").rule_results == []


def test_rule_boundary_ignores_unrelated_active_fact_on_suspected_diagnosis() -> None:
    facts = [
        fact("f1", "heart failure", [1], status="suspected"),
        fact("f2", "hypertension", [2]),
    ]
    out = run(r11_uncertain_diagnosis.apply, [sug("s1", "I50.9", ["f1", "f2"])], facts)

    assert outcomes(by_code(out, "I50.9"), "R11") == ["fail"]
