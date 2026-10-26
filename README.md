# IME Email Segregation

Install:
pip install -r requirements.txt

Run:
streamlit run app.py

## Evaluation

`eval/emails.json` holds 42 labeled emails (category + expected fields), split into
`dev` (24) and `test` (18). The emails are synthetic, written to resemble chartering
emails; replace or extend them with real (anonymised) emails before drawing conclusions.

python eval/evaluate.py --split dev --errors
python eval/evaluate.py --split test

Reports classification accuracy, per-category precision/recall/F1, a confusion matrix,
per-field extraction accuracy, spurious fields, and the share of fully correct emails.
Field values are compared case- and whitespace-insensitively; everything else must match exactly.

Iterate on the classifier using `dev` only. Run `test` rarely (e.g. once per milestone),
otherwise the rules end up tuned to the test emails and the score stops meaning anything.

Results:

| Version | Split | Category accuracy | Macro F1 | Field accuracy | Fully correct |
|---------|-------|-------------------|----------|----------------|---------------|
| v0 keyword rules | dev  | 70.6% (12/17) | 0.66 | 30.6% (11/36) | 23.5% (4/17) |
| v0 keyword rules | test | 55.6% (10/18) | 0.52 | 32.4% (12/37) | 22.2% (4/18) |
| v1 weighted scoring | dev  | 100% (17/17) | 1.00 | 36.1% (13/36) | 41.2% (7/17) |
| v1 weighted scoring | test | 100% (18/18) | 1.00 | 37.8% (14/37) | 38.9% (7/18) |
| v2 + extractor rewrite | dev (24) | 100% (24/24) | 1.00 | 100% (55/55) | 100% (24/24) |
| v2 + extractor rewrite | test | 100% (18/18) | 1.00 | 100% (37/37) | 100% (18/18) |

v1/v2 test scores are optimistic: the test emails were written by the same person who designed the
rules, so they are not truly unseen. In v2 the test split also exposed one bug ("Period enquiry"
taken as a duration) that was then fixed, so test is no longer a clean held-out set. Seven new
emails used to probe v2 were added to dev (t11-t13, v11, v12, c09, c10). A fresh test set of
real, anonymised emails is needed for a trustworthy number. Known v1 misses on new emails: tonnage positions with no
"MV"/"DWT" (e.g. "Supramax open Kandla 5 Nov") are UNKNOWN, and an email containing both a cargo
order and a vessel position gets only one label.
