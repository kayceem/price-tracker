import argparse
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.config.settings import config
from src.database import get_db, Floorsheet, FloorsheetSchema, FetchListItemSchema, Scripts, Broker, BrokerSchema
from src.core.nepse.client import NEPSE
import json

logger = logging.getLogger(__name__)

class FloorsheetFetcher:
    """Fetches floorsheet data from NEPSE API and stores in database."""

    def __init__(self):
        self.nepse = NEPSE()

    async def aclose(self) -> None:
        await self.nepse.aclose()

    async def get_stock_id(self, ticker: str) -> Optional[int]:
        """Get NEPSE stock ID from database by ticker symbol."""
        async with get_db() as db:
            result = await db.execute(
                select(Scripts).filter(Scripts.ticker == ticker)
            )
            script = result.scalars().first()
            if not script:
                return None

            # Return nepse_id if available, otherwise parse from href
            if script.nepse_id:
                return script.nepse_id

            # Fallback: parse from href
            try:
                return int(script.href.split("/")[-1])
            except (ValueError, IndexError):
                return None

    async def check_existing_data(self, ticker: str, date: str) -> bool:
        """Check if floorsheet data already exists for given ticker and date."""
        async with get_db() as db:
            # Get script by ticker
            script_result = await db.execute(
                select(Scripts).filter(Scripts.ticker == ticker)
            )
            script = script_result.scalars().first()

            if not script:
                return False

            # Check if floorsheet exists for this script and date
            result = await db.execute(
                select(Floorsheet).filter(
                    Floorsheet.script_id == script.id,
                    Floorsheet.trade_date == date
                )
            )
            return result.scalars().first() is not None

    async def fetch_floorsheet(
        self,
        stock_id: int,
        ticker: str,
        date: str,
        page: int = 0,
        size: int = 500
    ) -> dict:
        """Fetch floorsheet data from NEPSE API."""
        try:
            data = await self.nepse.fetch_floorsheet(
                stock_id=stock_id,
                symbol=ticker,
                business_date=date,
                page=page,
                size=size,
            )
            if not data:
                logger.warning(
                    "Empty floorsheet response for ticker=%s stock_id=%s business_date=%s",
                    ticker,
                    stock_id,
                    date,
                )
                return {}
            return data
        except Exception as e:
            logger.exception("Error fetching floorsheet for ticker=%s business_date=%s", ticker, date)
            return {}

    async def get_or_create_broker(self, db, member_id: str, name: str) -> int:
        """Get or create a broker and return its ID."""
        # Try to find existing broker
        if not member_id:
            return None
        
        result = await db.execute(
            select(Broker).filter(Broker.member_id == member_id)
        )
        broker = result.scalars().first()

        if broker:
            # Update name if it's different (in case of data updates)
            if broker.name != name:
                broker.name = name
                await db.commit()
            return broker.id

        # Create new broker
        broker_schema = BrokerSchema(member_id=member_id, name=name)
        broker = Broker(**broker_schema.model_dump())
        db.add(broker)
        await db.flush()  # Flush to get the ID without committing
        return broker.id

    async def get_or_update_script(self, db, stock_id: int, symbol: str, name: str) -> int:
        """Get or update script and return its ID."""
        # Try to find by NEPSE ID
        result = await db.execute(
            select(Scripts).filter(Scripts.nepse_id == stock_id)
        )
        script = result.scalars().first()

        if script:
            # Update name if provided and different
            if name and script.name != name:
                script.name = name
                await db.commit()
            return script.id

        # Try to find by ticker
        result = await db.execute(
            select(Scripts).filter(Scripts.ticker == symbol)
        )
        script = result.scalars().first()

        if script:
            # Update NEPSE ID and name
            script.nepse_id = stock_id
            if name:
                script.name = name
            await db.commit()
            return script.id

        logger.info("Creating missing script from floorsheet for ticker=%s stock_id=%s", symbol, stock_id)
        script = Scripts(
            ticker=symbol,
            name=name,
            href=f"/company/detail/{stock_id}",
            nepse_id=stock_id,
        )
        db.add(script)
        await db.flush()
        await db.commit()
        return script.id

    async def get_or_update_floorsheet(
        self,
        db,
        contract_id: int,
        trade_date: str,
        floorsheet_data: dict
    ) -> tuple[Floorsheet, bool]:
        """
        Get existing floorsheet by contract_id or create new one.
        Returns (floorsheet, is_new) tuple.
        """
        # Try to find existing floorsheet by contract_id
        result = await db.execute(
            select(Floorsheet).filter(Floorsheet.contract_id == contract_id)
        )
        floorsheet = result.scalars().first()

        is_new = False
        if floorsheet:
            # Update existing record
            for key, value in floorsheet_data.items():
                if hasattr(floorsheet, key):
                    setattr(floorsheet, key, value)
        else:
            # Create new record
            floorsheet = Floorsheet(**floorsheet_data)
            db.add(floorsheet)
            is_new = True

        return floorsheet, is_new

    async def save_floorsheet_data(self, floorsheet_items: list[dict]) -> tuple[int, int, int]:
        """
        Save floorsheet data to database with broker and script relationships.
        Returns (new_count, updated_count, skipped_count).
        """
        new_count = 0
        updated_count = 0
        skipped_count = 0

        async with get_db() as db:
            for item in floorsheet_items:
                try:
                    # Parse the floorsheet schema
                    floorsheet_schema = FloorsheetSchema(**item)

                    # Get or create brokers
                    buyer_broker_id = await self.get_or_create_broker(
                        db,
                        floorsheet_schema.buyer_member_id,
                        floorsheet_schema.buyer_broker_name or f"Broker {floorsheet_schema.buyer_member_id}"
                    )

                    seller_broker_id = await self.get_or_create_broker(
                        db,
                        floorsheet_schema.seller_member_id,
                        floorsheet_schema.seller_broker_name or f"Broker {floorsheet_schema.seller_member_id}"
                    )

                    # Get or update script
                    script_id = await self.get_or_update_script(
                        db,
                        floorsheet_schema.stock_id,
                        floorsheet_schema.stock_symbol,
                        floorsheet_schema.security_name
                    )

                    if not script_id:
                        logger.warning("Skipping floorsheet record contract_id=%s: script not found", item.get("contractId"))
                        skipped_count += 1
                        continue

                    # Set the IDs in the schema
                    floorsheet_schema.script_id = script_id
                    floorsheet_schema.buyer_broker_id = buyer_broker_id
                    floorsheet_schema.seller_broker_id = seller_broker_id

                    # Prepare floorsheet data (exclude the temporary fields)
                    floorsheet_data = floorsheet_schema.model_dump(
                        exclude={'stock_symbol', 'stock_id', 'buyer_member_id', 'seller_member_id',
                                'buyer_broker_name', 'seller_broker_name', 'security_name'}
                    )

                    # Get or update floorsheet record
                    floorsheet, is_new = await self.get_or_update_floorsheet(
                        db,
                        floorsheet_schema.contract_id,
                        floorsheet_schema.trade_date,
                        floorsheet_data
                    )

                    await db.commit()
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1

                except IntegrityError as e:
                    await db.rollback()
                    logger.warning("Duplicate floorsheet record for contract_id=%s", item.get("contractId"))
                    skipped_count += 1
                except Exception as e:
                    await db.rollback()
                    logger.exception("Error saving floorsheet record contract_id=%s", item.get("contractId"))
                    skipped_count += 1

        return new_count, updated_count, skipped_count

    async def fetch_and_save(
        self,
        ticker: str,
        date: str,
        force: bool = False
    ) -> dict:
        """Fetch and save floorsheet data for a ticker and date."""
        if not force and await self.check_existing_data(ticker, date):
            logger.info("Floorsheet data already exists for ticker=%s business_date=%s", ticker, date)
            return {"ticker": ticker, "date": date, "status": "skipped", "reason": "already_exists"}

        stock_id = await self.get_stock_id(ticker)
        if not stock_id:
            logger.warning("Stock ID not found for ticker=%s", ticker)
            return {"ticker": ticker, "date": date, "status": "error", "reason": "stock_not_found"}

        logger.info("Fetching floorsheet for ticker=%s stock_id=%s business_date=%s", ticker, stock_id, date)
        page = 0
        total_new = 0
        total_updated = 0
        total_skipped = 0

        while True:
            data = await self.fetch_floorsheet(stock_id, ticker, date, page)

            if not data or "floorsheets" not in data:
                break

            floorsheet_data = data["floorsheets"]
            content = floorsheet_data.get("content", [])

            if not content:
                break

            new, updated, skipped = await self.save_floorsheet_data(content)
            total_new += new
            total_updated += updated
            total_skipped += skipped

            logger.info(
                "Floorsheet page processed ticker=%s business_date=%s page=%s new=%s updated=%s skipped=%s",
                ticker,
                date,
                page,
                new,
                updated,
                skipped,
            )

            if floorsheet_data.get("last", True):
                break

            page += 1

        total_saved = total_new + total_updated
        logger.info(
            "Floorsheet fetch complete ticker=%s business_date=%s new=%s updated=%s skipped=%s",
            ticker,
            date,
            total_new,
            total_updated,
            total_skipped,
        )
        return {
            "ticker": ticker,
            "date": date,
            "status": "success",
            "new": total_new,
            "updated": total_updated,
            "saved": total_saved,
            "skipped": total_skipped
        }

    async def fetch_from_list(self, fetch_list: list[dict]) -> list[dict]:
        """Fetch floorsheet data for multiple tickers and dates from a list."""
        results = []

        try:
            for item in fetch_list:
                try:
                    fetch_item = FetchListItemSchema(**item)

                    result = await self.fetch_and_save(
                            fetch_item.ticker,
                            fetch_item.date,
                            fetch_item.force
                        )
                    results.append(result)
                except Exception as e:
                    logger.exception("Error processing floorsheet fetch item: %s", item)
                    results.append({
                        "ticker": item.get("ticker"),
                        "status": "error",
                        "reason": str(e)
                    })

            return results
        finally:
            await self.aclose()


async def main():
    parser = argparse.ArgumentParser(description="Fetch NEPSE floorsheet data")
    parser.add_argument("--ticker", type=str, help="Stock ticker symbol")
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format")
    parser.add_argument("--dates", type=str, nargs="+", help="Multiple dates in YYYY-MM-DD format")
    parser.add_argument("--force", action="store_true", help="Force refetch even if data exists")
    parser.add_argument("--fetch-list", type=str, help="Path to JSON file with fetch list")

    args = parser.parse_args()

    fetcher = FloorsheetFetcher()

    try:
        if args.fetch_list:
            fetch_list_path = Path(args.fetch_list)
            if not fetch_list_path.exists():
                logger.error("Fetch list file not found: %s", args.fetch_list)
                return

            with open(fetch_list_path, "r") as f:
                fetch_list = json.load(f)

            results = await fetcher.fetch_from_list(fetch_list)
            for result in results:
                logger.info("Floorsheet fetch result: %s", result)

        elif args.ticker:
            result = await fetcher.fetch_and_save(args.ticker, args.date, args.force)
            logger.info("Floorsheet fetch result: %s", result)

        else:
            parser.print_help()
    finally:
        await fetcher.aclose()


if __name__ == "__main__":
    asyncio.run(main())
