import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta, timezone
from itertools import combinations


# ============================================================
# WETT-KI
# ============================================================
# Daten:
#   - football-data.org = Spiele + Ergebnisse
#   - The Odds API      = aktuelle Buchmacherquoten
#
# WICHTIG:
# Es werden KEINE Beispieldaten verwendet.
# Es werden nur Spiele angezeigt, die von der Datenquelle
# als echte zukünftige Spiele geliefert werden.
# ============================================================


st.set_page_config(
    page_title="WETT-KI",
    page_icon="⚽",
    layout="wide"
)


# ============================================================
# KONFIGURATION
# ============================================================

FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
ODDS_API_URL = "https://api.the-odds-api.com/v4"

LOCAL_TZ = "Europe/Berlin"

# football-data.org Codes
LEAGUES = {
    "Premier League": {
        "football_data": "PL",
        "odds": "soccer_epl",
    },
    "Bundesliga": {
        "football_data": "BL1",
        "odds": "soccer_germany_bundesliga",
    },
    "La Liga": {
        "football_data": "PD",
        "odds": "soccer_spain_la_liga",
    },
    "Serie A": {
        "football_data": "SA",
        "odds": "soccer_italy_serie_a",
    },
    "Ligue 1": {
        "football_data": "FL1",
        "odds": "soccer_france_ligue_one",
    },
    "Champions League": {
        "football_data": "CL",
        "odds": "soccer_uefa_champs_league",
    },
    "Europa League": {
        "football_data": "EL",
        "odds": "soccer_uefa_europa_league",
    },
    "Conference League": {
        "football_data": "EC",
        "odds": "soccer_uefa_europa_conference_league",
    },
}


# ============================================================
# SESSION STATE
# ============================================================

if "fixtures" not in st.session_state:
    st.session_state.fixtures = pd.DataFrame()

if "last_update" not in st.session_state:
    st.session_state.last_update = None

if "errors" not in st.session_state:
    st.session_state.errors = []

if "football_token" not in st.session_state:
    st.session_state.football_token = ""

if "odds_key" not in st.session_state:
    st.session_state.odds_key = ""


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
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        return None


def format_local_datetime(value):
    dt = parse_utc(value)

    if dt is None:
        return "—"

    try:
        local_dt = dt.astimezone(
            __import__("zoneinfo").ZoneInfo(LOCAL_TZ)
        )

        return local_dt.strftime(
            "%d.%m.%Y %H:%M"
        )

    except Exception:
        return dt.strftime(
            "%d.%m.%Y %H:%M"
        )


def next_friday():
    """
    Liefert den kommenden Freitag.

    Wenn heute Samstag/Sonntag etc. ist,
    wird der nächste Freitag genommen.

    Wenn heute Freitag ist, wird HEUTE genommen.
    """

    today = utc_now().date()

    weekday = today.weekday()

    # Freitag = 4
    days = (4 - weekday) % 7

    return today + timedelta(days=days)


def get_week_dates():
    start = next_friday()

    return [
        start + timedelta(days=i)
        for i in range(7)
    ]


def normalize_name(name):
    if not name:
        return ""

    replacements = {
        " FC": "",
        " CF": "",
        " AFC": "",
        " United": "",
        " Utd": "",
        "Football Club": "",
    }

    result = str(name).strip()

    for old, new in replacements.items():
        result = result.replace(
            old,
            new
        )

    return (
        result.lower()
        .replace(".", "")
        .replace("-", " ")
        .replace("'", "")
        .strip()
    )


def names_match(a, b):
    a = normalize_name(a)
    b = normalize_name(b)

    if not a or not b:
        return False

    if a == b:
        return True

    if a in b or b in a:
        return True

    return False


# ============================================================
# API REQUEST HELPER
# ============================================================

def api_get(
    url,
    headers=None,
    params=None,
    timeout=25
):

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=timeout
        )

        if response.status_code == 200:
            return response.json(), None

        if response.status_code == 401:
            return None, (
                "401 – API-Key/Token ungültig."
            )

        if response.status_code == 403:
            return None, (
                "403 – Zugriff auf diesen "
                "Datenbereich nicht erlaubt."
            )

        if response.status_code == 404:
            return None, (
                "404 – Datenquelle oder "
                "Wettbewerb nicht gefunden."
            )

        if response.status_code == 429:
            return None, (
                "429 – API-Limit erreicht. "
                "Bitte kurz warten."
            )

        try:
            data = response.json()

            message = (
                data.get("message")
                or data.get("error")
                or str(data)
            )

        except Exception:
            message = response.text[:300]

        return None, (
            f"HTTP {response.status_code}: "
            f"{message}"
        )

    except requests.exceptions.Timeout:
        return None, (
            "Zeitüberschreitung beim "
            "Abruf der Daten."
        )

    except requests.exceptions.RequestException as e:
        return None, (
            f"Netzwerkfehler: {e}"
        )

    except Exception as e:
        return None, (
            f"Unbekannter Fehler: {e}"
        )


# ============================================================
# FOOTBALL-DATA.ORG
# ============================================================

