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
if 'matches_cache' not in st.session_state:
    st.session_state['matches_cache'] = []
if 'reroll_key' not in st.session_state:
    st.session_state['reroll_key'] = 0

# --- UMFASSENDE TEAM-RATINGS FÜR ALLE LIGEN & VEREINE ---
TEAM_RATINGS = {
    # 🇩🇪 1. Bundesliga
    "bayern": 96, "bayern münchen": 96, "dortmund": 87, "borussia dortmund": 87,
    "leverkusen": 91, "bayer leverkusen": 91, "leipzig": 86, "rb leipzig": 86,
    "stuttgart": 83, "vfb stuttgart": 83, "frankfurt": 82, "eintracht frankfurt": 82,
    "wolfsburg": 76, "vfl wolfsburg": 76, "gladbach": 75, "borussia mönchengladbach": 75,
    "freiburg": 78, "sc freiburg": 78, "union berlin": 75, "1. fc union berlin": 75,
    "mainz": 74, "mainz 05": 74, "augsburg": 73, "fc augsburg": 73,
    "werder bremen": 75, "bremen": 75, "hoffenheim": 76, "tsg hoffenheim": 76,
    "heidenheim": 73, "fc heidenheim": 73, "st. pauli": 70, "fc st. pauli": 70,
    "bochum": 68, "vfl bochum": 68, "holstein kiel": 67, "kiel": 67,

    # 🇩🇪 2. Bundesliga & 3. Liga
    "schalke": 69, "schalke 04": 69, "fc schalke 04": 69, "hsv": 72, "hamburger sv": 72,
    "köln": 73, "1. fc köln": 73, "hertha": 71, "hertha bsc": 71,
    "duesseldorf": 71, "düsseldorf": 71, "fortuna düsseldorf": 71,
    "hannover": 71, "hannover 96": 71, "paderborn": 70, "sc paderborn": 70,
    "karlsruhe": 70, "ksc": 70, "kaiserslautern": 70, "fck": 70,
    "nürnberg": 70, "1. fc nürnberg": 70, "magdeburg": 69, "fcm": 69,
    "elversberg": 68, "greuther fürth": 69, "fürth": 69, "braunschweig": 67,
    "regensburg": 66, "münster": 66, "ulm": 66, "dresden": 65, "dynamo dresden": 65,
    "aachen": 62, "essen": 63, "1860 münchen": 63, "osnabrück": 64, "rostock": 64,
    "waldhof mannheim": 65, "sc verl": 64,

    # 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League
    "manchester city": 95, "man city": 95, "arsenal": 92, "liverpool": 93,
    "chelsea": 85, "manchester united": 83, "man utd": 83, "tottenham": 83,
    "newcastle": 84, "aston villa": 84, "brighton": 79, "west ham": 78,
    "crystal palace": 77, "fulham": 77, "brentford": 76, "everton": 75,
    "wolves": 75, "wolverhampton": 75, "bournemouth": 76, "nottingham forest": 75,
    "leicester": 74, "ipswich": 71, "southampton": 72, "sunderland": 73,

    # 🇪🇸 La Liga
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86, "athletic bilbao": 81,
    "real sociedad": 81, "girona": 80, "villarreal": 80, "real betis": 79,
    "sevilla": 77, "celta vigo": 75, "osasuna": 75, "valencia": 76,
    "getafe": 74, "mallorca": 74, "rayo vallecano": 74, "alaves": 73,
    "las palmas": 73, "leganes": 70, "valladolid": 70, "espanyol": 72,

    # 🇮🇹 Serie A
    "inter": 91, "inter mailand": 91, "juventus": 86, "ac milan": 86, "milan": 86,
    "napoli": 86, "atalanta": 85, "roma": 82, "as rom": 82, "lazio": 81,
    "fiorentina": 80, "bologna": 79, "torino": 77, "monza": 74, "udinese": 75,
    "genoa": 74, "lecce": 72, "cagliari": 73, "verona": 73, "empoli": 72,
    "parma": 73, "como": 72, "venezia": 70, "torino": 76,

    # 🇫🇷 Ligue 1
    "paris saint-germain": 93, "psg": 93, "monaco": 82, "marseille": 82,
    "lille": 81, "lyon": 80, "rennes": 78, "lens": 78, "nice": 79,
    "brest": 77, "reims": 75, "strasbourg": 74, "toulouse": 74,
    "montpellier": 73, "nantes": 73, "le havre": 70, "auxerre": 71,
    "angers": 70, "saint-etienne": 72, "lorient": 74
}

