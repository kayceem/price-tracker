import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests
from playwright.sync_api import sync_playwright

from src.config.settings import config


logger = logging.getLogger(__name__)


class TradeBookFetcher:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.base_dir = Path(__file__).resolve().parents[3] / "scripts"
        self.users_dir = self.base_dir / "users"
        self.cookies = None
        self.host = None
        self.user_id = None

    def load_credentials(self) -> Dict:
        cred_file = self.users_dir / "user_cred.json"
        if not cred_file.exists():
            return {}
        return json.loads(cred_file.read_text())

    def _fetch_token(self, max_retries: int = 3) -> bool:
        credentials = self.load_credentials()
        if not credentials:
            logger.error("TMS credentials file not found at %s", self.users_dir / "user_cred.json")
            return False
        self.host = credentials.get("host", "")
        self.user_id = credentials.get("user_id", "")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(credentials["login_url"])
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                for _ in range(max_retries):
                    page.locator("xpath=/html/body/app-root/app-login/div/div/div[2]/form/div[1]/input").fill(
                        credentials["username"]
                    )
                    time.sleep(0.5)
                    page.locator("xpath=//*[@id='password-field']").fill(credentials["password"])
                    time.sleep(0.5)
                    captcha_text = input("Enter captcha manually: ")
                    if not captcha_text:
                        page.reload()
                        page.wait_for_load_state("networkidle")
                        time.sleep(1)
                        continue
                    page.locator("xpath=//*[@id='captchaEnter']").fill(captcha_text)
                    time.sleep(1)
                    cookie_dict = {}

                    def handle_response(response):
                        if "/tmsapi/dashboard/businessDate" in response.url and response.status == 200:
                            cookie_dict["host_session_id"] = response.request.headers.get("host-session-id", "")
                            cookie_dict["request_owner"] = response.request.headers.get("request-owner", "")

                    page.on("response", handle_response)
                    page.locator("xpath=/html/body/app-root/app-login/div/div/div[2]/form/div[4]/input").click()
                    try:
                        time.sleep(1)
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    for cookie in context.cookies():
                        if cookie["name"] in ["_rid", "_aid", "XSRF-TOKEN"]:
                            cookie_dict[cookie["name"]] = cookie["value"]
                    if cookie_dict:
                        browser.close()
                        self.cookies = cookie_dict
                        return True
                    page.reload()
                    page.wait_for_load_state("networkidle")
                browser.close()
                return False
            except Exception:
                logger.exception("TMS login/token fetch failed")
                browser.close()
                return False

    def generate_headers(self) -> Dict:
        if not self.cookies and not self._fetch_token():
            return {}
        cookies = []
        for key, value in self.cookies.items():
            if key in ["_rid", "_aid", "XSRF-TOKEN"]:
                cookies.append(f"{key}={value}")
        return {
            "host-session-id": self.cookies.get("host_session_id", ""),
            "request-owner": self.cookies.get("request_owner", ""),
            "x-xsrf-token": self.cookies.get("XSRF-TOKEN", ""),
            "host": self.host,
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate, br, zstd",
            "membercode": "1",
            "sec-gpc": "1",
            "connection": "keep-alive",
            "referer": f"https://{self.host}/tms/me/trade-book-history",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "te": "trailers",
            "cookie": "; ".join(cookies),
        }

    def fetch_trade_history(self) -> Optional[Dict]:
        headers = self.generate_headers()
        if not headers:
            logger.error("Failed to generate TMS headers")
            return None
        from_date = "2021-01-01"
        to_date = datetime.now().strftime("%Y-%m-%d")
        endpoint = (
            f"https://{self.host}/tmsapi/orderTradeApi/tradebook-history/client/2156970"
            f"?fromDate={from_date}&toDate={to_date}&pageSize=500&pageNo=1"
        )
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            return response.json()
        logger.error("TMS trade history request failed with status=%s", response.status_code)
        return None

    def save_to_csv(self, data: Dict, save_path: Path):
        if not data:
            return
        records = []
        for item in data:
            records.append(
                {
                    "SYMBOL": item.get("symbol", ""),
                    "EXCHANGE TRADE ID": str(item.get("exchangeTradeId", "")),
                    "BUY/SELL": "Buy" if item.get("buyOrSell", 0) == 1 else "Sell",
                    "TRADE QTY": item.get("tradedQuantity", 0),
                    "PRICE(NPR)": item.get("tradePrice", 0.0),
                    "Value(NPR)": item.get("tradePrice", 0.0) * item.get("tradedQuantity", 0),
                }
            )
        df = pd.DataFrame(records)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_path, index=False)

    def fetch_and_save(self, save_path: Path | None = None) -> Path | None:
        trade_history = self.fetch_trade_history()
        if trade_history is None:
            return None
        if save_path is None:
            save_path = config.get_user_csv_dir(self.user_id) / "history" / "Trade Book Details.csv"
        self.save_to_csv(trade_history, save_path)
        return save_path

    async def fetch_and_save_async(self, save_path: Path | None = None) -> Path | None:
        return await asyncio.to_thread(self.fetch_and_save, save_path)