def get_current_fixtures(
    token,
    competition_codes,
    start_date,
    end_date
):

    url = (
        f"{FOOTBALL_DATA_URL}/matches"
    )

    headers = {
        "X-Auth-Token": token
    }

    params = {
        "dateFrom": start_date.isoformat(),
        "dateTo": (
            end_date + timedelta(days=1)
        ).isoformat(),
        "competitions": ",".join(
            competition_codes
        ),
        "limit": 500,
    }

    data, error = api_get(
        url,
        headers=headers,
        params=params
    )

    if error:
        return [], error

    matches = data.get(
        "matches",
        []
    )

    rows = []

    current_time = utc_now()

    for match in matches:

        try:

            utc_date = parse_utc(
                match.get("utcDate")
            )

            if utc_date is None:
                continue

            # ABSOLUT WICHTIG:
            # Keine alten Spiele.
            if utc_date <= current_time:
                continue

            status = str(
                match.get(
                    "status",
                    ""
                )
            ).upper()

            # Abgesagte/annullierte Spiele raus.
            if status in {
                "CANCELLED",
                "POSTPONED",
                "SUSPENDED",
                "FINISHED",
                "IN_PLAY",
                "PAUSED",
            }:
                continue

            competition = match.get(
                "competition",
                {}
            )

            competition_code = (
                competition.get(
                    "code"
                )
            )

            competition_name = (
                competition.get(
                    "name"
                )
            )

            home = match.get(
                "homeTeam",
                {}
            )

            away = match.get(
                "awayTeam",
                {}
            )

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

            rows.append({
                "match_id": match.get("id"),
                "competition_code":
                    competition_code,
                "league":
                    competition_name,
                "utcDate":
                    utc_date,
                "home":
                    home_name,
                "away":
                    away_name,
                "status":
                    status,
            })

        except Exception:
            continue

    return rows, None


# ============================================================
# HISTORISCHE SPIELE
# ============================================================

def get_historical_matches(
    token,
    competition_codes,
    days_back=180
):

    end_date = utc_now().date()

    start_date = (
        end_date
        - timedelta(days=days_back)
    )

    url = (
        f"{FOOTBALL_DATA_URL}/matches"
    )

    headers = {
        "X-Auth-Token": token
    }

    params = {
        "dateFrom":
            start_date.isoformat(),
        "dateTo":
            end_date.isoformat(),
        "competitions":
            ",".join(competition_codes),
        "status":
            "FINISHED",
        "limit": 500,
    }

    data, error = api_get(
        url,
        headers=headers,
        params=params
    )

    if error:
        return [], error

    return data.get(
        "matches",
        []
    ), None


# ============================================================
# TEAM FORM
# ============================================================

def build_team_stats(
    historical_matches
):

    stats = {}

    for match in historical_matches:

        try:

            status = str(
                match.get(
                    "status",
                    ""
                )
            ).upper()

            if status != "FINISHED":
                continue

            home = match.get(
                "homeTeam",
                {}
            )

            away = match.get(
                "awayTeam",
                {}
            )

            home_name = (
                home.get("name")
                or home.get("shortName")
            )

            away_name = (
                away.get("name")
                or away.get("shortName")
            )

            score = match.get(
                "score",
                {}
            )

            full_time = score.get(
                "fullTime",
                {}
            )

            hg = full_time.get(
                "home"
            )

            ag = full_time.get(
                "away"
            )

            if hg is None or ag is None:
                continue

            hg = safe_float(hg)
            ag = safe_float(ag)

            if hg is None or ag is None:
                continue

            if home_name not in stats:
                stats[home_name] = {
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "gf": 0,
                    "ga": 0,
                    "home_played": 0,
                    "home_gf": 0,
                    "home_ga": 0,
                    "recent": [],
                }

            if away_name not in stats:
                stats[away_name] = {
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "gf": 0,
                    "ga": 0,
                    "home_played": 0,
                    "home_gf": 0,
                    "home_ga": 0,
                    "recent": [],
                }

            hs = stats[home_name]
            aws = stats[away_name]

            hs["played"] += 1
            hs["gf"] += hg
            hs["ga"] += ag
            hs["home_played"] += 1
            hs["home_gf"] += hg
            hs["home_ga"] += ag

            aws["played"] += 1
            aws["gf"] += ag
            aws["ga"] += hg

            if hg > ag:

                hs["wins"] += 1
                aws["losses"] += 1

                hs["recent"].append("W")
                aws["recent"].append("L")

            elif hg < ag:

                hs["losses"] += 1
                aws["wins"] += 1

                hs["recent"].append("L")
                aws["recent"].append("W")

            else:

                hs["draws"] += 1
                aws["draws"] += 1

                hs["recent"].append("D")
                aws["recent"].append("D")

        except Exception:
            continue

    return stats


# ============================================================
# POISSON
# ============================================================

def poisson_pmf(
    goals,
    expected
):

    try:

        return (
            math.exp(-expected)
            * expected ** goals
            / math.factorial(goals)
        )

    except Exception:
        return 0.0


