import time, os
from playwright.async_api import async_playwright
from src.config.settings import config


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
        self.download_dir = os.path.join(config.get_user_csv_dir(self.username))
        self.urls = {
            "login": "https://meroshare.cdsc.com.np/#/login",
            "portfolio": "https://meroshare.cdsc.com.np/#/portfolio",
            "purchase_source": "https://meroshare.cdsc.com.np/#/purchase",
            "transaction_history": "https://meroshare.cdsc.com.np/#/transaction",
        }
        

    async def __start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
        self.context = await self.browser.new_context(viewport={"width": 1920, "height": 1800})
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

    async def calculate_holding_days(self):
        # click holding tab
        # <li _ngcontent-c7="" class="nav-item">
        #     <a _ngcontent-c7="" class="nav-link">
        #       <i _ngcontent-c7="" class="ca /myHoldings"></i>
        #       <span _ngcontent-c7="">My Holdings</span>
        #     </a>
        #   </li>
        pass

    async def calculate_wacc(self):
        await self.page.reload()
        await self.page.wait_for_timeout(2000)

        # Get all available scripts from datalist
        script_options = await self.page.locator("datalist#browsers option").all()
        scripts = []
        for option in script_options:
            value = await option.get_attribute("value")
            if value:
                scripts.append(value)

        print(f"Found {len(scripts)} scripts to process")

        # Process each script
        for idx, script in enumerate(scripts, 1):
            try:
                print(f"Processing {idx}/{len(scripts)}: {script}")

                # Enter script name in input field
                await self.page.fill("input#script", script)
                await self.page.wait_for_timeout(500)

                # Click search button
                await self.page.click("button.btn.btn-primary[type='submit']")
                await self.page.wait_for_timeout(1500)

                # Check if any results found
                checkboxes = await self.page.locator("input[type='checkbox']").all()
                if not checkboxes:
                    print(f"  No purchase records found for {script}")
                    await self.page.click("button.btn.btn-default[type='reset']")
                    await self.page.wait_for_timeout(500)
                    continue

                # Click all checkboxes
                for checkbox in checkboxes:
                    if await checkbox.is_visible():
                        await checkbox.check()

                await self.page.wait_for_timeout(500)

                # Click proceed button
                await self.page.click("button.btn.btn-primary[type='button']:has-text('Proceed')")
                await self.page.wait_for_timeout(1500)

                # Click disclaimer checkbox
                await self.page.click("input.disclaimer[type='checkbox']")
                await self.page.wait_for_timeout(500)

                # Click update button
                await self.page.click("button.btn.btn-primary[type='submit']:has-text('Update')")
                await self.page.wait_for_timeout(2000)

                # Check for success toast message
                toast_container = await self.page.query_selector("div#toast-container")
                if toast_container:
                    toast_text = await toast_container.inner_text()
                    if "updated" in toast_text.lower():
                        print(f"  Successfully updated WACC for {script}")
                    else:
                        print(f"  Update response for {script}: {toast_text}")

                # Wait for toast to disappear
                await self.page.wait_for_timeout(1000)

                # Click reset button to prepare for next script
                await self.page.click("button.btn.btn-default[type='reset']")
                await self.page.wait_for_timeout(500)

            except Exception as e:
                print(f"  Error processing {script}: {str(e)}")
                # Try to reset and continue with next script
                try:
                    await self.page.click("button.btn.btn-default[type='reset']")
                    await self.page.wait_for_timeout(500)
                except:
                    pass
                continue

        print(f"Completed WACC calculation for all scripts")

    async def fetch_wacc_csv(self):
        while True:
            await self.page.goto(self.urls["purchase_source"])
            await self.page.wait_for_timeout(2000)
            await self.page.click("a.nav-link:has-text('My WACC')")
            await self.page.wait_for_timeout(2000)
            try:
                async with self.page.expect_download() as download_info:
                    await self.page.click("button >> i.msi-download-csv", timeout=5000)
                download = await download_info.value
                download_path = os.path.join(self.download_dir, download.suggested_filename)
                await download.save_as(download_path)
                await self.page.wait_for_timeout(2000)
                break
            except:
                error_message = await self.page.query_selector("div.fallback-title-message")
                if error_message and "holding" in (await error_message.inner_text()).lower():
                    await self.calculate_holding_days()
                    continue
                if error_message and "wacc" in (await error_message.inner_text()).lower():
                    await self.calculate_wacc()
                    continue
                break

    async def fetch_protfolio_csv(self):
        await self.page.goto(self.urls["portfolio"])
        await self.page.wait_for_timeout(2000)
        async with self.page.expect_download() as download_info:
            await self.page.click("button >> i.msi-download-csv")

        download = await download_info.value
        download_path = os.path.join(self.download_dir, download.suggested_filename)
        await download.save_as(download_path)
        await self.page.wait_for_timeout(2000)
    
    async def fetch_transaction_csv(self):
        await self.page.goto(self.urls["transaction_history"])
        await self.page.wait_for_timeout(2000)
        radio_button = await self.page.click("input#radio-range")
        await self.page.wait_for_timeout(2000)
        async with self.page.expect_download() as download_info:
            await self.page.click("button >> i.msi-download-csv")
        download = await download_info.value
        download_path = os.path.join(self.download_dir, "history", download.suggested_filename)
        await download.save_as(download_path)
        await self.page.wait_for_timeout(2000)

    async def fetch_csv(self):
        await self.fetch_protfolio_csv()
        await self.fetch_wacc_csv()
        await self.fetch_transaction_csv()


    async def start(self):
        await self.__start()
        await self.login()
        await self.fetch_csv()
        await self.__close()