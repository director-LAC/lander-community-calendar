import json
import os
from datetime import datetime
import re
from difflib import SequenceMatcher

# --- CONFIGURATION ---
SOURCE_RANK = {
    "LVHS": 1,
    "Lander Chamber": 2,
    "CWC": 3,
    "WRVC": 4, 
    "County 10": 5
}

SOURCE_COLORS = {
    "County 10":      {'bg': '#e91e63', 'text': 'white'},
    "WRVC":           {'bg': '#3498db', 'text': 'white'},
    "Lander Chamber": {'bg': '#00b894', 'text': 'white'},
    "CWC":            {'bg': '#e67e22', 'text': 'white'},
    "LVHS":           {'bg': '#f1c40f', 'text': 'black'}
}

# --- NEW LANDER TAXONOMY & WEIGHTS ---
CATEGORY_WEIGHTS = {
    "Government & Civic": {
        "keywords": ["council", "board", "commission", "trustee", "session", "committee", "legislative", "mayor", "ward"],
        "source_boost": {"Lander Chamber": 1}
    },
    "School & Education": {
        "keywords": ["no school", "graduation", "parent", "teacher", "class", "workshop", "college", "university", "seminar", "training", "scholarship", "fafsa", "exam", "testing", "break"],
        "source_boost": {"LVHS": 5, "CWC": 3}
    },
    "Sports & Outdoors": {
        "keywords": ["pickleball", "tennis", "bouldering", "climb", "hike", "trek", "race", "run", "marathon", "volleyball", "basketball", "football", "soccer", "swim", "wrestling", "golf", "track", "gym", "ski", "yoga", "fitness"],
        "source_boost": {"LVHS": 2, "WRVC": 2}
    },
    "Arts & Culture": {
        "keywords": ["concert", "play", "theater", "theatre", "art", "painting", "drawing", "music", "opera", "symphony", "choir", "band", "jazz", "performance", "exhibit", "gallery", "film", "movie", "screening", "dance", "recital"],
        "source_boost": {"CWC": 1}
    },
    "Community & Social": {
        "keywords": ["coffee", "rotary", "bingo", "fundraiser", "support group", "pflag", "aa", "na", "club", "lodge", "social", "gathering", "meetup", "volunteer", "donation"],
        "source_boost": {}
    },
    "Family & Youth": {
        "keywords": ["storytime", "lego", "kids", "youth", "family", "toddler", "baby", "children", "homeschool", "scouts", "4-h", "camp"],
        "source_boost": {"WRVC": 1}
    },
    "Business & Networking": {
        "keywords": ["business after hours", "bah", "chamber", "networking", "expo", "ribbon cutting", "grand opening", "job fair", "career", "employment", "entrepreneur", "innovation"],
        "source_boost": {"Lander Chamber": 3}
    },
    "Food & Drink": {
        "keywords": ["farmers market", "pancake", "dinner", "luncheon", "breakfast", "brunch", "bbq", "barbecue", "steak", "wine", "beer", "brew", "chili", "feed"],
        "source_boost": {}
    },
    "Holiday / Seasonal": {
        "keywords": ["christmas", "halloween", "easter", "thanksgiving", "4th of july", "independence day", "santa", "holiday", "festive", "parade", "fireworks", "trick or treat"],
        "source_boost": {}
    }
}

# --- PART 1: DATE PARSER ---
def parse_event_date(date_str, link_str=""):
    current_year = datetime.now().year
    iso_check = re.search(r'(\d{4}-\d{2}-\d{2})', str(date_str))
    if iso_check: return iso_check.group(1)
    if link_str:
        url_match = re.search(r'(\d{4}-\d{2}-\d{2})', link_str)
        if url_match: return url_match.group(1)
    clean_text = str(date_str).replace('at', '@').replace(',', '').replace('.', '')
    try:
        date_match = re.search(r'([A-Za-z]{3,9})\s+(\d{1,2})', clean_text)
        if date_match:
            month, day = date_match.groups()
            fmt = "%b" if len(month) == 3 else "%B"
            year = current_year
            year_match = re.search(r'\d{4}', clean_text)
            if year_match: year = year_match.group(0)
            dt = datetime.strptime(f"{month} {day} {year}", f"{fmt} %d %Y")
            return dt.strftime("%Y-%m-%d")
    except:
        pass
    return datetime.now().strftime("%Y-%m-%d")

