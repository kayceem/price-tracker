import argparse
import asyncio
import json
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wasmtime import Store, Module, Instance
from src.config.settings import config
from src.database import get_db, Floorsheet, FloorsheetSchema, FetchListItemSchema, Scripts, Broker, BrokerSchema


class NepseAuthenticator:
    """Handles authentication with NEPSE API."""

    def __init__(self):
        self.base_url = "https://www.nepalstock.com"
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.salt_values: list[int] = []  # Store salt1-salt5 from initial /prove
        self.original_salt_values: list[int] = []  # Keep original salts for ID calculation
        self.market_status_id: Optional[int] = None  # dummyId from market-open API
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/floor-sheet",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
        }

        # Load WebAssembly module for token trimming
        self.wasm_store = Store()
        wasm_path = config.data_dir / "css.wasm"
        self.wasm_module = Module.from_file(self.wasm_store.engine, str(wasm_path))
        self.wasm_instance = Instance(self.wasm_store, self.wasm_module, [])

    async def get_market_status(self, client: httpx.AsyncClient) -> bool:
        """Get market status which includes the dummyId."""
        try:
            response = await client.get(
                f"{self.base_url}/api/nots/nepse-data/market-open",
                headers=self.get_auth_headers()
            )
            response.raise_for_status()
            data = response.json()
            self.market_status_id = data.get("id")
            return bool(self.market_status_id is not None)
        except Exception as e:
            print(f"Failed to get market status: {e}")
            return False

    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Get initial access token and refresh token."""
        try:
            response = await client.get(
                f"{self.base_url}/api/authenticate/prove",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessToken")
            self.refresh_token = data.get("refreshToken")

            # Store salt values for request ID calculation
            self.salt_values = [
                data.get("salt1", 0),
                data.get("salt2", 0),
                data.get("salt3", 0),
                data.get("salt4", 0),
                data.get("salt5", 0)
            ]

            # Store original salts - these are used for request ID calculation
            # even after token refresh
            self.original_salt_values = self.salt_values.copy()

            # Trim tokens using WebAssembly functions
            self.access_token = self._trim_access_token(self.access_token, self.salt_values)
            self.refresh_token = self._trim_refresh_token(self.refresh_token, self.salt_values)

            # Get market status to obtain dummyId
            await self.get_market_status(client)

            return bool(self.access_token)
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False

    async def refresh_access_token(self, client: httpx.AsyncClient) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            return await self.authenticate(client)

        try:
            headers = {**self.headers, "Authorization": f"Salter {self.refresh_token}"}
            response = await client.post(
                f"{self.base_url}/api/authenticate/refresh-token",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessToken")
            self.refresh_token = data.get("refreshToken")

            # Update current salt values after token refresh
            self.salt_values = [
                data.get("salt1", 0),
                data.get("salt2", 0),
                data.get("salt3", 0),
                data.get("salt4", 0),
                data.get("salt5", 0)
            ]

            # IMPORTANT: Keep original_salt_values unchanged!
            # Request ID calculation always uses the original /prove salts

            # Trim the refreshed tokens
            self.access_token = self._trim_access_token(self.access_token, self.salt_values)
            self.refresh_token = self._trim_refresh_token(self.refresh_token, self.salt_values)

            return bool(self.access_token)
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return await self.authenticate(client)

    def _trim_access_token(self, token: str, salt_values: list[int]) -> str:
        """
        Trim access token by removing characters at positions determined by WebAssembly functions.
        Pattern: token.slice(0, cdx) + token.slice(cdx+1, rdx) + ... + token.slice(mdx+1)
        """
        s1, s2, s3, s4, s5 = salt_values

        # Get WASM exports
        cdx = self.wasm_instance.exports(self.wasm_store)["cdx"]
        rdx = self.wasm_instance.exports(self.wasm_store)["rdx"]
        bdx = self.wasm_instance.exports(self.wasm_store)["bdx"]
        ndx = self.wasm_instance.exports(self.wasm_store)["ndx"]
        mdx = self.wasm_instance.exports(self.wasm_store)["mdx"]

        # Calculate positions (note the parameter order from snippet.js)
        cdx_pos = cdx(self.wasm_store, s1, s2, s3, s4, s5)
        rdx_pos = rdx(self.wasm_store, s1, s2, s4, s3, s5)  # salt3 and salt4 swapped
        bdx_pos = bdx(self.wasm_store, s1, s2, s4, s3, s5)
        ndx_pos = ndx(self.wasm_store, s1, s2, s4, s3, s5)
        mdx_pos = mdx(self.wasm_store, s1, s2, s4, s3, s5)

        # Apply trimming - skip characters at these positions
        trimmed = (
            token[:cdx_pos] +
            token[cdx_pos + 1:rdx_pos] +
            token[rdx_pos + 1:bdx_pos] +
            token[bdx_pos + 1:ndx_pos] +
            token[ndx_pos + 1:mdx_pos] +
            token[mdx_pos + 1:]
        )

        return trimmed

    def _trim_refresh_token(self, token: str, salt_values: list[int]) -> str:
        """
        Trim refresh token by removing characters at positions determined by WebAssembly functions.
        Uses different parameter order than access token.
        """
        s1, s2, s3, s4, s5 = salt_values

        # Get WASM exports
        cdx = self.wasm_instance.exports(self.wasm_store)["cdx"]
        rdx = self.wasm_instance.exports(self.wasm_store)["rdx"]
        bdx = self.wasm_instance.exports(self.wasm_store)["bdx"]
        ndx = self.wasm_instance.exports(self.wasm_store)["ndx"]
        mdx = self.wasm_instance.exports(self.wasm_store)["mdx"]

        # Calculate positions (different parameter order for refresh token)
        cdx_pos = cdx(self.wasm_store, s2, s1, s3, s5, s4)
        rdx_pos = rdx(self.wasm_store, s2, s1, s3, s4, s5)
        bdx_pos = bdx(self.wasm_store, s2, s1, s4, s3, s5)
        ndx_pos = ndx(self.wasm_store, s2, s1, s4, s3, s5)
        mdx_pos = mdx(self.wasm_store, s2, s1, s4, s3, s5)

        # Apply trimming
        trimmed = (
            token[:cdx_pos] +
            token[cdx_pos + 1:rdx_pos] +
            token[rdx_pos + 1:bdx_pos] +
            token[bdx_pos + 1:ndx_pos] +
            token[ndx_pos + 1:mdx_pos] +
            token[mdx_pos + 1:]
        )

        return trimmed

    def get_auth_headers(self) -> dict:
        """Get headers with authorization token."""
        return {
            **self.headers,
            "Authorization": f"Salter {self.access_token}"
        }

    def calculate_request_id(self) -> int:
        """
        Calculate the request ID using salt values.
        Based on: i + accessTokens[index] * day - accessTokens[index - 1]
        where i = getDummyData()[dummyId] + dummyId + 2 * day
        """
        # Dummy data array from NEPSE's obfuscated JavaScript
        dummy_data = [
            147, 117, 239, 143, 157, 312, 161, 612, 512, 804, 411, 527, 170, 511, 421, 667, 764, 621, 301, 106,
            133, 793, 411, 511, 312, 423, 344, 346, 653, 758, 342, 222, 236, 811, 711, 611, 122, 447, 128, 199,
            183, 135, 489, 703, 800, 745, 152, 863, 134, 211, 142, 564, 375, 793, 212, 153, 138, 153, 648, 611,
            151, 649, 318, 143, 117, 756, 119, 141, 717, 113, 112, 146, 162, 660, 693, 261, 362, 354, 251, 641,
            157, 178, 631, 192, 734, 445, 192, 883, 187, 122, 591, 731, 852, 384, 565, 596, 451, 772, 624, 691
        ]

        day = datetime.now().day

        # dummyId comes from market-open API response
        dummy_id = self.market_status_id if self.market_status_id is not None else 1

        if dummy_id >= len(dummy_data):
            dummy_id = dummy_id % len(dummy_data)

        # Get dummy value from array
        dummy_data_value = dummy_data[dummy_id]

        # Calculate i
        i = dummy_data_value + dummy_id + 2 * day

        # Determine index based on i % 10
        index = 1 if i % 10 < 4 else 3

        # Calculate final ID
        # IMPORTANT: Always use original_salt_values from /prove, not current salt_values
        # accessTokens array is [salt1, salt2, salt3, salt4, salt5]
        salt_values_for_calc = self.original_salt_values if self.original_salt_values else self.salt_values
        request_id = i + salt_values_for_calc[index] * day - salt_values_for_calc[index - 1]

        return request_id


class FloorsheetFetcher:
    """Fetches floorsheet data from NEPSE API and stores in database."""

    def __init__(self):
        self.authenticator = NepseAuthenticator()
        self.base_url = "https://www.nepalstock.com"

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
        client: httpx.AsyncClient,
        stock_id: int,
        ticker: str,
        date: str,
        page: int = 0,
        size: int = 500
    ) -> dict:
        """Fetch floorsheet data from NEPSE API."""
        url = f"{self.base_url}/api/nots/nepse-data/floorsheet?&page={page}&size={size}&stockId={stock_id}&sort=contractId,desc&businessDate={date}"

        # Calculate request ID from salt values
        request_id = self.authenticator.calculate_request_id()
        request_body = {"id": request_id}

        try:
            # Send as raw JSON data (not using json= parameter)
            response = await client.post(
                url,
                headers=self.authenticator.get_auth_headers(),
                content=json.dumps(request_body)
            )

            if response.status_code == 401:
                print("Token expired, refreshing...")
                if await self.authenticator.refresh_access_token(client):
                    request_id = self.authenticator.calculate_request_id()
                    request_body = {"id": request_id}
                    response = await client.post(
                        url,
                        headers=self.authenticator.get_auth_headers(),
                        content=json.dumps(request_body)
                    )

            response.raise_for_status()
            # Check if response is empty
            if not response.text:
                print(f"Empty response for {ticker} on {date} - market may be closed or no data available")
                return {}

            return response.json()
        except Exception as e:
            print(f"Error fetching floorsheet for {ticker} on {date}: {e}")
            print(f"Request ID used: {request_id}")
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

        # Should not happen if Scripts table is properly seeded
        # But handle it anyway
        print(f"Warning: Script {symbol} (ID: {stock_id}) not found in database")
        return None

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
                        print(f"Skipping floorsheet record {item.get('contractId')}: Script not found")
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
                    print(f"Duplicate record for contract ID {item.get('contractId')}: {e}")
                    skipped_count += 1
                except Exception as e:
                    await db.rollback()
                    print(f"Error saving floorsheet record {item.get('contractId')}: {e}")
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
            print(f"Data already exists for {ticker} on {date}. Use --force to refetch.")
            return {"ticker": ticker, "date": date, "status": "skipped", "reason": "already_exists"}

        stock_id = await self.get_stock_id(ticker)
        if not stock_id:
            print(f"Stock ID not found for ticker: {ticker}")
            return {"ticker": ticker, "date": date, "status": "error", "reason": "stock_not_found"}

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            if not self.authenticator.access_token:
                if not await self.authenticator.authenticate(client):
                    return {"ticker": ticker, "date": date, "status": "error", "reason": "auth_failed"}

            page = 0
            total_new = 0
            total_updated = 0
            total_skipped = 0

            while True:
                data = await self.fetch_floorsheet(client, stock_id, ticker, date, page)

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

                print(f"Page {page}: New {new}, Updated {updated}, Skipped {skipped} records for {ticker} on {date}")

                if floorsheet_data.get("last", True):
                    break

                page += 1

            total_saved = total_new + total_updated
            print(f"Total for {ticker} on {date}: New {total_new}, Updated {total_updated}, Skipped {total_skipped}")
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
                print(f"Error processing item {item}: {e}")
                results.append({
                    "ticker": item.get("ticker"),
                    "status": "error",
                    "reason": str(e)
                })

        return results


async def main():
    parser = argparse.ArgumentParser(description="Fetch NEPSE floorsheet data")
    parser.add_argument("--ticker", type=str, help="Stock ticker symbol")
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format")
    parser.add_argument("--dates", type=str, nargs="+", help="Multiple dates in YYYY-MM-DD format")
    parser.add_argument("--force", action="store_true", help="Force refetch even if data exists")
    parser.add_argument("--fetch-list", type=str, help="Path to JSON file with fetch list")

    args = parser.parse_args()

    fetcher = FloorsheetFetcher()

    if args.fetch_list:
        fetch_list_path = Path(args.fetch_list)
        if not fetch_list_path.exists():
            print(f"Fetch list file not found: {args.fetch_list}")
            return

        with open(fetch_list_path, "r") as f:
            fetch_list = json.load(f)

        results = await fetcher.fetch_from_list(fetch_list)
        for result in results:
            print(result)

    elif args.ticker:
        result = await fetcher.fetch_and_save(args.ticker, args.date, args.force)
        print(result)

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
