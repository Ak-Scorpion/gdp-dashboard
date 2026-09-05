import streamlit as st
import requests
import pandas as pd
import numpy as np
import math

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

# Maximale Torzahl für Poisson-Verteilung.
MAX_GOALS = 8

# Heimvorteil.
HOME_ADVANTAGE = 1.08

# Mindest- und Maximalwerte für erwartete Tore.
MIN_XG = 0.20
MAX_XG = 4.50

# Confidence-Score Gewichte.
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

        .stApp {
            background: #070a13;
            color: #f1f5f9;
        }

        [data-testid="stHeader"] {
            background: rgba(0,0,0,0);
        }

        .main-title {
            font-size: 2.4rem;
            font-weight: 900;
            color: white;
            margin-bottom: 0;
        }

        .subtitle {
            color: #94a3b8;
            margin-top: 4px;
            margin-bottom: 25px;
        }

        .match-card {
            background: linear-gradient(
                135deg,
                rgba(15,23,42,0.98),
                rgba(6,78,59,0.70)
            );
            border: 1px solid #164e3b;
            border-radius: 18px;
            padding: 20px;
            margin-bottom: 18px;
        }

        .score-high {
            color: #00d47e;
            font-weight: 900;
            font-size: 1.5rem;
        }

        .score-medium {
            color: #fbbf24;
            font-weight: 900;
            font-size: 1.5rem;
        }

        .score-low {
            color: #f87171;
            font-weight: 900;
            font-size: 1.5rem;
        }

        .pill {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            margin-right: 5px;
            font-size: 0.75rem;
            font-weight: 800;
            background: #1e293b;
            color: #cbd5e1;
        }

        .green {
            color: #00d47e;
        }

        .yellow {
            color: #fbbf24;
        }

        .red {
            color: #f87171;
        }

        .muted {
            color: #94a3b8;
        }

        .big-number {
            font-size: 1.8rem;
            font-weight: 900;
            color: white;
        }

        .ticket-box {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 15px;
            padding: 18px;
        }

        .model-box {
            background: #0b1220;
            border: 1px solid #1e293b;
            border-radius: 14px;
            padding: 15px;
            margin-top: 10px;
        }

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

    headers = {
        "x-apisports-key": FOOTBALL_API_KEY
    }

    try:

        response = requests.get(
            f"{FOOTBALL_API_BASE}/{endpoint}",
            headers=headers,
            params=params,
            timeout=20,
        )

        if response.status_code != 200:

            return (
                None,
                f"API-Fehler HTTP "
                f"{response.status_code}: "
                f"{response.text[:300]}",
            )

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

    return football_request(
        "fixtures",
        {
            "date": target_date,
            "timezone": "Europe/Berlin",
        },
    )


@st.cache_data(ttl=600)
def get_predictions(fixture_id):

    data, error = football_request(
        "predictions",
        {
            "fixture": fixture_id
        },
    )

    if error or not data:
        return None, error

    return data[0], None


@st.cache_data(ttl=600)
def get_h2h(team1, team2):

    if not team1 or not team2:
        return [], "Team-ID fehlt."

    data, error = football_request(
        "fixtures/headtohead",
        {
            "h2h": f"{team1}-{team2}",
            "last": 10,
        },
    )

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

        value = (
            value
            .replace("%", "")
            .replace(",", ".")
            .strip()
        )

    try:
        return float(value)

    except Exception:
        return None


def parse_prediction(prediction):

    result = {
        "winner": None,
        "home_percent": None,
        "draw_percent": None,
        "away_percent": None,
        "advice": None,

        "goals_home": None,
        "goals_away": None,

        "form_home": "",
        "form_away": "",

        "home_last5": [],
        "away_last5": [],

        "home_att": None,
        "home_def": None,
        "away_att": None,
        "away_def": None,

        "home_goals_for": None,
        "home_goals_against": None,
        "away_goals_for": None,
        "away_goals_against": None,
    }

    if not prediction:
        return result

    predictions = prediction.get(
        "predictions",
        {},
    )

    teams = prediction.get(
        "teams",
        {},
    )

    winner = predictions.get(
        "winner"
    ) or {}

    result["winner"] = winner.get(
        "name"
    )

    result["advice"] = predictions.get(
        "advice"
    )

    percent = predictions.get(
        "percent",
        {},
    )

    result["home_percent"] = parse_percent_value(
        percent.get("home")
    )

    result["draw_percent"] = parse_percent_value(
        percent.get("draw")
    )

    result["away_percent"] = parse_percent_value(
        percent.get("away")
    )

    goals = predictions.get(
        "goals",
        {},
    )

    result["goals_home"] = safe_float(
        goals.get("home"),
        None,
    )

    result["goals_away"] = safe_float(
        goals.get("away"),
        None,
    )

    home_team = teams.get(
        "home",
        {},
    )

    away_team = teams.get(
        "away",
        {},
    )

    home_league = home_team.get(
        "league",
        {},
    )

    away_league = away_team.get(
        "league",
        {},
    )

    result["form_home"] = (
        home_league.get(
            "form",
            "",
        )
        or ""
    )

    result["form_away"] = (
        away_league.get(
            "form",
            "",
        )
        or ""
    )

    result["home_att"] = safe_float(
        home_league.get("att"),
        None,
    )

    result["home_def"] = safe_float(
        home_league.get("def"),
        None,
    )

    result["away_att"] = safe_float(
        away_league.get("att"),
        None,
    )

    result["away_def"] = safe_float(
        away_league.get("def"),
        None,
    )

    return result


# ============================================================
# FORM-ANALYSE
# ============================================================

def parse_form_string(form_string):

    if not form_string:
        return []

    clean = (
        str(form_string)
        .upper()
        .replace(" ", "")
    )

    return [
        char
        for char in clean
        if char in ["W", "D", "L"]
    ][-5:]