# --- PART 2: SMART CATEGORY SCORING ---
def get_categories(title, source):
    """
    Returns a LIST of categories based on weighted keywords in the title.
    Primary category is the one with the highest score.
    'Community & Social' is auto-added for Festivals/Fairs/Parades.
    """
    title_lower = title.lower()
    scores = {cat: 0 for cat in CATEGORY_WEIGHTS}

    # 1. Calculate scores
    for cat, data in CATEGORY_WEIGHTS.items():
        # Source Boost
        matches_source = data["source_boost"].get(source, 0)
        scores[cat] += matches_source
        
        # Keyword Match
        for kw in data["keywords"]:
            if kw in title_lower:
                scores[cat] += 2 

    # 2. Determine Categories
    current_categories = []
    
    # Get winner(s)
    active_scores = {k: v for k, v in scores.items() if v > 0}
    if active_scores:
        primary_cat = max(active_scores, key=active_scores.get)
        current_categories.append(primary_cat)
    else:
        current_categories.append("Community & Social")

    # 3. Apply "Festival Rule" (Multi-Tagging)
    # If it's a Fest/Fair/Parade, ensure it's ALSO "Community & Social"
    festival_keywords = ["festival", "fest", "fair", "parade", "celebration", "market"]
    if any(k in title_lower for k in festival_keywords):
        if "Community & Social" not in current_categories:
            current_categories.append("Community & Social")

        # Farmer's Markets are also Food & Drink
        if "market" in title_lower and "Food & Drink" not in current_categories:
             current_categories.append("Food & Drink")

    return current_categories

# --- PART 3: ADVANCED DEDUPLICATION ---
master_events = {} 

def is_same_event(evt1, evt2):
    # 1. URL Match (Strongest Signal)
    if evt1['url'] and evt2['url'] and evt1['url'] != '#' and evt1['url'] == evt2['url']:
        return True
        
    # 2. Date Match (Relaxed - ignore time)
    # We only group by date key in master_events, so we know they are on the "same day" broadly.
    # But let's verify exact date string matches if formats differ
    if evt1['start'] != evt2['start']: return False
    
    # 3. Title Fuzzy Match
    def clean(t): 
        # Remove common filler words for better matching
        t = t.lower()
        t = re.sub(r'\\b(the|annual|monthly|weekly|meeting|of)\\b', '', t)
        return re.sub(r'[^a-z0-9]', '', t)
        
    t1, t2 = clean(evt1['title']), clean(evt2['title'])
    
    if t1 == t2: return True
    if len(t1) < 5 or len(t2) < 5: return False # Don't fuzzy match short titles
    
    return SequenceMatcher(None, t1, t2).ratio() > 0.75

def add_event_smart(new_event):
    date_key = new_event['start']
    if date_key not in master_events: master_events[date_key] = []
    merged = False
    for existing_event in master_events[date_key]:
        if is_same_event(new_event, existing_event):
            # Merge Logic: Keep highest rank source
            new_rank = SOURCE_RANK.get(new_event['extendedProps']['source'], 99)
            old_rank = SOURCE_RANK.get(existing_event['extendedProps']['source'], 99)
            
            if new_rank < old_rank:
                # Update existing with better data
                existing_event['title'] = new_event['title']
                existing_event['url'] = new_event['url']
                existing_event['color'] = new_event['color']
                existing_event['textColor'] = new_event['textColor']
                existing_event['extendedProps']['source'] = new_event['extendedProps']['source']
                # CHANGED: Use categories list
                existing_event['extendedProps']['categories'] = new_event['extendedProps']['categories'] 
            
            merged = True
            break
    if not merged: master_events[date_key].append(new_event)

# --- PART 4: LOAD DATA ---
def load_source(filename, source_name):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding='utf-8') as f:
                data = json.load(f)
                for e in data:
                    iso_date = parse_event_date(e['date'], e.get('link', ''))
                    style = SOURCE_COLORS.get(source_name, {'bg': '#3788d8', 'text': 'white'})
                    
                    event_obj = {
                        "title": e['title'],
                        "start": iso_date,
                        "allDay": True,
                        "url": e.get('link', '#'),
                        "color": style['bg'],
                        "textColor": style['text'],
                        "extendedProps": {
                            "source": source_name,
                            # CHANGED: Call get_categories
                            "categories": get_categories(e['title'], source_name)
                        }
                    }
                    add_event_smart(event_obj)
            print(f"✅ Processed {source_name}")
        except Exception as err:
            print(f"❌ Error in {filename}: {err}")


