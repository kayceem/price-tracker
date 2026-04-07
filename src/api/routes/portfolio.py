"""
Portfolio API Routes for FastAPI
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import pandas as pd
import math
from typing import Dict, Optional

from src.core.portfolio.analyzer import PortfolioAnalyzer, get_current_prices_from_db, get_wacc_data_from_db
from src.config.settings import config

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Initialize analyzer
analyzer = PortfolioAnalyzer(config.username)

# Use database functions for prices
def get_current_prices() -> Dict[str, float]:
    """Load current prices from database"""
    return get_current_prices_from_db()

def get_wacc_data() -> Dict[str, Dict]:
    """Load wacc data including 52-week high/low from database"""
    return get_wacc_data_from_db()


@router.get("/summary")
async def get_portfolio_summary():
    """Get complete portfolio summary"""
    try:
        current_prices = get_current_prices()
        wacc_data = get_wacc_data()
        summary_df = analyzer.get_portfolio_summary(current_prices, wacc_data)

        # Calculate current investment (only for scripts with current holdings)
        current_holdings_df = summary_df[summary_df['Current Holdings'] > 0]
        current_investment = float((current_holdings_df['Current Holdings'] * current_holdings_df['Avg Cost']).sum())

        # Calculate totals
        totals = {
            'total_investment': float(summary_df['Total Investment'].sum()),
            'current_investment': current_investment,
            'current_value': float(summary_df['Current Value'].sum()),
            'realized_pnl': float(summary_df['Realized P&L'].sum()),
            'unrealized_pnl': float(summary_df['Unrealized P&L'].sum()),
            'total_pnl': float(summary_df['Total P&L'].sum()),
            'interest_cost': float(summary_df['Interest Cost'].sum()),
            'net_pnl': float(summary_df['Net P&L (After Interest)'].sum()),
            'total_return_pct': float(summary_df['Total P&L'].sum() / summary_df['Total Investment'].sum() * 100) if summary_df['Total Investment'].sum() > 0 else 0,
            'net_return_pct': float(summary_df['Net P&L (After Interest)'].sum() / summary_df['Total Investment'].sum() * 100) if summary_df['Total Investment'].sum() > 0 else 0
        }

        # Convert DataFrame to dict
        summary_df = summary_df.fillna(0)
        scripts = summary_df.to_dict('records')

        return JSONResponse({
            'totals': totals,
            'scripts': scripts,
            'script_count': len(summary_df)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/holdings")
async def get_current_holdings():
    """Get current holdings"""
    try:
        current_prices = get_current_prices()
        holdings_df = analyzer.get_current_holdings_summary(current_prices)

        # Convert date columns to string
        if 'First Purchase' in holdings_df.columns:
            holdings_df['First Purchase'] = holdings_df['First Purchase'].astype(str)

        holdings_df = holdings_df.fillna(0)

        return JSONResponse({
            'holdings': holdings_df.to_dict('records'),
            'count': len(holdings_df)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions")
async def get_transaction_history():
    """Get complete transaction history"""
    try:
        trans_df = analyzer.get_transaction_history()
        trans_df['Date'] = trans_df['Date'].astype(str)
        trans_df = trans_df.fillna('')

        return JSONResponse({
            'transactions': trans_df.to_dict('records'),
            'count': len(trans_df)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pools")
async def get_detailed_pools():
    """Get detailed holdings by pool (weighted average cost)"""
    try:
        current_prices = get_current_prices()
        pools_df = analyzer.get_detailed_pools(current_prices)
        if 'First Purchase Date' in pools_df.columns:
            pools_df['First Purchase Date'] = pools_df['First Purchase Date'].astype(str)
        if 'Last Purchase Date' in pools_df.columns:
            pools_df['Last Purchase Date'] = pools_df['Last Purchase Date'].astype(str)
        pools_df = pools_df.fillna(0)

        return JSONResponse({
            'pools': pools_df.to_dict('records'),
            'count': len(pools_df)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interest")
async def get_interest_analysis():
    """Get interest cost analysis for current holdings"""
    try:
        interest_df = analyzer.get_interest_analysis()
        interest_df = interest_df.fillna(0)

        total_interest = float(interest_df['Interest Cost'].sum())
        total_investment = float(interest_df['Investment Amount'].sum())

        return JSONResponse({
            'analysis': interest_df.to_dict('records'),
            'total_interest': total_interest,
            'total_investment': total_investment,
            'avg_interest_pct': total_interest / total_investment * 100 if total_investment > 0 else 0
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sold-interest")
async def get_sold_interest_analysis():
    """Get interest cost analysis for sold stocks"""
    try:
        sold_interest_df = analyzer.get_sold_interest_analysis()
        sold_interest_df = sold_interest_df.fillna(0)

        total_interest = float(sold_interest_df['Interest Cost'].sum()) if not sold_interest_df.empty else 0
        total_investment = float(sold_interest_df['Investment Amount'].sum()) if not sold_interest_df.empty else 0
        total_realized = float(sold_interest_df['Realized P&L'].sum()) if not sold_interest_df.empty else 0
        total_net_pnl = float(sold_interest_df['Net P&L (After Interest)'].sum()) if not sold_interest_df.empty else 0

        return JSONResponse({
            'analysis': sold_interest_df.to_dict('records'),
            'total_interest': total_interest,
            'total_investment': total_investment,
            'total_realized_pnl': total_realized,
            'total_net_pnl': total_net_pnl,
            'avg_interest_pct': total_interest / total_investment * 100 if total_investment > 0 else 0
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/script/{symbol}")
async def get_script_detail(symbol: str):
    """Get detailed information for a specific script"""
    try:
        current_prices = get_current_prices()
        wacc_data = get_wacc_data()

        # Portfolio summary for this script
        summary_df = analyzer.get_portfolio_summary(current_prices, wacc_data)
        script_summary = summary_df[summary_df['Scrip'] == symbol]

        if script_summary.empty:
            raise HTTPException(status_code=404, detail=f"Script {symbol} not found")

        # Transaction history for this script
        trans_df = analyzer.get_transaction_history()
        script_trans = trans_df[trans_df['Scrip'] == symbol].copy()
        script_trans['Date'] = script_trans['Date'].astype(str)

        # Current pool for this script
        pools_df = analyzer.get_detailed_pools(current_prices)
        script_pool = pools_df[pools_df['Scrip'] == symbol].copy()
        if 'First Purchase Date' in script_pool.columns:
            script_pool['First Purchase Date'] = script_pool['First Purchase Date'].astype(str)
        if 'Last Purchase Date' in script_pool.columns:
            script_pool['Last Purchase Date'] = script_pool['Last Purchase Date'].astype(str)

        script_summary = script_summary.fillna(0)
        script_trans = script_trans.fillna('')
        script_pool = script_pool.fillna(0)

        return JSONResponse({
            'summary': script_summary.to_dict('records')[0],
            'transactions': script_trans.to_dict('records'),
            'pool': script_pool.to_dict('records')[0] if len(script_pool) > 0 else None,
            'current_price': current_prices.get(symbol, 0)
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_portfolio_stats():
    """Get portfolio statistics"""
    try:
        current_prices = get_current_prices()
        wacc_data = get_wacc_data()
        summary_df = analyzer.get_portfolio_summary(current_prices, wacc_data)
        holdings_df = analyzer.get_current_holdings_summary(current_prices)
        trans_df = analyzer.get_transaction_history()

        # Top performers - use current holdings with at least 15 shares and Unrealized P&L %
        filtered_holdings = holdings_df[holdings_df['Quantity'] >= 15].copy()
        filtered_holdings = filtered_holdings.dropna(subset=['Unrealized P&L %'])
        top_5 = filtered_holdings.nlargest(5, 'Unrealized P&L %')[['Scrip', 'Unrealized P&L', 'Unrealized P&L %']].to_dict('records')
        bottom_5 = filtered_holdings.nsmallest(5, 'Unrealized P&L %')[['Scrip', 'Unrealized P&L', 'Unrealized P&L %']].to_dict('records')

        # Close to 52 Week High - calculate distance from 52 week high for current holdings
        close_to_high = []
        for _, script in summary_df.iterrows():
            try:
                # Check if all required values are present and valid
                if (script['Current Holdings'] > 0 and
                    pd.notna(script['52 Week High']) and
                    pd.notna(script['Current Price']) and
                    script['52 Week High'] != 0 and
                    script['Current Price'] != 0):

                    current_price = float(script['Current Price'])
                    week_52_high = float(script['52 Week High'])
                    distance_pct = ((current_price - week_52_high) / week_52_high) * 100

                    # Skip if distance is NaN or infinite
                    if pd.notna(distance_pct) and not math.isinf(distance_pct):
                        close_to_high.append({
                            'Scrip': script['Scrip'],
                            'Current Price': current_price,
                            '52 Week High': week_52_high,
                            'Distance from High %': round(distance_pct, 2)
                        })
            except (ValueError, TypeError, ZeroDivisionError):
                # Skip scripts with invalid data
                continue

        # Sort by distance (closest to 52 week high = highest percentage, which is least negative)
        close_to_high = sorted(close_to_high, key=lambda x: x['Distance from High %'], reverse=True)[:10]

        # Close to 52 Week Low - calculate distance from 52 week low for current holdings
        close_to_low = []
        for _, script in summary_df.iterrows():
            try:
                # Check if all required values are present and valid
                if (script['Current Holdings'] > 0 and
                    pd.notna(script['52 Week Low']) and
                    pd.notna(script['Current Price']) and
                    script['52 Week Low'] != 0 and
                    script['Current Price'] != 0):

                    current_price = float(script['Current Price'])
                    week_52_low = float(script['52 Week Low'])
                    distance_pct = ((current_price - week_52_low) / week_52_low) * 100

                    # Skip if distance is NaN or infinite
                    if pd.notna(distance_pct) and not math.isinf(distance_pct):
                        close_to_low.append({
                            'Scrip': script['Scrip'],
                            'Current Price': current_price,
                            '52 Week Low': week_52_low,
                            'Distance from Low %': round(distance_pct, 2)
                        })
            except (ValueError, TypeError, ZeroDivisionError):
                # Skip scripts with invalid data
                continue

        # Sort by distance (closest to 52 week low = lowest percentage, which is closest to 0)
        close_to_low = sorted(close_to_low, key=lambda x: x['Distance from Low %'])[:10]

        # Transaction type breakdown
        type_counts = trans_df['Type'].value_counts().to_dict()

        stats = {
            'total_scripts': len(summary_df),
            'scripts_with_holdings': len(holdings_df),
            'scripts_fully_sold': len(summary_df[summary_df['Current Holdings'] == 0]),
            'total_transactions': len(trans_df),
            'profit_making_scripts': len(summary_df[summary_df['Total P&L'] > 0]),
            'loss_making_scripts': len(summary_df[summary_df['Total P&L'] < 0]),
            'break_even_scripts': len(summary_df[summary_df['Total P&L'] == 0]),
            'transaction_breakdown': type_counts,
            'top_performers': top_5,
            'bottom_performers': bottom_5,
            'close_to_52week_high': close_to_high,
            'close_to_52week_low': close_to_low
        }

        return JSONResponse(stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{report_type}")
async def export_report(report_type: str):
    """Export report as CSV"""
    try:
        file_mapping = {
            'summary': 'portfolio_summary.csv',
            'holdings': 'current_holdings.csv',
            'transactions': 'transaction_history.csv',
            'pools': 'detailed_holdings_pools.csv',
            'interest': 'interest_analysis.csv'
        }

        if report_type not in file_mapping:
            raise HTTPException(status_code=400, detail="Invalid report type")

        # Check in reports directory first, then base directory
        reports_dir = Path(analyzer.base_dir, 'reports')
        file_path = Path(reports_dir, file_mapping[report_type])

        if not file_path.exists():
            file_path = Path(analyzer.base_dir, file_mapping[report_type])

        if not file_path.exists():
            # Generate reports if they don't exist
            analyzer.generate_reports()
            file_path = Path(reports_dir, file_mapping[report_type])

        return FileResponse(
            path=file_path,
            filename=file_mapping[report_type],
            media_type='text/csv'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
