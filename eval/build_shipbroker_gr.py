import argparse
import difflib
import html
import json
import os
import re
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
FIRST_SNAPSHOT = "26 October 2026"


def paths(snapshot):
    # The first snapshot keeps its original file names; later ones are suffixed with their date tag.
    suffix = f"_{snapshot}" if snapshot else ""
    return (os.path.join(EVAL_DIR, "real", f"shipbroker_gr_posts{suffix}.json"),
            os.path.join(EVAL_DIR, f"shipbroker_gr_labels{suffix}.json"),
            os.path.join(EVAL_DIR, "real", f"shipbroker_gr{suffix}.json"))

DATE_LINE = re.compile(r"^\d{1,2} [A-Z][a-z]+ 20\d\d$")
SIGN_OFF = re.compile(
    r"^(?:(?:thanks|thank you|and|&|kind|kindest|best|warm|warmest|with|many)[ ,]*)*(?:regards|rgds|brgds|b\.?rgds)\b"
    r"|^thanks?\s*[,.!]*$",
    re.IGNORECASE,
)
CONTACT_LINE = re.compile(r"^\(?(?:tel|phone|mob|mobile|fax|e-?mail|teams|whats\s*app|website|web|skype|personnel\s+e-?mail)\b",
                          re.IGNORECASE)
NAME_LINE = re.compile(r"^[^\W\d_][\w.'’ -]{1,40}$")
PHONE = re.compile(r"(?:\+\d[\d ()/.-]{6,}\d|\(?\d[\d ()/.-]{8,}\d)")
SHIPPING_WORDS = r"\b(?:mts?|dwt|open|l/[cd]|laycan|lc)\b|\d\s*%"
PERSONAL = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"[\w.+-]+\s*[(\[]at[)\]]\s*[\w-]+(?:\.[\w-]+)+", re.IGNORECASE), "[EMAIL]"),
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


def snapshot_tags():
    folder = os.path.join(EVAL_DIR, "real")
    return [m.group(1) for name in os.listdir(folder)
            for m in [re.fullmatch(r"shipbroker_gr_posts_(\d{8})\.json", name)] if m]


def is_new(post, earlier_texts, cutoff):
    # Later snapshots keep only posts dated after the previous snapshot that are not reposts of earlier ones.
    if datetime.strptime(post["date"], "%d %B %Y") <= cutoff:
        return False
    return all(difflib.SequenceMatcher(None, post["text"], old).ratio() < 0.9 for old in earlier_texts)


def parse(args):
    posts_path, _, _ = paths(args.snapshot)
    posts = []
    for page, path in (("cargo", args.cargo_html), ("vessel", args.vessel_html)):
        for i, (date, lines) in enumerate(split_posts(page_text(path)), start=1):
            text = anonymise(lines)
            if text:
                posts.append({"id": f"{page}-{i:02d}", "page": page, "date": date, "text": text})
    total = len(posts)
    if args.snapshot:
        # Every earlier snapshot is development data by the time a new one is labelled, so a post must be
        # dated after the previous snapshot and must not repeat a post from any earlier snapshot.
        earlier_tags = sorted(tag for tag in snapshot_tags() if tag < args.snapshot)
        earlier = []
        for tag in [""] + earlier_tags:
            with open(paths(tag)[0], encoding="utf-8") as f:
                earlier += [p["text"] for p in json.load(f)]
        cutoff = (datetime.strptime(earlier_tags[-1], "%Y%m%d") if earlier_tags
                  else datetime.strptime(FIRST_SNAPSHOT, "%d %B %Y"))
        posts = [p for p in posts if is_new(p, earlier, cutoff)]
        if args.snapshot > "20261103":
            # The same circular is often posted on several days; keep only its earliest post. (Added after the
            # 3 Nov set, which contains one such pair, cargo-04 / cargo-22, and is kept as published.)
            unique = []
            for post in sorted(posts, key=lambda p: datetime.strptime(p["date"], "%d %B %Y")):
                if all(difflib.SequenceMatcher(None, post["text"], kept["text"]).ratio() < 0.9 for kept in unique):
                    unique.append(post)
            posts = [p for p in posts if p in unique]
        print(f"compared with {len(earlier)} posts from {1 + len(earlier_tags)} earlier snapshots; "
              f"kept posts dated after {cutoff:%d %b %Y}")
    os.makedirs(os.path.dirname(posts_path), exist_ok=True)
    with open(posts_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f"{total} posts on the pages, wrote {len(posts)} new anonymised posts to {posts_path}")


def merge(args):
    posts_path, labels_path, out_path = paths(args.snapshot)
    with open(posts_path, encoding="utf-8") as f:
        posts = {p["id"]: p for p in json.load(f)}
    with open(labels_path, encoding="utf-8") as f:
        labels = json.load(f)
    examples = []
    for i, label in enumerate(labels):
        post = posts[label["id"]]
        if args.snapshot:
            split = f"real-{args.snapshot}"
        else:
            split = "real-dev" if i % 2 == 0 else "real-test"
        examples.append({
            "id": label["id"],
            "split": split,
            "category": label["category"],
            "text": post["text"],
            "fields": label["fields"],
            **({"records": label["records"]} if "records" in label else {}),
            "note": label.get("note", ""),
        })
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(examples)} labelled posts to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Public broker circulars from shipbroker.gr (open cargoes / open ships).")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("parse", help="split saved HTML pages into anonymised posts")
    p.add_argument("--cargo-html", required=True, help="saved http://www.ship.gr/shipbroker/cargo.html")
    p.add_argument("--vessel-html", required=True, help="saved http://www.ship.gr/shipbroker/vessel.html")
    m = sub.add_parser("merge", help="combine posts with eval/shipbroker_gr_labels[_SNAPSHOT].json")
    for command in (p, m):
        command.add_argument("--snapshot", default="", help="date tag of a later snapshot, e.g. 20261103")
    args = parser.parse_args()
    parse(args) if args.command == "parse" else merge(args)


if __name__ == "__main__":
    main()
