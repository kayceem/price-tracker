import logging
from datetime import date, datetime
from math import ceil
from typing import Any, Awaitable, Callable

from nepse import AsyncNepse


logger = logging.getLogger(__name__)


class NEPSE:
    """Compatibility adapter around the upstream unofficial nepse library."""

    def __init__(self):
        self.client = AsyncNepse()
        self.client.setTLSVerification(False)

    async def __aenter__(self) -> "NEPSE":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        http_client = getattr(self.client, "client", None)
        if http_client is not None and hasattr(http_client, "aclose"):
            await http_client.aclose()

    async def _call_with_retry(
        self,
        fn: Callable[[], Awaitable[Any]],
        *,
        label: str,
        retries: int = 2,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                return await fn()
            except Exception as exc:
                last_error = exc
                logger.warning("%s attempt %s/%s failed: %s", label, attempt, retries, exc)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"{label} failed without raising an exception")

    async def get_market_status(self) -> bool:
        try:
            return bool(await self._call_with_retry(self.client.isNepseOpen, label="market status"))
        except Exception:
            logger.exception("Failed to get NEPSE market status")
            return False

    def _normalize_live_row(self, row: dict[str, Any]) -> dict[str, Any]:
        security_id = row.get("securityId")
        return {
            "symbol": row.get("symbol"),
            "securityId": int(security_id) if security_id is not None else None,
            "securityName": row.get("securityName"),
            "openPrice": row.get("openPrice"),
            "highPrice": row.get("highPrice"),
            "lowPrice": row.get("lowPrice"),
            "closePrice": row.get("lastTradedPrice") or row.get("previousClose"),
            "lastUpdatedPrice": row.get("lastTradedPrice"),
            "totalTradedQuantity": row.get("totalTradeQuantity", 0),
            "totalTrades": 0,
            "previousDayClosePrice": row.get("previousClose"),
            "averageTradedPrice": row.get("averageTradedPrice"),
            "marketCapitalization": None,
            "fiftyTwoWeekHigh": None,
            "fiftyTwoWeekLow": None,
            "lastUpdatedDateTime": row.get("lastUpdatedDateTime"),
        }

    async def _fetch_live_market_rows(self) -> list[dict[str, Any]]:
        rows = await self._call_with_retry(self.client.getLiveMarket, label="live market")
        if not isinstance(rows, list):
            return []
        return [self._normalize_live_row(row) for row in rows]

    async def _enrich_row_with_company_details(self, row: dict[str, Any]) -> dict[str, Any]:
        symbol = row.get("symbol")
        if not symbol:
            return row

        details = await self._call_with_retry(
            lambda: self.client.getCompanyDetails(symbol),
            label=f"company details for {symbol}",
        )
        daily = details.get("securityDailyTradeDto") or {}
        security = details.get("security") or {}

        if daily:
            security_id = daily.get("securityId", row.get("securityId"))
            row.update(
                {
                    "securityId": int(security_id) if security_id is not None else row.get("securityId"),
                    "openPrice": daily.get("openPrice", row.get("openPrice")),
                    "highPrice": daily.get("highPrice", row.get("highPrice")),
                    "lowPrice": daily.get("lowPrice", row.get("lowPrice")),
                    "closePrice": daily.get("closePrice", row.get("closePrice")),
                    "lastUpdatedPrice": daily.get("lastTradedPrice", row.get("lastUpdatedPrice")),
                    "totalTradedQuantity": daily.get("totalTradeQuantity", row.get("totalTradedQuantity", 0)),
                    "totalTrades": daily.get("totalTrades", row.get("totalTrades", 0)),
                    "previousDayClosePrice": daily.get("previousClose", row.get("previousDayClosePrice")),
                    "fiftyTwoWeekHigh": daily.get("fiftyTwoWeekHigh"),
                    "fiftyTwoWeekLow": daily.get("fiftyTwoWeekLow"),
                    "businessDate": daily.get("businessDate"),
                    "lastUpdatedDateTime": daily.get("lastUpdatedDateTime", row.get("lastUpdatedDateTime")),
                }
            )

        if security:
            row["symbol"] = security.get("symbol") or row.get("symbol")
            row["securityName"] = security.get("securityName") or row.get("securityName")

        row["marketCapitalization"] = details.get("marketCapitalization")
        row["stockListedShares"] = details.get("stockListedShares")
        return row

    async def fetch_all_today_price(
        self,
        *,
        business_date: str | None = None,
        only_tickers: set[str] | None = None,
        include_details: bool = False,
    ) -> list[dict[str, Any]]:
        target_date = business_date or date.today().isoformat()
        if target_date != date.today().isoformat():
            logger.warning(
                "The upstream nepse library does not expose historical today-price pages; using current live market data for requested business_date=%s",
                target_date,
            )

        rows = await self._fetch_live_market_rows()
        if only_tickers is not None:
            rows = [row for row in rows if row.get("symbol") in only_tickers]

        if include_details:
            enriched_rows = []
            for row in rows:
                try:
                    enriched_rows.append(await self._enrich_row_with_company_details(row))
                except Exception:
                    logger.exception("Failed to enrich company details for ticker=%s", row.get("symbol"))
                    enriched_rows.append(row)
            rows = enriched_rows

        return rows

    async def fetch_floorsheet(
        self,
        *,
        stock_id: int,
        symbol: str | None = None,
        business_date: str,
        page: int = 0,
        size: int = 500,
    ) -> dict[str, Any]:
        try:
            if symbol:
                try:
                    rows = await self._call_with_retry(
                        lambda: self.client.getFloorSheetOf(symbol, business_date),
                        label=f"floorsheet for {symbol} on {business_date}",
                    )
                except Exception:
                    logger.warning(
                        "Falling back to full floorsheet download for symbol=%s business_date=%s",
                        symbol,
                        business_date,
                    )
                    rows = await self._call_with_retry(
                        lambda: self.client.getFloorSheet(show_progress=False, symbol=symbol),
                        label=f"full floorsheet fallback for {symbol} on {business_date}",
                    )
                    rows = [
                        row
                        for row in rows
                        if row.get("stockSymbol") == symbol
                        and str(row.get("tradeTime", "")).startswith(business_date)
                    ]
            else:
                rows = await self._call_with_retry(
                    lambda: self.client.getFloorSheet(show_progress=False),
                    label=f"floorsheet for stock_id={stock_id} on {business_date}",
                )
                rows = [
                    row
                    for row in rows
                    if int(row.get("stockId", -1)) == stock_id
                    and str(row.get("tradeTime", "")).startswith(business_date)
                ]

            total_pages = max(1, ceil(len(rows) / size)) if rows else 1
            start = page * size
            end = start + size
            return {
                "floorsheets": {
                    "content": rows[start:end],
                    "page": page,
                    "size": size,
                    "totalPages": total_pages,
                    "last": end >= len(rows),
                }
            }
        except Exception:
            logger.exception(
                "Error fetching floorsheet for stock_id=%s business_date=%s",
                stock_id,
                business_date,
            )
            return {}

    async def fetch_today_price(
        self,
        *,
        business_date: str | None = None,
        page: int = 0,
        size: int = 500,
    ) -> dict[str, Any]:
        target_date = business_date or datetime.now().strftime("%Y-%m-%d")
        try:
            rows = await self.fetch_all_today_price(
                business_date=target_date,
                include_details=False,
            )
            start = page * size
            end = start + size
            return {
                "content": rows[start:end],
                "page": page,
                "size": size,
                "last": end >= len(rows),
            }
        except Exception:
            logger.exception("Error fetching NEPSE today-price for business_date=%s", target_date)
            return {}
