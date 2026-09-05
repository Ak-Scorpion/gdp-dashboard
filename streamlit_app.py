import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from itertools import combinations
import random

# ============================================================
# WETT-KI – STRIKTE SPIELTAGS-SYNCHRONISATION
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
if "reroll_seed" not in st.session_state:
    st.session_state.reroll_seed = 42

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

def normalize_name(name):
    if not name:
        return ""
    replacements = {"fc": "", "cf": "", "afc": "", "united": "", "utd": "", "tsg": "", "sv": "", "sc": "", "bv": ""}
    words = str(name).lower().replace(".", "").replace("-", " ").replace("'", "").split()
    filtered = [w for w in words if w not in replacements]
    return " ".join(filtered).strip()

def names_match(a, b):
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    set_a, set_b = set(na.split()), set(nb.split())
    if set_a & set_b:
        return True
    return False

@st.cache_data(ttl=300)
def api_get_cached(url, headers=None, params=None):
    try:
        response = requests.get(url, headers=headers, params=params, timeout=25)
        if response.status_code == 200:
            return response.json(), None
        return None, f"HTTP {response.status_code}"
    except Exception as e:
        return None, str(e)

def get_strict_matchday_fixtures(token, selected_league_names):
    headers = {"X-Auth-Token": token}
    all_rows = []
    current_time = utc_now()
    errors = []

    for l_name in selected_league_names:
        code = LEAGUES[l_name]["football_data"]
        
        # 1. Aktuellen Spieltag der Liga direkt ermitteln
        comp_url = f"{FOOTBALL_DATA_URL}/competitions/{code}"
        comp_data, error = api_get_cached(comp_url, headers=headers)
        if error:
            errors.append(f"{l_name}: {error}")
            continue

        current_matchday = comp_data.get("currentSeason", {}).get("currentMatchday")
        if not current_matchday:
            continue

        # 2. Partien exakt für diesen Spieltag laden
        matches_url = f"{FOOTBALL_DATA_URL}/competitions/{code}/matches"
        matches_data, err = api_get_cached(matches_url, headers=headers, params={"matchday": current_matchday})
        if err or not matches_data:
            continue

        matches = matches_data.get("matches", [])
        
        # Falls alle Spiele dieses Spieltags vorbei sind, nimm automatisch den nächsten Spieltag
        future_matches = [m for m in matches if parse_utc(m.get("utcDate")) and parse_utc(m.get("utcDate")) > current_time]
        if not future_matches:
            current_matchday += 1
            matches_data_next, err_next = api_get_cached(matches_url, headers=headers, params={"matchday": current_matchday})
            if not err_next and matches_data_next:
                matches = matches_data_next.get("matches", [])

        for match in matches:
            utc_date = parse_utc(match.get("utcDate"))
            if utc_date is None or utc_date <= current_time:
                continue
            
            status = str(match.get("status", "")).upper()
            if status in {"CANCELLED", "POSTPONED", "SUSPENDED", "FINISHED", "IN_PLAY", "PAUSED"}:
                continue

            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})
            home_name = home.get("name") or home.get("shortName")
            away_name = away.get("name") or away.get("shortName")

            if not home_name or not away_name:
                continue

            all_rows.append({
                "match_id": match.get("id"),
                "competition_code": code,
                "league": l_name,
                "matchday": current_matchday,
                "utcDate": utc_date,
                "home": home_name,
                "away": away_name,
                "status": status,
            })
    return all_rows, errors

def get_historical_matches(token, selected_league_names, days_back=90):
    end_date = utc_now().date()
    start_date = end_date - timedelta(days=days_back)
    headers = {"X-Auth-Token": token}
    all_historical = []
    
    for l_name in selected_league_names:
        code = LEAGUES[l_name]["football_data"]
        url = f"{FOOTBALL_DATA_URL}/competitions/{code}/matches"
        params = {"dateFrom": start_date.isoformat(), "dateTo": end_date.isoformat(), "status": "FINISHED"}
        data, error = api_get_cached(url, headers=headers, params=params)
        if not error and data:
            all_historical.extend(data.get("matches", []))
    return all_historical

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
                stats[team] = {"played": 0, "gf": 0, "ga": 0}

        stats[home_name]["played"] += 1; stats[home_name]["gf"] += hg; stats[home_name]["ga"] += ag
        stats[away_name]["played"] += 1; stats[away_name]["gf"] += ag; stats[away_name]["ga"] += hg
    return stats

