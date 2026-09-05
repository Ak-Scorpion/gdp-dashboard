import streamlit as st
import requests
import pandas as pd
import numpy as np
import math
import re
import html
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Football AI Analyzer V3",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

BERLIN_TZ = ZoneInfo("Europe/Berlin")

FOOTBALL_API_BASE = "https://v3.football.api-sports.io"
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


# ============================================================
# SECRETS
# ============================================================

def get_secret(name, default=None):
    try:
        value = st.secrets.get(name, default)
        if value is None:
            return default

        value = str(value).strip()

        if not value:
            return default

        return value
    except Exception:
        return default


FOOTBALL_API_KEY = get_secret("FOOTBALL_API_KEY")
ODDS_API_KEY = get_secret("ODDS_API_KEY")

FOOTBALL_DATA_API_KEYS = [
    get_secret("FOOTBALL_DATA_API_KEY_1"),
    get_secret("FOOTBALL_DATA_API_KEY_2"),
]

FOOTBALL_DATA_API_KEYS = [
    key for key in FOOTBALL_DATA_API_KEYS
    if key
]


# ============================================================
# SESSION STATE
# ============================================================

if "football_data_key_index" not in st.session_state:
    st.session_state.football_data_key_index = 0

if "analysis_cache_version" not in st.session_state:
    st.session_state.analysis_cache_version = "v3"


# ============================================================
# HTTP HELPERS
# ============================================================

def football_request(endpoint, params=None):
    if not FOOTBALL_API_KEY:
        return None

    url = f"{FOOTBALL_API_BASE}{endpoint}"

    headers = {
        "x-apisports-key": FOOTBALL_API_KEY
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params or {},
            timeout=15,
        )

        if response.status_code != 200:
            return None

        return response.json()

    except requests.RequestException:
        return None


def football_data_request(endpoint, params=None):
    """
    football-data.org request with automatic failover
    between the configured API keys.
    """

    if not FOOTBALL_DATA_API_KEYS:
        return None

    total_keys = len(FOOTBALL_DATA_API_KEYS)
    start_index = st.session_state.football_data_key_index

    for offset in range(total_keys):

        index = (start_index + offset) % total_keys
        key = FOOTBALL_DATA_API_KEYS[index]

        headers = {
            "X-Auth-Token": key
        }

        url = f"{FOOTBALL_DATA_BASE}{endpoint}"

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params or {},
                timeout=15,
            )

            if response.status_code == 200:
                st.session_state.football_data_key_index = index
                return response.json()

            if response.status_code in (401, 403, 429):
                continue

        except requests.RequestException:
            continue

    return None


def odds_request(endpoint, params=None):
    if not ODDS_API_KEY:
        return None

    url = f"{ODDS_API_BASE}{endpoint}"

    params = dict(params or {})
    params["apiKey"] = ODDS_API_KEY

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            return None

        return response.json()

    except requests.RequestException:
        return None


# ============================================================
# NAME / MATCHING HELPERS
# ============================================================

