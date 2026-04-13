import logging

from sqlalchemy import select

from src.database import Scripts, get_db
from src.database import ScriptDetails
from src.database import Tracker
from sqlalchemy.orm import selectinload

from .fetch import fetch_all_script_details

from src.utils import check_time_delta, valid_day_time
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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


class ScriptDetailsFetcher:
    """Refresh script details from the NEPSE today-price endpoint."""

    async def fetch_and_save(self, only_tickers: set[str] | None = None) -> dict[str, dict]:
        payloads = await fetch_all_script_details()
        if not payloads:
            logger.warning("No NEPSE today-price payloads returned for script detail refresh")
            return {}

        data_by_ticker = {item["symbol"]: item for item in payloads if item.get("symbol")}

        async with get_db() as db:
            existing_scripts = {
                script.ticker: script
                for script in (await db.execute(select(Scripts))).scalars().all()
            }
            details_by_script_id = {
                details.script_id: details
                for details in (await db.execute(select(ScriptDetails))).scalars().all()
            }

            for ticker, payload in data_by_ticker.items():
                if only_tickers is not None and ticker not in only_tickers:
                    continue

                security_id = payload.get("securityId")
                if security_id is None:
                    continue

                script = existing_scripts.get(ticker)
                if script is None:
                    logger.info("Creating missing script for ticker=%s security_id=%s", ticker, security_id)
                    script = Scripts(
                        ticker=ticker,
                        name=payload.get("securityName"),
                        href=_to_script_href(security_id),
                        nepse_id=security_id,
                    )
                    db.add(script)
                    await db.flush()
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
                    existing_details = ScriptDetails(**details_payload)
                    db.add(existing_details)
                    details_by_script_id[script.id] = existing_details

            await db.commit()

        refreshed_count = len(data_by_ticker) if only_tickers is None else len([t for t in data_by_ticker if t in only_tickers])
        logger.info("Refreshed script details for %s tickers", refreshed_count)
        return data_by_ticker


async def _get_script_details_row(db: Session, script_id: int) -> ScriptDetails | None:
    return (
        await db.execute(
            select(ScriptDetails).filter(ScriptDetails.script_id == script_id)
        )
    ).scalars().first()


async def get_script_ltp(db: Session, script: Scripts):
    details_row = await _get_script_details_row(db, script.id)

    if not details_row or (check_time_delta(details_row.updated_at, 30) and valid_day_time()):
        try:
            logger.debug("Refreshing LTP from NEPSE for ticker=%s", script.ticker)
            await ScriptDetailsFetcher().fetch_and_save({script.ticker})
            details_row = await _get_script_details_row(db, script.id)
            if not details_row:
                logger.warning("No script details found after refresh for ticker=%s", script.ticker)
                return None
        except Exception as e:
            logger.exception("Failed to refresh script LTP for ticker=%s", script.ticker)
            return None

    script.script_details = details_row
    return details_row.last_traded_price

async def refresh_script_detail(ticker):
    try:
        data_by_ticker = await ScriptDetailsFetcher().fetch_and_save({ticker})
        return ticker in data_by_ticker
    except Exception as e:
        logger.exception("Failed to refresh script detail for ticker=%s", ticker)
        return False

async def refresh_script_details():
    async with get_db() as db:
        scripts = (await db.execute(select(Scripts).join(Tracker))).scalars().all()
    if not scripts:
        return False
    tickers = {script.ticker for script in scripts}
    try:
        await ScriptDetailsFetcher().fetch_and_save(tickers)
        return True
    except Exception as e:
        logger.exception("Failed to refresh tracked script details")
        return False

async def refresh_all_script_details():
    try:
        data_by_ticker = await ScriptDetailsFetcher().fetch_and_save()
        return bool(data_by_ticker)
    except Exception as e:
        logger.exception("Failed to refresh all script details")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(refresh_all_script_details())
