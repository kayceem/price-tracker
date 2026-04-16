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


if __name__ == "__main__":
    unittest.main()
