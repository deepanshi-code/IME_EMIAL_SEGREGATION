"""Score a broker's verdicts on the blind match-review sheet against the hidden key."""
import argparse
import json
import math
import os
import sys
from collections import Counter

sys.dont_write_bytecode = True
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_DIR = os.path.join(EVAL_DIR, "real")

from openpyxl import load_workbook

VERDICTS = ["Good fit", "Possible", "Not workable"]


def wilson(hits, n, z=1.96):
    # 95% interval for a proportion; honest about how little 12-36 judgements can show.
    if not n:
        return 0.0, 0.0
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - spread), min(1.0, centre + spread)


def read_verdicts(path):
    sheet = load_workbook(path, data_only=True).active
    rows = list(sheet.iter_rows(min_row=3, values_only=True))
    headers = list(rows[0])
    verdicts = {}
    for row in rows[1:]:
        record = dict(zip(headers, row))
        verdict = (record.get("Verdict") or "").strip()
        if record.get("Review #") and verdict:
            match = next((v for v in VERDICTS if v.lower() == verdict.lower()), None)
            if match is None:
                sys.exit(f"{record['Review #']}: unknown verdict {verdict!r}; use one of {VERDICTS}")
            verdicts[record["Review #"]] = (match, (record.get("Comment") or "").strip())
    return verdicts


def line(label, items, good):
    hits, n = sum(1 for v in items if v in good), len(items)
    low, high = wilson(hits, n)
    share = f"{100 * hits / n:5.1f}%" if n else "  n/a"
    return f"  {label:<26} {hits:>2}/{n:<2} = {share}   (95% interval {100 * low:.0f}-{100 * high:.0f}%)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", nargs="?", default=os.path.join(REAL_DIR, "match_review_sheet.xlsx"),
                        help="the sheet the broker filled in")
    parser.add_argument("--key", default=os.path.join(REAL_DIR, "match_review_key.json"))
    args = parser.parse_args()

    with open(args.key, encoding="utf-8") as f:
        key = {k["review_id"]: k for k in json.load(f)}
    verdicts = read_verdicts(args.sheet)
    missing = sorted(set(key) - set(verdicts))
    print(f"{len(verdicts)} of {len(key)} pairs judged" + (f"; not judged: {', '.join(missing)}" if missing else ""))

    groups = {
        "Top-ranked vessel (rank 1)": [verdicts[r][0] for r, k in key.items() if r in verdicts and k["top_rank"] == 1],
        "Top 3 suggestions": [verdicts[r][0] for r, k in key.items() if r in verdicts and k["kind"] == "top"],
        "Controls (low-ranked)": [verdicts[r][0] for r, k in key.items() if r in verdicts and k["kind"] == "control"],
    }
    for title, good in (("Good fit", {"Good fit"}), ("Good fit or Possible", {"Good fit", "Possible"})):
        print(f"\n{title}:")
        for label, items in groups.items():
            print(line(label, items, good))
    print("\nVerdict counts:")
    for label, items in groups.items():
        counts = Counter(items)
        print(f"  {label:<26} " + ", ".join(f"{v} {counts[v]}" for v in VERDICTS))

    top, control = groups["Top 3 suggestions"], groups["Controls (low-ranked)"]
    if top and control:
        gap = sum(v == "Good fit" for v in top) / len(top) - sum(v == "Good fit" for v in control) / len(control)
        print(f"\nTop-3 'Good fit' rate minus control rate: {100 * gap:+.0f} points. With this few judgements, "
              "treat a gap under about 30 points as inconclusive.")

    rejected = [(r, verdicts[r][1]) for r, k in key.items()
                if r in verdicts and k["kind"] == "top" and verdicts[r][0] == "Not workable"]
    if rejected:
        print("\nTop suggestions the broker rejected (use these to improve matching):")
        for review_id, comment in rejected:
            k = key[review_id]
            print(f"  {review_id} (rank {k['top_rank']}, score {k['score']:+d}): {comment or 'no comment'}")
            print(f"      system's reasons: {'; '.join(k['reasons'])}")


if __name__ == "__main__":
    main()
