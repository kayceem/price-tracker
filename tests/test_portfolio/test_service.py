import tempfile
import unittest
from pathlib import Path

from src.modules.portfolio.service import PortfolioQueryService


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class PortfolioQueryServiceTests(unittest.TestCase):
    def test_builds_summary_from_csv_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "Wacc Rates.csv",
                "\n".join(
                    [
                        "Scrip,Balance,WACC,Investment,LTP,Current Value,Profit/Loss,High,Low",
                        "AAA,10,100,1000,120,1200,200,150,80",
                    ]
                ),
            )
            _write(
                root / "history" / "Trade Book Details.csv",
                "\n".join(
                    [
                        "SYMBOL,EXCHANGE TRADE ID,BUY/SELL,TRADE QTY,PRICE(NPR),Value(NPR)",
                        "AAA,2024010100000001,Buy,10,100,1000",
                    ]
                ),
            )
            _write(
                root / "history" / "Transaction History.csv",
                "\n".join(
                    [
                        "Transaction Date,Scrip,History Description,Credit Quantity",
                        "2024-01-01,AAA,CA-BONUS,0",
                    ]
                ),
            )

            service = PortfolioQueryService(username="tester", csv_base_path=root)
            summary = service.get_portfolio_summary(service.get_current_prices())

            self.assertEqual(len(summary), 1)
            row = summary.iloc[0]
            self.assertEqual(row["Scrip"], "AAA")
            self.assertEqual(row["Current Holdings"], 10)
            self.assertEqual(row["Current Value"], 1200)
            self.assertEqual(row["Unrealized P&L"], 200)

    def test_returns_script_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "Wacc Rates.csv",
                "\n".join(
                    [
                        "Scrip,Balance,WACC,Investment,LTP,Current Value,Profit/Loss,High,Low",
                        "AAA,10,100,1000,120,1200,200,150,80",
                    ]
                ),
            )
            _write(
                root / "history" / "Trade Book Details.csv",
                "\n".join(
                    [
                        "SYMBOL,EXCHANGE TRADE ID,BUY/SELL,TRADE QTY,PRICE(NPR),Value(NPR)",
                        "AAA,2024010100000001,Buy,10,100,1000",
                        "AAA,2024020100000001,Sell,5,110,550",
                    ]
                ),
            )
            _write(
                root / "history" / "Transaction History.csv",
                "Transaction Date,Scrip,History Description,Credit Quantity\n",
            )

            service = PortfolioQueryService(username="tester", csv_base_path=root)
            detail = service.get_script_detail("AAA")

            self.assertEqual(detail["summary"]["Scrip"], "AAA")
            self.assertEqual(detail["current_price"], 120)
            self.assertEqual(len(detail["transactions"]), 2)

    def test_generate_reports_writes_csv_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "Wacc Rates.csv",
                "\n".join(
                    [
                        "Scrip,Balance,WACC,Investment,LTP,Current Value,Profit/Loss,High,Low",
                        "AAA,10,100,1000,120,1200,200,150,80",
                    ]
                ),
            )
            _write(
                root / "history" / "Trade Book Details.csv",
                "\n".join(
                    [
                        "SYMBOL,EXCHANGE TRADE ID,BUY/SELL,TRADE QTY,PRICE(NPR),Value(NPR)",
                        "AAA,2024010100000001,Buy,10,100,1000",
                    ]
                ),
            )
            _write(
                root / "history" / "Transaction History.csv",
                "Transaction Date,Scrip,History Description,Credit Quantity\n",
            )

            service = PortfolioQueryService(username="tester", csv_base_path=root)
            outputs = service.generate_reports()

            self.assertTrue(outputs["portfolio_summary"].exists())
            self.assertTrue(outputs["transaction_history"].exists())
            self.assertTrue(outputs["current_holdings"].exists())


if __name__ == "__main__":
    unittest.main()
