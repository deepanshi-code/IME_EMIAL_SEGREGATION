# App guide

What each part of the app does, the extracted fields, the tests and the modules. Back to the
[README](../README.md).

## Categories and fields

Sorts maritime chartering emails into **TONNAGE** (vessel open positions), **CARGO VC**
(voyage-charter cargo orders), **CARGO TC** (time-charter enquiries) or **UNKNOWN**, and extracts
the key fields for every vessel position or cargo order in the email.

| Category | Extracted fields (per record) |
|----------|------------------|
| TONNAGE  | Vessel Name, Vessel Size (DWT), Open Port, Open Date |
| CARGO VC | Loading Port, Discharge Port, Cargo, Quantity (tonnes, "min-max" for ranges), Laycan |
| CARGO TC | Delivery Port, Redelivery Port, Duration |

Broker circulars often list several vessels or cargoes; `extractor.extract_records()` returns one
record per vessel position or cargo order (e.g. 20 vessels in one tonnage list). Records go on a
searchable **positions board**, and the app **matches open vessels to cargo orders** by dates, size
and location, explaining every suggestion. Emails can come from files, an exported mailbox (.mbox)
or a read-only IMAP connection.

## The app

The app has five tabs and an About sidebar (what the four types mean, how to read confidence,
measured accuracy):

- **Single email** – six "Try a sample" buttons (vessel position, cargo order, vessel list, time
  charter, a tricky vessel-for-cargo email, a normal email) load and process an example in one click, or paste
  your own. The result card shows the type and confidence as coloured badges, a plain-language
  reason ("Close call: looks like a voyage cargo order (6 points) but also a vessel position
  (5 points). Please check."), the extracted details in large print, and a table of every record
  when the email lists more than one. Scores and JSON download are under "Technical details".
- **Batch upload** – upload several `.txt` / `.eml` files (one email each) and/or `.csv` files
  (one email per row; the text column is guessed and can be changed, a subject column is
  optional), or switch on the 42 demo emails from `samples/`. Shows counts per type, and a table
  with one readable "Key Details" line and a "Why" reason per email; emails needing review come
  first. Click a row to see the email beside its result card. "All columns" shows every field and
  score. Downloads: results CSV (one row per email) and records CSV (one row per vessel or cargo);
  **Add to positions board** puts the records on the board.
- **Inbox** – read emails from an exported **.mbox** file (Gmail Takeout, Thunderbird, Apple Mail; no
  password involved) or over **IMAP** (Gmail, Outlook/Microsoft 365, Yahoo, Zoho or any server).
  IMAP opens the folder **read-only** and fetches with `BODY.PEEK`, so nothing is deleted, moved or
  marked as read; it reads the last N days, at most M emails. Use an **app password**, never your
  normal password; credentials are used for that request only and never stored or logged. On a
  shared deployment the host's server sees what you type, so connect real mailboxes only from a copy
  running on your own computer. The table shows which emails are chartering emails; one click adds
  them to the board.
- **Positions board** – every vessel position and cargo order added this session, with filters (type,
  free-text search, trading region, date window, DWT/tonnage range) and Excel/CSV downloads.
  **Load demo board** adds invented tonnage lists and cargo orders (`samples/demo_board.csv`) that
  match each other, for demos.
  - **Correct a value** by clicking its cell (vessel, DWT/DWCC, ports, dates, cargo, quantity,
    laycan). Dates, region and matches update. **Download corrections** gives every correction with
    the email text, extracted value and corrected value (JSON), ready to use as labelled test data.
  - **Posts** counts records that look like the same vessel (same name) or cargo (same route,
    overlapping quantity and dates) sent by several brokers; **Hide reposts** keeps the latest one.
    Matching always uses the latest post.
  - The board lives in the browser session only. **Save board (backup)** downloads it as JSON;
    **Restore a saved board** loads it back (records already on the board are kept).
- **Matches** – pick a cargo order to see vessels ranked for it, or a vessel to see cargoes for it.

## Tests

```
python -m unittest discover -s tests -v
```

`tests/test_rules.py` checks number and quantity parsing ("7.331,1", "42-4500 MT" = 4200-4500),
classification including known false-positive traps, laycan forms, and record splitting.
`tests/test_stage2.py` covers date ranges (including year roll-over), regions, the board (filters,
no duplicates), matching (best vessel first, impossible pairs left out, tanker check), .mbox
reading, and IMAP against a fake server (read-only select, `BODY.PEEK` fetches, always logs out).
`tests/test_accuracy.py` runs the evaluation on the committed datasets and fails if accuracy drops
below the current level. GitHub Actions (`.github/workflows/tests.yml`) runs all of them on every push.
IMAP has not been tested against a real mailbox.

## Modules

- `pipeline.py` is shared by the app: it runs the classifier and extractor, computes confidence,
  parses `.eml` / `.csv` uploads, and builds the results table with a fixed set of columns.
- `inbox.py` reads .mbox files and IMAP folders; `board.py` stores records; `dates.py` parses date
  phrases; `regions.py` maps ports to trading regions; `matching.py` ranks vessel–cargo pairs.

- `classifier.py` scores each category by adding weighted evidence (e.g. `DWT` = 3, "from X to Y"
  route = 2, "Laycan" = 1) and returns the highest score, or UNKNOWN below 3 points.
  `score_email()` shows the evidence totals behind a decision.
- `extractor.py` uses regexes per category: labelled fields ("Load Port: X"), prose routes
  ("from X to Y", "ex X to Y"), subject-line routes ("X/Y", "X --> Y", cross-checked against
  the body), and normalises sizes ("58,000", "75k" -> 58000, 75000).
