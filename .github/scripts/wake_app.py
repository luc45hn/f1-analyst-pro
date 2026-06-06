import asyncio
from playwright.async_api import async_playwright

async def wake():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://f1-analyst.streamlit.app', timeout=120000)
        await page.wait_for_timeout(5000)
        btn = page.get_by_role('button', name='Yes, get this app back up!')
        if await btn.count() > 0:
            print('App was sleeping - waking up')
            await btn.click()
            await page.wait_for_timeout(60000)
        else:
            print('App is already awake')
        await browser.close()

asyncio.run(wake())