def calculate_advanced_markets(home_lambda, away_lambda):
    p1, px, p2 = 0.0, 0.0, 0.0
    for h in range(0, 8):
        for a in range(0, 8):
            p_h = math.exp(-home_lambda) * (home_lambda ** h) / math.factorial(h)
            p_a = math.exp(-away_lambda) * (away_lambda ** a) / math.factorial(a)
            p = p_h * p_a
            if h > a: p1 += p
            elif h == a: px += p
            else: p2 += p
    total = p1 + px + p2
    if total <= 0:
        return {"1": 1/3, "X": 1/3, "2": 1/3}
    return {"1": p1 / total, "X": px / total, "2": p2 / total}

def calculate_model(home, away, stats):
    hs, aws = stats.get(home), stats.get(away)
    home_gf = (hs["gf"] / max(hs["played"], 1)) if hs and hs["played"] > 0 else 1.4
    home_ga = (hs["ga"] / max(hs["played"], 1)) if hs and hs["played"] > 0 else 1.2
    away_gf = (aws["gf"] / max(aws["played"], 1)) if aws and aws["played"] > 0 else 1.3
    away_ga = (aws["ga"] / max(aws["played"], 1)) if aws and aws["played"] > 0 else 1.3

    home_lambda = max(0.4, (home_gf * 0.5 + away_ga * 0.5) * 1.03)
    away_lambda = max(0.4, (away_gf * 0.5 + home_ga * 0.5))
    return calculate_advanced_markets(home_lambda, away_lambda)

