from datetime import datetime
import logging
from typing import Any, Optional

from src.core.nepse.client import NEPSE

logger = logging.getLogger(__name__)


def _extract_content(payload: dict[str, Any]) -> list[dict[str, Any]]:
    content = payload.get("content", [])
    if isinstance(content, list):
        return content
    return []


def _is_last_page(payload: dict[str, Any]) -> bool:
    if "last" in payload:
        return bool(payload.get("last"))
    return True


async def fetch_today_price_page(
    business_date: Optional[str] = None,
    *,
    page: int = 0,
    size: int = 500,
) -> dict[str, Any]:
    async with NEPSE() as nepse:
        return await nepse.fetch_today_price(
            business_date=business_date,
            page=page,
            size=size,
        )


async def fetch_all_script_details(
    business_date: Optional[str] = None,
    *,
    only_tickers: set[str] | None = None,
    include_details: bool = False,
) -> list[dict[str, Any]]:
    async with NEPSE() as nepse:
        results = await nepse.fetch_all_today_price(
            business_date=business_date,
            only_tickers=only_tickers,
            include_details=include_details,
        )

    target_date = business_date or datetime.now().strftime("%Y-%m-%d")
    logger.info("Fetched %s today-price rows for business_date=%s", len(results), target_date)
    return results
