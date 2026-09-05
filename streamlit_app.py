import streamlit as st
import requests
from datetime import datetime, timezone, timedelta

# Zeitzone (Berlin)
try:
    from zoneinfo import ZoneInfo
    tz_de = ZoneInfo("Europe/Berlin")
except ImportError:
    tz_de = timezone(timedelta(hours=2))

st.set_page_config(
    page_title="Elite Value Engine — Schritt 1",
    page_icon="⚽",
    layout="wide"
)

# API-Key Pool mit automatischer Rotation
API_KEYS = [
    "f0dc02ac1e10f8e6c0e607698964b5a6",
    "1aa566d1bdb18c77b5c1210904adf5d5",
    "25d237353cf0c5920d358d1e79f9450c",
    "0339fb12fa7a92411c4fe5ca32d3755c",
    "5d317d36dab0f21697792fe154902716",
    "e36dbfffe1a22ab682e2759aea044180",
    "e66bcb054c6ace9de606da63612c8f4c",
    "796a27287d73f08d0257cc838ebb6cd9",
    "a5e0323a0a14698cdeec004e3b9b18c"
]

if 'api_key_idx' not in st.session_state:
    st.session_state['api_key_idx'] = 0

st.markdown("""
    <style>
    .stApp { background-color: #030712; color: #f3f4f6; }
    .header-box { background: #0f172a; border: 1px solid #312e81; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header-box">
        <h2 style="color: #fff; margin: 0;">Schritt 1: Automatischer Live-Datenabruf</h2>
        <p style="color: #94a3b8; margin: 5px 0 0 0;">Intelligente Key-Rotation für The Odds API (Aktuelle Spiele & Quoten)</p>
    </div>
""", unsafe_allow_html=True)

# Ligen-Auswahl
with st.sidebar:
    st.subheader("⚙️ Wettbewerb wählen")
    sport_key = st.selectbox(
        "Liga:",
        [
            ("soccer_germany_bundesliga", "🇩🇪 1. Bundesliga"),
            ("soccer_epl", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League"),
            ("soccer_spain_la_liga", "🇪🇸 La Liga"),
            ("soccer_italy_serie_a", "🇮🇹 Serie A"),
            ("soccer_uefa_champs_league", "🏆 Champions League")
        ],
        format_func=lambda x: x[1]
    )[0]
    st.caption(f"Aktiver API-Key Index: {st.session_state['api_key_idx'] + 1} / {len(API_KEYS)}")

# Robuste Abfrage mit automatischer Key-Umschaltung
@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_schedule(sport, keys):
    for idx in range(len(keys)):
        current_idx = (st.session_state['api_key_idx'] + idx) % len(keys)
        key = keys[current_idx]
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        params = {
            "apiKey": key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                st.session_state['api_key_idx'] = current_idx
                return response.json(), None
            elif response.status_code in [401, 429]:
                continue
            else:
                return None, f"API Fehler {response.status_code}: {response.text}"
        except Exception as e:
            return None, f"Netzwerkfehler: {str(e)}"
            
    return None, "Alle API-Keys sind erschöpft oder ungültig."

with st.spinner("Lade aktuelle Live-Spiele und Quoten..."):
    data, error = fetch_live_schedule(sport_key, API_KEYS)
    
    if error:
        st.error(error)
    elif not data:
        st.info("Aktuell keine anstehenden Spiele in dieser Liga verfügbar.")
    else:
        st.success(f"✅ {len(data)} aktuelle Partien erfolgreich geladen.")
        
        cols = st.columns(2)
        for i, match in enumerate(data):
            home = match['home_team']
            away = match['away_team']
            commence = datetime.fromisoformat(match['commence_time'].replace('Z', '+00:00')).astimezone(tz_de).strftime("%d.%m.%Y - %H:%M Uhr")
            
            bookmakers = match.get('bookmakers', [])
            tipico = next((b for b in bookmakers if 'tipico' in b['key'].lower()), bookmakers[0] if bookmakers else None)
            
            with cols[i % 2]:
                with st.container(border=True):
                    st.caption(f"📅 Anstoß: {commence} | Anbieter: {tipico['title'] if tipico else 'Keine Quoten'}")
                    st.markdown(f"### {home} vs {away}")
                    
                    if tipico and tipico.get('markets'):
                        outcomes = tipico['markets'][0]['outcomes']
                        q1 = next((o['price'] for o in outcomes if o['name'] == home), "-")
                        qx = next((o['price'] for o in outcomes if o['name'] == 'Draw'), "-")
                        q2 = next((o['price'] for o in outcomes if o['name'] == away), "-")
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("1 (Heim)", f"{q1}")
                        c2.metric("X (Unentschieden)", f"{qx}")
                        c3.metric("2 (Auswärts)", f"{q2}")
                    else:
                        st.info("Noch keine Quoten verfügbar.")

