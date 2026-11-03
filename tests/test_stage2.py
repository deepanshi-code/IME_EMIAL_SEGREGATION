import os
import sys
import unittest
from datetime import date
from email.message import EmailMessage

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import board
import matching
from dates import parse_range
from inbox import read_imap, read_mbox
from pipeline import process_email
from regions import proximity, region_of

REF = date(2026, 10, 26)


class Dates(unittest.TestCase):
    def test_formats(self):
        cases = {
            "12-14 Nov": (date(2026, 11, 12), date(2026, 11, 14)),
            "27-28/OCT": (date(2026, 10, 27), date(2026, 10, 28)),
            "nov 1-10": (date(2026, 11, 1), date(2026, 11, 10)),
            "sep 28-oct 5": (date(2026, 9, 28), date(2026, 10, 5)),
            "29 OCT - 05 NOV": (date(2026, 10, 29), date(2026, 11, 5)),
            "1-10/11": (date(2026, 11, 1), date(2026, 11, 10)),
            "31.10/2.11": (date(2026, 10, 31), date(2026, 11, 2)),
            "MID OF OCT": (date(2026, 10, 11), date(2026, 10, 20)),
            "First half of November": (date(2026, 11, 1), date(2026, 11, 15)),
            "SPOT": (REF, date(2026, 11, 2)),
            "20 nov onwards": (date(2026, 11, 20), date(2026, 12, 4)),
        }
        for text, expected in cases.items():
            self.assertEqual(parse_range(text, REF), expected, text)
        self.assertIsNone(parse_range("Vsl date", REF))

    def test_year_rolls_over(self):
        self.assertEqual(parse_range("05 Jan", date(2026, 12, 20)), (date(2027, 1, 5), date(2027, 1, 5)))
        self.assertEqual(parse_range("27 Dec", date(2027, 1, 2)), (date(2026, 12, 27), date(2026, 12, 27)))


