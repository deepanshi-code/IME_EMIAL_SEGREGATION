import re

MIN_SCORE = 3
FLAGS = re.IGNORECASE | re.MULTILINE
NOT_DATE = (r"(?!(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY\b|JANUARY\b|FEBRUARY\b|MARCH\b|APRIL\b|MAY\b"
            r"|JUNE\b|JULY\b|AUGUST\b|SEPTEMBER\b|OCTOBER\b|NOVEMBER\b|DECEMBER\b)")

# Vessel particulars ("GRT / NRT", "HO/HA", "Grain / Bale") look like "X / Y" routes.
SPEC_WORDS = (r"\b(?:LOA|LBP|GRT|NRT|GT|NT|HO|HA|GRAIN|BALE|BOX|FLAG|CLASS|DRA(?:FT|UGHT)|HOLDS?|HATCH(?:ES)?"
              r"|BEAM|DEPTH|CRANES?|GRABS?|BUILT|BLT|GEN|GENERAL|SID|TWD|MPP|DWT|DWCC|CARGO|DECKER|MTS?|CBM"
              r"|CBFT|SIR|MADAM|DEAR|L/[CD]|SHEX|SHINC|FHEX|ATTN|DESK|CO2|IMO)\b")
ROUTE_WORD = r"(?!(?:or|o|and)\b)[^\W\d_][\w.'’]*"
ROUTE_SIDE = re.compile(r"(?:\d(?:-\d)?[ \t]*(?:S[BP]{1,3}P?)?[ \t]+)?(" + ROUTE_WORD + r"(?:[ \t]+" + ROUTE_WORD + r"){0,2})"
                        r"(?=$|[ \t]*(?:[(,+.]|[-–—]|\bor\b|\bo\b))", re.IGNORECASE)


def route_side(part):
    match = ROUTE_SIDE.match(part.strip())
    if not match or len(match.group(1)) < 3:
        return None
    return match.group(1)


def find_route_line(text):
    # Broker circulars put the route on a line of its own: "Kandla / Subic Bay", "Orlivka - Marmara",
    # "Misurata/1 Greece", "Galati (6,1 m) / Marghera".
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 70 or re.search(SPEC_WORDS, line, re.IGNORECASE):
            continue
        if "/" in line:
            parts = line.split("/", 1)
        elif re.search(r"[ \t][-–][ \t]|–", line):
            parts = re.split(r"[ \t]*–[ \t]*|[ \t]+-[ \t]+", line, maxsplit=1)
        elif "-" in line:
            parts = line.split("-", 1)
        else:
            continue
        load, discharge = route_side(parts[0]), route_side(parts[1])
        if load and discharge and load[0].isupper():
            return load, discharge
    return None, None


EVIDENCE = {
    "TONNAGE": [
        (r"\b(?:DWT|DEADWEIGHT)\b", 3),
        (r"\bM[./]?V\b\.?\s+[A-Z]", 2),
        (r"\bOPEN\s*(?:AT\s+|:\s*)?[A-Z][A-Z ,'-]*?\s+\d{1,2}\b", 2),
        (r"\b(?:OPEN|HOME|EXCLUSIVE|INHOUSE|OWNERS)\s+TONNAGES?\b|\b(?:OPEN|VESSEL)\s+POSITIONS?\b", 2),
        (r"\bDWCC\b", 2),
        # A vessel looking for cargo: "need named/rated cgo", "propose your firm cargoes", "pls pps suitable cargo".
        (r"\b(?:NEEDS?|SEEKING|PROPOSE|PPS)\b(?:(?!VESSEL|VSL|TONNAGE)[^\n]){0,30}?\b(?:CARGO|CARGOES|CGO)\b"
         r"|\b(?:RATED|NAMED)\b[ /&\w]{0,12}\b(?:CARGO|CARGOES|CGO)\b", 3),
    ],
    "CARGO VC": [
        (find_route_line, 2),
        # A cargo looking for a vessel: "looking vessel for", "need suitable vessel", "offer firm tonnage for".
        (r"\b(?:LOOKING|NEEDS?|REQUIRED?|PROVIDE)\b[^\n]{0,25}?\b(?:VESSEL|VSL|TONNAGE)\b"
         r"|\bOFFER\s+(?:FIRM\s+)?(?:VESSEL|VSL|TONNAGE)\b", 2),
        # A required size range is a cargo order ("Any Dwt 6-9,000", "12,000 - 17,000 dwt").
        (r"\bANY\s+DWT\b|\d[ \t]*[-–][ \t]*\d[\d,.]*[ \t]*K?[ \t]*(?:MT[ \t]*)?DWT\b", 2),
        # Laytime terms only appear in voyage charters.
        (r"\b(?:S?SHINC|S?SHEX|FSHEX|FHEX|SATSHEX|FSATHEX|PWWD|WWDS?|TTL[ \t]*DAYS|TTDAYS)\b"
         r"|\b\d[\d,.]*[ \t]*[XC][ \t]*/[ \t]*\d[\d,.]*[ \t]*[XC]\b", 2),
        (r"\b(?:LOAD(?:ING)?\s+PORT|(?-i:POL))\b", 3),
        (r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISPORT|(?-i:POD))\b", 3),
        (r"^\s*LOAD\s*:", 2),
        (r"\bEX\s+[A-Z]+\s+TO\s+[A-Z]+", 2),
        (r"\bFROM\s+" + NOT_DATE + r"(?-i:[A-Z][\w'\-]*(?:[ \t]+[A-Z][\w'\-]*)*)\s+TO\s+" + NOT_DATE + r"(?-i:[A-Z])", 2),
        (r"\d[\d,]*\s*K?\s*(?:MT|MTS|METRIC\s+TON(?:NE)?S|TONNES|TONS)\b", 2),
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
            weight for pattern, weight in rules
            if (any(pattern(text)) if callable(pattern) else re.search(pattern, text, FLAGS))
        )
    return scores


def classify_email(text):
    scores = score_email(text)
    category = max(scores, key=scores.get)
    if scores[category] < MIN_SCORE:
        return "UNKNOWN"
    return category
