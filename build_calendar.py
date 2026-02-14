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
    "Wind River": 4,
    "County 10": 5
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

# --- PART 2: CATEGORY TAGGING ---
def get_category(title, source):
    t = title.lower()
    if source == "LVHS":
        if any(x in t for x in ['basketball', 'football', 'volleyball', 'soccer', 'swim', 'wrestling', 'golf', 'track', 'tennis']):
            return 'Sports & Outdoor'
        if any(x in t for x in ['concert', 'band', 'choir', 'jazz', 'play', 'drama', 'theater', 'art']):
            return 'Arts & Music'
        return 'Kids & Family'
    if any(x in t for x in ['kids', 'storytime', 'lego', 'youth', 'family', 'toddler', 'baby']): return 'Kids & Family'
    if any(x in t for x in ['music', 'concert', 'jam', 'live', 'band', 'choir', 'opera', 'art', 'paint', 'draw', 'clay', 'theater']): return 'Arts & Music'
    if any(x in t for x in ['hike', 'run', 'yoga', 'fitness', 'pickleball', 'sport', 'tennis', 'gym', 'ski', 'trek']): return 'Sports & Outdoor'
    if any(x in t for x in ['book', 'reading', 'author', 'poetry', 'library', 'history', 'museum', 'class', 'workshop', 'lecture']): return 'Learning & Lit'
    if any(x in t for x in ['chamber', 'business', 'networking', 'expo', 'leadership']): return 'Business'
    return 'Community'

# --- PART 3: SMART MERGE ---
master_events = {} 

def is_same_event(evt1, evt2):
    if evt1['start'] != evt2['start']: return False
    def clean(t): return re.sub(r'[^a-z0-9]', '', t.lower())
    t1, t2 = clean(evt1['title']), clean(evt2['title'])
    if t1 == t2: return True
    return SequenceMatcher(None, t1, t2).ratio() > 0.70

def add_event_smart(new_event):
    date_key = new_event['start']
    if date_key not in master_events: master_events[date_key] = []
    merged = False
    for existing_event in master_events[date_key]:
        if is_same_event(new_event, existing_event):
            new_rank = SOURCE_RANK.get(new_event['extendedProps']['source'], 99)
            old_rank = SOURCE_RANK.get(existing_event['extendedProps']['source'], 99)
            if new_rank < old_rank:
                existing_event['title'] = new_event['title']
                existing_event['url'] = new_event['url']
                existing_event['color'] = new_event['color']
                existing_event['extendedProps']['source'] = new_event['extendedProps']['source']
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
                    event_obj = {
                        "title": e['title'],
                        "start": iso_date,
                        "allDay": True,
                        "url": e.get('link', '#'),
                        "extendedProps": {
                            "source": source_name,
                            "category": get_category(e['title'], source_name)
                        }
                    }
                    if source_name == "County 10": event_obj['color'] = '#e91e63' 
                    elif source_name == "Wind River": event_obj['color'] = '#3498db' 
                    elif source_name == "Lander Chamber": event_obj['color'] = '#00b894' 
                    elif source_name == "CWC": event_obj['color'] = '#e67e22' 
                    elif source_name == "LVHS": event_obj['color'] = '#f1c40f'
                    add_event_smart(event_obj)
            print(f"✅ Processed {source_name}")
        except Exception as err:
            print(f"❌ Error in {filename}: {err}")

load_source("lvhs_data.json", "LVHS")
load_source("chamber_data.json", "Lander Chamber")
load_source("cwc_data.json", "CWC")
load_source("windriver_data.json", "Wind River")
load_source("county10_data.json", "County 10")

final_list = []
for day_list in master_events.values():
    final_list.extend(day_list)

