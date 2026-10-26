# MaritimEmails attribution

`maritimemails_ext-dev.json` and `maritimemails_ext-test.json` contain material adapted from:

Kevin Bruendler and Simon Clematide. 2026. *MaritimEmails: A Synthetic Dataset for Maritime
Chartering Correspondence.* Proceedings of LREC 2026, pages 7556–7567.
https://aclanthology.org/2026.lrec-1.599/

Dataset: https://github.com/ZurichNLP/MaritimEmails
License: CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/). Non-commercial use only.

All MaritimEmails content is fully synthetic (LLM-generated); it contains no real people or business data.

## Changes made

- Took only the first email of each thread, as `Subject: <subject>\n\n<body>`.
- Kept threads whose `load_port` and `discharge_port` labels are non-empty, differ, and both
  appear verbatim in the first email body.
- Sampled 150 threads per split (seed 42) from the dataset's `dev.jsonl.gz` and `test.jsonl.gz`.
- Assigned category `CARGO VC` to every sample (this project's labelling decision, not the dataset's).
- Renamed fields: `load_port` -> `Loading Port`, `discharge_port` -> `Discharge Port`.

To rebuild:

```
git clone https://github.com/ZurichNLP/MaritimEmails
python eval/build_maritimemails.py MaritimEmails/dev.jsonl.gz --split ext-dev
python eval/build_maritimemails.py MaritimEmails/test.jsonl.gz --split ext-test
```
