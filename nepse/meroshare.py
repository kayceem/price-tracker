import time, os
from playwright.async_api import async_playwright
from utils.utils import get_dir_path

class Meroshare:
    def __init__(self, dp, username, password, headless=False):
        self.dp = str(dp)
        self.username = username
        self.password = password
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.download_dir = os.path.join(get_dir_path(), "csv")
        self.urls = {
            "login": "https://meroshare.cdsc.com.np/#/login",
            "portfolio": "https://meroshare.cdsc.com.np/#/portfolio",
            "purchase_source": "https://meroshare.cdsc.com.np/#/purchase",
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

        await self.page.click("span.select2-selection--single")
        await self.page.fill("input.select2-search__field", self.dp)
        await self.page.keyboard.press("Enter")
        
        await self.page.fill("input[name='username']", self.username)
        await self.page.fill("input[name='password']", self.password)
        await self.page.click("button[type='submit']")

        await self.page.wait_for_timeout(2000)

    def logout(self):
        # Implement logout logic here
        pass

    async def fetch_wacc_csv(self):
        await self.page.goto(self.urls["purchase_source"])
        await self.page.wait_for_timeout(2000)
        await self.page.click("a.nav-link:has-text('My WACC')")
        await self.page.wait_for_timeout(2000)
        async with self.page.expect_download() as download_info:
            await self.page.click("button >> i.msi-download-csv")

        download = await download_info.value
        download_path = os.path.join(self.download_dir, self.username ,download.suggested_filename)
        await download.save_as(download_path)
        await self.page.wait_for_timeout(2000)

    async def fetch_protfolio_csv(self):
        await self.page.goto(self.urls["portfolio"])
        await self.page.wait_for_timeout(2000)
        async with self.page.expect_download() as download_info:
            await self.page.click("button >> i.msi-download-csv")

        download = await download_info.value
        download_path = os.path.join(self.download_dir, self.username ,download.suggested_filename)
        await download.save_as(download_path)
        await self.page.wait_for_timeout(2000)

    async def fetch_csv(self):
        await self.fetch_protfolio_csv()
        await self.fetch_wacc_csv()


    async def start(self):
        await self.__start()
        await self.login()
        await self.fetch_csv()
        await self.__close()