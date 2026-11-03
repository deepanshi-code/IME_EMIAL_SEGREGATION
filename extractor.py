import re

from classifier import NOT_DATE, find_route_line, normalize_newlines, route_lines

FLAGS = re.IGNORECASE | re.MULTILINE

SEP = r"[ \t]*[:@\-]?[ \t]*"
PLACE = r"([A-Z][A-Z' \-]*?[A-Z])"
PLACE_END = (r"(?=[ \t]*(?:\d|[/,;:.()|—]|[-–][ \t]|\b(?:PPT|SPOT|POL|POD|LAYCAN|LAYDAYS|CARGO|FRT|FREIGHT|OR|ON"
             r"|JAN|FEB|MAR|APR|MAY|JUNE?|JULY?|AUG|SEPT?|OCT|NOV|DEC|EARLY|MID|END|BEG|PROMPT)\b"
             r"|\bPORT\b(?![ \t]+[A-Z])|$))")
QUALIFIER = r"(?:(?:DOP|APS|PASSING|ON ARRIVAL|AT|IN)\s+)?"
SAFE_PORT = r"\d(?:-\d)?[ \t]*(?:SAFE[ \t]+PORTS?|SPS?|SBS?)[ \t]+"
PORT_COUNT = r"(?:\d(?:-\d)?[ \t]*S[BP]{1,3}P?[ \t]+)?"
NUMBER = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?[ \t]*K?)"
TITLE_PLACE = r"(?-i:([A-Z][\w'\-]*(?:[ \t]+(?:of[ \t]+)?[A-Z][\w'\-]*)*))"
ROUTE_SEP = r"[ \t]*(?:/|-+>|-|(?i:\bto\b))[ \t]*"
LOAD_LABEL = r"\b(?:LOAD(?:ING)?\s+PORT|LD\.?\s+PORT|PORT\s+OF\s+LOADING|(?-i:POL))\b"
DISCHARGE_LABEL = r"\b(?:DISCHARG(?:E|ING)\s+PORT|DISCH\.?\s+PORT|PORT\s+OF\s+DISCHARGE|DISPORT|(?-i:POD))\b"
NOT_OPEN_PORT = (r"(?!(?:HATCH|HA|VESSEL|VSL|VESSELS|POSITIONS?|TONNAGES?|CARGO|CARGOES|TO|FOR|AROUND|ABOUT"
                 r"|HOME|OUR|OWNERS|DIRECT|CURRENT|EXCLUSIVE)\b)")

MONTH = (r"(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUNE?|JULY?|AUG(?:UST)?|SEPT?(?:EMBER)?"
         r"|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)\b\.?")
DAY = r"\d{1,2}(?:ST|ND|RD|TH)?"
DATE = (r"(?:" + DAY + r"(?:[ \t]*(?:[-–/_]|TO)[ \t]*" + DAY + r")?[ \t]*/?[ \t]*" + MONTH + r"(?:[ \t]*,?[ \t]*20\d\d)?"
        r"|" + MONTH + r"[ \t]+" + DAY + r"(?:[ \t]*[-–/][ \t]*" + DAY + r")?(?:[ \t]*,?[ \t]*20\d\d)?"
        r"|\b\d{1,2}[-–]\d{1,2}/\d{1,2}\b"
        r"|\b(?:EARLY|MID|END|BEG|LATE|FIRST[ \t]+HALF|SECOND[ \t]+HALF)[ \t-]*(?:OF[ \t]+)?" + MONTH +
        r"|\b(?:SPOT|PROMPT|PPT|NEXT[ \t]+WEEK)\b"
        r"|\b" + MONTH + r")")
TONNE_UNIT = r"(?:MTS?|TS|TONS?|TONNES|T)\b"
QUANTITY = (r"(?<![\d.,])(\d[\d.,]*)[ \t]*(K)?[ \t]*"
            r"(?:(?:(?:MTS?|TS)\b[ \t]*)?(?:[-–/_]|UP[ \t]*TO|TO)[ \t]*(\d[\d.,]*)[ \t]*(K)?[ \t]*)?"
            r"(?:\(\+/-[^)]*\)[ \t]*)?(?:(?:MTS?|TS|TONS|TONNES|T)\b|(?<=K)(?=[ \t]+[A-Z])|(?:(?<=\) )|(?<=\)))(?=OF\b))")
