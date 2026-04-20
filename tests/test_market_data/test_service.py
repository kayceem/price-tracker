import asyncio
import unittest
from types import SimpleNamespace

from src.modules.market_data.service import FloorsheetQueryService


def make_row(contract_id, buyer, seller, quantity, rate, amount, trade_time):
    return SimpleNamespace(
        Floorsheet=SimpleNamespace(
            contract_id=contract_id,
            contract_quantity=quantity,
            contract_rate=rate,
            contract_amount=amount,
            trade_time=trade_time,
        ),
        buyer_member_id=buyer,
        seller_member_id=seller,
        buyer_broker_name=f"Buyer {buyer}",
        seller_broker_name=f"Seller {seller}",
    )


class StubFloorsheetRepository:
    def __init__(self, rows):
        self._rows = rows

    async def query_rows(self, date=None, ticker=None):
        return self._rows

    async def list_available_dates(self):
        return []

    async def list_companies(self, date=None):
        return []


class FloorsheetQueryServiceTests(unittest.TestCase):
    def test_price_switch_analysis_is_computed_server_side(self):
        rows = [
            make_row(1, "10", "20", 100, 100.0, 10000.0, "11:00:10.000"),
            make_row(2, "11", "21", 100, 98.0, 9800.0, "11:00:20.000"),
            make_row(3, "11", "21", 100, 98.0, 9800.0, "11:00:40.000"),
            make_row(4, "11", "21", 100, 99.0, 9900.0, "11:01:00.000"),
            make_row(5, "12", "22", 100, 98.0, 9800.0, "11:02:30.000"),
        ]
        service = FloorsheetQueryService(db=None)
        service.floorsheets = StubFloorsheetRepository(rows)

        result = asyncio.run(service.get_price_switch_analysis(date="2026-04-16", ticker="AAA"))

        self.assertEqual(result["levels"]["highest"], 100.0)
        self.assertEqual(result["levels"]["second"], 99.0)
        self.assertEqual(result["levels"]["third"], 98.0)
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["rows"][0]["label"], "1st · first")
        self.assertEqual(result["rows"][1]["label"], "3rd · last")
        self.assertEqual(result["rows"][2]["label"], "2nd · first")
        self.assertEqual(result["stats"]["switch_interval"], "20.000s")
        self.assertEqual(result["stats"]["minutes_after_open"], "40.000s")

    def test_broker_side_summary_aggregates_all_brokers_before_frontend_top_10(self):
        rows = [
            make_row(1, "10", "20", 100, 100.0, 10000.0, "11:00:10.000"),
            make_row(2, "10", "21", 50, 102.0, 5100.0, "11:00:20.000"),
            make_row(3, "11", "20", 200, 98.0, 19600.0, "11:00:30.000"),
            make_row(4, "12", "22", 25, 110.0, 2750.0, "11:00:40.000"),
        ]
        service = FloorsheetQueryService(db=None)
        service.floorsheets = StubFloorsheetRepository(rows)

        result = asyncio.run(service.get_broker_side_summary(date="2026-04-16", ticker="AAA"))

        buyer_rows = {row["broker_id"]: row for row in result["buyer"]}
        seller_rows = {row["broker_id"]: row for row in result["seller"]}

        self.assertEqual(result["totals"]["buyer"], 375)
        self.assertEqual(result["totals"]["seller"], 375)
        self.assertEqual(buyer_rows["10"]["quantity"], 150)
        self.assertAlmostEqual(buyer_rows["10"]["average_price"], 15100.0 / 150)
        self.assertAlmostEqual(buyer_rows["10"]["percentage"], 40.0)
        self.assertEqual(seller_rows["20"]["quantity"], 300)
        self.assertAlmostEqual(seller_rows["20"]["percentage"], 80.0)
        self.assertEqual(len(result["buyer"]), 3)
        self.assertEqual(len(result["seller"]), 3)


if __name__ == "__main__":
    unittest.main()
