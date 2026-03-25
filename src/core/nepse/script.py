from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select

from src.database import Scripts, get_db
from src.database import ScriptDetails
from src.database import Tracker
from src.database import ScriptDetailsSchema
from sqlalchemy.orm import selectinload

from .fetch import fetch_script_details, fetch_all_script_details

from src.utils import check_time_delta, valid_day_time
from sqlalchemy.orm import Session

async def get_script_ltp(db : Session, script:Scripts):
    if not script.script_details or (check_time_delta(script.script_details.updated_at, 30) and valid_day_time()):
        try:
            script_details = ScriptDetailsSchema(**await fetch_script_details(script.href, script.id))
            script.script_details = ScriptDetails(**script_details.model_dump())
            await db.commit()
            return script.script_details.last_traded_price
        except Exception as e:
            print(e)
            return None
    return script.script_details.last_traded_price

async def refresh_script_detail(ticker):
    async with get_db() as db:
        script = (await db.execute(select(Scripts).filter(Scripts.ticker==ticker))).scalars().first()
    if not script:
        return False
    with ThreadPoolExecutor() as executor:
        future = executor.submit(fetch_script_details, script.href ,script.id)
        # await as_completed(future)
        try:
            scripts_details = ScriptDetailsSchema(**await future.result())
        except Exception as e:
            print(e)
    async with get_db() as db:
        script = (await db.execute(select(Scripts).filter(Scripts.id == scripts_details.script_id).options(selectinload(Scripts.script_details)))).scalars().first()
        script.script_details = ScriptDetails(**scripts_details.model_dump())
        await db.commit()
    return True

async def refresh_script_details():
    async with get_db() as db:
        scripts = (await db.execute(select(Scripts).join(Tracker))).scalars().all()
    if not scripts:
        return False
    scripts_details = []
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_script_details, script.href ,script.id) for script in scripts]
        for future in as_completed(futures):
            try:
                scripts_details.append(ScriptDetailsSchema(**await future.result()))
            except Exception as e:
                print(e)
    async with get_db() as db:
        for details in scripts_details:
            script = (await db.execute(select(Scripts).filter(Scripts.id == details.script_id).options(selectinload(Scripts.script_details)))).scalars().first()
            script.script_details = ScriptDetails(**details.model_dump())
            await db.commit()
    return True

async def refresh_all_script_details():
    data = await fetch_all_script_details()
    details_by_ticker = {details["ticker"]: details for details in data}
    async with get_db() as db:
        scripts = (await db.execute(
            select(Scripts).options(selectinload(Scripts.script_details))
        )).scalars().all()

        for script in scripts:
            details = details_by_ticker.get(script.ticker)
            if details:
                if script.script_details:
                    # Update existing record
                    script.script_details.last_traded_price = float(details["last_traded_price"])
                    script.script_details.total_traded_quantity = int(details["total_traded_quantity"])
                    script.script_details.total_trades = int(details["total_trades"])
                    script.script_details.previous_day_close_price = float(details["previous_day_close_price"])
                    script.script_details.high_price_low_price = details["high_price_low_price"]
                    script.script_details.week_52_high_low = details["week_52_high_low"]
                    script.script_details.open_price = float(details["open_price"])
                    script.script_details.close_price = float(details["close"] if details["close"] != "-" else details["last_traded_price"])
                    script.script_details.market_capitalization = float(details["market_capitalization"]) if details["market_capitalization"] and details["market_capitalization"] != "-" else None
                else:
                    # Create new record
                    script.script_details = ScriptDetails(
                        script_id=script.id,
                        last_traded_price=float(details["last_traded_price"]),
                        total_traded_quantity=int(details["total_traded_quantity"]),
                        total_trades=int(details["total_trades"]),
                        previous_day_close_price=float(details["previous_day_close_price"]),
                        high_price_low_price=details["high_price_low_price"],
                        week_52_high_low=details["week_52_high_low"],
                        open_price=float(details["open_price"]),
                        close_price=float(details["close"] if details["close"] != "-" else details["last_traded_price"]),
                        market_capitalization=float(details["market_capitalization"]) if details["market_capitalization"] and details["market_capitalization"] != "-" else None
                    )
        await db.commit()
    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(refresh_all_script_details())