import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from itertools import combinations

# ============================================================
# WETT-KI – AKTUALISIERTE VERSION MIT HINTERLEGTEN KEYS
# ============================================================

st.set_page_config(
    page_title="WETT-KI",
    page_icon="⚽",
    layout="wide"
)

FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
ODDS_API_URL = "https://api.the-odds-api.com/v4"
LOCAL_TZ = "Europe/Berlin"

LEAGUES = {
    "Premier League": {"football_data": "PL", "odds": "soccer_epl"},
    "Bundesliga": {"football_data": "BL1", "odds": "soccer_germany_bundesliga"},
    "La Liga": {"football_data": "PD", "odds": "soccer_spain_la_liga"},
    "Serie A": {"football_data": "SA", "odds": "soccer_italy_serie_a"},
    "Ligue 1": {"football_data": "FL1", "odds": "soccer_france_ligue_one"},
    "Champions League": {"football_data": "CL", "odds": "soccer_uefa_champs_league"},
    "Europa League": {"football_data": "EL", "odds": "soccer_uefa_europa_league"},
    "Conference League": {"football_data": "EC", "odds": "soccer_uefa_europa_conference_league"},
}

if "football_token" not in st.session_state:
    st.session_state.football_token = "1e330696e0324932848d33cc95be84f0"

if "odds_key" not in st.session_state:
    st.session_state.odds_key = "d0d0d6f9c7c493345eee17b80f3ded05"

if "fixtures" not in st.session_state:
    st.session_state.fixtures = pd.DataFrame()
if "last_update" not in st.session_state:
    st.session_state.last_update = None
if "errors" not in st.session_state:
    st.session_state.errors = []

def utc_now():
    return datetime.now(timezone.utc)

def safe_float(value, default=None):
    try:
        return float(value) if value is not None else default
    except Exception:
        return default

