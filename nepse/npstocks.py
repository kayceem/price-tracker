from pathlib import Path
import pandas as pd
import time, os
from playwright.async_api import async_playwright
from utils.utils import get_dir_path

class Npstocks:
    def __init__(self, username, password, headless=True):
        self.username = username
        self.password = password
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.download_dir = os.path.join(get_dir_path(), "csv")
        self.urls = {
            "login": "https://app.npstocks.com/auth/login",
            "portfolio": "https://app.npstocks.com/portfolio/portfolios",
        }
        

    async def __start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self.page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"})

    async def __close(self):
        await self.browser.close()
        await self.playwright.stop()

    async def login(self):
        await self.page.goto(self.urls["login"])

        await self.page.fill("input[id='username']", self.username)
        await self.page.fill("input[id='password']", self.password)
        await self.page.click("button[type='submit']")

        await self.page.wait_for_timeout(2000)

    def logout(self):
        # Implement logout logic here
        pass

    def parse_trade_book(self, file_path):
        df = pd.read_excel(file_path)
        df.drop_duplicates(inplace=True)
        df = df[['SYMBOL', 'BUY/SELL', 'TRADE QTY', 'PRICE(NPR)']]
        return df.iloc[::-1]

    def parse_transaction_history(self, file_path):
        df = pd.read_csv(file_path)
        df.drop_duplicates(inplace=True)
        df = df[df['History Description'].str.contains('CA-', na=False)]
        df = df[['Scrip', 'Transaction Date', 'Credit Quantity', 'History Description']]
        return df.iloc[::-1]

    async def add_stocks_transaction_history(self, df):
        await self.page.goto(self.urls["portfolio"])
        await self.page.wait_for_timeout(2000)
        await self.page.click("text=Test")
        await self.page.wait_for_timeout(1000)

        for _, row in df.iterrows():
            scrip = row['Scrip']
            qty = row['Credit Quantity']
            description = row['History Description']
            price = 100
            is_bonus = 'Bonus' in description

            await self.page.click("button:has-text('Add Stocks')")
            await self.page.wait_for_timeout(1000)
            await self.page.click("button:has-text('SECONDARY')")
            await self.page.wait_for_timeout(300)
            if is_bonus:
                await self.page.locator(f'div.cursor-pointer:has-text("BONUSSHARE")').click()
            else:
                await self.page.locator(f'div.cursor-pointer:has-text("RIGHTSHARE")').click()

            await self.page.wait_for_timeout(500)
            await self.page.click("button:has-text('Select Company')")
            await self.page.wait_for_timeout(500)
            await self.page.locator('input[placeholder="Search"]').fill(scrip)
            await self.page.wait_for_timeout(500)
            await self.page.locator(f'div.cursor-pointer:has-text("({scrip})")').click()
            await self.page.wait_for_timeout(500)
            await self.page.locator('input[name="qty"]').fill(str(qty))
            await self.page.wait_for_timeout(500)
            if not is_bonus:
                await self.page.locator('input[name="price"]').fill(str(price))
                await self.page.wait_for_timeout(500)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_timeout(500)

    async def add_stocks_trade_book(self, df):
        await self.page.goto(self.urls["portfolio"])
        await self.page.wait_for_timeout(2000)
        await self.page.click("text=Test")
        await self.page.wait_for_timeout(1000)

        for _, row in df.iterrows():
            symbol = row['SYMBOL']
            action = row['BUY/SELL']
            qty = row['TRADE QTY']
            price = row['PRICE(NPR)']

            if action == 'Sell':
                continue
            await self.page.click("button:has-text('Add Stocks')")
            await self.page.wait_for_timeout(1000)

            await self.page.click("button:has-text('Select Company')")
            await self.page.wait_for_timeout(500)
            await self.page.locator('input[placeholder="Search"]').fill(symbol)
            await self.page.wait_for_timeout(500)
            await self.page.locator(f'div.cursor-pointer:has-text("({symbol})")').click()
            await self.page.wait_for_timeout(500)
            await self.page.locator('input[name="qty"]').fill(str(qty))
            await self.page.wait_for_timeout(500)
            await self.page.locator('input[name="price"]').fill(str(price))
            await self.page.wait_for_timeout(500)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_timeout(500)

    async def sell_stocks_trade_book(self, df):
        await self.page.goto(self.urls["portfolio"])
        await self.page.wait_for_timeout(2000)
        await self.page.click("text=Test")
        await self.page.wait_for_timeout(1000)

        for _, row in df.iterrows():
            symbol = row['SYMBOL']
            action = row['BUY/SELL']
            qty = row['TRADE QTY']
            price = row['PRICE(NPR)']

            if action == 'Buy':
                continue
            await self.page.click(f"p:has-text('{symbol}')")
            await self.page.wait_for_timeout(1000)

            await self.page.click("button:has-text('Sell')")
            await self.page.wait_for_timeout(500)
            await self.page.locator('input[name="price"]').fill(str(price))
            await self.page.wait_for_timeout(500)
            await self.page.locator('div:has-text("Allocated Shares") input[type="number"]').fill(qty)
            await self.page.wait_for_timeout(500)
            await self.page.click("button[type='submit']")
            await self.page.wait_for_timeout(500)



    async def start(self):
        await self.__start()
        await self.login()
        df = self.parse_trade_book(Path(get_dir_path(),"csv/Trade Book Details.xlsx"))
        # await self.add_stocks_trade_book(df)
        await self.sell_stocks_trade_book(df)
        # df = self.parse_transaction_history(Path(get_dir_path(),"csv/Transaction History.csv"))
        # await self.add_stocks_transaction_history(df)
        await self.__close()