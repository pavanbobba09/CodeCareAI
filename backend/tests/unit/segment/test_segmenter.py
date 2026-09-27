import pytest

from app.segment.segmenter import segment_note

WORKED_EXAMPLE = (
    "Assessment: Type 2 diabetes mellitus with chronic kidney disease stage 3.\n"
    "HPI: 62-year-old presents for diabetes and kidney follow-up. "
    "Denies chest pain or shortness of breath.\n"
    "Plan: Continue current regimen. Recheck renal function in 3 months.\n"
)


def _check_offsets(text: str) -> None:
    for s in segment_note(text):
        assert text[s.start : s.end] == s.text


def test_worked_example_numbers_sections_and_offsets() -> None:
    sentences = segment_note(WORKED_EXAMPLE)

    assert [(s.n, s.section, s.text) for s in sentences] == [
        (1, "assessment", "Type 2 diabetes mellitus with chronic kidney disease stage 3."),
        (2, "hpi", "62-year-old presents for diabetes and kidney follow-up."),
        (3, "hpi", "Denies chest pain or shortness of breath."),
        (4, "plan", "Continue current regimen."),
        (5, "plan", "Recheck renal function in 3 months."),
    ]
    _check_offsets(WORKED_EXAMPLE)


def test_text_before_any_header_uses_default_section() -> None:
    [s] = segment_note("Follow-up visit for blood pressure.")
    assert s.section == "note"


def test_header_alone_on_line_sets_section_for_following_lines() -> None:
    text = "Assessment and Plan:\nHypertension, controlled.\n"
    [s] = segment_note(text)
    assert (s.section, s.text) == ("assessment_plan", "Hypertension, controlled.")
    _check_offsets(text)


def test_unknown_colon_line_stays_in_current_section() -> None:
    text = "HPI: Here for follow-up.\nBP: 132/84 today.\n"
    sentences = segment_note(text)
    assert [(s.section, s.text) for s in sentences] == [
        ("hpi", "Here for follow-up."),
        ("hpi", "BP: 132/84 today."),
    ]


def test_decimals_and_abbreviations_do_not_split() -> None:
    text = "Labs: A1c 7.2 today vs. 7.8 prior per Dr. Lee. eGFR 52."
    assert [s.text for s in segment_note(text)] == [
        "A1c 7.2 today vs. 7.8 prior per Dr. Lee.",
        "eGFR 52.",
    ]
    _check_offsets(text)


def test_bullets_are_stripped_and_each_line_is_a_sentence() -> None:
    text = "Plan:\n- Continue metformin\n* Recheck BMP in 3 months\n"
    sentences = segment_note(text)
    assert [s.text for s in sentences] == ["Continue metformin", "Recheck BMP in 3 months"]
    _check_offsets(text)


@pytest.mark.parametrize(
    "text",
    ["", "\n\n  \n", "Plan:\n\n"],
)
def test_empty_content_gives_no_sentences(text: str) -> None:
    assert segment_note(text) == []


def test_crlf_offsets() -> None:
    text = "HPI: Here for review.\r\nPlan: Return in 1 month.\r\n"
    _check_offsets(text)
    assert [s.n for s in segment_note(text)] == [1, 2]
