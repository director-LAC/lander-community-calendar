import json
import os
from datetime import datetime
import re
from difflib import SequenceMatcher
from typing import Dict, List, Any

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
CATEGORY_WEIGHTS: Dict[str, Dict[str, Any]] = {
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
            if year_match: year = int(year_match.group(0))
            dt = datetime.strptime(f"{month} {day} {year}", f"{fmt} %d %Y")
            return dt.strftime("%Y-%m-%d")
    except:
        pass
    return datetime.now().strftime("%Y-%m-%d")

# --- PART 2: SMART CATEGORY SCORING ---
def get_categories(title: str, source: str) -> List[str]:
    title_lower = title.lower()
    scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_WEIGHTS}

    # 1. Calculate scores
    for cat, data in CATEGORY_WEIGHTS.items():
        # Source Boost
        boost_dict = data.get("source_boost", {})
        if isinstance(boost_dict, dict):
            scores[cat] += boost_dict.get(source, 0)
        
        # Keyword Match
        for kw in data.get("keywords", []):
            if kw in title_lower:
                scores[cat] += 2 

    # 2. Determine Categories
    current_categories: List[str] = []
    
    # Get winner(s)
    active_scores = {k: v for k, v in scores.items() if v > 0}
    if active_scores:
        # Use simple lambda for key to avoid .get ambiguity
        primary_cat = max(active_scores.keys(), key=lambda x: active_scores[x])
        current_categories.append(primary_cat)
    else:
        current_categories.append("Community & Social")

    # 3. Apply "Festival Rule"
    festival_keywords = ["festival", "fest", "fair", "parade", "celebration", "market"]
    if any(k in title_lower for k in festival_keywords):
        if "Community & Social" not in current_categories:
            current_categories.append("Community & Social")
        if "market" in title_lower and "Food & Drink" not in current_categories:
             current_categories.append("Food & Drink")

    return current_categories

# --- PART 3: ADVANCED DEDUPLICATION ---
master_events: Dict[str, List[Dict[str, Any]]] = {} 

def is_same_event(evt1, evt2):
    if evt1['url'] and evt2['url'] and evt1['url'] != '#' and evt1['url'] == evt2['url']:
        return True
    if evt1['start'] != evt2['start']: return False
    def clean(t): 
        t = t.lower()
        t = re.sub(r'\b(the|annual|monthly|weekly|meeting|of)\b', '', t)
        return re.sub(r'[^a-z0-9]', '', t)
    t1, t2 = clean(evt1['title']), clean(evt2['title'])
    if t1 == t2: return True
    if len(t1) < 5 or len(t2) < 5: return False
    return SequenceMatcher(None, t1, t2).ratio() > 0.75

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
                existing_event['textColor'] = new_event['textColor']
                existing_event['extendedProps']['source'] = new_event['extendedProps']['source']
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
                            "categories": get_categories(e['title'], source_name)
                        }
                    }
                    add_event_smart(event_obj)
            print(f"✅ Processed {source_name}")
        except Exception as err:
            print(f"❌ Error in {filename}: {err}")


