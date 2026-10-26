import argparse
import json
import os
import sys
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from classifier import classify_email
from extractor import extract_data

CATEGORIES = ["TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"]
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emails.json")


def normalize(value):
    # Case- and whitespace-insensitive only; separators like ": " still count as wrong.
    return " ".join(str(value).upper().split())


def load_examples(split):
    with open(DATA_PATH, encoding="utf-8") as f:
        examples = json.load(f)
    if split != "all":
        examples = [e for e in examples if e["split"] == split]
    return examples


def evaluate(examples):
    confusion = defaultdict(Counter)
    field_stats = defaultdict(Counter)
    spurious = 0
    fully_correct = 0
    errors = []

    for ex in examples:
        predicted = classify_email(ex["text"])
        fields = extract_data(ex["text"], predicted)
        confusion[ex["category"]][predicted] += 1

        problems = []
        if predicted != ex["category"]:
            problems.append(f"category: expected {ex['category']}, got {predicted}")

        for name, gold in ex["fields"].items():
            if name not in fields:
                field_stats[name]["missing"] += 1
                problems.append(f"{name}: missing (expected {gold!r})")
            elif normalize(fields[name]) == normalize(gold):
                field_stats[name]["correct"] += 1
            else:
                field_stats[name]["wrong"] += 1
                problems.append(f"{name}: expected {gold!r}, got {fields[name]!r}")

        for name in fields:
            if name not in ex["fields"]:
                spurious += 1
                problems.append(f"{name}: spurious {fields[name]!r}")

        if problems:
            errors.append((ex, problems))
        else:
            fully_correct += 1

    return confusion, field_stats, spurious, fully_correct, errors


def pct(num, den):
    return f"{100 * num / den:5.1f}%" if den else "  n/a"


def report(examples, confusion, field_stats, spurious, fully_correct, errors, show_errors):
    n = len(examples)
    correct = sum(confusion[c][c] for c in CATEGORIES)
    print(f"Examples: {n}")
    print(f"\n== Classification ==")
    print(f"Accuracy: {correct}/{n} = {pct(correct, n)}")

    print(f"\n{'Category':<10} {'Prec':>7} {'Recall':>7} {'F1':>7} {'Support':>8}")
    f1s = []
    for c in CATEGORIES:
        tp = confusion[c][c]
        pred_total = sum(confusion[g][c] for g in CATEGORIES)
        gold_total = sum(confusion[c].values())
        p = tp / pred_total if pred_total else 0.0
        r = tp / gold_total if gold_total else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        if gold_total:
            f1s.append(f1)
        print(f"{c:<10} {p:7.2f} {r:7.2f} {f1:7.2f} {gold_total:8}")
    print(f"Macro F1 (over categories present): {sum(f1s) / len(f1s):.2f}" if f1s else "")

    print("\nConfusion matrix (rows = expected, cols = predicted)")
    print(" " * 10 + "".join(f"{c:>10}" for c in CATEGORIES))
    for g in CATEGORIES:
        print(f"{g:<10}" + "".join(f"{confusion[g][c]:>10}" for c in CATEGORIES))

    print("\n== Field extraction (end-to-end, uses predicted category) ==")
    print(f"{'Field':<16} {'Correct':>8} {'Wrong':>6} {'Missing':>8} {'Accuracy':>9}")
    total_correct = total = 0
    for name in sorted(field_stats):
        s = field_stats[name]
        count = s["correct"] + s["wrong"] + s["missing"]
        total_correct += s["correct"]
        total += count
        print(f"{name:<16} {s['correct']:>8} {s['wrong']:>6} {s['missing']:>8} {pct(s['correct'], count):>9}")
    print(f"Overall field accuracy: {total_correct}/{total} = {pct(total_correct, total)}")
    print(f"Spurious fields (predicted but not in gold): {spurious}")
    print(f"\nEmails fully correct (category + all fields, nothing spurious): {fully_correct}/{n} = {pct(fully_correct, n)}")

    if show_errors and errors:
        print("\n== Errors ==")
        for ex, problems in errors:
            print(f"\n[{ex['id']}] {ex.get('note', '')}")
            for p in problems:
                print(f"  - {p}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate the email classifier and extractor.")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--errors", action="store_true", help="list every failing example")
    args = parser.parse_args()

    examples = load_examples(args.split)
    print(f"Split: {args.split}")
    report(examples, *evaluate(examples), args.errors)


if __name__ == "__main__":
    main()
