import argparse
import gzip
import json
import os
import random
import sys
from collections import Counter

sys.dont_write_bytecode = True
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(EVAL_DIR, ".."))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from build_maritimemails import first_email_text, usable
from build_negatives import enron_ham, spamassassin_ham
from classifier import classify_email

CATEGORIES = ["TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"]
EVAL_SETS = [
    ("test (hand-written, 4 classes)", "emails.json", "test"),
    ("ext-test (MaritimEmails, CARGO VC)", "maritimemails_ext-test.json", "ext-test"),
    ("neg-test (non-shipping, UNKNOWN)", "negatives_neg-test.json", "neg-test"),
]
if os.path.exists(os.path.join(EVAL_DIR, "real", "shipbroker_gr.json")):
    EVAL_SETS.append(("real-test (broker circulars)", os.path.join("real", "shipbroker_gr.json"), "real-test"))


def load(name, split):
    with open(os.path.join(EVAL_DIR, name), encoding="utf-8") as f:
        return [e for e in json.load(f) if e["split"] == split]


def training_data(args, rng):
    texts, labels = [], []

    for e in load("emails.json", "dev"):
        texts.append(e["text"])
        labels.append(e["category"])

    with gzip.open(args.maritimemails_train, "rt", encoding="utf-8") as f:
        threads = sorted((t for t in map(json.loads, f) if usable(t)), key=lambda t: t["thread_id"])
    rng.shuffle(threads)
    for thread in threads[: args.n]:
        texts.append(first_email_text(thread))
        labels.append("CARGO VC")

    held_out = {e["id"] for s in ("neg-dev", "neg-test") for e in load(f"negatives_{s}.json", s)}
    for rows in (enron_ham(args.enron), spamassassin_ham(args.spamassassin)):
        rows = sorted((email_id, text) for email_id, text in rows if email_id not in held_out)
        rng.shuffle(rows)
        for _, text in rows[: args.n // 2]:
            texts.append(text[:4000])
            labels.append("UNKNOWN")

    return texts, labels


def main():
    parser = argparse.ArgumentParser(description="TF-IDF + logistic regression baseline vs the rule classifier.")
    parser.add_argument("--maritimemails-train", required=True, help="MaritimEmails train.jsonl.gz")
    parser.add_argument("--enron", required=True, help="SetFit/enron_spam test.jsonl")
    parser.add_argument("--spamassassin", required=True, help="20030228_easy_ham.tar.bz2")
    parser.add_argument("--n", type=int, default=600, help="CARGO VC and UNKNOWN training emails each")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    texts, labels = training_data(args, random.Random(args.seed))
    eval_texts = {e["text"] for _, name, split in EVAL_SETS for e in load(name, split)}
    kept = [(t, l) for t, l in zip(texts, labels) if t not in eval_texts]
    print(f"Dropped {len(texts) - len(kept)} training emails identical to an evaluation email")
    texts, labels = [t for t, _ in kept], [l for _, l in kept]
    print("Training emails per class:", dict(Counter(labels)))

    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        LogisticRegression(class_weight="balanced", max_iter=2000),
    )
    model.fit(texts, labels)

    print(f"\n{'Evaluation set':<38} {'n':>4} {'Rules':>8} {'TF-IDF+LR':>10}")
    per_class = {"Rules": Counter(), "TF-IDF+LR": Counter(), "total": Counter()}
    for title, name, split in EVAL_SETS:
        examples = load(name, split)
        gold = [e["category"] for e in examples]
        rules = [classify_email(e["text"]) for e in examples]
        ml = list(model.predict([e["text"] for e in examples]))
        rules_ok = sum(g == p for g, p in zip(gold, rules))
        ml_ok = sum(g == p for g, p in zip(gold, ml))
        print(f"{title:<38} {len(examples):>4} {100 * rules_ok / len(gold):7.1f}% {100 * ml_ok / len(gold):9.1f}%")
        for g, r, m in zip(gold, rules, ml):
            per_class["total"][g] += 1
            per_class["Rules"][g] += g == r
            per_class["TF-IDF+LR"][g] += g == m

    print(f"\nRecall per category, all evaluation sets combined")
    print(f"{'Category':<10} {'n':>4} {'Rules':>8} {'TF-IDF+LR':>10}")
    for c in CATEGORIES:
        n = per_class["total"][c]
        print(f"{c:<10} {n:>4} {100 * per_class['Rules'][c] / n:7.1f}% {100 * per_class['TF-IDF+LR'][c] / n:9.1f}%")

    stress = load("stress.json", "stress")
    print(f"\nStress test: emails that break the training data's style pattern")
    print(f"{'id':<5} {'expected':<9} {'Rules':<9} {'TF-IDF+LR':<9} note")
    totals = Counter()
    for e in stress:
        rule, ml = classify_email(e["text"]), model.predict([e["text"]])[0]
        totals["Rules"] += rule == e["category"]
        totals["TF-IDF+LR"] += ml == e["category"]
        print(f"{e['id']:<5} {e['category']:<9} {rule:<9} {ml:<9} {e['note']}")
    print(f"Correct: Rules {totals['Rules']}/{len(stress)}, TF-IDF+LR {totals['TF-IDF+LR']}/{len(stress)}")


if __name__ == "__main__":
    main()
