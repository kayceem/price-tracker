import unittest
import asyncio

import pandas as pd

from src.interfaces.http.api.routes.portfolio import get_portfolio_summary


class FakePortfolioService:
    def get_current_prices(self):
        return {"AAA": 120.0}

    def get_portfolio_summary(self, _current_prices):
        return pd.DataFrame(
            [
                {
                    "Scrip": "AAA",
                    "Current Holdings": 10,
                    "Avg Cost": 100.0,
                    "Total Investment": 1000.0,
                    "Current Price": 120.0,
                    "Current Value": 1200.0,
                    "Realized P&L": 0.0,
                    "Unrealized P&L": 200.0,
                    "Total P&L": 200.0,
                    "Interest Cost": 0.0,
                    "Net P&L (After Interest)": 200.0,
                }
            ]
        )

    def get_current_holdings(self, _current_prices):
        return pd.DataFrame()

    def get_transaction_history(self):
        return pd.DataFrame()

    def get_detailed_pools(self, _current_prices):
        return pd.DataFrame()

    def get_interest_analysis(self):
        return pd.DataFrame()

    def get_sold_interest_analysis(self):
        return pd.DataFrame()

    def get_portfolio_stats(self):
        return {"holding_count": 1}

    def get_script_detail(self, symbol):
        return {"summary": {"Scrip": symbol}, "transactions": [], "pool": None, "current_price": 120.0}


class PortfolioRouteTests(unittest.TestCase):
    def test_summary_route_returns_expected_payload(self):
        response = asyncio.run(get_portfolio_summary(FakePortfolioService()))
        self.assertEqual(response.status_code, 200)
        payload = response.body.decode()
        import json
        payload = json.loads(payload)
        self.assertEqual(payload["script_count"], 1)
        self.assertEqual(payload["totals"]["current_value"], 1200.0)
        self.assertEqual(payload["scripts"][0]["Scrip"], "AAA")


if __name__ == "__main__":
    unittest.main()
