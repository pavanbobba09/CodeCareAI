import xml.etree.ElementTree as ET
from pathlib import Path

from app.loaders.icd10cm import (
    dot,
    normalize_index_code,
    parent_codes,
    parse_index,
    parse_order_file,
    parse_sources,
    parse_tabular,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "icd10cm"


def test_dot_inserts_after_category() -> None:
    assert dot("E1122") == "E11.22"
    assert dot("I10") == "I10"
    assert dot("T360X1A") == "T36.0X1A"


def test_order_file_fixed_width() -> None:
    lines = (FIXTURES / "icd10cm_order_2027.txt").read_text().splitlines()
    rows = {r.code: r for r in parse_order_file(iter(lines))}

    assert rows["E11.22"].billable is True
    assert rows["E11.22"].description == (
        "Type 2 diabetes mellitus with diabetic chronic kidney disease"
    )
    assert rows["E11.2"].billable is False
    assert rows["N18.32"].description == "Chronic kidney disease, stage 3b"


def test_order_file_skips_short_lines() -> None:
    assert parse_order_file(iter(["", "junk"])) == []


def test_parent_is_longest_existing_prefix() -> None:
    parents = parent_codes(["E11", "E11.2", "E11.22", "I10", "T36.0X1", "T36.0X1A", "T36.0"])

    assert parents["E11.22"] == "E11.2"
    assert parents["E11.2"] == "E11"
    assert parents["E11"] is None
    assert parents["I10"] is None
    assert parents["T36.0X1A"] == "T36.0X1"


def test_parent_skips_missing_levels() -> None:
    assert parent_codes(["N18", "N18.32"])["N18.32"] == "N18"


def test_tabular_notes_stay_on_declaring_code() -> None:
    root = ET.parse(FIXTURES / "icd10cm_tabular_2027.xml").getroot()
    notes = parse_tabular(root)

    assert notes["E11"]["excludes1"] == ["type 1 diabetes mellitus (E10.-)"]
    assert notes["E11"]["use_additional"] == [
        "insulin (Z79.4)",
        "oral antidiabetic drugs (Z79.84)",
    ]
    assert notes["E11.22"] == {
        "use_additional": ["code to identify stage of chronic kidney disease (N18.1-N18.6)"]
    }
    assert "E11.2" not in notes


def test_index_flattens_paths_and_keeps_nemod() -> None:
    root = ET.parse(FIXTURES / "icd10cm_index_2027.xml").getroot()
    rows = parse_index(root)

    assert (
        "Diabetes, diabetic (mellitus) (sugar) > type 2 > with > chronic kidney disease",
        "E11.22",
    ) in [(r.path, r.code) for r in rows]
    stage_3b = next(r for r in rows if r.code == "N18.32")
    assert stage_3b.term == "Disease, diseased kidney chronic stage 3b"
    assert stage_3b.path == "Disease, diseased > kidney (functional) (pelvis) > chronic > stage 3b"


def test_index_code_dash_means_category() -> None:
    assert normalize_index_code("I50.-") == "I50"
    assert normalize_index_code("H93.29-") == "H93.29"
    assert normalize_index_code(" E11.9 ") == "E11.9"


def test_parse_sources_drops_index_codes_not_in_release() -> None:
    order = (FIXTURES / "icd10cm_order_2027.txt").read_text()
    index = ET.fromstring(
        "<i><mainTerm><title>Made up</title><code>Q99.99</code></mainTerm>"
        "<mainTerm><title>Hypertension</title><code>I10</code></mainTerm></i>"
    )
    parsed = parse_sources(order, ET.fromstring("<t/>"), index)

    assert [r.code for r in parsed.index] == ["I10"]


def test_note_headings_never_reach_index_text() -> None:
    root = ET.parse(FIXTURES / "icd10cm_index_2027.xml").getroot()
    rows = parse_index(root)

    assert rows, "fixture should produce index rows"
    assert not [r for r in rows if "Note:" in r.term or "Note:" in r.path]
    # The note heading follows "heart", so its subterms are heart's subterms.
    systolic = next(r for r in rows if r.code == "I50.20")
    assert systolic.term == "Failure, failed heart systolic"
    assert systolic.path == (
        "Failure, failed > heart (acute) (senile) (sudden) > "
        "systolic (congestive) (left ventricular)"
    )


SEE_INDEX = """<i>
<mainTerm><title>Diabetes, diabetic<nemod>(mellitus)</nemod></title><code>E11.9</code>
  <term level="1"><title>poorly controlled</title>
    <see>Diabetes, by type, with hyperglycemia</see></term>
  <term level="1"><title>type 1</title><code>E10.9</code>
    <term level="2"><title>with</title>
      <term level="3"><title>hyperglycemia</title><code>E10.65</code></term></term></term>
  <term level="1"><title>type 2</title><code>E11.9</code>
    <term level="2"><title>with</title>
      <term level="3"><title>hyperglycemia</title><code>E11.65</code></term></term></term>
</mainTerm>
<mainTerm><title>Failure, failed</title>
  <term level="1"><title>heart<nemod>(acute)</nemod></title><code>I50.9</code>
    <term level="2"><title>with</title>
      <term level="3"><title>reduced ejection fraction</title>
        <see>Failure, heart, systolic</see></term></term></term>
  <term level="1"><title>Note: guidance heading</title>
    <term level="2"><title>systolic<nemod>(congestive)</nemod></title><code>I50.20</code>
    </term></term>
</mainTerm>
<mainTerm><title>Oddity</title><see>Nowhere, at all</see></mainTerm>
</i>"""


def test_see_reference_takes_the_target_terms_codes() -> None:
    rows = parse_index(ET.fromstring(SEE_INDEX))
    poorly = [(r.code, r.path) for r in rows if r.term == "Diabetes, diabetic poorly controlled"]

    # "by type" matches every type subterm; "with hyperglycemia" walks "with" > "hyperglycemia".
    assert [c for c, _ in poorly] == ["E10.65", "E11.65"]
    assert poorly[1][1] == (
        "Diabetes, diabetic (mellitus) > poorly controlled "
        "(see Diabetes, by type, with hyperglycemia)"
    )


def test_see_reference_looks_through_note_headings() -> None:
    rows = parse_index(ET.fromstring(SEE_INDEX))
    term = "Failure, failed heart with reduced ejection fraction"
    hfref = [r.code for r in rows if r.term == term]

    assert hfref == ["I50.20"]


def test_unresolvable_see_reference_adds_no_rows() -> None:
    rows = parse_index(ET.fromstring(SEE_INDEX))

    assert not [r for r in rows if r.term == "Oddity"]
