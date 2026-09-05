import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import random
import time

# ============================================================
# WETT-KI LIVE
# Robuste Version:
# - kommende Spiele statt problematischem currentMatchday
# - echte Odds only
# - robustes Team-Matching
# - Value + Kelly nur mit echten Quoten
# - funktionierende Kombi
# - API-Fehler sichtbar
# ============================================================

st.set_page_config(
    page_title="WETT-KI Live",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# KONFIGURATION
# ============================================================

FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
ODDS_API_URL = "https://api.the-odds-api.com/v4"
LOCAL_TZ = "Europe/Berlin"

LEAGUES = {
    "Premier League": {
        "football_data": "PL",
        "odds": "soccer_epl"
    },
    "Bundesliga": {
        "football_data": "BL1",
        "odds": "soccer_germany_bundesliga"
    },
    "La Liga": {
        "football_data": "PD",
        "odds": "soccer_spain_la_liga"
    },
    "Serie A": {
        "football_data": "SA",
        "odds": "soccer_italy_serie_a"
    },
    "Ligue 1": {
        "football_data": "FL1",
        "odds": "soccer_france_ligue_one"
    },
    "Champions League": {
        "football_data": "CL",
        "odds": "soccer_uefa_champs_league"
    },
    "Europa League": {
        "football_data": "EL",
        "odds": "soccer_uefa_europa_league"
    },
    "Conference League": {
        "football_data": "EC",
        "odds": "soccer_uefa_europa_conference_league"
    },
}

# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "football_token": "",
    "odds_key": "",
    "fixtures": pd.DataFrame(),
    "last_update": None,
    "errors": [],
    "api_messages": [],
    "reroll_seed": 42,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def utc_now():
    return datetime.now(timezone.utc)


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def parse_utc(value):
    if value is None or value == "":
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def format_local_datetime(value):
    dt = parse_utc(value)

    if dt is None:
        return "—"

    return dt.astimezone(
        ZoneInfo(LOCAL_TZ)
    ).strftime("%d.%m.%Y %H:%M")


def normalize_team_name(name):
    """
    Vorsichtiges Normalisieren.
    Nicht zu aggressiv, damit z.B. unterschiedliche Teams
    nicht versehentlich gematcht werden.
    """

    if not name:
        return ""

    s = str(name).lower().strip()

    replacements = [
        ".", ",", "'", '"', "-", "_", "(", ")", "[", "]"
    ]

    for char in replacements:
        s = s.replace(char, " ")

    aliases = {
        "fc": "",
        "cf": "",
        "afc": "",
        "sc": "",
        "sv": "",
        "tsg": "",
        "fk": "",
        "ac": "",
        "as": "",
        "rc": "",
        "ud": "",
        "cd": "",
    }

    words = s.split()

    words = [
        aliases.get(word, word)
        for word in words
    ]

    words = [w for w in words if w]

    return " ".join(words)


def team_names_match(name_a, name_b):
    """
    Robustes Matching.

    Wichtig:
    Keine einfache Teilstring-Suche mehr wie
    'united' in 'newcastle united'.
    """

    a = normalize_team_name(name_a)
    b = normalize_team_name(name_b)

    if not a or not b:
        return False

    if a == b:
        return True

    tokens_a = set(a.split())
    tokens_b = set(b.split())

    # Sehr guter Treffer: mehrere gemeinsame Tokens
    common = tokens_a.intersection(tokens_b)

    if len(common) >= 2:
        return True

    # Bei Namen mit nur einem Token muss es exakt sein
    if len(tokens_a) == 1 and len(tokens_b) == 1:
        return a == b

    # Einer besteht aus mehreren Tokens und der andere
    # enthält den vollständigen Namen
    if len(a) >= 5 and len(b) >= 5:
        if a in b or b in a:
            return True

    return False


def odds_are_valid(odd):
    try:
        return float(odd) >= 1.01
    except Exception:
        return False


# ============================================================
# HTTP
# ============================================================

@st.cache_data(ttl=120, show_spinner=False)
def api_request(
    url,
    headers_tuple=(),
    params_tuple=()
):
    """
    Einheitlicher API-Requester.

    Dicts werden als Tuple übergeben, damit Streamlit
    zuverlässig cachen kann.
    """

    headers = dict(headers_tuple)
    params = dict(params_tuple)

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        status = response.status_code

        if status == 200:
            try:
                return {
                    "ok": True,
                    "status": status,
                    "data": response.json(),
                    "message": ""
                }
            except Exception:
                return {
                    "ok": False,
                    "status": status,
                    "data": None,
                    "message": "Ungültige JSON-Antwort"
                }

        if status == 401:
            return {
                "ok": False,
                "status": status,
                "data": None,
                "message": "API-Key/Token ungültig (401)"
            }

        if status == 403:
            return {
                "ok": False,
                "status": status,
                "data": None,
                "message": "Zugriff verweigert (403)"
            }

        if status == 404:
            return {
                "ok": False,
                "status": status,
                "data": None,
                "message": "Endpoint/Sport nicht gefunden (404)"
            }

        if status == 429:
            return {
                "ok": False,
                "status": status,
                "data": None,
                "message": "API-Limit erreicht (429)"
            }

        return {
            "ok": False,
            "status": status,
            "data": None,
            "message": f"HTTP {status}"
        }

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": "Timeout"
        }

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": str(e)
        }


