"""Build a blind review sheet so a broker can judge the vessel-cargo matches.

For each sampled cargo order the sheet lists the top 3 suggested vessels and 1 control (a workable
but low-ranked vessel), shuffled, with scores and ranks hidden. The hidden key goes to a separate
file that score_match_review.py reads after the broker has filled in the sheet.
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime

sys.dont_write_bytecode = True
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(EVAL_DIR, ".."))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

import board
import matching
from pipeline import format_quantity, process_email

REAL_DIR = os.path.join(EVAL_DIR, "real")
SNAPSHOTS = ["shipbroker_gr_posts.json", "shipbroker_gr_posts_20261103.json"]
VERDICTS = ["Good fit", "Possible", "Not workable"]


def load_board():
    conn = board.connect()
    items = []
    for name in SNAPSHOTS:
        with open(os.path.join(REAL_DIR, name), encoding="utf-8") as f:
            for post in json.load(f):
                posted = datetime.strptime(post["date"], "%d %B %Y").date()
                items.append((f"{name[19:-5] or '20261026'}:{post['id']}", post["text"], process_email(post["text"]), posted))
    board.add(conn, items)
    return conn


def describe_cargo(c):
    quantity = format_quantity(c["quantity"]) if c["quantity"] else "quantity not stated"
    return (f"{quantity} {c['cargo'] or ''}".strip() + f", {c['loading_port']} → {c['discharge_port'] or '?'}, "
            f"laycan {c['laycan']} (posted {c['received']})")


def describe_vessel(v):
    size = ", ".join(s for s in [f"{v['vessel_size']:,} DWT" if v["vessel_size"] else "",
                                 f"{v['vessel_dwcc']:,} DWCC" if v["vessel_dwcc"] else ""] if s) or "size not stated"
    return (f"{v['vessel_name'] or 'Unnamed vessel'}, {size}, open {v['open_port'] or '?'} "
            f"{v['open_date'] or ''} (posted {v['received']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cargoes", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    conn = load_board()
    # A broker can only judge a vessel whose open port is stated; reposts keep the latest post only.
    vessels = [v for v in matching.latest_positions(board.records(board.search(conn, category="TONNAGE")))
               if v["open_port"] and (v["vessel_name"] or v["vessel_size"] or v["vessel_dwcc"])]
    cargoes = [c for c in board.records(board.search(conn, category="CARGO VC"))
               if c["start"] and c["loading_port"] and (c["qty_max"] or c["qty_min"])]
    rng.shuffle(cargoes)

    rows, key = [], []
    for cargo in cargoes:
        ranked = matching.rank(cargo, vessels, limit=len(vessels))
        top = [r for r in ranked[:3] if r[0] > 0]
        # The control is workable (not excluded) but ranked well below the top picks.
        controls = [r for r in ranked[5:] if r[0] <= top[-1][0] - 3] if len(top) == 3 else []
        if len(top) < 3 or not controls:
            continue
        picks = [(r, "top", i + 1) for i, r in enumerate(top)] + [(rng.choice(controls), "control", None)]
        rng.shuffle(picks)
        number = len({row["Cargo #"] for row in rows}) + 1
        for (score, vessel, reasons), kind, rank in picks:
            review_id = f"R{len(rows) + 1:03d}"
            rows.append({"Review #": review_id, "Cargo #": number, "Cargo order": describe_cargo(cargo),
                         "Vessel": describe_vessel(vessel), "Verdict": "", "Comment": ""})
            full_rank = next(i for i, r in enumerate(ranked, 1) if r[1] is vessel)
            key.append({"review_id": review_id, "cargo": number, "kind": kind, "top_rank": rank, "rank": full_rank,
                        "score": score, "reasons": reasons, "cargo_source": cargo["source"],
                        "vessel_source": vessel["source"]})
        if number == args.cargoes:
            break

    book = Workbook()
    sheet = book.active
    sheet.title = "Match review"
    sheet.append(["Please judge each vessel for its cargo order as a broker would, from these details only. "
                  "Verdict: Good fit (you would propose it), Possible (with reservations), Not workable. "
                  "Add a short reason when you can."])
    sheet.append([])
    headers = list(rows[0]) if rows else []
    sheet.append(headers)
    for row in rows:
        sheet.append([row[h] for h in headers])
    for cell in sheet[3]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
    for column, width in zip("ABCDEF", (10, 8, 60, 60, 16, 40)):
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=4):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    choice = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
    sheet.add_data_validation(choice)
    choice.add(f"E4:E{3 + len(rows)}")

    os.makedirs(REAL_DIR, exist_ok=True)
    sheet_path = os.path.join(REAL_DIR, "match_review_sheet.xlsx")
    key_path = os.path.join(REAL_DIR, "match_review_key.json")
    book.save(sheet_path)
    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(key, f, indent=1, ensure_ascii=False)
    cargo_count = len({k["cargo"] for k in key})
    print(f"{cargo_count} cargo orders, {len(rows)} vessel pairs ({sum(k['kind'] == 'control' for k in key)} controls)")
    print(f"sheet for the broker: {sheet_path}\nhidden key (do not share): {key_path}")


if __name__ == "__main__":
    main()
