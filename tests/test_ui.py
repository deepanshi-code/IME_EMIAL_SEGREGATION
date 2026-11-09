import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui  # noqa: E402
from pipeline import process_email  # noqa: E402


class HtmlSafety(unittest.TestCase):
    """The result cards render email content as HTML, so email text must never become markup."""

    def test_extracted_values_are_escaped(self):
        text = 'MV <img src=x onerror=alert(1)> 58,000 DWT\nOPEN <script>alert(1)</script> 10-12 DEC'
        html = ui.result_card(process_email(text))
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)

    def test_match_card_escapes_label_and_reasons(self):
        html = ui.match_card(1, 7, "<b>x</b>", [("Dates", 3)], ["<i>reason</i>"])
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertNotIn("<i>reason", html)

    def test_every_category_renders(self):
        for text in ("MV SEA HAWK 58,000 DWT\nOPEN TIANJIN 10-12 DEC",
                     "Pls offer firm for;\nMundra / Chittagong\n12,000 mt bagged sugar\n5-10 Dec",
                     "Period enquiry\nDel: Haldia\nRedel: Far East\nPeriod: 11-13 months",
                     "Hi Sarah, could we move the budget review to Thursday?"):
            self.assertIn("ime-result", ui.result_card(process_email(text)))


if __name__ == "__main__":
    unittest.main()
