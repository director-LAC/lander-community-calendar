import asyncio
from playwright.async_api import async_playwright
import json
import sys

async def scrape_county10_deep():
    async with async_playwright() as p:
        # 1. Launch with a Real User-Agent to bypass bot detection
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080} # BIG SCREEN required for infinite scroll triggers
        )
        page = await context.new_page()

        print("🌐 Navigating to County 10...")
        await page.goto("https://county10.com/events/#/", timeout=90000)

        # 2. Wait for the app to actually load
        try:
            await page.wait_for_selector(".csEventTile", state="visible", timeout=30000)
            print("✅ Initial events loaded.")
        except:
            print("❌ Page loaded but no events found. Taking screenshot.")
            await page.screenshot(path="county10_error.png")
            await browser.close()
            sys.exit(1)

        # 3. THE MARATHON LOOP (Scroll + Click)
        print("🏃 Starting Deep Scroll Sequence...")
        
        previous_count = 0
        no_change_counter = 0
        max_no_change = 3  # Stop if no new events after 3 tries
        
        while no_change_counter < max_no_change:
            # A. Scroll to the absolute bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2) # Give it time to render

            # B. Look for and Click "See More" / "Load More" buttons
            # County 10 often hides events behind a "See More" button at the bottom
            try:
                # Try generic text matches and specific classes
                load_buttons = await page.query_selector_all("text=/See\s*More/i")
                for btn in load_buttons:
                    if await btn.is_visible():
                        print("   👆 Clicking 'See More' button...")
                        await btn.click()
                        await asyncio.sleep(2) # Wait for click effect
            except:
                pass

            # C. Count how many events we have now
            current_cards = await page.query_selector_all(".csEventTile")
            current_count = len(current_cards)

            if current_count > previous_count:
                print(f"   ...Expanded list to {current_count} events.")
                previous_count = current_count
                no_change_counter = 0 # Reset counter because we found new stuff
            else:
                no_change_counter += 1
                print(f"   ...No new events found (Attempt {no_change_counter}/{max_no_change})")
                
                # Try a small scroll up and down to trigger intersection observers
                await page.evaluate("window.scrollBy(0, -500)")
                await asyncio.sleep(0.5)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

        # 4. Extract Data
        print("👀 Extraction Phase...")
        cards = await page.query_selector_all(".csEventTile")
        print(f"📊 Processing {len(cards)} total cards.")

        events = []
        for card in cards:
            iso_date_raw = await card.get_attribute("data-date")
            title_el = await card.query_selector(".csOneLine")
            title = await title_el.inner_text() if title_el else "Unknown Title"
            
            # Smart Link Extraction
            link = ""
            anchor = await card.query_selector("a") 
            if not anchor:
                href = await card.get_attribute("href")
                if href: link = href
            else:
                link = await anchor.get_attribute("href")

            if link and link.startswith("#"): 
                link = "https://county10.com/events/" + link

            if iso_date_raw:
                clean_date = iso_date_raw.split("T")[0]
                events.append({
                    "source": "County 10",
                    "title": title.strip(),
                    "date": clean_date,
                    "link": link
                })

        await browser.close()
        
        # Deduplicate
        unique_events = {}
        for e in events:
            key = e['link'] if e['link'] else f"{e['title']}{e['date']}"
            unique_events[key] = e

        with open("county10_data.json", "w") as f:
            json.dump(list(unique_events.values()), f, indent=2)
            
        print(f"🎉 Successfully scraped {len(unique_events)} future events from County 10.")

if __name__ == "__main__":
    asyncio.run(scrape_county10_deep())
    sys.exit(0)
