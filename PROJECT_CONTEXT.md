# Project Context & Architecture Handoff

## Project: Lander Mega Calendar
**Goal:** A centralized community calendar aggregation for Lander, WY, running via GitHub Actions.

## Current Architecture
* **Infrastructure:** GitHub Pages (hosting) + GitHub Actions (automation).
* **Core Script:** `build_calendar.py` (Python) aggregates JSON data, handles logic, and generates a static `index.html`.
* **Scrapers:** Independent Python scripts (`scrape_county10.py`, etc.) using Playwright to fetch events and save them as JSON files.
* **Frontend:** FullCalendar.js embedded in a static HTML file.
* **Embedding:** The calendar is embedded via `iframe` on a Squarespace site.

## Key Features & Logic
1.  **Stealth Scraping:** County 10 scraper uses specific headers/viewports to bypass bot detection.
2.  **Auto-Grow Iframe:** The calendar communicates with the parent Squarespace page via `postMessage` to resize the iframe dynamically (preventing scrollbars).
3.  **Mobile View:** Automatically switches to "List View" on mobile (<768px) and "Month View" on desktop.
4.  **Universal Search:** Searching auto-switches the view to "Year List" to ensure all events (even off-screen ones) are searchable.
5.  **Smart Filtering:** Source "Pills" (CSS classes) toggle visibility without reloading.

## Current Status
* **Status:** Stable.
* **Known Issues:** None currently.
* **Next Phase:** Refinement of tagging logic (making `get_category` smarter) and deduplication of events across sources.