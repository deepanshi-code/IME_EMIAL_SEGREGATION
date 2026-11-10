import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402
from pipeline import process_email  # noqa: E402

VESSEL = "MV SEA HAWK 58,000 DWT\nOPEN TIANJIN 10-12 DEC\nPLS OFFER SUITABLE CARGO"
CARGO = "Pls offer firm for;\nMundra / Chittagong\n12,000 mt bagged sugar\n5-10 Dec\n2000x / 1500x"


def board_with(*items):
    conn = board.connect()
    board.add(conn, [(source, text, process_email(text), received) for source, text, received in items])
    return conn


class Corrections(unittest.TestCase):
    def test_update_recomputes_derived_columns(self):
        conn = board_with(("a", CARGO, date(2026, 11, 1)))
        key = board.frame(conn)["key"][0]
        board.update(conn, key, {"quantity": "20,000-25,000", "laycan": "20-25 Nov", "loading_port": "Haldia"})
        row = board.records(board.frame(conn))[0]
        self.assertEqual((row["qty_min"], row["qty_max"]), (20000, 25000))
        self.assertEqual((row["start"], row["end"]), ("2026-11-20", "2026-11-25"))
        self.assertEqual(row["region"], "India/Pakistan")

    def test_update_rejects_bad_numbers_and_unknown_columns(self):
        conn = board_with(("a", VESSEL, date(2026, 11, 1)))
        key = board.frame(conn)["key"][0]
        with self.assertRaises(ValueError):
            board.update(conn, key, {"vessel_size": "about fifty thousand"})
        with self.assertRaises(ValueError):
            board.update(conn, key, {"region": "Mars"})
        self.assertEqual(board.records(board.frame(conn))[0]["vessel_size"], 58000)


class BackupRestore(unittest.TestCase):
    def test_round_trip_through_json(self):
        conn = board_with(("a", VESSEL, date(2026, 11, 1)), ("b", CARGO, date(2026, 11, 1)))
        data = json.loads(json.dumps(board.backup(conn)))
        fresh = board.connect()
        self.assertEqual(board.restore(fresh, data), 2)
        self.assertEqual(board.restore(fresh, data), 0)  # restoring twice adds nothing
        self.assertEqual(board.records(board.frame(fresh)), board.records(board.frame(conn)))

    def test_rejects_other_json(self):
        with self.assertRaises(ValueError):
            board.restore(board.connect(), [{"key": "x"}])

    def test_old_board_file_gets_new_columns(self):
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        old = sqlite3.connect(path)
        old.execute("CREATE TABLE records (key TEXT UNIQUE, source TEXT, category TEXT)")
        old.commit()
        old.close()
        conn = board.connect(path)
        board.add(conn, [("a", VESSEL, process_email(VESSEL), date(2026, 11, 1))])
        self.assertEqual(board.records(board.frame(conn))[0]["text"], VESSEL)
        conn.close()


class Reposts(unittest.TestCase):
    def test_same_vessel_from_two_brokers_is_one_group(self):
        repost = VESSEL.replace("MV SEA HAWK", "M/V SEA HAWK") + "\nBRGDS, ANOTHER BROKER"
        conn = board_with(("a", VESSEL, date(2026, 11, 1)), ("b", repost, date(2026, 11, 3)))
        counts, latest = board.repost_groups(board.frame(conn))
        rows = board.records(board.frame(conn))
        self.assertEqual(sorted(counts.values()), [2, 2])
        newest = [r["source"] for r in rows if latest[r["key"]]]
        self.assertEqual(newest, ["b"])

    def test_different_cargoes_on_same_route_stay_apart(self):
        bigger = CARGO.replace("12,000 mt", "40,000 mt")
        conn = board_with(("a", CARGO, date(2026, 11, 1)), ("b", bigger, date(2026, 11, 1)),
                          ("c", CARGO + "\nRgds", date(2026, 11, 2)))
        counts, _ = board.repost_groups(board.frame(conn))
        by_source = {r["source"]: counts[r["key"]] for r in board.records(board.frame(conn))}
        self.assertEqual(by_source, {"a": 2, "b": 1, "c": 2})


if __name__ == "__main__":
    unittest.main()
