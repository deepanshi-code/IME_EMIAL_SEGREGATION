import argparse
import email
import email.policy
import json
import os
import random
import tarfile

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_CHARS = 4000


def enron_ham(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["label_text"] == "ham" and row["text"].strip():
                yield f"enron-{row['message_id']}", f"Subject: {row['subject']}\n\n{row['text']}"


def plain_body(message):
    part = message.get_body(preferencelist=("plain",))
    if part is None:
        return ""
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        return part.get_payload(decode=True).decode("latin-1", errors="replace")


def spamassassin_ham(path):
    with tarfile.open(path, "r:bz2") as tar:
        for member in tar:
            if not member.isfile() or os.path.basename(member.name) == "cmds":
                continue
            raw = tar.extractfile(member).read()
            message = email.message_from_bytes(raw, policy=email.policy.default)
            body = plain_body(message)
            if body.strip():
                yield f"sa-{os.path.basename(member.name).split('.')[0]}", f"Subject: {message['subject'] or ''}\n\n{body}"


def main():
    parser = argparse.ArgumentParser(description="Sample non-shipping (ham) emails as UNKNOWN examples.")
    parser.add_argument("--enron", required=True, help="path to SetFit/enron_spam test.jsonl")
    parser.add_argument("--spamassassin", required=True, help="path to 20030228_easy_ham.tar.bz2")
    parser.add_argument("--n", type=int, default=300, help="emails per source")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    splits = {"neg-dev": [], "neg-test": []}
    for source, rows in (("enron", enron_ham(args.enron)), ("spamassassin", spamassassin_ham(args.spamassassin))):
        rows = sorted(rows)
        rng.shuffle(rows)
        for i, (email_id, text) in enumerate(rows[: args.n]):
            split = "neg-dev" if i % 2 == 0 else "neg-test"
            splits[split].append({
                "id": email_id,
                "split": split,
                "category": "UNKNOWN",
                "text": text if len(text) <= MAX_CHARS else text[:MAX_CHARS].rsplit(None, 1)[0],
                "fields": {},
                "note": source,
            })

    for split, examples in splits.items():
        out_path = os.path.join(EVAL_DIR, f"negatives_{split}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(examples, f, indent=2, ensure_ascii=False)
        print(f"wrote {len(examples)} to {out_path}")


if __name__ == "__main__":
    main()
