# IME Email Segregation

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

## Run

```
pip install -r requirements.txt
streamlit run app.py
```

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
- **Matches** – pick a cargo order to see vessels ranked for it, or a vessel to see cargoes for it.

### Positions board and privacy

`board.py` stores records in SQLite. By default the board is **in memory, one per browser session**,
so visitors of the public deployment never see each other's emails, and it is lost when the session
ends. To keep a board between runs on your own computer, set `POSITIONS_DB=positions.db` before
`streamlit run app.py`. Adding the same email twice adds nothing (records are keyed by email text and
position). Dates are turned into ranges by `dates.py` (e.g. "27-28/OCT", "mid Oct", "1-10/11",
"SPOT" = the next 7 days); the year is inferred from the email's date. It parses 106 of the 107
labelled laycans/open dates in the real posts; the other one ("Vsl date") has no date.

### Matching

`matching.py` scores each vessel–cargo pair (max +9):

| Check | Points | Rule |
|-------|--------|------|
| Dates | +3 / +2 / 0 / excluded | open dates overlap the laycan / opens up to 10 days before it / earlier / opens after the laycan ends |
| Size | +3 / +1 / −1 / excluded | cargo is 70–95% of DWT (or 70–100% of DWCC, the cargo capacity, used when stated) / 40–70% (part cargo) / under 40% / too big |
| Location | +3 / +2 / +1 / 0 / −2 | open at the load port / same trading region / neighbouring region / unknown / far apart |
| Vessel type | −3 | liquid cargo (crude, fuel oil, vegoil, chemicals, LPG…) with a vessel not described as a tanker |

Regions come from `regions.py`, a hand-written table of 17 trading regions (Black Sea, Marmara/Aegean,
East Med, Continent/UK, Arabian Gulf, India/Pakistan, SE Asia, Far East, …) with their neighbours and
the port/area names brokers use. It covers 109 of the 110 port/area names in the real labels, but
it was written with those names in view, so coverage of other inboxes will be lower; unknown ports
score 0, not a penalty. Weak matches (score 0 or below) are hidden unless switched on.

**Matching is not validated.** There is no ground truth for "the right vessel for this cargo"; the
rules are standard broker considerations (dates, size, position), but distances, vessel type and
gear, draft and port restrictions, and commercial terms are not modelled. Treat matches as a
shortlist to check, and validate them with a broker before claiming accuracy.

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

**Confidence** comes from the category scores in `classifier.score_email()`:

| Level | Rule |
|-------|------|
| High   | top score >= 6 and >= 3 points ahead of the next category; or UNKNOWN with no evidence at all |
| Medium | anything between |
| Low    | top two scores within 1 point, top score exactly at the threshold (3), or UNKNOWN with 1-2 points of evidence. Flagged **Needs Review** |

Checked on the tuning splits only (dev, ext-dev, neg-dev, real-dev; 516 emails, v5 rules): High was
correct 391/392 (99.7%), Medium 57/57, Low 53/67 (79.1%). 14 of the 15 category errors were
flagged Low, so reviewing only the Low emails (13% of the batch) catches almost all mistakes.

The reason text lists the rules that fired, using the plain-language label each rule carries in
`classifier.EVIDENCE` (`classifier.evidence()` returns them).

## How it works

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

## Evaluation

```
python eval/evaluate.py --split dev --errors
python eval/evaluate.py --split test
python eval/evaluate.py --data eval/maritimemails_ext-dev.json --split ext-dev --errors
python eval/evaluate.py --data eval/maritimemails_ext-test.json --split ext-test
python eval/evaluate.py --data eval/negatives_neg-dev.json --split neg-dev --errors
python eval/evaluate.py --data eval/negatives_neg-test.json --split neg-test
```

Reports classification accuracy, per-category precision/recall/F1, a confusion matrix,
per-field extraction accuracy, spurious fields, and the share of fully correct emails.
Field values are compared case- and whitespace-insensitively; everything else must match exactly.

### Datasets

