import re

FLAGS = re.IGNORECASE | re.MULTILINE

SEP = r"[ \t]*[:\-]?[ \t]*"
PLACE = r"([A-Z][A-Z' \-]*?[A-Z])"
PLACE_END = r"(?=[ \t]*(?:\d|[/,;:.()]|\b(?:PPT|SPOT|POL|POD|LAYCAN|LAYDAYS|CARGO|FRT|FREIGHT)\b|$))"
QUALIFIER = r"(?:(?:DOP|APS|PASSING|ON ARRIVAL|AT|IN)\s+)?"
SAFE_PORT = r"\d(?:-\d)?[ \t]*(?:SAFE[ \t]+PORTS?|SPS?|SBS?)[ \t]+"
NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?[ \t]*K?)"


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


def find_route(text):
    patterns = [
        r"\bEX\s+" + PLACE + r"\s+TO\s+" + PLACE + PLACE_END,
        SAFE_PORT + PLACE + r"\s+TO\s+" + SAFE_PORT + PLACE + PLACE_END,
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
        load = search(r"\b(?:LOAD(?:ING)?\s+PORT|POL|LOAD)\b" + SEP + PLACE + PLACE_END, text)
        discharge = search(r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISPORT|POD)\b" + SEP + PLACE + PLACE_END, text)
        if not (load and discharge):
            route_load, route_discharge = find_route(text)
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
