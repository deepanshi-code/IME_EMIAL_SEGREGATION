import os
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from classifier import classify_email
from extractor import extract_data, extract_records, to_tonnes
from pipeline import process_email


class NumberParsing(unittest.TestCase):
    def test_tonnes(self):
        cases = {"58,000": "58000", "7.331,1": "7331", "4299,59": "4299", "63.5k": "63500", "11.000": "11000",
                 "32,318.3": "32318", "18K": "18000", "22,107.50": "22107"}
        for raw, expected in cases.items():
            self.assertEqual(to_tonnes(raw), expected, raw)

    def test_quantity_shorthand(self):
        cases = {
            "8k mt bagged rice": "8000",
            "2-4000 MT GENERALS": "2000-4000",
            "42-4500 MT OF WIRE RODS": "4200-4500",
            "7-20,000 mts cement in bags": "7000-20000",
            "9,000/12,000mt minerals in bulk": "9000-12000",
            "11.000 mts up to 17.000 mts GBFS in bulk": "11000-17000",
        }
        for line, expected in cases.items():
            text = f"Pls offer firm for;\nGulluk / Sousse\n{line}\nSPOT\n1000x/1000x"
            self.assertEqual(extract_data(text, "CARGO VC").get("Quantity"), expected, line)


class Classification(unittest.TestCase):
    def test_categories(self):
        cases = {
            "MV SEA HAWK 58,000 DWT OPEN TIANJIN 10-12 DEC / PLS OFFER": "TONNAGE",
            "Pls offer firm for;\nKandla / Subic Bay\n8k mt bagged rice\n20 nov onwards\n1500x / 1000x": "CARGO VC",
            "Supramax needed on period\nDel: Singapore\nRedel: worldwide\nPeriod: 4-6 months": "CARGO TC",
            "Hi Sarah,\nCould we move the budget review to Thursday?": "UNKNOWN",
        }
        for text, expected in cases.items():
            self.assertEqual(classify_email(text), expected, text)

    def test_known_false_positives(self):
        for text in [
            "Hi, are you open for a meeting about the vessel insurance renewal?",
            "Our freight forwarder will send the invoice from Monday to Friday.",
            "delivery point : i / b link\nvolume 30 , 000 dth / day",
            "On Monday - member panel to discuss the port lockout. The freight still isn't moving.",
        ]:
            self.assertEqual(classify_email(text), "UNKNOWN", text)


class Extraction(unittest.TestCase):
    def test_vessel_table_without_open(self):
        text = "Please offer firm for our home tonnage;\nMV FLOKI /09-11 NOV IZMIR\nDWCC 2100 / DRAFT 4,80"
        fields = extract_data(text, "TONNAGE")
        self.assertEqual(fields.get("Open Port"), "IZMIR")
        self.assertEqual(fields.get("Open Date"), "09-11 NOV")

    def test_home_tonnage_is_not_a_port(self):
        text = "Please note our current open home tonnage:\nMV TBN 1\n4000 DWT / OPEN @MARMARA / 12-15 NOVEMBER"
        self.assertEqual(extract_data(text, "TONNAGE").get("Open Port"), "MARMARA")

    def test_laycan_forms(self):
        cases = {
            "LAYCAN 15 – 20 November 2026": "15 – 20 November 2026",
            "Laycan : spot/ppt/try vsl date": "spot",
            "Laycan mid/End oct 2026": "mid/End oct 2026",
            "The laycan is 15-20 October. Freight USD 20/MT.": "15-20 October",
        }
        for line, expected in cases.items():
            text = f"Pls offer firm for;\nGulluk / Sousse\n5000 mt minerals\n{line}"
            self.assertEqual(extract_data(text, "CARGO VC").get("Laycan"), expected, line)


class Records(unittest.TestCase):
    def test_vessel_list(self):
        text = ("M/V SNOW: 4,226 DWT – Open at Marmara 13-14 Oct.\n"
                "M/V SKY FEYZ: 3,662 DWT -  Open at Izmail 16-18 Oct.\n"
                "M/V SNOW\nDwt S/W : 4,226 mts / 4,093 mts\nBuilt 2008")
        records = extract_records(text, "TONNAGE")
        self.assertEqual([r.get("Vessel Name") for r in records], ["SNOW", "SKY FEYZ"])
        self.assertEqual(records[1].get("Open Port"), "Izmail")

    def test_cargo_list(self):
        text = ("Pls offer firm for;\nGulluk / Sousse\n9,000/12,000mt minerals in bulk\nSPOT\n"
                "Pls offer firm for;\nabt 3000 mts wheat in blk, sf 47\nGalati (6,7m) / 1 Egypt\nspot onw")
        records = extract_records(text, "CARGO VC")
        self.assertEqual([(r.get("Loading Port"), r.get("Discharge Port")) for r in records],
                         [("Gulluk", "Sousse"), ("Galati", "Egypt")])
        self.assertEqual(records[1].get("Quantity"), "3000")

    def test_pipeline_flags_close_calls(self):
        result = process_email("Hi John, we have a vessel available for a crude oil shipment from Houston to "
                               "Rotterdam. The vessel is the MV Ocean Star, 150,000 DWT. The laycan is 15-20 October. "
                               "Freight USD 20/MT.")
        self.assertTrue(result["needs_review"])


if __name__ == "__main__":
    unittest.main()
