import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_workflow import financial_summary, pct_change, render_template


class FinancialSummaryTests(unittest.TestCase):
    def test_growth_and_rd_ratio_are_computed(self):
        rows = [
            {"year": 2022.0, "revenue": 100.0, "adjusted_net_profit": 10.0, "rd_expense": 5.0},
            {"year": 2023.0, "revenue": 120.0, "adjusted_net_profit": 11.0, "rd_expense": 7.2},
        ]
        table = "\n".join(financial_summary(rows))
        self.assertIn("20.00%", table)
        self.assertIn("10.00%", table)
        self.assertIn("6.00%", table)

    def test_zero_and_negative_bases_are_not_misleading(self):
        self.assertIn("上年为零", pct_change(5, 0))
        self.assertIn("负值", pct_change(5, -2))

    def test_template_includes_five_questions(self):
        report = render_template("甲公司", "测试行业")
        for number in range(1, 6):
            self.assertIn(f"## {number}.", report)
        self.assertIn("甲公司", report)


if __name__ == "__main__":
    unittest.main()
