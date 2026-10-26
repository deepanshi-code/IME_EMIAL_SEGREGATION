import argparse
import html
import json
import os
import re

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
POSTS_PATH = os.path.join(EVAL_DIR, "real", "shipbroker_gr_posts.json")
LABELS_PATH = os.path.join(EVAL_DIR, "shipbroker_gr_labels.json")
OUT_PATH = os.path.join(EVAL_DIR, "real", "shipbroker_gr.json")

DATE_LINE = re.compile(r"^\d{1,2} [A-Z][a-z]+ 20\d\d$")
SIGN_OFF = re.compile(
    r"^(?:(?:thanks|thank you|and|&|kind|kindest|best|warm|warmest|with|many)[ ,]*)*(?:regards|rgds|brgds|b\.?rgds)\b"
    r"|^thanks?\s*[,.!]*$",
    re.IGNORECASE,
)
CONTACT_LINE = re.compile(r"^\(?(?:tel|phone|mob|mobile|fax|e-?mail|teams|whats\s*app|website|skype)\b", re.IGNORECASE)
NAME_LINE = re.compile(r"^[^\W\d_][\w.'’ -]{1,40}$")
PHONE = re.compile(r"(?:\+\d[\d ()/.-]{6,}\d|\(?\d[\d ()/.-]{8,}\d)")
SHIPPING_WORDS = r"\b(?:mts?|dwt|open|l/[cd]|laycan|lc)\b|\d\s*%"
PERSONAL = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"(?:https?://|www\.)\S+"), "[URL]"),
]


def mask_phones(line):
    # Quantities and rates ("5000-10000 mts", "1000x/1000x") look like phone numbers;
    # only mask sequences with a leading "+" or at least 10 digits.
    def replace(match):
        text = match.group(0)
        digits = sum(c.isdigit() for c in text)
        return "[PHONE]" if text.startswith("+") or digits >= 10 else text
    return PHONE.sub(replace, line)


def page_text(path):
    with open(path, "rb") as f:
        raw = f.read().decode("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</tr>|</div>|</li>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", "", raw)).replace("\xa0", " ")
    return [line.strip() for line in text.splitlines()]


def split_posts(lines):
    posts, current, date = [], None, None
    for line in lines:
        if DATE_LINE.match(line):
            if current is not None:
                posts.append((date, current))
            date, current = line, []
        elif current is not None:
            current.append(line)
    if current is not None:
        posts.append((date, current))
    return posts


def anonymise(lines):
    kept = []
    for line in lines:
        if SIGN_OFF.match(line):
            break
        if CONTACT_LINE.match(line):
            # A short name line directly above a contact line is the sender's name.
            while kept and not kept[-1]:
                kept.pop()
            if kept and NAME_LINE.match(kept[-1]) and len(kept[-1].split()) <= 4:
                kept.pop()
            continue
        for pattern, token in PERSONAL:
            line = pattern.sub(token, line)
        line = mask_phones(line)
        if re.search(r"\[(?:PHONE|EMAIL)\]", line) and not re.search(SHIPPING_WORDS, line, re.IGNORECASE):
            continue
        kept.append(line)
    text = "\n".join(kept).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    # The site footer follows the last post on each page.
    return re.split(r"\n(?:ADD SHIP or CARGO|Contact\s*\|)", text)[0].strip()


def parse(args):
    posts = []
    for page, path in (("cargo", args.cargo_html), ("vessel", args.vessel_html)):
        for i, (date, lines) in enumerate(split_posts(page_text(path)), start=1):
            text = anonymise(lines)
            if text:
                posts.append({"id": f"{page}-{i:02d}", "page": page, "date": date, "text": text})
    os.makedirs(os.path.dirname(POSTS_PATH), exist_ok=True)
    with open(POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(posts)} anonymised posts to {POSTS_PATH}")


def merge():
    with open(POSTS_PATH, encoding="utf-8") as f:
        posts = {p["id"]: p for p in json.load(f)}
    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = json.load(f)
    examples = []
    for i, label in enumerate(labels):
        post = posts[label["id"]]
        examples.append({
            "id": label["id"],
            "split": "real-dev" if i % 2 == 0 else "real-test",
            "category": label["category"],
            "text": post["text"],
            "fields": label["fields"],
            "note": label.get("note", ""),
        })
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(examples)} labelled posts to {OUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Public broker circulars from shipbroker.gr (open cargoes / open ships).")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("parse", help="split saved HTML pages into anonymised posts")
    p.add_argument("--cargo-html", required=True, help="saved http://www.ship.gr/shipbroker/cargo.html")
    p.add_argument("--vessel-html", required=True, help="saved http://www.ship.gr/shipbroker/vessel.html")
    sub.add_parser("merge", help="combine posts with eval/shipbroker_gr_labels.json")
    args = parser.parse_args()
    parse(args) if args.command == "parse" else merge()


if __name__ == "__main__":
    main()