def generate_html(events):
    # Convert for FullCalendar
    fc_events = []
    
    # Color mapping for Sources
    source_colors = {
        "LVHS": "#f1c40f",       # Yellow
        "Lander Chamber": "#00b894", # Green/Teal
        "CWC": "#e67e22",        # Orange
        "WRVC": "#3498db",       # Blue
        "County 10": "#e91e63"   # Pink
    }

    for e in events:
        fc_events.append({
            "title": e["title"],
            "start": e["start"],
            "allDay": True,
            "url": e["url"],
            "color": source_colors.get(e["extendedProps"]["source"], "#95a5a6"),
            "textColor": "black" if e["extendedProps"]["source"] == "LVHS" else "white",
            "extendedProps": {
                "source": e["extendedProps"]["source"],
                "categories": e["extendedProps"]["categories"] # Pass list
            }
        })

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
  <head>
    <meta charset='utf-8' />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Lander Community Calendar</title>
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      html, body {{ height: auto; margin: 0; padding: 0; overflow-y: auto; }} 
      body {{ font-family: 'Inter', sans-serif; background-color: #f8f9fa; }}
      #calendar {{ max-width: 1100px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
      .fc-event {{ cursor: pointer; border: none; }}
      .filter-group {{ margin-bottom: 0.5rem; }}
      #main-wrapper {{ padding: 20px; }}
      @media (max-width: 768px) {{
          #main-wrapper {{ padding: 10px; }}
      }}
    </style>
  </head>
  <body>
    <div id="main-wrapper">
        <div class="max-w-6xl mx-auto mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">Lander Community Calendar</h1>
            <p class="text-gray-600 mb-6">Aggregated events from LVHS, Chamber, CWC, Wind River, and County 10.</p>
            
            <div class="bg-white p-4 rounded-lg shadow flex flex-wrap gap-6 items-center">
                
                <!-- Category Filter -->
                <div class="filter-group">
                    <label class="block text-sm font-semibold text-gray-700 mb-1">Category</label>
                    <select id="categoryFilter" class="p-2 border rounded hover:border-blue-500 focus:ring focus:ring-blue-200 transition">
                        <option value="all">All Categories</option>
                        <option value="Government & Civic">Government & Civic</option>
                        <option value="School & Education">School & Education</option>
                        <option value="Sports & Outdoors">Sports & Outdoors</option>
                        <option value="Arts & Culture">Arts & Culture</option>
                        <option value="Community & Social">Community & Social</option>
                        <option value="Family & Youth">Family & Youth</option>
                        <option value="Business & Networking">Business & Networking</option>
                        <option value="Food & Drink">Food & Drink</option>
                        <option value="Holiday / Seasonal">Holiday / Seasonal</option>
                    </select>
                </div>

                <!-- Source Filter -->
                <div class="filter-group">
                    <label class="block text-sm font-semibold text-gray-700 mb-1">Source</label>
                    <select id="sourceFilter" class="p-2 border rounded hover:border-blue-500 focus:ring focus:ring-blue-200 transition">
                        <option value="all">All Sources</option>
                        <option value="LVHS">LVHS</option>
                        <option value="Lander Chamber">Lander Chamber</option>
                        <option value="CWC">CWC</option>
                        <option value="WRVC">Wind River Visitors Council</option>
                        <option value="County 10">County 10</option>
                    </select>
                </div>

                <button id="resetFilters" class="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded text-gray-700 transition">Reset</button>
            </div>
        </div>

        <div id='calendar'></div>
    </div>

    <script>
        var rawEvents = {json.dumps(fc_events)};

        // --- BROADCASTER (Iframe Resizer) ---
        function sendHeight() {{
            const wrapper = document.getElementById('main-wrapper');
            if (wrapper) {{
                const height = wrapper.offsetHeight;
                window.parent.postMessage({{ frameHeight: height }}, "*");
            }}
        }}
        window.addEventListener('load', sendHeight);
        window.addEventListener('resize', sendHeight);
        const resizeObserver = new ResizeObserver(() => requestAnimationFrame(sendHeight));
        resizeObserver.observe(document.getElementById('main-wrapper'));
        setInterval(sendHeight, 1000); 

        document.addEventListener('DOMContentLoaded', function() {{
            var calendarEl = document.getElementById('calendar');
            var categoryFilter = document.getElementById('categoryFilter');
            var sourceFilter = document.getElementById('sourceFilter');
            var resetBtn = document.getElementById('resetFilters');
            
            // Default to Year list on mobile or if previously selected
            var initialView = window.innerWidth < 768 ? 'listYear' : 'dayGridMonth';

            // --- FILTERING LOGIC ---
            function getFilterValues() {{
                return {{
                    category: categoryFilter.value,
                    source: sourceFilter.value
                }};
            }}

            function filterEvents(events) {{
                var filters = getFilterValues();
                return events.filter(function(event) {{
                    // Source Filter
                    if (filters.source !== 'all' && event.extendedProps.source !== filters.source) {{
                        return false;
                    }}
                    
                    // Category Filter (Multi-tag support)
                    if (filters.category !== 'all') {{
                        if (!event.extendedProps.categories.includes(filters.category)) {{
                            return false;
                        }}
                    }}
                    
                    return true;
                }});
            }}

            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: initialView,
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,listYear'
                }},
                height: 'auto', // Allow it to grow, don't scroll internally
                events: rawEvents,
                eventClick: function(info) {{
                    info.jsEvent.preventDefault();
                    if (info.event.url) {{
                        window.open(info.event.url);
                    }}
                }},
                eventDidMount: function(info) {{
                    // Tooltip
                    info.el.title = info.event.title + " (" + info.event.extendedProps.source + ")";
                    
                    // Replace "all-day" with tags in List View
                    if (info.view.type === 'listYear' || info.view.type === 'listMonth') {{
                        var timeEl = info.el.querySelector('.fc-list-event-time');
                        if (timeEl) {{
                            timeEl.innerText = ''; // Clear "all-day"
                            var cats = info.event.extendedProps.categories;
                            if (cats && cats.length > 0) {{
                                cats.forEach(function(cat) {{
                                    var span = document.createElement('span');
                                    span.innerText = cat;
                                    // Style logic (could be improved with a map, but hardcoding broad colors for now)
                                    var bg = '#e2e8f0'; // default gray
                                    var text = '#475569';
                                    
                                    if (cat.includes('Sports')) {{ bg = '#dcfce7'; text = '#166534'; }} // green
                                    else if (cat.includes('Arts')) {{ bg = '#fce7f3'; text = '#9d174d'; }} // pink
                                    else if (cat.includes('Community')) {{ bg = '#dbeafe'; text = '#1e40af'; }} // blue
                                    else if (cat.includes('School')) {{ bg = '#fef9c3'; text = '#854d0e'; }} // yellow
                                    else if (cat.includes('Food')) {{ bg = '#ffedd5'; text = '#9a3412'; }} // orange
                                    else if (cat.includes('Business')) {{ bg = '#f3f4f6'; text = '#1f2937'; }} // gray-dark
                                    
                                    span.style.cssText = 'display: inline-block; padding: 2px 6px; margin-right: 4px; border-radius: 4px; font-size: 0.75em; font-weight: 600; text-transform: uppercase; background-color: ' + bg + '; color: ' + text + ';';
                                    timeEl.appendChild(span);
                                }});
                            }}
                        }}
                    }}
                }},
                datesSet: function() {{
                    setTimeout(sendHeight, 200);
                }},
                windowResize: function(view) {{
                    if (window.innerWidth < 768) {{
                        calendar.changeView('listYear');
                    }} else {{
                        calendar.changeView('dayGridMonth');
                    }}
                }}
            }});

            calendar.render();

            // --- EVENT LISTENERS ---
            function applyFilters() {{
                var filtered = filterEvents(rawEvents);
                calendar.removeAllEvents();
                calendar.addEventSource(filtered);
                calendar.render(); 
                setTimeout(sendHeight, 200);
            }}

            categoryFilter.addEventListener('change', applyFilters);
            sourceFilter.addEventListener('change', applyFilters);

            resetBtn.addEventListener('click', function() {{
                categoryFilter.value = 'all';
                sourceFilter.value = 'all';
                applyFilters();
            }});
        }});
    </script>
  </body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


def main():
    load_source("lvhs_data.json", "LVHS")
    load_source("chamber_data.json", "Lander Chamber")
    load_source("cwc_data.json", "CWC")
    load_source("windriver_data.json", "WRVC")
    load_source("county10_data.json", "County 10")

    final_list = []
    for day_list in master_events.values():
        final_list.extend(day_list)
        
    # Debug output
    print(f"Total Unique Events: {len(final_list)}")
    from collections import Counter
    cats = Counter()
    for e in final_list:
        if 'categories' in e['extendedProps']:
            for c in e['extendedProps']['categories']:
                cats[c] += 1
    print("Category Distribution:", cats)
    
    generate_html(final_list)
    print("Generated index.html")

if __name__ == "__main__":
    main()
