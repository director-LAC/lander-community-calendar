import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime, timedelta
import sys

async def scrape_lvhs_api():
    async with async_playwright() as p:
        print("🚀 Starting LVHS Direct Feed Scraper...")
        
        # UPDATED: headless=True is required for the cloud environment
        browser = await p.chromium.launch(headless=True)
        
        # We create a context to look like a real user (valid User-Agent)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        base_url = "https://thrillshare-cmsv2.services.thrillshare.com/api/v4/o/24886/cms/events"
        
        all_events = []
        page_num = 1
        target_date = datetime.now() + timedelta(days=365)
        keep_scraping = True

        while keep_scraping:
            print(f"📡 Fetching Page {page_num} from School Server...")
            
            try:
                # Use the browser context to fetch the JSON data securely
                response = await context.request.get(base_url, params={
                    "slug": "events-lvhs-fremontcsd1wy",
                    "page_no": str(page_num)
                })
                
                if not response.ok:
                    print(f"   ⚠️ Server returned error: {response.status}")
                    break
                    
                data = await response.json()
                
                events_list = data.get("events", [])
                if not events_list:
                    print("   ✅ No more events found. Stopping.")
                    break
                
                print(f"   ...Received {len(events_list)} events.")
                
                for event in events_list:
                    title = event.get("title", "No Title")
                    start_raw = event.get("start_at", "")
                    
                    if start_raw:
                        final_date = start_raw
                    else:
                        continue 

                    all_events.append({
                        "source": "LVHS",
                        "title": title.strip(),
                        "date": final_date,
                        "link": "https://www.landerschools.org/o/lvhs/events"
                    })
                    
                    try:
                        dt = datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
                        dt_naive = dt.replace(tzinfo=None)
                        if dt_naive > target_date:
                            print("   🕒 Reached 1 year target.")
                            keep_scraping = False
                    except:
                        pass

                page_num += 1
                await asyncio.sleep(0.5) 
                
            except Exception as e:
                print(f"   ❌ Error fetching data: {e}")
                break

        await browser.close()
        
        unique_events = {f"{e['title']}{e['date']}": e for e in all_events}.values()
        
        with open("lvhs_data.json", "w") as f:
            json.dump(list(unique_events), f, indent=2)
        print(f"🎉 Saved {len(unique_events)} LVHS events.")

if __name__ == "__main__":
    asyncio.run(scrape_lvhs_api())
    sys.exit(0)
