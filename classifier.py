def classify_email(text):
    text = text.upper()

    if "OPEN" in text and ("DWT" in text or "MV " in text or "VESSEL" in text):
        return "TONNAGE"

    if (
        "LOAD PORT" in text
        or "DISCHARGE PORT" in text
        or "POL:" in text
        or "POD:" in text
    ):
        return "CARGO VC"

    if (
        "DELIVERY" in text
        or "REDELIVERY" in text
        or "DURATION" in text
        or "TCT" in text
    ):
        return "CARGO TC"

    return "UNKNOWN"