def normalize_name(name):
    if not name:
        return ""

    text = str(name).lower()

    replacements = [
        "football club",
        "fc",
        "afc",
        "cf",
        "sc",
        "ac",
        "sv",
        "fk",
        "1.",
        "ii",
        "b",
        "women",
        "w",
    ]

    for item in replacements:
        text = re.sub(rf"\b{re.escape(item)}\b", " ", text)

    text = re.sub(r"[^a-z0-9äöüß ]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def similarity(a, b):
    a = normalize_name(a)
    b = normalize_name(b)

    if not a or not b:
        return 0

    if a == b:
        return 1.0

    if a in b or b in a:
        return 0.92

    return SequenceMatcher(None, a, b).ratio()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


# ============================================================
# API-FOOTBALL
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_today_fixtures(target_date):
    data = football_request(
        "/fixtures",
        {
            "date": target_date,
            "timezone": "Europe/Berlin",
        },
    )

    if not data:
        return []

    return data.get("response", [])


@st.cache_data(ttl=600, show_spinner=False)
def get_predictions(fixture_id):
    data = football_request(
        "/predictions",
        {
            "fixture": fixture_id,
        },
    )

    if not data:
        return None

    response = data.get("response", [])

    if not response:
        return None

    return response[0]


@st.cache_data(ttl=900, show_spinner=False)
def get_h2h(team1, team2):
    if not team1 or not team2:
        return []

    data = football_request(
        "/fixtures/headtohead",
        {
            "h2h": f"{team1}-{team2}",
            "last": 10,
        },
    )

    if not data:
        return []

    return data.get("response", [])


# ============================================================
# FOOTBALL-DATA.ORG
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_football_data_matches(
    date_from,
    date_to,
    status="FINISHED",
):
    """
    Holt einen Match-Pool für einen Zeitraum.

    Vorteil:
    Wir machen nicht für jedes Team einen einzelnen API-Call.
    Dadurch bleibt die App wesentlich API-schonender.
    """

    data = football_data_request(
        "/matches",
        {
            "dateFrom": date_from,
            "dateTo": date_to,
            "status": status,
        },
    )

    if not data:
        return []

    return data.get("matches", [])


@st.cache_data(ttl=1800, show_spinner=False)
def get_football_data_competitions():
    data = football_data_request("/competitions")

    if not data:
        return []

    return data.get("competitions", [])


@st.cache_data(ttl=1800, show_spinner=False)
def get_football_data_standings(competition_code):
    if not competition_code:
        return None

    data = football_data_request(
        f"/competitions/{competition_code}/standings"
    )

    return data


def build_external_team_form(team_name, matches, last_n=5):
    """
    Ermittelt die letzten N Ergebnisse eines Teams
    aus football-data.org.
    """

    candidates = []

    for match in matches:

        home = (
            match.get("homeTeam", {}) or {}
        ).get("name")

        away = (
            match.get("awayTeam", {}) or {}
        ).get("name")

        score = match.get("score", {}) or {}
        full_time = score.get("fullTime", {}) or {}

        home_goals = full_time.get("home")
        away_goals = full_time.get("away")

        if home_goals is None or away_goals is None:
            continue

        home_similarity = similarity(team_name, home)
        away_similarity = similarity(team_name, away)

        if max(home_similarity, away_similarity) < 0.70:
            continue

        if home_similarity >= away_similarity:
            matched_team = home
            opponent = away
            goals_for = safe_float(home_goals)
            goals_against = safe_float(away_goals)
            location = "H"
            match_similarity = home_similarity
        else:
            matched_team = away
            opponent = home
            goals_for = safe_float(away_goals)
            goals_against = safe_float(home_goals)
            location = "A"
            match_similarity = away_similarity

        if goals_for > goals_against:
            result = "W"
            points = 3
        elif goals_for == goals_against:
            result = "D"
            points = 1
        else:
            result = "L"
            points = 0

        candidates.append({
            "date": match.get("utcDate"),
            "team": matched_team,
            "opponent": opponent,
            "result": result,
            "points": points,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "location": location,
            "similarity": match_similarity,
        })

    candidates.sort(
        key=lambda x: x.get("date") or "",
        reverse=True,
    )

    # Nur sehr gute Namensmatches verwenden
    candidates = [
        item for item in candidates
        if item["similarity"] >= 0.70
    ]

    candidates = candidates[:last_n]

    if not candidates:
        return {
            "matches": [],
            "results": "",
            "points": 0,
            "max_points": 0,
            "strength": 0,
            "goals_for": 0,
            "goals_against": 0,
        }

    points = sum(x["points"] for x in candidates)
    max_points = len(candidates) * 3

    goals_for = sum(x["goals_for"] for x in candidates)
    goals_against = sum(x["goals_against"] for x in candidates)

    strength = (
        points / max_points * 100
        if max_points
        else 0
    )

    return {
        "matches": candidates,
        "results": " ".join(x["result"] for x in candidates),
        "points": points,
        "max_points": max_points,
        "strength": strength,
        "goals_for": goals_for,
        "goals_against": goals_against,
    }


# ============================================================
# PREDICTION PARSING
# ============================================================

def parse_form_string(form):
    if not form:
        return []

    form = str(form).upper()

    return [
        char
        for char in form
        if char in ("W", "D", "L")
    ]


def form_points(form):
    values = {
        "W": 3,
        "D": 1,
        "L": 0,
    }

    return sum(values.get(x, 0) for x in form)


def form_strength(form):
    if not form:
        return 0

    return form_points(form) / (len(form) * 3) * 100


def form_difference(home_form, away_form):
    return form_strength(home_form) - form_strength(away_form)


def parse_prediction(prediction):
    if not prediction:
        return {
            "home_pct": 0,
            "draw_pct": 0,
            "away_pct": 0,
            "home_goals": None,
            "away_goals": None,
            "advice": "",
            "home_form": [],
            "away_form": [],
            "att_home": 0,
            "att_away": 0,
            "def_home": 0,
            "def_away": 0,
        }

    predictions = prediction.get("predictions", {}) or {}
    teams = prediction.get("teams", {}) or {}

    percent = predictions.get("percent", {}) or {}

    home_pct = safe_float(
        str(percent.get("home", "0")).replace("%", "")
    )

    draw_pct = safe_float(
        str(percent.get("draw", "0")).replace("%", "")
    )

    away_pct = safe_float(
        str(percent.get("away", "0")).replace("%", "")
    )

    goals = predictions.get("goals", {}) or {}

    home_goals = goals.get("home")
    away_goals = goals.get("away")

    try:
        home_goals = float(home_goals)
    except (TypeError, ValueError):
        home_goals = None

    try:
        away_goals = float(away_goals)
    except (TypeError, ValueError):
        away_goals = None

    advice = predictions.get("advice", "") or ""

    home_form = parse_form_string(
        (teams.get("home", {}) or {}).get("form")
    )

    away_form = parse_form_string(
        (teams.get("away", {}) or {}).get("form")
    )

    home_att = safe_float(
        (teams.get("home", {}) or {}).get("att")
    )

    away_att = safe_float(
        (teams.get("away", {}) or {}).get("att")
    )

    home_def = safe_float(
        (teams.get("home", {}) or {}).get("def")
    )

    away_def = safe_float(
        (teams.get("away", {}) or {}).get("def")
    )

    return {
        "home_pct": home_pct,
        "draw_pct": draw_pct,
        "away_pct": away_pct,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "advice": advice,
        "home_form": home_form,
        "away_form": away_form,
        "att_home": home_att,
        "att_away": away_att,
        "def_home": home_def,
        "def_away": away_def,
    }


# ============================================================
# POISSON MODEL
# ============================================================

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0

    return (
        math.exp(-lam)
        * (lam ** k)
        / math.factorial(k)
    )


def poisson_distribution(lam, max_goals=8):
    probabilities = np.array([
        poisson_pmf(k, lam)
        for k in range(max_goals + 1)
    ])

    total = probabilities.sum()

    if total > 0:
        probabilities = probabilities / total

    return probabilities


def score_matrix(home_xg, away_xg, max_goals=8):

    home_distribution = poisson_distribution(
        home_xg,
        max_goals,
    )

    away_distribution = poisson_distribution(
        away_xg,
        max_goals,
    )

    return np.outer(
        home_distribution,
        away_distribution,
    )


def market_probabilities(home_xg, away_xg):

    matrix = score_matrix(
        home_xg,
        away_xg,
    )

    home_win = 0
    draw = 0
    away_win = 0

    over_15 = 0
    over_25 = 0
    btts = 0

    for home_goals in range(matrix.shape[0]):
        for away_goals in range(matrix.shape[1]):

            probability = matrix[
                home_goals,
                away_goals,
            ]

            if home_goals > away_goals:
                home_win += probability

            elif home_goals == away_goals:
                draw += probability

            else:
                away_win += probability

            if home_goals + away_goals >= 2:
                over_15 += probability

            if home_goals + away_goals >= 3:
                over_25 += probability

            if home_goals >= 1 and away_goals >= 1:
                btts += probability

    return {
        "home": home_win,
        "draw": draw,
        "away": away_win,
        "1X": home_win + draw,
        "X2": draw + away_win,
        "12": home_win + away_win,
        "over_1_5": over_15,
        "over_2_5": over_25,
        "btts": btts,
    }


# ============================================================
# XG DERIVATION
# ============================================================

def derive_xg_from_prediction(pred):

    home_goals = pred.get("home_goals")
    away_goals = pred.get("away_goals")

    if (
        home_goals is not None
        and away_goals is not None
        and home_goals >= 0
        and away_goals >= 0
    ):
        return (
            max(0.1, home_goals),
            max(0.1, away_goals),
        )

    home_pct = pred.get("home_pct", 0)
    draw_pct = pred.get("draw_pct", 0)
    away_pct = pred.get("away_pct", 0)

    total = home_pct + draw_pct + away_pct

    if total > 0:
        home_pct /= total
        draw_pct /= total
        away_pct /= total

        home_xg = 1.45 + (
            home_pct - away_pct
        ) * 1.2

        away_xg = 1.15 + (
            away_pct - home_pct
        ) * 1.2

        return (
            max(0.25, home_xg),
            max(0.20, away_xg),
        )

    return 1.35, 1.10


# ============================================================
# EXTERNAL FORM ADJUSTMENT
# ============================================================

def blend_external_form(
    home_xg,
    away_xg,
    home_external,
    away_external,
):
    """
    Kleine Korrektur des Poisson-Modells anhand
    der externen Form.

    Die Anpassung bleibt bewusst begrenzt,
    damit die Form nicht das komplette Modell dominiert.
    """

    if not home_external["matches"]:
        return home_xg, away_xg

    if not away_external["matches"]:
        return home_xg, away_xg

    home_strength = home_external["strength"]
    away_strength = away_external["strength"]

    difference = (
        home_strength - away_strength
    ) / 100

    adjustment = difference * 0.20

    home_xg = home_xg + adjustment
    away_xg = away_xg - adjustment

    home_xg = clamp(home_xg, 0.20, 4.50)
    away_xg = clamp(away_xg, 0.15, 4.00)

    return home_xg, away_xg


# ============================================================
# ODDS API
# ============================================================

ODDS_SPORT_KEYS = [
    "soccer_germany_bundesliga",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga",
    "soccer_belgium_first_div",
    "soccer_turkey_super_league",
    "soccer_uefa_champs_league",
]


@st.cache_data(ttl=180, show_spinner=False)
def get_all_odds():

    if not ODDS_API_KEY:
        return []

    all_events = []

    for sport_key in ODDS_SPORT_KEYS:

        data = odds_request(
            f"/sports/{sport_key}/odds",
            {
                "regions": "eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
            },
        )

        if not data:
            continue

        if isinstance(data, list):
            all_events.extend(data)

    return all_events


def find_odds_for_match(
    home_team,
    away_team,
    events,
):

    best_event = None
    best_score = 0

    for event in events:

        event_home = event.get("home_team", "")
        event_away = event.get("away_team", "")

        home_similarity = similarity(
            home_team,
            event_home,
        )

        away_similarity = similarity(
            away_team,
            event_away,
        )

        score = (
            home_similarity
            + away_similarity
        ) / 2

        if score > best_score:
            best_score = score
            best_event = event

    if best_score < 0.70:
        return None

    return best_event


def extract_best_odds(event, preferred_bookmaker=None):

    if not event:
        return {}

    bookmakers = event.get("bookmakers", [])

    if preferred_bookmaker:
        preferred = [
            b
            for b in bookmakers
            if b.get("title") == preferred_bookmaker
        ]

        if preferred:
            bookmakers = (
                preferred
                + [
                    b
                    for b in bookmakers
                    if b not in preferred
                ]
            )

    markets = {}

    for bookmaker in bookmakers:

        bookmaker_name = bookmaker.get(
            "title",
            "Unknown",
        )

        for market in bookmaker.get("markets", []):

            market_key = market.get("key")

            outcomes = market.get(
                "outcomes",
                [],
            )

            if market_key == "h2h":

                for outcome in outcomes:

                    name = outcome.get("name")
                    price = safe_float(
                        outcome.get("price")
                    )

                    if not price:
                        continue

                    key = None

                    if name == event.get("home_team"):
                        key = "home"

                    elif name == event.get("away_team"):
                        key = "away"

                    elif str(name).lower() in (
                        "draw",
                        "tie",
                    ):
                        key = "draw"

                    if key:
                        current = markets.get(key)

                        if (
                            not current
                            or price > current["odds"]
                        ):
                            markets[key] = {
                                "odds": price,
                                "bookmaker": bookmaker_name,
                            }

            elif market_key == "totals":

                for outcome in outcomes:

                    name = str(
                        outcome.get("name", "")
                    ).lower()

                    point = safe_float(
                        outcome.get("point")
                    )

                    price = safe_float(
                        outcome.get("price")
                    )

                    if not price:
                        continue

                    if name == "over":

                        if point == 1.5:
                            key = "over_1_5"

                        elif point == 2.5:
                            key = "over_2_5"

                        else:
                            continue

                        current = markets.get(key)

                        if (
                            not current
                            or price > current["odds"]
                        ):
                            markets[key] = {
                                "odds": price,
                                "bookmaker": bookmaker_name,
                            }

    return markets


# ============================================================
# MARKET SELECTION
# ============================================================

MARKET_LABELS = {
    "home": "Heimsieg",
    "draw": "Unentschieden",
    "away": "Auswärtssieg",
    "1X": "Doppelte Chance 1X",
    "X2": "Doppelte Chance X2",
    "12": "Doppelte Chance 12",
    "over_1_5": "Over 1.5 Tore",
    "over_2_5": "Over 2.5 Tore",
    "btts": "Beide Teams treffen",
}


def select_market(
    probabilities,
    odds,
    market_type,
):

    candidates = []

    if market_type == "1X2":

        for key in [
            "home",
            "draw",
            "away",
        ]:
            if key in odds:
                candidates.append(key)

    elif market_type == "Doppelte Chance":

        for key in [
            "1X",
            "X2",
            "12",
        ]:
            if key in odds:
                candidates.append(key)

    elif market_type == "Over 1.5":

        if "over_1_5" in odds:
            candidates.append("over_1_5")

    elif market_type == "Over 2.5":

        if "over_2_5" in odds:
            candidates.append("over_2_5")

    elif market_type == "BTTS":

        if "btts" in odds:
            candidates.append("btts")

    if not candidates:
        return None

    best = None

    for key in candidates:

        probability = probabilities.get(
            key,
            0,
        )

        odds_value = odds[key]["odds"]

        value = (
            probability * odds_value - 1
        )

        item = {
            "key": key,
            "label": MARKET_LABELS.get(
                key,
                key,
            ),
            "probability": probability,
            "odds": odds_value,
            "value": value,
            "ev": value * 100,
            "bookmaker": odds[key].get(
                "bookmaker",
                "",
            ),
        }

        if (
            best is None
            or item["value"] > best["value"]
        ):
            best = item

    return best


# ============================================================
# DATA QUALITY
# ============================================================

def calculate_data_quality(
    prediction,
    h2h,
    odds,
    external_home,
    external_away,
):

    score = 0

    if prediction:
        score += 30

    if prediction:
        if (
            prediction.get("home_pct", 0)
            + prediction.get("draw_pct", 0)
            + prediction.get("away_pct", 0)
            > 0
        ):
            score += 15

    if h2h:
        score += 10

    if odds:
        score += 20

    if external_home["matches"]:
        score += 12.5

    if external_away["matches"]:
        score += 12.5

    return clamp(score)


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    model_probability,
    form_score,
    value,
    data_quality,
):

    model_score = clamp(
        model_probability * 100
    )

    form_score = clamp(form_score)

    value_score = clamp(
        50 + value * 200
    )

    confidence = (
        model_score * 0.55
        + form_score * 0.15
        + value_score * 0.20
        + data_quality * 0.10
    )

    return clamp(confidence)


