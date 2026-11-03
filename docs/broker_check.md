# Broker check: validating the vessel–cargo matches (40 minutes)

**Goal:** find out whether the app's suggested vessels are ones a real broker would consider, and
collect evidence for the presentation. Until this is done, the matches are an untested heuristic.

**Who:** a shipbroker, chartering manager or operator who works with dry cargo/general cargo
(the circulars are mostly 2,000–30,000 t trades in the Med, Black Sea and Asia). One person is
useful; two or three independent people are much better.

## Before the session

1. Build a fresh sheet (it uses the real shipbroker.gr posts on your laptop):
   ```
   python eval/build_match_review.py
   ```
   This writes `eval/real/match_review_sheet.xlsx` (give this to the broker) and
   `eval/real/match_review_key.json` (**keep this to yourself**: it says which rows are the
   app's top picks and which are controls).
2. Check the sheet opens and the Verdict column has a dropdown.
3. Open https://ime-email-segregation.streamlit.app/ 10 minutes early (free apps sleep).
4. Bring: laptop with the app open, the sheet (on the laptop or printed), this guide, a notebook.

**Consent and privacy:** ask before recording or quoting the person, and whether you may name
their company (default: no). Do not ask for or record their clients' names or deal terms. The
sheet only contains public board posts, with no contact details.

## Script

### 1. Introduction (3 min)
> "I've built a tool that reads chartering emails and suggests vessels for cargo orders. I want to
> know whether its suggestions make sense to someone who does this for real. There are no right
> answers; please be blunt."

Do **not** say that some rows are controls, how the score works, or which rows you think are good.

### 2. Blind sheet (15–20 min)
Hand over the sheet. It has 12 cargo orders, each with 4 vessels in random order.
> "For each vessel, would you propose it for that cargo? Good fit, Possible, or Not workable,
> and a few words why if you can."

While they work:
- Don't explain rows or defend the app. If they ask what a field means, answer only that.
- Write down anything they say out loud ("this one's already fixed", "too old", "wrong area").
- If a row is unclear because the extraction is wrong (e.g. an odd open port), let them mark it
  Not workable and note "extraction error" in the comment.

### 3. Live demo (10 min)
Now show the app: Positions board → **Load demo board** → Matches. Pick a cargo, show the ranked
vessels and the "Why" text. In the Matches table they can set a **Verdict** per suggestion; at the
end use **Download verdicts CSV**. Ask:
1. "Is the ranking in the order you'd look at them?"
2. "What does the app ignore that you always check?" (e.g. distance, draft, gear, ice class,
   flag, charterers' restrictions, last cargo)
3. "Would a board like this save you time? Where would it fit in your day?"

### 4. Close (2 min)
Thank them, ask if you may contact them with one follow-up question, and if they could review the
*next* version on fresh posts.

## After the session

```
python eval/score_match_review.py path/to/their_filled_sheet.xlsx
```

It compares the broker's verdicts on the app's top picks with the controls:

- **Good fit rate** for the rank-1 vessel, the top 3, and the controls, each with a 95% interval;
- the gap between top-3 and control "Good fit" rates (treat under ~30 points as inconclusive with
  12 cargoes);
- every top pick the broker rejected, with their comment next to the app's reasons: this is the
  list of what to fix.

**How to report it** (example wording, fill in real numbers):
> "A broker judged 48 vessel–cargo pairs blind. They rated X of 36 of the app's top-3 suggestions
> a good fit, against Y of 12 low-ranked controls. Main reasons for rejection: …"

Report the result whichever way it goes. If top picks and controls score about the same, say so:
it means the ranking does not yet add value, and the broker's comments tell you why.

## Limits of this check

- One broker is one opinion; their trades may differ from the posts in the sheet.
- The posts are from late Oct–early Nov 2026, so dates are "as of" those posts; ask the broker to
  judge as if it were the posting date.
- Twelve cargoes give wide intervals; this is a sanity check, not a benchmark.
- Matching uses only dates, size, region and a tanker check; anything else the broker cares about
  is, by design, missing; their comments are the point.