def poisson_1x2(
    home_lambda,
    away_lambda
):

    p1 = 0.0
    px = 0.0
    p2 = 0.0

    for home_goals in range(0, 9):

        for away_goals in range(0, 9):

            p_home = poisson_pmf(
                home_goals,
                home_lambda
            )

            p_away = poisson_pmf(
                away_goals,
                away_lambda
            )

            p = (
                p_home
                * p_away
            )

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
            "2": 1 / 3,
        }

    return {
        "1": p1 / total,
        "X": px / total,
        "2": p2 / total,
    }


# ============================================================
# STATISTISCHE MODELLBERECHNUNG
# ============================================================

def calculate_model(
    home,
    away,
    stats
):

    default_home_attack = 1.45
    default_away_attack = 1.15

    hs = stats.get(
        home
    )

    aws = stats.get(
        away
    )

    if hs:

        played = max(
            hs["played"],
            1
        )

        home_gf = (
            hs["home_gf"]
            / max(
                hs["home_played"],
                1
            )
        )

        home_ga = (
            hs["home_ga"]
            / max(
                hs["home_played"],
                1
            )
        )

        overall_gf = (
            hs["gf"]
            / played
        )

        overall_ga = (
            hs["ga"]
            / played
        )

        home_attack = (
            0.60 * home_gf
            + 0.40 * overall_gf
        )

        home_defence = (
            0.60 * home_ga
            + 0.40 * overall_ga
        )

        recent = hs[
            "recent"
        ][-5:]

        recent_points = 0

        for result in recent:

            if result == "W":
                recent_points += 3

            elif result == "D":
                recent_points += 1

        recent_factor = (
            recent_points
            / max(
                len(recent) * 3,
                1
            )
        )

    else:

        home_attack = (
            default_home_attack
        )

        home_defence = 1.20

        recent_factor = 0.50

    if aws:

        played = max(
            aws["played"],
            1
        )

        away_gf = (
            aws["gf"]
            / played
        )

        away_ga = (
            aws["ga"]
            / played
        )

        recent = aws[
            "recent"
        ][-5:]

        recent_points = 0

        for result in recent:

            if result == "W":
                recent_points += 3

            elif result == "D":
                recent_points += 1

        away_recent_factor = (
            recent_points
            / max(
                len(recent) * 3,
                1
            )
        )

    else:

        away_gf = (
            default_away_attack
        )

        away_ga = 1.35

        away_recent_factor = 0.50

    # --------------------------------------------------------
    # Erwartete Tore
    # --------------------------------------------------------

    home_lambda = (
        0.55 * home_attack
        + 0.45 * away_ga
    )

    away_lambda = (
        0.55 * away_gf
        + 0.45 * home_defence
    )

    # Heimvorteil
    home_lambda *= 1.08

    # Form leicht berücksichtigen
    home_lambda *= (
        0.92
        + 0.16 * recent_factor
    )

    away_lambda *= (
        0.92
        + 0.16 * away_recent_factor
    )

    # Extreme Werte verhindern
    home_lambda = min(
        max(home_lambda, 0.25),
        3.50
    )

    away_lambda = min(
        max(away_lambda, 0.20),
        3.20
    )

    probabilities = poisson_1x2(
        home_lambda,
        away_lambda
    )

    return probabilities


# ============================================================
# ODDS API
# ============================================================

def get_odds_for_sport(
    odds_key,
    sport_key
):

    if not odds_key:
        return [], None

    url = (
        f"{ODDS_API_URL}/sports/"
        f"{sport_key}/odds"
    )

    params = {
        "apiKey": odds_key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }

    data, error = api_get(
        url,
        params=params
    )

    if error:
        return [], error

    if not isinstance(data, list):
        return [], (
            "Odds API lieferte kein "
            "gültiges Listenformat."
        )

    return data, None


# ============================================================
# ODDS VERARBEITUNG
# ============================================================

def extract_best_odds(
    event
):

    result = {
        "odd_1": None,
        "odd_x": None,
        "odd_2": None,
        "bookmaker_1": None,
        "bookmaker_x": None,
        "bookmaker_2": None,
    }

    home = event.get(
        "home_team"
    )

    away = event.get(
        "away_team"
    )

    bookmakers = event.get(
        "bookmakers",
        []
    )

    for bookmaker in bookmakers:

        bookmaker_name = (
            bookmaker.get(
                "title"
            )
            or bookmaker.get(
                "key"
            )
        )

        markets = bookmaker.get(
            "markets",
            []
        )

        for market in markets:

            if market.get("key") != "h2h":
                continue

            outcomes = market.get(
                "outcomes",
                []
            )

            for outcome in outcomes:

                name = outcome.get(
                    "name"
                )

                price = safe_float(
                    outcome.get(
                        "price"
                    )
                )

                if price is None:
                    continue

                # Heim
                if (
                    names_match(
                        name,
                        home
                    )
                ):

                    if (
                        result["odd_1"]
                        is None
                        or price
                        > result["odd_1"]
                    ):

                        result["odd_1"] = price
                        result[
                            "bookmaker_1"
                        ] = bookmaker_name

                # Auswärts
                elif (
                    names_match(
                        name,
                        away
                    )
                ):

                    if (
                        result["odd_2"]
                        is None
                        or price
                        > result["odd_2"]
                    ):

                        result["odd_2"] = price
                        result[
                            "bookmaker_2"
                        ] = bookmaker_name

                # Unentschieden
                elif str(name).lower() in {
                    "draw",
                    "tie",
                    "unentschieden",
                }:

                    if (
                        result["odd_x"]
                        is None
                        or price
                        > result["odd_x"]
                    ):

                        result["odd_x"] = price
                        result[
                            "bookmaker_x"
                        ] = bookmaker_name

    return result