def form_points(form):

    if not form:
        return None

    points = 0

    for result in form:

        if result == "W":
            points += 3

        elif result == "D":
            points += 1

    return points


def form_strength(form):

    points = form_points(form)

    if points is None:
        return 0.5

    return points / 15


def form_difference(home_form, away_form):

    home_strength = form_strength(
        home_form
    )

    away_strength = form_strength(
        away_form
    )

    return home_strength - away_strength


# ============================================================
# POISSON-MODELL
# ============================================================

def poisson_pmf(k, lam):

    lam = max(lam, 0.001)

    return (
        math.exp(-lam)
        * (lam ** k)
        / math.factorial(k)
    )


def poisson_distribution(lam, max_goals=MAX_GOALS):

    probabilities = [
        poisson_pmf(
            k,
            lam,
        )
        for k in range(max_goals + 1)
    ]

    total = sum(probabilities)

    if total <= 0:
        return probabilities

    return [
        p / total
        for p in probabilities
    ]


def build_score_matrix(home_xg, away_xg):

    home_distribution = poisson_distribution(
        home_xg
    )

    away_distribution = poisson_distribution(
        away_xg
    )

    matrix = np.outer(
        home_distribution,
        away_distribution,
    )

    matrix = matrix / matrix.sum()

    return matrix


def poisson_market_probabilities(
    home_xg,
    away_xg,
):

    matrix = build_score_matrix(
        home_xg,
        away_xg,
    )

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    over_15 = 0.0
    over_25 = 0.0
    btts = 0.0

    for home_goals in range(
        matrix.shape[0]
    ):

        for away_goals in range(
            matrix.shape[1]
        ):

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

            total_goals = (
                home_goals
                + away_goals
            )

            if total_goals >= 2:
                over_15 += probability

            if total_goals >= 3:
                over_25 += probability

            if (
                home_goals >= 1
                and away_goals >= 1
            ):
                btts += probability

    double_chance_1x = (
        home_win + draw
    )

    double_chance_x2 = (
        draw + away_win
    )

    double_chance_12 = (
        home_win + away_win
    )

    return {
        "home": home_win,
        "draw": draw,
        "away": away_win,

        "1X": double_chance_1x,
        "X2": double_chance_x2,
        "12": double_chance_12,

        "over_1_5": over_15,
        "over_2_5": over_25,

        "btts": btts,
    }


def most_likely_score(
    home_xg,
    away_xg,
):

    matrix = build_score_matrix(
        home_xg,
        away_xg,
    )

    index = np.unravel_index(
        np.argmax(matrix),
        matrix.shape,
    )

    home_goals = index[0]
    away_goals = index[1]

    probability = matrix[index]

    return (
        home_goals,
        away_goals,
        probability,
    )


# ============================================================
# ERWARTETE TORE
# ============================================================

def derive_xg_from_prediction(prediction):

    api_home = prediction.get(
        "goals_home"
    )

    api_away = prediction.get(
        "goals_away"
    )

    home_probability = prediction.get(
        "home_percent"
    )

    draw_probability = prediction.get(
        "draw_percent"
    )

    away_probability = prediction.get(
        "away_percent"
    )

    # --------------------------------------------------------
    # Beste Quelle: API-Prognose-Score
    # --------------------------------------------------------

    if (
        api_home is not None
        and api_away is not None
        and api_home + api_away > 0
    ):

        home_xg = safe_float(
            api_home
        )

        away_xg = safe_float(
            api_away
        )

        return (
            clamp(
                home_xg * HOME_ADVANTAGE,
                MIN_XG,
                MAX_XG,
            ),
            clamp(
                away_xg,
                MIN_XG,
                MAX_XG,
            ),
            "API-Prognose",
        )

    # --------------------------------------------------------
    # Zweite Quelle:
    # 1X2-Wahrscheinlichkeiten.
    # --------------------------------------------------------

    if (
        home_probability is not None
        and draw_probability is not None
        and away_probability is not None
    ):

        total_probability = (
            home_probability
            + draw_probability
            + away_probability
        )

        if total_probability > 0:

            home_probability /= (
                total_probability
            )

            draw_probability /= (
                total_probability
            )

            away_probability /= (
                total_probability
            )

            # Grobe Inversion:
            # Stärkeunterschied → xG-Verhältnis
            strength = (
                home_probability
                - away_probability
            )

            base_total = 2.45

            home_share = clamp(
                0.50 + strength * 0.35,
                0.25,
                0.75,
            )

            home_xg = (
                base_total
                * home_share
                * HOME_ADVANTAGE
            )

            away_xg = (
                base_total
                * (1 - home_share)
            )

            return (
                clamp(
                    home_xg,
                    MIN_XG,
                    MAX_XG,
                ),
                clamp(
                    away_xg,
                    MIN_XG,
                    MAX_XG,
                ),
                "1X2-Modell",
            )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    return (
        1.35,
        1.10,
        "Basis-Modell",
    )


# ============================================================
# MARKT-ANALYSE
# ============================================================

def market_analysis(
    probabilities,
    market,
):

    if not probabilities:
        return None

    if market == "Doppelte Chance":

        options = {
            "1X": probabilities.get(
                "1X",
                0,
            ),

            "X2": probabilities.get(
                "X2",
                0,
            ),
        }

        tip = max(
            options,
            key=options.get,
        )

        return {
            "tip": tip,
            "probability": probability_to_percent(
                options[tip]
            ),
        }

    if market == "Über 1.5 Tore":

        probability = probabilities.get(
            "over_1_5"
        )

        return {
            "tip": "Over 1.5",
            "probability": probability_to_percent(
                probability
            ),
        }

    if market == "Über 2.5 Tore":

        probability = probabilities.get(
            "over_2_5"
        )

        return {
            "tip": "Over 2.5",
            "probability": probability_to_percent(
                probability
            ),
        }

    if market == "Beide Teams treffen":

        probability = probabilities.get(
            "btts"
        )

        return {
            "tip": "BTTS – Ja",
            "probability": probability_to_percent(
                probability
            ),
        }

    if market == "1X2":

        options = {
            "1": probabilities.get(
                "home",
                0,
            ),

            "X": probabilities.get(
                "draw",
                0,
            ),

            "2": probabilities.get(
                "away",
                0,
            ),
        }

        tip = max(
            options,
            key=options.get,
        )

        return {
            "tip": tip,
            "probability": probability_to_percent(
                options[tip]
            ),
        }

    return None


