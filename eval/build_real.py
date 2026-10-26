import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pipeline import FIELD_NAMES, decode_text, parse_eml

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_DIR = os.path.join(EVAL_DIR, "real")
CATEGORIES = {"TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"}
PERSONAL_DATA = {
    "email address": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone number": r"(?:\+\d[\d ()-]{7,}\d|\b\d{3}[ -]\d{3,4}[ -]\d{4}\b)",
}


def load_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    return parse_eml(raw) if path.lower().endswith(".eml") else decode_text(raw)


def main():
    parser = argparse.ArgumentParser(description="Convert labelled real emails in eval/real/ to eval/real.json.")
    parser.add_argument("--labels", default=os.path.join(REAL_DIR, "labels.csv"))
    parser.add_argument("--emails", default=os.path.join(REAL_DIR, "emails"))
    args = parser.parse_args()

    problems, warnings, examples = [], [], []
    with open(args.labels, encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            name = (row.get("file") or "").strip()
            if not name:
                continue
            path = os.path.join(args.emails, name)
            if not os.path.exists(path):
                problems.append(f"line {line}: file not found: {name}")
                continue
            category = (row.get("category") or "").strip().upper()
            if category not in CATEGORIES:
                problems.append(f"line {line}: category must be one of {sorted(CATEGORIES)}, got {category!r}")
                continue

            text = load_text(path)
            fields = {field: row[field].strip() for field in FIELD_NAMES if (row.get(field) or "").strip()}
            for field, value in fields.items():
                if field != "Vessel Size" and value.lower() not in text.lower():
                    warnings.append(f"{name}: {field} {value!r} does not appear in the email text (typo?)")
            for kind, pattern in PERSONAL_DATA.items():
                if re.search(pattern, text):
                    warnings.append(f"{name}: contains what looks like an {kind}; anonymise it before sharing")

            examples.append({
                "id": name,
                "split": "real",
                "category": category,
                "text": text,
                "fields": fields,
                "note": (row.get("notes") or "").strip(),
            })

    for message in warnings:
        print("WARNING:", message)
    for message in problems:
        print("ERROR:", message)
    if problems:
        sys.exit(1)

    out_path = os.path.join(EVAL_DIR, "real.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(examples)} labelled real emails to {out_path}")


if __name__ == "__main__":
    main()
