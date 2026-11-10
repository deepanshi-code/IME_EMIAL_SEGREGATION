# Evaluation

How the classifier and extractor were measured, version by version. The headline numbers are in the
[README](../README.md); this page has the datasets, protocol, full results, the ML comparison and
known errors. Commands assume you are in the project root.

## Confidence levels

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

## Running the evaluation

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

## Datasets

| File | Split | Size | Source |
|------|-------|------|--------|
| `eval/emails.json` | dev / test | 24 / 18 | Hand-written broker-style emails covering all four categories |
| `eval/maritimemails_ext-dev.json` | ext-dev | 150 | MaritimEmails dev split (first email of each thread) |
| `eval/maritimemails_ext-test.json` | ext-test | 150 | MaritimEmails test split (first email of each thread) |
| `eval/negatives_neg-dev.json` | neg-dev | 300 | Non-shipping emails: 150 Enron ham + 150 SpamAssassin easy_ham |
| `eval/negatives_neg-test.json` | neg-test | 300 | Same sources, disjoint emails |
| `eval/real/shipbroker_gr.json` | real-dev / real-test | 42 / 42 | **Real broker circulars** from shipbroker.gr, 26 Oct 2026 (see below); development data since v6 |
| `eval/real/shipbroker_gr_20261103.json` | real-20261103 | 30 | Fresh shipbroker.gr snapshot, 3 Nov 2026: posts after 26 Oct that are not reposts. v6 held-out test; development data since v7 |
| `eval/real/shipbroker_gr_20261110.json` | real-20261110 | 16 | Fresh snapshot, 10 Nov 2026: posts after 3 Nov, not reposts of any earlier snapshot or of each other. **v7 held-out test** |

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
python eval/build_shipbroker_gr.py parse --snapshot 20261110 --cargo-html cargo.html --vessel-html vessel.html
python eval/build_shipbroker_gr.py merge --snapshot 20261110
python eval/evaluate.py --data eval/real/shipbroker_gr_20261110.json --split all --errors
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

## Results

**Latest headline (v7, 16 fresh real broker circulars from 10 Nov 2026, never seen during
development): 93.8% category accuracy (15/16, 95% CI 72-99%), 83.1% field accuracy (59/71, CI
73-90%), 60.0% exact record counts (9/15, CI 36-80%).** The samples are small, so the ranges are
wide; quote the ranges, not only the point values.

**The main lesson from v7: in-sample gains did not transfer.** v7 was developed on the 26 Oct and
3 Nov posts and lifted 3 Nov field accuracy from 66.4% to 89.9%. On the fresh 10 Nov posts the
frozen **v6 rules score almost the same as v7** (93.8% / 81.7% / 60.0% vs 93.8% / 83.1% / 60.0%):
the formats fixed in v7 barely occur in the new posts, which bring their own (below). The 10 Nov
posts are also easier than the 3 Nov ones (v6 field accuracy 81.7% vs 66.4%), so the snapshots
differ a lot from week to week. Rule fixes from one snapshot are not evidence of improvement; only
the next snapshot is.

| Version | real 26 Oct + 3 Nov (development) cat / fields / records | **real 10 Nov, 16 (held out)** cat / fields / records | ext-test (150) cat / fields | False positives neg-test (300) |
|---------|------|------|------|------|
| v6 | 98.8% / 93.3% / 86.9% and 83.3% / 66.4% / 96.3% | 93.8% / 81.7% / 60.0% | 89.3% / 83.3% | 1 (0.3%) |
| v7 | 98.8% / 93.3% / 86.9% and 93.3% / 89.9% / 96.3% | **93.8% / 83.1% / 60.0%** | 89.3% / 83.3% | 1 (0.3%) |

v7 changes (developed on 26 Oct and 3 Nov posts only; rules frozen in commit `a396ff2` before the
10 Nov posts were labelled): time-charter evidence ("Firm T/C Requirement", "Time Charter offers",
"Charter Type: TC", daily hire "USD 10,000 PDPR", periods in years); a line offering "time charter
OR voyage" is not forced to TC; a required size "4/5K DWT" counts as a cargo order; labels behind
markdown bold and bullets ("- **Load Port:**"), "L/Port", "D/port", "Disch/Diach port", "Voyage: X –
Y" (country dropped); "5k 10% Wheat", "mtons", load/discharge guarantees ("3k load gtee") not taken
as the quantity, barrels/CBM/units not read as tonnes; sizes run together ("MV DSX (DWT53k)"),
"MV.SL GOLDEN FORTUNE", "9-10TH,NOV"; packaging words dropped from cargo ("1 ton jumbo bag sulphur",
"in bb").

Known v7 errors on the 10 Nov posts, left unfixed so the number stays clean (v8 work, to be measured
on a later snapshot):

- **Record counts (9/15)** are the weak spot: vessels listed with particulars but no open position
  (5 vessels, 1 record); "On Period" vessels; orders separated only by "==" or blank lines; one COA
  post split into two records.
- **Number formats:** apostrophe thousands ("3'000-25'000 mts" read as 0); a COA total (300,000 t)
  taken instead of the per-shipment quantity (40-45,000 t).
- **Labels without colons** ("Load port Busan New Port" cut to "Busan New"; "Cargo Power plant
  equipment parts" missed, "packages" taken instead); "Cargo: abt 5,000 MT Rebars" (cargo after
  the quantity inside a label) missed.
- **A time-charter request without labels** ("12 months t/c period", "Delivery: Marmara") read as a
  voyage order because it also offers a voyage basis.
- Laycan "Any November dates" shortened to "November"; padded bullet labels ("• Laycan: 1st
  shipment DEC") missed.

**Two data issues found while building the 10 Nov set.** (1) The same circular is often posted on
several days. The 3 Nov set contains one such pair (cargo-04 / cargo-22, 91% similar), so the v6
3 Nov numbers count one post twice; it is kept as published. From the 10 Nov snapshot on, near-
duplicates within a snapshot are removed (earliest kept; cargo-08 dropped as a 99% repost of
cargo-12) and posts must not repeat any earlier snapshot, not only the first. (2) The anonymiser
masks phone numbers and emails but missed a personal name in one signature and masked one
quantity range as a phone number (cargo-02, so that quantity is not labelled). The real posts stay
out of the repository for this reason.

**Earlier headline (v6, 30 fresh real broker circulars from 3 Nov): 83.3% category accuracy (25/30,
CI 66-93%), 66.4% field accuracy (79/119, CI 58-74%), 96.3% exact record counts (26/27).** The v5
rules score 76.7% / 31.9% on the same posts. Since v7 the 3 Nov posts are development data.

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

## Comparison with an ML baseline

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

## Testing on real emails

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

## Limitations

- **Small real sample, one source.** 130 real circulars from one public board (three snapshots),
  mostly small general-cargo/bulk trades in the Med, Black Sea and Asia, with AI-drafted labels
  not yet checked by a domain expert. A broker's own inbox (larger ships, replies, forwarded threads)
  may differ. The latest held-out snapshot has only 16 posts, so one error moves category accuracy
  by about 6 points; the 95% intervals above are the honest summary.
- **CARGO TC is barely tested.** Only 4 real posts are time-charter requests (3 in the 3 Nov set,
  now development data, and 1 in the 10 Nov set, missed by v7); the rest of CARGO TC testing is
  hand-written emails.
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