# ============================================================
# FOOTBALL-DATA
# ============================================================

def get_upcoming_fixtures(
    token,
    league_names,
    days_forward=10
):
    """
    Lädt kommende Spiele über dateFrom/dateTo.

    Damit sind wir nicht mehr abhängig von
    currentSeason.currentMatchday.
    """

    if not token:
        return [], ["football-data.org Token fehlt."]

    headers = {
        "X-Auth-Token": token
    }

    start_date = utc_now().date()
    end_date = start_date + timedelta(days=days_forward)

    all_matches = []
    errors = []

    for league_name in league_names:

        code = LEAGUES[league_name]["football_data"]

        url = (
            f"{FOOTBALL_DATA_URL}/competitions/"
            f"{code}/matches"
        )

        params = {
            "dateFrom": start_date.isoformat(),
            "dateTo": end_date.isoformat()
        }

        result = api_request(
            url,
            headers_tuple=tuple(sorted(headers.items())),
            params_tuple=tuple(sorted(params.items()))
        )

        if not result["ok"]:
            errors.append(
                f"{league_name}: {result['message']}"
            )
            continue

        data = result["data"] or {}

        matches = data.get("matches", [])

        for match in matches:

            status = str(
                match.get("status", "")
            ).upper()

            if status in {
                "FINISHED",
                "CANCELLED",
                "POSTPONED",
                "SUSPENDED",
                "IN_PLAY",
                "PAUSED"
            }:
                continue

            match_time = parse_utc(
                match.get("utcDate")
            )

            if not match_time:
                continue

            if match_time <= utc_now():
                continue

            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})

            home_name = (
                home.get("name")
                or home.get("shortName")
            )

            away_name = (
                away.get("name")
                or away.get("shortName")
            )

            if not home_name or not away_name:
                continue

            all_matches.append({
                "match_id": match.get("id"),
                "league": league_name,
                "competition_code": code,
                "matchday": match.get("matchday"),
                "utcDate": match_time,
                "home": home_name,
                "away": away_name,
                "status": status,
            })

    # Duplikate entfernen
    unique = {}

    for row in all_matches:
        unique[row["match_id"]] = row

    all_matches = list(unique.values())

    all_matches.sort(
        key=lambda x: x["utcDate"]
    )

    return all_matches, errors


# ============================================================
# HISTORISCHE DATEN
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_historical_matches_cached(
    token,
    league_names_tuple,
    days_back=90
):

    league_names = list(league_names_tuple)

    if not token:
        return []

    end_date = utc_now().date()
    start_date = (
        end_date -
        timedelta(days=days_back)
    )

    headers = {
        "X-Auth-Token": token
    }

    all_historical = []

    for league_name in league_names:

        code = LEAGUES[league_name]["football_data"]

        url = (
            f"{FOOTBALL_DATA_URL}/competitions/"
            f"{code}/matches"
        )

        params = {
            "dateFrom": start_date.isoformat(),
            "dateTo": end_date.isoformat(),
            "status": "FINISHED"
        }

        result = api_request(
            url,
            headers_tuple=tuple(sorted(headers.items())),
            params_tuple=tuple(sorted(params.items()))
        )

        if not result["ok"]:
            continue

        data = result["data"] or {}

        all_historical.extend(
            data.get("matches", [])
        )

    return all_historical


# ============================================================
# TEAM STATS
# ============================================================

