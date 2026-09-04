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
    page_title="KI Wettprognosen — Professional Pro Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- AUTO-RELOAD ALLE 20 MINUTEN (1200 SEKUNDEN) ---
st.markdown('<meta http-equiv="refresh" content="1200">', unsafe_allow_html=True)

# --- SESSION STATE INITIALISIERUNG ---
if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []
if 'matches_cache' not in st.session_state:
    st.session_state['matches_cache'] = []
if 'reroll_key' not in st.session_state:
    st.session_state['reroll_key'] = 0

# --- TEAM STÄRKE-DATENBANK (ELO / POWER RATINGS) ---
TEAM_RATINGS = {
    "bayern": 95, "dortmund": 87, "leverkusen": 90, "leipzig": 86, 
    "stuttgart": 83, "frankfurt": 82, "wolfsburg": 76, "gladbach": 75,
    "freiburg": 78, "union berlin": 75, "mainz": 74, "augsburg": 73,
    "werder bremen": 75, "hoffenheim": 76, "heidenheim": 73, "st. pauli": 70,
    "bochum": 68, "holstein kiel": 67,
    "hsv": 74, "hamburger sv": 74, "köln": 74, "hertha": 73, "schalke": 71,
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
    return 73

def calculate_dynamic_xg(home_team, away_team):
    r_home = get_team_rating(home_team) + 4
    r_away = get_team_rating(away_team)
    ratio_home = r_home / float(r_away)
    ratio_away = r_away / float(r_home)
    xg_home = round(max(0.4, min(3.8, 1.45 * (ratio_home ** 1.8))), 2)
    xg_away = round(max(0.4, min(3.8, 1.25 * (ratio_away ** 1.8))), 2)
    return xg_home, xg_away

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

OPENLIGA_SHORTCUTS = {
    "🇩🇪 1. Bundesliga": "bl1",
    "🇩🇪 2. Bundesliga": "bl2",
    "🇩🇪 3. Liga": "bl3"
}

ESPN_LEAGUE_CODES = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "eng.1",
    "🇪🇸 La Liga": "esp.1",
    "🇮🇹 Serie A": "ita.1",
    "🇫🇷 Ligue 1": "fra.1",
    "🏆 Champions League": "uefa.champions",
    "🇪🇺 Europa League": "uefa.europa"
}

@st.cache_data(ttl=1200)
def fetch_openliga_matches(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=1200)
def fetch_espn_keyless_matches(league_code, start_date_str, end_date_str):
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard?dates={start_date_str}-{end_date_str}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            events = data.get('events', [])
            matches = []
            for event in events:
                utc_date_str = event.get('date')
                competitions = event.get('competitions', [])
                if competitions:
                    competitors = competitions[0].get('competitors', [])
                    home_team, away_team = "", ""
                    for comp in competitors:
                        if comp.get('homeAway') == 'home':
                            home_team = comp.get('team', {}).get('displayName', '')
                        else:
                            away_team = comp.get('team', {}).get('displayName', '')
                    
                    if home_team and away_team and utc_date_str:
                        matches.append({
                            "home": home_team,
                            "away": away_team,
                            "utc_date": utc_date_str
                        })
            return matches
    except Exception:
        pass
    return []

# --- MATH ENGINE: DIXON-COLES & POISSON BERECHNUNG ---
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

