import asyncio
from playwright.async_api import async_playwright
import json
import sys

async def scrape_county10_load_all():
    async with async_playwright() as p:
        # UPDATED: headless=True for Cloud Execution
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌐 Navigating to County 10...")
        await page.goto("https://county10.com/events/#/", timeout=60000)

        # 1. Wait for initial load
        try:
            await page.wait_for_selector(".csEventTile", timeout=15000)
            print("✅ Page loaded. Initializing...")
        except:
            print("⚠️ Initial load timed out. Trying to proceed anyway.")

        # 2. Scroll to bottom to find the button
        print("⏬ Scrolling to find the button...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        # 3. Find and Click "See More Events" (ONCE)
        load_button = await page.query_selector("text=/See\s*More/i") or \
                      await page.query_selector("text=/Load\s*More/i") or \
                      await page.query_selector(".cs-load-more")

        if load_button and await load_button.is_visible():
            print("👆 Found 'See More' button. Clicking...")
            try:
                await load_button.click()
                await asyncio.sleep(5)
            except Exception as e:
                print(f"⚠️ Error clicking button: {e}")
        else:
            print("⚠️ Button not found or already expanded.")

        # 4. THE BIG SCROLL (Render everything)
        print("🏃 Starting Marathon Scroll to render all items...")
        
        previous_height = 0
        same_height_count = 0
        
        while True:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5) # Wait for cards to "pop in"
            
            current_height = await page.evaluate("document.body.scrollHeight")
            
            if current_height == previous_height:
                same_height_count += 1
                if same_height_count >= 3:
                    print("✅ Reached absolute bottom.")
                    break
            else:
                same_height_count = 0
                print(f"   ...Page grew to {current_height}px")
            
            previous_height = current_height

        # 5. Extract Data
        print("👀 Extracting data from all loaded cards...")
        cards = await page.query_selector_all(".csEventTile")
        print(f"📊 Found {len(cards)} event cards.")

        events = []
        for card in cards:
            iso_date = await card.get_attribute("data-date")
            title_el = await card.query_selector(".csOneLine")
            title = await title_el.inner_text() if title_el else "Unknown Title"
            
            link = ""
            parent = await card.query_selector("xpath=ancestor::a")
            if parent: link = await parent.get_attribute("href")
            
            if not link:
                anchor = await card.query_selector("a")
                if anchor: link = await anchor.get_attribute("href")
            
            if link and link.startswith("#"): 
                link = "https://county10.com/events/" + link

            if iso_date:
                events.append({
                    "source": "County 10",
                    "title": title.strip(),
                    "date": iso_date,
                    "link": link
                })

        await browser.close()
        
        unique_events = {e['link']: e for e in events}.values()

        with open("county10_data.json", "w") as f:
            json.dump(list(unique_events), f, indent=2)
        print(f"🎉 Saved {len(unique_events)} County 10 events.")

if __name__ == "__main__":
    asyncio.run(scrape_county10_load_all())
    sys.exit(0)
