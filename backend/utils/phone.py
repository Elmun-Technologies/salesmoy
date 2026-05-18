"""Phone number normalization for Uzbekistan (UZ) numbers.

Different systems (MoySklad, Sales Doctor, Telegram bot) format phones
differently — "+998 90 123 45 67", "998901234567", "90 123-45-67",
"(90) 123-45-67". This module gives a single canonical form.

Canonical form: digits only, with the +998 prefix.
Example: any of the above → "+998901234567"
"""

import re
from typing import Optional

# All non-digit chars (spaces, dashes, parens, plus, dots).
_NON_DIGIT = re.compile(r"\D+")


def normalize_phone(raw: Optional[str]) -> str:
    """Return phone in canonical "+998XXXXXXXXX" form, or "" if not parseable.

    Rules:
      - Strip every non-digit (spaces, dashes, parens, +, dots).
      - If the result starts with "998" and has 12 digits, return "+<digits>".
      - If the result has 9 digits (operator+number), prepend "+998".
      - If the result has 12 digits but starts with anything else, return raw
        digits prefixed with "+" (best effort — supports foreign numbers).
      - If empty or under 9 digits, return "".

    Examples:
        "+998 90 123 45 67"   → "+998901234567"
        "998901234567"        → "+998901234567"
        "90 123-45-67"        →  "+998901234567"
        "(90) 1234567"        →  "+998901234567"
        "9012345"             →  "" (too short)
        ""                    →  ""
    """
    if not raw:
        return ""
    digits = _NON_DIGIT.sub("", str(raw))
    if not digits:
        return ""
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) >= 10:
        return f"+{digits}"
    return ""


def phones_match(a: Optional[str], b: Optional[str]) -> bool:
    """True if two raw phone strings refer to the same number after normalization."""
    na, nb = normalize_phone(a), normalize_phone(b)
    return bool(na) and na == nb
