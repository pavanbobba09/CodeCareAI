"""Code references inside Tabular notes, e.g. "type 1 diabetes mellitus (E10.-)".

A reference is a code ("P70.2"), a category written with a dash ("E10.-", "I50.4-"), or a
range ("O10-O11"). References are kept as patterns and matched against dotted codes.
"""

import re

_CODE = r"[A-Z]\d[0-9A-Z](?:\.[0-9A-Z]{1,4})?"
_REF = re.compile(rf"^({_CODE})(?:\.?-)?(?:\s*-\s*({_CODE})(?:\.?-)?)?$")
_PARENS = re.compile(r"\(([^()]*)\)")


def code_refs(note: str) -> list[str]:
    """Patterns referenced by one note: "E10", "P70.2", "O10-O11"."""
    refs: list[str] = []
    for group in _PARENS.findall(note):
        for token in group.split(","):
            m = _REF.match(token.strip())
            if m:
                refs.append(m[1] if m[2] is None else f"{m[1]}-{m[2]}")
    return refs


def _flat(code: str) -> str:
    return code.replace(".", "")


def matches(pattern: str, code: str) -> bool:
    """True when code falls under the pattern (a code, its category, or a range)."""
    c = _flat(code)
    if "-" in pattern:
        lo, hi = (_flat(p) for p in pattern.split("-"))
        return lo <= c[: len(lo)] and c[: len(hi)] <= hi
    return c.startswith(_flat(pattern))