def build_team_stats(matches):

    stats = {}

    for match in matches:

        if str(
            match.get("status", "")
        ).upper() != "FINISHED":
            continue

        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})

        home_name = (
            home.get("name")
            or home.get("shortName")
        )

        away_name = (
            away.get("name")
            or away.get("shortName")
        )

        score = (
            match.get("score", {})
            .get("fullTime", {})
        )

        hg = safe_float(score.get("home"))
        ag = safe_float(score.get("away"))

        if hg is None or ag is None:
            continue

        for team in [home_name, away_name]:

            if team not in stats:

                stats[team] = {
                    "played": 0,
                    "gf": 0.0,
                    "ga": 0.0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0
                }

        # Heim
        stats[home_name]["played"] += 1
        stats[home_name]["gf"] += hg
        stats[home_name]["ga"] += ag

        if hg > ag:
            stats[home_name]["wins"] += 1
        elif hg == ag:
            stats[home_name]["draws"] += 1
        else:
            stats[home_name]["losses"] += 1

        # Auswärts
        stats[away_name]["played"] += 1
        stats[away_name]["gf"] += ag
        stats[away_name]["ga"] += hg

        if ag > hg:
            stats[away_name]["wins"] += 1
        elif ag == hg:
            stats[away_name]["draws"] += 1
        else:
            stats[away_name]["losses"] += 1

    return stats


# ============================================================
# POISSON-MODELL
# ============================================================

def poisson_probability(lmbda, k):
    try:
        return (
            math.exp(-lmbda)
            * (lmbda ** k)
            / math.factorial(k)
        )
    except Exception:
        return 0.0


def calculate_1x2(home_lambda, away_lambda):

    p1 = 0.0
    px = 0.0
    p2 = 0.0

    # 0-0 bis 10-10
    for home_goals in range(0, 11):

        for away_goals in range(0, 11):

            ph = poisson_probability(
                home_lambda,
                home_goals
            )

            pa = poisson_probability(
                away_lambda,
                away_goals
            )

            p = ph * pa

            if home_goals > away_goals:
                p1 += p

            elif home_goals == away_goals:
                px += p

            else:
                p2 += p

    total = p1 + px + p2

    if total <= 0:
        return {
            "1": 1 / 3,
            "X": 1 / 3,
            "2": 1 / 3
        }

    return {
        "1": p1 / total,
        "X": px / total,
        "2": p2 / total
    }


def calculate_model(
    home,
    away,
    stats
):

    hs = stats.get(home)
    aws = stats.get(away)

    # Fallback-Werte für neue/fehlende Teams
    home_gf = 1.50
    home_ga = 1.10
    away_gf = 1.20
    away_ga = 1.40

    if hs and hs["played"] > 0:

        home_gf = (
            hs["gf"] /
            hs["played"]
        )

        home_ga = (
            hs["ga"] /
            hs["played"]
        )

    if aws and aws["played"] > 0:

        away_gf = (
            aws["gf"] /
            aws["played"]
        )

        away_ga = (
            aws["ga"] /
            aws["played"]
        )

    home_lambda = (
        home_gf * 0.55 +
        away_ga * 0.45
    )

    away_lambda = (
        away_gf * 0.55 +
        home_ga * 0.45
    )

    # Extreme Werte vermeiden
    home_lambda = max(
        0.25,
        min(home_lambda, 4.5)
    )

    away_lambda = max(
        0.25,
        min(away_lambda, 4.5)
    )

    return calculate_1x2(
        home_lambda,
        away_lambda
    )


# ============================================================
# ODDS API
# ============================================================