DATE = (r"(?:" + DAY + r"[ \t]*" + MONTH + r"[ \t]*[-–/][ \t]*" + DAY + r"[ \t]*" + MONTH + r"(?:[ \t]*,?[ \t]*20\d\d)?|"
        + DATE[3:])
# A short trailing number is part of the name ("YONGSHENG 151", "TBN 1"); a long one is the size.
VESSEL_NAME = (r"\bM[./]?V\b\.?\s+(" + PLACE[1:-1] + r"(?:[ \t]+\d{1,3}\b(?![\d,.]|[ \t]*K\b))?)"
               r"(?=\s*(?:[/,(:;|]|[-–—]|\d|\bDWT\b|\bDWCC\b|\bOPEN\b|\bSPOT\b|\bBLT\b|\bIMO\b|$))")
VESSEL_START = re.compile(r"^[ \t]*(?:[•*\-]|\d+[.)])?[ \t]*M[./]?V\b\.?\s", re.IGNORECASE)
NOT_CARGO_WORDS = {"or", "up", "to", "upto", "of", "abt", "about", "per", "day", "in", "x", "and", "with"}


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


def tonnes_value(number, k):
    value = int(to_tonnes(number))
    return value * 1000 if k else value


def parse_quantity(match):
    low = tonnes_value(match.group(1), match.group(2) or match.group(4))
    if not match.group(3):
        return str(low)
    high = tonnes_value(match.group(3), match.group(4))
    # Broker shorthand drops the low end's zeros: "2-4000" = 2000-4000, "42-4500" = 4200-4500,
    # "7-20,000" = 7000-20000.
    while low * 10 <= high:
        low *= 10
    return f"{low}-{high}" if low != high else str(low)


def clean_cargo(words):
    words = re.sub(r"^(?:[\s/,:;(+\-]|\d[\d.,]*\s*(?:K\b)?\s*(?:MTS?|CBM|TS|TONS|PCS|UNITS?(?:\s+OF)?)?\b)+", "",
                   words, flags=re.IGNORECASE)
    for _ in range(3):
        words = re.sub(r"^(?:OF|ABT|ABOUT|TOTAL|BLK)\s+|^\d*\s*(?:PCT|%)\s*(?:MOLOO|MOLCO)?\s*", "", words,
                       flags=re.IGNORECASE)
    words = re.split(r"\s*(?:\d|\bSF\b|\bSTF\b|\babt\b|\bup\s*to\b|\bupto\b|\bwog\b|\btotal\b|\bof\b|[(,;:'’=]"
                     r"|\s[-–/]\s|\bu/o\b)", words, maxsplit=1, flags=re.IGNORECASE)[0]
    tokens = words.split()[:4]
    if not tokens or tokens[0].lower() in NOT_CARGO_WORDS or not re.search(r"[^\W\d_]", tokens[0]):
        return None
    return " ".join(tokens).strip(" .")


def find_cargo_quantity(lines):
    for line in lines:
        # Skip vessel sizes ("Any Dwt 6-9,000 Mt"), laytime rates and unit weights.
        if re.search(r"\d[\d,.]*\s*K?\s*(?:MT\s*)?(?:DWT|DWCC)\b|\b(?:DWT|DWCC)\s*:?\s*\d|\bANY\s+DWT\b|\bL/?D\b"
                     r"|\bRATE\b|PWWD|SHINC|SHEX|\bPER\b|\bEACH\b|\bUNIT", line, re.IGNORECASE):
            continue
        match = re.search(QUANTITY, line, re.IGNORECASE)
        if match:
            cargo = clean_cargo(line[match.end():])
            if not cargo:
                before = re.sub(r"(?i)\b(?:QTY|QUANTITY|VOLUME|CARGO|ANY|ABT|TOTAL)\b\s*:?", "", line[:match.start()])
                cargo = clean_cargo(before)
            return parse_quantity(match), cargo
    for line in lines:
        labelled = re.match(r"^\s*(?:QUANTITY|QTY|VOLUME)\b\s*:?\s*(\d[\d.,]*)", line, re.IGNORECASE)
        if labelled:
            return to_tonnes(labelled.group(1)), None
    return None, None


def find_labelled_cargo(lines):
    for line in lines:
        match = re.match(r"^\s*(?:CARGO|CGO|COMMODITY)\b\s*(:)?\s*(.+)$", line, re.IGNORECASE)
        if match and (match.group(1) or not re.match(r"(?i)(?:is|will|ready|in|to|of)\b", match.group(2))):
            return clean_cargo(match.group(2))
    return None


