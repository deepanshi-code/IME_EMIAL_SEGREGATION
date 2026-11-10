import re

MIN_SCORE = 3
FLAGS = re.IGNORECASE | re.MULTILINE
NOT_DATE = (r"(?!(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY\b|JANUARY\b|FEBRUARY\b|MARCH\b|APRIL\b|MAY\b"
            r"|JUNE\b|JULY\b|AUGUST\b|SEPTEMBER\b|OCTOBER\b|NOVEMBER\b|DECEMBER\b)")

# Vessel particulars ("GRT / NRT", "HO/HA", "Grain / Bale") look like "X / Y" routes.
SPEC_WORDS = (r"\b(?:LOA|LBP|GRT|NRT|GT|NT|HO|HA|GRAIN|BALE|BOX|FLAG|CLASS|DRA(?:FT|UGHT)|HOLDS?|HATCH(?:ES)?"
              r"|BEAM|DEPTH|CRANES?|GRABS?|BUILT|BLT|GEN|GENERAL|SID|TWD|MPP|DWT|DWCC|CARGO|DECKER|MTS?|CBM"
              r"|CBFT|SIR|MADAM|DEAR|L/[CD]|SHEX|SHINC|FHEX|ATTN|DESK|CO2|IMO|SPOT|PROMPT|PPT|TRY|ONW|ONWARDS"
              r"|DATES?)\b")
ROUTE_WORD = r"(?!(?:or|o|and)\b)[^\W\d_][\w.'’]*"
ROUTE_SIDE = re.compile(r"(?:\d(?:-\d)?[ \t]*(?:S[BP]{1,3}P?)?[ \t]+)?(" + ROUTE_WORD + r"(?:[ \t]+" + ROUTE_WORD + r"){0,2})"
                        r"(?=$|[ \t]*(?:[(,+.]|[-–—]|\bor\b|\bo\b))", re.IGNORECASE)


def route_side(part):
    match = ROUTE_SIDE.match(part.strip())
    if not match or len(match.group(1)) < 3:
        return None
    return match.group(1)


def route_lines(text):
    # Broker circulars put the route on a line of its own: "Kandla / Subic Bay", "Orlivka - Marmara",
    # "Misurata/1 Greece", "Galati (6,1 m) / Marghera". Returns (line index, load, discharge) for each.
    found = []
    for index, line in enumerate(text.splitlines()):
        line = line.strip()
        # Bracketed notes ("Abidjan / Norrsundet (draft 6,20m)") do not make a line vessel particulars.
        if not line or len(line) > 70 or re.search(SPEC_WORDS, re.sub(r"\([^)]*\)", "", line), re.IGNORECASE):
            continue
        if "/" in line:
            parts, hyphen = line.split("/", 1), False
        elif re.search(r"[ \t][-–][ \t]|–", line):
            parts, hyphen = re.split(r"[ \t]*–[ \t]*|[ \t]+-[ \t]+", line, maxsplit=1), True
        elif "-" in line:
            parts, hyphen = line.split("-", 1), True
        else:
            continue
        load, discharge = route_side(parts[0]), route_side(parts[1])
        # A hyphen also joins ordinary prose ("On Monday - member panel to ..."), so both sides of a
        # hyphenated route must be capitalised.
        if load and discharge and load[0].isupper() and (discharge[0].isupper() or not hyphen):
            found.append((index, load, discharge))
    return found


def find_route_line(text):
    found = route_lines(text)
    return found[0][1:] if found else (None, None)


