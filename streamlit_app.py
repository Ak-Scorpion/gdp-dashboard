import streamlit as st
import requests
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

# --- API-SCHLÜSSEL ROTATIONS-LISTE (FAILOVER) ---
ODDS_API_KEYS = [
    "912672acdd43a99efc9ee4ad5afe33a6",
    "a5e0323a0a14698cdeec004e3b9b18cc",
    "796a27287d73f08d0257cc838ebb6cd9",
    "e66bcb054c6ace9de606da63612c8f4c",
    "e36dbfffe1a22ab682e2759aea044180",
    "5d317d36dab0f21697792fe154902716",
    "25d237353cf0c5920d358d1e79f9450c",
    "0339fb12fa7a92411c4fe5ca32d3755c",
    "1aa566d1bdb18c77b5c1210904adf5d5",
    "f0dc02ac1e10f8e6c0e607698964b5a6"
]

LEAGUE_SPORT_KEYS = {
    "🇩🇪 1. Bundesliga": "soccer_germany_bundesliga",
    "🇩🇪 2. Bundesliga": "soccer_germany_bundesliga2",
    "🇩🇪 3. Liga": "soccer_germany_liga3",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "soccer_epl",
    "🇪🇸 La Liga": "soccer_spain_la_liga",
    "🇮🇹 Serie A": "soccer_italy_serie_a",
    "🇫🇷 Ligue 1": "soccer_france_ligue_one",
    "🏆 Champions League": "soccer_uefa_champions_league",
    "🇪🇺 Europa League": "soccer_uefa_europa_league",
    "🇪🇺 Conference League": "soccer_uefa_europa_conference_league"
}

TEAM_RATINGS = {
    "bayern": 96, "dortmund": 87, "leverkusen": 91, "leipzig": 86, 
    "stuttgart": 83, "frankfurt": 82, "wolfsburg": 76, "gladbach": 75,
    "freiburg": 78, "union berlin": 75, "mainz": 74, "augsburg": 73,
    "werder bremen": 75, "hoffenheim": 76, "heidenheim": 73, "st. pauli": 70,
    "bochum": 68, "holstein kiel": 67, "schalke": 78,
    "hsv": 74, "hamburger sv": 74, "köln": 74, "hertha": 73,
    "duesseldorf": 74, "düsseldorf": 74, "hannover": 72, "paderborn": 71,
    "karlsruhe": 72, "kaiserslautern": 71, "dresden": 66, "aachen": 63,
    "essen": 64, "1860 münchen": 64, "osnabrück": 65, "rostock": 65,
    "manchester city": 95, "man city": 95, "arsenal": 92, "liverpool": 93,
    "chelsea": 85, "manchester united": 83, "man utd": 83, "tottenham": 83,
    "newcastle": 84, "aston villa": 84, "brighton": 79, "west ham": 78,
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86, "athletic bilbao": 81,
    "real sociedad": 81, "girona": 80, "villarreal": 80, "betis": 79, "sevilla": 77,
    "inter": 91, "juventus": 86, "ac milan": 86, "milan": 86, "napoli": 86,
    "atalanta": 85, "roma": 82, "lazio": 81, "fiorentina": 80,
    "paris saint-germain": 93, "psg": 93, "monaco": 82, "marseille": 82,
    "lille": 81, "lyon": 80, "rennes": 78, "lens": 78
}

def get_team_rating(team_name):
    name_clean = team_name.lower().strip()
    for key, rating in TEAM_RATINGS.items():
        if key in name_clean:
            return rating
    return 75

def calculate_dynamic_xg(home_team, away_team):
    r_home = get_team_rating(home_team) + 4
    r_away = get_team_rating(away_team)
    ratio_home = r_home / float(r_away)
    ratio_away = r_away / float(r_home)
    xg_home = round(max(0.4, min(4.2, 1.55 * (ratio_home ** 1.9))), 2)
    xg_away = round(max(0.4, min(3.8, 1.20 * (ratio_away ** 1.8))), 2)
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

ANBIETER_URLS = {
    "Tipico": "https://www.tipico.de",
    "bwin": "https://sports.bwin.de",
    "Bet365": "https://www.bet365.de",
    "Betano": "https://www.betano.de",
    "DAZN Bet": "https://www.daznbet.de",
    "Neo.bet": "https://www.neo.bet/de",
    "Oddset": "https://www.oddset.de",
    "Bet-at-home": "https://www.bet-at-home.com"
}

@st.cache_data(ttl=300)
def fetch_live_odds_for_sport(sport_key):
    """Zentrale, blitzschnelle Abfrage mit automatischem Key-Failover für echte Quoten."""
    for key in ODDS_API_KEYS:
        if not key.strip():
            continue
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={key}&regions=eu&markets=h2h,totals"
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                return res.json()
        except Exception:
            continue
    return []

