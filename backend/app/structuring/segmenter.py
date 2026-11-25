import re
from typing import List, Dict, Any

# Pattern matching boundaries where an organ, finding, negation, or correction starts after a delimiter
SPLIT_TRIGGERS = [
    r"correction",
    r"sorry",
    r"scratch\s+that",
    r"replace\s+with",
    r"make\s+that",
    r"no\s+",
    r"not\s+",
    r"normal\s+",
    r"possible\s+",
    r"cannot\s+",
    r"liver",
    r"hepatic",
    r"gall\s*bladder",
    r"gallstones?",
    r"gb",
    r"cbd",
    r"common\s+bile\s+duct",
    r"pancreas",
    r"retroperitoneum",
    r"retroperitoneal",
    r"aorta",
    r"spleen",
    r"splenic",
    r"right\s+kidney",
    r"left\s+kidney",
    r"both\s+kidneys",
    r"kidneys",
    r"hydronephrosis",
    r"pericholecystic",
    r"urinary\s+bladder",
    r"bladder",
    r"prostate",
    r"uterus",
    r"endometrium",
    r"right\s+ovary",
    r"left\s+ovary",
    r"both\s+ovaries",
    r"ovaries",
    r"bowel",
    r"free\s+fluid",
    r"impression"
]

TRIGGER_GROUP = "|".join(SPLIT_TRIGGERS)

BOUNDARY_REGEX = re.compile(
    rf"(?:(?<!\d)[.!?;\n]+(?!\d)|,\s*(?=(?:{TRIGGER_GROUP})\b)|\b(?:and)\b\s*(?=(?:{TRIGGER_GROUP})\b))",
    re.IGNORECASE
)

STANDALONE_CORRECTION_REGEX = re.compile(
    r"^(?:correction|sorry|scratch\s+that|replace\s+with|make\s+that)$",
    re.IGNORECASE
)

def segment_transcript(transcript: str) -> List[Dict[str, Any]]:
    """
    Segments a raw transcript into discrete clinical clauses while:
    1. Preserving decimal numbers (e.g. 10.2 cm, 7.2 x 3.5 x 4.1 cm).
    2. Splitting on periods, semicolons, newlines.
    3. Splitting on commas or 'and' when followed by an organ trigger, negation, or correction.
    4. Merging standalone correction triggers (e.g. 'correction', 'sorry') with the next clause.
    5. Tracking exact char_start and char_end offsets in the original text.
    """
    if not transcript or not transcript.strip():
        return []

    cleaned = transcript.strip()
    segments = []
    last_idx = 0

    for match in BOUNDARY_REGEX.finditer(cleaned):
        start, end = match.span()
        clause_text = cleaned[last_idx:start].strip()
        if clause_text:
            segments.append({
                "text": clause_text,
                "char_start": last_idx,
                "char_end": start
            })
        last_idx = end

    if last_idx < len(cleaned):
        tail_text = cleaned[last_idx:].strip()
        if tail_text:
            segments.append({
                "text": tail_text,
                "char_start": last_idx,
                "char_end": len(cleaned)
            })

    if not segments and cleaned:
        segments.append({
            "text": cleaned,
            "char_start": 0,
            "char_end": len(cleaned)
        })

    # Clean punctuation
    cleaned_segments = []
    for s in segments:
        clean_s = s["text"].strip(",;.- \t\n")
        if clean_s and any(c.isalnum() for c in clean_s):
            s["text"] = clean_s
            cleaned_segments.append(s)

    # Merge standalone correction trigger with the next clause
    merged_segments = []
    i = 0
    while i < len(cleaned_segments):
        curr = cleaned_segments[i]
        if STANDALONE_CORRECTION_REGEX.match(curr["text"]) and (i + 1 < len(cleaned_segments)):
            next_seg = cleaned_segments[i + 1]
            merged_segments.append({
                "text": f"{curr['text']}: {next_seg['text']}",
                "char_start": curr["char_start"],
                "char_end": next_seg["char_end"]
            })
            i += 2
        else:
            merged_segments.append(curr)
            i += 1

    return merged_segments