def build_odds_index(
    all_odds
):

    index = []

    for league_name, events in all_odds.items():

        for event in events:

            event_home = event.get(
                "home_team"
            )

            event_away = event.get(
                "away_team"
            )

            commence = parse_utc(
                event.get(
                    "commence_time"
                )
            )

            if not event_home or not event_away:
                continue

            if commence is None:
                continue

            odds = extract_best_odds(
                event
            )

            index.append({
                "league":
                    league_name,
                "home":
                    event_home,
                "away":
                    event_away,
                "commence":
                    commence,
                **odds
            })

    return index


def find_matching_odds(
    row,
    odds_index
):

    match_time = row[
        "utcDate"
    ]

    best = None
    best_score = 999999

    for candidate in odds_index:

        if not names_match(
            row["home"],
            candidate["home"]
        ):
            continue

        if not names_match(
            row["away"],
            candidate["away"]
        ):
            continue

        time_difference = abs(
            (
                match_time
                - candidate["commence"]
            ).total_seconds()
        )

        # Nur vernünftige zeitliche Übereinstimmung.
        if time_difference > 12 * 3600:
            continue

        if time_difference < best_score:

            best_score = time_difference
            best = candidate

    return best


# ============================================================
# MARKET PROBABILITY
# ============================================================

def market_probabilities(
    odd_1,
    odd_x,
    odd_2
):

    if (
        odd_1 is None
        or odd_x is None
        or odd_2 is None
    ):
        return None

    if (
        odd_1 <= 1
        or odd_x <= 1
        or odd_2 <= 1
    ):
        return None

    raw = np.array([
        1 / odd_1,
        1 / odd_x,
        1 / odd_2,
    ])

    total = raw.sum()

    if total <= 0:
        return None

    normalized = (
        raw / total
    )

    return {
        "1": float(normalized[0]),
        "X": float(normalized[1]),
        "2": float(normalized[2]),
    }


# ============================================================
# ANALYSE
# ============================================================

def analyze_match(
    row,
    stats
):

    model = calculate_model(
        row["home"],
        row["away"],
        stats
    )

    p1 = model["1"]
    px = model["X"]
    p2 = model["2"]

    market = market_probabilities(
        row.get("odd_1"),
        row.get("odd_x"),
        row.get("odd_2")
    )

    # --------------------------------------------------------
    # Modell + Markt
    # --------------------------------------------------------

    if market:

        final = {
            "1":
                0.70 * p1
                + 0.30 * market["1"],

            "X":
                0.70 * px
                + 0.30 * market["X"],

            "2":
                0.70 * p2
                + 0.30 * market["2"],
        }

    else:

        final = {
            "1": p1,
            "X": px,
            "2": p2,
        }

    total = sum(
        final.values()
    )

    final = {
        key:
            value / total
        for key, value in final.items()
    }

    prediction = max(
        final,
        key=final.get
    )

    confidence = final[
        prediction
    ]

    sorted_values = sorted(
        final.values(),
        reverse=True
    )

    gap = (
        sorted_values[0]
        - sorted_values[1]
    )

    # --------------------------------------------------------
    # Risiko
    # --------------------------------------------------------

    if (
        confidence >= 0.64
        and gap >= 0.20
    ):

        risk = "LOW"

    elif (
        confidence >= 0.54
        and gap >= 0.10
    ):

        risk = "MID"

    else:

        risk = "HIGH"

    # --------------------------------------------------------
    # Value
    # --------------------------------------------------------

    selected_odd = None

    if prediction == "1":
        selected_odd = row.get(
            "odd_1"
        )

    elif prediction == "X":
        selected_odd = row.get(
            "odd_x"
        )

    else:
        selected_odd = row.get(
            "odd_2"
        )

    if selected_odd:

        value = (
            confidence
            * selected_odd
            - 1
        )

    else:

        value = None

    return {
        "p1": final["1"],
        "px": final["X"],
        "p2": final["2"],
        "prediction":
            prediction,
        "confidence":
            confidence,
        "risk":
            risk,
        "value":
            value,
    }


# ============================================================
# GESAMTDATEN LADEN
# ============================================================

