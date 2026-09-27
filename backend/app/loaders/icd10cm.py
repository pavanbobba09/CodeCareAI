"""Parse and load a CMS ICD-10-CM release (order file, tabular XML, index XML).

Sources are the public CMS files listed in `RELEASES`. Raw downloads live in
`data/raw/` and are never committed.
"""

import io
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import ARRAY, String, all_, bindparam, case, delete, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Code, CodeSet, IndexTerm

CMS_BASE = "https://www.cms.gov/files/zip/"


@dataclass(frozen=True)
class Release:
    fy: int
    valid_from: date
    valid_to: date
    order_zip: str  # contains icd10cm_order_{fy}.txt
    tables_zip: str  # contains icd10cm_tabular_{fy}.xml and icd10cm_index_{fy}.xml

    @property
    def code_set_id(self) -> str:
        return f"ICD10CM-FY{self.fy}"


# CMS file names are not consistent across years, so each release is listed explicitly.
RELEASES: dict[int, Release] = {
    # FY2026 is loaded only as the April 1, 2026 update (owner decision, 2026-09-26).
    # The October 2025 release is not loaded, so visits before 2026-04-01 get
    # CODE_SET_MISSING.
    2026: Release(
        fy=2026,
        valid_from=date(2026, 4, 1),
        valid_to=date(2026, 9, 30),
        order_zip="april-1-2026-code-descriptions-tabular-order.zip",
        tables_zip="april-1-2026-code-tables-tabular-index.zip",
    ),
    2027: Release(
        fy=2027,
        valid_from=date(2026, 10, 1),
        valid_to=date(2027, 9, 30),
        order_zip="2027-code-descriptions-tabular-order.zip",
        tables_zip="2027-code-tables-tabular-index.zip",
    ),
}

# Tabular XML note tags -> keys stored in codes.tabular_notes.
NOTE_TAGS = {
    "excludes1": "excludes1",
    "excludes2": "excludes2",
    "useAdditionalCode": "use_additional",
    "codeFirst": "code_first",
    "codeAlso": "code_also",
    "inclusionTerm": "inclusion",
}


@dataclass(frozen=True)
class OrderRow:
    code: str  # dotted, e.g. E11.22
    billable: bool
    description: str  # long description


@dataclass(frozen=True)
class IndexRow:
    term: str  # path as one phrase without nonessential modifiers; trigram search text
    path: str  # "Main term (nemod) > subterm > ...", for display
    code: str  # dotted, trailing "-" removed


def dot(raw: str) -> str:
    """CMS order files drop the dot: E1122 -> E11.22."""
    return raw if len(raw) <= 3 else f"{raw[:3]}.{raw[3:]}"


def normalize_index_code(code: str) -> str:
    """Index codes may end in '-' or '.-' meaning 'more characters needed'."""
    return code.strip().rstrip("-").rstrip(".")


def parse_order_file(lines: Iterator[str]) -> list[OrderRow]:
    """Fixed-width layout from icd10OrderFiles.pdf: code 7-13, billable 15, long title 78+."""
    rows = []
    for line in lines:
        line = line.rstrip("\r\n")
        if len(line) < 78:
            continue
        rows.append(
            OrderRow(
                code=dot(line[6:13].strip()),
                billable=line[14] == "1",
                description=line[77:].strip(),
            )
        )
    return rows


def parent_codes(codes: list[str]) -> dict[str, str | None]:
    """Parent = longest proper prefix that is itself a code (E11.22 -> E11.2 -> E11)."""
    raw = {c.replace(".", "") for c in codes}
    parents: dict[str, str | None] = {}
    for code in codes:
        r = code.replace(".", "")
        parents[code] = next((dot(r[:i]) for i in range(len(r) - 1, 2, -1) if r[:i] in raw), None)
    return parents


def _text(el: ET.Element) -> str:
    return " ".join(" ".join(el.itertext()).split())


def _core_text(title: ET.Element) -> str:
    """Title without nonessential modifiers: they dilute trigram similarity."""
    parts = [title.text or ""]
    for child in title:
        if child.tag != "nemod":
            parts.append(_text(child))
        parts.append(child.tail or "")
    return " ".join(" ".join(parts).split())


def parse_tabular(root: ET.Element) -> dict[str, dict[str, list[str]]]:
    """Map code -> tabular notes declared directly on that code."""
    notes: dict[str, dict[str, list[str]]] = {}
    for diag in root.iter("diag"):
        name = diag.findtext("name")
        if not name:
            continue
        found: dict[str, list[str]] = {}
        for tag, key in NOTE_TAGS.items():
            for block in diag.findall(tag):
                found.setdefault(key, []).extend(_text(n) for n in block.findall("note"))
        if found:
            notes[name.strip()] = found
    return notes


