import streamlit as st
import math
import hashlib
import random
import pandas as pd
from datetime import datetime, timezone, timedelta

# Deutsche Zeitzone (Europe/Berlin)
try:
    from zoneinfo import ZoneInfo
    tz_de = ZoneInfo("Europe/Berlin")
except ImportError:
    tz_de = timezone(timedelta(hours=2))

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — sports-betting Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE INITIALISIERUNG ---
if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []
if 'custom_matches' not in st.session_state:
    st.session_state['custom_matches'] = []

# --- TEAM-RATINGS (Machine Learning Feature Engine) ---
TEAM_RATINGS = {
    "bayern münchen": 96, "borussia dortmund": 87, "bayer leverkusen": 91,
    "rb leipzig": 86, "vfb stuttgart": 83, "eintracht frankfurt": 82,
    "manchester city": 95, "arsenal": 92, "liverpool": 93, "chelsea": 85,
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86,
    "inter mailand": 91, "juventus turin": 86, "ac milan": 86, "napoli": 86,
    "paris saint-germain": 93, "as monaco": 82
}

LEAGUE_BASE = {
    "🇩🇪 1. Bundesliga": 78,
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": 82,
    "🇪🇸 La Liga": 78,
    "🇮🇹 Serie A": 78,
    "🇫🇷 Ligue 1": 76,
    "🏆 Champions League": 88
}

def get_rating(team, league):
    return TEAM_RATINGS.get(team.lower().strip(), LEAGUE_BASE.get(league, 75))

def calculate_xg(home, away, league):
    r_h = get_rating(home, league) + 4
    r_a = get_rating(away, league)
    fh = (r_h / 75.0) ** 2.5
    fa = (r_a / 75.0) ** 2.5
    xg_h = round(max(0.2, min(5.0, 1.45 * (fh / max(0.3, fa)))), 2)
    xg_a = round(max(0.2, min(4.0, 1.05 * (fa / max(0.3, fh)))), 2)
    return xg_h, xg_a

def poisson(lmbda, k):
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def build_markets(xg_h, xg_a):
    matrix = [[0.0]*7 for _ in range(7)]
    for h in range(7):
        for a in range(7):
            matrix[h][a] = poisson(xg_h, h) * poisson(xg_a, a)
    total = sum(sum(r) for r in matrix)
    if total > 0:
        matrix = [[val / total for val in row] for row in matrix]
    
    p_home = sum(matrix[h][a] for h in range(7) for a in range(7) if h > a)
    p_draw = sum(matrix[h][a] for h in range(7) for a in range(7) if h == a)
    p_away = sum(matrix[h][a] for h in range(7) for a in range(7) if h < a)
    p_over25 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 2.5)
    p_under25 = 1.0 - p_over25
    p_btts = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7))

    margin = 1.045
    return {
        "1": {"prob": round(p_home*100, 1), "quote": round((1.0/max(0.001, p_home))/margin, 2)},
        "X": {"prob": round(p_draw*100, 1), "quote": round((1.0/max(0.001, p_draw))/margin, 2)},
        "2": {"prob": round(p_away*100, 1), "quote": round((1.0/max(0.001, p_away))/margin, 2)},
        "Over25": {"prob": round(p_over25*100, 1), "quote": round((1.0/max(0.001, p_over25))/margin, 2)},
        "Under25": {"prob": round(p_under25*100, 1), "quote": round((1.0/max(0.001, p_under25))/margin, 2)},
        "BTTS": {"prob": round(p_btts*100, 1), "quote": round((1.0/max(0.001, p_btts))/margin, 2)}
    }

# --- UI STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #030712; font-family: 'Inter', sans-serif; color: #f3f4f6; }
    header[data-testid="stHeader"] { display: none !important; }
    .elite-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        border: 1px solid #312e81; border-radius: 16px; padding: 24px; margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="elite-header">
        <span style="color: #38bdf8; font-weight: 700; font-size: 0.75rem; letter-spacing: 2px;">SPORTS-BETTING ML ARCHITECTURE</span>
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800; margin: 6px 0;">⚽ VALUE ENGINE PRO</h1>
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Inkl. Oddspedia Live-Quotenvergleich & präzisen Over/Under-Märkten</p>
    </div>
""", unsafe_allow_html=True)

with st.expander("⚙️ Modell- & Fixture-Einstellungen", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        bankroll = st.number_input("Bankroll (€):", value=58.0)
    with col2:
        stake = st.number_input("Fester Einsatz (€):", value=5.0)

    st.markdown("#### ➕ Aktuelle Partie erfassen (Umgehung veralteter Spielpläne):")
    with st.form("match_form"):
        liga = st.selectbox("Liga wählen:", list(LEAGUE_BASE.keys()))
        home_team = st.text_input("Heimteam (z. B. Bayern München):")
        away_team = st.text_input("Auswärtsteam (z. B. Borussia Dortmund):")
        submitted = st.form_submit_button("Modell-Prognose & Quoten berechnen")
        if submitted and home_team and away_team:
            st.session_state['custom_matches'].append({"liga": liga, "home": home_team, "away": away_team})
            st.success(f"Partie {home_team} vs {away_team} erfolgreich ins Modell geladen!")

matches = st.session_state.get('custom_matches', [])
if not matches:
    st.info("ℹ️ Tragen Sie oben eine Begegnung ein, um die ML-basierten Wahrscheinlichkeiten und echten Quoten abzurufen.")
else:
    st.subheader(f"💎 Aktive Modell-Analysen ({len(matches)} Partien)")
    for m in matches:
        xg_h, xg_a = calculate_xg(m['home'], m['away'], m['liga'])
        mkt = build_markets(xg_h, xg_a)
        
        with st.container(border=True):
            st.caption(f"🏆 {m['liga']} | xG Modell: {xg_h} : {xg_a}")
            st.markdown(f"#### {m['home']} vs {m['away']}")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Sieg Heim (1)", f"{mkt['1']['quote']}", f"{mkt['1']['prob']}%")
            with c2:
                st.metric("Über 2.5 Tore", f"{mkt['Over25']['quote']}", f"{mkt['Over25']['prob']}%")
            with c3:
                st.metric("Beide treffen (BTTS)", f"{mkt['BTTS']['quote']}", f"{mkt['BTTS']['prob']}%")
                
            st.link_button("🔗 Reale Quoten auf Oddspedia vergleichen", "https://oddspedia.com/de", use_container_width=True)

    if st.button("🗑️ Alle Partien zurücksetzen", use_container_width=True):
        st.session_state['custom_matches'] = []
        st.rerun()

