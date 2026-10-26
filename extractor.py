import re

from classifier import NOT_DATE

FLAGS = re.IGNORECASE | re.MULTILINE

SEP = r"[ \t]*[:\-]?[ \t]*"
PLACE = r"([A-Z][A-Z' \-]*?[A-Z])"
PLACE_END = r"(?=[ \t]*(?:\d|[/,;:.()]|\b(?:PPT|SPOT|POL|POD|LAYCAN|LAYDAYS|CARGO|FRT|FREIGHT)\b|$))"
QUALIFIER = r"(?:(?:DOP|APS|PASSING|ON ARRIVAL|AT|IN)\s+)?"
SAFE_PORT = r"\d(?:-\d)?[ \t]*(?:SAFE[ \t]+PORTS?|SPS?|SBS?)[ \t]+"
NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[ \t]*K?)"
TITLE_PLACE = r"(?-i:([A-Z][\w'\-]*(?:[ \t]+(?:of[ \t]+)?[A-Z][\w'\-]*)*))"
ROUTE_SEP = r"[ \t]*(?:/|-+>|-|(?i:\bto\b))[ \t]*"
LOAD_LABEL = r"\b(?:LOAD(?:ING)?\s+PORT|(?-i:POL))\b"
DISCHARGE_LABEL = r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISPORT|(?-i:POD))\b"


def to_tonnes(raw):
    raw = raw.replace(",", "").replace(" ", "").upper()
    if raw.endswith("K"):
        return str(int(float(raw[:-1]) * 1000))
    return str(int(float(raw)))


def search(pattern, text):
    match = re.search(pattern, text, FLAGS)
    return match.group(1).strip() if match else None


def find_open_port(text):
    candidates = list(re.finditer(r"\bOPEN\b" + SEP + r"(?:AT\s+)?" + PLACE + PLACE_END, text, FLAGS))
    for match in candidates:
        rest = text[match.end():]
        if re.match(r"[ \t]+(?:\d|PPT\b|SPOT\b|PROMPT\b)", rest, re.IGNORECASE):
            return match.group(1)
    return candidates[0].group(1) if candidates else None


def find_labelled(label, text):
    # With a ":" or "-" separator any case is accepted; without one the place must be capitalised,
    # so prose like "expected load is around" is not read as a port.
    return (search(label + r"[ \t]*[:\-][ \t]*" + PLACE + PLACE_END, text)
            or search(label + r"[ \t]+(?=(?-i:[A-Z]))" + PLACE + PLACE_END, text))


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
    result = {}

    if category == "TONNAGE":
        vessel = search(r"\bM[./]?V\b\.?\s+" + PLACE + r"(?=\s*(?:[/,(]|\d|\bDWT\b|\bOPEN\b|$))", text)
        size = re.search(NUMBER + r"[ \t]*(?:MT[ \t]*)?DWT\b|\bDWT" + SEP + NUMBER, text, FLAGS)
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
        for find, source in ((find_route, body), (find_route, text), (find_subject_route, text)):
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
