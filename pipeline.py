import email
import email.policy
import html
import io
import re

import pandas as pd

from classifier import MIN_SCORE, classify_email, evidence, score_email
from extractor import extract_data, extract_records

FIELD_NAMES = [
    "Vessel Name", "Vessel Size", "Open Port", "Open Date",
    "Loading Port", "Discharge Port", "Cargo", "Quantity", "Laycan",
    "Delivery Port", "Redelivery Port", "Duration",
]
TEXT_COLUMN_HINTS = ["text", "body", "email", "content", "message"]


def confidence(category, scores):
    ranked = sorted(scores.values(), reverse=True)
    top, second = ranked[0], ranked[1]
    if category == "UNKNOWN":
        return "High" if top == 0 else "Low"
    margin = top - second
    if margin <= 1 or top == MIN_SCORE:
        return "Low"
    if top >= 6 and margin >= 3:
        return "High"
    return "Medium"


CATEGORY_NAMES = {
    "TONNAGE": "vessel position",
    "CARGO VC": "voyage cargo order",
    "CARGO TC": "time-charter enquiry",
    "UNKNOWN": "not chartering",
}


def explain(text, category, level, scores):
    ranked = sorted(scores, key=scores.get, reverse=True)
    top, second = ranked[0], ranked[1]
    if category == "UNKNOWN":
        if level == "High":
            return "No chartering terms found. This looks like a normal email."
        clues = ", ".join(evidence(text, top))
        return f"Some chartering terms found ({clues}), but not enough to decide. Please check."
    clues = ", ".join(evidence(text, category)[:4])
    name = CATEGORY_NAMES[category]
    if level == "Low" and scores[second] >= scores[top] - 1 and scores[second] > 0:
        return (f"Close call: looks like a {name} ({scores[top]} points) but also a "
                f"{CATEGORY_NAMES[second]} ({scores[second]} points). Please check.")
    if level == "Low":
        return f"Only weak evidence for a {name}: {clues}. Please check."
    prefix = "Clearly" if level == "High" else "Probably"
    return f"{prefix} a {name}, based on: {clues}."


def format_quantity(value):
    return "–".join(f"{int(part):,}" for part in value.split("-")) + " t"


def summary(fields):
    # One readable line per email for the batch table: "SEA HAWK · 58,000 DWT · open Tianjin".
    parts = []
    if fields["Vessel Name"]:
        parts.append(fields["Vessel Name"])
    if fields["Vessel Size"]:
        parts.append(f"{int(fields['Vessel Size']):,} DWT")
    if fields["Open Port"]:
        parts.append(f"open {fields['Open Port']}")
    if fields["Open Date"]:
        parts.append(fields["Open Date"])
    if fields["Quantity"]:
        parts.append(format_quantity(fields["Quantity"]))
    if fields["Cargo"]:
        parts.append(fields["Cargo"])
    if fields["Loading Port"] or fields["Discharge Port"]:
        parts.append(f"{fields['Loading Port'] or '?'} → {fields['Discharge Port'] or '?'}")
    if fields["Laycan"]:
        parts.append(f"laycan {fields['Laycan']}")
    if fields["Delivery Port"]:
        parts.append(f"del {fields['Delivery Port']}")
    if fields["Redelivery Port"]:
        parts.append(f"redel {fields['Redelivery Port']}")
    if fields["Duration"]:
        parts.append(fields["Duration"])
    return " · ".join(parts)


def process_email(text):
    scores = score_email(text)
    category = classify_email(text)
    level = confidence(category, scores)
    found = extract_data(text, category)
    records = extract_records(text, category) if category in ("TONNAGE", "CARGO VC") else []
    return {
        "category": category,
        "confidence": level,
        "needs_review": level == "Low",
        "reason": explain(text, category, level, scores),
        "scores": scores,
        "fields": {name: found.get(name) for name in FIELD_NAMES},
        "records": [{name: record.get(name) for name in FIELD_NAMES} for record in records],
    }


def parse_eml(raw):
    message = email.message_from_bytes(raw, policy=email.policy.default)
    part = message.get_body(preferencelist=("plain", "html"))
    body = ""
    if part is not None:
        try:
            body = part.get_content()
        except (LookupError, UnicodeDecodeError):
            body = part.get_payload(decode=True).decode("latin-1", errors="replace")
        if part.get_content_type() == "text/html":
            body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return f"Subject: {message['subject'] or ''}\n\n{body}"


def decode_text(raw):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue


def read_csv(raw):
    return pd.read_csv(io.StringIO(decode_text(raw)), dtype=str).fillna("")


def guess_column(columns, hints):
    for hint in hints:
        for column in columns:
            if hint in column.lower():
                return column
    return columns[0]


def results_table(sources, results):
    rows = []
    for source, result in zip(sources, results):
        row = {
            "Source": source,
            "Category": result["category"],
            "Confidence": result["confidence"],
            "Needs Review": result["needs_review"],
            "Records": len(result["records"]) or None,
            "Key Details": summary(result["fields"]),
            "Why": result["reason"],
        }
        row.update(result["fields"])
        row.update({f"Score {name}": value for name, value in result["scores"].items()})
        rows.append(row)
    return pd.DataFrame(rows)


def records_table(sources, results):
    # One row per vessel position or cargo order across the whole batch (a positions board).
    rows = []
    for source, result in zip(sources, results):
        for number, record in enumerate(result["records"], start=1):
            row = {"Source": source, "Record": number, "Category": result["category"],
                   "Confidence": result["confidence"]}
            row.update(record)
            rows.append(row)
    return pd.DataFrame(rows)
