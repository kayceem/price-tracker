"""
Floorsheet API Routes for FastAPI
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, and_
from datetime import datetime
from typing import Optional

from src.database import get_db, Floorsheet, Scripts, Broker

router = APIRouter(prefix="/api/floorsheet", tags=["floorsheet"])


@router.get("/dates")
async def get_available_dates():
    """Get all available trading dates with floorsheet data"""
    try:
        async with get_db() as db:
            result = await db.execute(
                select(Floorsheet.trade_date)
                .distinct()
                .order_by(Floorsheet.trade_date.desc())
            )
            dates = [row[0] for row in result.all()]

            return JSONResponse({
                'dates': dates,
                'count': len(dates)
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies")
async def get_available_companies(date: Optional[str] = Query(None, description="Filter by trade date")):
    """Get all companies with floorsheet data, optionally filtered by date"""
    try:
        async with get_db() as db:
            query = select(Scripts.ticker).join(
                Floorsheet, Floorsheet.script_id == Scripts.id
            ).distinct()

            if date:
                query = query.filter(Floorsheet.trade_date == date)

            query = query.order_by(Scripts.ticker.asc())

            result = await db.execute(query)
            companies = [row[0] for row in result.all()]

            return JSONResponse({
                'companies': companies,
                'count': len(companies)
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data")
async def get_floorsheet_data(
    date: Optional[str] = Query(None, description="Trade date in YYYY-MM-DD format"),
    ticker: Optional[str] = Query(None, description="Stock ticker symbol")
):
    """Get floorsheet data for a specific date and/or ticker"""
    try:
        async with get_db() as db:
            # Build query with aliases for buyer and seller brokers
            buyer_broker = Broker.__table__.alias('buyer_broker')
            seller_broker = Broker.__table__.alias('seller_broker')

            query = select(
                Floorsheet,
                Scripts.ticker.label('stock_symbol'),
                buyer_broker.c.member_id.label('buyer_member_id'),
                seller_broker.c.member_id.label('seller_member_id')
            ).join(
                Scripts, Floorsheet.script_id == Scripts.id
            ).join(
                buyer_broker, Floorsheet.buyer_broker_id == buyer_broker.c.id
            ).join(
                seller_broker, Floorsheet.seller_broker_id == seller_broker.c.id
            )

            # Add filters
            filters = []
            if date:
                filters.append(Floorsheet.trade_date == date)
            if ticker:
                filters.append(Scripts.ticker == ticker)

            if filters:
                query = query.filter(and_(*filters))

            # Order by trade time
            query = query.order_by(Floorsheet.trade_time.asc())

            result = await db.execute(query)
            rows = result.all()

            # Convert to list of dicts
            floorsheet_data = []
            for row in rows:
                floorsheet_data.append({
                    'contract_id': row.Floorsheet.contract_id,
                    'stock_symbol': row.stock_symbol,
                    'buyer_member_id': row.buyer_member_id,
                    'seller_member_id': row.seller_member_id,
                    'contract_quantity': row.Floorsheet.contract_quantity,
                    'contract_rate': row.Floorsheet.contract_rate,
                    'contract_amount': row.Floorsheet.contract_amount,
                    'trade_date': row.Floorsheet.trade_date,
                    'trade_time': row.Floorsheet.trade_time
                })

            return JSONResponse({
                'floorsheet': floorsheet_data,
                'count': len(floorsheet_data)
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_floorsheet_summary(
    date: str = Query(..., description="Trade date in YYYY-MM-DD format"),
    ticker: Optional[str] = Query(None, description="Stock ticker symbol")
):
    """Get consecutive buyer broker summary for a specific date"""
    try:
        async with get_db() as db:
            # Build query
            query = select(
                Floorsheet,
                Scripts.ticker.label('stock_symbol'),
                Broker.name.label('buyer_broker_name'),
                Broker.member_id.label('buyer_member_id')
            ).join(
                Scripts, Floorsheet.script_id == Scripts.id
            ).join(
                Broker, Floorsheet.buyer_broker_id == Broker.id
            ).filter(
                Floorsheet.trade_date == date
            )

            if ticker:
                query = query.filter(Scripts.ticker == ticker)

            # Order by trade time (chronological order)
            query = query.order_by(Floorsheet.trade_time.asc())

            result = await db.execute(query)
            rows = result.all()

            # Group consecutive trades by buyer broker
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

                # If same broker as previous trade, accumulate
                if buyer_id == current_broker_id:
                    current_quantity += quantity
                    current_trade_count += 1
                    current_total_amount += amount
                    current_prices.append(price)
                else:
                    # Save previous group if it exists
                    if current_broker_id is not None:
                        avg_price = current_total_amount / current_quantity if current_quantity > 0 else 0
                        summaries.append({
                            'broker_id': current_broker_id,
                            'broker_name': current_broker_name,
                            'quantity': current_quantity,
                            'trades': current_trade_count,
                            'total_amount': current_total_amount,
                            'average_price': round(avg_price, 2),
                            'min_price': min(current_prices),
                            'max_price': max(current_prices),
                            'start_time': current_start_time
                        })

                    # Start new group
                    current_broker_id = buyer_id
                    current_broker_name = buyer_name
                    current_quantity = quantity
                    current_trade_count = 1
                    current_total_amount = amount
                    current_prices = [price]
                    current_start_time = trade_time

            # Don't forget the last group
            if current_broker_id is not None:
                avg_price = current_total_amount / current_quantity if current_quantity > 0 else 0
                summaries.append({
                    'broker_id': current_broker_id,
                    'broker_name': current_broker_name,
                    'quantity': current_quantity,
                    'trades': current_trade_count,
                    'total_amount': current_total_amount,
                    'average_price': round(avg_price, 2),
                    'min_price': min(current_prices),
                    'max_price': max(current_prices),
                    'start_time': current_start_time
                })

            # Calculate statistics
            total_groups = len(summaries)
            total_trades = sum(s['trades'] for s in summaries)
            total_quantity = sum(s['quantity'] for s in summaries)
            total_amount = sum(s['total_amount'] for s in summaries)

            return JSONResponse({
                'summaries': summaries,
                'statistics': {
                    'total_groups': total_groups,
                    'total_trades': total_trades,
                    'total_quantity': total_quantity,
                    'total_amount': round(total_amount, 2)
                }
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
