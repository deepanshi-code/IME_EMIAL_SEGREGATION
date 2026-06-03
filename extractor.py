import re

def extract_data(text, category):
    text = text.upper()
    result = {}

    if category == "TONNAGE":
        vessel = re.search(r"MV\s+([A-Z ]+?)(?:\n|DWT|OPEN)", text)
        port = re.search(r"OPEN\s+([A-Z ,]+)", text)
        size = re.search(r"DWT\s+(\d+)", text)

        if vessel:
            result["Vessel Name"] = vessel.group(1).strip()
        if port:
            result["Open Port"] = port.group(1).strip()
        if size:
            result["Vessel Size"] = size.group(1)

    elif category == "CARGO VC":
        load = re.search(r"(LOAD PORT|POL)\s*:?\s*(.+)", text)
        discharge = re.search(r"(DISCHARGE PORT|POD)\s*:?\s*(.+)", text)

        if load:
            result["Loading Port"] = load.group(2).strip()
        if discharge:
            result["Discharge Port"] = discharge.group(2).strip()

    elif category == "CARGO TC":
        delivery = re.search(r"DELIVERY\s*(.+)", text)
        redelivery = re.search(r"REDELIVERY\s*(.+)", text)
        duration = re.search(r"DURATION\s*(.+)", text)

        if delivery:
            result["Delivery Port"] = delivery.group(1).strip()
        if redelivery:
            result["Redelivery Port"] = redelivery.group(1).strip()
        if duration:
            result["Duration"] = duration.group(1).strip()

    return result
