import json
import time
from pathlib import Path
from typing import Dict, Optional
import requests
from playwright.sync_api import sync_playwright, Page, Browser
from datetime import datetime
from src.config.settings import config


class TradeBookFetcher:
    """
    A class to automate login and fetch trade book data using Playwright.
    """

    def __init__(self, headless: bool = False):
        """
        Initialize the TradeBookFetcher.

        Args:
            headless: Whether to run browser in headless mode
            manual_captcha: If True, prompt user to manually enter captcha instead of OCR
            debug_images: If True, save captcha images for debugging
        """
        self.headless = headless
        self.base_dir = Path(__file__).parent
        self.users_dir = self.base_dir / "users"
        self.cookies = None
        self.host = None


    def load_credentials(self) -> Dict:
        """
        Load user credentials from JSON file.

        Returns:
            Dictionary containing user_id, username, password, and login_url
        """
        cred_file = self.users_dir / "user_cred.json"

        if not cred_file.exists():
            return False

        with open(cred_file, 'r') as f:
            return json.load(f)


    def _fetch_token(self,max_retries: int = 3) -> Dict:
        """
        Fetch authentication token.

        Args:
            max_retries: Maximum number of login attempts

        """
        credentials = self.load_credentials()
        if not credentials:
            print("Credentials not found.")
            return 
        self.host = credentials.get('host', '')
        self.user_id = credentials.get('user_id', '')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()

            try:
                # Navigate to login page
                page.goto(credentials['login_url'])
                page.wait_for_load_state('networkidle')
                time.sleep(1)

                for attempt in range(max_retries):
                    print(f"Login attempt {attempt + 1}/{max_retries}.")

                    # Fill username
                    username_xpath = "/html/body/app-root/app-login/div/div/div[2]/form/div[1]/input"
                    page.locator(f"xpath={username_xpath}").fill(credentials['username'])
                    time.sleep(0.5)

                    # Fill password
                    password_xpath = "//*[@id='password-field']"
                    page.locator(f"xpath={password_xpath}").fill(credentials['password'])
                    time.sleep(0.5)

                    # Solve captcha
                    captcha_text = input("Enter captcha manually: ")

                    if not captcha_text:
                        print(f"Failed to solve captcha on attempt {attempt + 1}")
                        page.reload()
                        page.wait_for_load_state('networkidle')
                        time.sleep(1)
                        continue

                    print(f"Captcha solved: {captcha_text}")

                    # Fill captcha
                    captcha_input_xpath = "//*[@id='captchaEnter']"
                    page.locator(f"xpath={captcha_input_xpath}").fill(captcha_text)
                    time.sleep(1)

                    # Click login button
                    login_button_xpath = "/html/body/app-root/app-login/div/div/div[2]/form/div[4]/input"

                    # Setup response listener to capture headers
                    cookie_dict = {}

                    def handle_response(response):
                        nonlocal cookie_dict
                        # Capture headers from response
                        if '/tmsapi/dashboard/businessDate' in response.url and response.status == 200:
                            cookie_dict['host_session_id'] = response.request.headers.get('host-session-id', '')
                            cookie_dict['request_owner'] = response.request.headers.get('request-owner', '')

                    page.on('response', handle_response)

                    # Click login
                    page.locator(f"xpath={login_button_xpath}").click()

                    # Wait for navigation or error
                    try:
                        time.sleep(1)
                        page.wait_for_load_state('networkidle', timeout=10000)
                    except Exception:
                        pass

                    # Get cookies from browser context
                    cookies = context.cookies()

                    for cookie in cookies:
                        if cookie['name'] in ['_rid', '_aid', 'XSRF-TOKEN']:
                            cookie_dict[cookie['name']] = cookie['value']

                    # Check if login was successful by verifying we have cookies
                    if cookie_dict:
                        print(f"Login successful for user.")
                        browser.close()
                        self.cookies = cookie_dict
                        return True
                    else:
                        print(f"Login failed on attempt {attempt + 1}")
                        # Refresh page for next attempt
                        page.reload()
                        page.wait_for_load_state('networkidle')

                browser.close()
                return False
                
            except Exception as e:
                print(f"Error during login: {str(e)}")
                browser.close()
                return False

    def generate_headers(self) -> Dict:
        if not self.cookies and not self._fetch_token():
            print("Failed to fetch token.")
            return {}

        cookies = []
        for key, value in self.cookies.items():
            if key not in ['_rid', '_aid', 'XSRF-TOKEN']:
                continue
            cookies.append(f"{key}={value}")

        headers = {
            'host-session-id': self.cookies.get('host_session_id', ''),
            'request-owner': self.cookies.get('request_owner', ''),
            'x-xsrf-token': self.cookies.get('XSRF-TOKEN', ''),
            'host': self.host,
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'membercode': '1',
            'sec-gpc': '1',
            'connection': 'keep-alive',
            'referer': f'https://{self.host}/tms/me/trade-book-history',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'te': 'trailers',
            'cookie': '; '.join(cookies)
        }
        return headers

    def fetch_trade_history(self) -> Optional[Dict]:
        headers = self.generate_headers()
        if not headers:
            print("Failed to generate headers for API request.")
            return None

        from_date = "2021-01-01"
        to_date = datetime.now().strftime("%Y-%m-%d")
        size = 500
        endpoint = f"https://{self.host}/tmsapi/orderTradeApi/tradebook-history/client/2156970?fromDate={from_date}&toDate={to_date}&pageSize={size}&pageNo=1"
        print(endpoint)
        input()
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch trade history: {response.status_code}")
            return None            


def save_to_csv(data: Dict, save_path: Path):
    import pandas as pd
    if not data:
        print("No data to save.")
        return
    records = []
    for item in data:
        record = {
            'SYMBOL': item.get('symbol', ''),
            'EXCHANGE TRADE ID': str(item.get('exchangeTradeId', '')),
            'BUY/SELL': 'Buy' if item.get('buyOrSell', 0) == 1 else 'Sell',
            'TRADE QTY': item.get('tradedQuantity', 0),
            'PRICE(NPR)': item.get('tradePrice', 0.0),
            'Value(NPR)': item.get('tradePrice', 0.0) * item.get('tradedQuantity', 0)
        }
        records.append(record)
    df = pd.DataFrame(records)
    df.to_csv(save_path, index=False)
    print(f"Trade history saved to {save_path}")

def main():
    fetcher = TradeBookFetcher(headless=False)
    trade_history = fetcher.fetch_trade_history()
    save_path = config.get_user_csv_dir(fetcher.user_id) / "history" / "Trade Book Details.csv"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_to_csv(trade_history, save_path)




if __name__ == "__main__":
    main()