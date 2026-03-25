import httpx
from playwright.async_api import async_playwright
from urllib.parse import urljoin

import requests

async def fetch_script_details(href:str,script_id:int):
    data = {"script_id": script_id}
    url = urljoin("https://nepalstock.com/",href)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"})
        await page.goto(url)
        await page.locator("app-company-details").wait_for(state="attached")
        await page.locator("app-company-details div").nth(3).wait_for(state="visible")
        await page.get_by_role("cell", name="Instrument Type").wait_for(state="visible", timeout=10000)
        table = page.locator("table.table").nth(0)
        rows = await table.locator("tr").all()
        for row in rows:
            td = await row.locator("td").all_text_contents()
            th = await row.locator("th").all_text_contents()
            if td and th:
                data[th[0].strip().replace("/","-")] = td[0].strip().replace("/","-")
        await browser.close()
        print(data)
        return data
        
async def fetch_all_script_details():
    """
    Fetches all script details from NEPSE API.
    Returns a list of dictionaries containing script details.
    """
    data = []
    url = "https://www.nepalstock.com/today-price"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"})
        await page.goto(url)
        await page.locator("select").select_option("500")
        await page.wait_for_timeout(500)
        await page.locator("button.box__filter--search").click()
        await page.wait_for_timeout(1000)
        await page.wait_for_load_state("networkidle")
        table = page.locator("table.table").nth(0)
        rows = await table.locator("tr").all()
        for row in rows:
            td = await row.locator("td").all_text_contents()
            if td and len(td) == 15:
                ltp = td[9].strip().replace(",","")
                if "(" in ltp:
                    ltp = ltp.split("(")[0]
                data.append({
                    "ticker": td[1].strip(),
                    "close": td[2].strip().replace(",",""),
                    "open_price": td[3].strip().replace(",",""),
                    "total_traded_quantity": td[6].strip().replace(",",""),
                    "total_trades": td[8].strip().replace(",",""),
                    "last_traded_price": ltp,
                    "previous_day_close_price": td[10].strip().replace(",",""),
                    "high_price_low_price": f"{td[4].strip().replace(',','')} - {td[5].strip().replace(',','')}",
                    "week_52_high_low": f"{td[12].strip().replace(',','')} - {td[13].strip().replace(',','')}",
                    "market_capitalization": td[14].strip().replace(",","")
                    })
        await browser.close()
        return data