| File | Split | Size | Source |
|------|-------|------|--------|
| `eval/emails.json` | dev / test | 24 / 18 | Hand-written broker-style emails covering all four categories |
| `eval/maritimemails_ext-dev.json` | ext-dev | 150 | MaritimEmails dev split (first email of each thread) |
| `eval/maritimemails_ext-test.json` | ext-test | 150 | MaritimEmails test split (first email of each thread) |
| `eval/negatives_neg-dev.json` | neg-dev | 300 | Non-shipping emails: 150 Enron ham + 150 SpamAssassin easy_ham |
| `eval/negatives_neg-test.json` | neg-test | 300 | Same sources, disjoint emails |
| `eval/real/shipbroker_gr.json` | real-dev / real-test | 42 / 42 | **Real broker circulars** from shipbroker.gr, 26 Oct 2026 (see below); development data since v6 |
| `eval/real/shipbroker_gr_20261103.json` | real-20261103 | 30 | Fresh shipbroker.gr snapshot, 3 Nov 2026: posts after 26 Oct that are not reposts. **v6 held-out test** |

**Real broker circulars.** [shipbroker.gr](http://www.ship.gr/shipbroker/cargo.html) publishes
cargo orders and open-vessel positions that brokers submit, as the circulars they email
("Pls offer firm for… Kandla / Subic Bay… 8k mt bagged rice"). A snapshot taken on 26 Oct 2026
gave 84 posts (49 cargo, 35 vessel). `eval/build_shipbroker_gr.py parse` splits the saved pages
and anonymises them (cuts the sign-off and signature, removes emails, URLs, phone numbers and
contact lines); the site's terms do not restrict reuse, but the posts name real people, so the
text stays in `eval/real/` (not committed). Every post was labelled **before** the system was
run on it, using the rules in `eval/shipbroker_gr_labels.json` (committed; port and vessel names
only): category from what the post is, fields for the first record, Vessel Size only when a DWT
is stated. Labels were drafted with AI assistance and have not yet been checked by a domain
expert; spot-check them. Alternate posts form real-dev and real-test. There are no CARGO TC posts: period/TCT
requests only appear as side items inside cargo posts.

For v6 the 84 first-snapshot posts also got labels for the new fields (Open Date; Cargo, Quantity,
Laycan for the first record) and a record count (vessel positions or cargo orders of the post's
category). Free-text fields (Cargo, Laycan, Open Date) are scored leniently: one value's words must
contain the other's and the shorter must have at least half as many words ("29 OCT" matches
"29 OCT - 05 NOV"; "Oct" does not match "26-28 Oct"). Quantity must match exactly in tonnes.

**Fresh snapshots as held-out tests.** The board changes daily, so a later snapshot gives an unseen
test set: `parse --snapshot YYYYMMDD` keeps only posts dated after 26 Oct that are not reposts
(90% text similarity). The 3 Nov snapshot was saved before any v6 change, left unread until the v6
rules were frozen, then labelled (`eval/shipbroker_gr_labels_20261103.json`) and run once.

```
python eval/build_shipbroker_gr.py parse --cargo-html cargo.html --vessel-html vessel.html
python eval/build_shipbroker_gr.py merge
python eval/evaluate.py --data eval/real/shipbroker_gr.json --split all --errors
python eval/build_shipbroker_gr.py parse --snapshot 20261103 --cargo-html cargo.html --vessel-html vessel.html
python eval/build_shipbroker_gr.py merge --snapshot 20261103
python eval/evaluate.py --data eval/real/shipbroker_gr_20261103.json --split real-20261103
```

**Non-shipping negatives** measure false positives (normal emails classified as shipping).
They are real people's emails from two public corpora, so they are **not committed** (see
`.gitignore`); rebuild them locally:

```
curl -L -o enron_test.jsonl https://huggingface.co/datasets/SetFit/enron_spam/resolve/main/test.jsonl
curl -L -o easy_ham.tar.bz2 https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2
python eval/build_negatives.py --enron enron_test.jsonl --spamassassin easy_ham.tar.bz2
```