def generate_html(events):
    fc_events = []
    categories_list = sorted(list(CATEGORY_WEIGHTS.keys()))
    sources_list = sorted(list(SOURCE_RANK.keys()))

    source_colors = {
        "LVHS": "#f1c40f",
        "Lander Chamber": "#00b894",
        "CWC": "#e67e22",
        "WRVC": "#3498db",
        "County 10": "#e91e63"
    }

    for e in events:
        fc_events.append({
            "title": e["title"],
            "start": e["start"],
            "url": e["url"],
            "color": source_colors.get(e["extendedProps"]["source"], "#95a5a6"),
            "textColor": "black" if e["extendedProps"]["source"] == "LVHS" else "white",
            "extendedProps": {
                "source": e["extendedProps"]["source"],
                "categories": e["extendedProps"]["categories"]
            }
        })
    
    # Generate Pill HTML without literal \n
    cat_pills = " ".join([f'<button class="filter-btn" data-type="category" data-value="{cat}">{cat}</button>' for cat in categories_list])
    
    # Generate Source pills with color metadata
    src_pills_list = []
    for src in sources_list:
        color_config = SOURCE_COLORS.get(src, {'bg': '#3788d8', 'text': 'white'})
        src_pills_list.append(f'<button class="filter-btn" data-type="source" data-value="{src}" data-color="{color_config["bg"]}" data-text="{color_config["text"]}">{src}</button>')
    src_pills = " ".join(src_pills_list)

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
      .filter-container {{ background: white; padding: 1.5rem; border-radius: 0.8rem; box-shadow: 0 4px 20px -5px rgb(0 0 0 / 0.1); margin-bottom: 2rem; }}
      .filter-section {{ margin-bottom: 1.2rem; }}
      .filter-label {{ display: block; font-size: 0.85rem; font-weight: 700; color: #4b5563; margin-bottom: 0.6rem; text-transform: uppercase; letter-spacing: 0.025em; }}
      .pills-wrapper {{ display: flex; flex-wrap: wrap; gap: 0.6rem; }}
      .filter-btn {{ padding: 0.35rem 1rem; border-radius: 99px; border: 1px solid #e5e7eb; background: white; color: #374151; font-size: 0.9rem; font-weight: 500; transition: all 0.2s; cursor: pointer; }}
      .filter-btn:hover {{ border-color: #3b82f6; background: #eff6ff; }}
      
      /* Active state for Category pills (Standard Blue) */
      [data-type="category"].filter-btn.active {{ background: #3b82f6; color: white; border-color: #3b82f6; box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3); }}
      
      /* Active state for Source pills (Managed by JS/Dynamic) */
      [data-type="source"].filter-btn.active {{ border-color: transparent; }}

      #search-container {{ position: relative; margin-bottom: 1.5rem; }}
      #search-input {{ width: 100%; padding: 0.75rem 1rem; padding-left: 2.5rem; border: 1px solid #d1d5db; border-radius: 0.5rem; font-size: 1rem; box-shadow: inset 0 2px 4px 0 rgb(0 0 0 / 0.05); }}
      .search-icon {{ position: absolute; left: 0.8rem; top: 0.8rem; color: #9ca3af; }}
      #main-wrapper {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
      
      @media (max-width: 768px) {{ 
        #main-wrapper {{ padding: 10px; }}
        .filter-container {{ display: none; margin-bottom: 1rem; }}
        .filter-container.show {{ display: block; }}
        #mobile-filter-toggle {{ display: block; }}
        .fc-toolbar {{ flex-direction: column; gap: 10px; }}
      }}
      @media (min-width: 769px) {{ #mobile-filter-toggle {{ display: none; }} }}
    </style>
  </head>
  <body>
    <div id="main-wrapper">
        <div class="mb-8">
            <h1 class="text-4xl font-black text-slate-900 mb-2">Lander Community Calendar</h1>
            <p class="text-slate-500 font-medium whitespace-nowrap overflow-hidden text-ellipsis">Aggregated events from LVHS, Chamber, CWC, Wind River, and County 10.</p>
        </div>

        <button id="mobile-filter-toggle" class="w-full bg-slate-800 text-white font-bold py-3 px-4 rounded-lg mb-4 flex justify-between items-center">
            <span>🔍 Filters & Search</span>
            <span id="toggle-icon">▼</span>
        </button>

        <div class="filter-container" id="filter-panel">
            <div id="search-container">
                <span class="search-icon">🔍</span>
                <input type="text" id="search-input" placeholder="Search events...">
            </div>

            <div class="filter-section">
                <span class="filter-label">Categories</span>
                <div class="pills-wrapper" id="category-filters">
                    <button class="filter-btn active" data-type="category" data-value="all">All</button>
                    {cat_pills}
                </div>
            </div>

            <div class="filter-section">
                <span class="filter-label">Sources</span>
                <div class="pills-wrapper" id="source-filters">
                    <button class="filter-btn active" data-type="source" data-value="all" data-color="#3b82f6">All</button>
                    {src_pills}
                </div>
            </div>
            
            <div class="flex justify-end pt-2 border-t border-slate-100">
                 <button id="resetFilters" class="text-xs font-bold text-slate-400 hover:text-blue-500 uppercase tracking-widest transition-colors">Reset All</button>
            </div>
        </div>

        <div id='calendar'></div>
    </div>

    <script>
        var masterEventsList = {json.dumps(fc_events)};
        var currentFilters = {{ category: 'all', sources: ['all'], search: '' }};

        function applySourceStyles() {{
            document.querySelectorAll('[data-type="source"].filter-btn').forEach(btn => {{
                var color = btn.getAttribute('data-color') || '#3b82f6';
                var textColor = btn.getAttribute('data-text') || 'white';
                var val = btn.getAttribute('data-value');
                var isActive = currentFilters.sources.includes(val);

                btn.style.backgroundColor = color;
                btn.style.color = textColor;
                btn.style.borderColor = color;

                if (isActive) {{
                    btn.classList.add('active');
                    btn.style.opacity = '1';
                    btn.style.boxShadow = '0 0 0 3px ' + color + '44, 0 4px 6px -1px rgba(0,0,0,0.1)';
                    btn.style.transform = 'scale(1.05)';
                }} else {{
                    btn.classList.remove('active');
                    btn.style.opacity = '0.4';
                    btn.style.boxShadow = 'none';
                    btn.style.transform = 'scale(1)';
                }}
            }});
        }}

        function sendHeight() {{
            const wrapper = document.getElementById('main-wrapper');
            if (wrapper) {{
                const height = wrapper.offsetHeight;
                window.parent.postMessage({{ frameHeight: height }}, "*");
            }}
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            // Mobile toggle logic
            const toggleBtn = document.getElementById('mobile-filter-toggle');
            const filterPanel = document.getElementById('filter-panel');
            const toggleIcon = document.getElementById('toggle-icon');

            toggleBtn.addEventListener('click', function() {{
                filterPanel.classList.toggle('show');
                toggleIcon.innerText = filterPanel.classList.contains('show') ? '▲' : '▼';
                setTimeout(sendHeight, 300);
            }});

            var calendarEl = document.getElementById('calendar');
            applySourceStyles();
            
            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: window.innerWidth < 768 ? 'listYear' : 'dayGridMonth',
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,listYear'
                }},
                height: 'auto', 
                events: function(info, successCallback, failureCallback) {{
                    var filtered = masterEventsList.filter(function(e) {{
                        if (currentFilters.search) {{
                            var term = currentFilters.search.toLowerCase();
                            if (!e.title.toLowerCase().includes(term)) return false;
                        }}
                        
                        // Multi-source filtering
                        if (!currentFilters.sources.includes('all')) {{
                            if (!currentFilters.sources.includes(e.extendedProps.source)) return false;
                        }}

                        if (currentFilters.category !== 'all' && !e.extendedProps.categories.includes(currentFilters.category)) return false;
                        return true;
                    }});
                    successCallback(filtered);
                }},
                eventClick: function(info) {{
                    info.jsEvent.preventDefault();
                    if (info.event.url) window.open(info.event.url);
                }},
                eventDidMount: function(info) {{
                    info.el.title = info.event.title + " (" + info.event.extendedProps.source + ")";
                    if (info.view.type.includes('list')) {{
                        // Support list view items
                        var titleEl = info.el.querySelector('.fc-list-event-title');
                        if (titleEl) {{
                            // Prepend tags to title without breaking the title cell
                            var tagContainer = document.createElement('div');
                            tagContainer.style.marginBottom = '4px';
                            
                            var cats = info.event.extendedProps.categories;
                            (cats || []).forEach(function(cat) {{
                                var span = document.createElement('span');
                                span.innerText = cat;
                                var bg = '#f1f5f9'; var text = '#475569';
                                if (cat.includes('Sports')) {{ bg = '#dcfce7'; text = '#166534'; }}
                                else if (cat.includes('Arts')) {{ bg = '#fce7f3'; text = '#9d174d'; }}
                                else if (cat.includes('Community')) {{ bg = '#dbeafe'; text = '#1e40af'; }}
                                else if (cat.includes('School')) {{ bg = '#fef9c3'; text = '#854d0e'; }}
                                else if (cat.includes('Food')) {{ bg = '#ffedd5'; text = '#9a3412'; }}
                                span.style.cssText = 'display: inline-block; padding: 1px 6px; margin-right: 4px; border-radius: 4px; font-size: 0.65em; font-weight: 700; text-transform: uppercase; background:' + bg + '; color:' + text + ';';
                                tagContainer.appendChild(span);
                            }});
                            
                            // Insert before the title text link
                            var link = titleEl.querySelector('a');
                            if (link) {{
                                titleEl.insertBefore(tagContainer, link);
                            }} else {{
                                titleEl.prepend(tagContainer);
                            }}
                        }}
                    }}
                }},
                datesSet: function() {{ setTimeout(sendHeight, 200); }}
            }});

            calendar.render();

            // Filter Handlers
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    var type = this.dataset.type;
                    var val = this.dataset.value;

                    if (type === 'category') {{
                        this.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        currentFilters.category = val;
                    }} else if (type === 'source') {{
                        if (val === 'all') {{
                            currentFilters.sources = ['all'];
                        }} else {{
                            // Remove 'all' if present
                            currentFilters.sources = currentFilters.sources.filter(s => s !== 'all');
                            
                            // Toggle selection
                            if (currentFilters.sources.includes(val)) {{
                                currentFilters.sources = currentFilters.sources.filter(s => s !== val);
                            }} else {{
                                currentFilters.sources.push(val);
                            }}

                            // If nothing selected, default to 'all'
                            if (currentFilters.sources.length === 0) {{
                                currentFilters.sources = ['all'];
                            }}
                        }}
                        applySourceStyles();
                    }}
                    
                    calendar.refetchEvents();
                    setTimeout(sendHeight, 250);
                }});
            }});

            document.getElementById('search-input').addEventListener('input', function(e) {{
                currentFilters.search = e.target.value;
                calendar.refetchEvents();
            }});

            document.getElementById('resetFilters').addEventListener('click', function() {{
                currentFilters = {{ category: 'all', sources: ['all'], search: '' }};
                document.getElementById('search-input').value = '';
                document.querySelectorAll('[data-type="category"].filter-btn').forEach(b => b.classList.remove('active'));
                document.querySelector('[data-type="category"][data-value="all"]').classList.add('active');
                applySourceStyles();
                calendar.refetchEvents();
            }});
        }});

        window.addEventListener('load', sendHeight);
        window.addEventListener('resize', sendHeight);
        new ResizeObserver(() => sendHeight()).observe(document.getElementById('main-wrapper'));
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
    final_list = [e for dl in master_events.values() for e in dl]
    print(f"Total Unique Events: {{len(final_list)}}")
    generate_html(final_list)

if __name__ == "__main__":
    main()