def find_laycan(lines):
    for line in lines:
        match = re.search(r"\b(?:LAYCAN|L/C|LC|LCAN|LYCN|LAYDAYS)\b[ \t]*[:\-–]?[ \t]*([^\n]+)", line, re.IGNORECASE)
        if not match or "[" in match.group(1):
            continue
        # Prose: "The laycan is 15-20 October. Freight ..." -> "15-20 October".
        value = re.split(r"\.[ \t]", re.sub(r"(?i)^(?:is|will be|of|from)[ \t]+", "", match.group(1)), maxsplit=1)[0]
        # "spot/ppt/try vsl date" -> "spot", but keep "mid/End oct 2026" whole.
        slash = re.match(r"([^/]*?)[ \t]*/[ \t]*(?=[A-Za-z])(.*)", value)
        if slash and not (re.search(MONTH, slash.group(2), re.IGNORECASE)
                          and not re.search(r"\d|" + MONTH, slash.group(1), re.IGNORECASE)):
            value = slash.group(1)
        value = re.split(r"[ \t]+[-–][ \t]+(?=[A-Za-z])|\(|;|,[ \t]*(?=[A-Za-z])|[ \t]+try\b", value,
                         maxsplit=1)[0].strip(" .")
        if value and re.search(r"\d|" + DATE, value, re.IGNORECASE):
            return value
    return find_date(lines)


def find_date(lines):
    for line in lines:
        if re.search(r"\b(?:BUILT|BLT|EXPIRY|DATE:|L/D|RATE)\b", line, re.IGNORECASE):
            continue
        match = re.search(DATE, line, re.IGNORECASE)
        if match:
            return match.group(0).strip(" .,")
    return None


def table_open_port(lines):
    # Position tables without the word "open": "MV FLOKI /09-11 NOV IZMIR",
    # "MV Sky Falcon  3,821 Dwt  2025  E.Med  SPOT". Strip what is not a place and keep the last segment.
    for line in lines[:2]:
        name = re.search(VESSEL_NAME, line, FLAGS)
        rest = line[name.end():] if name else line
        rest = re.sub(DATE, " ", rest, flags=re.IGNORECASE)
        rest = re.sub(r"\d[\d.,]*[ \t]*K?[ \t]*(?:DWT|DWCC|MTS?|TS)?\b|\b(?:GEARED|GEARLESS|DIR|PREFER\w*|IMO|OPEN"
                      r"|ABOUT|ABT|AROUND|ON|SPOT|PROMPT|PERIOD)\b", " ", rest, flags=re.IGNORECASE)
        segments = [s.strip(" .:'\"") for s in re.split(r"[|/–—]|\s-\s|\s{2,}|^-|-$", rest)]
        places = [s for s in segments if re.fullmatch(r"[^\W\d_][\w.'’ ]{1,30}", s) and len(s.split()) <= 4]
        if places:
            return places[-1]
    return None


def tonnage_blocks(lines):
    starts = [i for i, line in enumerate(lines)
              if VESSEL_START.match(line)
              or (re.search(r"\bDWT\b", line, re.IGNORECASE) and re.search(DATE, line, re.IGNORECASE)
                  and not re.search(r"\b(?:BUILT|BLT)\b", line, re.IGNORECASE))]
    blocks = []
    for n, start in enumerate(starts):
        end = min(starts[n + 1] if n + 1 < len(starts) else len(lines), start + 4)
        block = lines[start:end]
        # Particulars ("MV SKY FALCON / 3821 DWT ON 5,48 M / BLT 2024", "Open hatch") repeat the name
        # without a position date or open port.
        if find_date(block) or find_open_port("\n".join(block)):
            blocks.append(block)
    return blocks


def find_dwcc(text):
    # Deadweight cargo capacity: what the vessel can actually load ("7150 dwcc", "DWCC: 4,000 mts").
    match = re.search(NUMBER + r"[ \t]*(?:MTS?[ \t]*)?DWCC\b|\bDWCC\b(?:[ \t]*S/W)?[^\d\n]{0,12}?" + NUMBER, text, FLAGS)
    return to_tonnes(match.group(1) or match.group(2)) if match else None


