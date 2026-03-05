"""Country extraction from article text using dictionary matching."""

import json
import re
from pathlib import Path

_data = json.loads((Path(__file__).parent / "country_data.json").read_text())
COUNTRY_TERMS: dict[str, str] = _data["terms"]
COUNTRY_NAMES: dict[str, str] = _data["names"]

# Pre-compile regex: longest terms first to match "South Korea" before "Korea"
_sorted_terms = sorted(COUNTRY_TERMS.keys(), key=len, reverse=True)
_pattern = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _sorted_terms) + r")\b",
    re.IGNORECASE,
)


def extract_countries(headline: str, summary: str = "") -> list[str]:
    """Extract deduplicated ISO alpha-3 country codes from headline + summary."""
    text = f"{headline} {summary}" if summary else headline
    matches = _pattern.findall(text)
    seen: set[str] = set()
    codes: list[str] = []
    for m in matches:
        code = COUNTRY_TERMS[m.lower()]
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes
