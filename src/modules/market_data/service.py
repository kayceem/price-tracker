from __future__ import annotations

import math
from datetime import time

from src.core.nepse.fetch import fetch_all_script_details
from src.infrastructure.db.models import ScriptDetails
from src.infrastructure.db.repositories import FloorsheetRepository, ScriptDetailsRepository, ScriptRepository, TrackerRepository


def _safe_float(value, default=None):
    if value is None or value == "-":
        return default
    return float(value)


def _safe_int(value, default=0):
    if value is None or value == "-":
        return default
    return int(value)


def _to_script_href(security_id: int) -> str:
    return f"/company/detail/{security_id}"


def _map_today_price_to_details(payload: dict, script_id: int) -> dict:
    high = _safe_float(payload.get("highPrice"), 0.0)
    low = _safe_float(payload.get("lowPrice"), 0.0)
    week_high = _safe_float(payload.get("fiftyTwoWeekHigh"), 0.0)
    week_low = _safe_float(payload.get("fiftyTwoWeekLow"), 0.0)
    last_traded_price = _safe_float(payload.get("lastUpdatedPrice"))
    close_price = _safe_float(payload.get("closePrice"), last_traded_price)
    return {
        "script_id": script_id,
        "last_traded_price": last_traded_price,
        "total_traded_quantity": _safe_int(payload.get("totalTradedQuantity")),
        "total_trades": _safe_int(payload.get("totalTrades")),
        "previous_day_close_price": _safe_float(payload.get("previousDayClosePrice"), 0.0),
        "high_price_low_price": f"{high} - {low}",
        "week_52_high_low": f"{week_high} - {week_low}",
        "open_price": _safe_float(payload.get("openPrice"), 0.0),
        "close_price": close_price if close_price is not None else 0.0,
        "market_capitalization": _safe_float(payload.get("marketCapitalization")),
    }


class ScriptRefreshService:
    def __init__(self, db):
        self.db = db
        self.scripts = ScriptRepository(db)
        self.details = ScriptDetailsRepository(db)
        self.trackers = TrackerRepository(db)

    async def refresh(self, only_tickers: set[str] | None = None) -> dict[str, dict]:
        payloads = await fetch_all_script_details()
        if not payloads:
            return {}
        data_by_ticker = {item["symbol"]: item for item in payloads if item.get("symbol")}
        existing_scripts = {script.ticker: script for script in await self.scripts.list_all()}
        details_by_script_id = {details.script_id: details for details in await self.details.list_all()}
        for ticker, payload in data_by_ticker.items():
            if only_tickers is not None and ticker not in only_tickers:
                continue
            security_id = payload.get("securityId")
            if security_id is None:
                continue
            script = existing_scripts.get(ticker)
            if script is None:
                script = await self.scripts.create(
                    ticker=ticker,
                    name=payload.get("securityName"),
                    href=_to_script_href(security_id),
                    nepse_id=security_id,
                )
                existing_scripts[ticker] = script
            else:
                script.name = payload.get("securityName") or script.name
                script.nepse_id = security_id
                script.href = script.href or _to_script_href(security_id)
            details_payload = _map_today_price_to_details(payload, script.id)
            existing_details = details_by_script_id.get(script.id)
            if existing_details:
                for key, value in details_payload.items():
                    if key != "script_id":
                        setattr(existing_details, key, value)
            else:
                self.db.add(ScriptDetails(**details_payload))
        await self.db.commit()
        return data_by_ticker

    async def refresh_tracked(self) -> bool:
        scripts = await self.trackers.list_tracked_scripts()
        if not scripts:
            return False
        await self.refresh({script.ticker for script in scripts})
        return True


