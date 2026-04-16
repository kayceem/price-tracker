from __future__ import annotations

from fastapi import Request

from src.modules.market_data import FloorsheetQueryService
from src.modules.portfolio import PortfolioQueryService


def get_portfolio_service() -> PortfolioQueryService:
    return PortfolioQueryService()


async def get_floorsheet_service(request: Request) -> FloorsheetQueryService:
    return FloorsheetQueryService(request.state.db)