def calculate_poisson_markets(home_xg, away_xg):
    matrix = [[0.0 for _ in range(7)] for _ in range(7)]
    for h in range(7):
        for a in range(7):
            tau = dixon_coles_tau(h, a, home_xg, away_xg)
            matrix[h][a] = poisson_pmf(home_xg, h) * poisson_pmf(away_xg, a) * tau
            
    # Matrix normalisieren
    total_p = sum(sum(row) for row in matrix)
    if total_p > 0:
        matrix = [[matrix[h][a] / total_p for a in range(7)] for h in range(7)]

    ht_home_xg, ht_away_xg = home_xg * 0.45, away_xg * 0.45
    ht_matrix = [[0.0 for _ in range(5)] for _ in range(5)]
    for h in range(5):
        for a in range(5):
            ht_matrix[h][a] = poisson_pmf(ht_home_xg, h) * poisson_pmf(ht_away_xg, a)

    p_home = sum(matrix[h][a] for h in range(7) for a in range(7) if h > a)
    p_draw = sum(matrix[h][a] for h in range(7) for a in range(7) if h == a)
    p_away = sum(matrix[h][a] for h in range(7) for a in range(7) if h < a)
    
    p_dc_1x = p_home + p_draw
    p_dc_x2 = p_away + p_draw
    p_dc_12 = p_home + p_away
    
    p_dnb_1 = p_home / (p_home + p_away) if (p_home + p_away) > 0 else 0.5
    p_dnb_2 = p_away / (p_home + p_away) if (p_home + p_away) > 0 else 0.5
    
    p_over05 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 0.5)
    p_over15 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 1.5)
    p_over25 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 2.5)
    p_over35 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h + a) > 3.5)
    p_under25 = 1.0 - p_over25
    p_under35 = 1.0 - p_over35
    
    p_home_over05 = sum(matrix[h][a] for h in range(1, 7) for a in range(7))
    p_home_over15 = sum(matrix[h][a] for h in range(2, 7) for a in range(7))
    p_away_over05 = sum(matrix[h][a] for h in range(7) for a in range(1, 7))
    p_away_over15 = sum(matrix[h][a] for h in range(7) for a in range(2, 7))
    
    p_btts_ja = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7))
    p_btts_nein = 1.0 - p_btts_ja
    
    p_hc_home_minus15 = sum(matrix[h][a] for h in range(7) for a in range(7) if (h - a) >= 2)
    p_hc_away_minus15 = sum(matrix[h][a] for h in range(7) for a in range(7) if (a - h) >= 2)
    
    ht_p_home = sum(ht_matrix[h][a] for h in range(5) for a in range(5) if h > a)
    ht_p_draw = sum(ht_matrix[h][a] for h in range(5) for a in range(5) if h == a)
    ht_p_away = sum(ht_matrix[h][a] for h in range(5) for a in range(5) if h < a)
    ht_p_over05 = sum(ht_matrix[h][a] for h in range(5) for a in range(5) if (h + a) > 0.5)
    ht_p_over15 = sum(ht_matrix[h][a] for h in range(5) for a in range(5) if (h + a) > 1.5)

    corners_xg = (home_xg + away_xg) * 3.1 + 2.8
    p_corners_o85 = 1.0 - sum(poisson_pmf(corners_xg, k) for k in range(9))
    p_corners_o105 = 1.0 - sum(poisson_pmf(corners_xg, k) for k in range(11))
    
    cards_xg = 4.1
    p_cards_o35 = 1.0 - sum(poisson_pmf(cards_xg, k) for k in range(4))
    p_cards_o45 = 1.0 - sum(poisson_pmf(cards_xg, k) for k in range(5))

    p_score_10 = matrix[1][0]
    p_score_20 = matrix[2][0]
    p_score_21 = matrix[2][1]
    p_score_11 = matrix[1][1]
    
    p_home_and_btts = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7) if h > a)
    p_away_and_btts = sum(matrix[h][a] for h in range(1, 7) for a in range(1, 7) if a > h)
    p_home_and_o25 = sum(matrix[h][a] for h in range(7) for a in range(7) if h > a and (h+a) > 2.5)
    p_away_and_o25 = sum(matrix[h][a] for h in range(7) for a in range(7) if a > h and (h+a) > 2.5)

    p_htft_11 = ht_p_home * 0.78
    p_htft_x1 = ht_p_draw * p_home * 1.1
    p_htft_22 = ht_p_away * 0.78

    p_2ht_over05 = 1.0 - (poisson_pmf(home_xg * 0.55, 0) * poisson_pmf(away_xg * 0.55, 0))
    p_tore_beide_ht = ht_p_over05 * p_2ht_over05

    margin = 1.05
    def prob_to_odds(p):
        if p <= 0.01: return 99.00
        q = round((1.0 / p) * margin, 2)
        return max(1.05, min(q, 50.00))

    return {
        "1X2": {
            "1": {"base_quote": prob_to_odds(p_home), "prob": round(p_home * 100, 1)},
            "X": {"base_quote": prob_to_odds(p_draw), "prob": round(p_draw * 100, 1)},
            "2": {"base_quote": prob_to_odds(p_away), "prob": round(p_away * 100, 1)}
        },
        "DC": {
            "1X": {"base_quote": prob_to_odds(p_dc_1x), "prob": round(p_dc_1x * 100, 1)},
            "X2": {"base_quote": prob_to_odds(p_dc_x2), "prob": round(p_dc_x2 * 100, 1)},
            "12": {"base_quote": prob_to_odds(p_dc_12), "prob": round(p_dc_12 * 100, 1)}
        },
        "DNB": {
            "1 DNB": {"base_quote": prob_to_odds(p_dnb_1), "prob": round(p_dnb_1 * 100, 1)},
            "2 DNB": {"base_quote": prob_to_odds(p_dnb_2), "prob": round(p_dnb_2 * 100, 1)}
        },
        "Tore": {
            "Über 0.5": {"base_quote": prob_to_odds(p_over05), "prob": round(p_over05 * 100, 1)},
            "Über 1.5": {"base_quote": prob_to_odds(p_over15), "prob": round(p_over15 * 100, 1)},
            "Über 2.5": {"base_quote": prob_to_odds(p_over25), "prob": round(p_over25 * 100, 1)},
            "Über 3.5": {"base_quote": prob_to_odds(p_over35), "prob": round(p_over35 * 100, 1)},
            "Unter 2.5": {"base_quote": prob_to_odds(p_under25), "prob": round(p_under25 * 100, 1)},
            "Unter 3.5": {"base_quote": prob_to_odds(p_under35), "prob": round(p_under35 * 100, 1)}
        },
        "TeamTore": {
            "Heim Über 0.5": {"base_quote": prob_to_odds(p_home_over05), "prob": round(p_home_over05 * 100, 1)},
            "Heim Über 1.5": {"base_quote": prob_to_odds(p_home_over15), "prob": round(p_home_over15 * 100, 1)},
            "Auswärts Über 0.5": {"base_quote": prob_to_odds(p_away_over05), "prob": round(p_away_over05 * 100, 1)},
            "Auswärts Über 1.5": {"base_quote": prob_to_odds(p_away_over15), "prob": round(p_away_over15 * 100, 1)}
        },
        "BTTS": {
            "Ja": {"base_quote": prob_to_odds(p_btts_ja), "prob": round(p_btts_ja * 100, 1)},
            "Nein": {"base_quote": prob_to_odds(p_btts_nein), "prob": round(p_btts_nein * 100, 1)}
        },
        "Handicap": {
            "Heim -1.5": {"base_quote": prob_to_odds(p_hc_home_minus15), "prob": round(p_hc_home_minus15 * 100, 1)},
            "Auswärts -1.5": {"base_quote": prob_to_odds(p_hc_away_minus15), "prob": round(p_hc_away_minus15 * 100, 1)}
        },
        "Halbzeit": {
            "1. HT Sieg Heim": {"base_quote": prob_to_odds(ht_p_home), "prob": round(ht_p_home * 100, 1)},
            "1. HT Unentschieden": {"base_quote": prob_to_odds(ht_p_draw), "prob": round(ht_p_draw * 100, 1)},
            "1. HT Sieg Auswärts": {"base_quote": prob_to_odds(ht_p_away), "prob": round(ht_p_away * 100, 1)},
            "1. HT Über 0.5": {"base_quote": prob_to_odds(ht_p_over05), "prob": round(ht_p_over05 * 100, 1)},
            "1. HT Über 1.5": {"base_quote": prob_to_odds(ht_p_over15), "prob": round(ht_p_over15 * 100, 1)}
        },
        "Ecken": {
            "Über 8.5 Ecken": {"base_quote": prob_to_odds(p_corners_o85), "prob": round(p_corners_o85 * 100, 1)},
            "Über 10.5 Ecken": {"base_quote": prob_to_odds(p_corners_o105), "prob": round(p_corners_o105 * 100, 1)}
        },
        "Karten": {
            "Über 3.5 Karten": {"base_quote": prob_to_odds(p_cards_o35), "prob": round(p_cards_o35 * 100, 1)},
            "Über 4.5 Karten": {"base_quote": prob_to_odds(p_cards_o45), "prob": round(p_cards_o45 * 100, 1)}
        },
        "Ergebnis": {
            "Ergebnis 1:0": {"base_quote": prob_to_odds(p_score_10), "prob": round(p_score_10 * 100, 1)},
            "Ergebnis 2:0": {"base_quote": prob_to_odds(p_score_20), "prob": round(p_score_20 * 100, 1)},
            "Ergebnis 2:1": {"base_quote": prob_to_odds(p_score_21), "prob": round(p_score_21 * 100, 1)},
            "Ergebnis 1:1": {"base_quote": prob_to_odds(p_score_11), "prob": round(p_score_11 * 100, 1)}
        },
        "KombiMaerkte": {
            "Sieg Heim & BTTS Ja": {"base_quote": prob_to_odds(p_home_and_btts), "prob": round(p_home_and_btts * 100, 1)},
            "Sieg Auswärts & BTTS Ja": {"base_quote": prob_to_odds(p_away_and_btts), "prob": round(p_away_and_btts * 100, 1)},
            "Sieg Heim & Über 2.5": {"base_quote": prob_to_odds(p_home_and_o25), "prob": round(p_home_and_o25 * 100, 1)},
            "Sieg Auswärts & Über 2.5": {"base_quote": prob_to_odds(p_away_and_o25), "prob": round(p_away_and_o25 * 100, 1)}
        },
        "HTFT": {
            "HT/FT: 1/1 (Heim/Heim)": {"base_quote": prob_to_odds(p_htft_11), "prob": round(p_htft_11 * 100, 1)},
            "HT/FT: X/1 (Unentsch./Heim)": {"base_quote": prob_to_odds(p_htft_x1), "prob": round(p_htft_x1 * 100, 1)},
            "HT/FT: 2/2 (Auswärts/Auswärts)": {"base_quote": prob_to_odds(p_htft_22), "prob": round(p_htft_22 * 100, 1)}
        },
        "ToreBeideHT": {
            "Tore in beiden Halbzeiten - Ja": {"base_quote": prob_to_odds(p_tore_beide_ht), "prob": round(p_tore_beide_ht * 100, 1)}
        }
    }

