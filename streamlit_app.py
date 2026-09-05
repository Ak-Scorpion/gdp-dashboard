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

# --- TEAM-RATINGS (Machine Learning Feature Engine) ---
TEAM_RATINGS = {
    "bayern münchen": 96, "borussia dortmund": 87, "bayer leverkusen": 91,
    "rb leipzig": 86, "vfb stuttgart": 83, "eintracht frankfurt": 82,
    "manchester city": 95, "arsenal": 92, "liverpool": 93, "chelsea": 85,
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86,
    "inter mailand": 91, "juventus turin": 86, "ac milan": 86, "napoli": 86,
    "paris saint-germain": 93, "as monaco": 82, "as rom": 82, "fc porto": 80
}

LEAGUE_BASE = {
    "🇩🇪 1. Bundesliga": 78,
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": 82,
    "🇪🇸 La Liga": 78,
    "🇮🇹 Serie A": 78,
    "🇫🇷 Ligue 1": 76,
    "🏆 Champions League": 88,
    "🇪🇺 Europa League": 77,
    "🇪🇺 Conference League": 73
}

# Automatisierter Spielpool für alle Ligen
MASTER_MATCH_POOL = [
    {"liga": "🇩🇪 1. Bundesliga", "home": "Bayern München", "away": "Borussia Dortmund"},
    {"liga": "🇩🇪 1. Bundesliga", "home": "Bayer Leverkusen", "away": "RB Leipzig"},
    {"liga": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "home": "Manchester City", "away": "Arsenal"},
    {"liga": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "home": "Liverpool", "away": "Chelsea"},
    {"liga": "🇪🇸 La Liga", "home": "Real Madrid", "away": "Barcelona"},
    {"liga": "🇪🇸 La Liga", "home": "Atletico Madrid", "away": "Real Sociedad"},
    {"liga": "🇮🇹 Serie A", "home": "Inter Mailand", "away": "Juventus Turin"},
    {"liga": "🇮🇹 Serie A", "home": "AC Milan", "away": "Napoli"},
    {"liga": "🇫🇷 Ligue 1", "home": "Paris Saint-Germain", "away": "AS Monaco"},
    {"liga": "🏆 Champions League", "home": "Real Madrid", "away": "Manchester City"},
    {"liga": "🏆 Champions League", "home": "Bayern München", "away": "Paris Saint-Germain"},
    {"liga": "🇪🇺 Europa League", "home": "AS Rom", "away": "FC Porto"},
    {"liga": "🇪🇺 Conference League", "home": "Fiorentina", "away": "Real Betis"}
]

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
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Automatisierter Ligen-Filter & Oddspedia Quotenvergleich</p>
    </div>
""", unsafe_allow_html=True)

with st.expander("⚙️ Einstellungen & Ligen-Auswahl", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        bankroll = st.number_input("Bankroll (€):", value=58.0)
    with col2:
        stake = st.number_input("Fester Einsatz (€):", value=5.0)

    st.markdown("---")
    st.markdown("#### 🏆 Ligen-Auswahl (Checkbox-System):")
    selected_leagues = []
    
    c_l1, c_l2 = st.columns(2)
    with c_l1:
        if st.checkbox("🇩🇪 1. Bundesliga", value=True): selected_leagues.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True): selected_leagues.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🇪🇸 La Liga", value=True): selected_leagues.append("🇪🇸 La Liga")
        if st.checkbox("🇮🇹 Serie A", value=True): selected_leagues.append("🇮🇹 Serie A")
    with c_l2:
        if st.checkbox("🇫🇷 Ligue 1", value=True): selected_leagues.append("🇫🇷 Ligue 1")
        if st.checkbox("🏆 Champions League", value=True): selected_leagues.append("🏆 Champions League")
        if st.checkbox("🇪🇺 Europa League", value=True): selected_leagues.append("🇪🇺 Europa League")
        if st.checkbox("🇪🇺 Conference League", value=True): selected_leagues.append("🇪🇺 Conference League")

    st.markdown("---")
    bet_mode = st.radio("🎯 Wettsystem auswählen:", ["📊 Reine Einzelwetten", "🎯 Standard Kombiwette"])

# Filtere Partien basierend auf den ausgewählten Ligen
active_matches = [m for m in MASTER_MATCH_POOL if m['liga'] in selected_leagues]

if not active_matches:
    st.warning("⚠️ Bitte wähle mindestens eine Liga in den Einstellungen aus.")
else:
    st.subheader(f"💎 Analysierte Top-Partien ({len(active_matches)} Spiele)")
    
    if bet_mode == "📊 Reine Einzelwetten":
        cols = st.columns(2)
        for idx, m in enumerate(active_matches):
            xg_h, xg_a = calculate_xg(m['home'], m['away'], m['liga'])
            mkt = build_markets(xg_h, xg_a)
            
            with cols[idx % 2]:
                with st.container(border=True):
                    st.caption(f"🏆 {m['liga']} | xG: {xg_h} : {xg_a}")
                    st.markdown(f"#### {m['home']} vs {m['away']}")
                    st.metric("Top-Tipp: Sieg Heim (1)", f"Quote: {mkt['1']['quote']}", f"Wahrsch: {mkt['1']['prob']}%")
                    st.link_button("🔗 Reale Quoten auf Oddspedia prüfen", "https://oddspedia.com/de", use_container_width=True)
    else:
        # Kombiwette Modus
        total_kombi_q = 1.0
        kombi_picks = active_matches[:3] # Max 3 für Kombi
        
        st.info(f"💡 Kombiwette aus {len(kombi_picks)} ausgewählten Top-Spielen zusammengestellt.")
        for m in kombi_picks:
            xg_h, xg_a = calculate_xg(m['home'], m['away'], m['liga'])
            mkt = build_markets(xg_h, xg_a)
            total_kombi_q *= mkt['1']['quote']
            
            with st.container(border=True):
                st.caption(f"🏆 {m['liga']}")
                st.markdown(f"**{m['home']} vs {m['away']}** ➔ Sieg Heim (1) @ `{mkt['1']['quote']}`")
                st.link_button("🔗 Auf Oddspedia vergleichen", "https://oddspedia.com/de", use_container_width=True)
                
        st.metric(label="📊 GESAMTQUOTE DER KOMBI", value=f"{round(total_kombi_q, 2)}")
        st.write(f"Möglicher Gewinn bei {stake}€ Einsatz: **{round(stake * total_kombi_q, 2)} €**")