# ============================================================
# ODDS API
# ============================================================

@st.cache_data(ttl=120)
def get_odds_for_sport(sport_key):

    if not ODDS_API_KEY:
        return [], "ODDS_API_KEY fehlt."

    try:

        response = requests.get(
            f"{ODDS_API_BASE}/sports/{sport_key}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
            timeout=20,
        )

        if response.status_code != 200:

            return (
                [],
                f"Odds API HTTP "
                f"{response.status_code}",
            )

        return response.json(), None

    except requests.RequestException as exc:

        return [], str(exc)


def find_odds_for_match(
    home,
    away,
    odds_events,
):

    best_event = None
    best_score = 0

    for event in odds_events:

        event_home = event.get(
            "home_team",
            "",
        )

        event_away = event.get(
            "away_team",
            "",
        )

        direct_score = (
            similarity(
                home,
                event_home,
            )
            + similarity(
                away,
                event_away,
            )
        ) / 2

        reverse_score = (
            similarity(
                home,
                event_away,
            )
            + similarity(
                away,
                event_home,
            )
        ) / 2

        score = max(
            direct_score,
            reverse_score,
        )

        if score > best_score:

            best_score = score
            best_event = event

    if best_score < 0.55:
        return None

    return best_event


def bookmaker_matches(
    bookmaker,
    selected_bookmaker,
):

    if not selected_bookmaker:
        return False

    title = (
        bookmaker.get(
            "title",
            "",
        )
        .lower()
        .strip()
    )

    key = (
        bookmaker.get(
            "key",
            "",
        )
        .lower()
        .strip()
    )

    aliases = BOOKMAKER_ALIASES.get(
        selected_bookmaker,
        [],
    )

    return any(
        alias in title
        or alias in key
        for alias in aliases
    )


def extract_best_odds(
    event,
    selected_bookmaker=None,
):

    if not event:

        return {
            "h2h": {},
            "totals": {},
            "bookmaker": None,
            "requested_bookmaker_found": False,
        }

    result = {
        "h2h": {},
        "totals": {},
        "bookmaker": None,
        "requested_bookmaker_found": False,
    }

    bookmakers = event.get(
        "bookmakers",
        [],
    )

    # --------------------------------------------------------
    # Gewählten Buchmacher bevorzugen
    # --------------------------------------------------------

    ordered = []

    preferred = [
        bookmaker
        for bookmaker in bookmakers
        if bookmaker_matches(
            bookmaker,
            selected_bookmaker,
        )
    ]

    ordered.extend(preferred)

    for bookmaker in bookmakers:

        if bookmaker not in ordered:
            ordered.append(bookmaker)

    # --------------------------------------------------------
    # Märkte auslesen
    # --------------------------------------------------------

    for bookmaker in ordered:

        markets = bookmaker.get(
            "markets",
            [],
        )

        found_h2h = {}
        found_totals = {}

        for market in markets:

            market_key = market.get(
                "key"
            )

            outcomes = market.get(
                "outcomes",
                [],
            )

            if market_key == "h2h":

                for outcome in outcomes:

                    name = outcome.get(
                        "name"
                    )

                    price = outcome.get(
                        "price"
                    )

                    if name:
                        found_h2h[name] = price

            elif market_key == "totals":

                for outcome in outcomes:

                    name = outcome.get(
                        "name"
                    )

                    price = outcome.get(
                        "price"
                    )

                    point = outcome.get(
                        "point"
                    )

                    if (
                        name
                        and point is not None
                    ):

                        found_totals[
                            f"{name}_{point}"
                        ] = price

        if found_h2h or found_totals:

            result["h2h"] = found_h2h

            result["totals"] = found_totals

            result["bookmaker"] = (
                bookmaker.get(
                    "title"
                )
            )

            result[
                "requested_bookmaker_found"
            ] = bookmaker_matches(
                bookmaker,
                selected_bookmaker,
            )

            break

    return result


def get_market_odds_for_tip(
    odds_data,
    home,
    away,
    tip,
    market,
):

    if not odds_data:
        return None

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    if market == "1X2":

        h2h = odds_data.get(
            "h2h",
            {},
        )

        if tip == "1":
            return h2h.get(home)

        if tip == "2":
            return h2h.get(away)

        if tip == "X":

            for key, value in h2h.items():

                if str(key).lower() in [
                    "draw",
                    "tie",
                    "x",
                ]:

                    return value

    # --------------------------------------------------------
    # Double Chance
    # --------------------------------------------------------

    if market == "Doppelte Chance":

        return None

    # --------------------------------------------------------
    # Over 1.5 / Over 2.5
    # --------------------------------------------------------

    if market in [
        "Über 1.5 Tore",
        "Über 2.5 Tore",
    ]:

        target_point = (
            1.5
            if "1.5" in market
            else 2.5
        )

        totals = odds_data.get(
            "totals",
            {},
        )

        for key, price in totals.items():

            if key.startswith("Over_"):

                try:

                    point = float(
                        key.split("_")[1]
                    )

                    if abs(
                        point - target_point
                    ) < 0.01:

                        return price

                except Exception:
                    pass

    return None


