import streamlit as st
import math
import hashlib
import random
import pandas as pd
from datetime import datetime, timedelta, timezone

# Deutsche Zeitzone (Europe/Berlin)
try:
    from zoneinfo import ZoneInfo
    tz_de = ZoneInfo("Europe/Berlin")
except ImportError:
    tz_de = timezone(timedelta(hours=2))

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Elite Pro Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- AUTO-RELOAD ALLE 20 MINUTEN ---
st.markdown('<meta http-equiv="refresh" content="1200">', unsafe_allow_html=True)

# --- SESSION STATE INITIALISIERUNG ---
if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []
if 'custom_matches' not in st.session_state:
    st.session_state['custom_matches'] = []
if 'reroll_key' not in st.session_state:
    st.session_state['reroll_key'] = 0

# --- UMFASSENDE TEAM-RATINGS FÜR ALLE LIGEN & VEREINE ---
TEAM_RATINGS = {
    "bayern": 96, "bayern münchen": 96, "fc bayern münchen": 96,
    "dortmund": 87, "borussia dortmund": 87,
    "leverkusen": 91, "bayer leverkusen": 91,
    "leipzig": 86, "rb leipzig": 86,
    "stuttgart": 83, "vfb stuttgart": 83,
    "frankfurt": 82, "eintracht frankfurt": 82,
    "wolfsburg": 76, "vfl wolfsburg": 76,
    "gladbach": 75, "borussia mönchengladbach": 75,
    "freiburg": 78, "sc freiburg": 78,
    "union berlin": 75, "1. fc union berlin": 75,
    "mainz": 74, "1. fsv mainz 05": 74,
    "augsburg": 73, "fc augsburg": 73,
    "werder bremen": 75, "sv werder bremen": 75,
    "hoffenheim": 76, "tsg hoffenheim": 76,
    "heidenheim": 73, "fc heidenheim": 73,
    "st. pauli": 70, "fc st. pauli": 70,
    "bochum": 68, "vfl bochum": 68,
    "kiel": 67, "holstein kiel": 67,
    "schalke": 69, "schalke 04": 69, "fc schalke 04": 69,
    "hsv": 72, "hamburger sv": 72,
    "köln": 73, "1. fc köln": 73,
    "hertha": 71, "hertha bsc": 71,
    "düsseldorf": 71, "fortuna düsseldorf": 71,
    "hannover": 71, "hannover 96": 71,
    "manchester city": 95, "arsenal": 92, "liverpool": 93,
    "chelsea": 85, "manchester united": 83, "tottenham": 83,
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86,
    "inter": 91, "juventus": 86, "ac milan": 86, "napoli": 86,
    "paris saint-germain": 93, "psg": 93, "monaco": 82, "marseille": 82
}

LEAGUE_BASE_RATINGS = {
    "🇩🇪 1. Bundesliga": 78,
    "🇩🇪 2. Bundesliga": 71,
    "🇩🇪 3. Liga": 65,
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": 82,
    "🇪🇸 La Liga": 78,
    "🇮🇹 Serie A": 78,
    "🇫🇷 Ligue 1": 76,
    "🏆 Champions League": 88
}

def get_team_rating(team_name, league_name="🇩🇪 1. Bundesliga"):
    name_clean = team_name.lower().strip()
    for key, rating in TEAM_RATINGS.items():
        if key in name_clean:
            return rating
    return LEAGUE_BASE_RATINGS.get(league_name, 75)

def calculate_dynamic_xg(home_team, away_team, league_name):
    r_home = get_team_rating(home_team, league_name) + 4
    r_away = get_team_rating(home_team, league_name)
    
    factor_home = (r_home / 75.0) ** 2.5
    factor_away = (r_away / 75.0) ** 2.5
    
    xg_home = round(max(0.2, min(5.0, 1.45 * (factor_home / max(0.3, factor_away)))), 2)
    xg_away = round(max(0.2, min(4.0, 1.05 * (factor_away / max(0.3, factor_home)))), 2)
    return xg_home, xg_away

def get_team_form(team_name):
    seed = int(hashlib.md5(team_name.encode()).hexdigest(), 16)
    forms = [["W", "W", "D", "W", "L"], ["W", "D", "W", "W", "W"], ["L", "D", "W", "L", "W"]]
    return forms[seed % len(forms)]

