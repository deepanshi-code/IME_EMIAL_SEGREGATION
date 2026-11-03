import hashlib
import sqlite3
from datetime import date

import pandas as pd

from dates import parse_range
from regions import region_of

COLUMNS = [
    ("key", "TEXT UNIQUE"), ("source", "TEXT"), ("received", "TEXT"), ("category", "TEXT"), ("confidence", "TEXT"),
    ("vessel_name", "TEXT"), ("vessel_size", "INTEGER"), ("vessel_dwcc", "INTEGER"), ("open_port", "TEXT"), ("open_date", "TEXT"),
    ("loading_port", "TEXT"), ("discharge_port", "TEXT"), ("cargo", "TEXT"), ("quantity", "TEXT"),
    ("qty_min", "INTEGER"), ("qty_max", "INTEGER"), ("laycan", "TEXT"),
    ("start", "TEXT"), ("end", "TEXT"), ("region", "TEXT"),
]
FIELD_COLUMNS = {
    "Vessel Name": "vessel_name", "Vessel Size": "vessel_size", "Cargo Capacity": "vessel_dwcc", "Open Port": "open_port", "Open Date": "open_date",
    "Loading Port": "loading_port", "Discharge Port": "discharge_port", "Cargo": "cargo", "Quantity": "quantity",
    "Laycan": "laycan",
}


def connect(path=":memory:"):
    # The default is an in-memory board, one per app session, so visitors of a shared deployment never
    # see each other's emails. Pass a file path to keep the board between runs on your own machine.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(f"CREATE TABLE IF NOT EXISTS records ({', '.join(f'{n} {t}' for n, t in COLUMNS)})")
    return conn


def record_row(source, text, number, result, record, received):
    reference = received or date.today()
    row = {column: record.get(name) for name, column in FIELD_COLUMNS.items()}
    when = parse_range(record.get("Open Date") if result["category"] == "TONNAGE" else record.get("Laycan"),
                       reference)
    quantity = record.get("Quantity")
    low, high = (quantity.split("-") + [quantity.split("-")[0]])[:2] if quantity else (None, None)
    row.update({
        "key": hashlib.sha1(f"{text}\x00{number}".encode("utf-8")).hexdigest(),
        "source": source,
        "received": reference.isoformat(),
        "category": result["category"],
        "confidence": result["confidence"],
        "vessel_size": int(row["vessel_size"]) if row["vessel_size"] else None,
        "vessel_dwcc": int(row["vessel_dwcc"]) if row["vessel_dwcc"] else None,
        "qty_min": int(low) if low else None,
        "qty_max": int(high) if high else None,
        "start": when[0].isoformat() if when else None,
        "end": when[1].isoformat() if when else None,
        "region": region_of(record.get("Open Port") or record.get("Loading Port")),
    })
    return row


def add(conn, items):
    """Add processed emails. items: (source, text, result, received date or None). Returns rows added."""
    rows = [record_row(source, text, number, result, record, received)
            for source, text, result, received in items
            for number, record in enumerate(result["records"], start=1)]
    names = [n for n, _ in COLUMNS]
    before = conn.total_changes
    conn.executemany(f"INSERT OR IGNORE INTO records ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                     [[row.get(n) for n in names] for row in rows])
    conn.commit()
    return conn.total_changes - before


def frame(conn):
    return pd.read_sql_query("SELECT * FROM records ORDER BY category, start", conn)


def search(conn, category=None, text="", region=None, start=None, end=None, min_size=None, max_size=None):
    """Board rows matching the filters. start/end: keep records whose date range overlaps them."""
    rows = frame(conn)
    if category:
        rows = rows[rows["category"] == category]
    if text:
        haystack = rows[["vessel_name", "open_port", "loading_port", "discharge_port", "cargo", "source"]]
        hit = haystack.fillna("").apply(lambda r: text.lower() in " ".join(r).lower(), axis=1)
        rows = rows[hit] if len(rows) else rows
    if region:
        rows = rows[rows["region"] == region]
    if start:
        rows = rows[rows["end"].isna() | (rows["end"] >= start.isoformat())]
    if end:
        rows = rows[rows["start"].isna() | (rows["start"] <= end.isoformat())]
    number = lambda column: pd.to_numeric(rows[column], errors="coerce")
    size = number("vessel_size").fillna(number("vessel_dwcc")).where(rows["category"] == "TONNAGE", number("qty_max"))
    if min_size:
        rows = rows[size.isna() | (size >= min_size)]
        size = size[rows.index]
    if max_size:
        rows = rows[size.isna() | (size <= max_size)]
    return rows


def records(rows):
    """Board rows as plain dicts: missing values None (not NaN), sizes and quantities as ints."""
    out = []
    for row in rows.to_dict("records"):
        clean = {key: (None if pd.isna(value) else value) for key, value in row.items()}
        for key in ("vessel_size", "vessel_dwcc", "qty_min", "qty_max"):
            if clean.get(key) is not None:
                clean[key] = int(clean[key])
        out.append(clean)
    return out


def clear(conn):
    conn.execute("DELETE FROM records")
    conn.commit()
