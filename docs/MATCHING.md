# Positions board and matching

How vessel positions and cargo orders are stored, how matches are scored, and how to check the
matches with a broker. Back to the [README](../README.md).

## Positions board and privacy

`board.py` stores records in SQLite. By default the board is **in memory, one per browser session**,
so visitors of the public deployment never see each other's emails, and it is lost when the session
ends. To keep a board between runs on your own computer, set `POSITIONS_DB=positions.db` before
`streamlit run app.py`. Adding the same email twice adds nothing (records are keyed by email text and
position). Dates are turned into ranges by `dates.py` (e.g. "27-28/OCT", "mid Oct", "1-10/11",
"SPOT" = the next 7 days); the year is inferred from the email's date. It parses 106 of the 107
labelled laycans/open dates in the real posts; the other one ("Vsl date") has no date.

## Matching

`matching.py` scores each vessel–cargo pair (max +9):

| Check | Points | Rule |
|-------|--------|------|
| Dates | +3 / +2 / 0 / excluded | open dates overlap the laycan / opens up to 10 days before it / 11-30 days before / opens after the laycan ends, or more than 30 days before it (out of date) |
| Size | +3 / +1 / −1 / excluded | cargo is 70–95% of DWT (or 70–100% of DWCC, the cargo capacity, used when stated) / 40–70% (part cargo) / under 40% / too big |
| Location | +3 / +2 / +1 / 0 / −2 | open at the load port / same trading region / neighbouring region / unknown / far apart |
| Vessel type | −3 | liquid cargo (crude, fuel oil, vegoil, chemicals, LPG…) with a vessel not described as a tanker |

Regions come from `regions.py`, a hand-written table of 17 trading regions (Black Sea, Marmara/Aegean,
East Med, Continent/UK, Arabian Gulf, India/Pakistan, SE Asia, Far East, …) with their neighbours and
the port/area names brokers use. It covers 109 of the 110 port/area names in the real labels, but
it was written with those names in view, so coverage of other inboxes will be lower; unknown ports
score 0, not a penalty. Weak matches (score 0 or below) are hidden unless switched on.

Brokers repost the same vessel with new dates, so matching uses only the latest post of each named
vessel (`matching.latest_positions()`); unnamed and "TBN" vessels are all kept.

**Matching is not validated yet.** There is no ground truth for "the right vessel for this cargo";
the rules are standard broker considerations (dates, size, position), but distances, vessel type
and gear, draft and port restrictions, and commercial terms are not modelled. Treat matches as a
shortlist to check.

## Broker check (blind review of the matches)

`docs/broker_check.md` is a 40-minute session plan for validating the matches with a broker.

```
python eval/build_match_review.py          # sheet + hidden key in eval/real/ (not committed)
python eval/score_match_review.py filled_sheet.xlsx
```

`build_match_review.py` loads the real shipbroker.gr posts, picks 12 cargo orders with a date,
quantity and load port, and lists for each the app's **top 3 vessels plus 1 control** (a workable
vessel ranked well below them), shuffled, with scores hidden. Only vessels with a stated open port
are used, so every row can be judged. The broker marks each pair Good fit / Possible / Not workable.
`score_match_review.py` then compares top picks with controls (with 95% intervals; 12 cargoes give
wide ones) and lists every top pick the broker rejected next to the app's reasons. If top picks are
not rated clearly above controls, the ranking does not add value yet, and the comments say why.

In the app, the Matches tab can also record a verdict and comment per suggestion during a live
session and download them as `match_verdicts.csv`.

**Status: no broker has reviewed the matches yet.**
