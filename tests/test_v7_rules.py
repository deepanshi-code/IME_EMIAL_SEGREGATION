"""v7 formats, written as invented examples of the patterns found in the 3 Nov 2026 posts."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import classify_email  # noqa: E402
from extractor import extract_data, extract_records  # noqa: E402


class TimeCharter(unittest.TestCase):
    def test_firm_tc_requirement_with_hire_idea(self):
        text = ("Firm T/C requirement - 30/32K DWT\nVessel: 30,000-32,000 DWT geared bulker\n"
                "Period: 90 + 90 days\nHire idea: USD 9,500 PDPR\nDelivery: Singapore\nLaycan: 1-5 Dec")
        self.assertEqual(classify_email(text), "CARGO TC")
        fields = extract_data(text, "CARGO TC")
        self.assertEqual(fields["Delivery Port"], "Singapore")
        self.assertEqual(fields["Duration"], "90 + 90 days")

    def test_charter_period_label(self):
        text = ("Please quote your best Time Charter offers:\nVessel type: Aframax\n"
                "Charter Period: 6 months firm + 6 months option\nDelivery: Fujairah")
        self.assertEqual(classify_email(text), "CARGO TC")
        self.assertEqual(extract_data(text, "CARGO TC")["Duration"], "6 months firm + 6 months option")

    def test_time_charter_or_voyage_is_not_forced_to_tc(self):
        text = "Pls offer firm for time charter or voyage request\nMarmara / West Africa\n4/5K DWT\nSpot"
        self.assertEqual(classify_email(text), "CARGO VC")


class Labels(unittest.TestCase):
    def test_markdown_bullets(self):
        text = ("Firm cargo inquiry:\n- **Cargo:** Clinker (25,000 MT)\n- **Load Port:** Ras Al Khaimah\n"
                "- **Discharge Port:** Chittagong\n- **Laycan:** 5-10 Dec")
        fields = extract_data(text, classify_email(text))
        self.assertEqual((fields["Loading Port"], fields["Discharge Port"], fields["Cargo"]),
                         ("Ras Al Khaimah", "Chittagong", "Clinker"))

    def test_short_and_misspelt_port_labels(self):
        text = "Pls offer:\nCargo: 8k mt urea in bulk\nL/Port: Yuzhny\nL/Rate: 3,000 mt\nD/port: Mersin\nLaycan: 1-5 Dec"
        fields = extract_data(text, "CARGO VC")
        self.assertEqual((fields["Loading Port"], fields["Discharge Port"]), ("Yuzhny", "Mersin"))
        self.assertEqual(extract_data("Load port: Odesa\nDiach port: Bari", "CARGO VC")["Discharge Port"], "Bari")

    def test_voyage_label_drops_country(self):
        fields = extract_data("Voyage: Basrah, Iraq – Ningbo, China\nQuantity: 1 million barrels", "CARGO VC")
        self.assertEqual((fields["Loading Port"], fields["Discharge Port"]), ("Basrah", "Ningbo"))
        self.assertNotIn("Quantity", fields)  # barrels are not tonnes


class Quantities(unittest.TestCase):
    def test_k_before_tolerance_and_mtons(self):
        self.assertEqual(extract_data("Pls offer\n6k 10% Barley\nConstanta / Marmara\nLC: 1-10 Dec", "CARGO VC")
                         ["Quantity"], "6000")
        fields = extract_data("PLS OFFER FIRM FOR:\n25,000 mtons %10 moloo soda ash\nAqaba / Gemlik", "CARGO VC")
        self.assertEqual((fields["Quantity"], fields["Cargo"]), ("25000", "soda ash"))

    def test_load_guarantee_is_not_the_quantity(self):
        text = "Cargo: 1 ton jumbo bag urea\n15k tons\nLoad port: Gemlik\n4k load gtee\nDisch port: Recife"
        fields = extract_records(text, "CARGO VC")[0]
        self.assertEqual((fields["Quantity"], fields["Cargo"]), ("15000", "urea"))

    def test_packaging_words_are_dropped(self):
        self.assertEqual(extract_data("Pls offer\n3,000 mt barite in bb\nPiraeus / Tripoli", "CARGO VC")["Cargo"],
                         "barite")


class Vessels(unittest.TestCase):
    def test_size_run_together_with_dwt(self):
        text = ("Need named cgo\nMV ALPHA (DWT41k)\nloading: qingdao\nlaycan dec 1-10\n"
                "MV BRAVO ( dwt 25k)\nloading: busan\nlaycan dec 5-15")
        sizes = [r.get("Vessel Size") for r in extract_records(text, "TONNAGE")]
        self.assertEqual(sizes, ["41000", "25000"])

    def test_name_after_mv_dot(self):
        fields = extract_data("OPEN TONNAGE\nMV.OCEAN PEARL OPEN CAM PHA O/A 12-13TH,DEC", "TONNAGE")
        self.assertEqual(fields["Vessel Name"], "OCEAN PEARL")
        self.assertEqual(fields["Open Date"], "12-13TH,DEC")


if __name__ == "__main__":
    unittest.main()
