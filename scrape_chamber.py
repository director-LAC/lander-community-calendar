import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime, timedelta
import re
import sys

async def scrape_chamber_scroll():
    async with async_playwright() as p:
        # UPDATED: headless=True for Cloud Execution
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("🌐 Navigating to Lander Chamber (Infinite Scroll Mode)...")
        await page.goto("https://info.landerchamber.org/events", timeout=60000)
        
        try:
            await page.wait_for_selector(".gz-list-card-wrapper", timeout=15000)
        except:
            print("⚠️ Initial load timed out.")

        target_date = datetime.now() + timedelta(days=365)
        current_year = datetime.now().year
        
        print("⏬ Starting Scroll Sequence...")
        
        last_height = await page.evaluate("document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 30
        
        while scroll_attempts < max_scrolls:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            
            cards = await page.query_selector_all(".gz-list-card-wrapper")
            if cards:
                last_card = cards[-1]
                date_el = await last_card.query_selector(".gz-card-date")
                if date_el:
                    date_text = (await date_el.inner_text()).strip()
                    try:
                        clean_d = re.sub(r'^[A-Za-z]+,?\s*', '', date_text).split(' - ')[0]
                        if ',' in clean_d:
                            dt = datetime.strptime(clean_d, "%b %d, %Y")
                        else:
                            dt = datetime.strptime(f"{clean_d}, {current_year}", "%b %d, %Y")
                        
                        print(f"   ...Scrolled to event: {date_text}")
                        if dt > target_date:
                            print("✅ Reached 12-month horizon. Stopping.")
                            break
                    except:
                        pass

            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                print("   ...Page height didn't change. Checking for 'Load More' button just in case...")
                try:
                    load_btn = await page.query_selector("text='Load More'")
                    if load_btn and await load_btn.is_visible():
                        await load_btn.click()
                        await asyncio.sleep(3)
                        new_height = await page.evaluate("document.body.scrollHeight")
                    else:
                        print("   🛑 Reached absolute bottom.")
                        break
                except:
                    break
            
            last_height = new_height
            scroll_attempts += 1

        print("👀 Collecting all loaded events...")
        all_events = []
        final_cards = await page.query_selector_all(".gz-list-card-wrapper")
        
        for card in final_cards:
            title_el = await card.query_selector(".gz-card-title a")
            date_el = await card.query_selector(".gz-card-date")
            
            if title_el:
                title = await title_el.inner_text()
                link = await title_el.get_attribute("href")
                date = await date_el.inner_text() if date_el else "Check Website"
                
                all_events.append({
                    "source": "Lander Chamber",
                    "title": title.strip(),
                    "date": date.strip(),
                    "link": link
                })

        await browser.close()
        
        unique_events = {e['link']: e for e in all_events}.values()
        
        with open("chamber_data.json", "w") as f:
            json.dump(list(unique_events), f, indent=2)
        print(f"🎉 Saved {len(unique_events)} Chamber events.")

if __name__ == "__main__":
    asyncio.run(scrape_chamber_scroll())
    sys.exit(0)
