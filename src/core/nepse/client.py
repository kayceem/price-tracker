import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx
from wasmtime import Instance, Module, Store

from src.config.settings import config

logger = logging.getLogger(__name__)


class NEPSE:
    """Centralized NEPSE API client with auth and endpoint helpers."""

    def __init__(self):
        self.base_url = "https://www.nepalstock.com"
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.salt_values: list[int] = []
        self.original_salt_values: list[int] = []
        self.market_status_id: Optional[int] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/today-price",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
        }
        self._setup_wasm()

    async def __aenter__(self) -> "NEPSE":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0, verify=False)
        return self.client

    def _setup_wasm(self) -> None:
        wasm_path = config.data_dir / "css.wasm"
        if not wasm_path.exists():
            logger.info("Downloading NEPSE wasm asset to %s", wasm_path)
            with httpx.Client(timeout=30.0, verify=False) as client:
                response = client.get(
                    f"{self.base_url}/assets/prod/css.wasm",
                    headers=self.headers,
                )
                response.raise_for_status()
                wasm_path.write_bytes(response.content)

        self.wasm_store = Store()
        self.wasm_module = Module.from_file(self.wasm_store.engine, str(wasm_path))
        self.wasm_instance = Instance(self.wasm_store, self.wasm_module, [])

    async def get_market_status(self) -> bool:
        try:
            client = await self._ensure_client()
            response = await client.get(
                f"{self.base_url}/api/nots/nepse-data/market-open",
                headers=self.get_auth_headers(),
            )
            response.raise_for_status()
            data = response.json()
            self.market_status_id = data.get("id")
            return self.market_status_id is not None
        except Exception as exc:
            logger.exception("Failed to get NEPSE market status")
            return False

    async def authenticate(self) -> bool:
        try:
            client = await self._ensure_client()
            response = await client.get(
                f"{self.base_url}/api/authenticate/prove",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessToken")
            self.refresh_token = data.get("refreshToken")
            self.salt_values = [
                data.get("salt1", 0),
                data.get("salt2", 0),
                data.get("salt3", 0),
                data.get("salt4", 0),
                data.get("salt5", 0),
            ]
            self.original_salt_values = self.salt_values.copy()
            self.access_token = self._trim_access_token(self.access_token, self.salt_values)
            self.refresh_token = self._trim_refresh_token(self.refresh_token, self.salt_values)
            await self.get_market_status()
            logger.info("Authenticated with NEPSE API")
            return bool(self.access_token)
        except Exception as exc:
            logger.exception("NEPSE authentication failed")
            return False

    async def refresh_access_token(self) -> bool:
        if not self.refresh_token:
            return await self.authenticate()

        try:
            logger.info("Refreshing NEPSE access token")
            client = await self._ensure_client()
            headers = {**self.headers, "Authorization": f"Salter {self.refresh_token}"}
            response = await client.post(
                f"{self.base_url}/api/authenticate/refresh-token",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("accessToken")
            self.refresh_token = data.get("refreshToken")
            self.salt_values = [
                data.get("salt1", 0),
                data.get("salt2", 0),
                data.get("salt3", 0),
                data.get("salt4", 0),
                data.get("salt5", 0),
            ]
            self.access_token = self._trim_access_token(self.access_token, self.salt_values)
            self.refresh_token = self._trim_refresh_token(self.refresh_token, self.salt_values)
            return bool(self.access_token)
        except Exception as exc:
            logger.exception("NEPSE token refresh failed")
            return await self.authenticate()

    async def _ensure_authenticated(self) -> bool:
        if self.access_token:
            return True
        return await self.authenticate()

    async def _post_authorized(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        referer_path: str = "/today-price",
    ) -> httpx.Response:
        client = await self._ensure_client()
        if not await self._ensure_authenticated():
            raise RuntimeError("NEPSE authentication failed")

        headers = {
            **self.get_auth_headers(),
            "Referer": f"{self.base_url}{referer_path}",
        }
        body = json.dumps(payload or {"id": self.calculate_request_id()})
        response = await client.post(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            content=body,
        )

        if response.status_code == 401 and await self.refresh_access_token():
            logger.warning("NEPSE request returned 401 for %s, retrying after token refresh", path)
            headers = {
                **self.get_auth_headers(),
                "Referer": f"{self.base_url}{referer_path}",
            }
            body = json.dumps(payload or {"id": self.calculate_request_id()})
            response = await client.post(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                content=body,
            )

        response.raise_for_status()
        logger.debug("NEPSE request succeeded: %s params=%s", path, params)
        return response

    async def fetch_floorsheet(
        self,
        *,
        stock_id: int,
        business_date: str,
        page: int = 0,
        size: int = 500,
    ) -> dict[str, Any]:
        try:
            response = await self._post_authorized(
                "/api/nots/nepse-data/floorsheet",
                params={
                    "page": page,
                    "size": size,
                    "stockId": stock_id,
                    "sort": "contractId,desc",
                    "businessDate": business_date,
                },
                referer_path="/floor-sheet",
            )
            return response.json() if response.text else {}
        except Exception as exc:
            logger.exception(
                "Error fetching floorsheet for stock_id=%s business_date=%s",
                stock_id,
                business_date,
            )
            return {}

    async def fetch_today_price(
        self,
        *,
        business_date: Optional[str] = None,
        page: int = 0,
        size: int = 500,
    ) -> dict[str, Any]:
        target_date = business_date or datetime.now().strftime("%Y-%m-%d")
        try:
            response = await self._post_authorized(
                "/api/nots/nepse-data/today-price",
                params={
                    "page": page,
                    "size": size,
                    "businessDate": target_date,
                },
                referer_path="/today-price",
            )
            return response.json() if response.text else {}
        except Exception as exc:
            logger.exception("Error fetching NEPSE today-price for business_date=%s", target_date)
            return {}

    def _trim_access_token(self, token: str, salt_values: list[int]) -> str:
        s1, s2, s3, s4, s5 = salt_values
        cdx = self.wasm_instance.exports(self.wasm_store)["cdx"]
        rdx = self.wasm_instance.exports(self.wasm_store)["rdx"]
        bdx = self.wasm_instance.exports(self.wasm_store)["bdx"]
        ndx = self.wasm_instance.exports(self.wasm_store)["ndx"]
        mdx = self.wasm_instance.exports(self.wasm_store)["mdx"]

        cdx_pos = cdx(self.wasm_store, s1, s2, s3, s4, s5)
        rdx_pos = rdx(self.wasm_store, s1, s2, s4, s3, s5)
        bdx_pos = bdx(self.wasm_store, s1, s2, s4, s3, s5)
        ndx_pos = ndx(self.wasm_store, s1, s2, s4, s3, s5)
        mdx_pos = mdx(self.wasm_store, s1, s2, s4, s3, s5)

        return (
            token[:cdx_pos]
            + token[cdx_pos + 1:rdx_pos]
            + token[rdx_pos + 1:bdx_pos]
            + token[bdx_pos + 1:ndx_pos]
            + token[ndx_pos + 1:mdx_pos]
            + token[mdx_pos + 1:]
        )

    def _trim_refresh_token(self, token: str, salt_values: list[int]) -> str:
        s1, s2, s3, s4, s5 = salt_values
        cdx = self.wasm_instance.exports(self.wasm_store)["cdx"]
        rdx = self.wasm_instance.exports(self.wasm_store)["rdx"]
        bdx = self.wasm_instance.exports(self.wasm_store)["bdx"]
        ndx = self.wasm_instance.exports(self.wasm_store)["ndx"]
        mdx = self.wasm_instance.exports(self.wasm_store)["mdx"]

        cdx_pos = cdx(self.wasm_store, s2, s1, s3, s5, s4)
        rdx_pos = rdx(self.wasm_store, s2, s1, s3, s4, s5)
        bdx_pos = bdx(self.wasm_store, s2, s1, s4, s3, s5)
        ndx_pos = ndx(self.wasm_store, s2, s1, s4, s3, s5)
        mdx_pos = mdx(self.wasm_store, s2, s1, s4, s3, s5)

        return (
            token[:cdx_pos]
            + token[cdx_pos + 1:rdx_pos]
            + token[rdx_pos + 1:bdx_pos]
            + token[bdx_pos + 1:ndx_pos]
            + token[ndx_pos + 1:mdx_pos]
            + token[mdx_pos + 1:]
        )

    def get_auth_headers(self) -> dict[str, str]:
        return {**self.headers, "Authorization": f"Salter {self.access_token}"}

    def calculate_request_id(self) -> int:
        dummy_data = [
            147, 117, 239, 143, 157, 312, 161, 612, 512, 804, 411, 527, 170, 511, 421, 667, 764, 621, 301, 106,
            133, 793, 411, 511, 312, 423, 344, 346, 653, 758, 342, 222, 236, 811, 711, 611, 122, 447, 128, 199,
            183, 135, 489, 703, 800, 745, 152, 863, 134, 211, 142, 564, 375, 793, 212, 153, 138, 153, 648, 611,
            151, 649, 318, 143, 117, 756, 119, 141, 717, 113, 112, 146, 162, 660, 693, 261, 362, 354, 251, 641,
            157, 178, 631, 192, 734, 445, 192, 883, 187, 122, 591, 731, 852, 384, 565, 596, 451, 772, 624, 691,
        ]

        day = datetime.now().day
        dummy_id = self.market_status_id if self.market_status_id is not None else 1
        if dummy_id >= len(dummy_data):
            dummy_id %= len(dummy_data)

        i = dummy_data[dummy_id] + dummy_id + 2 * day
        index = 1 if i % 10 < 4 else 3
        salt_values = self.original_salt_values or self.salt_values
        return i + salt_values[index] * day - salt_values[index - 1]
