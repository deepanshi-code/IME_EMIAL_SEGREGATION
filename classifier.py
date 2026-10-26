import re

MIN_SCORE = 3

EVIDENCE = {
    "TONNAGE": [
        (r"\bDWT\b", 3),
        (r"\bM/?V\b\s+[A-Z]", 2),
        (r"\bOPEN\s*(?:AT\s+|:\s*)?[A-Z][A-Z ,'-]*?\s+\d{1,2}\b", 2),
        (r"\bOPEN\s+(?:POSITION|TONNAGE)\b", 2),
    ],
    "CARGO VC": [
        (r"\b(?:LOAD(?:ING)?\s+PORT|POL)\b", 3),
        (r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISPORT|POD)\b", 3),
        (r"^\s*LOAD\s*:", 2),
        (r"\bEX\s+[A-Z]+\s+TO\s+[A-Z]+", 2),
        (r"\d[\d,]*\s*(?:MT|MTS|TONS)\b", 2),
        (r"\bLAYCAN\b", 1),
        (r"\b(?:SAFE PORT|SP)\b", 1),
    ],
    "CARGO TC": [
        (r"^\s*DEL(?:IVERY)?\b", 3),
        (r"^\s*REDEL(?:IVERY)?\b", 3),
        (r"\b(?:DURATION|PERIOD)\b.*\d+\s*(?:MONTHS?|DAYS)\b", 2),
        (r"\b(?:TCT|TC TRIP|ON PERIOD|PERIOD ENQUIRY)\b", 2),
    ],
}


def score_email(text):
    text = text.upper()
    scores = {}
    for category, rules in EVIDENCE.items():
        scores[category] = sum(
            weight for pattern, weight in rules if re.search(pattern, text, re.MULTILINE)
        )
    return scores


def classify_email(text):
    scores = score_email(text)
    category = max(scores, key=scores.get)
    if scores[category] < MIN_SCORE:
        return "UNKNOWN"
    return category
