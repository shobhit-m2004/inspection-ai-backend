import re
from typing import List

from app.services.chunking import chunk_text


RULE_LINE_RE = re.compile(r"^\s*(\d+[\.\)]|[a-zA-Z][\.\)]|[-*•])\s+")


def extract_rules(text: str) -> List[str]:
    """
    Deterministic SOP rule extraction.

    Strategy:
    1) Prefer numbered/bulleted lines as individual rules.
    2) Fallback to chunking when no clear rule lines are found.
    """
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rule_lines = [ln for ln in lines if RULE_LINE_RE.match(ln)]

    if rule_lines:
        # Normalize rule lines by removing the prefix marker
        rules = []
        for ln in rule_lines:
            normalized = RULE_LINE_RE.sub("", ln).strip()
            if normalized:
                rules.append(normalized)
        return rules

    # Fallback to chunking for unstructured text
    return chunk_text(text)