class Regions(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(region_of("Izmail"), "Black Sea")
        self.assertEqual(region_of("East Coast UK"), "Continent/UK")
        self.assertEqual(region_of("1sp Pakistan"), "India/Pakistan")
        self.assertIsNone(region_of("Atlantis"))

    def test_proximity(self):
        self.assertEqual(proximity("Kandla", "kandla"), 3)
        self.assertEqual(proximity("Constanta", "Izmail"), 2)
        self.assertEqual(proximity("Marmara", "Varna"), 1)
        self.assertEqual(proximity("Rotterdam", "Paradip"), -1)
        self.assertEqual(proximity("Atlantis", "Varna"), 0)


VESSELS = ("Please propose cargoes for our home tonnage:\n"
           "M/V SEA HAWK : 5,200 DWT – Open at Constanta 12-14 Nov.\n"
           "M/V BLUE ARROW : 3,800 DWT – Open at Izmir 15-17 Nov.\n"
           "M/V FAR STAR : 6,000 DWT – Open at Singapore 12-14 Nov.")
CARGO = "Pls offer firm for;\nIzmail / Marmara\n4,500 mt wheat in bulk\n13-16 Nov\n1000x / 1000x\n2.5% ttl"


class BoardAndMatching(unittest.TestCase):
    def setUp(self):
        self.conn = board.connect()
        items = [("vessels", VESSELS, process_email(VESSELS), REF), ("cargo", CARGO, process_email(CARGO), REF)]
        self.added = board.add(self.conn, items)
        self.again = board.add(self.conn, items)

    def tearDown(self):
        self.conn.close()

    def test_board(self):
        self.assertEqual(self.added, 4)
        self.assertEqual(self.again, 0)
        self.assertEqual(len(board.search(self.conn, category="TONNAGE")), 3)
        self.assertEqual(len(board.search(self.conn, region="Black Sea")), 2)
        self.assertEqual(len(board.search(self.conn, text="arrow")), 1)
        self.assertEqual(len(board.search(self.conn, category="TONNAGE", min_size=5000)), 2)

    def test_matching(self):
        vessels = board.records(board.search(self.conn, category="TONNAGE"))
        cargo = board.records(board.search(self.conn, category="CARGO VC"))[0]
        ranked = matching.rank(cargo, vessels)
        names = [v["vessel_name"] for _, v, _ in ranked]
        # SEA HAWK: same region, dates overlap, 4,500 t of 5,200 DWT. BLUE ARROW is too small.
        self.assertEqual(names[0], "SEA HAWK")
        self.assertNotIn("BLUE ARROW", names)
        self.assertLess(ranked[-1][0], ranked[0][0])

    def test_liquid_cargo_needs_tanker(self):
        score, reasons = matching.score_pair(
            {"vessel_size": 6000, "start": "2026-11-12", "end": "2026-11-14", "open_port": "Izmail", "source": ""},
            {"cargo": "vegoil", "qty_max": 4500, "start": "2026-11-13", "end": "2026-11-16", "loading_port": "Izmail"})
        self.assertIn("liquid cargo needs a tanker; check the vessel type", reasons)


class MatchingRules(unittest.TestCase):
    def test_stale_position_left_out(self):
        score, reasons = matching.score_pair(
            {"vessel_size": 6000, "start": "2026-09-27", "end": "2026-09-27", "open_port": "Constanta"},
            {"qty_max": 4000, "start": "2026-11-10", "end": "2026-11-15", "loading_port": "Constanta"})
        self.assertIsNone(score)
        self.assertIn("out of date", reasons[0])

    def test_latest_position_per_vessel(self):
        vessels = [{"vessel_name": "AGN LAGERTHA", "received": "2026-10-19", "open_date": "03-05 NOV"},
                   {"vessel_name": "agn lagertha", "received": "2026-11-02", "open_date": "05-07 NOV"},
                   {"vessel_name": "TBN", "received": "2026-10-01"}, {"vessel_name": "TBN", "received": "2026-10-02"}]
        kept = matching.latest_positions(vessels)
        self.assertEqual([v["open_date"] for v in kept if v["vessel_name"].upper() == "AGN LAGERTHA"], ["05-07 NOV"])
        self.assertEqual(sum(v["vessel_name"] == "TBN" for v in kept), 2)


class ReviewScoring(unittest.TestCase):
    def test_wilson_interval(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval"))
        from score_match_review import wilson
        low, high = wilson(6, 12)
        self.assertAlmostEqual(low, 0.254, places=2)
        self.assertAlmostEqual(high, 0.746, places=2)
        self.assertEqual(wilson(0, 0), (0.0, 0.0))


def raw_email(subject, body, day):
    message = EmailMessage()
    message["From"] = "broker@example.com"
    message["Subject"] = subject
    message["Date"] = f"{day} Nov 2026 10:00:00 +0000"
    message.set_content(body)
    return bytes(message)


class Inbox(unittest.TestCase):
    def test_mbox(self):
        raw = b"".join(b"From broker@example.com Mon Nov  2 10:00:00 2026\n" + raw_email(s, b, d) + b"\n"
                       for s, b, d in [("Cargo", CARGO, 2), ("Tonnage", VESSELS, 3)])
        items = read_mbox(raw)
        self.assertEqual([i["received"] for i in items], [date(2026, 11, 3), date(2026, 11, 2)])
        self.assertIn("SEA HAWK", items[0]["text"])

    def test_imap_is_read_only(self):
        calls = []

        class FakeIMAP:
            def __init__(self, host):
                calls.append(("connect", host))

            def login(self, user, password):
                calls.append(("login", user))

            def select(self, folder, readonly=False):
                calls.append(("select", readonly))
                return "OK", [b"1"]

            def search(self, charset, *criteria):
                return "OK", [b"1 2"]

            def fetch(self, message_id, parts):
                calls.append(("fetch", parts))
                return "OK", [(b"1 (BODY[] {100}", raw_email("Cargo", CARGO, 2)), b")"]

            def logout(self):
                calls.append(("logout",))

        items = read_imap("imap.example.com", "me@example.com", "app-password", connect=FakeIMAP)
        self.assertEqual(len(items), 2)
        self.assertIn(("select", True), calls)
        self.assertTrue(all(c[1] == "(BODY.PEEK[])" for c in calls if c[0] == "fetch"))
        self.assertEqual(calls[-1], ("logout",))


if __name__ == "__main__":
    unittest.main()