def load_all_data(
    football_token,
    odds_key,
    selected_leagues
):

    errors = []

    if not football_token:
        return (
            pd.DataFrame(),
            [
                "Kein football-data.org Token "
                "eingetragen."
            ]
        )

    selected = [
        LEAGUES[name]
        for name in selected_leagues
    ]

    competition_codes = [
        item["football_data"]
        for item in selected
    ]

    # --------------------------------------------------------
    # Zeitraum Freitag -> Donnerstag
    # --------------------------------------------------------

    dates = get_week_dates()

    start_date = dates[0]
    end_date = dates[-1]

    # --------------------------------------------------------
    # Kommende Spiele
    # EIN Request für alle ausgewählten Ligen
    # --------------------------------------------------------

    fixtures, error = (
        get_current_fixtures(
            football_token,
            competition_codes,
            start_date,
            end_date
        )
    )

    if error:
        errors.append(
            "Spiele: " + error
        )

    if not fixtures:

        return (
            pd.DataFrame(),
            errors
        )

    df = pd.DataFrame(
        fixtures
    )

    # --------------------------------------------------------
    # Historische Daten für Form
    # --------------------------------------------------------

    historical, error = (
        get_historical_matches(
            football_token,
            competition_codes,
            days_back=180
        )
    )

    if error:

        errors.append(
            "Formdaten: " + error
        )

        historical = []

    stats = build_team_stats(
        historical
    )

    # --------------------------------------------------------
    # Quoten
    # --------------------------------------------------------

    all_odds = {}

    if odds_key:

        for league_name in selected_leagues:

            sport_key = LEAGUES[
                league_name
            ]["odds"]

            odds, odds_error = (
                get_odds_for_sport(
                    odds_key,
                    sport_key
                )
            )

            if odds_error:

                errors.append(
                    f"Quoten {league_name}: "
                    f"{odds_error}"
                )

                all_odds[
                    league_name
                ] = []

            else:

                all_odds[
                    league_name
                ] = odds

    odds_index = build_odds_index(
        all_odds
    )

    # --------------------------------------------------------
    # Quoten + Analyse
    # --------------------------------------------------------

    odds_rows = []

    for _, row in df.iterrows():

        odds = find_matching_odds(
            row,
            odds_index
        )

        if odds:

            odds_rows.append(
                odds
            )

        else:

            odds_rows.append({
                "odd_1": None,
                "odd_x": None,
                "odd_2": None,
                "bookmaker_1": None,
                "bookmaker_x": None,
                "bookmaker_2": None,
            })

    odds_df = pd.DataFrame(
        odds_rows
    )

    df = pd.concat(
        [
            df.reset_index(
                drop=True
            ),
            odds_df.reset_index(
                drop=True
            )
        ],
        axis=1
    )

    # --------------------------------------------------------
    # Analyse
    # --------------------------------------------------------

    analyses = []

    for _, row in df.iterrows():

        analyses.append(
            analyze_match(
                row,
                stats
            )
        )

    analysis_df = pd.DataFrame(
        analyses
    )

    df = pd.concat(
        [
            df.reset_index(
                drop=True
            ),
            analysis_df.reset_index(
                drop=True
            )
        ],
        axis=1
    )

    # --------------------------------------------------------
    # Lokale Zeit
    # --------------------------------------------------------

    df["local_datetime"] = (
        df["utcDate"]
        .apply(
            format_local_datetime
        )
    )

    df["date"] = (
        df["utcDate"]
        .apply(
            lambda x:
                x.astimezone(
                    __import__("zoneinfo")
                    .ZoneInfo(LOCAL_TZ)
                ).date()
        )
    )

    df["time"] = (
        df["utcDate"]
        .apply(
            lambda x:
                x.astimezone(
                    __import__("zoneinfo")
                    .ZoneInfo(LOCAL_TZ)
                ).strftime("%H:%M")
        )
    )

    # --------------------------------------------------------
    # Nur Spiele des definierten Zeitraums
    # --------------------------------------------------------

    df = df[
        (
            df["date"]
            >= start_date
        )
        &
        (
            df["date"]
            <= end_date
        )
    ]

    # --------------------------------------------------------
    # Sicherheitscheck:
    # NUR zukünftige Spiele
    # --------------------------------------------------------

    df = df[
        df["utcDate"]
        > utc_now()
    ]

    # Keine Duplikate
    df = df.drop_duplicates(
        subset=["match_id"]
    )

    df = df.sort_values(
        "utcDate"
    ).reset_index(
        drop=True
    )

    return df, errors


# ============================================================
# SCHEIN-GENERATOR
# ============================================================

def ticket_probability(
    matches
):

    if matches.empty:
        return 0

    return float(
        matches["confidence"].prod()
    )


def build_ticket(
    dataframe,
    risk_levels,
    legs
):

    candidates = dataframe[
        dataframe["risk"].isin(
            risk_levels
        )
    ].copy()

    if len(candidates) < legs:
        return pd.DataFrame()

    candidates = candidates.sort_values(
        [
            "confidence",
            "value"
        ],
        ascending=[
            False,
            False
        ]
    )

    return candidates.head(
        legs
    ).copy()


def system_combinations(
    dataframe,
    min_legs,
    max_legs
):

    if dataframe.empty:
        return []

    candidates = dataframe.sort_values(
        "confidence",
        ascending=False
    ).head(8)

    result = []

    for size in range(
        min_legs,
        max_legs + 1
    ):

        if len(candidates) < size:
            continue

        for combo in combinations(
            range(len(candidates)),
            size
        ):

            rows = candidates.iloc[
                list(combo)
            ]

            probability = (
                ticket_probability(
                    rows
                )
            )

            result.append({
                "size": size,
                "probability":
                    probability,
                "rows":
                    rows
            })

    result.sort(
        key=lambda x:
            x["probability"],
        reverse=True
    )

    return result


