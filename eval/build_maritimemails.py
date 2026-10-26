import argparse
import gzip
import json
import os
import random

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))


def first_email_text(thread):
    email = thread["email_chain"][0]
    return f"Subject: {email['subject']}\n\n{email['body']}"


def usable(thread):
    labels = thread["labels"]
    load, discharge = labels.get("load_port", "").strip(), labels.get("discharge_port", "").strip()
    if not load or not discharge or load.lower() == discharge.lower():
        return False
    body = thread["email_chain"][0]["body"].lower()
    return load.lower() in body and discharge.lower() in body


def main():
    parser = argparse.ArgumentParser(description="Sample MaritimEmails first emails into the eval format.")
    parser.add_argument("source", help="path to a MaritimEmails split, e.g. dev.jsonl.gz")
    parser.add_argument("--split", required=True, help="split name to store, e.g. ext-dev or ext-test")
    parser.add_argument("--n", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with gzip.open(args.source, "rt", encoding="utf-8") as f:
        threads = [json.loads(line) for line in f]
    candidates = sorted((t for t in threads if usable(t)), key=lambda t: t["thread_id"])
    random.Random(args.seed).shuffle(candidates)

    examples = []
    for thread in candidates[: args.n]:
        labels = thread["labels"]
        examples.append({
            "id": thread["thread_id"],
            "split": args.split,
            "category": "CARGO VC",
            "text": first_email_text(thread),
            "fields": {
                "Loading Port": labels["load_port"].strip(),
                "Discharge Port": labels["discharge_port"].strip(),
            },
            "note": f"{thread['generation_method']} / {thread['model']}",
        })

    out_path = os.path.join(EVAL_DIR, f"maritimemails_{args.split}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)
    print(f"{len(candidates)} usable threads, wrote {len(examples)} to {out_path}")


if __name__ == "__main__":
    main()