def get_odds(
    odds_key,
    sport_key
):

    if not odds_key:
        return [], "Odds API Key fehlt."

    url = (
        f"{ODDS_API_URL}/sports/"
        f"{sport_key}/odds"
    )

    params = {
        "apiKey": odds_key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    result = api_request(
        url,
        params_tuple=tuple(
            sorted(params.items())
        )
    )

    if not result["ok"]:
        return [], result["message"]

    data = result["data"]

    if not isinstance(data, list):
        return [], "Odds API liefert keine Event-Liste."

    return data, ""


def extract_best_odds(event):

    home = event.get("home_team")
    away = event.get("away_team")

    result = {
        "odd_1": None,
        "odd_x": None,
        "odd_2": None,
        "bookmaker_1": None,
        "bookmaker_x": None,
        "bookmaker_2": None,
    }

    if not home or not away:
        return result

    for bookmaker in event.get(
        "bookmakers", []
    ):

        bookmaker_name = (
            bookmaker.get("title")
            or bookmaker.get("key")
            or "Buchmacher"
        )

        for market in bookmaker.get(
            "markets", []
        ):

            if market.get("key") != "h2h":
                continue

            for outcome in market.get(
                "outcomes", []
            ):

                outcome_name = outcome.get("name")
                price = safe_float(
                    outcome.get("price")
                )

                if not odds_are_valid(price):
                    continue

                # Heim
                if team_names_match(
                    outcome_name,
                    home
                ):

                    if (
                        result["odd_1"] is None
                        or price > result["odd_1"]
                    ):
                        result["odd_1"] = price
                        result["bookmaker_1"] = (
                            bookmaker_name
                        )

                # Auswärts
                elif team_names_match(
                    outcome_name,
                    away
                ):

                    if (
                        result["odd_2"] is None
                        or price > result["odd_2"]
                    ):
                        result["odd_2"] = price
                        result["bookmaker_2"] = (
                            bookmaker_name
                        )

                # Unentschieden
                elif str(
                    outcome_name
                ).strip().lower() in {
                    "draw",
                    "tie",
                    "x",
                    "unentschieden"
                }:

                    if (
                        result["odd_x"] is None
                        or price > result["odd_x"]
                    ):
                        result["odd_x"] = price
                        result["bookmaker_x"] = (
                            bookmaker_name
                        )

    return result


def find_odds_for_fixture(
    fixture,
    events
):

    best = {
        "odd_1": None,
        "odd_x": None,
        "odd_2": None,
        "bookmaker_1": None,
        "bookmaker_x": None,
        "bookmaker_2": None,
    }

    fixture_home = fixture["home"]
    fixture_away = fixture["away"]
    fixture_time = fixture["utcDate"]

    candidates = []

    for event in events:

        event_home = event.get("home_team")
        event_away = event.get("away_team")

        if not event_home or not event_away:
            continue

        if not team_names_match(
            fixture_home,
            event_home
        ):
            continue

        if not team_names_match(
            fixture_away,
            event_away
        ):
            continue

        event_time = parse_utc(
            event.get("commence_time")
        )

        # Wenn beide Zeiten vorhanden sind,
        # maximal 18 Stunden Differenz zulassen.
        if event_time and fixture_time:

            diff = abs(
                (event_time - fixture_time)
                .total_seconds()
            )

            if diff > 18 * 3600:
                continue

        candidates.append(event)

    if not candidates:
        return best

    # Wenn mehrere Treffer:
    # zeitlich nächsten nehmen.
    candidates.sort(
        key=lambda e: abs(
            (
                parse_utc(
                    e.get("commence_time")
                )
                - fixture_time
            ).total_seconds()
        )
        if parse_utc(e.get("commence_time"))
        else 999999999
    )

    return extract_best_odds(
        candidates[0]
    )


# ============================================================
# MODELL + VALUE + KELLY
# ============================================================

def calculate_market_probabilities(
    odd_1,
    odd_x,
    odd_2
):

    odds = [
        odd_1,
        odd_x,
        odd_2
    ]

    if not all(
        odds_are_valid(x)
        for x in odds
    ):
        return None

    inverse = np.array(
        [1 / x for x in odds],
        dtype=float
    )

    total = inverse.sum()

    if total <= 0:
        return None

    normalized = inverse / total

    return {
        "1": normalized[0],
        "X": normalized[1],
        "2": normalized[2]
    }


def calculate_kelly(
    probability,
    odds,
    fraction=0.25
):

    if not probability:
        return 0.0

    if not odds_are_valid(odds):
        return 0.0

    b = odds - 1

    if b <= 0:
        return 0.0

    q = 1 - probability

    full_kelly = (
        (b * probability - q) /
        b
    )

    return max(
        0.0,
        full_kelly
    ) * fraction


def analyze_match(
    fixture,
    stats
):

    model = calculate_model(
        fixture["home"],
        fixture["away"],
        stats
    )

    p1 = model["1"]
    px = model["X"]
    p2 = model["2"]

    odd_1 = fixture.get("odd_1")
    odd_x = fixture.get("odd_x")
    odd_2 = fixture.get("odd_2")

    market = calculate_market_probabilities(
        odd_1,
        odd_x,
        odd_2
    )

    # Kein echter Markt vorhanden
    if market is None:

        return {
            **model,
            "market_1": None,
            "market_x": None,
            "market_2": None,
            "prediction": max(
                model,
                key=model.get
            ),
            "confidence": max(
                model.values()
            ),
            "selected_odd": None,
            "value": None,
            "kelly": 0.0,
            "risk": "NO ODDS",
            "has_real_odds": False,
        }

    # 65% Modell / 35% Markt
    final = {
        "1": 0.65 * p1 + 0.35 * market["1"],
        "X": 0.65 * px + 0.35 * market["X"],
        "2": 0.65 * p2 + 0.35 * market["2"],
    }

    total = sum(final.values())

    final = {
        k: v / total
        for k, v in final.items()
    }

    prediction = max(
        final,
        key=final.get
    )

    confidence = final[prediction]

    if prediction == "1":
        selected_odd = odd_1
    elif prediction == "X":
        selected_odd = odd_x
    else:
        selected_odd = odd_2

    # Value
    value = (
        confidence * selected_odd - 1
    )

    # Kelly
    kelly = calculate_kelly(
        confidence,
        selected_odd,
        fraction=0.25
    )

    # Risiko
    if confidence >= 0.60 and value >= 0.05:
        risk = "LOW"

    elif confidence >= 0.52 and value >= 0.02:
        risk = "MID"

    else:
        risk = "HIGH"

    return {
        "p1": final["1"],
        "px": final["X"],
        "p2": final["2"],

        "market_1": market["1"],
        "market_x": market["X"],
        "market_2": market["2"],

        "prediction": prediction,
        "confidence": confidence,
        "selected_odd": selected_odd,
        "value": value,
        "kelly": kelly,
        "risk": risk,
        "has_real_odds": True,
    }


# ============================================================
# KOMBI
# ============================================================

def generate_kombi(
    df,
    num_legs,
    seed
):

    if df.empty:
        return pd.DataFrame()

    playable = df[
        (df["has_real_odds"] == True) &
        (df["selected_odd"].notna()) &
        (df["selected_odd"] >= 1.01)
    ].copy()

    if len(playable) < num_legs:
        return pd.DataFrame()

    # Nicht einfach blind zufällig.
    # Wir wählen aus den besseren Value-Spielen,
    # aber mischen sie mit dem Seed.
    playable = playable.sort_values(
        "value",
        ascending=False
    ).reset_index(drop=True)

    # Top-Kandidaten
    candidate_count = min(
        len(playable),
        max(num_legs * 3, 10)
    )

    candidates = playable.head(
        candidate_count
    ).copy()

    candidates = candidates.sample(
        frac=1,
        random_state=seed
    ).reset_index(drop=True)

    selected = candidates.head(
        num_legs
    ).copy()

    return selected


def calculate_kombi_stats(
    kombi_df
):

    if kombi_df.empty:
        return None

    total_odd = 1.0
    probability = 1.0

    for _, row in kombi_df.iterrows():

        total_odd *= float(
            row["selected_odd"]
        )

        probability *= float(
            row["confidence"]
        )

    return {
        "total_odd": total_odd,
        "probability": probability,
    }


# ============================================================
# APP HEADER
# ============================================================

st.title("⚽ WETT-KI Live")

st.caption(
    "Modell + echte Buchmacherquoten + Value + "
    "25%-Kelly + Kombi-Generator"
)

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ Konfiguration")

football_token = st.sidebar.text_input(
    "football-data.org Token",
    value=st.session_state.football_token,
    type="password",
    help="Am besten über Streamlit Secrets hinterlegen."
)

odds_key = st.sidebar.text_input(
    "The Odds API Key",
    value=st.session_state.odds_key,
    type="password",
    help="Am besten über Streamlit Secrets hinterlegen."
)

st.session_state.football_token = (
    football_token.strip()
)

st.session_state.odds_key = (
    odds_key.strip()
)

selected_leagues = st.sidebar.multiselect(
    "Wettbewerbe",
    list(LEAGUES.keys()),
    default=[
        "Premier League",
        "Bundesliga",
        "La Liga",
        "Serie A",
        "Ligue 1"
    ]
)

selected_risks = st.sidebar.multiselect(
    "Risiko-Filter",
    ["LOW", "MID", "HIGH"],
    default=["LOW", "MID", "HIGH"]
)

budget = st.sidebar.number_input(
    "💰 Gesamt-Bankroll (€)",
    min_value=1.0,
    value=100.0,
    step=10.0
)

days_forward = st.sidebar.slider(
    "📅 Spiele voraus",
    min_value=3,
    max_value=14,
    value=7
)

# ============================================================
# LADEN
# ============================================================

load_clicked = st.sidebar.button(
    "🔄 SPIELE & QUOTEN LADEN",
    use_container_width=True,
    type="primary"
)

if load_clicked:

    st.session_state.errors = []
    st.session_state.api_messages = []

    if not selected_leagues:

        st.error(
            "Bitte mindestens einen Wettbewerb auswählen."
        )

    elif not st.session_state.football_token:

        st.error(
            "football-data.org Token fehlt."
        )

    else:

        with st.spinner(
            "Lade kommende Spiele..."
        ):

            fixtures, fixture_errors = (
                get_upcoming_fixtures(
                    st.session_state.football_token,
                    selected_leagues,
                    days_forward
                )
            )

        st.session_state.errors.extend(
            fixture_errors
        )

        if not fixtures:

            st.session_state.fixtures = (
                pd.DataFrame()
            )

            st.error(
                "Keine kommenden Spiele gefunden."
            )

        else:

            with st.spinner(
                "Lade aktuelle Buchmacherquoten..."
            ):

                odds_by_league = {}

                for league_name in selected_leagues:

                    sport_key = LEAGUES[
                        league_name
                    ]["odds"]

                    events, error = get_odds(
                        st.session_state.odds_key,
                        sport_key
                    )

                    odds_by_league[
                        league_name
                    ] = events

                    if error:
                        st.session_state.errors.append(
                            f"{league_name} Odds: {error}"
                        )

                    # API etwas schonen
                    time.sleep(0.15)

            with st.spinner(
                "Analysiere Spiele..."
            ):

                historical = (
                    get_historical_matches_cached(
                        st.session_state.football_token,
                        tuple(selected_leagues),
                        90
                    )
                )

                stats = build_team_stats(
                    historical
                )

                rows = []

                for fixture in fixtures:

                    odds = find_odds_for_fixture(
                        fixture,
                        odds_by_league.get(
                            fixture["league"],
                            []
                        )
                    )

                    row = {
                        **fixture,
                        **odds
                    }

                    analysis = analyze_match(
                        row,
                        stats
                    )

                    row.update(
                        analysis
                    )

                    row[
                        "local_datetime"
                    ] = format_local_datetime(
                        row["utcDate"]
                    )

                    rows.append(row)

                result_df = pd.DataFrame(
                    rows
                )

                if not result_df.empty:

                    result_df = result_df.sort_values(
                        "utcDate"
                    ).reset_index(
                        drop=True
                    )

                st.session_state.fixtures = (
                    result_df
                )

                st.session_state.last_update = (
                    datetime.now()
                )

# ============================================================
# DATEN
# ============================================================

df_all = st.session_state.fixtures.copy()

# ============================================================
# STATUS
# ============================================================

if st.session_state.last_update:

    st.success(
        f"Zuletzt aktualisiert: "
        f"{st.session_state.last_update.strftime('%d.%m.%Y %H:%M:%S')}"
    )

if st.session_state.errors:

    with st.expander(
        "⚠️ API-Hinweise / Fehler",
        expanded=True
    ):

        for error in st.session_state.errors:
            st.warning(error)


if df_all.empty:

    st.info(
        "Noch keine Daten geladen. "
        "Klicke links auf **SPIELE & QUOTEN LADEN**."
    )

    st.stop()

# ============================================================
# QUOTEN-STATUS
# ============================================================

real_odds_count = int(
    df_all["has_real_odds"].sum()
)

total_games = len(df_all)

st.sidebar.markdown("---")

st.sidebar.metric(
    "Geladene Spiele",
    total_games
)

st.sidebar.metric(
    "Spiele mit echten Quoten",
    real_odds_count
)

if real_odds_count == 0:

    st.sidebar.error(
        "Keine echten Quoten gefunden."
    )

    st.warning(
        "Die Spiele wurden geladen, aber die Odds API "
        "hat keine passenden 1X2-Quoten geliefert. "
        "Deshalb werden bewusst keine Fake-Quoten erzeugt."
    )

# ============================================================
# SIDEBAR KOMBI
# ============================================================

st.sidebar.markdown("---")
st.sidebar.markdown(
    "### 🎟️ Kombi-Schein Generator"
)

num_legs = st.sidebar.number_input(
    "Anzahl Spiele",
    min_value=2,
    max_value=10,
    value=3,
    step=1
)

if st.sidebar.button(
    "🎲 KOMBI REROLL",
    use_container_width=True
):

    st.session_state.reroll_seed = (
        np.random.randint(
            0,
            1000000
        )
    )

    st.rerun()


kombi_df = generate_kombi(
    df_all,
    num_legs,
    st.session_state.reroll_seed
)

if kombi_df.empty:

    st.sidebar.info(
        f"Nicht genug Spiele mit echten Quoten "
        f"für eine {num_legs}er-Kombi."
    )

else:

    kombi_stats = calculate_kombi_stats(
        kombi_df
    )

    st.sidebar.markdown(
        f"**Aktive {num_legs}er-Kombi**"
    )

    for _, row in kombi_df.iterrows():

        prediction = row["prediction"]
        odd = row["selected_odd"]

        st.sidebar.write(
            f"• {row['home']} – {row['away']}"
        )

        st.sidebar.caption(
            f"→ {prediction} @ {odd:.2f} | "
            f"{row['confidence'] * 100:.1f}%"
        )

    total_odd = kombi_stats["total_odd"]
    combined_probability = (
        kombi_stats["probability"]
    )

    # kleiner Kombi-Einsatz
    kombi_stake = min(
        budget * 0.05,
        10.0
    )

    potential_return = (
        kombi_stake *
        total_odd
    )

    st.sidebar.markdown("---")

    st.sidebar.metric(
        "Gesamtquote",
        f"{total_odd:.2f}"
    )

    st.sidebar.metric(
        "Modell-Wahrscheinlichkeit",
        f"{combined_probability * 100:.2f}%"
    )

    st.sidebar.metric(
        "Einsatz",
        f"{kombi_stake:.2f} €"
    )

    st.sidebar.metric(
        "Auszahlung bei Treffer",
        f"{potential_return:.2f} €"
    )

# ============================================================
# HAUPTFILTER
# ============================================================

df = df_all.copy()

if selected_leagues:

    df = df[
        df["league"].isin(
            selected_leagues
        )
    ]

if selected_risks:

    df_display = df[
        df["risk"].isin(
            selected_risks
        )
    ].copy()

else:

    df_display = df.copy()

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🔥 Top Value & Kelly",
        "🤖 KI-Analyse",
        "📊 Live-Quoten",
        "🎟️ Kombi"
    ]
)

# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader(
        "🎯 Top Value Bets"
    )

    value_df = df_display[
        df_display["has_real_odds"] == True
    ].copy()

    value_df = value_df[
        value_df["value"].notna()
    ]

    value_df = value_df.sort_values(
        "value",
        ascending=False
    )

    if value_df.empty:

        st.info(
            "Keine Value Bets mit echten Quoten "
            "für die aktuelle Auswahl."
        )

    else:

        for _, row in value_df.head(15).iterrows():

            selected_quote = row[
                "selected_odd"
            ]

            kelly_stake = (
                row["kelly"] *
                budget
            )

            value_percent = (
                row["value"] *
                100
            )

            bookmaker = "—"

            if row["prediction"] == "1":
                bookmaker = row[
                    "bookmaker_1"
                ]

            elif row["prediction"] == "X":
                bookmaker = row[
                    "bookmaker_x"
                ]

            elif row["prediction"] == "2":
                bookmaker = row[
                    "bookmaker_2"
                ]

            st.markdown(
                f"### {row['home']} "
                f"vs {row['away']}"
            )

            st.write(
                f"**{row['league']}** | "
                f"{row['local_datetime']}"
            )

            col1, col2, col3, col4, col5 = (
                st.columns(5)
            )

            col1.metric(
                "Tipp",
                row["prediction"]
            )

            col2.metric(
                "Quote",
                f"{selected_quote:.2f}"
            )

            col3.metric(
                "Chance",
                f"{row['confidence'] * 100:.1f}%"
            )

            col4.metric(
                "Value",
                f"{value_percent:+.2f}%"
            )

            col5.metric(
                "Kelly",
                f"{kelly_stake:.2f} €"
            )

            st.caption(
                f"Buchmacher: {bookmaker} | "
                f"Risiko: {row['risk']}"
            )

            st.divider()

