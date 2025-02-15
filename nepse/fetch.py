from playwright.async_api import async_playwright
from urllib.parse import urljoin

async def fetch_script_details(href:str,script_id:int):
    data = {"script_id": script_id}
    url = urljoin("https://nepalstock.com/",href)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"})
        await page.goto(url)
        await page.wait_for_selector("table.table")
        table = page.locator("table.table").nth(0)
        rows = await table.locator("tr").all()
        for row in rows:
            td = await row.locator("td").all_text_contents()
            th = await row.locator("th").all_text_contents()
            if td and th:
                data[th[0].strip().replace("/","-")] = td[0].strip().replace("/","-")
        await browser.close()
        return data
        
    