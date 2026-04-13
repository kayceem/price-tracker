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


async def fetch_all_script_details(business_date: Optional[str] = None) -> list[dict[str, Any]]:
    target_date = business_date or datetime.now().strftime("%Y-%m-%d")
    results: list[dict[str, Any]] = []

    async with NEPSE() as nepse:
        page = 0
        while True:
            logger.debug("Fetching NEPSE today-price page=%s business_date=%s", page, target_date)
            payload = await nepse.fetch_today_price(
                business_date=target_date,
                page=page,
                size=500,
            )
            if not payload:
                break

            content = _extract_content(payload)
            if not content:
                break

            results.extend(content)
            if _is_last_page(payload):
                break

            page += 1

    logger.info("Fetched %s today-price rows for business_date=%s", len(results), target_date)
    return results