EVIDENCE = {
    "TONNAGE": [
        (r"\b(?:DWT|DEADWEIGHT)(?![A-Z])", 3, "DWT / deadweight"),
        (r"\bM[./]?V\b(?:\.[ \t]*|[ \t]+)[A-Z]", 2, "vessel name (MV ...)"),
        (r"\bOPEN\s*(?:AT\s+|:\s*)?[A-Z][A-Z ,'-]*?\s+\d{1,2}\b", 2, "open port with a date"),
        (r"\b(?:OPEN|HOME|EXCLUSIVE|INHOUSE|OWNERS)\s+TONNAGES?\b|\b(?:OPEN|VESSEL)\s+POSITIONS?\b", 2, "open tonnage / vessel positions"),
        (r"\bDWCC\b", 2, "DWCC (cargo capacity)"),
        # A vessel looking for cargo: "need named/rated cgo", "propose your firm cargoes", "pls pps suitable cargo".
        (r"\b(?:NEEDS?|SEEKING|PROPOSE|PPS)\b(?:(?!VESSEL|VSL|TONNAGE)[^\n]){0,30}?\b(?:CARGO|CARGOES|CGO)\b"
         r"|\b(?:RATED|NAMED)\b[ /&\w]{0,12}\b(?:CARGO|CARGOES|CGO)\b", 3, "asks for cargo"),
        # Liner/MPP space offers: "MV DSX / loading: tianjin, shanghai / disport: jeddah".
        (r"^[ \t]*M[./]?V\b[^\n]*\n(?:[^\n]*\n){0,4}?[ \t]*loading[ \t]*:", 3, "liner vessel with loading ports"),
    ],
    "CARGO VC": [
        (find_route_line, 2, "route line (X / Y)"),
        # A cargo looking for a vessel: "looking vessel for", "need suitable vessel", "offer firm tonnage for".
        (r"\b(?:LOOKING|NEEDS?|REQUIRED?|PROVIDE)\b[^\n]{0,25}?\b(?:VESSEL|VSL|TONNAGE)\b"
         r"|\bOFFER\s+(?:FIRM\s+)?(?:VESSEL|VSL|TONNAGE)\b", 2, "asks for a vessel"),
        # A required size range is a cargo order ("Any Dwt 6-9,000", "12,000 - 17,000 dwt").
        (r"\bANY\s+DWT\b|\d[ \t]*[-–/][ \t]*\d[\d,.]*[ \t]*K?[ \t]*(?:MT[ \t]*)?DWT\b", 2, "required vessel size range"),
        # Laytime terms only appear in voyage charters.
        (r"\b(?:S?SHINC|S?SHEX|FSHEX|FHEX|SATSHEX|FSATHEX|PWWD|WWDS?|TTL[ \t]*DAYS|TTDAYS)\b"
         r"|\b\d[\d,.]*[ \t]*[XC][ \t]*/[ \t]*\d[\d,.]*[ \t]*[XC]\b", 2, "laytime terms (SHINC, 1000x/1000x)"),
        (r"\b(?:LOAD(?:ING)?\s+PORT|L/PORT|(?-i:POL))\b", 3, "load port"),
        (r"\b(?:DISCHARG(?:E|ING)\s+PORT|DI[SA]CH\w*\.?\s+PORT|D/PORT|DISPORT|(?-i:POD))\b", 3, "discharge port"),
        (r"^\s*LOAD\s*:", 2, "'Load:' label"),
        (r"\bEX\s+[A-Z][A-Z ]*?\s+TO\s+[A-Z]+", 2, "'ex X to Y' route"),
        (r"\bFROM\s+" + NOT_DATE + r"(?-i:[A-Z][\w'\-]*(?:[ \t]+[A-Z][\w'\-]*)*)\s+TO\s+" + NOT_DATE + r"(?-i:[A-Z])", 2, "'from X to Y' route"),
        (r"\d[\d,]*\s*K?\s*(?:MT|MTS|MTONS?|METRIC\s+TON(?:NE)?S|TONNES|TONS)\b", 2, "cargo quantity (MT)"),
        (r"(?:\bPER\s+(?:MT|METRIC\s+TON(?:NE)?|TON(?:NE)?)\b|\bPMT\b|/\s*MT\b)", 2, "freight per tonne"),
        (r"\b(?:FOB|CIF|CFR|FAS|DAP|DDP)\b", 1, "Incoterm (FOB, CIF...)"),
        (r"\b(?:FREIGHT|LUMP\s*SUM)\b", 1, "freight / lumpsum"),
        (r"\b(?:L/?D|LD[ \t]+RATES?|R/D[ \t]+RATE)\b[ \t]*:?[ \t]*\d", 2, "loading/discharge rates"),
        (r"\bLAYCAN\b", 1, "laycan"),
        (r"\b(?:SAFE PORT|SP)\b", 1, "safe port"),
    ],
    "CARGO TC": [
        (r"^\s*DEL(?:IVERY)?\b", 2, "delivery"),
        (r"^\s*REDEL(?:IVERY)?\b", 2, "redelivery"),
        (r"\b(?:DURATION|PERIOD)\b.*\d+\)?\s*(?:MONTHS?|DAYS|YEARS?)\b", 2, "duration / period"),
        (r"\b(?:TCT|TC TRIP|ON PERIOD|PERIOD ENQUIRY)\b", 2, "TCT / period enquiry"),
        # "Firm T/C Requirement", "quote your best Time Charter offers", "Charter Type: Time Charter".
        # A line offering "time charter OR voyage" is left to the other rules.
        (r"^(?![^\n]*\bVOYAGE\b)[^\n]*\b(?:T/C|TIME[ \t-]*CHARTER)\b[^\n]{0,30}?\b(?:REQUIREMENTS?|REQUESTS?|OFFERS?"
         r"|ENQUIRY|INQUIRY)\b|^[ \t]*CHARTER[ \t]+TYPE[ \t]*:[ \t]*(?:TC|T/C|TIME)\b", 3, "time-charter request"),
        (r"\bHIRE[ \t]+(?:IDEA|RATE)\b|\bPDPR\b|\bUSD[ \t]*[\d,.]+[ \t]*(?:PER[ \t]+DAY|/[ \t]*DAY|PD)\b"
         r"|\b[\d,.]+[ \t]*USD[ \t]+PER[ \t]+DAY\b", 2, "daily hire (USD per day)"),
    ],
}


def normalize_newlines(text):
    # Also drops markdown bold markers ("- **Load Port:** Tunis"), which hide labels from the rules.
    return re.sub(r"\*\*|__", "", text.replace("\r\n", "\n").replace("\r", "\n"))


def score_email(text):
    text = normalize_newlines(text)
    scores = {}
    for category, rules in EVIDENCE.items():
        scores[category] = sum(weight for _, weight, _ in matched_rules(rules, text))
    return scores


def matched_rules(rules, text):
    return [rule for rule in rules
            if (any(rule[0](text)) if callable(rule[0]) else re.search(rule[0], text, FLAGS))]


def evidence(text, category):
    # The plain-language labels of the rules that fired for one category, strongest first.
    text = normalize_newlines(text)
    rules = sorted(matched_rules(EVIDENCE.get(category, []), text), key=lambda rule: -rule[1])
    return [label for _, _, label in rules]


def classify_email(text):
    scores = score_email(text)
    category = max(scores, key=scores.get)
    if scores[category] < MIN_SCORE:
        return "UNKNOWN"
    return category