# ============================================================
# TAB 2
# ============================================================

with tab2:

    st.subheader(
        "🤖 Vollständige Spielanalyse"
    )

    display = df_display.copy()

    if not display.empty:

        display["Chance"] = (
            display["confidence"] * 100
        ).round(1).astype(str) + "%"

        display["Value"] = np.where(
            display["value"].notna(),
            (
                display["value"] * 100
            ).round(2).astype(str) + "%",
            "—"
        )

        display["Quote"] = display[
            "selected_odd"
        ].apply(
            lambda x:
            f"{x:.2f}"
            if pd.notna(x)
            else "—"
        )

        display["1"] = (
            display["p1"] * 100
        ).round(1).astype(str) + "%"

        display["X"] = (
            display["px"] * 100
        ).round(1).astype(str) + "%"

        display["2"] = (
            display["p2"] * 100
        ).round(1).astype(str) + "%"

        columns = [
            "local_datetime",
            "league",
            "home",
            "away",
            "1",
            "X",
            "2",
            "prediction",
            "Chance",
            "Quote",
            "Value",
            "risk"
        ]

        st.dataframe(
            display[columns],
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# TAB 3
# ============================================================

with tab3:

    st.subheader(
        "📊 Aktuelle Buchmacherquoten"
    )

    odds_display = df_display.copy()

    odds_display["Quote 1"] = (
        odds_display["odd_1"]
        .apply(
            lambda x:
            f"{x:.2f}"
            if pd.notna(x)
            else "—"
        )
    )

    odds_display["Quote X"] = (
        odds_display["odd_x"]
        .apply(
            lambda x:
            f"{x:.2f}"
            if pd.notna(x)
            else "—"
        )
    )

    odds_display["Quote 2"] = (
        odds_display["odd_2"]
        .apply(
            lambda x:
            f"{x:.2f}"
            if pd.notna(x)
            else "—"
        )
    )

    odds_columns = [
        "local_datetime",
        "league",
        "home",
        "away",
        "Quote 1",
        "Quote X",
        "Quote 2",
        "bookmaker_1",
        "bookmaker_x",
        "bookmaker_2"
    ]

    st.dataframe(
        odds_display[odds_columns],
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Es werden ausschließlich echte Quoten der "
        "Odds API angezeigt. Fehlende Quoten werden "
        "nicht durch Modellquoten ersetzt."
    )

# ============================================================
# TAB 4
# ============================================================

with tab4:

    st.subheader(
        "🎟️ Aktuelle Kombi"
    )

    if kombi_df.empty:

        st.warning(
            f"Keine {num_legs} Legs mit echten "
            f"Quoten verfügbar."
        )

    else:

        st.success(
            f"{num_legs}er-Kombi erfolgreich erstellt."
        )

        rows = []

        for _, row in kombi_df.iterrows():

            bookmaker = "—"

            if row["prediction"] == "1":
                bookmaker = row[
                    "bookmaker_1"
                ]

            elif row["prediction"] == "X":
                bookmaker = row[
                    "bookmaker_x"
                ]

            else:
                bookmaker = row[
                    "bookmaker_2"
                ]

            rows.append({
                "Spiel": (
                    f"{row['home']} – "
                    f"{row['away']}"
                ),
                "Zeit": row[
                    "local_datetime"
                ],
                "Tipp": row[
                    "prediction"
                ],
                "Quote": round(
                    row["selected_odd"],
                    2
                ),
                "Chance": (
                    f"{row['confidence'] * 100:.1f}%"
                ),
                "Value": (
                    f"{row['value'] * 100:+.2f}%"
                ),
                "Buchmacher": bookmaker
            })

        kombi_table = pd.DataFrame(
            rows
        )

        st.dataframe(
            kombi_table,
            use_container_width=True,
            hide_index=True
        )

        stats_kombi = calculate_kombi_stats(
            kombi_df
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Gesamtquote",
            f"{stats_kombi['total_odd']:.2f}"
        )

        c2.metric(
            "Kombi-Wahrscheinlichkeit",
            f"{stats_kombi['probability'] * 100:.2f}%"
        )

        stake = min(
            budget * 0.05,
            10.0
        )

        c3.metric(
            "Mögliche Auszahlung",
            f"{stake * stats_kombi['total_odd']:.2f} €"
        )

# ============================================================
# FOOTER / DEBUG
# ============================================================

st.markdown("---")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Spiele",
    len(df_all)
)

col2.metric(
    "Mit echten Quoten",
    int(
        df_all["has_real_odds"].sum()
    )
)

col3.metric(
    "Value-Kandidaten",
    int(
        (
            (df_all["has_real_odds"] == True) &
            (df_all["value"].notna()) &
            (df_all["value"] > 0)
        ).sum()
    )
)

st.caption(
    "WETT-KI – Modellwahrscheinlichkeiten sind "
    "keine Garantie für Wettgewinne. "
    "Kelly ist eine mathematische Einsatzhilfe und "
    "kein Gewinnversprechen."
    )
