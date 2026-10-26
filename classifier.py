import re

MIN_SCORE = 3
FLAGS = re.IGNORECASE | re.MULTILINE
NOT_DATE = (r"(?!(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY\b|JANUARY\b|FEBRUARY\b|MARCH\b|APRIL\b|MAY\b"
            r"|JUNE\b|JULY\b|AUGUST\b|SEPTEMBER\b|OCTOBER\b|NOVEMBER\b|DECEMBER\b)")

EVIDENCE = {
    "TONNAGE": [
        (r"\bDWT\b", 3),
        (r"\bM[./]?V\b\.?\s+[A-Z]", 2),
        (r"\bOPEN\s*(?:AT\s+|:\s*)?[A-Z][A-Z ,'-]*?\s+\d{1,2}\b", 2),
        (r"\bOPEN\s+(?:POSITION|TONNAGE)\b", 2),
    ],
    "CARGO VC": [
        (r"\b(?:LOAD(?:ING)?\s+PORT|(?-i:POL))\b", 3),
        (r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISPORT|(?-i:POD))\b", 3),
        (r"^\s*LOAD\s*:", 2),
        (r"\bEX\s+[A-Z]+\s+TO\s+[A-Z]+", 2),
        (r"\bFROM\s+" + NOT_DATE + r"(?-i:[A-Z][\w'\-]*(?:[ \t]+[A-Z][\w'\-]*)*)\s+TO\s+" + NOT_DATE + r"(?-i:[A-Z])", 2),
        (r"\d[\d,]*\s*(?:MT|MTS|METRIC\s+TON(?:NE)?S|TONNES|TONS)\b", 2),
        (r"(?:\bPER\s+(?:MT|METRIC\s+TON(?:NE)?|TON(?:NE)?)\b|\bPMT\b|/\s*MT\b)", 2),
        (r"\b(?:FOB|CIF|CFR|FAS|DAP|DDP)\b", 1),
        (r"\b(?:FREIGHT|LUMP\s*SUM)\b", 1),
        (r"\bLAYCAN\b", 1),
        (r"\b(?:SAFE PORT|SP)\b", 1),
    ],
    "CARGO TC": [
        (r"^\s*DEL(?:IVERY)?\b", 2),
        (r"^\s*REDEL(?:IVERY)?\b", 2),
        (r"\b(?:DURATION|PERIOD)\b.*\d+\s*(?:MONTHS?|DAYS)\b", 2),
        (r"\b(?:TCT|TC TRIP|ON PERIOD|PERIOD ENQUIRY)\b", 2),
    ],
}


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def score_email(text):
    text = normalize_newlines(text)
    scores = {}
    for category, rules in EVIDENCE.items():
        scores[category] = sum(
            weight for pattern, weight in rules if re.search(pattern, text, FLAGS)
        )
    return scores


def classify_email(text):
    scores = score_email(text)
    category = max(scores, key=scores.get)
    if scores[category] < MIN_SCORE:
        return "UNKNOWN"
    return category