def tonnage_record(block_text, lines):
    vessel = search(VESSEL_NAME, block_text)
    size = re.search(NUMBER + r"[ \t]*(?:MTS?[ \t]*)?DWT\b|\b(?:DWT|DEADWEIGHT)\b[^\d\n]{0,20}?" + NUMBER,
                     block_text, FLAGS)
    record = {
        "Vessel Name": vessel,
        "Vessel Size": to_tonnes(size.group(1) or size.group(2)) if size else None,
        "Cargo Capacity": find_dwcc(block_text),
        "Open Port": find_open_port(block_text) or (table_open_port(lines) if lines else None),
        "Open Date": find_date(lines) if lines else None,
    }
    return {name: value for name, value in record.items() if value}


def cargo_anchors(lines):
    anchors = {index for index, _, _ in route_lines("\n".join(lines))}
    anchors |= {i for i, line in enumerate(lines) if re.search(LOAD_LABEL, line, FLAGS)}
    return sorted(anchors)


def cargo_window(lines, anchors, n):
    start = anchors[n - 1] + 1 if n > 0 else 0
    end = anchors[n + 1] if n + 1 < len(anchors) else len(lines)
    window = lines[start:end]
    # Lines within three of the anchor's route line come first (nearest first), then the rest in order.
    anchor = anchors[n] - start
    near = sorted((i for i in range(len(window)) if abs(i - anchor) <= 3), key=lambda i: (abs(i - anchor), i))
    return near + [i for i in range(len(window)) if abs(i - anchor) > 3], window


def cargo_details(order, window):
    ordered = [window[i] for i in order]
    quantity, cargo = find_cargo_quantity(ordered)
    details = {
        "Cargo": find_labelled_cargo(window) if re.search(r"(?im)^\s*(?:CARGO|CGO|COMMODITY)\s*:", "\n".join(window))
        else (cargo or find_labelled_cargo(window)),
        "Quantity": quantity,
        "Laycan": find_laycan(ordered),
    }
    return {name: value for name, value in details.items() if value}


def extract_records(text, category):
    """Every vessel position or cargo order in the email, first one first."""
    text = normalize_newlines(text)
    lines = [line for line in text.splitlines() if line.strip()]
    if category == "TONNAGE":
        records = [tonnage_record("\n".join(block), block) for block in tonnage_blocks(lines)]
        first = extract_data(text, category)
        if records:
            records[0] = {**records[0], **first}
        return records or [first]
    if category == "CARGO VC":
        anchors = cargo_anchors(lines)
        routes = {index: (load, discharge) for index, load, discharge in route_lines("\n".join(lines))}
        records = []
        for n, anchor in enumerate(anchors):
            order, window = cargo_window(lines, anchors, n)
            if anchor in routes:
                load, discharge = routes[anchor]
            else:
                block = "\n".join(window)
                load, discharge = find_labelled(LOAD_LABEL, block), find_labelled(DISCHARGE_LABEL, block)
            record = {"Loading Port": load, "Discharge Port": discharge, **cargo_details(order, window)}
            records.append({name: value for name, value in record.items() if value})
        first = extract_data(text, category)
        if records:
            records[0] = {**records[0], **first}
        return records or [first]
    return [extract_data(text, category)]


def extract_data(text, category):
    text = normalize_newlines(text)
    result = {}

    if category == "TONNAGE":
        vessel = search(VESSEL_NAME, text)
        size = re.search(NUMBER + r"[ \t]*(?:MTS?[ \t]*)?DWT\b|\b(?:DWT|DEADWEIGHT)\b[^\d\n]{0,20}?" + NUMBER,
                         text, FLAGS)
        port = find_open_port(text)

        lines = [line for line in text.splitlines() if line.strip()]
        blocks = tonnage_blocks(lines)
        if not port and blocks:
            port = table_open_port(blocks[0])
        date = find_date(blocks[0]) if blocks else find_date(lines)

        if vessel:
            result["Vessel Name"] = vessel
        if port:
            result["Open Port"] = port
        if size:
            result["Vessel Size"] = to_tonnes(size.group(1) or size.group(2))
        capacity = find_dwcc("\n".join(blocks[0]) if blocks else text)
        if capacity:
            result["Cargo Capacity"] = capacity
        if date:
            result["Open Date"] = date

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

        lines = [line for line in text.splitlines() if line.strip()]
        anchors = cargo_anchors(lines)
        if anchors:
            order, window = cargo_window(lines, anchors, 0)
        else:
            window = lines
            order = range(len(lines))
        result.update(cargo_details(order, window))

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