# ============================================================
# SINGLE MATCH ANALYSIS
# ============================================================

@st.cache_data(ttl=180, show_spinner=False)
def analyze_fixture(
    fixture_id,
    home_team,
    away_team,
    home_id,
    away_id,
    target_date,
    market_type,
    preferred_bookmaker,
):

    prediction_raw = get_predictions(
        fixture_id
    )

    prediction = parse_prediction(
        prediction_raw
    )

    h2h = get_h2h(
        home_id,
        away_id,
    )

    # --------------------------------------------------------
    # External form from football-data.org
    # --------------------------------------------------------

    target = datetime.strptime(
        target_date,
        "%Y-%m-%d",
    ).date()

    date_to = (
        target - timedelta(days=1)
    ).isoformat()

    date_from = (
        target - timedelta(days=75)
    ).isoformat()

    external_matches = (
        get_football_data_matches(
            date_from,
            date_to,
            "FINISHED",
        )
    )

    external_home = build_external_team_form(
        home_team,
        external_matches,
        5,
    )

    external_away = build_external_team_form(
        away_team,
        external_matches,
        5,
    )

    # --------------------------------------------------------
    # XG
    # --------------------------------------------------------

    home_xg, away_xg = (
        derive_xg_from_prediction(
            prediction
        )
    )

    home_xg, away_xg = (
        blend_external_form(
            home_xg,
            away_xg,
            external_home,
            external_away,
        )
    )

    probabilities = market_probabilities(
        home_xg,
        away_xg,
    )

    # --------------------------------------------------------
    # Odds
    # --------------------------------------------------------

    all_odds = get_all_odds()

    odds_event = find_odds_for_match(
        home_team,
        away_team,
        all_odds,
    )

    odds = extract_best_odds(
        odds_event,
        preferred_bookmaker,
    )

    selected_market = select_market(
        probabilities,
        odds,
        market_type,
    )

    # --------------------------------------------------------
    # Form
    # --------------------------------------------------------

    api_home_form = prediction[
        "home_form"
    ]

    api_away_form = prediction[
        "away_form"
    ]

    api_form_difference = (
        form_difference(
            api_home_form,
            api_away_form,
        )
    )

    external_form_difference = (
        external_home["strength"]
        - external_away["strength"]
    )

    if (
        external_home["matches"]
        and external_away["matches"]
    ):
        form_score = clamp(
            (
                (
                    form_strength(api_home_form)
                    + external_home["strength"]
                ) / 2
                +
                (
                    form_strength(api_away_form)
                    + external_away["strength"]
                ) / 2
            ) / 2
        )
    else:
        form_score = clamp(
            (
                form_strength(api_home_form)
                + form_strength(api_away_form)
            ) / 2
        )

    # --------------------------------------------------------
    # Data quality
    # --------------------------------------------------------

    data_quality = calculate_data_quality(
        prediction,
        h2h,
        odds,
        external_home,
        external_away,
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if selected_market:

        confidence = calculate_confidence(
            selected_market["probability"],
            form_score,
            selected_market["value"],
            data_quality,
        )

    else:
        confidence = (
            data_quality * 0.5
            + form_score * 0.5
        )

    # --------------------------------------------------------
    # H2H summary
    # --------------------------------------------------------

    h2h_home_wins = 0
    h2h_draws = 0
    h2h_away_wins = 0

    for match in h2h:

        goals = (
            match.get("goals", {})
            or {}
        )

        h = goals.get("home")
        a = goals.get("away")

        if h is None or a is None:
            continue

        if h > a:
            h2h_home_wins += 1

        elif h == a:
            h2h_draws += 1

        else:
            h2h_away_wins += 1

    return {
        "fixture_id": fixture_id,
        "home_team": home_team,
        "away_team": away_team,
        "home_id": home_id,
        "away_id": away_id,

        "prediction": prediction,
        "h2h": h2h,

        "home_xg": home_xg,
        "away_xg": away_xg,

        "probabilities": probabilities,

        "odds": odds,
        "odds_event": odds_event,

        "selected_market": selected_market,

        "api_home_form": api_home_form,
        "api_away_form": api_away_form,

        "external_home_form": external_home,
        "external_away_form": external_away,

        "api_form_difference": api_form_difference,
        "external_form_difference": external_form_difference,

        "form_score": form_score,
        "data_quality": data_quality,
        "confidence": confidence,

        "h2h_home_wins": h2h_home_wins,
        "h2h_draws": h2h_draws,
        "h2h_away_wins": h2h_away_wins,
    }


# ============================================================
# UI HELPERS
# ============================================================

def probability_percent(value):
    return f"{value * 100:.1f}%"


def odds_text(value):
    if value is None:
        return "—"

    return f"{value:.2f}"


def result_badge(result):
    if result == "W":
        return "🟢 W"

    if result == "D":
        return "🟡 D"

    if result == "L":
        return "🔴 L"

    return result


def render_form(form):
    if not form:
        return "—"

    return " ".join(
        result_badge(x)
        for x in form
    )


def confidence_label(value):

    if value >= 80:
        return "🔥 Sehr hoch"

    if value >= 70:
        return "🟢 Hoch"

    if value >= 60:
        return "🟡 Mittel"

    if value >= 50:
        return "🟠 Niedrig"

    return "🔴 Sehr niedrig"


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⚽ Football AI Analyzer")

st.sidebar.markdown(
    "### 🔌 API-Verbindungen"
)

if FOOTBALL_API_KEY:
    st.sidebar.success(
        "API-Football verbunden"
    )
else:
    st.sidebar.error(
        "API-Football fehlt"
    )

if ODDS_API_KEY:
    st.sidebar.success(
        "The Odds API verbunden"
    )
else:
    st.sidebar.warning(
        "The Odds API fehlt"
    )

if FOOTBALL_DATA_API_KEYS:
    st.sidebar.success(
        f"football-data.org verbunden "
        f"({len(FOOTBALL_DATA_API_KEYS)} Key(s))"
    )
else:
    st.sidebar.warning(
        "football-data.org nicht konfiguriert"
    )


st.sidebar.divider()

target_date = st.sidebar.date_input(
    "📅 Spieltag",
    value=datetime.now(
        BERLIN_TZ
    ).date(),
)

market_type = st.sidebar.selectbox(
    "🎯 Markt",
    [
        "1X2",
        "Doppelte Chance",
        "Over 1.5",
        "Over 2.5",
        "BTTS",
    ],
)

min_confidence = st.sidebar.slider(
    "📊 Mindest-Confidence",
    0,
    100,
    55,
)

min_value = st.sidebar.slider(
    "💰 Mindest-Value %",
    -50,
    100,
    0,
)

preferred_bookmaker = st.sidebar.text_input(
    "🏦 Bevorzugter Bookmaker",
    value="",
)

show_without_odds = st.sidebar.checkbox(
    "Spiele ohne Quote anzeigen",
    value=False,
)


# ============================================================
# HEADER
# ============================================================

st.title("⚽ Football AI Analyzer V3")

st.markdown(
    """
    **Multi-Source Fußballanalyse**

    API-Football + football-data.org + The Odds API
    werden kombiniert, um Modellwahrscheinlichkeit,
    Form, Value und Datenqualität zu bewerten.
    """
)

st.divider()


# ============================================================
# API CHECK
# ============================================================

if not FOOTBALL_API_KEY:
    st.error(
        "❌ `FOOTBALL_API_KEY` fehlt in `.streamlit/secrets.toml`."
    )
    st.stop()


# ============================================================
# LOAD FIXTURES
# ============================================================

target_date_string = target_date.isoformat()

with st.spinner(
    "⚽ Lade Spiele..."
):

    fixtures = get_today_fixtures(
        target_date_string
    )


if not fixtures:

    st.warning(
        "Für diesen Spieltag wurden keine "
        "Spiele gefunden."
    )

    st.stop()


# ============================================================
# QUICK STATS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Spiele",
    len(fixtures),
)