def parse_index(root: ET.Element) -> list[IndexRow]:
    """Flatten the Alphabetic Index into one row per (term path, code)."""
    rows: list[IndexRow] = []

    def walk(node: ET.Element, core: list[str], full: list[str]) -> None:
        title = node.find("title")
        # CMS wraps some subterms in a "Note: ..." pseudo-heading; it is guidance, not a term.
        if title is not None and not _text(title).startswith("Note:"):
            core, full = [*core, _core_text(title)], [*full, _text(title)]
        for code_el in node.findall("code"):
            if code_el.text and (code := normalize_index_code(code_el.text)):
                rows.append(IndexRow(term=" ".join(core), path=" > ".join(full), code=code))
        for child in node.findall("term"):
            walk(child, core, full)

    for main in root.iter("mainTerm"):
        walk(main, [], [])
    return rows


@dataclass(frozen=True)
class ParsedRelease:
    codes: list[OrderRow]
    parents: dict[str, str | None]
    notes: dict[str, dict[str, list[str]]]
    index: list[IndexRow]


def download(release: Release, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name in (release.order_zip, release.tables_zip):
        target = raw_dir / name
        if not target.exists():
            urllib.request.urlretrieve(CMS_BASE + name, target)


def _member(zf: zipfile.ZipFile, suffix: str) -> bytes:
    matches = [n for n in zf.namelist() if n.endswith(suffix)]
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one '{suffix}' in {zf.filename}, found {matches}")
    return zf.read(matches[0])


def parse_release(release: Release, raw_dir: Path) -> ParsedRelease:
    fy = release.fy
    with zipfile.ZipFile(raw_dir / release.order_zip) as zf:
        order_text = _member(zf, f"icd10cm_order_{fy}.txt").decode("latin-1")
    with zipfile.ZipFile(raw_dir / release.tables_zip) as zf:
        tabular = ET.parse(io.BytesIO(_member(zf, f"icd10cm_tabular_{fy}.xml"))).getroot()
        index = ET.parse(io.BytesIO(_member(zf, f"icd10cm_index_{fy}.xml"))).getroot()

    return parse_sources(order_text, tabular, index)


def parse_sources(order_text: str, tabular: ET.Element, index: ET.Element) -> ParsedRelease:
    codes = parse_order_file(iter(order_text.splitlines()))
    known = {c.code for c in codes}
    return ParsedRelease(
        codes=codes,
        parents=parent_codes([c.code for c in codes]),
        notes=parse_tabular(tabular),
        index=[r for r in parse_index(index) if r.code in known],
    )


def _chunks(rows: list[dict[str, Any]], size: int = 5000) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def store_release(session: Session, release: Release, parsed: ParsedRelease) -> None:
    """Replace one code set's codes and index terms in a single transaction.

    Codes are upserted, not deleted, so an unchanged description keeps its embedding
    and a rerun does not force re-embedding the whole release.
    """
    cs_id = release.code_set_id
    session.execute(
        pg_insert(CodeSet)
        .values(
            id=cs_id,
            system="ICD-10-CM",
            valid_from=release.valid_from,
            valid_to=release.valid_to,
            source_url=CMS_BASE + release.order_zip,
        )
        .on_conflict_do_update(
            index_elements=[CodeSet.id],
            set_={"valid_from": release.valid_from, "valid_to": release.valid_to},
        )
    )
    session.execute(delete(IndexTerm).where(IndexTerm.code_set_id == cs_id))

    code_rows = [
        {
            "code_set_id": cs_id,
            "code": c.code,
            "description": c.description,
            "billable": c.billable,
            "parent_code": parsed.parents[c.code],
            "tabular_notes": parsed.notes.get(c.code, {}),
        }
        for c in parsed.codes
    ]
    stmt = pg_insert(Code)
    upsert = stmt.on_conflict_do_update(
        index_elements=[Code.code_set_id, Code.code],
        set_={
            "description": stmt.excluded.description,
            "billable": stmt.excluded.billable,
            "parent_code": stmt.excluded.parent_code,
            "tabular_notes": stmt.excluded.tabular_notes,
            "embedding": case(
                (Code.description == stmt.excluded.description, Code.embedding), else_=None
            ),
        },
    )
    for chunk in _chunks(code_rows):
        session.execute(upsert, chunk)
    session.execute(
        delete(Code).where(
            Code.code_set_id == cs_id,
            # one array parameter: a 98k-item NOT IN exceeds the 65535 bind-parameter limit
            Code.code != all_(bindparam("keep", [c.code for c in parsed.codes], ARRAY(String))),
        )
    )

    index_rows = [
        {"code_set_id": cs_id, "term": r.term, "path": r.path, "code": r.code} for r in parsed.index
    ]
    for chunk in _chunks(index_rows):
        session.execute(insert(IndexTerm), chunk)