# ============================================================
# BUDGET-EMPFEHLUNG
# ============================================================

def budget_plan(
    budget
):

    if budget < 10:

        return {
            "LOW": budget * 0.70,
            "MID": budget * 0.25,
            "HIGH": budget * 0.05,
        }

    if budget < 50:

        return {
            "LOW": budget * 0.60,
            "MID": budget * 0.30,
            "HIGH": budget * 0.10,
        }

    return {
        "LOW": budget * 0.55,
        "MID": budget * 0.30,
        "HIGH": budget * 0.15,
    }


# ============================================================
# TITEL
# ============================================================

st.title("⚽ WETT-KI")

st.caption(
    "Aktuelle Fußballspiele · 1/X/2 · "
    "KI-Analyse · Buchmacherquoten"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "⚙️ Einstellungen"
)

st.sidebar.markdown(
    "### 🔑 Datenquellen"
)

football_token = st.sidebar.text_input(
    "football-data.org Token",
    value=st.session_state.football_token,
    type="password",
    help=(
        "Token von football-data.org"
    )
)

odds_key = st.sidebar.text_input(
    "The Odds API Key",
    value=st.session_state.odds_key,
    type="password",
    help=(
        "Optional für aktuelle "
        "Buchmacherquoten."
    )
)

st.session_state.football_token = (
    football_token.strip()
)

st.session_state.odds_key = (
    odds_key.strip()
)

st.sidebar.markdown("---")

selected_leagues = st.sidebar.multiselect(
    "Wettbewerbe",
    list(LEAGUES.keys()),
    default=[
        "Bundesliga",
        "Premier League",
        "La Liga",
        "Serie A",
        "Ligue 1",
        "Champions League",
        "Europa League",
        "Conference League",
    ]
)

budget = st.sidebar.number_input(
    "💰 Budget (€)",
    min_value=1.0,
    value=50.0,
    step=5.0
)

st.sidebar.markdown("---")

if st.sidebar.button(
    "🔄 AKTUELLE DATEN LADEN",
    use_container_width=True
):

    with st.spinner(
        "Aktuelle Fußballspiele werden geladen..."
    ):

        data, errors = load_all_data(
            football_token,
            odds_key,
            selected_leagues
        )

        st.session_state.fixtures = data

        st.session_state.errors = errors

        st.session_state.last_update = (
            datetime.now()
        )


# ============================================================
# HAUPTANSICHT
# ============================================================

df = st.session_state.fixtures.copy()

if not df.empty:

    df = df[
        df["league"].isin(
            selected_leagues
        )
    ].copy()


# ============================================================
# KEINE DATEN
# ============================================================

if df.empty:

    if not football_token:

        st.warning(
            "🔑 Bitte zuerst deinen "
            "football-data.org Token eintragen."
        )

        st.info(
            "Ohne diesen Token kann die App "
            "keine aktuellen Spiele abrufen."
        )

    else:

        st.error(
            "Es wurden keine kommenden Spiele "
            "für den ausgewählten Zeitraum gefunden."
        )

        st.info(
            "Die App verwendet ausschließlich "
            "echte zukünftige Spiele. "
            "Es werden keine Beispieldaten angezeigt."
        )

    if st.session_state.errors:

        with st.expander(
            "🔧 Technische Details"
        ):

            for error in (
                st.session_state.errors
            ):
                st.write(
                    "• " + str(error)
                )

    st.markdown("---")

    st.markdown(
        """
        ### 📅 Abgefragter Zeitraum

        **Freitag bis Donnerstag**

        Die App berechnet diesen Zeitraum automatisch
        aus dem aktuellen Datum.

        ### 🔐 Datenquellen

        **Spiele:** football-data.org

        **Quoten:** The Odds API

        **Keine API-Football-Abhängigkeit.**

        **Keine ESPN-Abhängigkeit.**
        """
    )

    st.stop()


# ============================================================
# KENNZAHLEN
# ============================================================

total_games = len(df)

low_count = len(
    df[df["risk"] == "LOW"]
)

mid_count = len(
    df[df["risk"] == "MID"]
)

high_count = len(
    df[df["risk"] == "HIGH"]
)

odds_count = len(
    df[
        df["odd_1"].notna()
        &
        df["odd_x"].notna()
        &
        df["odd_2"].notna()
    ]
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "⚽ Spiele",
        total_games
    )

with col2:
    st.metric(
        "🟢 LOW",
        low_count
    )

with col3:
    st.metric(
        "🟡 MID",
        mid_count
    )

with col4:
    st.metric(
        "📊 Spiele mit 1/X/2-Quoten",
        odds_count
    )


if st.session_state.last_update:

    st.caption(
        "Letzte Aktualisierung: "
        +
        st.session_state.last_update.strftime(
            "%d.%m.%Y %H:%M:%S"
        )
    )


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "🏠 Dashboard",
        "📅 Spiele",
        "🤖 KI-Analyse",
        "🎟️ Scheine",
        "📊 Quoten",
    ]
)


# ============================================================
# DASHBOARD
# ============================================================

