import asyncio
from playwright.async_api import async_playwright
import sys

# URL of a sample event from county10_data.json
SAMPLE_URL = "https://county10.com/events/#/details/wild-west-pickleball/17547052/2026-02-15T08"

async def fetch_event_metadata():
    async with async_playwright() as p:
        print(f"🚀 Launching browser to inspect: {SAMPLE_URL}")
        # 1. Launch with "Stealth" flags to hide automation (matching scrape_county10.py)
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

        try:
            # Shorter timeout, wait for domcontentloaded instead of networkidle
            await page.goto(SAMPLE_URL, timeout=30000, wait_until="domcontentloaded")
            print("✅ Page loaded (DOM). Waiting 5s for JS hydration...")
            await asyncio.sleep(5)
            
            # 1. Get full HTML
            content = await page.content()
            with open("county10_sample.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("📄 Saved HTML to county10_sample.html")

            # 2. Extract JSON-LD specifically
            json_ld = await page.evaluate("""() => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                return Array.from(scripts).map(s => s.innerText);
            }""")
            
            if json_ld:
                print(f"🔍 Found {len(json_ld)} JSON-LD blocks.")
                with open("county10_jsonld.txt", "w", encoding="utf-8") as f:
                    for block in json_ld:
                        f.write(block + "\n---\n")
            else:
                print("⚠️ No JSON-LD found.")

            # 3. Extract Meta Tags
            meta_tags = await page.evaluate("""() => {
                const metas = document.querySelectorAll('meta');
                return Array.from(metas).map(m => `${m.getAttribute('name') || m.getAttribute('property')}: ${m.getAttribute('content')}`);
            }""")
            
            with open("county10_meta.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(meta_tags))
            print("🏷️ Saved meta tags to county10_meta.txt")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_event_metadata())
