import re

from classifier import NOT_DATE, find_route_line, normalize_newlines

FLAGS = re.IGNORECASE | re.MULTILINE

SEP = r"[ \t]*[:@\-]?[ \t]*"
PLACE = r"([A-Z][A-Z' \-]*?[A-Z])"
PLACE_END = (r"(?=[ \t]*(?:\d|[/,;:.()|—]|[-–][ \t]|\b(?:PPT|SPOT|POL|POD|LAYCAN|LAYDAYS|CARGO|FRT|FREIGHT|OR|ON)\b"
             r"|\bPORT\b(?![ \t]+[A-Z])|$))")
QUALIFIER = r"(?:(?:DOP|APS|PASSING|ON ARRIVAL|AT|IN)\s+)?"
SAFE_PORT = r"\d(?:-\d)?[ \t]*(?:SAFE[ \t]+PORTS?|SPS?|SBS?)[ \t]+"
PORT_COUNT = r"(?:\d(?:-\d)?[ \t]*S[BP]{1,3}P?[ \t]+)?"
NUMBER = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?[ \t]*K?)"
TITLE_PLACE = r"(?-i:([A-Z][\w'\-]*(?:[ \t]+(?:of[ \t]+)?[A-Z][\w'\-]*)*))"
ROUTE_SEP = r"[ \t]*(?:/|-+>|-|(?i:\bto\b))[ \t]*"
LOAD_LABEL = r"\b(?:LOAD(?:ING)?\s+PORT|LD\.?\s+PORT|PORT\s+OF\s+LOADING|(?-i:POL))\b"
DISCHARGE_LABEL = r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISCH\.?\s+PORT|PORT\s+OF\s+DISCHARGE|DISPORT|(?-i:POD))\b"
NOT_OPEN_PORT = r"(?!(?:HATCH|HA|VESSEL|VSL|POSITIONS?|TONNAGES?|CARGO|CARGOES|TO|FOR|AROUND|ABOUT)\b)"


def to_tonnes(raw):
    raw = raw.replace(" ", "").upper()
    thousands = 1000 if raw.endswith("K") else 1
    raw = raw.rstrip("K")
    # The last "," or "." is a decimal mark unless exactly three digits follow it
    # ("7.331,1" -> 7331.1, "4299,59" -> 4299.59, "58,000" -> 58000, "63.5k" -> 63500).
    last = max(raw.rfind(","), raw.rfind("."))
    if last != -1 and len(raw) - last - 1 != 3:
        whole, fraction = raw[:last], raw[last + 1:]
    else:
        whole, fraction = raw, ""
    whole = whole.replace(",", "").replace(".", "")
    return str(int(float(f"{whole}.{fraction or 0}") * thousands))


def search(pattern, text):
    match = re.search(pattern, text, FLAGS)
    return match.group(1).strip() if match else None


def find_open_port(text):
    pattern = r"\bOPEN\b" + SEP + r"(?:(?:AT|IN)\s+)?" + NOT_OPEN_PORT + PLACE + PLACE_END
    candidates = list(re.finditer(pattern, text, FLAGS))
    for match in candidates:
        rest = text[match.end():]
        if re.match(r"[ \t]*(?:,|\bON\b)?[ \t]*(?:\d|PPT\b|SPOT\b|PROMPT\b)", rest, re.IGNORECASE):
            return match.group(1)
    return candidates[0].group(1) if candidates else None


def find_labelled(label, text):
    # With a ":" or "-" separator any case is accepted; without one the place must be capitalised,
    # so prose like "expected load is around" is not read as a port.
    return (search(label + r"[ \t]*[:\-][ \t]*" + PORT_COUNT + PLACE + PLACE_END, text)
            or search(label + r"[ \t]+" + PORT_COUNT + r"(?=(?-i:[A-Z]))" + PLACE + PLACE_END, text))


def trim_to_body(place, body):
    words = place.split()
    while words:
        candidate = " ".join(words)
        if re.search(r"\b" + re.escape(candidate) + r"\b", body, re.IGNORECASE):
            return candidate
        words = words[1:]
    return None