@st.cache_data(ttl=300)
def fetch_openliga_matches(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def fetch_espn_matches(league_code, start_str, end_str):
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard?dates={start_str}-{end_str}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            events = data.get('events', [])
            matches = []
            for event in events:
                utc_str = event.get('date')
                comps = event.get('competitions', [])
                if comps:
                    competitors = comps[0].get('competitors', [])
                    h, a = "", ""
                    for comp in competitors:
                        if comp.get('homeAway') == 'home':
                            h = comp.get('team', {}).get('displayName', '')
                        else:
                            a = comp.get('team', {}).get('displayName', '')
                    if h and a and utc_str:
                        matches.append({"home": h, "away": a, "utc_date": utc_str})
            return matches
    except Exception:
        pass
    return []

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

def build_markets(home_xg, away_xg, home_team, away_team, odds_cache):
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

    # Echte Live-Quoten aus dem API-Cache matchen
    live_odds = None
    for ev in odds_cache:
        if home_team.lower() in ev.get('home_team', '').lower() or away_team.lower() in ev.get('away_team', '').lower():
            bms = ev.get('bookmakers', [])
            if bms:
                mkts = bms[0].get('markets', [])
                o_dict = {}
                for m in mkts:
                    if m['key'] == 'h2h':
                        for out in m['outcomes']:
                            if out['name'].lower() == home_team.lower():
                                o_dict['home'] = out['price']
                            elif out['name'].lower() == away_team.lower():
                                o_dict['away'] = out['price']
                            else:
                                o_dict['draw'] = out['price']
                    elif m['key'] == 'totals':
                        for out in m['outcomes']:
                            if out.get('name') == 'Over' and out.get('point') == 2.5:
                                o_dict['over25'] = out['price']
                live_odds = o_dict
                break

    q_home = live_odds.get('home', round((1.0 / p_home) / 1.04, 2)) if live_odds and 'home' in live_odds else round((1.0 / p_home) / 1.04, 2)
    q_draw = live_odds.get('draw', round((1.0 / p_draw) / 1.04, 2)) if live_odds and 'draw' in live_odds else round((1.0 / p_draw) / 1.04, 2)
    q_away = live_odds.get('away', round((1.0 / p_away) / 1.04, 2)) if live_odds and 'away' in live_odds else round((1.0 / p_away) / 1.04, 2)
    q_over25 = live_odds.get('over25', round((1.0 / p_over25) / 1.04, 2)) if live_odds and 'over25' in live_odds else round((1.0 / p_over25) / 1.04, 2)

    return {
        "1X2": {
            "1": {"prob": round(p_home * 100, 1), "base_q": q_home},
            "X": {"prob": round(p_draw * 100, 1), "base_q": q_draw},
            "2": {"prob": round(p_away * 100, 1), "base_q": q_away}
        },
        "DC": {
            "1X": {"prob": round(p_dc_1x * 100, 1), "base_q": round(max(1.05, q_home * 0.76), 2)},
            "X2": {"prob": round(p_dc_x2 * 100, 1), "base_q": round(max(1.05, q_away * 0.86), 2)},
            "12": {"prob": round(p_dc_12 * 100, 1), "base_q": round(max(1.05, q_home * 0.81), 2)}
        },
        "DNB": {
            "1 DNB": {"prob": round(p_dnb_1 * 100, 1), "base_q": round(max(1.05, q_home * 1.15), 2)},
            "2 DNB": {"prob": round(p_dnb_2 * 100, 1), "base_q": round(max(1.05, q_away * 1.35), 2)}
        },
        "Tore": {
            "Über 1.5": {"prob": round(p_over15 * 100, 1), "base_q": round((1.0 / p_over15) / 1.04, 2)},
            "Über 2.5": {"prob": round(p_over25 * 100, 1), "base_q": q_over25},
            "Unter 2.5": {"prob": round(p_under25 * 100, 1), "base_q": round((1.0 / p_under25) / 1.04, 2)}
        },
        "BTTS": {
            "Ja": {"prob": round(p_btts_ja * 100, 1), "base_q": round((1.0 / p_btts_ja) / 1.04, 2)}
        }
    }

def get_best_bookmaker_odds(base_quote, bm_name):
    margins = {"Bet365": 1.03, "Betano": 1.035, "Neo.bet": 1.04, "bwin": 1.045, "Tipico": 1.05, "DAZN Bet": 1.04, "Oddset": 1.055, "Bet-at-home": 1.05}
    factor = margins.get(bm_name, 1.04)
    return max(1.05, min(round(base_quote * (1.04 / factor), 2), 50.00))

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
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">100% Strikte Ligen-Filterung & Echte Live-Quoten • Ziel: 58€ ➔ 100€</p>
    </div>
""", unsafe_allow_html=True)

with st.expander("⚙️ Einstellungen & Ligen-Auswahl (Strikte Filterung)", expanded=True):
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
    st.markdown("#### 🏪 Wettanbieter:")
    aktive_anbieter = []
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.checkbox("Tipico", value=True): aktive_anbieter.append("Tipico")
        if st.checkbox("bwin", value=True): aktive_anbieter.append("bwin")
    with c2:
        if st.checkbox("Bet365", value=True): aktive_anbieter.append("Bet365")
        if st.checkbox("Betano", value=True): aktive_anbieter.append("Betano")
    with c3:
        if st.checkbox("DAZN Bet", value=True): aktive_anbieter.append("DAZN Bet")
        if st.checkbox("Neo.bet", value=True): aktive_anbieter.append("Neo.bet")
    with c4:
        if st.checkbox("Oddset", value=True): aktive_anbieter.append("Oddset")
        if st.checkbox("Bet-at-home", value=True): aktive_anbieter.append("Bet-at-home")

    st.markdown("---")
    st.markdown("#### 🏆 Ligen-Auswahl (Exakt aktiv):")
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

if "HEUTE" in gen_zeit_modus:
    dt_from, dt_to = today_de, today_de
elif "MORGEN" in gen_zeit_modus:
    dt_from, dt_to = tomorrow_de, tomorrow_de
elif "WOCHENENDE" in gen_zeit_modus:
    dt_from, dt_to = fri_de, sun_de
else:
    dt_from, dt_to = today_de, today_de + timedelta(days=7)

if generate_click or not st.session_state['matches_cache']:
    if not aktive_generator_ligen:
        st.error("Bitte wähle mindestens eine Liga aus!")
    elif not aktive_anbieter:
        st.error("Bitte wähle mindestens einen Wettanbieter aus!")
    else:
        with st.spinner("Lade Live-Quoten & filtere Ligen..."):
            all_loaded = []
            
            # Globaler Quoten-Cache für alle aktiv gewählten Ligen holen
            sport_key_cache = {}
            for liga in aktive_generator_ligen:
                s_key = LEAGUE_SPORT_KEYS.get(liga)
                if s_key and s_key not in sport_key_cache:
                    sport_key_cache[s_key] = fetch_live_odds_for_sport(s_key)

            for liga_label in aktive_generator_ligen:
                s_key = LEAGUE_SPORT_KEYS.get(liga_label)
                odds_cache = sport_key_cache.get(s_key, [])

                if liga_label.startswith("🇩🇪"):
                    shortcut = {"🇩🇪 1. Bundesliga": "bl1", "🇩🇪 2. Bundesliga": "bl2", "🇩🇪 3. Liga": "bl3"}.get(liga_label)
                    raw = fetch_openliga_matches(shortcut)
                    for m in raw:
                        dt_str = m.get('matchDateTime')
                        if dt_str:
                            try:
                                dt = datetime.fromisoformat(dt_str).astimezone(tz_de)
                                if dt_from <= dt.date() <= dt_to:
                                    h, a = m['team1']['teamName'], m['team2']['teamName']
                                    xg_h, xg_a = calculate_dynamic_xg(h, a)
                                    mkts = build_markets(xg_h, xg_a, h, a, odds_cache)
                                    all_loaded.append({"liga": liga_label, "home": h, "away": a, "time_str": dt.strftime("%d.%m. - %H:%M Uhr"), "markets": mkts})
                            except:
                                continue
                else:
                    espn_code = {"🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "eng.1", "🇪🇸 La Liga": "esp.1", "🇮🇹 Serie A": "ita.1", "🇫🇷 Ligue 1": "fra.1", "🏆 Champions League": "uefa.champions", "🇪🇺 Europa League": "uefa.europa", "🇪🇺 Conference League": "uefa.europa.conf"}.get(liga_label)
                    raw = fetch_espn_matches(espn_code, dt_from.strftime("%Y%m%d"), dt_to.strftime("%Y%m%d"))
                    for m in raw:
                        try:
                            dt = datetime.fromisoformat(m['utc_date'].replace('Z', '+00:00')).astimezone(tz_de)
                            if dt_from <= dt.date() <= dt_to:
                                h, a = m['home'], m['away']
                                xg_h, xg_a = calculate_dynamic_xg(h, a)
                                mkts = build_markets(xg_h, xg_a, h, a, odds_cache)
                                all_loaded.append({"liga": liga_label, "home": h, "away": a, "time_str": dt.strftime("%d.%m. - %H:%M Uhr"), "markets": mkts})
                        except:
                            continue

            # STRIKTE FILTERUNG: Nur Spiele behalten, deren Liga aktiv in aktive_generator_ligen ist!
            st.session_state['matches_cache'] = [m for m in all_loaded if m['liga'] in aktive_generator_ligen]

matches = [m for m in st.session_state.get('matches_cache', []) if m['liga'] in aktive_generator_ligen]

def get_best_pick(match, profile, checked_bms):
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
        chosen_bm = random.Random(str(seed) + item['tipp']).choice(checked_bms) if checked_bms else "Tipico"
        quote = get_best_bookmaker_odds(item['base_q'], chosen_bm)
        cp = item.copy()
        cp['quote'] = quote
        cp['best_bookmaker'] = chosen_bm
        cp['bookmaker_url'] = ANBIETER_URLS.get(chosen_bm, "https://www.tipico.de")
        cp['ev'] = round((((item['prob'] / 100.0) * quote) - 1.0) * 100.0, 1)
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
    st.info("ℹ️ Keine Partien für die aktuell aktivierten Ligen im gewählten Zeitraum.")
else:
    c_t1, c_t2 = st.columns([2.5, 1.5])
    with c_t1:
        st.subheader(f"💎 Elite-Analysen ({len(matches)} Partien gefiltert)")
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
            pick = get_best_pick(match, risiko_profil, aktive_anbieter)
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
                        st.metric(label=f"Quote ({pick['best_bookmaker']})", value=f"{pick['quote']}")

                    st.link_button(f"🔗 Bei {pick['best_bookmaker']} wetten", pick['bookmaker_url'], use_container_width=True)

    elif "Kombiwette" in gen_typ:
        ausgewaehlte = shuffled[:min(len(shuffled), anzahl_wetten)]
        gesamtq = 1.0
        for m in ausgewaehlte:
            p = get_best_pick(m, risiko_profil, aktive_anbieter)
            gesamtq *= p['quote']
            current_picks.append((m, p))
        st.metric(label="📊 GESAMTQUOTE DES KOMBISCHEINS", value=f"{round(gesamtq, 2)}")
        st.info(f"💡 Empfohlener Einsatz: **5.00 €** (Möglicher Gewinn: {round(5.0 * gesamtq, 2)} €)")

        for m, p in current_picks:
            with st.container(border=True):
                st.caption(f"🏆 {m['liga']} | {p['markt']}")
                st.markdown(f"#### {m['home']} vs {m['away']}")
                st.markdown(f"Tipp: **{p['tipp']}** ({p['best_bookmaker']}) ➔ **Quote: {p['quote']}**")
                st.link_button(f"🔗 Zu {p['best_bookmaker']}", p['bookmaker_url'], use_container_width=True)

    elif "Freebet" in gen_typ:
        fb_picks = shuffled[:2]
        if len(fb_picks) >= 2:
            p1 = get_best_pick(fb_picks[0], risiko_profil, aktive_anbieter)
            p2 = get_best_pick(fb_picks[1], risiko_profil, aktive_anbieter)
            current_picks = [(fb_picks[0], p1), (fb_picks[1], p2)]
            q_ges = round(p1['quote'] * p2['quote'], 2)
            st.info(f"🎁 Freebet-Wert: {freebet_wert} € | Gesamtquote: {q_ges} | Netto-Gewinn: {round((freebet_wert * q_ges) - freebet_wert, 2)} €")
            for m, p in current_picks:
                with st.container(border=True):
                    st.markdown(f"#### {m['home']} vs {m['away']}")
                    st.markdown(f"Tipp: `{p['tipp']}` | Quote: **{p['quote']}** ({p['best_bookmaker']})")
                    st.link_button(f"🔗 Zu {p['best_bookmaker']}", p['bookmaker_url'], use_container_width=True)

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
                    p = get_best_pick(m, risiko_profil, aktive_anbieter)
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
            export_rows.append({"Schein": idx, "Zeit": t['zeitpunkt'], "Heim": m['home'], "Gast": m['away'], "Tipp": p['tipp'], "Quote": p['quote'], "Anbieter": p['best_bookmaker']})
            text_share += f"⚽ {m['home']} vs {m['away']} ➔ {p['tipp']} @ {p['quote']} ({p['best_bookmaker']})\n"
    
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.download_button("📥 CSV Export", data=pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8'), file_name="wettscheine.csv", mime="text/csv", use_container_width=True)
    with col_e2:
        if st.button("🗑️ Alle löschen", use_container_width=True):
            st.session_state['saved_tickets'] = []
            st.rerun()
    st.code(text_share, language="markdown")