# --- PART 5: GENERATE HTML (With Fixed Resize Logic) ---
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8' />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Lander Events</title>
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; background: #f0f2f5; color: #333; overflow-y: hidden; }}
        
        #header {{ 
            background: white; 
            padding: 25px; 
            border-radius: 12px; 
            margin-bottom: 20px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        h2 {{ color: #2c3e50; margin: 0 0 15px 0; font-size: 1.8rem; }}
        
        .search-row {{ margin-bottom: 15px; display: flex; gap: 10px; }}
        .search-wrapper {{ position: relative; width: 100%; }}
        #search-input {{ 
            width: 100%; 
            padding: 12px 16px 12px 45px; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            font-size: 1rem; 
            box-sizing: border-box; 
            transition: border-color 0.2s;
        }}
        #search-input:focus {{ border-color: #2c3e50; outline: none; }}
        .search-icon {{ 
            position: absolute; left: 15px; top: 50%; transform: translateY(-50%); 
            color: #999; font-size: 1.2rem; pointer-events: none;
        }}

        #mobile-filter-toggle {{
            display: none;
            padding: 12px 16px;
            background: #f0f2f5;
            border: 1px solid #ddd;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            color: #555;
            white-space: nowrap;
        }}
        #mobile-filter-toggle:hover {{ background: #e4e6e9; }}

        #controls-container {{
            transition: max-height 0.3s ease-out;
            overflow: hidden;
        }}

        .controls-row {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 15px; }}
        .label {{ font-weight: 600; color: #555; font-size: 0.9em; min-width: 80px; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        .filter-btn {{ padding: 8px 16px; border: 1px solid #e0e0e0; background: white; cursor: pointer; border-radius: 20px; font-size: 0.9rem; transition: all 0.2s; color: #555; }}
        .filter-btn:hover {{ background: #f5f5f5; border-color: #ccc; }}
        .filter-btn.active {{ background: #2c3e50; color: white; border-color: #2c3e50; }}
        
        .source-toggle {{ display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 6px 12px; border-radius: 6px; border: 1px solid #eee; background: #fafafa; font-size: 0.9rem; user-select: none; transition: background 0.2s; }}
        .source-toggle:hover {{ background: #f0f0f0; border-color: #ddd; }}
        .source-toggle input {{ accent-color: #2c3e50; cursor: pointer; width: 16px; height: 16px; }}
        
        #calendar {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); max-width: 1200px; margin: 0 auto; }}
        .fc-event {{ cursor: pointer; border: none !important; font-size: 0.9em; border-radius: 4px; }}
        .fc-event-title {{ color: #fff; text-shadow: 0 0 2px rgba(0,0,0,0.3); font-weight: 500; }}
        .fc-toolbar-title {{ font-size: 1.5em !important; color: #2c3e50; }}
        .fc-button-primary {{ background-color: #2c3e50 !important; border-color: #2c3e50 !important; }}

        @media (max-width: 768px) {{
            body {{ padding: 10px; }}
            #header {{ padding: 15px; margin-bottom: 10px; }}
            h2 {{ font-size: 1.4rem; margin-bottom: 10px; }}
            #mobile-filter-toggle {{ display: block; }}
            #controls-container {{ max-height: 0; opacity: 0; margin-top: 0; }}
            #controls-container.open {{ max-height: 500px; opacity: 1; margin-top: 15px; }}
            .controls-row {{ flex-direction: column; align-items: stretch; gap: 8px; }}
            .filter-btn {{ text-align: center; }}
            #calendar {{ padding: 10px; }}
            .fc-toolbar {{ flex-direction: column; gap: 10px; }}
            .fc-toolbar-title {{ font-size: 1.2em !important; }}
        }}
    </style>
</head>
<body>
    <div id="header">
        <h2>📅 Lander Mega Calendar</h2>
        
        <div class="search-row">
            <div class="search-wrapper">
                <span class="search-icon">🔍</span>
                <input type="text" id="search-input" placeholder="Search events..." onkeyup="handleSearch()" />
            </div>
            <button id="mobile-filter-toggle" onclick="toggleMobileFilters()">⚙️ Filters</button>
        </div>
        
        <div id="controls-container">
            <div class="controls-row">
                <div class="label">Filter:</div>
                <button class="filter-btn active" onclick="setCategory('all')">All</button>
                <button class="filter-btn" onclick="setCategory('Community')">🤝 Community</button>
                <button class="filter-btn" onclick="setCategory('Arts & Music')">🎨 Arts & Music</button>
                <button class="filter-btn" onclick="setCategory('Sports & Outdoor')">🏔️ Sports</button>
                <button class="filter-btn" onclick="setCategory('Kids & Family')">🧸 Kids</button>
                <button class="filter-btn" onclick="setCategory('Learning & Lit')">📚 Learning</button>
                <button class="filter-btn" onclick="setCategory('Business')">💼 Business</button>
            </div>

            <div class="controls-row">
                <div class="label">Sources:</div>
                <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('Lander Chamber')" /> Chamber</label>
                <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('LVHS')" /> High School</label>
                <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('CWC')" /> CWC</label>
                <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('Wind River')" /> Wind River</label>
                <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('County 10')" /> County 10</label>
            </div>
        </div>
    </div>
    
    <div id='calendar'></div>

    <script>
        var rawEvents = {json.dumps(final_list)};
        var calendar;
        var currentCategory = 'all';
        var activeSources = ['Lander Chamber', 'LVHS', 'CWC', 'Wind River', 'County 10'];
        var searchTerm = '';
        var lastWidth = window.innerWidth; // Track width to prevent resize loops

        // --- BROADCAST SYSTEM ---
        function sendHeight() {{
            const height = document.documentElement.scrollHeight;
            window.parent.postMessage({{ frameHeight: height }}, "*");
        }}

        // 1. Send immediately on load
        window.addEventListener('load', sendHeight);
        
        // 2. Send via Observer (Detects content changes like list view)
        const resizeObserver = new ResizeObserver(sendHeight);
        resizeObserver.observe(document.body);

        document.addEventListener('DOMContentLoaded', function() {{
            var calendarEl = document.getElementById('calendar');
            var initialView = window.innerWidth < 768 ? 'listMonth' : 'dayGridMonth';

            calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: initialView,
                headerToolbar: {{ left: 'prev,next today', center: 'title', right: 'dayGridMonth,listMonth' }},
                height: 'auto',
                events: rawEvents,
                eventClick: function(info) {{
                    info.jsEvent.preventDefault();
                    if (info.event.url) window.open(info.event.url, "_blank");
                }},
                windowResize: function(view) {{
                    var currentWidth = window.innerWidth;
                    // FIX: Only change view if we actually crossed the mobile/desktop threshold
                    // This prevents vertical resizing (from height changes) from resetting the view
                    if ((lastWidth < 768 && currentWidth >= 768) || (lastWidth >= 768 && currentWidth < 768)) {{
                        if (currentWidth < 768) {{
                            calendar.changeView('listMonth');
                        }} else {{
                            calendar.changeView('dayGridMonth');
                        }}
                    }}
                    lastWidth = currentWidth;
                    sendHeight();
                }},
                eventDidMount: function() {{
                     setTimeout(sendHeight, 100);
                }}
            }});
            calendar.render();
        }});

        function toggleMobileFilters() {{
            var container = document.getElementById('controls-container');
            container.classList.toggle('open');
            setTimeout(sendHeight, 350);
        }}

        function applyFilters() {{
            var filtered = rawEvents.filter(e => {{
                var catMatch = (currentCategory === 'all' || e.extendedProps.category === currentCategory);
                var sourceMatch = activeSources.includes(e.extendedProps.source);
                var searchMatch = true;
                if (searchTerm) {{
                    var lowerTerm = searchTerm.toLowerCase();
                    var inTitle = e.title.toLowerCase().includes(lowerTerm);
                    var inSource = e.extendedProps.source.toLowerCase().includes(lowerTerm);
                    var inTag = e.extendedProps.category.toLowerCase().includes(lowerTerm);
                    searchMatch = (inTitle || inSource || inTag);
                }}
                return catMatch && sourceMatch && searchMatch;
            }});
            
            calendar.removeAllEvents();
            calendar.addEventSource(filtered);
            setTimeout(sendHeight, 200);
        }}

        function setCategory(cat) {{
            currentCategory = cat;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            applyFilters();
        }}

        function toggleSource(sourceName) {{
            if (activeSources.includes(sourceName)) {{
                activeSources = activeSources.filter(s => s !== sourceName);
            }} else {{
                activeSources.push(sourceName);
            }}
            applyFilters();
        }}

        function handleSearch() {{
            var input = document.getElementById('search-input');
            searchTerm = input.value.trim();
            applyFilters();
        }}
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\n🎉 UI Updated! Fixed 'List View' snap-back bug.")