col2.metric(
    "Markt",
    market_type,
)

col3.metric(
    "football-data.org",
    "✓" if FOOTBALL_DATA_API_KEYS else "—",
)

col4.metric(
    "Odds API",
    "✓" if ODDS_API_KEY else "—",
)


# ============================================================
# ANALYSIS
# ============================================================

results = []

progress = st.progress(0)

for index, fixture in enumerate(fixtures):

    fixture_id = (
        fixture.get("fixture", {})
        .get("id")
    )

    teams = fixture.get(
        "teams",
        {},
    )

    home = teams.get(
        "home",
        {},
    )

    away = teams.get(
        "away",
        {},
    )

    home_id = home.get("id")
    away_id = away.get("id")

    home_name = home.get(
        "name",
        "Home",
    )

    away_name = away.get(
        "name",
        "Away",
    )

    if not fixture_id:
        continue

    try:

        analysis = analyze_fixture(
            fixture_id=fixture_id,
            home_team=home_name,
            away_team=away_name,
            home_id=home_id,
            away_id=away_id,
            target_date=target_date_string,
            market_type=market_type,
            preferred_bookmaker=(
                preferred_bookmaker
                or None
            ),
        )

        selected = analysis[
            "selected_market"
        ]

        if selected:

            if (
                selected["value"] * 100
                < min_value
            ):
                progress.progress(
                    (index + 1) / len(fixtures)
                )
                continue

        elif not show_without_odds:

            progress.progress(
                (index + 1) / len(fixtures)
            )
            continue

        if (
            analysis["confidence"]
            < min_confidence
        ):
            progress.progress(
                (index + 1) / len(fixtures)
            )
            continue

        results.append(
            analysis
        )

    except Exception as exc:

        st.warning(
            f"Fehler bei "
            f"{home_name} – {away_name}: "
            f"{exc}"
        )

    progress.progress(
        (index + 1) / len(fixtures)
    )


