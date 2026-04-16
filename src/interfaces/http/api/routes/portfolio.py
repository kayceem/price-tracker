from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.app.container import get_portfolio_service
from src.modules.portfolio import PortfolioQueryService
from src.shared.exceptions import NotFoundError


router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary")
async def get_portfolio_summary(service: PortfolioQueryService = Depends(get_portfolio_service)):
    summary_df = service.get_portfolio_summary(service.get_current_prices()).fillna(0)
    total_investment = float(summary_df["Total Investment"].sum()) if not summary_df.empty else 0
    current_holdings_df = summary_df[summary_df["Current Holdings"] > 0] if not summary_df.empty else summary_df
    current_investment = float((current_holdings_df["Current Holdings"] * current_holdings_df["Avg Cost"]).sum()) if not summary_df.empty else 0
    totals = {
        "total_investment": total_investment,
        "current_investment": current_investment,
        "current_value": float(summary_df["Current Value"].sum()) if not summary_df.empty else 0,
        "realized_pnl": float(summary_df["Realized P&L"].sum()) if not summary_df.empty else 0,
        "unrealized_pnl": float(summary_df["Unrealized P&L"].sum()) if not summary_df.empty else 0,
        "total_pnl": float(summary_df["Total P&L"].sum()) if not summary_df.empty else 0,
        "interest_cost": float(summary_df["Interest Cost"].sum()) if not summary_df.empty else 0,
        "net_pnl": float(summary_df["Net P&L (After Interest)"].sum()) if not summary_df.empty else 0,
        "total_return_pct": float(summary_df["Total P&L"].sum() / total_investment * 100) if total_investment > 0 else 0,
        "net_return_pct": float(summary_df["Net P&L (After Interest)"].sum() / total_investment * 100) if total_investment > 0 else 0,
    }
    return JSONResponse({"totals": totals, "scripts": summary_df.to_dict("records"), "script_count": len(summary_df)})


@router.get("/holdings")
async def get_current_holdings(service: PortfolioQueryService = Depends(get_portfolio_service)):
    holdings_df = service.get_current_holdings(service.get_current_prices())
    if "First Purchase" in holdings_df.columns:
        holdings_df["First Purchase"] = holdings_df["First Purchase"].astype(str)
    holdings_df = holdings_df.fillna(0)
    return JSONResponse({"holdings": holdings_df.to_dict("records"), "count": len(holdings_df)})


@router.get("/transactions")
async def get_transaction_history(service: PortfolioQueryService = Depends(get_portfolio_service)):
    trans_df = service.get_transaction_history()
    if not trans_df.empty:
        trans_df["Date"] = trans_df["Date"].astype(str)
    trans_df = trans_df.fillna("")
    return JSONResponse({"transactions": trans_df.to_dict("records"), "count": len(trans_df)})


@router.get("/pools")
async def get_detailed_pools(service: PortfolioQueryService = Depends(get_portfolio_service)):
    pools_df = service.get_detailed_pools(service.get_current_prices())
    for column in ["First Purchase Date", "Last Purchase Date"]:
        if column in pools_df.columns:
            pools_df[column] = pools_df[column].astype(str)
    pools_df = pools_df.fillna(0)
    return JSONResponse({"pools": pools_df.to_dict("records"), "count": len(pools_df)})


@router.get("/interest")
async def get_interest_analysis(service: PortfolioQueryService = Depends(get_portfolio_service)):
    interest_df = service.get_interest_analysis().fillna(0)
    total_interest = float(interest_df["Interest Cost"].sum()) if not interest_df.empty else 0
    total_investment = float(interest_df["Investment Amount"].sum()) if not interest_df.empty else 0
    return JSONResponse(
        {
            "analysis": interest_df.to_dict("records"),
            "total_interest": total_interest,
            "total_investment": total_investment,
            "avg_interest_pct": total_interest / total_investment * 100 if total_investment > 0 else 0,
        }
    )


@router.get("/sold-interest")
async def get_sold_interest_analysis(service: PortfolioQueryService = Depends(get_portfolio_service)):
    df = service.get_sold_interest_analysis().fillna(0)
    return JSONResponse(
        {
            "analysis": df.to_dict("records"),
            "total_interest": float(df["Interest Cost"].sum()) if not df.empty else 0,
            "total_investment": float(df["Investment Amount"].sum()) if not df.empty else 0,
            "total_realized_pnl": float(df["Realized P&L"].sum()) if not df.empty else 0,
            "total_net_pnl": float(df["Net P&L (After Interest)"].sum()) if not df.empty else 0,
            "avg_interest_pct": float(df["Interest Cost"].sum()) / float(df["Investment Amount"].sum()) * 100
            if not df.empty and float(df["Investment Amount"].sum()) > 0
            else 0,
        }
    )


@router.get("/script/{symbol}")
async def get_script_detail(symbol: str, service: PortfolioQueryService = Depends(get_portfolio_service)):
    try:
        return JSONResponse(service.get_script_detail(symbol))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/stats")
async def get_portfolio_stats(service: PortfolioQueryService = Depends(get_portfolio_service)):
    return JSONResponse(service.get_portfolio_stats())