def find_subject_route(text):
    subject = re.search(r"^SUBJECT:[ \t]*(.*)$", text, FLAGS)
    if not subject:
        return None, None
    body = text[subject.end():]
    for segment in re.split(r"[ \t]+-[ \t]+|:[ \t]*|[ \t]*\|[ \t]*|,[ \t]*", subject.group(1)):
        segment = re.sub(r"^\d[\d,.]*\s*\w*\s+", "", segment.strip())
        match = re.fullmatch(TITLE_PLACE + ROUTE_SEP + TITLE_PLACE, segment)
        if match:
            load, discharge = trim_to_body(match.group(1), body), trim_to_body(match.group(2), body)
            if load and discharge:
                return load, discharge
    return None, None


def find_route(text):
    patterns = [
        r"\bEX\s+" + PLACE + r"\s+TO\s+" + PLACE + PLACE_END,
        SAFE_PORT + PLACE + r"\s+TO\s+" + SAFE_PORT + PLACE + PLACE_END,
        r"\bFROM\s+" + NOT_DATE + TITLE_PLACE + r"\s+TO\s+" + NOT_DATE + TITLE_PLACE,
    ]
    for pattern in patterns:
        match = re.search(pattern, text, FLAGS)
        if match:
            return match.group(1), match.group(2)
    return None, None


def extract_data(text, category):
    text = normalize_newlines(text)
    result = {}

    if category == "TONNAGE":
        # A short trailing number is part of the name ("YONGSHENG 151", "TBN 1"); a long one is the size.
        vessel = search(r"\bM[./]?V\b\.?\s+(" + PLACE[1:-1] + r"(?:[ \t]+\d{1,3}\b(?![\d,.]|[ \t]*K\b))?)"
                        r"(?=\s*(?:[/,(:;|]|[-–—]|\d|\bDWT\b|\bDWCC\b|\bOPEN\b|\bSPOT\b|\bBLT\b|$))", text)
        size = re.search(NUMBER + r"[ \t]*(?:MTS?[ \t]*)?DWT\b|\b(?:DWT|DEADWEIGHT)\b[^\d\n]{0,20}?" + NUMBER,
                         text, FLAGS)
        port = find_open_port(text)

        if vessel:
            result["Vessel Name"] = vessel
        if port:
            result["Open Port"] = port
        if size:
            result["Vessel Size"] = to_tonnes(size.group(1) or size.group(2))

    elif category == "CARGO VC":
        load = find_labelled(LOAD_LABEL, text) or search(r"^[ \t]*LOAD[ \t]*:[ \t]*" + PLACE + PLACE_END, text)
        discharge = find_labelled(DISCHARGE_LABEL, text)
        body = re.sub(r"^SUBJECT:.*$", "", text, count=1, flags=FLAGS)
        routes = ((find_route_line, body), (find_route, body), (find_route, text), (find_subject_route, text))
        for find, source in routes:
            if load and discharge:
                break
            route_load, route_discharge = find(source)
            load = load or route_load
            discharge = discharge or route_discharge

        if load:
            result["Loading Port"] = load
        if discharge:
            result["Discharge Port"] = discharge

    elif category == "CARGO TC":
        delivery = search(r"^[ \t]*DEL(?:IVERY)?\b" + SEP + QUALIFIER + PLACE + PLACE_END, text)
        redelivery = search(r"^[ \t]*REDEL(?:IVERY)?\b" + SEP + QUALIFIER + PLACE + PLACE_END, text)
        duration = search(r"^[ \t]*(?:DURATION|PERIOD)\b" + SEP + r"(.*\d.*\b(?:MONTHS?|DAYS?|YEARS?)\b.*?)[ \t.]*$", text)

        if delivery:
            result["Delivery Port"] = delivery
        if redelivery:
            result["Redelivery Port"] = redelivery
        if duration:
            result["Duration"] = duration

    return result
