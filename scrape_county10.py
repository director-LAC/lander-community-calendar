import asyncio
from playwright.async_api import async_playwright
import json
import sys

async def scrape_county10_stealth():
    async with async_playwright() as p:
        # 1. Launch with "Stealth" flags to hide automation
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # 2. Mimic a real laptop screen and user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/Denver"
        )
        page = await context.new_page()

        print("🌐 Navigating to County 10...")
        try:
            await page.goto("https://county10.com/events/#/", timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"⚠️ Navigation timeout (might be slow loading): {e}")

        # 3. Soft Wait: Don't crash if it fails, just try to find the container first
        print("⏳ Waiting for calendar widget...")
        try:
            # First look for the main CitySpark container
            await page.wait_for_selector("#CitySpark", state="attached", timeout=20000)
            print("   ...Widget container found.")
            
            # Now wait for actual events
            await page.wait_for_selector(".csEventTile", state="visible", timeout=20000)
            print("✅ Events loaded!")
        except:
            print("⚠️ Events did not appear (Cloud Blockage?). Saving empty list for today.")
            # DO NOT EXIT WITH ERROR. Just save empty/old data and let other scripts run.
            await browser.close()
            # We exit normally so the workflow continues
            sys.exit(0)

        # 4. The Loop
        print("🏃 Starting Scroll Loop...")
        previous_count = 0
        no_change = 0
        
        for i in range(15): # Cap at 15 loops to prevent infinite runs
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            
            # Try clicking "Load More"
            try:
                btns = await page.query_selector_all("text=/See\s*More/i")
                for btn in btns:
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1)
            except: 
                pass

            cards = await page.query_selector_all(".csEventTile")
            count = len(cards)
            print(f"   Loop {i+1}: {count} events found.")
            
            if count == previous_count:
                no_change += 1
                if no_change >= 3:
                    break
            else:
                no_change = 0
                
            previous_count = count

        # 5. Extract
        print("👀 Extracting...")
        cards = await page.query_selector_all(".csEventTile")
        events = []
        
        for card in cards:
            iso_date_raw = await card.get_attribute("data-date")
            title_el = await card.query_selector(".csOneLine")
            title = await title_el.inner_text() if title_el else "Unknown"
            
            link = ""
            anchor = await card.query_selector("a") 
            if anchor: link = await anchor.get_attribute("href")
            
            if link and link.startswith("#"): 
                link = "https://county10.com/events/" + link

            if iso_date_raw:
                events.append({
                    "source": "County 10",
                    "title": title.strip(),
                    "date": iso_date_raw.split("T")[0],
                    "link": link
                })

        await browser.close()
        
        unique_events = {e['link']: e for e in events}.values()
        
        # Only overwrite file if we actually found data
        if len(unique_events) > 0:
            with open("county10_data.json", "w") as f:
                json.dump(list(unique_events), f, indent=2)
            print(f"🎉 Saved {len(unique_events)} events.")
        else:
            print("⚠️ No events found, leaving existing data file untouched.")

if __name__ == "__main__":
    asyncio.run(scrape_county10_stealth())
    sys.exit(0) # Always exit success so we don't block other scrapers
