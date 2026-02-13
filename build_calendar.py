import json
import os
from datetime import datetime
import re
from difflib import SequenceMatcher

# --- CONFIGURATION ---
SOURCE_RANK = {
    "LVHS": 1,          # School events take top priority
    "Lander Chamber": 2,
    "CWC": 3,
    "Wind River": 4,
    "County 10": 5
}

# --- PART 1: DATE PARSER ---
def parse_event_date(date_str, link_str=""):
    current_year = datetime.now().year
    
    # 1. ISO Check (Handles LVHS "2026-03-06T15:45:00...")
    iso_check = re.search(r'(\d{4}-\d{2}-\d{2})', str(date_str))
    if iso_check: return iso_check.group(1)

    # 2. URL Check
    if link_str:
        url_match = re.search(r'(\d{4}-\d{2}-\d{2})', link_str)
        if url_match: return url_match.group(1)

    # 3. Text Check
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
    
    # LVHS specific logic
    if source == "LVHS":
        if any(x in t for x in ['basketball', 'football', 'volleyball', 'soccer', 'swim', 'wrestling', 'golf', 'track', 'tennis']):
            return 'Sports & Outdoor'
        if any(x in t for x in ['concert', 'band', 'choir', 'jazz', 'play', 'drama', 'theater', 'art']):
            return 'Arts & Music'
        return 'Kids & Family' # Default for school events

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
                    elif source_name == "LVHS": event_obj['color'] = '#f1c40f' # Gold for Tigers
                    
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

# --- PART 5: GENERATE HTML ---
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8' />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Lander Events</title>
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; background: #f0f2f5; }}
        #header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        h2 {{ color: #2c3e50; margin: 0 0 15px 0; }}
        
        .controls-row {{ display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; }}
        .label {{ font-weight: bold; color: #555; font-size: 0.9em; min-width: 80px; }}
        
        .filter-btn {{ padding: 6px 12px; border: 1px solid #ccc; background: white; cursor: pointer; border-radius: 20px; font-size: 0.9rem; transition: all 0.2s; }}
        .filter-btn:hover {{ background: #eee; transform: translateY(-1px); }}
        .filter-btn.active {{ background: #2c3e50; color: white; border-color: #2c3e50; }}
        
        .source-toggle {{ display: flex; align-items: center; gap: 5px; cursor: pointer; padding: 4px 10px; border-radius: 4px; border: 1px solid #eee; background: #f9f9f9; }}
        .source-toggle:hover {{ background: #eee; }}
        .source-toggle input {{ accent-color: #2c3e50; cursor: pointer; }}
        
        #calendar {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 1200px; margin: 0 auto; }}
        .fc-event {{ cursor: pointer; border: none !important; font-size: 0.85em; }}
        .fc-daygrid-event {{ border-radius: 3px; padding: 2px 4px; margin-bottom: 2px !important; }}
        .fc-event-title {{ color: #fff; text-shadow: 0 0 2px rgba(0,0,0,0.5); }}
        
        @media (max-width: 600px) {{
            .controls-row {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
            .fc-toolbar {{ flex-direction: column; gap: 10px; }}
        }}
    </style>
</head>
<body>
    <div id="header">
        <h2>📅 Lander Mega Calendar</h2>
        
        <div class="controls-row">
            <div class="label">Filter By:</div>
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
            <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('Lander Chamber')" /> Lander Chamber</label>
            <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('LVHS')" /> LVHS (High School)</label>
            <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('CWC')" /> CWC</label>
            <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('Wind River')" /> Wind River</label>
            <label class="source-toggle"><input type="checkbox" checked onchange="toggleSource('County 10')" /> County 10</label>
        </div>
    </div>
    
    <div id='calendar'></div>

    <script>
        var rawEvents = {json.dumps(final_list)};
        var calendar;
        var currentCategory = 'all';
        var activeSources = ['Lander Chamber', 'LVHS', 'CWC', 'Wind River', 'County 10'];

        document.addEventListener('DOMContentLoaded', function() {{
            var calendarEl = document.getElementById('calendar');
            calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: 'dayGridMonth',
                displayEventTime: false,
                headerToolbar: {{ left: 'prev,next today', center: 'title', right: 'dayGridMonth,listMonth' }},
                events: rawEvents,
                eventClick: function(info) {{
                    info.jsEvent.preventDefault();
                    if (info.event.url) window.open(info.event.url, "_blank");
                }},
                eventDidMount: function(info) {{
                    info.el.title = info.event.title + "\\nSource: " + info.event.extendedProps.source;
                }}
            }});
            calendar.render();
        }});

        function applyFilters() {{
            var filtered = rawEvents.filter(e => {{
                var catMatch = (currentCategory === 'all' || e.extendedProps.category === currentCategory);
                var sourceMatch = activeSources.includes(e.extendedProps.source);
                return catMatch && sourceMatch;
            }});
            calendar.removeAllEvents();
            calendar.addEventSource(filtered);
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
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\n🎉 Added LVHS! Total Events: {len(final_list)}")
