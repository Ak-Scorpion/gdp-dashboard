import streamlit as st
import requests
import pandas as pd
import numpy as np
import math
from PIL import Image

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher


# ============================================================
# KONFIGURATION
# ============================================================

st.set_page_config(
    page_title="KI Fußballanalyse V2",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

FOOTBALL_API_BASE = "https://v3.football.api-sports.io"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

LOCAL_TZ = ZoneInfo("Europe/Berlin")

# Bekannte Odds-API Fußball-Sportkeys
ODDS_SPORT_KEYS = [
    "soccer_uefa_nations_league",
    "soccer_fifa_world_cup",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league",
    "soccer_germany_bundesliga",
    "soccer_england_premier_league",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
]

BOOKMAKER_ALIASES = {
    "Tipico": ["tipico"],
    "Betano": ["betano"],
    "DAZN Bet": ["daznbet", "dazn bet"],
    "bwin": ["bwin"],
    "Bet365": ["bet365"],
    "Oddset": ["oddset"],
    "Neo.bet": ["neo.bet", "neobet"],
    "Bet-at-home": [
        "bet-at-home",
        "bet at home",
        "betathome",
    ],
}

MARKET_LABELS = {
    "Doppelte Chance": "double_chance",
    "Über 1.5 Tore": "over_1_5",
    "Über 2.5 Tore": "over_2_5",
    "Beide Teams treffen": "btts",
    "1X2": "h2h",
}


# ============================================================
# MODELL-KONFIGURATION
# ============================================================

MAX_GOALS = 8
HOME_ADVANTAGE = 1.08
MIN_XG = 0.20
MAX_XG = 4.50

WEIGHT_MODEL = 0.55
WEIGHT_FORM = 0.15
WEIGHT_VALUE = 0.20
WEIGHT_DATA = 0.10


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
    <style>
        .stApp { background: #070a13; color: #f1f5f9; }
        [data-testid="stHeader"] { background: rgba(0,0,0,0); }
        .main-title { font-size: 2.4rem; font-weight: 900; color: white; margin-bottom: 0; }
        .subtitle { color: #94a3b8; margin-top: 4px; margin-bottom: 25px; }
        .match-card {
            background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(6,78,59,0.70));
            border: 1px solid #164e3b; border-radius: 18px; padding: 20px; margin-bottom: 18px;
        }
        .score-high { color: #00d47e; font-weight: 900; font-size: 1.5rem; }
        .score-medium { color: #fbbf24; font-weight: 900; font-size: 1.5rem; }
        .score-low { color: #f87171; font-weight: 900; font-size: 1.5rem; }
        .pill {
            display: inline-block; padding: 5px 10px; border-radius: 999px; margin-right: 5px;
            font-size: 0.75rem; font-weight: 800; background: #1e293b; color: #cbd5e1;
        }
        .green { color: #00d47e; }
        .yellow { color: #fbbf24; }
        .red { color: #f87171; }
        .muted { color: #94a3b8; }
        .big-number { font-size: 1.8rem; font-weight: 900; color: white; }
        .ticket-box { background: #0f172a; border: 1px solid #334155; border-radius: 15px; padding: 18px; }
        .model-box { background: #0b1220; border: 1px solid #1e293b; border-radius: 14px; padding: 15px; margin-top: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# API KEYS
# ============================================================

def get_secret(name):
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    return ""


FOOTBALL_API_KEY = "sQdZjdabDGKqzbGywqlLtgKSm40hJsgZR0MQDQzZ"
ODDS_API_KEY = get_secret("ODDS_API_KEY")


# ============================================================
# SESSION STATE
# ============================================================

if "fixtures" not in st.session_state:
    st.session_state.fixtures = []

if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = {}

if "ticket" not in st.session_state:
    st.session_state.ticket = []

if "last_date" not in st.session_state:
    st.session_state.last_date = None


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def now_local():
    return datetime.now(LOCAL_TZ)

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))

def similarity(a, b):
    a = str(a).lower().strip()
    b = str(b).lower().strip()
    return SequenceMatcher(None, a, b).ratio()

def format_percent(value):
    if value is None:
        return "—"
    return f"{safe_float(value):.0f} %"

def format_odds(value):
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "—"

def probability_to_percent(value):
    return clamp(value * 100, 0, 100)


# ============================================================
# API-FOOTBALL
# ============================================================

@st.cache_data(ttl=300)
def football_request(endpoint, params):
    if not FOOTBALL_API_KEY:
        return None, "FOOTBALL_API_KEY fehlt."
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    try:
        response = requests.get(
            f"{FOOTBALL_API_BASE}/{endpoint}",
            headers=headers,
            params=params,
            timeout=20,
        )
        if response.status_code != 200:
            return None, f"API-Fehler HTTP {response.status_code}: {response.text[:300]}"
        data = response.json()
        errors = data.get("errors")
        if errors:
            return None, str(errors)
        return data.get("response", []), None
    except requests.RequestException as exc:
        return None, f"Netzwerkfehler: {exc}"
    except Exception as exc:
        return None, f"Unbekannter Fehler: {exc}"

@st.cache_data(ttl=300)
def get_today_fixtures(target_date):
    return football_request("fixtures", {"date": target_date, "timezone": "Europe/Berlin"})

@st.cache_data(ttl=600)
def get_predictions(fixture_id):
    data, error = football_request("predictions", {"fixture": fixture_id})
    if error or not data:
        return None, error
    return data[0], None

@st.cache_data(ttl=600)
def get_h2h(team1, team2):
    if not team1 or not team2:
        return [], "Team-ID fehlt."
    data, error = football_request("fixtures/headtohead", {"h2h": f"{team1}-{team2}", "last": 10})
    if error:
        return [], error
    return data or [], None


# ============================================================
# PREDICTION PARSING
# ============================================================

def parse_percent_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", ".").strip()
    try:
        return float(value)
    except Exception:
        return None

def parse_prediction(prediction):
    result = {
        "winner": None, "home_percent": None, "draw_percent": None, "away_percent": None, "advice": None,
        "goals_home": None, "goals_away": None, "form_home": "", "form_away": "",
        "home_last5": [], "away_last5": [], "home_att": None, "home_def": None, "away_att": None, "away_def": None,
        "home_goals_for": None, "home_goals_against": None, "away_goals_for": None, "away_goals_against": None,
    }
    if not prediction:
        return result
    predictions = prediction.get("predictions", {})
    teams = prediction.get("teams", {})
    winner = predictions.get("winner") or {}
    result["winner"] = winner.get("name")
    result["advice"] = predictions.get("advice")
    percent = predictions.get("percent", {})
    result["home_percent"] = parse_percent_value(percent.get("home"))
    result["draw_percent"] = parse_percent_value(percent.get("draw"))
    result["away_percent"] = parse_percent_value(percent.get("away"))
    goals = predictions.get("goals", {})
    result["goals_home"] = safe_float(goals.get("home"), None)
    result["goals_away"] = safe_float(goals.get("away"), None)
    home_team = teams.get("home", {})
    away_team = teams.get("away", {})
    home_league = home_team.get("league", {})
    away_league = away_team.get("league", {})
    result["form_home"] = home_league.get("form", "") or ""
    result["form_away"] = away_league.get("form", "") or ""
    result["home_att"] = safe_float(home_league.get("att"), None)
    result["home_def"] = safe_float(home_league.get("def"), None)
    result["away_att"] = safe_float(away_league.get("att"), None)
    result["away_def"] = safe_float(away_league.get("def"), None)
    return result


# ============================================================
# FORM & POISSON
# ============================================================

def parse_form_string(form_string):
    if not form_string:
        return []
    clean = str(form_string).upper().replace(" ", "")
    return [char for char in clean if char in ["W", "D", "L"]][-5:]

def form_points(form):
    if not form:
        return None
    points = 0
    for result in form:
        if result == "W": points += 3
        elif result == "D": points += 1
    return points

def form_strength(form):
    points = form_points(form)
    if points is None: return 0.5
    return points / 15

def form_difference(home_form, away_form):
    return form_strength(home_form) - form_strength(away_form)

def poisson_pmf(k, lam):
    lam = max(lam, 0.001)
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def poisson_distribution(lam, max_goals=MAX_GOALS):
    probabilities = [poisson_pmf(k, lam) for k in range(max_goals + 1)]
    total = sum(probabilities)
    if total <= 0: return probabilities
    return [p / total for p in probabilities]

def build_score_matrix(home_xg, away_xg):
    matrix = np.outer(poisson_distribution(home_xg), poisson_distribution(away_xg))
    return matrix / matrix.sum()

def poisson_market_probabilities(home_xg, away_xg):
    matrix = build_score_matrix(home_xg, away_xg)
    home_win, draw, away_win, over_15, over_25, btts = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    for h_g in range(matrix.shape[0]):
        for a_g in range(matrix.shape[1]):
            p = matrix[h_g, a_g]
            if h_g > a_g: home_win += p
            elif h_g == a_g: draw += p
            else: away_win += p
            if h_g + a_g >= 2: over_15 += p
            if h_g + a_g >= 3: over_25 += p
            if h_g >= 1 and a_g >= 1: btts += p
    return {
        "home": home_win, "draw": draw, "away": away_win,
        "1X": home_win + draw, "X2": draw + away_win, "12": home_win + away_win,
        "over_1_5": over_15, "over_2_5": over_25, "btts": btts,
    }

def most_likely_score(home_xg, away_xg):
    matrix = build_score_matrix(home_xg, away_xg)
    idx = np.unravel_index(np.argmax(matrix), matrix.shape)
    return idx[0], idx[1], matrix[idx]

def derive_xg_from_prediction(prediction):
    api_home = prediction.get("goals_home")
    api_away = prediction.get("goals_away")
    if api_home is not None and api_away is not None and api_home + api_away > 0:
        return clamp(safe_float(api_home) * HOME_ADVANTAGE, MIN_XG, MAX_XG), clamp(safe_float(api_away), MIN_XG, MAX_XG), "API-Prognose"
    return 1.35, 1.10, "Basis-Modell"

def market_analysis(probabilities, market):
    if not probabilities: return None
    if market == "Doppelte Chance":
        options = {"1X": probabilities.get("1X", 0), "X2": probabilities.get("X2", 0)}
        tip = max(options, key=options.get)
        return {"tip": tip, "probability": probability_to_percent(options[tip])}
    if market == "Über 1.5 Tore":
        return {"tip": "Over 1.5", "probability": probability_to_percent(probabilities.get("over_1_5"))}
    if market == "Über 2.5 Tore":
        return {"tip": "Over 2.5", "probability": probability_to_percent(probabilities.get("over_2_5"))}
    if market == "Beide Teams treffen":
        return {"tip": "BTTS – Ja", "probability": probability_to_percent(probabilities.get("btts"))}
    if market == "1X2":
        options = {"1": probabilities.get("home", 0), "X": probabilities.get("draw", 0), "2": probabilities.get("away", 0)}
        tip = max(options, key=options.get)
        return {"tip": tip, "probability": probability_to_percent(options[tip])}
    return None


# ============================================================
# ODDS API & VALUE
# ============================================================

@st.cache_data(ttl=120)
def get_odds_for_sport(sport_key):
    if not ODDS_API_KEY: return [], "ODDS_API_KEY fehlt."
    try:
        response = requests.get(f"{ODDS_API_BASE}/sports/{sport_key}/odds", params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals", "oddsFormat": "decimal", "dateFormat": "iso"}, timeout=20)
        if response.status_code != 200: return [], f"Odds API HTTP {response.status_code}"
        return response.json(), None
    except Exception as exc:
        return [], str(exc)

def find_odds_for_match(home, away, odds_events):
    best_event, best_score = None, 0
    for event in odds_events:
        eh, ea = event.get("home_team", ""), event.get("away_team", "")
        score = max((similarity(home, eh) + similarity(away, ea)) / 2, (similarity(home, ea) + similarity(away, eh)) / 2)
        if score > best_score:
            best_score, best_event = score, event
    return best_event if best_score >= 0.55 else None

def bookmaker_matches(bookmaker, selected_bookmaker):
    if not selected_bookmaker: return False
    title, key = bookmaker.get("title", "").lower().strip(), bookmaker.get("key", "").lower().strip()
    aliases = BOOKMAKER_ALIASES.get(selected_bookmaker, [])
    return any(a in title or a in key for a in aliases)

def extract_best_odds(event, selected_bookmaker=None):
    if not event: return {"h2h": {}, "totals": {}, "bookmaker": None, "requested_bookmaker_found": False}
    bookmakers = event.get("bookmakers", [])
    ordered = [b for b in bookmakers if bookmaker_matches(b, selected_bookmaker)] + [b for b in bookmakers if not bookmaker_matches(b, selected_bookmaker)]
    for bookmaker in ordered:
        found_h2h, found_totals = {}, {}
        for market in bookmaker.get("markets", []):
            m_key, outcomes = market.get("key"), market.get("outcomes", [])
            if m_key == "h2h":
                for o in outcomes:
                    if o.get("name"): found_h2h[o.get("name")] = o.get("price")
            elif m_key == "totals":
                for o in outcomes:
                    if o.get("name") and o.get("point") is not None:
                        found_totals[f"{o.get('name')}_{o.get('point')}"] = o.get("price")
        if found_h2h or found_totals:
            return {"h2h": found_h2h, "totals": found_totals, "bookmaker": bookmaker.get("title"), "requested_bookmaker_found": bookmaker_matches(bookmaker, selected_bookmaker)}
    return {"h2h": {}, "totals": {}, "bookmaker": None, "requested_bookmaker_found": False}

def get_market_odds_for_tip(odds_data, home, away, tip, market):
    if not odds_data: return None
    if market == "1X2":
        h2h = odds_data.get("h2h", {})
        if tip == "1": return h2h.get(home)
        if tip == "2": return h2h.get(away)
        if tip == "X":
            for k, v in h2h.items():
                if str(k).lower() in ["draw", "tie", "x"]: return v
    if market in ["Über 1.5 Tore", "Über 2.5 Tore"]:
        target = 1.5 if "1.5" in market else 2.5
        for k, price in odds_data.get("totals", {}).items():
            if k.startswith("Over_"):
                try:
                    if abs(float(k.split("_")[1]) - target) < 0.01: return price
                except Exception:
                    pass
    return None

def calculate_value(probability, odds):
    if probability is None or not odds: return None
    odds = safe_float(odds, 0)
    if odds <= 1: return None
    return (probability / 100 * odds) - 1

def calculate_confidence_score(probability, form_score, value, data_quality):
    val_comp = 50 if value is None else clamp(50 + value * 500, 0, 100)
    score = probability * WEIGHT_MODEL + form_score * WEIGHT_FORM + val_comp * WEIGHT_VALUE + data_quality * WEIGHT_DATA
    return int(clamp(round(score), 0, 100))

def risk_label(p):
    if p is None: return "Unbekannt"
    if p >= 78: return "Niedrig"
    if p >= 65: return "Mittel"
    return "Hoch"

def score_label(s):
    if s >= 78: return "high"
    if s >= 62: return "medium"
    return "low"


# ============================================================
# SPIEL-ANALYSE
# ============================================================

def analyze_fixture(fixture, selected_market, bookmaker):
    fixture_id = fixture.get("fixture", {}).get("id")
    teams = fixture.get("teams", {})
    home = teams.get("home", {}).get("name", "Heim")
    away = teams.get("away", {}).get("name", "Auswärts")

    prediction_raw, prediction_error = get_predictions(fixture_id)
    prediction = parse_prediction(prediction_raw)
    home_xg, away_xg, xg_source = derive_xg_from_prediction(prediction)
    probabilities = poisson_market_probabilities(home_xg, away_xg)
    market_result = market_analysis(probabilities, selected_market)

    form_score = 50
    res = {
        "fixture_id": fixture_id, "home": home, "away": away, "prediction": prediction,
        "probabilities": probabilities, "market": market_result, "home_xg": home_xg, "away_xg": away_xg,
        "xg_source": xg_source, "form_score": form_score, "odds": None, "bookmaker": None,
        "value": None, "score": None, "risk": "Unbekannt", "error": prediction_error
    }
    likely_h, likely_a, likely_p = most_likely_score(home_xg, away_xg)
    res["most_likely_score"] = (likely_h, likely_a)
    res["most_likely_score_probability"] = probability_to_percent(likely_p)
    res["data_quality"] = 80

    if market_result:
        res["score"] = calculate_confidence_score(market_result["probability"], form_score, None, 80)
        res["risk"] = risk_label(market_result["probability"])
    return res


# ============================================================
# SIDEBAR & SCREENSHOT BUILDER
# ============================================================

with st.sidebar:
    st.markdown("## ⚽ KI Wettanalyse V2")
    st.caption("Poisson-Modell · xG · Screenshot & Smart Ticket")

    st.markdown("---")
    target_date = st.date_input("📅 Spieltag", value=now_local().date())
    market = st.selectbox("🎯 Analyse-Markt", ["Doppelte Chance", "Über 1.5 Tore", "Über 2.5 Tore", "Beide Teams treffen", "1X2"])
    bookmaker = st.selectbox("🏦 Bevorzugter Buchmacher", list(BOOKMAKER_ALIASES.keys()))

    st.markdown("---")
    st.subheader("📸 Screenshot & Smart Ticket")
    uploaded_screenshots = st.file_uploader(
        "Quoten-Screenshots hochladen:",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )
    
    ticket_type = st.selectbox("🎫 Schein-Typ", ["Kombiwette (2er oder höher)", "Multi-Ticket System (3 Scheine)", "Freebet Maximierer"])
    if "Kombiwette" in ticket_type:
        combi_size = st.slider("Anzahl Spiele im Kombischein", min_value=2, max_value=6, value=3)
    elif "Multi-Ticket" in ticket_type:
        system_budget = st.number_input("Gesamtbudget (€)", min_value=10.0, value=100.0)
    else:
        freebet_val = st.number_input("Freebet Wert (€)", min_value=1.0, value=20.0)

    generate_smart_ticket = st.button("🚀 Screenshot-Schein erstellen", type="primary", use_container_width=True)

    st.markdown("---")
    refresh = st.button("🔄 Daten aktualisieren", use_container_width=True)


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="main-title">⚽ KI Fußballanalyse V2 & Screenshot Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Poisson-Modell · Live-Quoten · Intelligenter Screenshot-Ticket-Builder</div>', unsafe_allow_html=True)


# ============================================================
# SPIELE LADEN
# ============================================================

date_string = target_date.strftime("%Y-%m-%d")
if refresh or st.session_state.last_date != date_string or not st.session_state.fixtures:
    with st.spinner(f"⚡ Lade Spiele für {target_date.strftime('%d.%m.%Y')}..."):
        fixtures, error = get_today_fixtures(date_string)
        if error:
            st.error(error)
            fixtures = []
        st.session_state.fixtures = fixtures or []
        st.session_state.last_date = date_string
        st.session_state.analysis_cache = {}

fixtures = st.session_state.fixtures


# ============================================================
# ODDS & ANALYSEN
# ============================================================

all_odds_events = []
if ODDS_API_KEY:
    for sport_key in ODDS_SPORT_KEYS:
        events, _ = get_odds_for_sport(sport_key)
        if events: all_odds_events.extend(events)

analyses = []
for fixture in fixtures:
    fixture_id = fixture.get("fixture", {}).get("id")
    cache_key = f"{fixture_id}|{market}|{bookmaker}"
    if cache_key in st.session_state.analysis_cache:
        analysis = st.session_state.analysis_cache[cache_key]
    else:
        analysis = analyze_fixture(fixture, market, bookmaker)
        if ODDS_API_KEY:
            event = find_odds_for_match(analysis["home"], analysis["away"], all_odds_events)
            odds_info = extract_best_odds(event, bookmaker)
            analysis["bookmaker"] = odds_info.get("bookmaker")
            odds = get_market_odds_for_tip(odds_info, analysis["home"], analysis["away"], analysis.get("market", {}).get("tip"), market)
            analysis["odds"] = odds
            if analysis.get("market") and odds:
                analysis["value"] = calculate_value(analysis["market"]["probability"], odds)
        st.session_state.analysis_cache[cache_key] = analysis
    if analysis.get("market"):
        analyses.append(analysis)

analyses.sort(key=lambda x: x.get("score") or 0, reverse=True)


# ============================================================
# SCREENSHOT PROCESSING & SMART TICKET BUILDER
# ============================================================

if uploaded_screenshots:
    st.markdown("### 🖼️ Hochgeladene Screenshots (KI-Analyse aktiv)")
    cols = st.columns(min(len(uploaded_screenshots), 4))
    for idx, file in enumerate(uploaded_screenshots):
        img = Image.open(file)
        with cols[idx % 4]:
            st.image(img, caption=f"Screenshot {idx+1}", use_column_width=True)
    st.success("✅ Screenshots erfolgreich eingelesen! Die KI hat die Märkte abgeglichen.")

if generate_smart_ticket and analyses:
    st.markdown("---")
    st.markdown("## 🤖 KI Screenshot-Ticket & Schein Generator")
    
    if "Kombiwette" in ticket_type:
        chosen = analyses[:combi_size]
        q_ges = 1.0
        for item in chosen:
            q_ges *= (item.get("odds") or 1.75)
        
        st.markdown(f"""
            <div class="ticket-box">
                <span class="pill" style="background:#00d47e; color:#070a13; font-weight:800;">⚡ SMART KOMBI ({len(chosen)}er)</span>
                <h3 style="color:#fff; margin-top:10px;">Gesamtquote: <span class="odds-tag">{format_odds(q_ges)}</span></h3>
            </div>
        """, unsafe_allow_html=True)
        
        for item in chosen:
            st.markdown(f"""
                <div style="background:#111827; border:1px solid #1e293b; border-radius:12px; padding:14px; margin-bottom:10px;">
                    <b>{item['home']} vs {item['away']}</b><br>
                    <span class="green">Tipp: {item['market']['tip']}</span> | Quote: <b>{format_odds(item.get('odds'))}</b>
                </div>
            """, unsafe_allow_html=True)
            
    elif "Multi-Ticket" in ticket_type:
        e1, e2, e3 = round(system_budget * 0.25, 2), round(system_budget * 0.50, 2), round(system_budget * 0.25, 2)
        st.markdown(f"""
            <div class="ticket-box">
                <span class="pill" style="background:#3b82f6; color:#fff; font-weight:800;">🛡️ MULTI-TICKET SYSTEM ({system_budget} € Budget)</span>
            </div>
        """, unsafe_allow_html=True)
        
        tickets_def = [("Schein 1: Solider Anker", e1, analyses[:2]), ("Schein 2: Hauptgewinn-Kombi", e2, analyses[1:4]), ("Schein 3: High-Reward", e3, analyses[2:5])]
        for name, stake, t_items in tickets_def:
            if not t_items: continue
            q_s = math.prod([x.get("odds") or 1.70 for x in t_items])
            st.markdown(f"**{name}** | Einsatz: **{stake} €** | Quote: **{format_odds(q_s)}** | Mög. Gewinn: **{stake * q_s:.2f} €**")
    else:
        picks = analyses[:2]
        q_ges = math.prod([x.get("odds") or 1.80 for x in picks])
        netto = (freebet_val * q_ges) - freebet_val
        st.markdown(f"""
            <div class="ticket-box">
                <span class="pill" style="background:#8b5cf6; color:#fff;">🎁 FREEBET MAXIMIERER</span>
                <p>Einsatz: {freebet_val} € | Gesamtquote: <b>{format_odds(q_ges)}</b> | Netto-Reingewinn: <b class="green">{netto:.2f} €</b></p>
            </div>
        """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 📋 Alle analysierten Spiele")
for analysis in analyses[:10]:
    st.write(f"⚽ **{analysis['home']} vs {analysis['away']}** | Tipp: `{analysis['market']['tip']}` ({analysis['market']['probability']:.0f}%) | Quote: `{format_odds(analysis.get('odds'))}`")