progress.empty()


# ============================================================
# SORT
# ============================================================

results.sort(
    key=lambda x: (
        x["confidence"],
        (
            x["selected_market"]["value"]
            if x["selected_market"]
            else -999
        ),
    ),
    reverse=True,
)


# ============================================================
# SUMMARY
# ============================================================

st.subheader(
    f"🎯 Gefundene Empfehlungen: {len(results)}"
)


if not results:

    st.info(
        "Keine Spiele erfüllen aktuell "
        "deine Filter."
    )

    st.stop()


# ============================================================
# TOP PICKS
# ============================================================

top_results = results[:3]

cols = st.columns(
    min(3, len(top_results))
)

for col, result in zip(
    cols,
    top_results,
):

    selected = result[
        "selected_market"
    ]

    with col:

        st.markdown(
            f"### ⭐ "
            f"{html.escape(result['home_team'])}"
        )

        st.markdown(
            f"vs. "
            f"**{html.escape(result['away_team'])}**"
        )

        if selected:

            st.metric(
                "Pick",
                selected["label"],
            )

            st.metric(
                "Quote",
                odds_text(
                    selected["odds"]
                ),
            )

            st.metric(
                "Confidence",
                f"{result['confidence']:.1f}",
            )

            st.caption(
                f"EV: {selected['ev']:+.1f}%"
            )