with tab1:

    st.subheader(
        "🔥 Beste aktuellen Tipps"
    )

    dashboard = df.copy()

    dashboard = dashboard.sort_values(
        [
            "confidence",
            "value"
        ],
        ascending=[
            False,
            False
        ]
    )

    for _, row in dashboard.head(10).iterrows():

        prediction = row[
            "prediction"
        ]

        if prediction == "1":
            symbol = "🏠"
            tip = "1"

        elif prediction == "X":
            symbol = "🤝"
            tip = "X"

        else:
            symbol = "✈️"
            tip = "2"

        value_text = "—"

        if row["value"] is not None:
            value_text = (
                f"{row['value'] * 100:+.1f}%"
            )

        st.markdown(
            f"""
            **{row['time']} · "
            f"{row['league']}**

            {row['home']} – {row['away']}

            {symbol} **Tipp {tip}** ·
            Sicherheit **{row['confidence']*100:.1f}%** ·
            Risiko **{row['risk']}** ·
            Value **{value_text}**
            """
        )

        st.divider()


# ============================================================
# SPIELE
# ============================================================

with tab2:

    st.subheader(
        "📅 Freitag bis Donnerstag"
    )

    dates = sorted(
        df["date"].unique()
    )

    weekday_names = {
        0: "Montag",
        1: "Dienstag",
        2: "Mittwoch",
        3: "Donnerstag",
        4: "Freitag",
        5: "Samstag",
        6: "Sonntag",
    }

    for date_value in dates:

        day_df = df[
            df["date"] == date_value
        ].sort_values(
            "utcDate"
        )

        weekday = weekday_names[
            date_value.weekday()
        ]

        st.markdown(
            f"### {weekday}, "
            f"{date_value.strftime('%d.%m.%Y')}"
        )

        for _, row in day_df.iterrows():

            st.write(
                f"**{row['time']}** · "
                f"{row['league']} · "
                f"**{row['home']}** – "
                f"**{row['away']}**"
            )


# ============================================================
# KI-ANALYSE
# ============================================================

with tab3:

    st.subheader(
        "🤖 KI-Analyse"
    )

    analysis_view = df.copy()

    analysis_view[
        "Sicherheit"
    ] = (
        analysis_view[
            "confidence"
        ] * 100
    ).round(1)

    analysis_view[
        "1"
    ] = (
        analysis_view["p1"]
        * 100
    ).round(1)

    analysis_view[
        "X"
    ] = (
        analysis_view["px"]
        * 100
    ).round(1)

    analysis_view[
        "2"
    ] = (
        analysis_view["p2"]
        * 100
    ).round(1)

    analysis_view[
        "Value"
    ] = analysis_view[
        "value"
    ].apply(
        lambda x:
            "—"
            if pd.isna(x)
            else f"{x*100:+.1f}%"
    )

    view = analysis_view[
        [
            "local_datetime",
            "league",
            "home",
            "away",
            "1",
            "X",
            "2",
            "prediction",
            "Sicherheit",
            "risk",
            "Value",
        ]
    ].copy()

    view.columns = [
        "Anstoß",
        "Liga",
        "Heim",
        "Auswärts",
        "1 %",
        "X %",
        "2 %",
        "KI-Tipp",
        "Sicherheit %",
        "Risiko",
        "Value",
    ]

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "Die KI-Bewertung ist ein statistisches "
        "Modell aus historischen Ergebnissen, "
        "Form, Heim-/Auswärtsdaten und – wenn "
        "vorhanden – aktuellen Marktquoten. "
        "Sie ist keine Gewinn-Garantie."
    )


# ============================================================
# SCHEINE
# ============================================================

