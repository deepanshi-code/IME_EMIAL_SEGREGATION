import email
import email.policy
import html
import io
import re

import pandas as pd

from classifier import MIN_SCORE, classify_email, score_email
from extractor import extract_data

FIELD_NAMES = [
    "Vessel Name", "Vessel Size", "Open Port",
    "Loading Port", "Discharge Port",
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


def process_email(text):
    scores = score_email(text)
    category = classify_email(text)
    level = confidence(category, scores)
    found = extract_data(text, category)
    return {
        "category": category,
        "confidence": level,
        "needs_review": level == "Low",
        "scores": scores,
        "fields": {name: found.get(name) for name in FIELD_NAMES},
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
        }
        row.update(result["fields"])
        row.update({f"Score {name}": value for name, value in result["scores"].items()})
        rows.append(row)
    return pd.DataFrame(rows)