def parse_utc(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def format_local_datetime(value):
    dt = parse_utc(value)
    if dt is None:
        return "—"
    try:
        local_dt = dt.astimezone(ZoneInfo(LOCAL_TZ))
        return local_dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt.strftime("%d.%m.%Y %H:%M")

def get_week_dates():
    now_local = datetime.now(ZoneInfo(LOCAL_TZ))
    today = now_local.date()
    weekday = today.weekday()
    days = (4 - weekday) % 7
    start = today + timedelta(days=days)
    return [start + timedelta(days=i) for i in range(7)]

def normalize_name(name):
    if not name:
        return ""
    replacements = {" FC": "", " CF": "", " AFC": "", " United": "", " Utd": "", "Football Club": ""}
    result = str(name).strip()
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result.lower().replace(".", "").replace("-", " ").replace("'", "").strip()

def names_match(a, b):
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return False
    return a == b or a in b or b in a

@st.cache_data(ttl=300)
def api_get_cached(url, headers=None, params=None):
    try:
        response = requests.get(url, headers=headers, params=params, timeout=25)
        if response.status_code == 200:
            return response.json(), None
        return None, f"HTTP {response.status_code}"
    except Exception as e:
        return None, str(e)

def get_current_fixtures(token, competition_codes, start_date, end_date):
    url = f"{FOOTBALL_DATA_URL}/matches"
    headers = {"X-Auth-Token": token}
    params = {
        "dateFrom": start_date.isoformat(),
        "dateTo": (end_date + timedelta(days=1)).isoformat(),
        "competitions": ",".join(competition_codes),
        "limit": 500,
    }
    data, error = api_get_cached(url, headers=headers, params=params)
    if error:
        return [], error

    matches = data.get("matches", [])
    rows = []
    current_time = utc_now()

    for match in matches:
        utc_date = parse_utc(match.get("utcDate"))
        if utc_date is None or utc_date <= current_time:
            continue
        status = str(match.get("status", "")).upper()
        if status in {"CANCELLED", "POSTPONED", "SUSPENDED", "FINISHED", "IN_PLAY", "PAUSED"}:
            continue

        comp = match.get("competition", {})
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        home_name = home.get("name") or home.get("shortName")
        away_name = away.get("name") or away.get("shortName")

        if not home_name or not away_name:
            continue

        rows.append({
            "match_id": match.get("id"),
            "competition_code": comp.get("code"),
            "league": comp.get("name"),
            "utcDate": utc_date,
            "home": home_name,
            "away": away_name,
            "status": status,
        })
    return rows, None

def get_historical_matches(token, competition_codes, days_back=180):
    end_date = utc_now().date()
    start_date = end_date - timedelta(days=days_back)
    url = f"{FOOTBALL_DATA_URL}/matches"
    headers = {"X-Auth-Token": token}
    params = {
        "dateFrom": start_date.isoformat(),
        "dateTo": end_date.isoformat(),
        "competitions": ",".join(competition_codes),
        "status": "FINISHED",
        "limit": 500,
    }
    data, error = api_get_cached(url, headers=headers, params=params)
    if error:
        return [], error
    return data.get("matches", []), None

def build_team_stats(historical_matches):
    stats = {}
    for match in historical_matches:
        if str(match.get("status", "")).upper() != "FINISHED":
            continue
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        home_name = home.get("name") or home.get("shortName")
        away_name = away.get("name") or away.get("shortName")
        score = match.get("score", {}).get("fullTime", {})
        hg, ag = safe_float(score.get("home")), safe_float(score.get("away"))
        if hg is None or ag is None:
            continue

        for team in [home_name, away_name]:
            if team not in stats:
                stats[team] = {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "home_played": 0, "home_gf": 0, "home_ga": 0, "recent": []}

        hs, aws = stats[home_name], stats[away_name]
        hs["played"] += 1; hs["gf"] += hg; hs["ga"] += ag; hs["home_played"] += 1; hs["home_gf"] += hg; hs["home_ga"] += ag
        aws["played"] += 1; aws["gf"] += ag; aws["ga"] += hg

        if hg > ag:
            hs["wins"] += 1; aws["losses"] += 1; hs["recent"].append("W"); aws["recent"].append("L")
        elif hg < ag:
            hs["losses"] += 1; aws["wins"] += 1; hs["recent"].append("L"); aws["recent"].append("W")
        else:
            hs["draws"] += 1; aws["draws"] += 1; hs["recent"].append("D"); aws["recent"].append("D")
    return stats

def calculate_advanced_markets(home_lambda, away_lambda):
    p1, px, p2 = 0.0, 0.0, 0.0
    btts_yes, over_25 = 0.0, 0.0

    for h in range(0, 9):
        for a in range(0, 9):
            p_h = math.exp(-home_lambda) * (home_lambda ** h) / math.factorial(h)
            p_a = math.exp(-away_lambda) * (away_lambda ** a) / math.factorial(a)
            p = p_h * p_a

            if h > a: p1 += p
            elif h == a: px += p
            else: p2 += p

            if h > 0 and a > 0: btts_yes += p
            if (h + a) > 2.5: over_25 += p

    total = p1 + px + p2
    if total <= 0:
        return {"1": 1/3, "X": 1/3, "2": 1/3, "btts": 0.5, "over25": 0.5}

    return {
        "1": p1 / total,
        "X": px / total,
        "2": p2 / total,
        "btts": btts_yes / total,
        "over25": over_25 / total
    }

def calculate_model(home, away, stats):
    hs, aws = stats.get(home), stats.get(away)
    home_attack = (hs["home_gf"] / max(hs["home_played"], 1)) if hs else 1.45
    home_defence = (hs["home_ga"] / max(hs["home_played"], 1)) if hs else 1.20
    away_attack = (aws["gf"] / max(aws["played"], 1)) if aws else 1.15
    away_defence = (aws["ga"] / max(aws["played"], 1)) if aws else 1.35

    home_lambda = min(max((0.55 * home_attack + 0.45 * away_defence) * 1.08, 0.25), 3.50)
    away_lambda = min(max((0.55 * away_attack + 0.45 * home_defence), 0.20), 3.20)

    return calculate_advanced_markets(home_lambda, away_lambda)

def get_fresh_odds(odds_key, sport_key):
    if not odds_key:
        return []
    url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
    params = {"apiKey": odds_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
    data, error = api_get_cached(url, params=params)
    return data if isinstance(data, list) else []

def extract_best_odds(event):
    result = {"odd_1": None, "odd_x": None, "odd_2": None, "bookmaker_1": None, "bookmaker_x": None, "bookmaker_2": None}
    home, away = event.get("home_team"), event.get("away_team")
    for bm in event.get("bookmakers", []):
        bm_name = bm.get("title") or bm.get("key")
        for market in bm.get("markets", []):
            if market.get("key") != "h2h": continue
            for outcome in market.get("outcomes", []):
                name, price = outcome.get("name"), safe_float(outcome.get("price"))
                if price is None: continue
                if names_match(name, home) and (result["odd_1"] is None or price > result["odd_1"]):
                    result["odd_1"], result["bookmaker_1"] = price, bm_name
                elif names_match(name, away) and (result["odd_2"] is None or price > result["odd_2"]):
                    result["odd_2"], result["bookmaker_2"] = price, bm_name
                elif str(name).lower() in {"draw", "tie", "unentschieden"} and (result["odd_x"] is None or price > result["odd_x"]):
                    result["odd_x"], result["bookmaker_x"] = price, bm_name
    return result

def analyze_match(row, stats):
    model = calculate_model(row["home"], row["away"], stats)
    p1, px, p2 = model["1"], model["X"], model["2"]
    
    market = None
    if row.get("odd_1") and row.get("odd_x") and row.get("odd_2"):
        raw = np.array([1/row["odd_1"], 1/row["odd_x"], 1/row["odd_2"]])
        norm = raw / raw.sum()
        market = {"1": float(norm[0]), "X": float(norm[1]), "2": float(norm[2])}

    final = {
        "1": 0.70 * p1 + 0.30 * market["1"] if market else p1,
        "X": 0.70 * px + 0.30 * market["X"] if market else px,
        "2": 0.70 * p2 + 0.30 * market["2"] if market else p2,
    }
    total = sum(final.values())
    final = {k: v / total for k, v in final.items()}

    prediction = max(final, key=final.get)
    confidence = final[prediction]
    gap = confidence - sorted(final.values(), reverse=True)[1]

    risk = "LOW" if confidence >= 0.64 and gap >= 0.20 else ("MID" if confidence >= 0.54 and gap >= 0.10 else "HIGH")
    
    selected_odd = row.get("odd_1") if prediction == "1" else (row.get("odd_x") if prediction == "X" else row.get("odd_2"))
    value = (confidence * selected_odd - 1) if selected_odd and selected_odd > 1 else None

    kelly = 0.0
    if value and value > 0 and selected_odd > 1:
        kelly = max(0.0, (confidence * selected_odd - 1) / (selected_odd - 1)) * 0.25

    return {
        "p1": final["1"], "px": final["X"], "p2": final["2"],
        "prediction": prediction, "confidence": confidence, "risk": risk, "value": value, "kelly": kelly
    }

# ============================================================
# APP UI & HAUPTBEREICH
# ============================================================

st.title("⚽ WETT-KI Live")
st.caption("Echtzeit-Fußballanalysen mit frischen Buchmacherquoten & Kelly-Formel")

st.sidebar.header("⚙️ Konfiguration")
football_token = st.sidebar.text_input("football-data.org Token", value=st.session_state.football_token, type="password")
odds_key = st.sidebar.text_input("The Odds API Key", value=st.session_state.odds_key, type="password")
st.session_state.football_token, st.session_state.odds_key = football_token.strip(), odds_key.strip()

selected_leagues = st.sidebar.multiselect("Wettbewerbe", list(LEAGUES.keys()), default=list(LEAGUES.keys())[:4])
budget = st.sidebar.number_input("💰 Gesamt-Bankroll (€)", min_value=1.0, value=100.0, step=10.0)

if st.sidebar.button("🔄 DATEN AKTUALISIEREN & LADEN", use_container_width=True):
    with st.spinner("Lade Live-Spiele und frische Quoten..."):
        codes = [LEAGUES[l]["football_data"] for l in selected_leagues]
        dates = get_week_dates()
        fixtures, err1 = get_current_fixtures(st.session_state.football_token, codes, dates[0], dates[-1])
        historical, _ = get_historical_matches(st.session_state.football_token, codes)
        stats = build_team_stats(historical)

        all_odds = {}
        if st.session_state.odds_key:
            for l_name in selected_leagues:
                all_odds[l_name] = get_fresh_odds(st.session_state.odds_key, LEAGUES[l_name]["odds"])

        if fixtures:
            df = pd.DataFrame(fixtures)
            rows_analysis = []
            for _, r in df.iterrows():
                match_odds = {"odd_1": None, "odd_x": None, "odd_2": None, "bookmaker_1": None}
                for ev in all_odds.get(r["league"], []):
                    if names_match(r["home"], ev.get("home_team")) and names_match(r["away"], ev.get("away_team")):
                        match_odds = extract_best_odds(ev)
                        break
                
                row_data = {**r, **match_odds}
                analysis = analyze_match(row_data, stats)
                rows_analysis.append({**row_data, **analysis})

            final_df = pd.DataFrame(rows_analysis)
            final_df["local_datetime"] = final_df["utcDate"].apply(format_local_datetime)
            final_df["date"] = final_df["utcDate"].apply(lambda x: x.astimezone(ZoneInfo(LOCAL_TZ)).date())
            final_df["time"] = final_df["utcDate"].apply(lambda x: x.astimezone(ZoneInfo(LOCAL_TZ)).strftime("%H:%M"))
            
            st.session_state.fixtures = final_df[final_df["utcDate"] > utc_now()].reset_index(drop=True)
            st.session_state.last_update = datetime.now()
        else:
            st.session_state.fixtures = pd.DataFrame()
        if err1: st.session_state.errors = [err1]

df = st.session_state.fixtures.copy()

if df.empty:
    st.info("Klicke in der Sidebar auf **'Daten aktualisieren & laden'**, um die aktuellen Spiele für diesen Spieltag abzurufen.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🔥 Top Value & Kelly", "🤖 KI-Analyse", "📊 Live-Quoten"])

with tab1:
    st.subheader("🎯 Empfohlene Value Bets mit Kelly-Einsatz")
    for _, row in df.sort_values("value", ascending=False).head(5).iterrows():
        kelly_stake = row["kelly"] * budget
        st.markdown(f"**{row['league']}** | {row['home']} vs {row['away']} ({row['local_datetime']})")
        st.write(f"Tipp: **{row['prediction']}** | Quote: **{row.get('odd_1' if row['prediction']=='1' else 'odd_2', '—')}** | Kelly-Empfehlung: **{kelly_stake:.2f} €** ({row['kelly']*100:.1f}% der Bankroll)")
        st.divider()

with tab2:
    st.subheader("Vollständige Spielmatrix")
    st.dataframe(df[["local_datetime", "league", "home", "away", "prediction", "confidence", "risk"]], use_container_width=True)

with tab3:
    st.subheader("Aktuelle Buchmacherquoten (Live)")
    st.dataframe(df[["local_datetime", "league", "home", "away", "odd_1", "odd_x", "odd_2"]], use_container_width=True)

