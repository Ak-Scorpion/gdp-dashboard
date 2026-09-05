import streamlit as st
import math
import pandas as pd
from datetime import datetime, timezone, timedelta

# Deutsche Zeitzone
try:
    from zoneinfo import ZoneInfo
    tz_de = ZoneInfo("Europe/Berlin")
except ImportError:
    tz_de = timezone(timedelta(hours=2))

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="Elite Value Engine Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE ---
if 'custom_matches' not in st.session_state:
    st.session_state['custom_matches'] = []

# --- TEAM-RATINGS & LIGEN ---
TEAM_RATINGS = {
    "bayern münchen": 96, "borussia dortmund": 87, "bayer leverkusen": 91,
    "rb leipzig": 86, "vfb stuttgart": 83, "eintracht frankfurt": 82,
    "manchester city": 95, "arsenal": 92, "liverpool": 93, "chelsea": 85,
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86,
    "inter mailand": 91, "juventus": 86, "ac milan": 86, "napoli": 86,
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
    p_btts = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7))

    margin = 1.045
    return {
        "1": {"prob": round(p_home*100, 1), "quote": round((1.0/max(0.001, p_home))/margin, 2)},
        "X": {"prob": round(p_draw*100, 1), "quote": round((1.0/max(0.001, p_draw))/margin, 2)},
        "2": {"prob": round(p_away*100, 1), "quote": round((1.0/max(0.001, p_away))/margin, 2)},
        "Over25": {"prob": round(p_over25*100, 1), "quote": round((1.0/max(0.001, p_over25))/margin, 2)},
        "BTTS": {"prob": round(p_btts*100, 1), "quote": round((1.0/max(0.001, p_btts))/margin, 2)}
    }

# --- UI DESIGN ---
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
        <span style="color: #38bdf8; font-weight: 700; font-size: 0.75rem; letter-spacing: 2px;">ELITE VALUE ENGINE PRO</span>
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800; margin: 6px 0;">⚽ Wett-Prognosen & Quoten</h1>
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Multi-Ligen Filter, ML-Modell & Oddspedia Quotenvergleich</p>
    </div>
""", unsafe_allow_html=True)

# --- SIDEBAR / EINSTELLUNGEN ---
with st.sidebar:
    st.subheader("⚙️ Konfiguration")
    bankroll = st.number_input("Bankroll (€):", value=58.0)
    stake = st.number_input("Fester Einsatz (€):", value=5.0)
    
    st.markdown("---")
    st.markdown("#### 🏆 Ligen-Filter")
    selected_leagues = []
    for league in LEAGUE_BASE.keys():
        if st.checkbox(league, value=True, key=f"chk_{league}"):
            selected_leagues.append(league)
            
    st.markdown("---")
    bet_mode = st.radio("🎯 Wettsystem:", ["📊 Reine Einzelwetten", "🎯 Standard Kombiwette"])

# --- HAUPTBEREICH: SPIEL-EINGABE ---
with st.expander("➕ Partie hinzufügen (Flexibel & Aktuell)", expanded=True):
    with st.form("match_add_form"):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            f_liga = st.selectbox("Liga:", list(LEAGUE_BASE.keys()))
        with col_f2:
            f_home = st.text_input("Heimteam:")
        with col_f3:
            f_away = st.text_input("Auswärtsteam:")
            
        submitted = st.form_submit_button("Analysieren & Hinzufügen", use_container_width=True)
        if submitted and f_home and f_away:
            st.session_state['custom_matches'].append({"liga": f_liga, "home": f_home, "away": f_away})
            st.success(f"{f_home} vs {f_away} erfolgreich hinzugefügt!")

# --- ANALYSE & ANZEIGE ---
matches = [m for m in st.session_state['custom_matches'] if m['liga'] in selected_leagues]

if not matches:
    st.info("ℹ️ Füge oben eine Partie hinzu und wähle die entsprechenden Ligen in der Sidebar aus.")
else:
    if bet_mode == "📊 Reine Einzelwetten":
        cols = st.columns(2)
        for idx, m in enumerate(matches):
            xg_h, xg_a = calculate_xg(m['home'], m['away'], m['liga'])
            mkt = build_markets(xg_h, xg_a)
            
            with cols[idx % 2]:
                with st.container(border=True):
                    st.caption(f"🏆 {m['liga']} | xG: {xg_h} : {xg_a}")
                    st.markdown(f"#### {m['home']} vs {m['away']}")
                    st.metric("Sieg Heim (1)", f"Quote: {mkt['1']['quote']}", f"Wahrsch: {mkt['1']['prob']}%")
                    st.markdown(f"Über 2.5: `{mkt['Over25']['quote']}` | BTTS: `{mkt['BTTS']['quote']}`")
                    st.link_button("🔗 Auf Oddspedia vergleichen", "https://oddspedia.com/de", use_container_width=True)
    else:
        total_q = 1.0
        st.info(f"💡 Kombiwette aus {len(matches)} ausgewählten Partien:")
        for m in matches:
            xg_h, xg_a = calculate_xg(m['home'], m['away'], m['liga'])
            mkt = build_markets(xg_h, xg_a)
            total_q *= mkt['1']['quote']
            
            with st.container(border=True):
                st.caption(f"🏆 {m['liga']}")
                st.markdown(f"**{m['home']} vs {m['away']}** ➔ Sieg Heim (1) @ `{mkt['1']['quote']}`")
                st.link_button("🔗 Auf Oddspedia vergleichen", "https://oddspedia.com/de", use_container_width=True)
                
        st.metric("📊 GESAMTQUOTE", value=f"{round(total_q, 2)}")
        st.write(f"Möglicher Gewinn ({stake} € Einsatz): **{round(stake * total_q, 2)} €**")

if st.button("🗑️ Alle Partien zurücksetzen", use_container_width=True):
    st.session_state['custom_matches'] = []
    st.rerun()
