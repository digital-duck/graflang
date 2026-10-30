"""A small, deterministic PII detector, so a policy can ask `has_pii(@in_document)` and mean it.

It finds what has a recognisable shape: email addresses, phone numbers, US social security numbers, payment card numbers (checked
with the Luhn rule), and IBANs. It does not find names, addresses or anything that needs understanding the text; a clean answer
means "none of these shapes", not "no personal data". Use an LLM node (see `cookbook/compliance_audit`) when that matters.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Tuple

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w.])(?:\+\d{1,3}[ .-]?)?(?:\(\d{2,4}\)[ .-]?|\d{2,4}[ .-])\d{3,4}[ .-]\d{3,4}(?!\w)")
SSN = re.compile(r"(?<!\d)(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def find_pii(value: Any) -> List[Tuple[str, str]]:
    """[(kind, text found)] for a string, or for any JSON-like value (looked at as text)."""
    text = _text(value)
    found = [("email", m.group()) for m in EMAIL.finditer(text)]
    found += [("ssn", m.group()) for m in SSN.finditer(text)]
    found += [("card", m.group()) for m in CARD.finditer(text) if 13 <= len(re.sub(r"\D", "", m.group())) <= 19 and _luhn(re.sub(r"\D", "", m.group()))]
    found += [("iban", m.group()) for m in IBAN.finditer(text)]
    taken = [m for _, m in found]
    long_numbers = [m.span() for m in CARD.finditer(text)]              # a long digit run is a card or an id, not a phone number
    found += [("phone", m.group()) for m in PHONE.finditer(text)
              if 9 <= len(re.sub(r"\D", "", m.group())) <= 15 and not any(m.group() in t or t in m.group() for t in taken)
              and not any(a <= m.start() and m.end() <= b for a, b in long_numbers if len(re.sub(r"\D", "", text[a:b])) >= 13)]
    return found


def has_pii(value: Any) -> bool:
    return bool(find_pii(value))
