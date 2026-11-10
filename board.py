import hashlib
import re
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
    ("start", "TEXT"), ("end", "TEXT"), ("region", "TEXT"), ("text", "TEXT"),
]
BACKUP_VERSION = 1
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
    existing = {row[1] for row in conn.execute("PRAGMA table_info(records)")}
    for name, kind in COLUMNS:  # boards saved by older versions lack newer columns
        if name not in existing:
            conn.execute(f"ALTER TABLE records ADD COLUMN {name} {kind.replace(' UNIQUE', '')}")
    return conn


def derived(row, reference):
    """Columns computed from the extracted fields: sizes as ints, quantity range, date range, region."""
    when = parse_range(row.get("open_date") if row.get("category") == "TONNAGE" else row.get("laycan"), reference)
    quantity = str(row["quantity"]).replace(",", "").replace(" ", "") if row.get("quantity") else None
    low, high = (quantity.split("-") + [quantity.split("-")[0]])[:2] if quantity else (None, None)

    def as_int(value):
        return int(str(value).replace(",", "")) if value not in (None, "") else None

    return {
        "vessel_size": as_int(row.get("vessel_size")),
        "vessel_dwcc": as_int(row.get("vessel_dwcc")),
        "quantity": quantity,
        "qty_min": int(low) if low else None,
        "qty_max": int(high) if high else None,
        "start": when[0].isoformat() if when else None,
        "end": when[1].isoformat() if when else None,
        "region": region_of(row.get("open_port") or row.get("loading_port")),
    }


def record_row(source, text, number, result, record, received):
    reference = received or date.today()
    row = {column: record.get(name) for name, column in FIELD_COLUMNS.items()}
    row.update({
        "key": hashlib.sha1(f"{text}\x00{number}".encode("utf-8")).hexdigest(),
        "source": source,
        "received": reference.isoformat(),
        "category": result["category"],
        "confidence": result["confidence"],
        "text": text,
    })
    row.update(derived(row, reference))
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


def update(conn, key, changes):
    """Correct extracted fields of one record (changes: {column: value}); derived columns are recomputed.

    Raises ValueError for a column that cannot be edited or a size/quantity that is not a number."""
    editable = set(FIELD_COLUMNS.values())
    unknown = set(changes) - editable
    if unknown:
        raise ValueError(f"not editable: {', '.join(sorted(unknown))}")
    found = records(frame(conn).query("key == @key"))
    if not found:
        raise KeyError(key)
    row = {**found[0], **{column: (value.strip() if isinstance(value, str) else value) or None
                          for column, value in changes.items()}}
    reference = date.fromisoformat(row["received"]) if row.get("received") else date.today()
    try:
        row.update(derived(row, reference))
    except ValueError:
        raise ValueError("sizes and quantities must be numbers, e.g. 58000 or 2000-3000") from None
    columns = sorted(editable | {"qty_min", "qty_max", "start", "end", "region"})
    conn.execute(f"UPDATE records SET {', '.join(f'{c} = ?' for c in columns)} WHERE key = ?",
                 [row.get(c) for c in columns] + [key])
    conn.commit()


def backup(conn):
    """The whole board as JSON-ready data, to keep on your own computer and restore later."""
    return {"version": BACKUP_VERSION, "records": records(frame(conn))}


def restore(conn, data):
    """Add the records of a backup (rows already on the board are kept). Returns rows added."""
    if not isinstance(data, dict) or data.get("version") != BACKUP_VERSION or not isinstance(data.get("records"), list):
        raise ValueError("not a positions board backup from this app")
    names = [n for n, _ in COLUMNS]
    rows = [row for row in data["records"] if isinstance(row, dict) and row.get("key")]
    before = conn.total_changes
    conn.executemany(f"INSERT OR IGNORE INTO records ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                     [[row.get(n) for n in names] for row in rows])
    conn.commit()
    return conn.total_changes - before


def _name(value):
    name = re.sub(r"^(?:M/?V|M/?T)\.?\s+", "", str(value or "").strip().upper())
    return re.sub(r"\s+", " ", name)


def _overlap(low1, high1, low2, high2):
    if low1 is None or low2 is None:
        return True  # unknown on one side: do not rule the repost out
    return low1 <= (high2 or low2) and low2 <= (high1 or low1)


def _same(item, first):
    if item["category"] != first["category"]:
        return False
    if item["category"] == "TONNAGE":
        name = _name(item["vessel_name"])
        return bool(name) and not name.startswith("TBN") and name == _name(first["vessel_name"])
    return bool(item["loading_port"] and item["discharge_port"]
                and _name(item["loading_port"]) == _name(first["loading_port"])
                and _name(item["discharge_port"]) == _name(first["discharge_port"])
                and _overlap(item["qty_min"], item["qty_max"], first["qty_min"], first["qty_max"])
                and _overlap(item["start"], item["end"], first["start"], first["end"]))


def repost_groups(rows):
    """(posts per record, is-latest per record), both keyed by record key.

    Brokers circulate the same ship or order to many desks. Vessels: same name (TBN excluded).
    Cargoes: same load and discharge port, overlapping quantity and overlapping dates."""
    groups = []
    for item in records(rows):
        group = next((g for g in groups if _same(item, g[0])), None)
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    counts, latest = {}, {}
    for group in groups:
        newest = max(group, key=lambda r: (r.get("received") or "", r["key"]))
        for item in group:
            counts[item["key"]] = len(group)
            latest[item["key"]] = item["key"] == newest["key"]
    return counts, latest


def clear(conn):
    conn.execute("DELETE FROM records")
    conn.commit()
