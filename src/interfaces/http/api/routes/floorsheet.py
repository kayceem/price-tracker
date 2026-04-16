from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from src.modules.market_data import FloorsheetQueryService


router = APIRouter(prefix="/api/floorsheet", tags=["floorsheet"])


async def get_service(request: Request) -> FloorsheetQueryService:
    return FloorsheetQueryService(request.state.db)


@router.get("/dates")
async def get_available_dates(service: FloorsheetQueryService = Depends(get_service)):
    return JSONResponse(await service.get_available_dates())


@router.get("/companies")
async def get_available_companies(
    date: str | None = Query(None, description="Filter by trade date"),
    service: FloorsheetQueryService = Depends(get_service),
):
    return JSONResponse(await service.get_companies(date=date))


@router.get("/data")
async def get_floorsheet_data(
    date: str | None = Query(None, description="Trade date in YYYY-MM-DD format"),
    ticker: str | None = Query(None, description="Stock ticker symbol"),
    service: FloorsheetQueryService = Depends(get_service),
):
    return JSONResponse(await service.get_floorsheet_data(date=date, ticker=ticker))


@router.get("/summary")
async def get_floorsheet_summary(
    date: str = Query(..., description="Trade date in YYYY-MM-DD format"),
    ticker: str | None = Query(None, description="Stock ticker symbol"),
    service: FloorsheetQueryService = Depends(get_service),
):
    return JSONResponse(await service.get_floorsheet_summary(date=date, ticker=ticker))


@router.get("/price-switch")
async def get_price_switch(
    date: str = Query(..., description="Trade date in YYYY-MM-DD format"),
    ticker: str | None = Query(None, description="Stock ticker symbol"),
    service: FloorsheetQueryService = Depends(get_service),
):
    return JSONResponse(await service.get_price_switch_analysis(date=date, ticker=ticker))