def render_form_badges(form_list):
    html = "<div style='display: flex; gap: 4px; margin-top: 4px;'>"
    for res in form_list:
        if res == "W":
            html += "<span style='background-color: #059669; color: white; width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; font-size: 0.65rem; font-weight: bold;'>S</span>"
        elif res == "D":
            html += "<span style='background-color: #d97706; color: white; width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; font-size: 0.65rem; font-weight: bold;'>U</span>"
        else:
            html += "<span style='background-color: #dc2626; color: white; width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; font-size: 0.65rem; font-weight: bold;'>N</span>"
    html += "</div>"
    return html

def poisson_pmf(lmbda, k):
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def dixon_coles_tau(h, a, home_xg, away_xg, rho=-0.13):
    if h == 0 and a == 0: return max(0.2, 1.0 - (home_xg * away_xg * rho))
    elif h == 0 and a == 1: return max(0.2, 1.0 + (home_xg * rho))
    elif h == 1 and a == 0: return max(0.2, 1.0 + (away_xg * rho))
    elif h == 1 and a == 1: return max(0.2, 1.0 - rho)
    return 1.0

def build_markets(home_xg, away_xg):
    matrix = [[0.0 for _ in range(7)] for _ in range(7)]
    for h in range(7):
        for a in range(7):
            tau = dixon_coles_tau(h, a, home_xg, away_xg)
            matrix[h][a] = poisson_pmf(home_xg, h) * poisson_pmf(away_xg, a) * tau
            
    total_p = sum(sum(row) for row in matrix)
    if total_p > 0:
        matrix = [[matrix[h][a] / total_p for a in range(7)] for h in range(7)]

    p_home = sum(matrix[h][a] for h in range(7) for a in range(7) if h > a)
    p_draw = sum(matrix[h][a] for h in range(7) for a in range(7) if h == a)
    p_away = sum(matrix[h][a] for h in range(7) for a in range(7) if h < a)
    
    p_dc_1x = p_home + p_draw
    p_dc_x2 = p_away + p_draw
    
    p_over15 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 1.5)
    p_over25 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 2.5)
    p_under25 = 1.0 - p_over25
    p_btts_ja = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7))

    margin = 1.045
    return {
        "1X2": {
            "1": {"prob": round(p_home * 100, 1), "base_q": round((1.0 / max(0.001, p_home)) / margin, 2)},
            "X": {"prob": round(p_draw * 100, 1), "base_q": round((1.0 / max(0.001, p_draw)) / margin, 2)},
            "2": {"prob": round(p_away * 100, 1), "base_q": round((1.0 / max(0.001, p_away)) / margin, 2)}
        },
        "DC": {
            "1X": {"prob": round(p_dc_1x * 100, 1), "base_q": round((1.0 / max(0.001, p_dc_1x)) / margin, 2)},
            "X2": {"prob": round(p_dc_x2 * 100, 1), "base_q": round((1.0 / max(0.001, p_dc_x2)) / margin, 2)}
        },
        "Tore": {
            "Über 1.5": {"prob": round(p_over15 * 100, 1), "base_q": round((1.0 / max(0.001, p_over15)) / margin, 2)},
            "Über 2.5": {"prob": round(p_over25 * 100, 1), "base_q": round((1.0 / max(0.001, p_over25)) / margin, 2)},
            "Unter 2.5": {"prob": round(p_under25 * 100, 1), "base_q": round((1.0 / max(0.001, p_under25)) / margin, 2)}
        },
        "BTTS": {
            "Ja": {"prob": round(p_btts_ja * 100, 1), "base_q": round((1.0 / max(0.001, p_btts_ja)) / margin, 2)}
        }
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
    .badge-elite-ev { background: linear-gradient(135deg, #059669 0%, #10b981 100%); color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 0.75rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="elite-header">
        <span style="color: #38bdf8; font-weight: 700; font-size: 0.75rem; letter-spacing: 2px;">APP VON PASCAL GELLERS</span>
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800; margin: 6px 0;">⚽ ELITE PRO VALUE ENGINE</h1>
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Inkl. Oddspedia Quotenvergleich & echten Über/Unter 2.5 Werten • Ziel: 58€ ➔ 100€</p>
    </div>
""", unsafe_allow_html=True)

with st.expander("⚙️ Einstellungen & Spiel-Eingabe", expanded=True):
    col_bank1, col_bank2 = st.columns(2)
    with col_bank1:
        total_bankroll = st.number_input("💰 Gesamt-Bankroll (€):", min_value=1.0, value=58.0, step=1.0)
    with col_bank2:
        fixed_stake_mode = st.checkbox("Fester 5€ Einsatz pro Wette", value=True)

    st.markdown("---")
    st.markdown("#### ✍️ Spiel für Analyse hinzufügen:")
    with st.form("custom_match_form"):
        c_liga = st.selectbox("Liga wählen:", list(LEAGUE_BASE_RATINGS.keys()))
        c_home = st.text_input("Heimmannschaft (z.B. FC Bayern München):")
        c_away = st.text_input("Auswärtsmannschaft (z.B. Borussia Dortmund):")
        submitted = st.form_submit_button("➕ Spiel hinzufügen & Quoten berechnen")
        if submitted and c_home and c_away:
            st.session_state['custom_matches'].append({"liga": c_liga, "home": c_home, "away": c_away})
            st.success(f"✅ {c_home} vs {c_away} hinzugefügt!")

    st.markdown("---")
    gen_typ = st.selectbox("🎯 Wählen Sie Ihr Wettsystem:", ["📊 Reine Einzelwetten", "🎯 Standard Kombiwette"])
    risiko_profil = st.selectbox("🧠 KI-Risiko-Modus:", ["🟢 Safe Mode (bis 1.50)", "⚖️ Mittleres Risiko (1.50 - 2.10)", "🔥 Hohes Risiko (2.10+)"], index=1)

matches = st.session_state.get('custom_matches', [])

if not matches:
    st.info("ℹ️ Füge oben ein Spiel hinzu, um die berechneten Quoten (inkl. Über/Unter 2.5) anzuzeigen.")
else:
    st.subheader(f"💎 Analysen & Oddspedia Quoten-Check ({len(matches)} Partien)")
    
    def get_best_pick(match, profile):
        xg_h, xg_a = calculate_dynamic_xg(match['home'], match['away'], match['liga'])
        mkts = build_markets(xg_h, xg_a)
        
        raw = [
            {"tipp": f"Sieg {match['home']} (1)", "prob": mkts['1X2']['1']['prob'], "base_q": mkts['1X2']['1']['base_q'], "markt": "1X2"},
            {"tipp": f"Sieg {match['away']} (2)", "prob": mkts['1X2']['2']['prob'], "base_q": mkts['1X2']['2']['base_q'], "markt": "1X2"},
            {"tipp": "Über 2.5 Tore", "prob": mkts['Tore']['Über 2.5']['prob'], "base_q": mkts['Tore']['Über 2.5']['base_q'], "markt": "Tore"},
            {"tipp": "Unter 2.5 Tore", "prob": mkts['Tore']['Unter 2.5']['prob'], "base_q": mkts['Tore']['Unter 2.5']['base_q'], "markt": "Tore"},
            {"tipp": "Beide Teams treffen - Ja", "prob": mkts['BTTS']['Ja']['prob'], "base_q": mkts['BTTS']['Ja']['base_q'], "markt": "BTTS"}
        ]
        
        # Filter nach Risiko-Profil
        if "Safe Mode" in profile:
            valid = [c for c in raw if c['base_q'] < 1.50]
        elif "Hohes Risiko" in profile:
            valid = [c for c in raw if c['base_q'] > 2.10]
        else:
            valid = [c for c in raw if 1.50 <= c['base_q'] <= 2.10]
            
        if not valid:
            valid = raw
            
        selected = valid[0]
        selected['quote'] = selected['base_q']
        selected['stake'] = 5.0 if fixed_stake_mode else round(total_bankroll * 0.02, 2)
        selected['ev'] = round((((selected['prob'] / 100.0) * selected['quote']) - 1.0) * 100.0, 1)
        return selected

    cols = st.columns(2)
    current_picks = []
    for idx, match in enumerate(matches):
        pick = get_best_pick(match, risiko_profil)
        current_picks.append((match, pick))
        
        with cols[idx % 2]:
            with st.container(border=True):
                st.caption(f"🏆 {match['liga']}")
                st.markdown(f"#### {match['home']} vs {match['away']}")
                st.markdown(f"**Tipp:** `{pick['tipp']}` | **Modell-Quote:** `{pick['quote']}`")
                st.markdown(f"💵 Einsatz: `{pick['stake']} €` | Wahrsch.: `{pick['prob']}%`")
                st.link_button("🔗 Reale Quoten auf Oddspedia vergleichen", "https://oddspedia.com/de", use_container_width=True)

    if st.button("🗑️ Alle Spiele zurücksetzen", use_container_width=True):
        st.session_state['custom_matches'] = []
        st.rerun()