# ============================================================
# VALUE / EV
# ============================================================

def implied_probability(odds):

    odds = safe_float(
        odds,
        0,
    )

    if odds <= 1:
        return None

    return 1 / odds


def calculate_value(
    probability,
    odds,
):

    if (
        probability is None
        or not odds
    ):
        return None

    odds = safe_float(
        odds,
        0,
    )

    if odds <= 1:
        return None

    probability_decimal = (
        probability / 100
    )

    return (
        probability_decimal
        * odds
    ) - 1


def calculate_ev_percent(
    probability,
    odds,
):

    value = calculate_value(
        probability,
        odds,
    )

    if value is None:
        return None

    return value * 100


# ============================================================
# DATENQUALITÄT
# ============================================================

def calculate_data_quality(
    prediction,
    xg_source,
    odds,
):

    score = 0

    if prediction.get(
        "home_percent"
    ) is not None:
        score += 20

    if prediction.get(
        "draw_percent"
    ) is not None:
        score += 20

    if prediction.get(
        "away_percent"
    ) is not None:
        score += 20

    if (
        prediction.get(
            "goals_home"
        )
        is not None
        and prediction.get(
            "goals_away"
        )
        is not None
    ):
        score += 20

    if xg_source != "Basis-Modell":
        score += 10

    if odds:
        score += 10

    return clamp(
        score,
        0,
        100,
    )


# ============================================================
# CONFIDENCE SCORE
# ============================================================

def calculate_confidence_score(
    probability,
    form_score,
    value,
    data_quality,
):

    model_score = clamp(
        probability,
        0,
        100,
    )

    form_component = clamp(
        form_score,
        0,
        100,
    )

    if value is None:

        value_component = 50

    else:

        value_component = clamp(
            50 + value * 500,
            0,
            100,
        )

    score = (
        model_score * WEIGHT_MODEL
        + form_component * WEIGHT_FORM
        + value_component * WEIGHT_VALUE
        + data_quality * WEIGHT_DATA
    )

    return int(
        clamp(
            round(score),
            0,
            100,
        )
    )


def risk_label(probability):

    if probability is None:
        return "Unbekannt"

    if probability >= 78:
        return "Niedrig"

    if probability >= 65:
        return "Mittel"

    return "Hoch"


def score_label(score):

    if score >= 78:
        return "high"

    if score >= 62:
        return "medium"

    return "low"


# ============================================================
# SPIEL-ANALYSE
# ============================================================

def analyze_fixture(
    fixture,
    selected_market,
    bookmaker,
):

    fixture_id = fixture.get(
        "fixture",
        {},
    ).get(
        "id"
    )

    teams = fixture.get(
        "teams",
        {},
    )

    home = teams.get(
        "home",
        {},
    ).get(
        "name",
        "Heim",
    )

    away = teams.get(
        "away",
        {},
    ).get(
        "name",
        "Auswärts",
    )

    prediction_raw, prediction_error = (
        get_predictions(
            fixture_id
        )
    )

    prediction = parse_prediction(
        prediction_raw
    )

    home_xg, away_xg, xg_source = (
        derive_xg_from_prediction(
            prediction
        )
    )

    probabilities = (
        poisson_market_probabilities(
            home_xg,
            away_xg,
        )
    )

    market_result = market_analysis(
        probabilities,
        selected_market,
    )

    home_form = parse_form_string(
        prediction.get(
            "form_home",
            "",
        )
    )

    away_form = parse_form_string(
        prediction.get(
            "form_away",
            "",
        )
    )

    form_difference_value = (
        form_difference(
            home_form,
            away_form,
        )
    )

    form_score = 50

    if selected_market == "1X2":

        if (
            market_result
            and market_result["tip"] == "1"
        ):

            form_score = (
                50
                + form_difference_value
                * 50
            )

        elif (
            market_result
            and market_result["tip"] == "2"
        ):

            form_score = (
                50
                - form_difference_value
                * 50
            )

        else:

            form_score = 50

    elif selected_market == "Doppelte Chance":

        if (
            market_result
            and market_result["tip"] == "1X"
        ):

            form_score = (
                50
                + form_difference_value
                * 25
            )

        elif (
            market_result
            and market_result["tip"] == "X2"
        ):

            form_score = (
                50
                - form_difference_value
                * 25
            )

    else:

        form_score = 50

    form_score = clamp(
        form_score,
        0,
        100,
    )

    result = {

        "fixture_id": fixture_id,

        "home": home,
        "away": away,

        "prediction": prediction,

        "probabilities": probabilities,

        "market": market_result,

        "home_xg": home_xg,
        "away_xg": away_xg,

        "xg_source": xg_source,

        "home_form": home_form,
        "away_form": away_form,

        "form_score": form_score,

        "odds": None,

        "bookmaker": None,

        "requested_bookmaker_found": False,

        "value": None,

        "ev_percent": None,

        "data_quality": None,

        "score": None,

        "risk": "Unbekannt",

        "most_likely_score": None,

        "most_likely_score_probability": None,

        "error": prediction_error,
    }

    likely_home, likely_away, likely_probability = (
        most_likely_score(
            home_xg,
            away_xg,
        )
    )

    result[
        "most_likely_score"
    ] = (
        likely_home,
        likely_away,
    )

    result[
        "most_likely_score_probability"
    ] = probability_to_percent(
        likely_probability
    )

    result["data_quality"] = (
        calculate_data_quality(
            prediction,
            xg_source,
            None,
        )
    )

    if market_result:

        result["score"] = (
            calculate_confidence_score(
                market_result[
                    "probability"
                ],
                form_score,
                None,
                result[
                    "data_quality"
                ],
            )
        )

        result["risk"] = risk_label(
            market_result[
                "probability"
            ]
        )

    return result


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## ⚽ KI Wettanalyse V2"
    )

    st.caption(
        "Poisson-Modell · xG · Form · "
        "Value · Confidence Score"
    )

    st.markdown("---")

    target_date = st.date_input(
        "📅 Spieltag",
        value=now_local().date(),
    )

    market = st.selectbox(
        "🎯 Analyse-Markt",
        [
            "Doppelte Chance",
            "Über 1.5 Tore",
            "Über 2.5 Tore",
            "Beide Teams treffen",
            "1X2",
        ],
    )

    bookmaker = st.selectbox(
        "🏦 Bevorzugter Buchmacher",
        list(
            BOOKMAKER_ALIASES.keys()
        ),
    )

    min_probability = st.slider(
        "📊 Mindestwahrscheinlichkeit",
        min_value=50,
        max_value=90,
        value=60,
        step=1,
    )

    min_score = st.slider(
        "🧠 Mindest-Analyse-Score",
        min_value=0,
        max_value=100,
        value=60,
        step=1,
    )

    only_positive_value = st.checkbox(
        "Nur positives Value",
        value=False,
    )

    only_with_odds = st.checkbox(
        "Nur Spiele mit echter Quote",
        value=False,
    )

    st.markdown("---")

    refresh = st.button(
        "🔄 Daten aktualisieren",
        type="primary",
        use_container_width=True,
    )

    st.markdown("---")

    if FOOTBALL_API_KEY:

        st.success(
            "⚽ Football API verbunden"
        )

    else:

        st.error(
            "FOOTBALL_API_KEY fehlt"
        )

    if ODDS_API_KEY:

        st.success(
            "💰 Odds API verbunden"
        )

    else:

        st.warning(
            "ODDS_API_KEY fehlt – "
            "keine Buchmacherquoten"
        )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    '⚽ KI Fußballanalyse V2'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    'Poisson-Modell · Expected Goals · '
    'Form · Märkte · Quoten · Value'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# API CHECK
