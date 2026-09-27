"""Split a note into sections and numbered sentences with exact character offsets.

Invariant: for every Sentence s, note_text[s.start:s.end] == s.text.
"""

import re
from itertools import pairwise

from app.models import Sentence

DEFAULT_SECTION = "note"

# Header text (lowercased, spaces collapsed) -> normalized section name.
SECTION_HEADERS: dict[str, str] = {
    "cc": "chief_complaint",
    "chief complaint": "chief_complaint",
    "hpi": "hpi",
    "history of present illness": "hpi",
    "pmh": "pmh",
    "past medical history": "pmh",
    "medications": "medications",
    "meds": "medications",
    "current medications": "medications",
    "allergies": "allergies",
    "ros": "ros",
    "review of systems": "ros",
    "exam": "exam",
    "pe": "exam",
    "physical exam": "exam",
    "labs": "results",
    "results": "results",
    "data": "results",
    "assessment": "assessment",
    "impression": "assessment",
    "plan": "plan",
    "a/p": "assessment_plan",
    "assessment/plan": "assessment_plan",
    "assessment and plan": "assessment_plan",
}

_HEADER = re.compile(r"^\s*(?P<name>[A-Za-z][A-Za-z /]{0,40}?)\s*:")
_BULLET = re.compile(r"[-*•]\s+")
# A sentence ends at . ! or ? followed by whitespace and a letter, digit, quote, or "(".
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Za-z0-9\"(])")
# Words that end in a period without ending the sentence.
_NO_SPLIT_BEFORE = {"dr", "mr", "mrs", "ms", "vs", "e.g", "i.e", "approx", "no", "st", "pt"}


def _section_for(line: str) -> tuple[str | None, int]:
    """Return (section, content offset in line) if the line starts with a known header."""
    match = _HEADER.match(line)
    if match:
        name = " ".join(match.group("name").lower().split())
        if name in SECTION_HEADERS:
            return SECTION_HEADERS[name], match.end()
    return None, 0


def _split_points(text: str) -> list[int]:
    """Offsets in `text` where a new sentence starts (after sentence-ending whitespace)."""
    points = []
    for match in _BOUNDARY.finditer(text):
        before = text[: match.start()].rsplit(None, 1)
        last_word = before[-1].rstrip(".!?").lower() if before else ""
        if last_word in _NO_SPLIT_BEFORE:
            continue
        points.append(match.end())
    return points


def segment_note(text: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    section = DEFAULT_SECTION
    offset = 0
    for line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(line)

        header, content_at = _section_for(line)
        if header is not None:
            section = header
        content = line[content_at:]
        base = line_start + content_at

        bounds = [0, *_split_points(content), len(content)]
        for lo, hi in pairwise(bounds):
            piece = content[lo:hi]
            stripped = piece.strip()
            bullet = _BULLET.match(stripped)
            if bullet:
                stripped = stripped[bullet.end() :]
            if not stripped:
                continue
            start = base + lo + piece.index(stripped)
            sentences.append(
                Sentence(
                    n=len(sentences) + 1,
                    section=section,
                    text=stripped,
                    start=start,
                    end=start + len(stripped),
                )
            )
    return sentences