class FloorsheetQueryService:
    def __init__(self, db):
        self.db = db
        self.floorsheets = FloorsheetRepository(db)

    async def get_available_dates(self) -> dict:
        dates = await self.floorsheets.list_available_dates()
        return {"dates": dates, "count": len(dates)}

    async def get_companies(self, date: str | None = None) -> dict:
        companies = await self.floorsheets.list_companies(date=date)
        return {"companies": companies, "count": len(companies)}

    async def get_floorsheet_data(
        self,
        date: str | None = None,
        ticker: str | None = None,
        *,
        page: int = 1,
        page_size: int = 100,
        sort_column: str = "trade_time",
        sort_direction: str = "asc",
    ) -> dict:
        total = await self.floorsheets.count_rows(date=date, ticker=ticker)
        rows = await self.floorsheets.query_rows_page(
            date=date,
            ticker=ticker,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_direction=sort_direction,
        )
        payload = [
            {
                "contract_id": row.Floorsheet.contract_id,
                "stock_symbol": row.stock_symbol,
                "buyer_member_id": row.buyer_member_id,
                "seller_member_id": row.seller_member_id,
                "buyer_broker_name": row.buyer_broker_name,
                "seller_broker_name": row.seller_broker_name,
                "contract_quantity": row.Floorsheet.contract_quantity,
                "contract_rate": row.Floorsheet.contract_rate,
                "contract_amount": row.Floorsheet.contract_amount,
                "trade_date": row.Floorsheet.trade_date,
                "trade_time": row.Floorsheet.trade_time,
            }
            for row in rows
        ]
        total_pages = math.ceil(total / page_size) if total else 1
        return {
            "floorsheet": payload,
            "count": len(payload),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "sort": {
                "column": sort_column,
                "direction": sort_direction,
            },
        }

    async def get_floorsheet_summary(self, date: str, ticker: str | None = None) -> dict:
        rows = await self.floorsheets.query_rows(date=date, ticker=ticker)
        summaries = []
        current_broker_id = None
        current_broker_name = None
        current_quantity = 0
        current_trade_count = 0
        current_total_amount = 0.0
        current_prices = []
        current_start_time = None
        for row in rows:
            buyer_id = row.buyer_member_id
            buyer_name = row.buyer_broker_name
            quantity = row.Floorsheet.contract_quantity
            price = row.Floorsheet.contract_rate
            amount = row.Floorsheet.contract_amount
            trade_time = row.Floorsheet.trade_time
            if buyer_id == current_broker_id:
                current_quantity += quantity
                current_trade_count += 1
                current_total_amount += amount
                current_prices.append(price)
                continue
            if current_broker_id is not None:
                avg_price = current_total_amount / current_quantity if current_quantity > 0 else 0
                summaries.append(
                    {
                        "broker_id": current_broker_id,
                        "broker_name": current_broker_name,
                        "quantity": current_quantity,
                        "trades": current_trade_count,
                        "total_amount": current_total_amount,
                        "average_price": round(avg_price, 2),
                        "min_price": min(current_prices),
                        "max_price": max(current_prices),
                        "start_time": current_start_time,
                    }
                )
            current_broker_id = buyer_id
            current_broker_name = buyer_name
            current_quantity = quantity
            current_trade_count = 1
            current_total_amount = amount
            current_prices = [price]
            current_start_time = trade_time
        if current_broker_id is not None:
            avg_price = current_total_amount / current_quantity if current_quantity > 0 else 0
            summaries.append(
                {
                    "broker_id": current_broker_id,
                    "broker_name": current_broker_name,
                    "quantity": current_quantity,
                    "trades": current_trade_count,
                    "total_amount": current_total_amount,
                    "average_price": round(avg_price, 2),
                    "min_price": min(current_prices),
                    "max_price": max(current_prices),
                    "start_time": current_start_time,
                }
            )
        return {
            "summaries": summaries,
            "statistics": {
                "total_groups": len(summaries),
                "total_trades": sum(s["trades"] for s in summaries),
                "total_quantity": sum(s["quantity"] for s in summaries),
                "total_amount": round(sum(s["total_amount"] for s in summaries), 2),
            },
        }

    async def get_broker_side_summary(self, date: str, ticker: str | None = None) -> dict:
        rows = await self.floorsheets.query_rows(date=date, ticker=ticker)
        buyer_agg: dict[str, dict] = {}
        seller_agg: dict[str, dict] = {}
        buyer_total = 0
        seller_total = 0

        for row in rows:
            qty = row.Floorsheet.contract_quantity
            amt = row.Floorsheet.contract_amount

            buyer_id = row.buyer_member_id
            if buyer_id:
                current = buyer_agg.setdefault(
                    buyer_id,
                    {
                        "broker_id": buyer_id,
                        "broker_name": row.buyer_broker_name,
                        "quantity": 0,
                        "total_amount": 0.0,
                    },
                )
                current["quantity"] += qty
                current["total_amount"] += amt
                buyer_total += qty

            seller_id = row.seller_member_id
            if seller_id:
                current = seller_agg.setdefault(
                    seller_id,
                    {
                        "broker_id": seller_id,
                        "broker_name": row.seller_broker_name,
                        "quantity": 0,
                        "total_amount": 0.0,
                    },
                )
                current["quantity"] += qty
                current["total_amount"] += amt
                seller_total += qty

        def _finalize(agg: dict[str, dict], total: int) -> list[dict]:
            rows = []
            for item in agg.values():
                quantity = item["quantity"]
                rows.append(
                    {
                        **item,
                        "average_price": item["total_amount"] / quantity if quantity > 0 else 0,
                        "percentage": (quantity / total * 100) if total > 0 else 0,
                    }
                )
            return rows

        return {
            "buyer": _finalize(buyer_agg, buyer_total),
            "seller": _finalize(seller_agg, seller_total),
            "totals": {
                "buyer": buyer_total,
                "seller": seller_total,
            },
        }

    def _parse_trade_time_seconds(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            time_part, _, fraction_part = value.partition(".")
            parsed = time.fromisoformat(time_part)
            fraction = float(f"0.{fraction_part}") if fraction_part else 0.0
            return parsed.hour * 3600 + parsed.minute * 60 + parsed.second + fraction
        except ValueError:
            return None

    def _format_duration(self, total_seconds: float | None) -> str:
        if total_seconds is None or math.isnan(total_seconds):
            return "\u2014"
        sign = "-" if total_seconds < 0 else ""
        seconds = abs(total_seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remainder = seconds % 60
        if hours > 0:
            return f"{sign}{hours}h {minutes}m {remainder:.1f}s"
        if minutes > 0:
            return f"{sign}{minutes}m {remainder:.1f}s"
        return f"{sign}{remainder:.3f}s"

    async def get_price_switch_analysis(self, date: str, ticker: str | None = None) -> dict:
        rows = await self.floorsheets.query_rows(date=date, ticker=ticker)
        payload = [
            {
                "contract_id": row.Floorsheet.contract_id,
                "buyer_member_id": row.buyer_member_id,
                "seller_member_id": row.seller_member_id,
                "buyer_broker_name": row.buyer_broker_name,
                "seller_broker_name": row.seller_broker_name,
                "contract_quantity": row.Floorsheet.contract_quantity,
                "contract_rate": row.Floorsheet.contract_rate,
                "contract_amount": row.Floorsheet.contract_amount,
                "trade_time": row.Floorsheet.trade_time,
            }
            for row in rows
        ]
        unique_rates = sorted({float(item["contract_rate"]) for item in payload}, reverse=True)
        empty_response = {
            "levels": {"highest": None, "second": None, "third": None},
            "rows": [],
            "stats": {
                "switch_interval": "\u2014",
                "switch_interval_detail": "",
                "minutes_after_open": "\u2014",
                "minutes_after_open_detail": "",
                "selected_ticker": ticker,
                "selected_date": date,
            },
        }
        if len(unique_rates) < 3:
            return empty_response

        highest, second, third = unique_rates[:3]
        by_time = sorted(payload, key=lambda item: item["trade_time"] or "")
        first_highest = next((item for item in by_time if float(item["contract_rate"]) == highest), None)
        first_second = next((item for item in by_time if float(item["contract_rate"]) == second), None)
        third_candidates = [item for item in by_time if float(item["contract_rate"]) == third]
        if first_second:
            third_before_second = [
                item for item in third_candidates if (item["trade_time"] or "") <= (first_second["trade_time"] or "")
            ]
            last_third = third_before_second[-1] if third_before_second else None
        else:
            last_third = None
        if last_third is None and third_candidates:
            last_third = third_candidates[-1]

        tagged_rows = []
        if last_third:
            tagged_rows.append(
                {
                    **last_third,
                    "label": "3rd \u00b7 last",
                    "accent": "slate",
                }
            )
        if first_second:
            tagged_rows.append(
                {
                    **first_second,
                    "label": "2nd \u00b7 first",
                    "accent": "amber",
                }
            )
        if first_highest:
            tagged_rows.append(
                {
                    **first_highest,
                    "label": "1st \u00b7 first",
                    "accent": "emerald",
                }
            )
        tagged_rows.sort(key=lambda item: item["trade_time"] or "")

        switch_interval = "\u2014"
        switch_interval_detail = ""
        if last_third and first_second:
            start_seconds = self._parse_trade_time_seconds(last_third["trade_time"])
            end_seconds = self._parse_trade_time_seconds(first_second["trade_time"])
            if start_seconds is not None and end_seconds is not None:
                switch_interval = self._format_duration(end_seconds - start_seconds)
                switch_interval_detail = f"{last_third['trade_time']} \u2192 {first_second['trade_time']}"

        minutes_after_open = "\u2014"
        minutes_after_open_detail = ""
        if last_third:
            trade_seconds = self._parse_trade_time_seconds(last_third["trade_time"])
            market_open_seconds = 11 * 3600
            if trade_seconds is not None:
                diff_seconds = trade_seconds - market_open_seconds
                minutes_after_open = self._format_duration(diff_seconds)
                minutes_after_open_detail = f"trade at {last_third['trade_time']}"

        return {
            "levels": {
                "highest": highest,
                "second": second,
                "third": third,
            },
            "rows": tagged_rows,
            "stats": {
                "switch_interval": switch_interval,
                "switch_interval_detail": switch_interval_detail,
                "minutes_after_open": minutes_after_open,
                "minutes_after_open_detail": minutes_after_open_detail,
                "selected_ticker": ticker,
                "selected_date": date,
            },
        }