with tab4:

    st.subheader(
        "🎟️ Automatischer Schein-Generator"
    )

    st.write(
        f"Verfügbares Budget: "
        f"**{budget:.2f} €**"
    )

    allocation = budget_plan(
        budget
    )

    st.markdown(
        "### 💰 Budget-Aufteilung"
    )

    allocation_df = pd.DataFrame({
        "Kategorie": [
            "LOW",
            "MID",
            "HIGH"
        ],
        "Budget (€)": [
            round(
                allocation["LOW"],
                2
            ),
            round(
                allocation["MID"],
                2
            ),
            round(
                allocation["HIGH"],
                2
            ),
        ]
    })

    st.dataframe(
        allocation_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # LOW
    # --------------------------------------------------------

    st.markdown(
        "### 🟢 LOW – Sicherheits-Schein"
    )

    safe = build_ticket(
        df,
        ["LOW"],
        2
    )

    if not safe.empty:

        probability = (
            ticket_probability(
                safe
            )
        )

        st.write(
            f"Geschätzte gemeinsame "
            f"Wahrscheinlichkeit: "
            f"**{probability*100:.1f}%**"
        )

        for _, row in safe.iterrows():

            st.write(
                f"• {row['home']} – "
                f"{row['away']} → "
                f"**{row['prediction']}**"
            )

        st.caption(
            f"Empfohlener Einsatz: "
            f"{allocation['LOW']:.2f} €"
        )

    else:

        st.info(
            "Nicht genügend LOW-Spiele."
        )

    # --------------------------------------------------------
    # MID
    # --------------------------------------------------------

    st.markdown(
        "### 🟡 MID – Ausgewogener Schein"
    )

    balanced = build_ticket(
        df,
        ["LOW", "MID"],
        3
    )

    if not balanced.empty:

        probability = (
            ticket_probability(
                balanced
            )
        )

        st.write(
            f"Geschätzte gemeinsame "
            f"Wahrscheinlichkeit: "
            f"**{probability*100:.1f}%**"
        )

        for _, row in balanced.iterrows():

            st.write(
                f"• {row['home']} – "
                f"{row['away']} → "
                f"**{row['prediction']}**"
            )

        st.caption(
            f"Empfohlener Einsatz: "
            f"{allocation['MID']:.2f} €"
        )

    else:

        st.info(
            "Nicht genügend LOW/MID-Spiele."
        )

    # --------------------------------------------------------
    # HIGH
    # --------------------------------------------------------

    st.markdown(
        "### 🔴 HIGH – Aggressiver Schein"
    )

    aggressive = build_ticket(
        df,
        ["MID", "HIGH"],
        3
    )

    if not aggressive.empty:

        probability = (
            ticket_probability(
                aggressive
            )
        )

        st.write(
            f"Geschätzte gemeinsame "
            f"Wahrscheinlichkeit: "
            f"**{probability*100:.1f}%**"
        )

        for _, row in aggressive.iterrows():

            st.write(
                f"• {row['home']} – "
                f"{row['away']} → "
                f"**{row['prediction']}**"
            )

        st.caption(
            f"Empfohlener Einsatz: "
            f"{allocation['HIGH']:.2f} €"
        )

    else:

        st.info(
            "Nicht genügend MID/HIGH-Spiele."
        )

    # --------------------------------------------------------
    # SYSTEM
    # --------------------------------------------------------

    st.markdown("---")

    st.markdown(
        "### 🧩 System-Kombinationen"
    )

    st.write(
        "Die App sucht zusätzlich nach "
        "2/3-, 2/4-, 3/4- und 3/5-Kombinationen."
    )

    systems = system_combinations(
        df,
        2,
        5
    )

    if systems:

        for system in systems[:8]:

            size = system[
                "size"
            ]

            probability = system[
                "probability"
            ]

            rows = system[
                "rows"
            ]

            if size == 2:
                name = "2er-System"

            elif size == 3:
                name = "3er-System"

            elif size == 4:
                name = "4er-System"

            else:
                name = "5er-System"

            with st.expander(
                f"{name} · "
                f"{probability*100:.1f}%"
            ):

                for _, row in rows.iterrows():

                    st.write(
                        f"• {row['home']} – "
                        f"{row['away']} → "
                        f"**{row['prediction']}** · "
                        f"{row['risk']}"
                    )

    else:

        st.info(
            "Keine passenden System-Kombinationen."
        )


# ============================================================
# QUOTEN
# ============================================================

with tab5:

    st.subheader(
        "📊 Aktuelle 1/X/2-Buchmacherquoten"
    )

    if not odds_key:

        st.warning(
            "Kein The Odds API Key eingetragen."
        )

        st.write(
            "Die Spiele und KI-Analyse funktionieren "
            "trotzdem. Für aktuelle Buchmacherquoten "
            "muss ein Odds-API-Key eingetragen werden."
        )

    odds_view = df.copy()

    odds_view["Quote 1"] = (
        odds_view["odd_1"]
        .apply(
            lambda x:
                "—"
                if pd.isna(x)
                else f"{x:.2f}"
        )
    )

    odds_view["Quote X"] = (
        odds_view["odd_x"]
        .apply(
            lambda x:
                "—"
                if pd.isna(x)
                else f"{x:.2f}"
        )
    )

    odds_view["Quote 2"] = (
        odds_view["odd_2"]
        .apply(
            lambda x:
                "—"
                if pd.isna(x)
                else f"{x:.2f}"
        )
    )

    odds_view["Bookmaker"] = (
        odds_view[
            "bookmaker_1"
        ]
        .fillna(
            odds_view[
                "bookmaker_x"
            ]
        )
        .fillna(
            odds_view[
                "bookmaker_2"
            ]
        )
    )

    odds_display = odds_view[
        [
            "local_datetime",
            "league",
            "home",
            "away",
            "Bookmaker",
            "Quote 1",
            "Quote X",
            "Quote 2",
            "prediction",
            "risk",
        ]
    ].copy()

    odds_display.columns = [
        "Anstoß",
        "Liga",
        "Heim",
        "Auswärts",
        "Bester Bookmaker",
        "1",
        "X",
        "2",
        "KI-Tipp",
        "Risiko",
    ]

    st.dataframe(
        odds_display,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Es werden ausschließlich tatsächlich "
        "gelieferte Quoten angezeigt. "
        "Fehlende Quoten bleiben leer."
    )


# ============================================================
# FEHLER
# ============================================================

if st.session_state.errors:

    st.markdown("---")

    with st.expander(
        "🔧 Technische Hinweise"
    ):

        for error in (
            st.session_state.errors
        ):

            st.write(
                "• " + str(error)
            )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "⚠️ WETT-KI ist ein statistisches Analysewerkzeug "
    "und keine Garantie für Gewinne. Wetten können "
    "zu Verlusten führen."
                    )