def get_fresh_odds(odds_key, sport_key):
    if not odds_key:
        return []
    url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
    params = {"apiKey": odds_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
    data, error = api_get_cached(url, params=params)
    return data if isinstance(data, list) else []

def extract_best_odds(event):
    result = {"odd_1": None, "odd_x": None, "odd_2": None, "bookmaker_1": None}
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
                    result["odd_2"] = price
                elif str(name).lower() in {"draw", "tie", "unentschieden"} and (result["odd_x"] is None or price > result["odd_x"]):
                    result["odd_x"] = price
    return result

def analyze_match(row, stats):
    model = calculate_model(row["home"], row["away"], stats)
    p1, px, p2 = model["1"], model["X"], model["2"]
    
    odd_1 = row.get("odd_1")
    odd_x = row.get("odd_x")
    odd_2 = row.get("odd_2")
    
    if not odd_1 or not odd_x or not odd_2:
        odd_1 = round(1.0 / max(p1, 0.05) * 0.93, 2)
        odd_x = round(1.0 / max(px, 0.05) * 0.93, 2)
        odd_2 = round(1.0 / max(p2, 0.05) * 0.93, 2)
        row["bookmaker_1"] = "WETT-KI Modell-Quote"

    market = np.array([1/odd_1, 1/odd_x, 1/odd_2])
    market = market / market.sum()

    final = {
        "1": 0.60 * p1 + 0.40 * market[0],
        "X": 0.60 * px + 0.40 * market[1],
        "2": 0.60 * p2 + 0.40 * market[2],
    }
    total = sum(final.values())
    final = {k: v / total for k, v in final.items()}

    prediction = max(final, key=final.get)
    confidence = final[prediction]
    sorted_probs = sorted(final.values(), reverse=True)
    gap = sorted_probs[0] - sorted_probs[1]

    if confidence >= 0.52 and gap >= 0.12:
        risk = "LOW"
    elif confidence >= 0.40 and gap >= 0.05:
        risk = "MID"
    else:
        risk = "HIGH"
    
    selected_odd = odd_1 if prediction == "1" else (odd_x if prediction == "X" else odd_2)
    value = (confidence * selected_odd - 1) if selected_odd > 1 else 0.0
    kelly = max(0.0, (confidence * selected_odd - 1) / (selected_odd - 1)) * 0.25 if selected_odd > 1 else 0.0

    return {
        "p1": final["1"], "px": final["X"], "p2": final["2"],
        "odd_1": odd_1, "odd_x": odd_x, "odd_2": odd_2,
        "prediction": prediction, "confidence": confidence, "risk": risk, "value": value, "kelly": kelly
    }

# ============================================================
# APP UI & HAUPTBEREICH
# ============================================================

st.title("⚽ WETT-KI Live")
st.caption("Aktueller Spieltag der Top-Ligen mit Echtzeit-Quoten & Kelly-Formel")

st.sidebar.header("⚙️ Konfiguration")
football_token = st.sidebar.text_input("football-data.org Token", value=st.session_state.football_token, type="password")
odds_key = st.sidebar.text_input("The Odds API Key", value=st.session_state.odds_key, type="password")
st.session_state.football_token, st.session_state.odds_key = football_token.strip(), odds_key.strip()

selected_leagues = st.sidebar.multiselect("Wettbewerbe", list(LEAGUES.keys()), default=list(LEAGUES.keys())[:5])
selected_risks = st.sidebar.multiselect("Risiko-Filter", ["LOW", "MID", "HIGH"], default=["LOW", "MID", "HIGH"])
budget = st.sidebar.number_input("💰 Gesamt-Bankroll (€)", min_value=1.0, value=100.0, step=10.0)

if st.sidebar.button("🔄 SPIELE & QUOTEN LADEN", use_container_width=True):
    with st.spinner("Lade aktuellen Spieltag aller Top-Ligen und Quoten..."):
        fixtures, err1 = get_strict_matchday_fixtures(st.session_state.football_token, selected_leagues)
        historical = get_historical_matches(st.session_state.football_token, selected_leagues)
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
            
            st.session_state.fixtures = final_df[final_df["utcDate"] > utc_now()].reset_index(drop=True)
            st.session_state.last_update = datetime.now()
        else:
            st.session_state.fixtures = pd.DataFrame()
        if err1: st.session_state.errors = err1

df = st.session_state.fixtures.copy()

if not df.empty and selected_leagues:
    df = df[df["league"].isin(selected_leagues)]
if not df.empty and selected_risks:
    df = df[df["risk"].isin(selected_risks)]

# ============================================================
# SIDEBAR KOMBI-GENERATOR
# ============================================================
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎟️ Kombi-Schein Generator")
num_legs = st.sidebar.number_input("Anzahl Spiele (Legs)", min_value=2, max_value=10, value=3, step=1)

if st.sidebar.button("🎲 Kombi Reroll", use_container_width=True):
    st.session_state.reroll_seed = np.random.randint(0, 100000)
    st.rerun()

if not df.empty:
    if len(df) >= num_legs:
        shuffled_df = df.sample(frac=1.0, random_state=st.session_state.reroll_seed).reset_index(drop=True)
        kombi_rows = shuffled_df.head(num_legs)
        total_kombi_odd = 1.0
        combined_conf = 1.0
        
        st.sidebar.markdown(f"**Aktive {num_legs}er-Kombi:**")
        for _, row in kombi_rows.iterrows():
            sel_odd = row['odd_1'] if row['prediction'] == '1' else (row['odd_x'] if row['prediction'] == 'X' else row['odd_2'])
            total_kombi_odd *= sel_odd
            combined_conf *= row['confidence']
            st.sidebar.text(f"• {row['home'][:12]}.. vs {row['away'][:12]}.. → {row['prediction']} ({sel_odd:.2f})")
        
        st.sidebar.markdown(f"**Gesamtquote:** {total_kombi_odd:.2f}")
        st.sidebar.markdown(f"**Modell-Wahrsch.:** {combined_conf * 100:.1f}%")
        kombi_stake = min(budget * 0.1, 10.0)
        st.sidebar.markdown(f"**Einsatz:** {kombi_stake:.2f} € (Gewinn: {kombi_stake * total_kombi_odd:.2f} €)")
    else:
        st.sidebar.info(f"Zu wenig Spiele für {num_legs} Legs (aktuell: {len(df)}).")

if df.empty:
    st.info("Klicke in der Sidebar auf **'Spiele & Quoten laden'**, um die Partien anzuzeigen.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🔥 Top Value & Kelly", "🤖 KI-Analyse", "📊 Live-Quoten"])

with tab1:
    st.subheader("🎯 Empfohlene Value Bets mit Kelly-Einsatz")
    for _, row in df.sort_values("value", ascending=False).head(10).iterrows():
        kelly_stake = row["kelly"] * budget
        selected_quote = row['odd_1'] if row['prediction'] == '1' else (row['odd_x'] if row['prediction'] == 'X' else row['odd_2'])
        st.markdown(f"**{row['league']} (Spieltag {row['matchday']})** | {row['home']} vs {row['away']} ({row['local_datetime']})")
        st.write(f"Tipp: **{row['prediction']}** | Quote: **{selected_quote:.2f}** ({row.get('bookmaker_1', 'Modell')}) | Risiko: **{row['risk']}** | Kelly: **{kelly_stake:.2f} €**")
        st.divider()

with tab2:
    st.subheader("Vollständige Spielmatrix")
    st.dataframe(df[["local_datetime", "league", "matchday", "home", "away", "prediction", "confidence", "risk"]], use_container_width=True)

with tab3:
    st.subheader("Aktuelle Buchmacherquoten & Fallback")
    st.dataframe(df[["local_datetime", "league", "matchday", "home", "away", "odd_1", "odd_x", "odd_2", "bookmaker_1"]], use_container_width=True)