- *Enron-Spam* (Metsis et al., 2006; [SetFit/enron_spam](https://huggingface.co/datasets/SetFit/enron_spam)),
  ham messages: business email from an energy-trading company, so it is full of near-miss
  vocabulary ("delivery point", "volume", "rate", "freight markets"). The text is lowercased and
  tokenised, which hides case-sensitive rules, hence the second source.
- *SpamAssassin public corpus*, `easy_ham` (2003): raw, original-case personal and mailing-list email.

The external sets come from **MaritimEmails** (Bruendler & Clematide, LREC 2026), a corpus of
19,817 synthetic chartering email threads generated by five LLMs, licensed CC BY-NC 4.0. See
`eval/MARITIMEMAILS_NOTICE.md` for attribution and how the samples were built
(`eval/build_maritimemails.py`, seed 42). Only threads whose first email contains both labelled
ports were used; each is labelled CARGO VC with the dataset's `load_port` / `discharge_port`.

Tune rules on `dev`, `ext-dev`, `neg-dev` and the first real snapshot only. `ext-test`, `neg-test`
and the newest real snapshot are run once per frozen version.

### Results

**Headline (v6, 30 fresh real broker circulars never seen during development): 83.3% category
accuracy (25/30), 66.4% field accuracy (79/119, including the new fields), 96.3% exact record
counts (26/27).** The v5 rules score 76.7% / 31.9% on the same posts.

| Version | real 26 Oct, all 84 (development) cat / fields / records | **real 3 Nov, 30 (held out)** cat / fields / records | ext-test (150) cat / fields | False positives neg-test (300) |
|---------|------|------|------|------|
| v5 | 95.2% / 83.5% (old fields only) / – | 76.7% / 31.9% / – | 89.3% / 83.3% | 1 (0.3%) |
| v6 multi-record + new fields | 98.8% / 92.7% / 85.7% | **83.3% / 66.4% / 96.3%** | 89.3% / 83.3% | 1 (0.3%) |

v6 field accuracy on the fresh posts: Open Date 88.9%, Vessel Name 88.9%, Open Port 85.7%, Laycan
77.8%, Vessel Size 71.4%, Quantity 69.2%, Loading/Discharge Port 61.1%, Cargo 37.5%. The drop from
development (92.7%) to held out (66.4%) is the honest generalisation gap: the fresh posts contain
formats the development posts did not. Known v6 errors on the 3 Nov posts, left unfixed so the number
stays clean (v7 work, to be measured on a later snapshot):

- **Real time-charter requests are missed** (2 of 3): "Firm T/C Requirement", "Charter Period:",
  "Hire Idea: USD 10,000 PDPR" are not evidence yet; a tanker TC request with load/discharge ports was
  read as a voyage order.
- **"Time charter OR voyage" route requests with a required size** ("4/5K DWT") read as vessel offers.
- **Unseen label formats:** markdown "**Load Port:**", "L/Port:" / "D/port:", "Voyage: Basrah –
  Shandong", "Diach port" (typo), "N China TO Med".
- **Wrong record window:** in posts with two orders written as labelled blocks, cargo/quantity were
  taken from the second order; cargo cleaning keeps packaging words ("chopt Feldspar in bb",
  "ton jumbo bag sulphur").
- Liner vessel sizes written "MV DSX (DWT53k)" are missed or taken from the next vessel.

v6 changes (all from development-set analysis): records per vessel/cargo; Open Date, Cargo,
Quantity (broker shorthand "2-4000" = 2000-4000, "42-4500" = 4200-4500, "8k", "11.000 mts up to
17.000"), Laycan (labelled forms, "spot/ppt", prose "the laycan is ..."); vessel tables without
"open" ("MV FLOKI /09-11 NOV IZMIR"); "open home tonnage" no longer read as a port; hyphenated route
lines need capitalised ports ("On Monday - member panel" is not a route); liner posts ("MV X /
loading: ...") count as vessels seeking cargo; loading/discharge rates count as voyage evidence;
bracketed notes no longer hide a route line. Older version history:

| Version | dev (24) cat / fields | test (18) cat / fields | ext-dev (150) cat / fields | ext-test (150) cat / fields | False positives neg-dev / neg-test (300 each) | real-dev (42) cat / fields | real-test (42) cat / fields |
|---------|------|------|------|------|------|------|------|
| v0 keyword rules | 70.6% / 30.6% * | 55.6% / 32.4% | 24.7% / 6.7% | 30.0% / 8.0% | - | - | - |
| v1 weighted scoring | 100% / 36.1% * | 100% / 37.8% | - | - | - | - | - |
| v2 extractor rewrite | 100% / 100% | 100% / 100% | 24.7% / 6.7% | 30.0% / 8.0% | - | - | - |
| v3 prose + subject routes | 100% / 100% | 100% / 100% | 89.3% / 85.0% | 88.7% / 82.7% | 3 (1.0%) / 0 | - | - |
| v4 false-positive fixes | 100% / 100% | 100% / 100% | 89.3% / 85.0% | 88.7% / 82.7% | 0 / 0 | 42.9% / 23.9% | 57.1% / 28.6% |
| v5 broker-circular rules | 100% / 100% | 100% / 100% | 91.3% / 85.7% | 89.3% / 83.3% | 0 / 1 (0.3%) | 95.2% / 92.0% | **95.2% / 74.7%** |

\* measured when dev had 17 emails.

**v4 → v5 (real circulars).** v4 scored 100% on hand-written emails and 89% on MaritimEmails but
only 43-57% / 24-29% on real circulars: most cargo orders were UNKNOWN. Analysing real-dev showed
broker conventions the synthetic data never contained, all now handled by general rules:
a route on its own line ("Kandla / Subic Bay", "Orlivka - Marmara", "Misurata/1 Greece"), with
vessel-particulars lines such as "GRT / NRT" excluded; laytime terms that only occur in voyage
charters ("1500x/3000x", SHINC/SHEX, "ttl days"); a required DWT range meaning a cargo order
("Any Dwt 6-9,000"); vessels asking for cargo ("need named/rated cgo", "propose your firm cargoes",
"home tonnage", DWCC); European numbers ("7.331,1", "4299,59"), "18K", "SUMMER DEADWEIGHT";
open-port noise ("OPEN AT X ON 27", "open hatch", "OPEN @MARMARA"); more port labels ("Ld port",
"Port of Loading", "1SBP Bin Qasim", "Kandla or Mundra").

Real-test fields (74.7%) are well below real-dev (92.0%), so part of the real-dev gain is fitted to
real-dev's posts; quote the real-test number. Known v5 errors, found on the held-out sets and left
unfixed so those numbers stay honest (fix in v6, then measure on a fresh shipbroker.gr snapshot):
"current open **home tonnage**" gives "home tonnage…" as the open port (3 real-test posts); a
hyphenated prose line ("On Monday - member panel to…") counts as a route line, which caused the
neg-test false positive; vessel tables with no "open" keyword ("MV FLOKI /09-11 NOV IZMIR") have
no open port; liner posts ("MV X loading Tianjin / disport Jeddah, need cargo") are read as cargo
orders; only the first of several vessels or cargoes is extracted.

v4 fixed the three neg-dev false positives (all Enron energy-trading emails) with two general
rules: a single "Delivery ..." line now scores 2 instead of 3, so a TC needs at least two pieces
of evidence (energy emails have "Delivery point:" lines); and POL/POD only count in capitals
(lowercase "pol"/"pod" are ordinary words). 0/300 on neg-test means the false-positive rate is
probably below about 1% (rule of three: 3/300) on emails like these; 4 neg-dev emails still
score 2, one rule short of the threshold.

The v2 rows show why the external data matters: 100% on hand-written emails fell to 30% / 8% on
emails written by someone else. v3 adds general rules found by analysing ext-dev failures
("from X to Y" routes, subject-line routes, freight per MT, Incoterms, "freight"/"lumpsum",
excluding date ranges such as "from Monday to Friday"), and the ext-test score matches ext-dev.

### Comparison with an ML baseline

`eval/ml_baseline.py` trains TF-IDF (word 1-2 grams) + logistic regression (class-balanced) on
data disjoint from every held-out set: 605 MaritimEmails *train*-split first emails (CARGO VC),
603 Enron/SpamAssassin ham not used in the negatives sets (UNKNOWN), and the 24 dev emails
(the only TONNAGE/CARGO TC examples: 8 and 6). Exact duplicates of evaluation emails are dropped.

```
python eval/ml_baseline.py --maritimemails-train MaritimEmails/train.jsonl.gz --enron enron_test.jsonl --spamassassin easy_ham.tar.bz2
```

| Evaluation set (category accuracy) | n | Rules (v5) | TF-IDF + LR |
|------------------------------------|---|------------|-------------|
| test – hand-written, 4 classes     | 18  | 100%  | 94.4% |
| ext-test – MaritimEmails           | 150 | 89.3% | 100%  |
| neg-test – non-shipping            | 300 | 99.7% | 100%  |
| **real-test – real broker circulars** | 42 | **95.2%** | **54.8%** |
| stress – 10 emails that break the training data's style pattern (`eval/stress.json`) | 10 | 10/10 | 4/10 |

On real circulars the ML model recognised only 40% of TONNAGE posts across all sets (it had 8
TONNAGE training emails). Fairness note: the rules were tuned on real-dev (same source as
real-test); the ML model saw no real circulars. Both were scored on the same unseen real-test posts.

The ML model wins on ext-test, but that set comes from the same LLM generator as its training
data. The stress set shows why that number doesn't carry over: the model labelled **every polite,
modern non-shipping email** (a budget meeting, a flight booking, an order notice, a webinar
invite, a container booking) as CARGO VC. In training, all shipping emails were polished
LLM prose and all non-shipping emails were 2000-2003 Enron/mailing-list text, so it learned
*writing style* instead of *shipping content* (shortcut learning). It also missed a terse period
enquiry, having seen only 6 CARGO TC examples.

Caveat: the stress emails were written by the rule designer, so the rules' 10/10 is biased
upward; the ML failures are on emails with no shipping evidence at all, which is the point.

Conclusion: with little real labelled data, the rules are the safer choice; an ML model needs
hundreds of real emails from all four categories, with the same writing style in shipping and
non-shipping examples, before its scores mean anything.

### Testing on real emails

Real emails stay on your machine (`eval/real/` and `eval/real.json` are in `.gitignore`).

1. Put each email in `eval/real/emails/` as `.txt` or `.eml`, with names, phone numbers and
   email addresses removed.
2. Copy `eval/real_labels_template.csv` to `eval/real/labels.csv` and fill one row per email
   (category and expected fields) **before** running the app on them, so the labels are not
   influenced by the output.
3. Run `python eval/build_real.py` (it warns about labels that don't appear in the text and
   leftover email addresses or phone numbers), then
   `python eval/evaluate.py --data eval/real.json --split real --errors`.

`docs/user_interview.md` is a 15-minute question sheet for talking to a broker or operator.

### Limitations

- **Small real sample, one source.** 114 real circulars from one public board (two snapshots),
  mostly small general-cargo/bulk trades in the Med, Black Sea and Asia, with AI-drafted labels
  not yet checked by a domain expert. A broker's own inbox (larger ships, replies, forwarded threads)
  may differ. The held-out snapshot has 30 posts, so one error moves accuracy by about 3.3 points.
- **CARGO TC is barely tested.** Only 3 real posts are time-charter requests (2 missed by v6); the
  rest of CARGO TC testing is 10 hand-written emails.
- **Negatives are old and narrow.** Enron (2000-2002) and SpamAssassin (2002-2003) ham;
  no spam, newsletters from shipping companies, or non-chartering logistics email (courier,
  container booking), which are the likeliest real false positives in a broker's inbox.
- **Biased hand-written test.** `emails.json` test was written by the rule designer and exposed one bug that was
  then fixed, so it is not a clean held-out set.
- **One label per email.** A vessel offered for a specific cargo ("MV Ocean Star available for
  your crude from Houston to Rotterdam") is both TONNAGE and CARGO VC; 3 ext-test emails were
  labelled TONNAGE for this reason.
- **Label conventions.** "Hull" vs gold "Hull, UK" and "AG" vs "Arabian Gulf" count as wrong.
- **Missed formats.** Tonnage positions without "MV"/"DWT" ("Supramax open Kandla 5 Nov") are
  UNKNOWN; weak-evidence enquiries (only a route, no quantity or freight terms) are UNKNOWN.
- **Records.** Orders written one per line with the quantity on the same line ("20-25000 MT BGD RICE -
  1SP WCI/1-2SP MOZAMBIQUE - ...") are not split into records; only the first record's fields are
  scored against labels (record counts are scored separately).
- **Fields not extracted.** Freight and hire rates, commission, demurrage, vessel type and gear.

## AI assistance

An AI coding assistant (Claude) was used for code suggestions, evaluation scripts, and drafting
test labels. All design decisions, testing, and results were reviewed by the author.
