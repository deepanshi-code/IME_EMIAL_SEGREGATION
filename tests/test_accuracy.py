import os
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from evaluate import CATEGORIES, evaluate, load_examples

EVAL = os.path.join(ROOT, "eval")

# Floors at (or just under) the v6 results on the committed datasets. A change that drops below
# them fails CI. Real broker posts and the non-shipping corpora are not committed, so they are
# checked locally with eval/evaluate.py instead.
FLOORS = [
    ("emails.json", "dev", 1.00, 1.00),
    ("emails.json", "test", 1.00, 1.00),
    ("maritimemails_ext-dev.json", "ext-dev", 0.91, 0.85),
    ("maritimemails_ext-test.json", "ext-test", 0.89, 0.83),
    ("stress.json", "stress", 1.00, None),
]


def scores(name, split):
    examples = load_examples(split, os.path.join(EVAL, name))
    confusion, field_stats, *_ = evaluate(examples)
    category = sum(confusion[c][c] for c in CATEGORIES) / len(examples)
    total = sum(sum(s.values()) for s in field_stats.values())
    fields = sum(s["correct"] for s in field_stats.values()) / total if total else None
    return category, fields


class AccuracyFloors(unittest.TestCase):
    def test_floors(self):
        for name, split, category_floor, field_floor in FLOORS:
            with self.subTest(split=split):
                category, fields = scores(name, split)
                self.assertGreaterEqual(category, category_floor - 1e-9)
                if field_floor is not None:
                    self.assertGreaterEqual(fields, field_floor - 1e-9)


if __name__ == "__main__":
    unittest.main()