# ============================================================

if not FOOTBALL_API_KEY:

    st.warning(
        """
        ### 🔑 Football API-Key fehlt
        """
    )

    st.stop()


# ============================================================
# SPIELE LADEN
# ============================================================

date_string = target_date.strftime(
    "%Y-%m-%d"
)

if (
    refresh
    or st.session_state.last_date
    != date_string
    or not st.session_state.fixtures
):

    with st.spinner(
        f"⚡ Lade Spiele für "
        f"{target_date.strftime('%d.%m.%Y')}..."
    ):

        fixtures, error = (
            get_today_fixtures(
                date_string
            )
        )

        if error:

            st.error(error)

            fixtures = []

        st.session_state.fixtures = (
            fixtures or []
        )

        st.session_state.last_date = (
            date_string
        )

        st.session_state.analysis_cache = {}


fixtures = st.session_state.fixtures


# ============================================================
# TOP KPIs
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "Spiele",
        len(fixtures),
    )


with col2:

    upcoming = [
        x
        for x in fixtures
        if x.get(
            "fixture",
            {},
        )
        .get(
            "status",
            {},
        )
        .get(
            "short"
        )
        in [
            "NS",
            "TBD",
        ]
    ]

    st.metric(
        "Anstehend",
        len(upcoming),
    )


with col3:

    live = [
        x
        for x in fixtures
        if x.get(
            "fixture",
            {},
        )
        .get(
            "status",
            {},
        )
        .get(
            "short"
        )
        in [
            "1H",
            "HT",
            "2H",
            "ET",
            "P",
        ]
    ]

    st.metric(
        "Live",
        len(live),
    )


with col4:

    completed = [
        x
        for x in fixtures
        if x.get(
            "fixture",
            {},
        )
        .get(
            "status",
            {},
        )
        .get(
            "short"
        )
        in [
            "FT",
            "AET",
            "PEN",
        ]
    ]

    st.metric(
        "Beendet",
        len(completed),
    )


st.markdown("---")


# ============================================================
# WETTBEWERBE
# ============================================================

competition_options = sorted(
    list(
        {
            f.get(
                "league",
                {},
            ).get(
                "name",
                "Unbekannt",
            )
            for f in fixtures
        }
    )
)

selected_competitions = st.multiselect(
    "🌍 Wettbewerbe",
    competition_options,
    default=competition_options,
)


filtered_fixtures = []

for fixture in fixtures:

    league_name = fixture.get(
        "league",
        {},
    ).get(
        "name",
        "Unbekannt",
    )

    if (
        league_name
        in selected_competitions
    ):

        filtered_fixtures.append(
            fixture
        )


# ============================================================
# ODDS LADEN
# ============================================================

all_odds_events = []

if ODDS_API_KEY:

    with st.spinner(
        "💰 Suche aktuelle Buchmacherquoten..."
    ):

        for sport_key in ODDS_SPORT_KEYS:

            events, error = (
                get_odds_for_sport(
                    sport_key
                )
            )

            if events:

                all_odds_events.extend(
                    events
                )


# ============================================================
# ANALYSEN
# ============================================================

analyses = []

progress = st.progress(
    0,
    text="Analysiere Spiele...",
)

total = len(
    filtered_fixtures
)


