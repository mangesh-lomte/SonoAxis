import re
from typing import Optional, Tuple

REGEX_RIGHT = re.compile(r"\b(right|rt|right-sided)\b", re.IGNORECASE)
REGEX_LEFT = re.compile(r"\b(left|lt|left-sided)\b", re.IGNORECASE)
REGEX_BILATERAL = re.compile(r"\b(both|bilateral|bilaterally|either)\b", re.IGNORECASE)
REGEX_MIDLINE = re.compile(r"\b(midline|central)\b", re.IGNORECASE)

REGEX_NEGATION = re.compile(
    r"\b(no|not|neither|nor|without|absent|unremarkable|free\s+of|negative\s+for|no\s+definite|no\s+significant|non-visualized)\b",
    re.IGNORECASE
)

REGEX_UNCERTAINTY = re.compile(
    r"\b(possible|cannot\s+exclude|suspicious|equivocal|poorly\s+visualized|sub-?optimally|probable|questionable|cannot\s+rule\s+out)\b",
    re.IGNORECASE
)

def detect_laterality(text: str) -> Optional[str]:
    """
    Detects laterality in a clause: 'right', 'left', 'bilateral', or 'midline'.
    """
    has_right = bool(REGEX_RIGHT.search(text))
    has_left = bool(REGEX_LEFT.search(text))
    has_bilateral = bool(REGEX_BILATERAL.search(text))

    if has_bilateral or (has_right and has_left):
        return "bilateral"
    if has_right:
        return "right"
    if has_left:
        return "left"
    if REGEX_MIDLINE.search(text):
        return "midline"
    return None

def detect_negation(text: str) -> bool:
    """Detects if a finding statement is a negative observation."""
    return bool(REGEX_NEGATION.search(text))

def detect_uncertainty(text: str) -> bool:
    """Detects if a finding contains clinical uncertainty or qualifiers."""
    return bool(REGEX_UNCERTAINTY.search(text))
