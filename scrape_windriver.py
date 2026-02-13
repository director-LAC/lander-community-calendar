import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime, timedelta
import sys
from dateutil import parser 

async def scrape_windriver_marathon():
    async with async_playwright() as p:
        # UPDATED: headless=True for Cloud Execution
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌐 Navigating to Wind River...")
        await page.goto("https://windriver.org/events/", timeout=60000)

        all_events = []
        target_date = datetime.now() + timedelta(days=365)
        
        page_num = 1
        max_pages = 60
        reached_target = False

        while page_num <= max_pages and not reached_target:
            print(f"📖 Scraping Page {page_num}...")
            
            try:
                await page.wait_for_selector(".type-tribe_events", timeout=10000)
            except:
                print("   ⚠️ No events found on this page. Retrying or stopping.")
                break

            cards = await page.query_selector_all(".type-tribe_events")
            print(f"   ...Found {len(cards)} events.")
            
            last_event_date = None

            for card in cards:
                title_el = await card.query_selector(".tribe-events-list-event-title a")
                date_el = await card.query_selector(".tribe-event-date-start")
                
                if title_el and date_el:
                    title = await title_el.inner_text()
                    link = await title_el.get_attribute("href")
                    date_str = await date_el.inner_text()
                    
                    all_events.append({
                        "source": "Wind River",
                        "title": title.strip(),
                        "date": date_str.strip(),
                        "link": link
                    })
                    
                    try:
                        clean_d = date_str.split('@')[0].strip()
                        dt = parser.parse(clean_d)
                        if dt.month < datetime.now().month and dt.year == datetime.now().year:
                             dt = dt.replace(year=dt.year + 1)
                        last_event_date = dt
                    except:
                        pass
            
            if last_event_date:
                print(f"   ...Latest event on page: {last_event_date.strftime('%Y-%m-%d')}")
                if last_event_date > target_date:
                    print("✅ Reached target date (1 year out). Stopping.")
                    reached_target = True
                    break

            try:
                next_btn = await page.query_selector("li.tribe-events-nav-next a")
                if next_btn:
                    await next_btn.scroll_into_view_if_needed()
                    await next_btn.click()
                    await page.wait_for_timeout(2000) 
                    page_num += 1
                else:
                    print("   🛑 No 'Next' button found. End of calendar.")
                    break
            except Exception as e:
                print(f"   ⚠️ Error clicking next: {e}")
                break

        await browser.close()
        
        unique_events = {f"{e['title']}{e['date']}": e for e in all_events}.values()
        
        with open("windriver_data.json", "w") as f:
            json.dump(list(unique_events), f, indent=2)
        print(f"🎉 Saved {len(unique_events)} Wind River events.")

if __name__ == "__main__":
    asyncio.run(scrape_windriver_marathon())
    sys.exit(0)
