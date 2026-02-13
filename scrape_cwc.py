import asyncio
from playwright.async_api import async_playwright
import json
import sys

async def scrape_cwc_visual():
    async with async_playwright() as p:
        # UPDATED: headless=True for Cloud Execution
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("🌐 Navigating to CWC Calendar...")
        await page.goto("https://www.cwc.edu/calendar/", timeout=60000)
        
        try:
            await page.wait_for_selector(".tribe-events-calendar-list", timeout=15000)
        except:
            print("⚠️ Calendar list not found.")

        all_events = []
        max_clicks = 12 
        clicks = 0

        while clicks < max_clicks:
            print(f"📖 Scraping Month {clicks + 1}...")
            
            rows = await page.query_selector_all(".tribe-events-calendar-list__event-row")
            print(f"   ...Found {len(rows)} events on this page.")
            
            for row in rows:
                title_el = await row.query_selector(".tribe-events-calendar-list__event-title-link")
                time_el = await row.query_selector("time")
                
                if title_el:
                    title = await title_el.inner_text()
                    link = await title_el.get_attribute("href")
                    
                    date_str = await time_el.get_attribute("datetime") if time_el else ""
                    if not date_str and time_el:
                        date_str = await time_el.inner_text()
                    
                    all_events.append({
                        "source": "CWC",
                        "title": title.strip(),
                        "date": date_str,
                        "link": link
                    })

            next_btn = await page.query_selector("li.tribe-events-c-top-bar__nav-list-item--next a") or \
                       await page.query_selector("a.tribe-events-c-top-bar__nav-link--next") or \
                       await page.query_selector("a[rel='next']")
            
            if next_btn:
                try:
                    print("   ➡️ Loading next month...")
                    await next_btn.click()
                    await asyncio.sleep(4)
                    clicks += 1
                except:
                    print("   ⚠️ Failed to click next.")
                    break
            else:
                print("   🛑 No 'Next' button found (End of calendar).")
                break

        await browser.close()
        
        unique_events = {e['link']: e for e in all_events}.values()

        with open("cwc_data.json", "w") as f:
            json.dump(list(unique_events), f, indent=2)
        print(f"🎉 Saved {len(unique_events)} CWC events.")

if __name__ == "__main__":
    asyncio.run(scrape_cwc_visual())
    sys.exit(0)
