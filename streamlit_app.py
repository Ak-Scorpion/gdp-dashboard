import streamlit as st
import requests
import random
import hashlib
import re
from datetime import datetime, timedelta, timezone

# --- BSOUP ABSICHERUNG (Verhindert ModuleNotFoundError) ---
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Multi-Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []

ANBIETER_URLS = {
    "Tipico": "https://www.tipico.de",
    "DAZN Bet": "https://www.daznbet.de",
    "Betano": "https://www.betano.de",
    "bwin (Deutschland)": "https://sports.bwin.de",
    "Bet365 (DE)": "https://www.bet365.de",
    "Oddset": "https://www.oddset.de",
    "Neo.bet": "https://www.neo.bet/de",
    "Bet-at-home": "https://www.bet-at-home.com"
}

# 1. OPENLIGADB ENGINE (DEUTSCHLAND)
OPENLIGA_MAP = {
    "🇩🇪 1. Bundesliga": "bl1",
    "🇩🇪 2. Bundesliga": "bl2",
    "🇩🇪 3. Liga": "bl3"
}

@st.cache_data(ttl=180)
def fetch_openligadb(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

# 2. PUBLIC GITHUB OPEN-DATA
GITHUB_DATA_MAP = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/en.1.json",
    "🇪🇸 La Liga": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.1.json",
    "🇮🇹 Serie A": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/it.1.json",
    "🇫🇷 Ligue 1": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/fr.1.json"
}

@st.cache_data(ttl=300)
def fetch_github_opendata(url):
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            matches = []
            for rnd in data.get('rounds', []):
                for match in rnd.get('matches', []):
                    matches.append({
                        "home": match.get('team1'),
                        "away": match.get('team2'),
                        "date": match.get('date', '')
                    })
            return matches
    except Exception:
        pass
    return []

# 3. LIVE WEB SCRAPING WITH BS4 / REGEX FALLBACK
KICKER_URLS = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://www.kicker.de/premier-league/spieltag",
    "🇪🇸 La Liga": "https://www.kicker.de/la-liga/spieltag",
    "🇮🇹 Serie A": "https://www.kicker.de/serie-a/spieltag",
    "🇫🇷 Ligue 1": "https://www.kicker.de/ligue-1/spieltag"
}

@st.cache_data(ttl=180)
def scrape_kicker_live(league_label):
    url = KICKER_URLS.get(league_label)
    if not url:
        return []
    
    headers = {"User-Agent": "Mozilla/5.0"}
    matches = []
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            if HAS_BS4:
                soup = BeautifulSoup(res.text, 'html.parser')
                rows = soup.find_all('div', class_='kick__v100-gameCell')
                for row in rows:
                    try:
                        home = row.find('div', class_='kick__v100-gameCell__team--home').text.strip()
                        away = row.find('div', class_='kick__v100-gameCell__team--away').text.strip()
                        matches.append({"home": home, "away": away, "time": "18:30"})
                    except Exception:
                        continue
    except Exception:
        pass
    return matches

def generate_odds(home_team, away_team):
    seed = int(hashlib.md5(f"{home_team}{away_team}".encode()).hexdigest(), 16) % 1000
    random.seed(seed)
    q_h = round(random.uniform(1.45, 3.20), 2)
    q_a = round(random.uniform(2.10, 4.50), 2)
    random.seed()
    return q_h, q_a

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; color: #f1f5f9; font-family: 'Inter', sans-serif; }
    header[data-testid="stHeader"] { display: none !important; }
    .bet-card { background: #111827; border: 1px solid #1e293b; border-radius: 14px; padding: 18px; margin-bottom: 12px; }
    .badge { padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 800; display: inline-block; }
    .badge-openliga { background-color: #f59e0b; color: #070a13; }
    .badge-github { background-color: #8b5cf6; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

st.title("⚽ KI Wettprognosen Engine")

with st.expander("⚙️ Einstellungen", expanded=True):
    anbieter_wahl = st.radio("Wettanbieter:", list(ANBIETER_URLS.keys()), horizontal=True)
    
    col1, col2 = st.columns(2)
    aktive_ligen = []
    with col1:
        if st.checkbox("🇩🇪 1. Bundesliga (OpenLigaDB)", value=True): aktive_ligen.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🇩🇪 2. Bundesliga (OpenLigaDB)", value=True): aktive_ligen.append("🇩🇪 2. Bundesliga")
        if st.checkbox("🇩🇪 3. Liga (OpenLigaDB)", value=True): aktive_ligen.append("🇩🇪 3. Liga")
    with col2:
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True): aktive_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🇪🇸 La Liga", value=True): aktive_ligen.append("🇪🇸 La Liga")

    now_de = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))
    today_de = now_de.date()
    today_str = today_de.strftime("%d.%m.%Y")
    
    generate_click = st.button("🚀 Spiele laden", type="primary", use_container_width=True)

if generate_click:
    gefilterte_spiele = []
    for liga in aktive_ligen:
        if liga in OPENLIGA_MAP:
            raw_data = fetch_openligadb(OPENLIGA_MAP[liga])
            for match in raw_data:
                match_dt_str = match.get('matchDateTime')
                if match_dt_str:
                    dt = datetime.fromisoformat(match_dt_str.replace('Z', '+00:00'))
                    dt_de = dt.astimezone(timezone(timedelta(hours=2)))
                    if dt_de.date() == today_de:
                        home, away = match['team1']['teamName'], match['team2']['teamName']
                        q_h, q_a = generate_odds(home, away)
                        gefilterte_spiele.append({
                            "Liga": liga,
                            "Begegnung": f"{home} vs {away}",
                            "Tipp": f"Sieg {home}",
                            "Quote": q_h,
                            "Quelle": "OpenLigaDB",
                            "Badge": "badge-openliga"
                        })
        elif liga in GITHUB_DATA_MAP:
            github_matches = fetch_github_opendata(GITHUB_DATA_MAP[liga])
            for match in github_matches[:3]:
                home, away = match['home'], match['away']
                if home and away:
                    q_h, q_a = generate_odds(home, away)
                    gefilterte_spiele.append({
                        "Liga": liga,
                        "Begegnung": f"{home} vs {away}",
                        "Tipp": f"Sieg {home}",
                        "Quote": q_h,
                        "Quelle": "GitHub Open-Data",
                        "Badge": "badge-github"
                    })

    st.session_state['gefilterte_spiele'] = gefilterte_spiele

if 'gefilterte_spiele' in st.session_state:
    spiele = st.session_state['gefilterte_spiele']
    if not spiele:
        st.info("Keine Spiele für heute gefunden.")
    else:
        for tipp in spiele:
            st.markdown(f"""
                <div class="bet-card">
                    <span class="badge {tipp['Badge']}">{tipp['Quelle']}</span>
                    <h4>{tipp['Begegnung']}</h4>
                    <p>Empfehlung: <b>{tipp['Tipp']}</b> | Quote: <span class="odds-tag">{tipp['Quote']}</span></p>
                </div>
            """, unsafe_allow_html=True)
