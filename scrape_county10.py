import asyncio
from playwright.async_api import async_playwright
import json
import sys

async def scrape_county10_load_all():
    async with async_playwright() as p:
        # Launch browser (Headless=True for cloud, False for watching locally)
        browser = await p.chromium.launch(headless=True)
        
        # KEY FIX: Use a real User-Agent to bypass "bot" detection
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("🌐 Navigating to County 10...")
        await page.goto("https://county10.com/events/#/", timeout=90000)

        # 1. Force Wait for the specific event cards to load
        try:
            print("⏳ Waiting for event cards to appear...")
            # Wait up to 30 seconds for the '.csEventTile' class to show up
            await page.wait_for_selector(".csEventTile", state="attached", timeout=30000)
            print("✅ Event cards detected!")
        except Exception as e:
            print(f"❌ Error: Page loaded, but event cards didn't appear. {e}")
            # Take a screenshot to help debug if it fails again
            await page.screenshot(path="county10_failed.png")
            await browser.close()
            sys.exit(1)

        # 2. Scroll to bottom to trigger lazy loading
        print("⏬ Scrolling to load more events...")
        # Scroll a few times to ensure the list populates
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

        # 3. Find and Click "See More" / "Load More" button if it exists
        # (County 10 often uses infinite scroll, but sometimes has a button)
        try:
            load_button = await page.query_selector("text=/See\s*More/i") or \
                          await page.query_selector(".cs-load-more")
            
            if load_button and await load_button.is_visible():
                print("👆 Found 'See More' button. Clicking...")
                await load_button.click()
                await asyncio.sleep(3)
        except:
            pass # It's fine if there's no button

        # 4. Extract Data
        print("👀 Extracting data...")
        cards = await page.query_selector_all(".csEventTile")
        print(f"📊 Found {len(cards)} event cards.")

        events = []
        for card in cards:
            # Get data-date attribute (e.g. "2026-02-14T00:00:00Z")
            iso_date_raw = await card.get_attribute("data-date")
            
            # Get Title
            title_el = await card.query_selector(".csOneLine")
            title = await title_el.inner_text() if title_el else "Unknown Title"
            
            # Get Link
            # County 10 links are often dynamic, we'll try to find the anchor tag
            link = ""
            # Check for direct anchor child or parent
            anchor = await card.query_selector("a") 
            if not anchor:
                # sometimes the wrapper itself is the click target, but we need a URL.
                # often County 10 links look like #/details/...
                href = await card.get_attribute("href")
                if href: link = href
            else:
                link = await anchor.get_attribute("href")

            # Clean up link
            if link and link.startswith("#"): 
                link = "https://county10.com/events/" + link

            # Only add if we have a date
            if iso_date_raw:
                # Clean date to YYYY-MM-DD
                clean_date = iso_date_raw.split("T")[0]
                
                events.append({
                    "source": "County 10",
                    "title": title.strip(),
                    "date": clean_date,
                    "link": link
                })

        await browser.close()
        
        # Deduplicate based on link or title+date
        unique_events = {}
        for e in events:
            key = e['link'] if e['link'] else f"{e['title']}{e['date']}"
            unique_events[key] = e

        with open("county10_data.json", "w") as f:
            json.dump(list(unique_events.values()), f, indent=2)
            
        print(f"🎉 Saved {len(unique_events)} County 10 events.")

if __name__ == "__main__":
    asyncio.run(scrape_county10_load_all())
    sys.exit(0)