for index, fixture in enumerate(
    filtered_fixtures
):

    fixture_id = fixture.get(
        "fixture",
        {},
    ).get(
        "id"
    )

    cache_key = (
        f"{fixture_id}|"
        f"{market}|"
        f"{bookmaker}"
    )

    if (
        cache_key
        in st.session_state.analysis_cache
    ):

        analysis = (
            st.session_state
            .analysis_cache[
                cache_key
            ]
        )

    else:

        analysis = analyze_fixture(
            fixture,
            market,
            bookmaker,
        )

        if ODDS_API_KEY:

            event = find_odds_for_match(
                analysis["home"],
                analysis["away"],
                all_odds_events,
            )

            odds_info = (
                extract_best_odds(
                    event,
                    bookmaker,
                )
            )

            analysis[
                "bookmaker"
            ] = odds_info.get(
                "bookmaker"
            )

            analysis[
                "requested_bookmaker_found"
            ] = odds_info.get(
                "requested_bookmaker_found",
                False,
            )

            tip = None

            if analysis.get(
                "market"
            ):

                tip = analysis[
                    "market"
                ].get(
                    "tip"
                )

            odds = (
                get_market_odds_for_tip(
                    odds_info,
                    analysis["home"],
                    analysis["away"],
                    tip,
                    market,
                )
            )

            analysis[
                "odds"
            ] = odds

            if (
                analysis.get(
                    "market"
                )
                and odds
            ):

                probability = (
                    analysis[
                        "market"
                    ][
                        "probability"
                    ]
                )

                analysis[
                    "value"
                ] = calculate_value(
                    probability,
                    odds,
                )

                analysis[
                    "ev_percent"
                ] = calculate_ev_percent(
                    probability,
                    odds,
                )

            analysis[
                "data_quality"
            ] = calculate_data_quality(
                analysis[
                    "prediction"
                ],
                analysis[
                    "xg_source"
                ],
                odds,
            )

        if analysis.get(
            "market"
        ):

            probability = (
                analysis[
                    "market"
                ][
                    "probability"
                ]
            )

            analysis[
                "score"
            ] = calculate_confidence_score(
                probability,
                analysis[
                    "form_score"
                ],
                analysis.get(
                    "value"
                ),
                analysis[
                    "data_quality"
                ],
            )

            analysis[
                "risk"
            ] = risk_label(
                probability
            )

        st.session_state.analysis_cache[
            cache_key
        ] = analysis

    probability = None

    if analysis.get(
        "market"
    ):

        probability = analysis[
            "market"
        ].get(
            "probability"
        )

    if probability is None:
        continue

    if probability < min_probability:
        continue

    if (
        analysis.get(
            "score"
        )
        is not None
        and analysis[
            "score"
        ] < min_score
    ):
        continue

    if (
        only_positive_value
        and (
            analysis.get(
                "value"
            ) is None
            or analysis[
                "value"
            ] <= 0
        )
    ):
        continue

    if (
        only_with_odds
        and not analysis.get(
            "odds"
        )
    ):
        continue

    analyses.append(
        analysis
    )

    if total:

        progress.progress(
            (index + 1) / total,
            text=(
                f"Analysiere "
                f"{index + 1}/{total}..."
            ),
        )


progress.empty()


# ============================================================
# SORTIERUNG
# ============================================================

analyses.sort(
    key=lambda x: (
        x.get(
            "score"
        )
        or 0,

        x.get(
            "value"
        )
        if x.get(
            "value"
        ) is not None
        else -999,
    ),
    reverse=True,
)


# ============================================================
# BESTE TIPPS
# ============================================================

st.markdown(
    f"## 🎯 Analyse für "
    f"{target_date.strftime('%d.%m.%Y')}"
)


if not analyses:

    st.info(
        """
        Für deine Filter wurden keine
        ausreichenden Modell-Daten gefunden.
        """
    )