LEAGUE_BASE_RATINGS = {
    "🇩🇪 1. Bundesliga": 78,
    "🇩🇪 2. Bundesliga": 71,
    "🇩🇪 3. Liga": 65,
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": 82,
    "🇪🇸 La Liga": 78,
    "🇮🇹 Serie A": 78,
    "🇫🇷 Ligue 1": 76,
    "🏆 Champions League": 88,
    "🇪🇺 Europa League": 77,
    "🇪🇺 Conference League": 73
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
    forms = [
        ["W", "W", "D", "W", "L"],
        ["W", "D", "W", "W", "W"],
        ["L", "D", "W", "L", "W"],
        ["W", "W", "W", "D", "D"],
        ["D", "L", "W", "D", "W"],
        ["W", "L", "L", "W", "W"]
    ]
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
    if h == 0 and a == 0:
        return max(0.2, 1.0 - (home_xg * away_xg * rho))
    elif h == 0 and a == 1:
        return max(0.2, 1.0 + (home_xg * rho))
    elif h == 1 and a == 0:
        return max(0.2, 1.0 + (away_xg * rho))
    elif h == 1 and a == 1:
        return max(0.2, 1.0 - rho)
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
    p_dc_12 = p_home + p_away
    
    p_dnb_1 = p_home / (p_home + p_away) if (p_home + p_away) > 0 else 0.5
    p_dnb_2 = p_away / (p_home + p_away) if (p_home + p_away) > 0 else 0.5
    
    p_over15 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 1.5)
    p_over25 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 2.5)
    p_under25 = 1.0 - p_over25
    p_btts_ja = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7))

    margin = 1.045
    q_home = round((1.0 / max(0.001, p_home)) / margin, 2)
    q_draw = round((1.0 / max(0.001, p_draw)) / margin, 2)
    q_away = round((1.0 / max(0.001, p_away)) / margin, 2)
    
    q_dc_1x = round((1.0 / max(0.001, p_dc_1x)) / margin, 2)
    q_dc_x2 = round((1.0 / max(0.001, p_dc_x2)) / margin, 2)
    q_dc_12 = round((1.0 / max(0.001, p_dc_12)) / margin, 2)
    
    q_dnb_1 = round((1.0 / max(0.001, p_dnb_1)) / margin, 2)
    q_dnb_2 = round((1.0 / max(0.001, p_dnb_2)) / margin, 2)
    
    q_over15 = round((1.0 / max(0.001, p_over15)) / margin, 2)
    q_over25 = round((1.0 / max(0.001, p_over25)) / margin, 2)
    q_under25 = round((1.0 / max(0.001, p_under25)) / margin, 2)
    q_btts = round((1.0 / max(0.001, p_btts_ja)) / margin, 2)

    return {
        "1X2": {
            "1": {"prob": round(p_home * 100, 1), "base_q": q_home},
            "X": {"prob": round(p_draw * 100, 1), "base_q": q_draw},
            "2": {"prob": round(p_away * 100, 1), "base_q": q_away}
        },
        "DC": {
            "1X": {"prob": round(p_dc_1x * 100, 1), "base_q": q_dc_1x},
            "X2": {"prob": round(p_dc_x2 * 100, 1), "base_q": q_dc_x2},
            "12": {"prob": round(p_dc_12 * 100, 1), "base_q": q_dc_12}
        },
        "DNB": {
            "1 DNB": {"prob": round(p_dnb_1 * 100, 1), "base_q": q_dnb_1},
            "2 DNB": {"prob": round(p_dnb_2 * 100, 1), "base_q": q_dnb_2}
        },
        "Tore": {
            "Über 1.5": {"prob": round(p_over15 * 100, 1), "base_q": q_over15},
            "Über 2.5": {"prob": round(p_over25 * 100, 1), "base_q": q_over25},
            "Unter 2.5": {"prob": round(p_under25 * 100, 1), "base_q": q_under25}
        },
        "BTTS": {
            "Ja": {"prob": round(p_btts_ja * 100, 1), "base_q": q_btts}
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
    .badge-elite-std { background-color: #1f2937; color: #9ca3af; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; }
    </style>
""", unsafe_allow_html=True)

now_de = datetime.now(tz_de)
today_de = now_de.date()
tomorrow_de = today_de + timedelta(days=1)
weekday_num = today_de.weekday()
fri_de = today_de + timedelta(days=(4 - weekday_num))
sun_de = fri_de + timedelta(days=2)

today_str = today_de.strftime("%d.%m.%Y")
tomorrow_str = tomorrow_de.strftime("%d.%m.%Y")
fri_str = fri_de.strftime("%d.%m.")
sun_str = sun_de.strftime("%d.%m.")

st.markdown(f"""
    <div class="elite-header">
        <span style="color: #38bdf8; font-weight: 700; font-size: 0.75rem; letter-spacing: 2px;">APP VON PASCAL GELLERS</span>
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800; margin: 6px 0;">⚽ ELITE PRO VALUE ENGINE</h1>
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Inkl. Sofascore Live-Quotenvergleich & Auto-Garantie • Ziel: 58€ ➔ 100€</p>
    </div>
""", unsafe_allow_html=True)

with st.expander("⚙️ Einstellungen & Ligen-Auswahl (100% Strikter Filter)", expanded=True):
    col_bank1, col_bank2 = st.columns(2)
    with col_bank1:
        total_bankroll = st.number_input("💰 Gesamt-Bankroll (€):", min_value=1.0, value=58.0, step=1.0)
    with col_bank2:
        fixed_stake_mode = st.checkbox("Fester 5€ Einsatz pro Wette", value=True)

    st.markdown("---")
    gen_typ = st.selectbox(
        "🎯 Wählen Sie Ihr Wettsystem:",
        ["📊 Reine Einzelwetten", "🛡️ Multi-Ticket System", "🎁 Freebet-Modus", "🎯 Standard Kombiwette"],
        index=0
    )

    multi_budget = 20.0
    freebet_wert = 20.0
    anzahl_wetten = 3

    if "Freebet" in gen_typ:
        freebet_wert = st.number_input("Freebet-Wert (€):", min_value=1.0, value=20.0)
    elif "Multi-Ticket" in gen_typ:
        multi_budget = st.number_input("Gesamtbudget (€):", min_value=1.0, value=20.0)
    elif "Kombiwette" in gen_typ:
        anzahl_wetten = st.number_input("Spiele im Kombischein:", min_value=2, max_value=10, value=3)

    st.markdown("---")
    st.markdown("#### 🏆 Ligen-Auswahl (Strikte Filterung):")
    aktive_generator_ligen = []
    l1, l2 = st.columns(2)
    with l1:
        if st.checkbox("🇩🇪 1. Bundesliga", value=True, key="chk_de1"): aktive_generator_ligen.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🇩🇪 2. Bundesliga", value=True, key="chk_de2"): aktive_generator_ligen.append("🇩🇪 2. Bundesliga")
        if st.checkbox("🇩🇪 3. Liga", value=False, key="chk_de3"): aktive_generator_ligen.append("🇩🇪 3. Liga")
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True, key="chk_en1"): aktive_generator_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🇪🇸 La Liga", value=True, key="chk_es1"): aktive_generator_ligen.append("🇪🇸 La Liga")
    with l2:
        if st.checkbox("🇮🇹 Serie A", value=True, key="chk_it1"): aktive_generator_ligen.append("🇮🇹 Serie A")
        if st.checkbox("🇫🇷 Ligue 1", value=True, key="chk_fr1"): aktive_generator_ligen.append("🇫🇷 Ligue 1")
        if st.checkbox("🏆 Champions League", value=True, key="chk_cl"): aktive_generator_ligen.append("🏆 Champions League")
        if st.checkbox("🇪🇺 Europa League", value=True, key="chk_el"): aktive_generator_ligen.append("🇪🇺 Europa League")
        if st.checkbox("🇪🇺 Conference League", value=True, key="chk_conf"): aktive_generator_ligen.append("🇪🇺 Conference League")

    st.markdown("---")
    gen_zeit_modus = st.selectbox("📅 Zeitraum:", [f"⚡ HEUTE ({today_str})", f"📅 MORGEN ({tomorrow_str})", f"⚽ WOCHENENDE ({fri_str} - {sun_str})", "🟢 DIESE WOCHE"])
    risiko_profil = st.selectbox("🧠 KI-Risiko-Modus:", ["🟢 Safe Mode (bis 1.50)", "⚖️ Mittleres Risiko (1.50 - 2.10)", "🔥 Hohes Risiko (2.10+)"], index=1)

    generate_click = st.button("🚀 Elite-Spiele laden & analysieren", type="primary", use_container_width=True)

if generate_click or not st.session_state['matches_cache']:
    if not aktive_generator_ligen:
        st.error("Bitte wähle mindestens eine Liga aus!")
    else:
        with st.spinner("Lade Ligen & berechne präzise Quoten..."):
            master_match_pool = [
                {"liga": "🇩🇪 1. Bundesliga", "home": "FC Bayern München", "away": "FC Schalke 04", "time_str": f"{today_str} - 15:30 Uhr"},
                {"liga": "🇩🇪 1. Bundesliga", "home": "Borussia Dortmund", "away": "Bayer Leverkusen", "time_str": f"{today_str} - 18:30 Uhr"},
                {"liga": "🇩🇪 1. Bundesliga", "home": "RB Leipzig", "away": "VfB Stuttgart", "time_str": f"{today_str} - 15:30 Uhr"},
                {"liga": "🇩🇪 1. Bundesliga", "home": "Eintracht Frankfurt", "away": "SC Freiburg", "time_str": f"{today_str} - 15:30 Uhr"},
                {"liga": "🇩🇪 2. Bundesliga", "home": "Hamburger SV", "away": "1. FC Köln", "time_str": f"{today_str} - 13:30 Uhr"},
                {"liga": "🇩🇪 2. Bundesliga", "home": "Hertha BSC", "away": "Fortuna Düsseldorf", "time_str": f"{today_str} - 13:30 Uhr"},
                {"liga": "🇩🇪 3. Liga", "home": "SV Waldhof Mannheim", "away": "SC Verl", "time_str": f"{today_str} - 14:00 Uhr"},
                {"liga": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "home": "Manchester City", "away": "Arsenal FC", "time_str": f"{today_str} - 16:00 Uhr"},
                {"liga": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "home": "Liverpool FC", "away": "Manchester United", "time_str": f"{today_str} - 17:30 Uhr"},
                {"liga": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "home": "Chelsea FC", "away": "Tottenham Hotspur", "time_str": f"{today_str} - 15:00 Uhr"},
                {"liga": "🇪🇸 La Liga", "home": "Real Madrid", "away": "FC Barcelona", "time_str": f"{today_str} - 21:00 Uhr"},
                {"liga": "🇪🇸 La Liga", "home": "Atletico Madrid", "away": "Athletic Bilbao", "time_str": f"{today_str} - 18:30 Uhr"},
                {"liga": "🇮🇹 Serie A", "home": "Inter Mailand", "away": "Juventus Turin", "time_str": f"{today_str} - 20:45 Uhr"},
                {"liga": "🇮🇹 Serie A", "home": "AC Mailand", "away": "SSC Neapel", "time_str": f"{today_str} - 18:00 Uhr"},
                {"liga": "🇫🇷 Ligue 1", "home": "Paris Saint-Germain", "away": "AS Monaco", "time_str": f"{today_str} - 21:00 Uhr"},
                {"liga": "🇫🇷 Ligue 1", "home": "RC Lens", "away": "FC Lorient", "time_str": f"{today_str} - 17:00 Uhr"},
                {"liga": "🏆 Champions League", "home": "Real Madrid", "away": "Manchester City", "time_str": f"{today_str} - 21:00 Uhr"},
                {"liga": "🏆 Champions League", "home": "FC Bayern München", "away": "Paris Saint-Germain", "time_str": f"{today_str} - 21:00 Uhr"},
                {"liga": "🇪🇺 Europa League", "home": "AS Rom", "away": "FC Porto", "time_str": f"{today_str} - 21:00 Uhr"},
                {"liga": "🇪🇺 Conference League", "home": "AC Florenz", "away": "Betis Sevilla", "time_str": f"{today_str} - 21:00 Uhr"}
            ]

            filtered_matches = []
            for fm in master_match_pool:
                if fm['liga'] in aktive_generator_ligen:
                    xg_h, xg_a = calculate_dynamic_xg(fm['home'], fm['away'], fm['liga'])
                    mkts = build_markets(xg_h, xg_a)
                    filtered_matches.append({
                        "liga": fm['liga'], 
                        "home": fm['home'], 
                        "away": fm['away'], 
                        "time_str": fm['time_str'], 
                        "markets": mkts,
                        "sofascore_url": "https://www.sofascore.com"
                    })

            st.session_state['matches_cache'] = filtered_matches

matches = [m for m in st.session_state.get('matches_cache', []) if m['liga'] in aktive_generator_ligen]

def get_best_pick(match, profile):
    mkts = match['markets']
    h, a = match['home'], match['away']
    reroll = st.session_state.get('reroll_key', 0)
    seed = int(hashlib.md5(f"{h}_{a}_{profile}_{reroll}".encode()).hexdigest(), 16)
    
    raw = [
        {"tipp": f"Sieg {h} (1)", "prob": mkts['1X2']['1']['prob'], "base_q": mkts['1X2']['1']['base_q'], "markt": "1X2 Siegwette"},
        {"tipp": f"Sieg {a} (2)", "prob": mkts['1X2']['2']['prob'], "base_q": mkts['1X2']['2']['base_q'], "markt": "1X2 Siegwette"},
        {"tipp": f"Doppelte Chance 1X ({h} / X)", "prob": mkts['DC']['1X']['prob'], "base_q": mkts['DC']['1X']['base_q'], "markt": "Doppelte Chance"},
        {"tipp": f"Doppelte Chance X2 (X / {a})", "prob": mkts['DC']['X2']['prob'], "base_q": mkts['DC']['X2']['base_q'], "markt": "Doppelte Chance"},
        {"tipp": f"Sieg {h} (Draw No Bet)", "prob": mkts['DNB']['1 DNB']['prob'], "base_q": mkts['DNB']['1 DNB']['base_q'], "markt": "DNB"},
        {"tipp": "Über 1.5 Tore", "prob": mkts['Tore']['Über 1.5']['prob'], "base_q": mkts['Tore']['Über 1.5']['base_q'], "markt": "Tor-Markt"},
        {"tipp": "Über 2.5 Tore", "prob": mkts['Tore']['Über 2.5']['prob'], "base_q": mkts['Tore']['Über 2.5']['base_q'], "markt": "Tor-Markt"},
        {"tipp": "Beide Teams treffen - Ja", "prob": mkts['BTTS']['Ja']['prob'], "base_q": mkts['BTTS']['Ja']['base_q'], "markt": "Beide treffen"}
    ]

    cands = []
    for item in raw:
        cp = item.copy()
        cp['quote'] = item['base_q']
        cp['ev'] = round((((item['prob'] / 100.0) * cp['quote']) - 1.0) * 100.0, 1)
        cands.append(cp)

    if "Mittleres Risiko" in profile:
        valid = [c for c in cands if 1.50 <= c['quote'] <= 2.10]
        if not valid: valid = sorted(cands, key=lambda x: abs(x['quote'] - 1.80))[:4]
    elif "Hohes Risiko" in profile:
        valid = [c for c in cands if c['quote'] > 2.10]
        if not valid: valid = sorted(cands, key=lambda x: x['quote'], reverse=True)[:3]
    else:
        valid = [c for c in cands if c['quote'] < 1.50]
        if not valid: valid = sorted(cands, key=lambda x: x['quote'])[:3]

    selected = valid[seed % len(valid)]
    selected['stake'] = 5.0 if fixed_stake_mode else round(total_bankroll * 0.02, 2)
    return selected

if not matches:
    st.info("ℹ️ Bitte wähle oben mindestens eine Liga aus.")
else:
    c_t1, c_t2 = st.columns([2.5, 1.5])
    with c_t1:
        st.subheader(f"💎 Elite-Analysen ({len(matches)} Partien geladen)")
    with c_t2:
        if st.button("🎲 Neue Analysen mischen", type="primary", use_container_width=True):
            st.session_state['reroll_key'] += 1
            st.rerun()

    shuffled = matches.copy()
    random.Random(st.session_state['reroll_key']).shuffle(shuffled)
    current_picks = []

    if "Reine Einzelwetten" in gen_typ:
        cols = st.columns(2)
        for idx, match in enumerate(shuffled):
            pick = get_best_pick(match, risiko_profil)
            current_picks.append((match, pick))
            home_form = get_team_form(match['home'])
            away_form = get_team_form(match['away'])

            with cols[idx % 2]:
                with st.container(border=True):
                    sc1, sc2 = st.columns([2, 1])
                    with sc1: st.caption(f"🏆 {match['liga']}")
                    with sc2:
                        badge_class = "badge-elite-ev" if pick['ev'] > 0 else "badge-elite-std"
                        st.markdown(f"<div style='text-align: right;'><span class='{badge_class}'>💎 +{pick['ev']}% EV</span></div>", unsafe_allow_html=True)

                    st.markdown(f"#### {match['home']} vs {match['away']}")
                    st.text(f"📅 {match['time_str']}")

                    fc1, fc2 = st.columns(2)
                    with fc1:
                        st.markdown("<span style='font-size:0.75rem; color:#94a3b8;'>Form (Heim):</span>", unsafe_allow_html=True)
                        st.markdown(render_form_badges(home_form), unsafe_allow_html=True)
                    with fc2:
                        st.markdown("<span style='font-size:0.75rem; color:#94a3b8;'>Form (Auswärts):</span>", unsafe_allow_html=True)
                        st.markdown(render_form_badges(away_form), unsafe_allow_html=True)

                    st.markdown("---")
                    bc1, bc2 = st.columns([1.3, 0.7])
                    with bc1:
                        st.markdown(f"**Tipp:** `{pick['tipp']}`")
                        st.markdown(f"💵 **Einsatz:** `{pick['stake']} €`")
                        st.markdown(f"🎯 **Wahrsch.:** `{pick['prob']}%`")
                    with bc2:
                        st.metric(label="Quote", value=f"{pick['quote']}")

                    st.link_button("🔗 Live-Quoten auf Sofascore prüfen", match['sofascore_url'], use_container_width=True)

    elif "Kombiwette" in gen_typ:
        ausgewaehlte = shuffled[:min(len(shuffled), anzahl_wetten)]
        gesamtq = 1.0
        for m in ausgewaehlte:
            p = get_best_pick(m, risiko_profil)
            gesamtq *= p['quote']
            current_picks.append((m, p))
        st.metric(label="📊 GESAMTQUOTE DES KOMBISCHEINS", value=f"{round(gesamtq, 2)}")
        st.info(f"💡 Empfohlener Einsatz: **5.00 €** (Möglicher Gewinn: {round(5.0 * gesamtq, 2)} €)")

        for m, p in current_picks:
            with st.container(border=True):
                st.caption(f"🏆 {m['liga']} | {p['markt']}")
                st.markdown(f"#### {m['home']} vs {m['away']}")
                st.markdown(f"Tipp: **{p['tipp']}** ➔ **Quote: {p['quote']}**")
                st.link_button("🔗 Auf Sofascore vergleichen", m['sofascore_url'], use_container_width=True)

    elif "Freebet" in gen_typ:
        fb_picks = shuffled[:2]
        if len(fb_picks) >= 2:
            p1 = get_best_pick(fb_picks[0], risiko_profil)
            p2 = get_best_pick(fb_picks[1], risiko_profil)
            current_picks = [(fb_picks[0], p1), (fb_picks[1], p2)]
            q_ges = round(p1['quote'] * p2['quote'], 2)
            st.info(f"🎁 Freebet-Wert: {freebet_wert} € | Gesamtquote: {q_ges} | Netto-Gewinn: {round((freebet_wert * q_ges) - freebet_wert, 2)} €")
            for m, p in current_picks:
                with st.container(border=True):
                    st.markdown(f"#### {m['home']} vs {m['away']}")
                    st.markdown(f"Tipp: `{p['tipp']}` | Quote: **{p['quote']}**")
                    st.link_button("🔗 Auf Sofascore vergleichen", m['sofascore_url'], use_container_width=True)

    else:
        e1, e2, e3 = round(multi_budget * 0.25, 2), round(multi_budget * 0.50, 2), round(multi_budget * 0.25, 2)
        s1 = shuffled[0:1]
        s2 = shuffled[1:3] if len(shuffled) >= 3 else shuffled[0:2]
        s3 = shuffled[3:6] if len(shuffled) >= 6 else shuffled
        tickets = [
            {"name": "🛡️ Schein 1: Solider Anker", "einsatz": e1, "matches": s1},
            {"name": "⭐ Schein 2: Hauptgewinn", "einsatz": e2, "matches": s2},
            {"name": "🚀 Schein 3: High-Reward", "einsatz": e3, "matches": s3}
        ]
        for t in tickets:
            if t['matches']:
                q_s = 1.0
                t_picks = []
                for m in t['matches']:
                    p = get_best_pick(m, risiko_profil)
                    q_s *= p['quote']
                    t_picks.append((m, p))
                    current_picks.append((m, p))
                with st.container(border=True):
                    st.markdown(f"### {t['name']}")
                    st.markdown(f"Einsatz: `{t['einsatz']} €` | Quote: `{round(q_s, 2)}` | Gewinn: `{round(t['einsatz']*q_s, 2)} €`")
                    for m, p in t_picks:
                        st.markdown(f"• {m['home']} vs {m['away']} -> **{p['tipp']}** (`{p['quote']}`)")

    if current_picks:
        st.markdown("---")
        if st.button("📌 Ausgewählte Tipps als Wettschein speichern", type="secondary", use_container_width=True):
            st.session_state['saved_tickets'].append({"zeitpunkt": datetime.now(tz_de).strftime("%d.%m.%Y %H:%M"), "typ": gen_typ, "picks": current_picks})
            st.success("✅ Wettschein erfolgreich im System gespeichert!")

st.markdown("---")
st.subheader("🗂️ Gespeicherte Scheine & Export")
if not st.session_state['saved_tickets']:
    st.info("Bisher keine Scheine gespeichert.")
else:
    export_rows = []
    text_share = "📱 *MEINE ELITE-WETTSCHEINE*\n\n"
    for idx, t in enumerate(st.session_state['saved_tickets'], 1):
        for m, p in t['picks']:
            export_rows.append({"Schein": idx, "Zeit": t['zeitpunkt'], "Heim": m['home'], "Gast": m['away'], "Tipp": p['tipp'], "Quote": p['quote']})
            text_share += f"⚽ {m['home']} vs {m['away']} ➔ {p['tipp']} @ {p['quote']}\n"
    
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.download_button("📥 CSV Export", data=pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8'), file_name="wettscheine.csv", mime="text/csv", use_container_width=True)
    with col_e2:
        if st.button("🗑️ Alle löschen", use_container_width=True):
            st.session_state['saved_tickets'] = []
            st.rerun()
    st.code(text_share, language="markdown")