st.divider()


# ============================================================
# MATCH CARDS
# ============================================================

st.subheader("📋 Analyse")


for result in results:

    home_name = html.escape(
        result["home_team"]
    )

    away_name = html.escape(
        result["away_team"]
    )

    selected = result[
        "selected_market"
    ]

    prediction = result[
        "prediction"
    ]

    probabilities = result[
        "probabilities"
    ]

    with st.expander(
        f"⚽ {result['home_team']} "
        f"vs. "
        f"{result['away_team']} "
        f"— Confidence "
        f"{result['confidence']:.0f}"
    ):

        # ----------------------------------------------------
        # Main metrics
        # ----------------------------------------------------

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "🏠 Home xG",
            f"{result['home_xg']:.2f}",
        )

        c2.metric(
            "✈️ Away xG",
            f"{result['away_xg']:.2f}",
        )

        c3.metric(
            "📊 Confidence",
            f"{result['confidence']:.1f}",
        )

        c4.metric(
            "🧪 Datenqualität",
            f"{result['data_quality']:.1f}",
        )

        st.markdown(
            f"**Confidence:** "
            f"{confidence_label(result['confidence'])}"
        )

        st.divider()

        # ----------------------------------------------------
        # 1X2
        # ----------------------------------------------------

        st.markdown("### 🎯 Modellwahrscheinlichkeiten")

        p1, p2, p3 = st.columns(3)

        p1.metric(
            "Heimsieg",
            probability_percent(
                probabilities["home"]
            ),
        )

        p2.metric(
            "Remis",
            probability_percent(
                probabilities["draw"]
            ),
        )

        p3.metric(
            "Auswärtssieg",
            probability_percent(
                probabilities["away"]
            ),
        )

        # ----------------------------------------------------
        # Selected pick
        # ----------------------------------------------------

        if selected:

            st.success(
                f"### 🎫 Empfehlung: "
                f"{selected['label']}\n\n"
                f"**Quote:** "
                f"{selected['odds']:.2f}  \n"
                f"**Modell:** "
                f"{selected['probability'] * 100:.1f}%  \n"
                f"**Value:** "
                f"{selected['value'] * 100:+.1f}%  \n"
                f"**EV:** "
                f"{selected['ev']:+.1f}%  \n"
                f"**Bookmaker:** "
                f"{selected['bookmaker'] or '—'}"
            )

        else:

            st.info(
                "Für diesen Markt wurde "
                "keine passende Quote gefunden."
            )

        st.divider()

        # ----------------------------------------------------
        # Form
        # ----------------------------------------------------

        form_col1, form_col2 = st.columns(2)

        with form_col1:

            st.markdown(
                f"#### 🏠 {home_name}"
            )

            st.write(
                "API-Football:",
                render_form(
                    result["api_home_form"]
                ),
            )

            ext = result[
                "external_home_form"
            ]

            st.write(
                "football-data.org:",
                render_form(
                    [
                        x["result"]
                        for x in ext["matches"]
                    ]
                ),
            )

            st.caption(
                f"{ext['points']}/"
                f"{ext['max_points']} Punkte"
            )

        with form_col2:

            st.markdown(
                f"#### ✈️ {away_name}"
            )

            st.write(
                "API-Football:",
                render_form(
                    result["api_away_form"]
                ),
            )

            ext = result[
                "external_away_form"
            ]

            st.write(
                "football-data.org:",
                render_form(
                    [
                        x["result"]
                        for x in ext["matches"]
                    ]
                ),
            )

            st.caption(
                f"{ext['points']}/"
                f"{ext['max_points']} Punkte"
            )

        # ----------------------------------------------------
        # External form table
        # ----------------------------------------------------

        st.markdown(
            "### 🌐 football-data.org Form"
        )

        form_rows = []

        for side, team_form in [
            (
                result["home_team"],
                result["external_home_form"],
            ),
            (
                result["away_team"],
                result["external_away_form"],
            ),
        ]:

            for match in team_form["matches"]:

                form_rows.append({
                    "Team": side,
                    "Gegner": match["opponent"],
                    "Ergebnis": match["result"],
                    "Tore": (
                        f"{int(match['goals_for'])}:"
                        f"{int(match['goals_against'])}"
                    ),
                    "Ort": match["location"],
                })

        if form_rows:

            st.dataframe(
                pd.DataFrame(form_rows),
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.caption(
                "Keine passende externe Form "
                "für dieses Team gefunden."
            )

        # ----------------------------------------------------
        # Odds
        # ----------------------------------------------------

        st.markdown(
            "### 💰 Quoten"
        )

        if result["odds"]:

            odds_rows = []

            for key, item in result[
                "odds"
            ].items():

                odds_rows.append({
                    "Markt": MARKET_LABELS.get(
                        key,
                        key,
                    ),
                    "Quote": item["odds"],
                    "Bookmaker": item[
                        "bookmaker"
                    ],
                })

            st.dataframe(
                pd.DataFrame(odds_rows),
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.caption(
                "Keine passende Quote gefunden."
            )

        # ----------------------------------------------------
        # H2H
        # ----------------------------------------------------

        st.markdown(
            "### 🤝 H2H"
        )

        h2h1, h2h2, h2h3 = st.columns(3)

        h2h1.metric(
            f"{home_name}",
            result["h2h_home_wins"],
        )

        h2h2.metric(
            "Remis",
            result["h2h_draws"],
        )

        h2h3.metric(
            f"{away_name}",
            result["h2h_away_wins"],
        )

        # ----------------------------------------------------
        # API-Football prediction
        # ----------------------------------------------------

        st.markdown(
            "### 🤖 API-Football Prediction"
        )

        pred1, pred2 = st.columns(2)

        with pred1:

            st.write(
                "**Advice:**",
                prediction["advice"] or "—",
            )

        with pred2:

            predicted_score = "—"

            if (
                prediction["home_goals"]
                is not None
                and prediction["away_goals"]
                is not None
            ):

                predicted_score = (
                    f"{prediction['home_goals']:.1f}"
                    f" : "
                    f"{prediction['away_goals']:.1f}"
                )

            st.write(
                "**Predicted Score:**",
                predicted_score,
            )


# ============================================================
# TICKET BUILDER
# ============================================================

st.divider()

st.subheader(
    "🎫 Ticket Builder"
)

ticket_candidates = [
    r
    for r in results
    if r["selected_market"]
]

if ticket_candidates:

    selected_ticket = st.multiselect(
        "Spiele auswählen",
        options=[
            (
                r["fixture_id"],
                f"{r['home_team']} "
                f"– "
                f"{r['away_team']} | "
                f"{r['selected_market']['label']} | "
                f"{r['selected_market']['odds']:.2f}"
            )
            for r in ticket_candidates
        ],
        format_func=lambda x: x[1],
    )

    if selected_ticket:

        selected_ids = {
            x[0]
            for x in selected_ticket
        }

        ticket_rows = [
            r
            for r in ticket_candidates
            if r["fixture_id"] in selected_ids
        ]

        total_odds = 1.0
        combined_probability = 1.0

        rows = []

        for r in ticket_rows:

            market = r[
                "selected_market"
            ]

            total_odds *= market[
                "odds"
            ]

            combined_probability *= market[
                "probability"
            ]

            rows.append({
                "Spiel": (
                    f"{r['home_team']} "
                    f"- "
                    f"{r['away_team']}"
                ),
                "Pick": market[
                    "label"
                ],
                "Quote": market[
                    "odds"
                ],
                "Modell": (
                    market[
                        "probability"
                    ] * 100
                ),
                "EV %": market[
                    "ev"
                ],
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        tc1, tc2, tc3 = st.columns(3)

        tc1.metric(
            "Gesamtquote",
            f"{total_odds:.2f}",
        )

        tc2.metric(
            "Modellwahrscheinlichkeit",
            f"{combined_probability * 100:.2f}%",
        )

        tc3.metric(
            "Theoretischer EV",
            f"{(
                combined_probability
                * total_odds
                - 1
            ) * 100:+.2f}%",
        )

        st.warning(
            "⚠️ Die kombinierte Wahrscheinlichkeit "
            "setzt vereinfacht unabhängige Ereignisse "
            "voraus. Tatsächlich können Spiele und Märkte "
            "korreliert sein. Der Ticket-Builder ist "
            "daher nur eine Modellrechnung."
        )

else:

    st.info(
        "Keine geeigneten Picks für den Ticket Builder."
    )


# ============================================================
# DATA SOURCE STATUS
# ============================================================

st.divider()

with st.expander(
    "🔌 Datenquellen & Systemstatus"
):

    status_data = {
        "Quelle": [
            "API-Football",
            "football-data.org",
            "The Odds API",
            "Poisson Modell",
        ],
        "Status": [
            "Verbunden"
            if FOOTBALL_API_KEY
            else "Nicht konfiguriert",

            (
                f"{len(FOOTBALL_DATA_API_KEYS)} Key(s)"
                if FOOTBALL_DATA_API_KEYS
                else "Nicht konfiguriert"
            ),

            "Verbunden"
            if ODDS_API_KEY
            else "Nicht konfiguriert",

            "Aktiv",
        ],
    }

    st.dataframe(
        pd.DataFrame(status_data),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "⚠️ Hinweis: Diese Anwendung liefert "
    "statistische Modellberechnungen und keine "
    "Gewinn- oder Wettempfehlungen mit Garantie. "
    "Sportwetten sind mit dem Risiko finanzieller "
    "Verluste verbunden. Quoten, Daten und "
    "Modellwahrscheinlichkeiten können sich ändern."
)

st.caption(
    f"Football AI Analyzer V3 · "
    f"{datetime.now(BERLIN_TZ).strftime('%d.%m.%Y %H:%M')} "
    f"Europe/Berlin"
)