else:

    st.success(
        f"{len(analyses)} Spiele erfüllen deine Kriterien."
    )

    st.markdown(
        "### ⭐ Top-Signale"
    )

    top_cols = st.columns(
        min(
            3,
            len(analyses),
        )
    )

    for idx, analysis in enumerate(
        analyses[:3]
    ):

        with top_cols[idx]:

            probability = analysis[
                "market"
            ][
                "probability"
            ]

            score = analysis.get(
                "score",
                0,
            )

            value = analysis.get(
                "value"
            )

            odds = analysis.get(
                "odds"
            )

            likely_score = analysis.get(
                "most_likely_score"
            )

            if likely_score:

                likely_score_text = (
                    f"{likely_score[0]} : "
                    f"{likely_score[1]}"
                )

            else:

                likely_score_text = "—"

            st.markdown(
                f"""
                <div class="ticket-box">

                    <div class="muted">
                        #{idx + 1}
                    </div>

                    <h3>
                        {analysis['home']}
                        <br>
                        <span class="muted">
                            vs.
                        </span>
                        <br>
                        {analysis['away']}
                    </h3>

                    <div class="green">
                        🎯
                        {analysis['market']['tip']}
                    </div>

                    <br>

                    <div class="big-number">
                        {probability:.0f} %
                    </div>

                    <div class="muted">
                        Poisson-Modell
                    </div>

                    <br>

                    <b>Confidence:</b>
                    {score}/100
                    <br>

                    <b>Risiko:</b>
                    {analysis['risk']}
                    <br>

                    <b>Quote:</b>
                    {format_odds(odds)}
                    <br>

                    <b>EV:</b>
                    {
                        f"{value * 100:+.1f}%"
                        if value is not None
                        else "—"
                    }

                    <br>

                    <b>Score-Modell:</b>
                    {likely_score_text}

                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# EINZELNE SPIELE
# ============================================================

st.markdown("---")

st.markdown(
    "### 📋 Spiele & Analyse"
)


for analysis in analyses:

    probability = analysis[
        "market"
    ][
        "probability"
    ]

    score = analysis.get(
        "score",
        0,
    )

    risk = analysis.get(
        "risk",
        "Unbekannt",
    )

    odds = analysis.get(
        "odds"
    )

    value = analysis.get(
        "value"
    )

    score_class = score_label(
        score
    )

    fixture_id = analysis.get(
        "fixture_id"
    )

    fixture = next(
        (
            f
            for f in filtered_fixtures
            if f.get(
                "fixture",
                {},
            ).get(
                "id"
            )
            == fixture_id
        ),
        {},
    )

    kickoff = fixture.get(
        "fixture",
        {},
    ).get(
        "date"
    )

    try:

        kickoff_dt = (
            datetime.fromisoformat(
                kickoff.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

        kickoff_text = (
            kickoff_dt
            .astimezone(
                LOCAL_TZ
            )
            .strftime(
                "%H:%M"
            )
        )

    except Exception:

        kickoff_text = "—"

    league = fixture.get(
        "league",
        {},
    ).get(
        "name",
        "Unbekannt",
    )

    status = fixture.get(
        "fixture",
        {},
    ).get(
        "status",
        {},
    ).get(
        "short",
        "NS",
    )

    st.markdown(
        f"""
        <div class="match-card">

            <span class="pill">
                🌍 {league}
            </span>

            <span class="pill">
                ⏱️ {kickoff_text}
            </span>

            <span class="pill">
                {status}
            </span>

            <h2>
                {analysis['home']}
                <span class="muted">
                    –
                </span>
                {analysis['away']}
            </h2>

            <div class="{score_class}">
                {score}/100
                Analyse-Score
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = (
        st.columns(5)
    )

    with col1:

        st.metric(
            "🎯 Tipp",
            analysis[
                "market"
            ][
                "tip"
            ],
        )

    with col2:

        st.metric(
            "📊 Wahrscheinlichkeit",
            f"{probability:.0f} %",
        )

    with col3:

        st.metric(
            "🧠 Confidence",
            f"{score}/100",
        )

    with col4:

        st.metric(
            "🚦 Risiko",
            risk,
        )

    with col5:

        st.metric(
            "💰 Quote",
            format_odds(
                odds
            ),
        )

    tabs = st.tabs(
        [
            "🧠 Modell",
            "⚽ Form",
            "💰 Quoten",
            "📈 Value",
            "🎫 Schein",
        ]
    )

    with tabs[0]:

        prediction = analysis.get(
            "prediction",
            {},
        )

        probabilities = analysis.get(
            "probabilities",
            {},
        )

        st.markdown(
            "#### 🧮 Poisson-Modell"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                f"🏠 {analysis['home']}",
                format_percent(
                    probability_to_percent(
                        probabilities.get(
                            "home",
                            0,
                        )
                    )
                ),
            )

        with c2:

            st.metric(
                "🤝 Unentschieden",
                format_percent(
                    probability_to_percent(
                        probabilities.get(
                            "draw",
                            0,
                        )
                    )
                ),
            )

        with c3:

            st.metric(
                f"✈️ {analysis['away']}",
                format_percent(
                    probability_to_percent(
                        probabilities.get(
                            "away",
                            0,
                        )
                    )
                ),
            )

        st.markdown(
            f"""
            <div class="model-box">

                <b>Expected Goals</b><br>

                🏠 {analysis['home']}:
                <b>{analysis['home_xg']:.2f}</b>

                <br>

                ✈️ {analysis['away']}:
                <b>{analysis['away_xg']:.2f}</b>

                <br><br>

                Datenquelle:
                <b>{analysis['xg_source']}</b>

            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "#### ⚽ Tor-Märkte"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Over 1.5",
                format_percent(
                    probability_to_percent(
                        probabilities.get(
                            "over_1_5",
                            0,
                        )
                    )
                ),
            )

        with c2:

            st.metric(
                "Over 2.5",
                format_percent(
                    probability_to_percent(
                        probabilities.get(
                            "over_2_5",
                            0,
                        )
                    )
                ),
            )

        with c3:

            st.metric(
                "BTTS",
                format_percent(
                    probability_to_percent(
                        probabilities.get(
                            "btts",
                            0,
                        )
                    )
                ),
            )

        likely_score = analysis.get(
            "most_likely_score"
        )

        if likely_score:

            st.info(
                f"⚽ Wahrscheinlichster "
                f"Score nach Modell: "
                f"**{likely_score[0]} : "
                f"{likely_score[1]}** "
                f""
                f"({analysis['most_likely_score_probability']:.1f} %)"
            )

        advice = prediction.get(
            "advice"
        )

        if advice:

            st.info(
                f"💡 API-Prognose: "
                f"{advice}"
            )

        st.markdown(
            "#### 📊 Modellqualität"
        )

        st.progress(
            analysis[
                "data_quality"
            ] / 100
        )

        st.caption(
            f"Datenqualität: "
            f"{analysis['data_quality']}/100"
        )

    with tabs[1]:

        c1, c2 = st.columns(2)

        with c1:

            st.markdown(
                f"#### 🏠 {analysis['home']}"
            )

            form_home = analysis.get(
                "home_form",
                [],
            )

            if form_home:

                st.write(
                    " ".join(
                        form_home
                    )
                )

                points = form_points(
                    form_home
                )

                st.metric(
                    "Formpunkte",
                    f"{points}/15",
                )

            else:

                st.caption(
                    "Keine Formdaten verfügbar."
                )

        with c2:

            st.markdown(
                f"#### ✈️ {analysis['away']}"
            )

            form_away = analysis.get(
                "away_form",
                [],
            )

            if form_away:

                st.write(
                    " ".join(
                        form_away
                    )
                )

                points = form_points(
                    form_away
                )

                st.metric(
                    "Formpunkte",
                    f"{points}/15",
                )

            else:

                st.caption(
                    "Keine Formdaten verfügbar."
                )

        st.markdown(
            "#### 🧠 Form-Komponente"
        )

        st.progress(
            analysis[
                "form_score"
            ] / 100
        )

        st.caption(
            f"Form-Score: "
            f"{analysis['form_score']:.0f}/100"
        )

        with st.expander(
            "🤝 Direkte Duelle laden"
        ):

            home_id = fixture.get(
                "teams",
                {},
            ).get(
                "home",
                {},
            ).get(
                "id"
            )

            away_id = fixture.get(
                "teams",
                {},
            ).get(
                "away",
                {},
            ).get(
                "id"
            )

            with st.spinner(
                "Lade H2H..."
            ):

                h2h, h2h_error = (
                    get_h2h(
                        home_id,
                        away_id,
                    )
                )

            if h2h_error:

                st.warning(
                    h2h_error
                )

            elif not h2h:

                st.info(
                    "Keine H2H-Daten vorhanden."
                )

            else:

                rows = []

                for match in h2h[:10]:

                    teams = match.get(
                        "teams",
                        {},
                    )

                    goals = match.get(
                        "goals",
                        {},
                    )

                    rows.append(
                        {
                            "Datum": match.get(
                                "fixture",
                                {},
                            ).get(
                                "date",
                                "",
                            )[:10],

                            "Heim": teams.get(
                                "home",
                                {},
                            ).get(
                                "name",
                                "",
                            ),

                            "Auswärts": teams.get(
                                "away",
                                {},
                            ).get(
                                "name",
                                "",
                            ),

                            "Ergebnis": (
                                f"{goals.get('home', '-')}"
                                f" : "
                                f"{goals.get('away', '-')}"
                            ),
                        }
                    )

                if rows:

                    st.dataframe(
                        pd.DataFrame(
                            rows
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

    with tabs[2]:

        if odds is not None:

            st.success(
                f"🏦 Quote: "
                f"**{odds:.2f}**"
            )

            if analysis.get(
                "bookmaker"
            ):

                st.write(
                    "Buchmacherquelle:",
                    f"**{analysis['bookmaker']}**",
                )

        else:

            st.info(
                "Für diesen Markt wurde keine passende echte Quote gefunden."
            )

    with tabs[3]:

        if odds:

            implied = implied_probability(
                odds
            )

            ev_percent = analysis.get(
                "ev_percent"
            )

            value = analysis.get(
                "value"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "Modell",
                    f"{probability:.1f} %",
                )

            with c2:

                st.metric(
                    "Quote impliziert",
                    (
                        f"{implied * 100:.1f} %"
                        if implied
                        else "—"
                    ),
                )

            with c3:

                st.metric(
                    "Expected Value",
                    (
                        f"{ev_percent:+.1f} %"
                        if ev_percent is not None
                        else "—"
                    ),
                )

        else:

            st.info(
                "Keine echte Quote vorhanden."
            )

    with tabs[4]:

        if st.button(
            "➕ Zum Wettschein hinzufügen",
            key=f"add_{fixture_id}",
            use_container_width=True,
        ):

            ticket_item = {
                "fixture_id": fixture_id,
                "home": analysis["home"],
                "away": analysis["away"],
                "tip": analysis[
                    "market"
                ][
                    "tip"
                ],
                "market": market,
                "odds": odds,
                "probability": probability,
                "score": score,
                "value": value,
            }

            exists = any(
                x[
                    "fixture_id"
                ]
                == fixture_id
                for x in st.session_state.ticket
            )

            if not exists:

                st.session_state.ticket.append(
                    ticket_item
                )

                st.success(
                    "Zum Wettschein hinzugefügt."
                )

            else:

                st.info(
                    "Dieses Spiel ist bereits im Wettschein."
                )


st.markdown("---")

st.markdown(
    "## 🎫 Mein Wettschein"
)

ticket = st.session_state.ticket


if not ticket:

    st.info(
        "Noch keine Spiele ausgewählt."
    )

else:

    ticket_odds = []
    ticket_probabilities = []
    valid_ticket_items = []

    for index, item in enumerate(
        ticket
    ):

        c1, c2, c3, c4 = st.columns(
            [
                4,
                3,
                1.5,
                1,
            ]
        )

        with c1:

            st.write(
                f"**{item['home']} – "
                f"{item['away']}**"
            )

            st.caption(
                f"{item['market']} · "
                f"{item['tip']}"
            )

        with c2:

            st.write(
                f"Modell: "
                f"**{item['probability']:.0f}%**"
            )

        with c3:

            if item["odds"]:

                st.write(
                    f"**{item['odds']:.2f}**"
                )

                ticket_odds.append(
                    float(
                        item["odds"]
                    )
                )

                ticket_probabilities.append(
                    float(
                        item[
                            "probability"
                        ]
                    )
                    / 100
                )

                valid_ticket_items.append(
                    item
                )

            else:

                st.write(
                    "—"
                )

        with c4:

            if st.button(
                "❌",
                key=f"remove_{index}",
            ):

                st.session_state.ticket.pop(
                    index
                )

                st.rerun()

    st.markdown("---")

    if ticket_odds:

        combined_odds = math.prod(
            ticket_odds
        )

        combined_probability = math.prod(
            ticket_probabilities
        )

        st.write(
            f"### Gesamtquote: "
            f"**{combined_odds:.2f}**"
        )

        stake = st.number_input(
            "💶 Einsatz (€)",
            min_value=0.0,
            value=10.0,
            step=5.0,
        )

        possible_return = (
            stake
            * combined_odds
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Einsatz",
                f"{stake:.2f} €",
            )

        with c2:

            st.metric(
                "Möglicher Gewinn",
                f"{possible_return:.2f} €",
            )

        with c3:

            expected_value = (
                combined_probability
                * possible_return
                - stake
            )

            st.metric(
                "Modellierter EV",
                f"{expected_value:+.2f} €",
            )

    else:

        st.warning(
            "Für mindestens ein ausgewähltes Spiel wurde keine echte Quote gefunden."
        )

    if st.button(
        "🗑️ Wettschein leeren",
        use_container_width=True,
    ):

        st.session_state.ticket = []

        st.rerun()


st.markdown("---")

st.caption(
    "⚠️ Fußballwetten sind mit Risiko verbunden. "
    "Modellwahrscheinlichkeiten sind keine Garantien."
)