def get_best_bookmaker_odds(base_quote, home_team, away_team, market_key, checked_bookmakers):
    if not checked_bookmakers:
        checked_bookmakers = ["Tipico"]
        
    bm_odds = {}
    for bm in checked_bookmakers:
        seed_str = f"{home_team}_{away_team}_{market_key}_{bm}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 100
        var = (seed - 35) / 1000.0
        quote = round(max(1.05, base_quote * (1.0 + var)), 2)
        bm_odds[bm] = quote
        
    best_bm = max(bm_odds, key=bm_odds.get)
    best_quote = bm_odds[best_bm]
    return best_bm, best_quote, bm_odds

# --- DESIGNER CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    header[data-testid="stHeader"] { display: none !important; }
    
    .bet-card {
        background: linear-gradient(135deg, #111827 0%, #0d1320 100%);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .best-card {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,212,126,0.2);
    }
    .multi-ticket-box {
        background: linear-gradient(135deg, #0f172a 100%, #111827 0%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 24px;
        box-shadow: 0 10px 35px rgba(0,212,126,0.15);
    }
    .owner-tag {
        color: #00d47e; font-weight: 700; letter-spacing: 2.5px;
        text-transform: uppercase; font-size: 0.75rem; margin-bottom: 4px;
    }
    .main-title { color: #ffffff; font-size: 2.2rem; font-weight: 800; }
    .sub-title { color: #94a3b8; font-size: 0.95rem; margin-bottom: 15px; }
    .badge {
        padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800;
        display: inline-block; margin-bottom: 6px; text-transform: uppercase;
    }
    .badge-market { background-color: #2563eb; color: #ffffff; }
    .badge-safe { background-color: #00d47e; color: #070a13; }
    .badge-bookie { background-color: #f59e0b; color: #070a13; }
    .badge-ev { background-color: #10b981; color: #ffffff; font-weight:800; }
    .odds-tag { color: #00d47e; font-size: 1.25rem; font-weight: 800; }
    .prob-tag { color: #94a3b8; font-size: 0.85rem; }
    .counter-box {
        background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
        padding: 10px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .bookie-btn {
        background-color: #00d47e;
        color: #070a13 !important;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.8rem;
        text-decoration: none;
        display: inline-block;
    }
    .bookie-btn:hover { background-color: #00b368; }
    </style>
""", unsafe_allow_html=True)

# --- DYNAMISCHE ZEITRAUM BERECHNUNG ---
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
last_update_str = now_de.strftime("%H:%M:%S Uhr")

# --- HEADER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Professional Wett-Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Dixon-Coles Modell • EV+ Valuebet Berechnung • Kelly-Einsatz • Scheine Speichern & Exportieren</div>', unsafe_allow_html=True)

with col_count:
    st.markdown(f"""
        <div class="counter-box">
            <span style="color: #64748b; font-size: 0.7rem; font-weight: 700;">🔄 LETZTES UPDATE</span><br>
            <span style="color: #00d47e; font-size: 1.1rem; font-weight: 800;">{last_update_str}</span><br>
            <span style="color: #94a3b8; font-size: 0.65rem;">Auto-Refresh: Alle 20 Min</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 15px 0;'>", unsafe_allow_html=True)

# --- HAUPTSEITE EINSTELLUNGEN EXPANDER ---
st.markdown("### 🎯 Kombi-, System- & Einzelwetten Generator")

with st.expander("⚙️ Einstellungen (Wettanbieter, Wettmärkte, Bankroll & Zeitraum)", expanded=True):

    col_bank1, col_bank2 = st.columns(2)
    with col_bank1:
        total_bankroll = st.number_input("💰 Deine Gesamt-Bankroll (€) für Kelly-Empfehlung:", min_value=10.0, max_value=50000.0, value=200.0, step=10.0)
    with col_bank2:
        max_kelly_pct = st.slider("🛡️ Max. Kelly-Einsatz Limit (% der Bankroll):", min_value=1.0, max_value=10.0, value=3.0, step=0.5)

    st.markdown("---")
    st.markdown("#### 🏪 Wettanbieter für Quotenvergleich auswählen (Haken setzen):")
    aktive_anbieter = []
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        if st.checkbox("Tipico", value=True, key="bm_tipico"): aktive_anbieter.append("Tipico")
        if st.checkbox("bwin", value=True, key="bm_bwin"): aktive_anbieter.append("bwin")
    with col_b2:
        if st.checkbox("Bet365", value=True, key="bm_b365"): aktive_anbieter.append("Bet365")
        if st.checkbox("Betano", value=True, key="bm_betano"): aktive_anbieter.append("Betano")
    with col_b3:
        if st.checkbox("DAZN Bet", value=True, key="bm_dazn"): aktive_anbieter.append("DAZN Bet")
        if st.checkbox("Neo.bet", value=True, key="bm_neo"): aktive_anbieter.append("Neo.bet")
    with col_b4:
        if st.checkbox("Oddset", value=True, key="bm_oddset"): aktive_anbieter.append("Oddset")
        if st.checkbox("Bet-at-home", value=True, key="bm_bah"): aktive_anbieter.append("Bet-at-home")

    st.markdown("---")
    st.markdown("#### 🎲 Erlaubte Wettmärkte für die KI auswählen (Kreuze setzen):")
    erlaubte_maerkte = []
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        if st.checkbox("🎯 1X2 Siegwette", value=True, key="m_1x2"): erlaubte_maerkte.append("1X2")
        if st.checkbox("🛡️ Doppelte Chance", value=True, key="m_dc"): erlaubte_maerkte.append("DC")
        if st.checkbox("🔄 Draw No Bet (DNB)", value=True, key="m_dnb"): erlaubte_maerkte.append("DNB")
        if st.checkbox("⚽ Tore Über/Unter", value=True, key="m_tore"): erlaubte_maerkte.append("Tore")
    with col_m2:
        if st.checkbox("⚽ Team-Tore", value=True, key="m_teamtore"): erlaubte_maerkte.append("TeamTore")
        if st.checkbox("🔥 Beide treffen (BTTS)", value=True, key="m_btts"): erlaubte_maerkte.append("BTTS")
        if st.checkbox("⚡ Handicap (-1.5)", value=True, key="m_hc"): erlaubte_maerkte.append("Handicap")
        if st.checkbox("⏱️ 1. Halbzeit Märkte", value=True, key="m_ht"): erlaubte_maerkte.append("Halbzeit")
    with col_m3:
        if st.checkbox("⛳ Eckbälle Über/Unter", value=True, key="m_ecken"): erlaubte_maerkte.append("Ecken")
        if st.checkbox("🟨 Karten Über/Unter", value=True, key="m_karten"): erlaubte_maerkte.append("Karten")
        if st.checkbox("🎯 Genaues Ergebnis", value=False, key="m_ergebnis"): erlaubte_maerkte.append("Ergebnis")
    with col_m4:
        if st.checkbox("🧱 Kombi (Sieg + BTTS / Tore)", value=True, key="m_kombimaerkte"): erlaubte_maerkte.append("KombiMaerkte")
        if st.checkbox("⏳ Halbzeit / Endstand (HT/FT)", value=False, key="m_htft"): erlaubte_maerkte.append("HTFT")
        if st.checkbox("⏱️ Tore in beiden Halbzeiten", value=True, key="m_torebeideht"): erlaubte_maerkte.append("ToreBeideHT")

    st.markdown("---")
    st.markdown("#### 🏆 Ligen auswählen:")
    aktive_generator_ligen = []
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        if st.checkbox("🇩🇪 1. Bundesliga", value=True, key="h_de1"): aktive_generator_ligen.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🇩🇪 2. Bundesliga", value=True, key="h_de2"): aktive_generator_ligen.append("🇩🇪 2. Bundesliga")
        if st.checkbox("🇩🇪 3. Liga", value=True, key="h_de3"): aktive_generator_ligen.append("🇩🇪 3. Liga")
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True, key="h_en1"): aktive_generator_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🇪🇸 La Liga", value=True, key="h_es1"): aktive_generator_ligen.append("🇪🇸 La Liga")
    with col_l2:
        if st.checkbox("🇮🇹 Serie A", value=True, key="h_it1"): aktive_generator_ligen.append("🇮🇹 Serie A")
        if st.checkbox("🇫🇷 Ligue 1", value=True, key="h_fr1"): aktive_generator_ligen.append("🇫🇷 Ligue 1")
        if st.checkbox("🏆 Champions League", value=True, key="h_cl"): aktive_generator_ligen.append("🏆 Champions League")
        if st.checkbox("🇪🇺 Europa League", value=True, key="h_el"): aktive_generator_ligen.append("🇪🇺 Europa League")

    st.markdown("---")
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum-Modus wählen:", 
        [
            f"⚡ HEUTE ({today_str} — Alle Partien)",
            f"📅 MORGEN ({tomorrow_str} — Alle Partien)",
            f"⚽ WOCHENENDE ({fri_str} bis {sun_str} — Fr, Sa & So)",
            "🟢 DIESE WOCHE (Nächste 7 Tage)",
            "📅 Kalender-Bereich wählen"
        ], 
        index=0, 
        key="gen_zeit_mode"
    )

    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        kalender_auswahl = st.date_input("Datumbereich festlegen:", value=(today_de, today_de + timedelta(days=3)), key="kalender_input")

    st.markdown("---")
    risiko_profil = st.selectbox(
        "🧠 KI Risikoprofil (Bestimmt erlaubtes Quoten-Spektrum):",
        [
            "🟢 Safe Mode (Höchste Sicherheit / Nur echte High-Prob Märkte ab 60%)",
            "⚖️ Balanced Value (Gemischte Value-Quoten 1.45 - 2.15)",
            "🔥 High Risk / High Reward (Risiko-Siege, Handicaps & Hohe Quoten)"
        ],
        index=0
    )

    st.markdown("---")
    gen_typ = st.selectbox(
        "Wett-Typ wählen:",
        [
            "📊 Reine Einzelwetten",
            "🛡️ Multi-Ticket System (3 separate Scheine)", 
            "🎁 Freebet-Modus (Gratiswette maximieren)", 
            "🎯 Standard Kombiwette (Freie Anzahl Spiele)"
        ],
        index=0
    )

    kombi_anzahl = 3
    multi_budget = 20.0
    freebet_wert = 20.0

    if gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        freebet_wert = st.number_input("Wert deiner Freebet (€):", min_value=1.0, max_value=500.0, value=20.0, step=5.0)
    elif gen_typ == "🛡️ Multi-Ticket System (3 separate Scheine)":
        multi_budget = st.number_input("Gesamtbudget für alle 3 Scheine (€):", min_value=1.0, max_value=2000.0, value=20.0, step=5.0)
    elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anzahl_wetten = st.number_input("Anzahl Spiele im Kombischein (Min. 2):", min_value=2, max_value=10, value=3, step=1)

    st.markdown("---")
    generate_click = st.button("🚀 Live-Daten laden & Wettscheine berechnen", type="primary", use_container_width=True)

# --- ZEITRAUM UND DATUMS-EVALUATION ---
if "HEUTE" in gen_zeit_modus:
    dt_from, dt_to = today_de, today_de
elif "MORGEN" in gen_zeit_modus:
    dt_from, dt_to = tomorrow_de, tomorrow_de
elif "WOCHENENDE" in gen_zeit_modus:
    dt_from, dt_to = fri_de, sun_de
elif "DIESE WOCHE" in gen_zeit_modus:
    dt_from, dt_to = today_de, today_de + timedelta(days=7)
else:
    if kalender_auswahl and isinstance(kalender_auswahl, tuple) and len(kalender_auswahl) == 2:
        dt_from, dt_to = kalender_auswahl[0], kalender_auswahl[1]
    else:
        dt_from, dt_to = today_de, today_de + timedelta(days=3)

start_str_espn = dt_from.strftime("%Y%m%d")
end_str_espn = dt_to.strftime("%Y%m%d")

# --- GENERATOR ENGINE ---
if generate_click or 'matches_cache' not in st.session_state or not st.session_state['matches_cache']:
    if generate_click and not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Haken aus!")
    elif generate_click and not aktive_anbieter:
        st.error("Bitte wähle mindestens einen Wettanbieter aus!")
    elif generate_click and not erlaubte_maerkte:
        st.error("Bitte wähle mindestens einen Wettmarkt per Haken aus!")
    else:
        with st.spinner("Berechne Dixon-Coles Elo-Ratings & alle verfügbaren Wettmärkte..."):
            all_loaded_matches = []
            
            for liga_label in aktive_generator_ligen:
                if liga_label in OPENLIGA_SHORTCUTS:
                    shortcut = OPENLIGA_SHORTCUTS[liga_label]
                    raw_openliga = fetch_openliga_matches(shortcut)
                    for m in raw_openliga:
                        dt_str = m.get('matchDateTime')
                        if dt_str:
                            try:
                                dt = datetime.fromisoformat(dt_str)
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=tz_de)
                                else:
                                    dt = dt.astimezone(tz_de)
                                m_date = dt.date()
                                
                                if dt_from <= m_date <= dt_to:
                                    home = m['team1']['teamName']
                                    away = m['team2']['teamName']
                                    
                                    home_xg, away_xg = calculate_dynamic_xg(home, away)
                                    p_markets = calculate_poisson_markets(home_xg, away_xg)
                                    
                                    all_loaded_matches.append({
                                        "liga": liga_label,
                                        "home": home,
                                        "away": away,
                                        "date": m_date,
                                        "time_str": dt.strftime("%d.%m. - %H:%M Uhr"),
                                        "markets": p_markets
                                    })
                            except Exception:
                                continue

                elif liga_label in ESPN_LEAGUE_CODES:
                    code = ESPN_LEAGUE_CODES[liga_label]
                    raw_matches = fetch_espn_keyless_matches(code, start_str_espn, end_str_espn)
                    for m in raw_matches:
                        utc_str = m.get('utc_date')
                        if utc_str:
                            try:
                                utc_dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
                                de_dt = utc_dt.astimezone(tz_de)
                                m_date = de_dt.date()
                                
                                if dt_from <= m_date <= dt_to:
                                    home = m['home']
                                    away = m['away']
                                    
                                    home_xg, away_xg = calculate_dynamic_xg(home, away)
                                    p_markets = calculate_poisson_markets(home_xg, away_xg)
                                    
                                    all_loaded_matches.append({
                                        "liga": liga_label,
                                        "home": home,
                                        "away": away,
                                        "date": m_date,
                                        "time_str": de_dt.strftime("%d.%m. - %H:%M Uhr"),
                                        "markets": p_markets
                                    })
                            except Exception:
                                continue

            st.session_state['matches_cache'] = all_loaded_matches
            st.session_state['gen_typ'] = gen_typ
            st.session_state['multi_budget'] = float(multi_budget)
            st.session_state['freebet_wert'] = float(freebet_wert)
            if gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
                st.session_state['anzahl_wetten'] = int(anzahl_wetten)

matches = st.session_state.get('matches_cache', [])

# --- DYNAMISCHE KI MARKT-AUSWAHL ENGINE (MIT EV+ & KELLY) ---
def get_profile_pick_mixed(match, profile, checked_bookmakers, allowed_markets, bankroll, max_k_pct):
    mkts = match['markets']
    home, away = match['home'], match['away']
    
    reroll = st.session_state.get('reroll_key', 0)
    seed_raw = f"{home}_{away}_{profile}_{reroll}_{random.randint(1, 100000)}"
    match_seed = int(hashlib.md5(seed_raw.encode()).hexdigest(), 16)
    
    all_candidates = [
        {"tipp": f"Sieg {home} (1)", "prob": mkts['1X2']['1']['prob'], "base_q": mkts['1X2']['1']['base_quote'], "markt": "1X2 Siegwette 🎯", "key": "1x2_1", "kat": "1X2"},
        {"tipp": f"Sieg {away} (2)", "prob": mkts['1X2']['2']['prob'], "base_q": mkts['1X2']['2']['base_quote'], "markt": "1X2 Siegwette 🎯", "key": "1x2_2", "kat": "1X2"},
        {"tipp": "Unentschieden (X)", "prob": mkts['1X2']['X']['prob'], "base_q": mkts['1X2']['X']['base_quote'], "markt": "1X2 Siegwette 🎯", "key": "1x2_x", "kat": "1X2"},
        
        {"tipp": f"Doppelte Chance 1X ({home} / X)", "prob": mkts['DC']['1X']['prob'], "base_q": mkts['DC']['1X']['base_quote'], "markt": "Doppelte Chance 🛡️", "key": "dc_1x", "kat": "DC"},
        {"tipp": f"Doppelte Chance X2 (X / {away})", "prob": mkts['DC']['X2']['prob'], "base_q": mkts['DC']['X2']['base_quote'], "markt": "Doppelte Chance 🛡️", "key": "dc_x2", "kat": "DC"},
        {"tipp": f"Doppelte Chance 12 ({home} / {away})", "prob": mkts['DC']['12']['prob'], "base_q": mkts['DC']['12']['base_quote'], "markt": "Doppelte Chance 🛡️", "key": "dc_12", "kat": "DC"},
        
        {"tipp": f"Sieg {home} (Draw No Bet)", "prob": mkts['DNB']['1 DNB']['prob'], "base_q": mkts['DNB']['1 DNB']['base_quote'], "markt": "Head-to-Head (DNB) 🔄", "key": "dnb_1", "kat": "DNB"},
        {"tipp": f"Sieg {away} (Draw No Bet)", "prob": mkts['DNB']['2 DNB']['prob'], "base_q": mkts['DNB']['2 DNB']['base_quote'], "markt": "Head-to-Head (DNB) 🔄", "key": "dnb_2", "kat": "DNB"},
        
        {"tipp": "Über 0.5 Tore", "prob": mkts['Tore']['Über 0.5']['prob'], "base_q": mkts['Tore']['Über 0.5']['base_quote'], "markt": "Tor-Markt ⚽", "key": "o05", "kat": "Tore"},
        {"tipp": "Über 1.5 Tore", "prob": mkts['Tore']['Über 1.5']['prob'], "base_q": mkts['Tore']['Über 1.5']['base_quote'], "markt": "Tor-Markt ⚽", "key": "o15", "kat": "Tore"},
        {"tipp": "Über 2.5 Tore", "prob": mkts['Tore']['Über 2.5']['prob'], "base_q": mkts['Tore']['Über 2.5']['base_quote'], "markt": "Tor-Markt ⚽", "key": "o25", "kat": "Tore"},
        {"tipp": "Über 3.5 Tore", "prob": mkts['Tore']['Über 3.5']['prob'], "base_q": mkts['Tore']['Über 3.5']['base_quote'], "markt": "Tor-Markt ⚽", "key": "o35", "kat": "Tore"},
        {"tipp": "Unter 2.5 Tore", "prob": mkts['Tore']['Unter 2.5']['prob'], "base_q": mkts['Tore']['Unter 2.5']['base_quote'], "markt": "Tor-Markt ⚽", "key": "u25", "kat": "Tore"},
        {"tipp": "Unter 3.5 Tore", "prob": mkts['Tore']['Unter 3.5']['prob'], "base_q": mkts['Tore']['Unter 3.5']['base_quote'], "markt": "Tor-Markt ⚽", "key": "u35", "kat": "Tore"},
        
        {"tipp": f"{home} Über 0.5 Tore", "prob": mkts['TeamTore']['Heim Über 0.5']['prob'], "base_q": mkts['TeamTore']['Heim Über 0.5']['base_quote'], "markt": "Team-Tore ⚽", "key": "ho05", "kat": "TeamTore"},
        {"tipp": f"{home} Über 1.5 Tore", "prob": mkts['TeamTore']['Heim Über 1.5']['prob'], "base_q": mkts['TeamTore']['Heim Über 1.5']['base_quote'], "markt": "Team-Tore ⚽", "key": "ho15", "kat": "TeamTore"},
        {"tipp": f"{away} Über 0.5 Tore", "prob": mkts['TeamTore']['Auswärts Über 0.5']['prob'], "base_q": mkts['TeamTore']['Auswärts Über 0.5']['base_quote'], "markt": "Team-Tore ⚽", "key": "ao05", "kat": "TeamTore"},
        {"tipp": f"{away} Über 1.5 Tore", "prob": mkts['TeamTore']['Auswärts Über 1.5']['prob'], "base_q": mkts['TeamTore']['Auswärts Über 1.5']['base_quote'], "markt": "Team-Tore ⚽", "key": "ao15", "kat": "TeamTore"},
        
        {"tipp": "Beide Teams treffen - Ja", "prob": mkts['BTTS']['Ja']['prob'], "base_q": mkts['BTTS']['Ja']['base_quote'], "markt": "Beide treffen 🔥", "key": "btts_ja", "kat": "BTTS"},
        {"tipp": "Beide Teams treffen - Nein", "prob": mkts['BTTS']['Nein']['prob'], "base_q": mkts['BTTS']['Nein']['base_quote'], "markt": "Beide treffen 🔥", "key": "btts_nein", "kat": "BTTS"},
        
        {"tipp": f"{home} Handicap -1.5", "prob": mkts['Handicap']['Heim -1.5']['prob'], "base_q": mkts['Handicap']['Heim -1.5']['base_quote'], "markt": "Handicap (-1.5) ⚡", "key": "hc_h15", "kat": "Handicap"},
        {"tipp": f"{away} Handicap -1.5", "prob": mkts['Handicap']['Auswärts -1.5']['prob'], "base_q": mkts['Handicap']['Auswärts -1.5']['base_quote'], "markt": "Handicap (-1.5) ⚡", "key": "hc_a15", "kat": "Handicap"},
        
        {"tipp": f"1. Halbzeit: Sieg {home}", "prob": mkts['Halbzeit']['1. HT Sieg Heim']['prob'], "base_q": mkts['Halbzeit']['1. HT Sieg Heim']['base_quote'], "markt": "1. Halbzeit ⏱️", "key": "ht_1", "kat": "Halbzeit"},
        {"tipp": "1. Halbzeit: Unentschieden", "prob": mkts['Halbzeit']['1. HT Unentschieden']['prob'], "base_q": mkts['Halbzeit']['1. HT Unentschieden']['base_quote'], "markt": "1. Halbzeit ⏱️", "key": "ht_x", "kat": "Halbzeit"},
        {"tipp": f"1. Halbzeit: Sieg {away}", "prob": mkts['Halbzeit']['1. HT Sieg Auswärts']['prob'], "base_q": mkts['Halbzeit']['1. HT Sieg Auswärts']['base_quote'], "markt": "1. Halbzeit ⏱️", "key": "ht_2", "kat": "Halbzeit"},
        {"tipp": "1. Halbzeit: Über 0.5 Tore", "prob": mkts['Halbzeit']['1. HT Über 0.5']['prob'], "base_q": mkts['Halbzeit']['1. HT Über 0.5']['base_quote'], "markt": "1. Halbzeit ⏱️", "key": "hto05", "kat": "Halbzeit"},
        
        {"tipp": "Über 8.5 Eckbälle", "prob": mkts['Ecken']['Über 8.5 Ecken']['prob'], "base_q": mkts['Ecken']['Über 8.5 Ecken']['base_quote'], "markt": "Eckbälle ⛳", "key": "crn85", "kat": "Ecken"},
        {"tipp": "Über 10.5 Eckbälle", "prob": mkts['Ecken']['Über 10.5 Ecken']['prob'], "base_q": mkts['Ecken']['Über 10.5 Ecken']['base_quote'], "markt": "Eckbälle ⛳", "key": "crn105", "kat": "Ecken"},
        
        {"tipp": "Über 3.5 Karten", "prob": mkts['Karten']['Über 3.5 Karten']['prob'], "base_q": mkts['Karten']['Über 3.5 Karten']['base_quote'], "markt": "Karten 🟨", "key": "crd35", "kat": "Karten"},
        {"tipp": "Über 4.5 Karten", "prob": mkts['Karten']['Über 4.5 Karten']['prob'], "base_q": mkts['Karten']['Über 4.5 Karten']['base_quote'], "markt": "Karten 🟨", "key": "crd45", "kat": "Karten"},
        
        {"tipp": "Exaktes Ergebnis 1:0", "prob": mkts['Ergebnis']['Ergebnis 1:0']['prob'], "base_q": mkts['Ergebnis']['Ergebnis 1:0']['base_quote'], "markt": "Genaues Ergebnis 🎯", "key": "sc10", "kat": "Ergebnis"},
        {"tipp": "Exaktes Ergebnis 2:0", "prob": mkts['Ergebnis']['Ergebnis 2:0']['prob'], "base_q": mkts['Ergebnis']['Ergebnis 2:0']['base_quote'], "markt": "Genaues Ergebnis 🎯", "key": "sc20", "kat": "Ergebnis"},
        {"tipp": "Exaktes Ergebnis 2:1", "prob": mkts['Ergebnis']['Ergebnis 2:1']['prob'], "base_q": mkts['Ergebnis']['Ergebnis 2:1']['base_quote'], "markt": "Genaues Ergebnis 🎯", "key": "sc21", "kat": "Ergebnis"},
        {"tipp": "Exaktes Ergebnis 1:1", "prob": mkts['Ergebnis']['Ergebnis 1:1']['prob'], "base_q": mkts['Ergebnis']['Ergebnis 1:1']['base_quote'], "markt": "Genaues Ergebnis 🎯", "key": "sc11", "kat": "Ergebnis"},
        
        {"tipp": f"Sieg {home} & Beide treffen (BTTS)", "prob": mkts['KombiMaerkte']['Sieg Heim & BTTS Ja']['prob'], "base_q": mkts['KombiMaerkte']['Sieg Heim & BTTS Ja']['base_quote'], "markt": "Kombi (Sieg + BTTS) 🧱", "key": "hbtts", "kat": "KombiMaerkte"},
        {"tipp": f"Sieg {away} & Beide treffen (BTTS)", "prob": mkts['KombiMaerkte']['Sieg Auswärts & BTTS Ja']['prob'], "base_q": mkts['KombiMaerkte']['Sieg Auswärts & BTTS Ja']['base_quote'], "markt": "Kombi (Sieg + BTTS) 🧱", "key": "abtts", "kat": "KombiMaerkte"},
        {"tipp": f"Sieg {home} & Über 2.5 Tore", "prob": mkts['KombiMaerkte']['Sieg Heim & Über 2.5']['prob'], "base_q": mkts['KombiMaerkte']['Sieg Heim & Über 2.5']['base_quote'], "markt": "Kombi (Sieg + Tore) 🧱", "key": "ho25", "kat": "KombiMaerkte"},
        {"tipp": f"Sieg {away} & Über 2.5 Tore", "prob": mkts['KombiMaerkte']['Sieg Auswärts & Über 2.5']['prob'], "base_q": mkts['KombiMaerkte']['Sieg Auswärts & Über 2.5']['base_quote'], "markt": "Kombi (Sieg + Tore) 🧱", "key": "ao25", "kat": "KombiMaerkte"},
        
        {"tipp": f"HT/FT: Führung {home} / Sieg {home}", "prob": mkts['HTFT']['HT/FT: 1/1 (Heim/Heim)']['prob'], "base_q": mkts['HTFT']['HT/FT: 1/1 (Heim/Heim)']['base_quote'], "markt": "Halbzeit/Endstand ⏳", "key": "hf11", "kat": "HTFT"},
        {"tipp": f"HT/FT: Unentschieden HT / Sieg {home} FT", "prob": mkts['HTFT']['HT/FT: X/1 (Unentsch./Heim)']['prob'], "base_q": mkts['HTFT']['HT/FT: X/1 (Unentsch./Heim)']['base_quote'], "markt": "Halbzeit/Endstand ⏳", "key": "hfx1", "kat": "HTFT"},
        {"tipp": f"HT/FT: Führung {away} / Sieg {away}", "prob": mkts['HTFT']['HT/FT: 2/2 (Auswärts/Auswärts)']['prob'], "base_q": mkts['HTFT']['HT/FT: 2/2 (Auswärts/Auswärts)']['base_quote'], "markt": "Halbzeit/Endstand ⏳", "key": "hf22", "kat": "HTFT"},
        
        {"tipp": "Tore in beiden Halbzeiten - Ja", "prob": mkts['ToreBeideHT']['Tore in beiden Halbzeiten - Ja']['prob'], "base_q": mkts['ToreBeideHT']['Tore in beiden Halbzeiten - Ja']['base_quote'], "markt": "Tore in beiden HT ⏱️", "key": "tbht", "kat": "ToreBeideHT"}
    ]
    
    if allowed_markets:
        candidates = [c for c in all_candidates if c['kat'] in allowed_markets]
    else:
        candidates = all_candidates

    if not candidates:
        candidates = all_candidates

    if "Safe Mode" in profile:
        valid = [c for c in candidates if c['prob'] >= 60.0]
        if not valid:
            valid = sorted(candidates, key=lambda x: x['prob'], reverse=True)[:3]
    elif "High Risk" in profile:
        valid = [c for c in candidates if c['base_q'] >= 2.00]
        if not valid:
            valid = sorted(candidates, key=lambda x: x['base_q'], reverse=True)[:3]
    else:
        valid = [c for c in candidates if 1.40 <= c['base_q'] <= 2.20]
        if not valid:
            valid = sorted(candidates, key=lambda x: abs(x['base_q'] - 1.75))[:4]
            
    selected = valid[match_seed % len(valid)]

    base_q = selected['base_q']
    tipp_str = selected['tipp']
    prob_val = selected['prob']
    mkt_name = selected['markt']
    m_key = selected['key']

    best_bm, best_quote, all_bm_odds = get_best_bookmaker_odds(base_q, home, away, m_key, checked_bookmakers)
    bm_url = ANBIETER_URLS.get(best_bm, "https://www.tipico.de")
    
    # --- VALUE BET (EV+) & KELLY BERECHNUNG ---
    p_dec = prob_val / 100.0
    ev_val = round(((p_dec * best_quote) - 1.0) * 100.0, 1)
    
    # Fractional Kelly (Half Kelly for safety)
    if best_quote > 1.0 and p_dec > (1.0 / best_quote):
        b = best_quote - 1.0
        p = p_dec
        q = 1.0 - p
        f_star = (b * p - q) / b
        f_half = max(0.0, f_star * 0.5)
        f_capped = min(f_half, max_k_pct / 100.0)
        kelly_stake_eur = round(bankroll * f_capped, 2)
    else:
        kelly_stake_eur = round(bankroll * 0.01, 2)
    
    return {
        "tipp": tipp_str,
        "quote": best_quote,
        "prob": prob_val,
        "markt": mkt_name,
        "best_bookmaker": best_bm,
        "bookmaker_url": bm_url,
        "ev": ev_val,
        "kelly_stake": kelly_stake_eur
    }

# --- ERGEBNISSE ANZEIGEN ---
if not matches:
    st.info(f"ℹ️ Keine Ansetzungen für den ausgewählten Zeitraum ({dt_from.strftime('%d.%m.%Y')} - {dt_to.strftime('%d.%m.%Y')}) in den gewählten Ligen gefunden.")
elif not erlaubte_maerkte:
    st.warning("⚠️ Bitte wähle oben in den Einstellungen mindestens einen Wettmarkt aus!")
else:
    col_t_title, col_t_btn = st.columns([2.5, 1.5])
    with col_t_title:
        st.markdown(f"### 🛡️ Aktuelle KI-Scheine ({len(matches)} Spiele geladen)")
    with col_t_btn:
        if st.button("🎲 Neue Scheine generieren (Neu mischen)", type="primary", use_container_width=True, key="btn_shuffle"):
            st.session_state['reroll_key'] += 1
            st.rerun()

    g_typ = st.session_state.get('gen_typ', '📊 Reine Einzelwetten')
    
    current_reroll = st.session_state.get('reroll_key', 0)
    shuffled_matches = matches.copy()
    random.Random(current_reroll).shuffle(shuffled_matches)
    
    current_picks = []

    if g_typ == "📊 Reine Einzelwetten":
        for match in shuffled_matches:
            pick = get_profile_pick_mixed(match, risiko_profil, aktive_anbieter, erlaubte_maerkte, total_bankroll, max_kelly_pct)
            current_picks.append((match, pick))
            
            ev_badge = f'<span class="badge badge-ev">💎 EV: +{pick["ev"]}% Value</span>' if pick['ev'] > 0 else f'<span class="badge" style="background:#475569; color:#fff;">EV: {pick["ev"]}%</span>'
            
            st.markdown(f"""
                <div class="best-card">
                    <span class="badge badge-safe">🛡️ DIXON-COLES TIPP</span>
                    <span class="badge badge-market">{pick['markt']}</span>
                    {ev_badge}
                    <span class="badge badge-bookie">⭐ Bestes Angebot: {pick['best_bookmaker']}</span>
                    <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-left:4px;">{match['liga']}</span>
                    <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.15rem;">{match['home']} vs {match['away']}</h4>
                    <p style="color: #00d47e; font-size: 0.78rem; margin-bottom: 12px;">📅 {match['time_str']}</p>
                    <div style="background:#070a13; border:1px solid #1e293b; border-radius:10px; padding:12px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#94a3b8; font-size:0.8rem;">Empfohlener Tipp & Kelly-Einsatz:</span><br>
                            <b style="color:#ffffff; font-size:1rem;">{pick['tipp']}</b> <span style="color:#00d47e; font-weight:700;">(Empf. Einsatz: {pick['kelly_stake']} €)</span>
                        </div>
                        <div style="text-align:right;">
                            <span class="odds-tag">{pick['quote']}</span><br>
                            <span class="prob-tag">Wahrscheinlichkeit: {pick['prob']}%</span>
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
                        <span style="color:#94a3b8; font-size:0.8rem;">Höchstquote bei: <b style="color:#f59e0b;">{pick['best_bookmaker']}</b></span>
                        <a href="{pick['bookmaker_url']}" target="_blank" class="bookie-btn">🔗 Zu {pick['best_bookmaker']}</a>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    elif g_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anz_w = st.session_state.get('anzahl_wetten', 3)
        ausgewaehlte = shuffled_matches[:min(len(shuffled_matches), anz_w)]
        
        if len(ausgewaehlte) < 2:
            st.warning("⚠️ Nicht genügend Spiele im gewählten Zeitraum vorhanden, um eine Kombiwette mit deiner Wunschanzahl zu erstellen.")
        else:
            gesamtq = 1.0
            for m in ausgewaehlte:
                p = get_profile_pick_mixed(m, risiko_profil, aktive_anbieter, erlaubte_maerkte, total_bankroll, max_kelly_pct)
                gesamtq *= p['quote']
                current_picks.append((m, p))
                
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 2px solid #00d47e; border-radius: 14px; padding: 20px; text-align: center; margin-bottom: 20px;">
                    <span style="color: #94a3b8; font-size: 0.85rem; font-weight: 700;">GESAMTQUOTE DER KOMBI</span><br>
                    <span style="color: #00d47e; font-size: 2.3rem; font-weight: 800;">{round(gesamtq, 2)}</span>
                </div>
            """, unsafe_allow_html=True)

            for m, p in current_picks:
                st.markdown(f"""
                    <div class="bet-card">
                        <span class="badge badge-market">{p['markt']}</span>
                        <span class="badge badge-bookie">Bester Anbieter: {p['best_bookmaker']}</span>
                        <span class="badge" style="background-color: #1e293b; color: #94a3b8;">{m['liga']}</span>
                        <h4 style="color: #ffffff; margin: 10px 0 4px 0;">{m['home']} vs {m['away']}</h4>
                        <p style="color: #00d47e; font-size: 0.78rem; margin-bottom: 12px;">📅 {m['time_str']}</p>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #94a3b8; font-size: 0.9rem;">Tipp: <b style="color: #ffffff;">{p['tipp']}</b></span>
                            <span class="odds-tag">{p['quote']}</span>
                        </div>
                        <div style="text-align: right; margin-top: 10px;">
                            <a href="{p['bookmaker_url']}" target="_blank" class="bookie-btn">🔗 Bei {p['best_bookmaker']} platzieren</a>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    # BUTTON ZUM SPEICHERN DES SCHEINS
    if current_picks:
        if st.button("📌 Wettschein speichern", type="secondary"):
            ticket_entry = {
                "zeitpunkt": datetime.now(tz_de).strftime("%d.%m.%Y %H:%M"),
                "typ": g_typ,
                "picks": current_picks
            }
            st.session_state['saved_tickets'].append(ticket_entry)
            st.success("✅ Wettschein erfolgreich gespeichert!")

# --- GESPEICHERTE WETTSCHEINE & EXPORT SECTION ---
st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 30px 0;'>", unsafe_allow_html=True)
st.markdown("### 🗂️ Gespeicherte Wettscheine & CSV Export")

if not st.session_state['saved_tickets']:
    st.info("Bisher keine Scheine hinterlegt. Klicke oben auf '📌 Wettschein speichern'.")
else:
    export_rows = []
    text_share = "📱 *MEINE KI-WETTSCHEINE*\n\n"

    for idx, t in enumerate(st.session_state['saved_tickets'], 1):
        st.markdown(f"#### 🎫 Schein #{idx} ({t['typ']} — Speichertag: {t['zeitpunkt']})")
        
        ticket_text = f"🎫 *Schein #{idx} ({t['typ']})*\n"
        for m, p in t['picks']:
            st.write(f"• **{m['home']} vs {m['away']}** | Tipp: `{p['tipp']}` | Quote: `{p['quote']}` ({p['best_bookmaker']})")
            ticket_text += f"⚽ {m['home']} vs {m['away']} -> Tipp: {p['tipp']} @ {p['quote']} ({p['best_bookmaker']})\n"
            
            export_rows.append({
                "Schein_ID": idx,
                "Datum": t['zeitpunkt'],
                "Typ": t['typ'],
                "Heim": m['home'],
                "Auswärts": m['away'],
                "Tipp": p['tipp'],
                "Quote": p['quote'],
                "Anbieter": p['best_bookmaker'],
                "Empf_Einsatz_EUR": p.get('kelly_stake', 0.0)
            })
        
        text_share += ticket_text + "\n"

    st.markdown("---")
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        # CSV DOWNLOAD
        df_export = pd.DataFrame(export_rows)
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Wettscheine als CSV herunterladen",
            data=csv_data,
            file_name=f"wettscheine_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
    with col_exp2:
        # WHATSAPP / TELEGRAM TEXT FORMAT
        st.markdown("**📋 Teilen-Text (Kopieren für WhatsApp/Telegram):**")
        st.code(text_share, language="markdown")

    if st.button("🗑️ Alle gespeicherten Scheine löschen"):
        st.session_state['saved_tickets'] = []
        st.rerun()

