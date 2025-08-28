from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select

from database import Scripts, get_db
from database import ScriptDetails
from database import Tracker
from database import ScriptDetailsSchema
from sqlalchemy.orm import selectinload

from .fetch import fetch_script_details

from utils import check_time_delta, valid_day_time
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
    async with get_db() as db:
        scripts = (await db.execute(select(Scripts))).scalars().all()
    if not scripts:
        return False
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_script_details, script.href ,script.id) for script in scripts]
        async with get_db() as db:
            for future in as_completed(futures):
                try:
                    details = ScriptDetailsSchema(**await future.result())
                    script = (await db.execute(select(Scripts).filter(Scripts.id == details.script_id).options(selectinload(Scripts.script_details)))).scalars().first()
                    script.script_details = ScriptDetails(**details.model_dump())
                    await db.commit()
                    print(f"{script.ticker}")
                except Exception as e:
                    print(e)
    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(refresh_all_script_details())