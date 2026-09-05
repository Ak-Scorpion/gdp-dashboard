import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
from difflib import SequenceMatcher


# ============================================================
# WETT-KI V2.1
#
# - dynamische Odds-Sportkeys über /sports
# - echter API-Fehlertext statt nur HTTP 400
# - keine Fake-Quoten
# - echte 1X2-Quoten
# - Over/Under 2.5
# - Doppelchance Modell
# - optionale Live-Doppelchance
# - Buchmachervergleich
# - Recency + Home/Away + Elo + Poisson + Dixon-Coles
# - stärkeres Bundesliga/CL-Modell
# - automatische Top-5-Kombi
# - Value + 25%-Kelly
# - nur echte Quoten für Value/Kelly/Kombi
# - globale football-data-Abfragen zur Reduzierung der API-Calls
# ============================================================


st.set_page_config(
    page_title="WETT-KI V2.1",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
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
        "odds_key": "soccer_epl",
        "model": "standard",
    },
    "Bundesliga": {
        "football_data": "BL1",
        "odds_key": "soccer_germany_bundesliga",
        "model": "bundesliga",
    },
    "La Liga": {
        "football_data": "PD",
        "odds_key": "soccer_spain_la_liga",
        "model": "standard",
    },
    "Serie A": {
        "football_data": "SA",
        "odds_key": "soccer_italy_serie_a",
        "model": "standard",
    },
    "Ligue 1": {
        "football_data": "FL1",
        "odds_key": "soccer_france_ligue_one",
        "model": "standard",
    },
    "Champions League": {
        "football_data": "CL",
        "odds_key": "soccer_uefa_champs_league",
        "model": "champions",
    },
    "Europa League": {
        "football_data": "EL",
        "odds_key": "soccer_uefa_europa_league",
        "model": "standard",
    },
    "Conference League": {
        "football_data": "EC",
        "odds_key": "soccer_uefa_europa_conference_league",
        "model": "standard",
    },
}


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "football_token": "",
    "odds_key": "",
    "fixtures": pd.DataFrame(),
    "errors": [],
    "api_status": {},
    "sports_catalog": [],
    "last_update": None,
    "refresh_id": 0,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SECRETS
# ============================================================

def get_secret(name):
    try:
        value = st.secrets.get(name, "")
        return str(value).strip()
    except Exception:
        return ""


secret_football = get_secret("FOOTBALL_DATA_TOKEN")
secret_odds = get_secret("ODDS_API_KEY")

if not st.session_state.football_token and secret_football:
    st.session_state.football_token = secret_football

if not st.session_state.odds_key and secret_odds:
    st.session_state.odds_key = secret_odds


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


def odds_valid(value):
    value = safe_float(value)
    return value is not None and value >= 1.01


def normalize_team_name(name):
    if not name:
        return ""

    s = str(name).lower().strip()

    replacements = [
        ".", ",", "'", '"', "-", "_",
        "(", ")", "[", "]", "/", "\\"
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
        "the": "",
    }

    words = [
        aliases.get(word, word)
        for word in s.split()
    ]

    return " ".join(
        word for word in words if word
    )


def team_similarity(name_a, name_b):
    a = normalize_team_name(name_a)
    b = normalize_team_name(name_b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    seq = SequenceMatcher(
        None,
        a,
        b
    ).ratio()

    tokens_a = set(a.split())
    tokens_b = set(b.split())

    common = tokens_a.intersection(tokens_b)

    if tokens_a and tokens_b:
        jaccard = (
            len(common) /
            len(tokens_a.union(tokens_b))
        )
    else:
        jaccard = 0.0

    return max(
        seq * 0.70 + jaccard * 0.30,
        jaccard,
    )


def teams_match(name_a, name_b):
    score = team_similarity(
        name_a,
        name_b
    )

    return score >= 0.72


# ============================================================
# API REQUEST
# ============================================================

@st.cache_data(
    ttl=120,
    show_spinner=False
)
def api_request(
    url,
    headers_json="{}",
    params_json="{}",
):
    try:
        headers = json.loads(headers_json)
        params = json.loads(params_json)

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=25,
        )

        status = response.status_code

        remaining = (
            response.headers.get(
                "x-requests-remaining"
            )
        )

        used = (
            response.headers.get(
                "x-requests-used"
            )
        )

        last_cost = (
            response.headers.get(
                "x-requests-last"
            )
        )

        meta = {
            "remaining": remaining,
            "used": used,
            "last_cost": last_cost,
        }

        if response.ok:

            try:
                data = response.json()
            except Exception:

                return {
                    "ok": False,
                    "status": status,
                    "data": None,
                    "message": (
                        "API antwortete nicht mit "
                        "gültigem JSON."
                    ),
                    "meta": meta,
                }

            return {
                "ok": True,
                "status": status,
                "data": data,
                "message": "",
                "meta": meta,
            }

        # ----------------------------------------------------
        # ECHTE API-FEHLERMELDUNG AUSLESEN
        # ----------------------------------------------------

        error_code = ""
        error_message = ""

        try:
            body = response.json()

            error_code = str(
                body.get("error_code", "")
            )

            error_message = str(
                body.get("message", "")
            )

        except Exception:
            body = None

        if not error_message:
            error_message = (
                response.text.strip()
            )

        if not error_message:
            error_message = (
                "Keine weitere Fehlermeldung "
                "vom Server."
            )

        if error_code:
            message = (
                f"{error_code}: "
                f"{error_message}"
            )
        else:
            message = error_message

        return {
            "ok": False,
            "status": status,
            "data": None,
            "message": message[:1000],
            "meta": meta,
        }

    except requests.exceptions.Timeout:

        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": "Timeout.",
            "meta": {},
        }

    except requests.exceptions.RequestException as e:

        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": (
                f"Netzwerkfehler: {e}"
            ),
            "meta": {},
        }

    except Exception as e:

        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": (
                f"Unerwarteter API-Fehler: {e}"
            ),
            "meta": {},
        }


def make_headers(headers):
    return json.dumps(
        headers,
        sort_keys=True
    )


def make_params(params):
    return json.dumps(
        params,
        sort_keys=True
    )


# ============================================================
# ODDS API: SPORT-KATALOG
# ============================================================

def get_odds_sports(api_key):
    """
    Holt zuerst alle aktuell verfügbaren/in-season Sportkeys.

    Das ist wichtig:
    Wir vertrauen nicht mehr blind auf einen hart codierten
    Sport-Key.
    """

    if not api_key:
        return [], {
            "ok": False,
            "status": None,
            "message": "Odds API Key fehlt.",
            "meta": {},
        }

    url = (
        f"{ODDS_API_URL}/sports"
    )

    params = {
        "apiKey": api_key
    }

    result = api_request(
        url,
        params_json=make_params(params)
    )

    if not result["ok"]:
        return [], result

    data = result["data"]

    if not isinstance(data, list):
        return [], {
            "ok": False,
            "status": result["status"],
            "message": (
                "Odds API /sports lieferte "
                "keine Liste."
            ),
            "meta": result.get("meta", {}),
        }

    return data, result


def resolve_sport_key(
    league_name,
    sports_catalog
):
    """
    Sucht den aktuellen Sport-Key.

    Erst exakter Key.
    Danach vorsichtiger Titelvergleich.
    """

    configured = LEAGUES[
        league_name
    ]["odds_key"]

    # 1. Exakter Key
    for sport in sports_catalog:

        if sport.get("key") == configured:

            if sport.get("active", True):
                return sport.get("key")

    # 2. Titel/Name
    search_terms = {
        "Premier League": [
            "EPL",
            "Premier League",
        ],
        "Bundesliga": [
            "Bundesliga - Germany",
            "Bundesliga",
        ],
        "La Liga": [
            "La Liga - Spain",
            "La Liga",
        ],
        "Serie A": [
            "Serie A - Italy",
            "Serie A",
        ],
        "Ligue 1": [
            "Ligue 1 - France",
            "Ligue 1",
        ],
        "Champions League": [
            "UEFA Champions League",
            "Champions League",
        ],
        "Europa League": [
            "UEFA Europa League",
            "Europa League",
        ],
        "Conference League": [
            "UEFA Europa Conference League",
            "Conference League",
        ],
    }

    terms = search_terms.get(
        league_name,
        []
    )

    for sport in sports_catalog:

        if not sport.get(
            "active",
            True
        ):
            continue

        title = str(
            sport.get("title", "")
        ).lower()

        description = str(
            sport.get("description", "")
        ).lower()

        for term in terms:

            if term.lower() in title:
                return sport.get("key")

            if term.lower() in description:
                return sport.get("key")

    return None


# ============================================================
# FOOTBALL-DATA
# ============================================================

@st.cache_data(
    ttl=300,
    show_spinner=False
)
def get_football_matches_cached(
    token,
    competition_codes_tuple,
    date_from,
    date_to,
    status=None,
):
    """
    Eine globale Abfrage über mehrere Wettbewerbe.

    football-data.org unterstützt /v4/matches mit
    competitions + dateFrom/dateTo/status.
    """

    if not token:
        return {
            "ok": False,
            "matches": [],
            "message": "Token fehlt.",
        }

    codes = ",".join(
        competition_codes_tuple
    )

    url = (
        f"{FOOTBALL_DATA_URL}/matches"
    )

    params = {
        "competitions": codes,
        "dateFrom": date_from,
        "dateTo": date_to,
    }

    if status:
        params["status"] = status

    headers = {
        "X-Auth-Token": token
    }

    result = api_request(
        url,
        headers_json=make_headers(headers),
        params_json=make_params(params),
    )

    if not result["ok"]:
        return {
            "ok": False,
            "matches": [],
            "message": (
                f"HTTP {result['status']}: "
                f"{result['message']}"
            ),
        }

    data = result["data"] or {}

    return {
        "ok": True,
        "matches": data.get(
            "matches",
            []
        ),
        "message": "",
        "result_set": data.get(
            "resultSet",
            {}
        ),
    }


def get_upcoming_fixtures(
    token,
    league_names,
    days_forward,
):
    start = utc_now().date()
    end = (
        start +
        timedelta(days=days_forward)
    )

    codes = tuple(
        LEAGUES[name][
            "football_data"
        ]
        for name in league_names
    )

    result = (
        get_football_matches_cached(
            token,
            codes,
            start.isoformat(),
            end.isoformat(),
            None,
        )
    )

    if not result["ok"]:
        return [], [result["message"]]

    league_by_code = {
        LEAGUES[name][
            "football_data"
        ]: name
        for name in league_names
    }

    fixtures = []

    for match in result["matches"]:

        status = str(
            match.get("status", "")
        ).upper()

        if status in {
            "FINISHED",
            "CANCELLED",
            "POSTPONED",
            "SUSPENDED",
            "IN_PLAY",
            "PAUSED",
            "LIVE",
        }:
            continue

        match_time = parse_utc(
            match.get("utcDate")
        )

        if not match_time:
            continue

        if match_time <= utc_now():
            continue

        competition = (
            match.get("competition", {})
        )

        code = competition.get(
            "code"
        )

        league_name = league_by_code.get(
            code
        )

        if not league_name:
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

        if not home_name or not away_name:
            continue

        fixtures.append({
            "match_id": match.get("id"),
            "league": league_name,
            "competition_code": code,
            "matchday": match.get(
                "matchday"
            ),
            "utcDate": match_time,
            "home": home_name,
            "away": away_name,
            "status": status,
        })

    fixtures.sort(
        key=lambda x: x["utcDate"]
    )

    return fixtures, []


# ============================================================
# HISTORISCHE DATEN
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False
)
def get_historical_cached(
    token,
    competition_codes_tuple,
    days_back=180,
):
    end_date = utc_now().date()

    start_date = (
        end_date -
        timedelta(days=days_back)
    )

    result = (
        get_football_matches_cached(
            token,
            competition_codes_tuple,
            start_date.isoformat(),
            end_date.isoformat(),
            "FINISHED",
        )
    )

    if not result["ok"]:
        return []

    return result["matches"]


# ============================================================
# ELO + RECENCY MODELL
# ============================================================

def empty_team_profile():
    return {
        "games": 0.0,
        "gf": 0.0,
        "ga": 0.0,

        "home_games": 0.0,
        "home_gf": 0.0,
        "home_ga": 0.0,

        "away_games": 0.0,
        "away_gf": 0.0,
        "away_ga": 0.0,

        "points": 0.0,
        "points_weight": 0.0,

        "recent_points": 0.0,
        "recent_weight": 0.0,
    }


def recency_weight(
    match_date,
    half_life_days=60,
):
    dt = parse_utc(match_date)

    if dt is None:
        return 0.20

    age = max(
        0,
        (
            utc_now() - dt
        ).days
    )

    return math.exp(
        -math.log(2)
        * age
        / half_life_days
    )


def build_model_context(
    historical_matches
):
    teams = defaultdict(
        empty_team_profile
    )

    league_stats = defaultdict(
        lambda: {
            "home_goals": 0.0,
            "away_goals": 0.0,
            "games": 0.0,
        }
    )

    elo = defaultdict(
        lambda: 1500.0
    )

    matches = []

    for match in historical_matches:

        if str(
            match.get("status", "")
        ).upper() != "FINISHED":
            continue

        home_obj = match.get(
            "homeTeam",
            {}
        )

        away_obj = match.get(
            "awayTeam",
            {}
        )

        home = (
            home_obj.get("name")
            or home_obj.get("shortName")
        )

        away = (
            away_obj.get("name")
            or away_obj.get("shortName")
        )

        score = (
            match.get("score", {})
            .get("fullTime", {})
        )

        hg = safe_float(
            score.get("home")
        )

        ag = safe_float(
            score.get("away")
        )

        if (
            not home
            or not away
            or hg is None
            or ag is None
        ):
            continue

        matches.append({
            "date": match.get(
                "utcDate"
            ),
            "home": home,
            "away": away,
            "hg": hg,
            "ag": ag,
            "competition": (
                match.get(
                    "competition",
                    {}
                ).get("code")
            ),
        })

    matches.sort(
        key=lambda x: (
            parse_utc(x["date"])
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        )
    )

    for match in matches:

        home = normalize_team_name(
            match["home"]
        )

        away = normalize_team_name(
            match["away"]
        )

        hg = match["hg"]
        ag = match["ag"]

        weight = recency_weight(
            match["date"],
            half_life_days=60,
        )

        league_code = (
            match["competition"]
        )

        # ----------------------------------------------
        # Liga-Torwerte
        # ----------------------------------------------

        ls = league_stats[
            league_code
        ]

        ls["home_goals"] += (
            hg * weight
        )

        ls["away_goals"] += (
            ag * weight
        )

        ls["games"] += weight

        # ----------------------------------------------
        # Heimteam
        # ----------------------------------------------

        hp = teams[home]

        hp["games"] += weight
        hp["gf"] += hg * weight
        hp["ga"] += ag * weight

        hp["home_games"] += weight
        hp["home_gf"] += hg * weight
        hp["home_ga"] += ag * weight

        # ----------------------------------------------
        # Auswärtsteam
        # ----------------------------------------------

        ap = teams[away]

        ap["games"] += weight
        ap["gf"] += ag * weight
        ap["ga"] += hg * weight

        ap["away_games"] += weight
        ap["away_gf"] += ag * weight
        ap["away_ga"] += hg * weight

        # ----------------------------------------------
        # Form
        # ----------------------------------------------

        home_points = (
            3 if hg > ag
            else 1 if hg == ag
            else 0
        )

        away_points = (
            3 if ag > hg
            else 1 if hg == ag
            else 0
        )

        hp["points"] += (
            home_points * weight
        )

        ap["points"] += (
            away_points * weight
        )

        hp["points_weight"] += weight
        ap["points_weight"] += weight

        recent_weight = recency_weight(
            match["date"],
            half_life_days=30,
        )

        hp["recent_points"] += (
            home_points * recent_weight
        )

        ap["recent_points"] += (
            away_points * recent_weight
        )

        hp["recent_weight"] += recent_weight
        ap["recent_weight"] += recent_weight

        # ----------------------------------------------
        # ELO
        # ----------------------------------------------

        if league_code == "CL":
            k_factor = 22
            home_adv = 45
        elif league_code == "BL1":
            k_factor = 25
            home_adv = 60
        else:
            k_factor = 24
            home_adv = 55

        home_elo = elo[home]
        away_elo = elo[away]

        expected_home = (
            1 /
            (
                1 +
                10 ** (
                    -(
                        home_elo
                        + home_adv
                        - away_elo
                    ) / 400
                )
            )
        )

        actual_home = (
            1.0 if hg > ag
            else 0.5 if hg == ag
            else 0.0
        )

        margin_multiplier = (
            1.0 +
            math.log(
                abs(hg - ag) + 1
            ) * 0.35
        )

        change = (
            k_factor
            * margin_multiplier
            * (
                actual_home
                - expected_home
            )
        )

        elo[home] += change
        elo[away] -= change

    return {
        "teams": dict(teams),
        "league_stats": dict(
            league_stats
        ),
        "elo": dict(elo),
    }


# ============================================================
# POISSON / DIXON-COLES
# ============================================================

def poisson_pmf(
    lmbda,
    goals
):
    try:
        return (
            math.exp(-lmbda)
            * lmbda ** goals
            / math.factorial(goals)
        )
    except Exception:
        return 0.0


def score_matrix(
    home_lambda,
    away_lambda,
    rho=-0.08,
    max_goals=9,
):
    matrix = np.zeros(
        (
            max_goals + 1,
            max_goals + 1
        )
    )

    for hg in range(
        max_goals + 1
    ):

        for ag in range(
            max_goals + 1
        ):

            p = (
                poisson_pmf(
                    home_lambda,
                    hg
                )
                *
                poisson_pmf(
                    away_lambda,
                    ag
                )
            )

            # Dixon-Coles Low-Score-Korrektur
            if hg == 0 and ag == 0:
                tau = (
                    1 -
                    home_lambda
                    * away_lambda
                    * rho
                )

            elif hg == 0 and ag == 1:
                tau = (
                    1 +
                    home_lambda
                    * rho
                )

            elif hg == 1 and ag == 0:
                tau = (
                    1 +
                    away_lambda
                    * rho
                )

            elif hg == 1 and ag == 1:
                tau = (
                    1 - rho
                )

            else:
                tau = 1.0

            matrix[hg, ag] = (
                max(0.0, p * tau)
            )

    total = matrix.sum()

    if total > 0:
        matrix /= total

    return matrix


def probabilities_from_matrix(
    matrix
):
    p1 = 0.0
    px = 0.0
    p2 = 0.0

    over25 = 0.0
    btts = 0.0

    for hg in range(
        matrix.shape[0]
    ):

        for ag in range(
            matrix.shape[1]
        ):

            p = matrix[hg, ag]

            if hg > ag:
                p1 += p
            elif hg == ag:
                px += p
            else:
                p2 += p

            if hg + ag >= 3:
                over25 += p

            if hg >= 1 and ag >= 1:
                btts += p

    return {
        "1": p1,
        "X": px,
        "2": p2,
        "over25": over25,
        "under25": 1 - over25,
        "btts": btts,
        "no_btts": 1 - btts,

        "1X": p1 + px,
        "X2": px + p2,
        "12": p1 + p2,
    }


# ============================================================
# MODELL
# ============================================================

def safe_strength(
    numerator,
    denominator,
    minimum=0.5,
):
    if denominator <= 0:
        return 1.0

    value = (
        numerator /
        denominator
    )

    return max(
        minimum,
        value
    )


def calculate_model(
    fixture,
    context,
):
    home_raw = fixture["home"]
    away_raw = fixture["away"]

    home_key = normalize_team_name(
        home_raw
    )

    away_key = normalize_team_name(
        away_raw
    )

    teams = context["teams"]
    league_stats = context[
        "league_stats"
    ]
    elo = context["elo"]

    hp = teams.get(
        home_key,
        empty_team_profile()
    )

    ap = teams.get(
        away_key,
        empty_team_profile()
    )

    league_code = fixture[
        "competition_code"
    ]

    ls = league_stats.get(
        league_code,
        {}
    )

    games = ls.get(
        "games",
        0
    )

    if games > 0:

        league_home_avg = (
            ls["home_goals"]
            / games
        )

        league_away_avg = (
            ls["away_goals"]
            / games
        )

    else:

        league_home_avg = 1.50
        league_away_avg = 1.20

    # ----------------------------------------------
    # Team-Angriff / Verteidigung
    # ----------------------------------------------

    if hp["home_games"] >= 2:

        home_attack_home = (
            hp["home_gf"]
            / hp["home_games"]
        ) / max(
            league_home_avg,
            0.5
        )

        home_def_home = (
            hp["home_ga"]
            / hp["home_games"]
        ) / max(
            league_away_avg,
            0.5
        )

    else:

        home_attack_home = 1.0
        home_def_home = 1.0

    if ap["away_games"] >= 2:

        away_attack_away = (
            ap["away_gf"]
            / ap["away_games"]
        ) / max(
            league_away_avg,
            0.5
        )

        away_def_away = (
            ap["away_ga"]
            / ap["away_games"]
        ) / max(
            league_home_avg,
            0.5
        )

    else:

        away_attack_away = 1.0
        away_def_away = 1.0

    # ----------------------------------------------
    # Gesamtstärke als Fallback
    # ----------------------------------------------

    if hp["games"] >= 3:

        home_attack_overall = (
            hp["gf"]
            / hp["games"]
        ) / max(
            (
                league_home_avg
                + league_away_avg
            ) / 2,
            0.5
        )

        home_def_overall = (
            hp["ga"]
            / hp["games"]
        ) / max(
            (
                league_home_avg
                + league_away_avg
            ) / 2,
            0.5
        )

    else:

        home_attack_overall = 1.0
        home_def_overall = 1.0

    if ap["games"] >= 3:

        away_attack_overall = (
            ap["gf"]
            / ap["games"]
        ) / max(
            (
                league_home_avg
                + league_away_avg
            ) / 2,
            0.5
        )

        away_def_overall = (
            ap["ga"]
            / ap["games"]
        ) / max(
            (
                league_home_avg
                + league_away_avg
            ) / 2,
            0.5
        )

    else:

        away_attack_overall = 1.0
        away_def_overall = 1.0

    # Home/Away mit Gesamtwert verschmelzen
    home_sample = min(
        1.0,
        hp["home_games"] / 6
    )

    away_sample = min(
        1.0,
        ap["away_games"] / 6
    )

    home_attack = (
        home_sample
        * home_attack_home
        +
        (1 - home_sample)
        * home_attack_overall
    )

    home_def = (
        home_sample
        * home_def_home
        +
        (1 - home_sample)
        * home_def_overall
    )

    away_attack = (
        away_sample
        * away_attack_away
        +
        (1 - away_sample)
        * away_attack_overall
    )

    away_def = (
        away_sample
        * away_def_away
        +
        (1 - away_sample)
        * away_def_overall
    )

    # ----------------------------------------------
    # Basis-Lambda
    # ----------------------------------------------

    home_lambda = (
        league_home_avg
        * home_attack
        * away_def
    )

    away_lambda = (
        league_away_avg
        * away_attack
        * home_def
    )

    # ----------------------------------------------
    # Form
    # ----------------------------------------------

    home_form = (
        hp["recent_points"]
        / max(
            hp["recent_weight"],
            0.01
        )
    )

    away_form = (
        ap["recent_points"]
        / max(
            ap["recent_weight"],
            0.01
        )
    )

    form_diff = (
        home_form
        - away_form
    )

    # Form bewusst nur als kleine Korrektur
    home_lambda *= math.exp(
        np.clip(
            form_diff * 0.035,
            -0.10,
            0.10
        )
    )

    away_lambda *= math.exp(
        np.clip(
            -form_diff * 0.035,
            -0.10,
            0.10
        )
    )

    # ----------------------------------------------
    # ELO
    # ----------------------------------------------

    home_elo = elo.get(
        home_key,
        1500.0
    )

    away_elo = elo.get(
        away_key,
        1500.0
    )

    if league_code == "CL":

        elo_home_adv = 45
        elo_strength = 0.45
        rho = -0.06

    elif league_code == "BL1":

        elo_home_adv = 60
        elo_strength = 0.30
        rho = -0.09

    else:

        elo_home_adv = 55
        elo_strength = 0.25
        rho = -0.08

    elo_diff = (
        home_elo
        + elo_home_adv
        - away_elo
    )

    elo_home_probability = (
        1 /
        (
            1 +
            10 ** (
                -elo_diff / 400
            )
        )
    )

    elo_shift = (
        elo_home_probability
        - 0.5
    )

    home_lambda *= (
        1 +
        elo_shift
        * elo_strength
    )

    away_lambda *= (
        1 -
        elo_shift
        * elo_strength
    )

    # ----------------------------------------------
    # Liga-spezifische Stabilisierung
    # ----------------------------------------------

    if league_code == "BL1":

        home_lambda *= 1.02
        away_lambda *= 1.00

    elif league_code == "CL":

        # CL stärker über Stärke/ELO,
        # weniger blind über wenige CL-Spiele.
        home_lambda *= 0.99
        away_lambda *= 0.99

    # Grenzen
    home_lambda = float(
        np.clip(
            home_lambda,
            0.20,
            4.50
        )
    )

    away_lambda = float(
        np.clip(
            away_lambda,
            0.20,
            4.50
        )
    )

    matrix = score_matrix(
        home_lambda,
        away_lambda,
        rho=rho,
        max_goals=9,
    )

    probs = probabilities_from_matrix(
        matrix
    )

    return {
        **probs,
        "home_lambda": home_lambda,
        "away_lambda": away_lambda,
        "home_elo": home_elo,
        "away_elo": away_elo,
        "elo_probability": elo_home_probability,
        "rho": rho,
    }


# ============================================================
# ODDS
# ============================================================

def get_odds_for_sport(
    api_key,
    sport_key,
):
    """
    Erst h2h + totals.

    Falls totals einen INVALID_MARKET erzeugt,
    automatisch auf h2h zurückfallen.
    """

    if not api_key:
        return [], {
            "ok": False,
            "status": None,
            "message": "Odds API Key fehlt.",
            "market_mode": None,
            "meta": {},
        }

    url = (
        f"{ODDS_API_URL}/sports/"
        f"{sport_key}/odds"
    )

    base_params = {
        "apiKey": api_key,
        "regions": "eu",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    # ----------------------------------------------
    # Versuch 1: h2h + totals
    # ----------------------------------------------

    params = {
        **base_params,
        "markets": "h2h,totals",
    }

    result = api_request(
        url,
        params_json=make_params(params)
    )

    if result["ok"]:

        data = result["data"]

        if isinstance(data, list):

            return data, {
                "ok": True,
                "status": 200,
                "message": "",
                "market_mode": "h2h,totals",
                "meta": result.get(
                    "meta",
                    {}
                ),
            }

    # ----------------------------------------------
    # Nur bei Marktproblem auf h2h zurückfallen
    # ----------------------------------------------

    message = str(
        result.get(
            "message",
            ""
        )
    )

    status = result.get(
        "status"
    )

    if (
        status == 400
        and (
            "INVALID_MARKET" in message
            or "market" in message.lower()
        )
    ):

        params = {
            **base_params,
            "markets": "h2h",
        }

        fallback = api_request(
            url,
            params_json=make_params(params)
        )

        if fallback["ok"]:

            return fallback["data"], {
                "ok": True,
                "status": 200,
                "message": (
                    "1X2 geladen. "
                    "Over/Under war für diesen "
                    "Sport/API-Aufruf nicht verfügbar."
                ),
                "market_mode": "h2h",
                "meta": fallback.get(
                    "meta",
                    {}
                ),
            }

        return [], {
            "ok": False,
            "status": fallback.get(
                "status"
            ),
            "message": fallback.get(
                "message",
                "Unbekannter Fehler."
            ),
            "market_mode": None,
            "meta": fallback.get(
                "meta",
                {}
            ),
        }

    return [], {
        "ok": False,
        "status": status,
        "message": message,
        "market_mode": None,
        "meta": result.get(
            "meta",
            {}
        ),
    }


# ============================================================
# EVENT MATCHING
# ============================================================

def find_odds_event(
    fixture,
    events,
):
    fixture_home = fixture["home"]
    fixture_away = fixture["away"]

    fixture_time = fixture[
        "utcDate"
    ]

    candidates = []

    for event in events:

        event_home = event.get(
            "home_team"
        )

        event_away = event.get(
            "away_team"
        )

        if not event_home or not event_away:
            continue

        home_score = team_similarity(
            fixture_home,
            event_home
        )

        away_score = team_similarity(
            fixture_away,
            event_away
        )

        # Beide Seiten müssen passen
        if (
            home_score < 0.72
            or away_score < 0.72
        ):
            continue

        event_time = parse_utc(
            event.get(
                "commence_time"
            )
        )

        time_score = 0.0

        if event_time and fixture_time:

            diff_hours = abs(
                (
                    event_time
                    - fixture_time
                ).total_seconds()
            ) / 3600

            if diff_hours > 12:
                continue

            time_score = max(
                0.0,
                1 -
                diff_hours / 12
            )

        score = (
            home_score * 0.40
            +
            away_score * 0.40
            +
            time_score * 0.20
        )

        candidates.append(
            (score, event)
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return candidates[0][1]


# ============================================================
# ODDS PARSING
# ============================================================

def parse_event_odds(
    event,
    fixture,
):
    result = {
        "odd_1": None,
        "odd_x": None,
        "odd_2": None,

        "bookmaker_1": None,
        "bookmaker_x": None,
        "bookmaker_2": None,

        "over25": None,
        "under25": None,

        "bookmaker_over25": None,
        "bookmaker_under25": None,

        "dc_1x": None,
        "dc_x2": None,
        "dc_12": None,

        "bookmaker_dc_1x": None,
        "bookmaker_dc_x2": None,
        "bookmaker_dc_12": None,

        "odds_event_id": event.get(
            "id"
        ),
    }

    home = fixture["home"]
    away = fixture["away"]

    bookmaker_rows = []

    for bookmaker in event.get(
        "bookmakers",
        []
    ):

        bookmaker_name = (
            bookmaker.get("title")
            or bookmaker.get("key")
            or "Buchmacher"
        )

        for market in bookmaker.get(
            "markets",
            []
        ):

            market_key = market.get(
                "key"
            )

            for outcome in market.get(
                "outcomes",
                []
            ):

                name = str(
                    outcome.get(
                        "name",
                        ""
                    )
                )

                price = safe_float(
                    outcome.get(
                        "price"
                    )
                )

                point = safe_float(
                    outcome.get(
                        "point"
                    )
                )

                if not odds_valid(price):
                    continue

                # --------------------------------------
                # H2H
                # --------------------------------------

                if market_key == "h2h":

                    if teams_match(
                        name,
                        home
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

                    elif teams_match(
                        name,
                        away
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

                    elif name.strip().lower() in {
                        "draw",
                        "tie",
                        "x",
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

                    bookmaker_rows.append({
                        "Buchmacher": bookmaker_name,
                        "Markt": "1X2",
                        "Auswahl": name,
                        "Quote": price,
                        "Linie": "",
                    })

                # --------------------------------------
                # TOTALS
                # --------------------------------------

                elif market_key == "totals":

                    if (
                        point is not None
                        and abs(
                            point - 2.5
                        ) < 0.01
                    ):

                        lower = (
                            name.lower()
                        )

                        if "over" in lower:

                            if (
                                result[
                                    "over25"
                                ] is None
                                or price
                                > result[
                                    "over25"
                                ]
                            ):

                                result[
                                    "over25"
                                ] = price

                                result[
                                    "bookmaker_over25"
                                ] = bookmaker_name

                        elif "under" in lower:

                            if (
                                result[
                                    "under25"
                                ] is None
                                or price
                                > result[
                                    "under25"
                                ]
                            ):

                                result[
                                    "under25"
                                ] = price

                                result[
                                    "bookmaker_under25"
                                ] = bookmaker_name

                        bookmaker_rows.append({
                            "Buchmacher": bookmaker_name,
                            "Markt": "Over/Under 2.5",
                            "Auswahl": name,
                            "Quote": price,
                            "Linie": point,
                        })

                # --------------------------------------
                # DOUBLE CHANCE
                # --------------------------------------

                elif market_key == "double_chance":

                    lower = (
                        name.lower()
                    )

                    # z.B. "Chelsea or Draw"
                    if (
                        (
                            teams_match(
                                home,
                                name
                            )
                            and
                            "draw" in lower
                        )
                        or
                        (
                            home.lower()
                            in lower
                            and "draw" in lower
                        )
                    ):

                        if (
                            result[
                                "dc_1x"
                            ] is None
                            or price
                            > result[
                                "dc_1x"
                            ]
                        ):

                            result[
                                "dc_1x"
                            ] = price

                            result[
                                "bookmaker_dc_1x"
                            ] = bookmaker_name

                    elif (
                        (
                            teams_match(
                                away,
                                name
                            )
                            and
                            "draw" in lower
                        )
                        or
                        (
                            away.lower()
                            in lower
                            and "draw" in lower
                        )
                    ):

                        if (
                            result[
                                "dc_x2"
                            ] is None
                            or price
                            > result[
                                "dc_x2"
                            ]
                        ):

                            result[
                                "dc_x2"
                            ] = price

                            result[
                                "bookmaker_dc_x2"
                            ] = bookmaker_name

                    elif (
                        "draw" not in lower
                        and
                        teams_match(
                            home,
                            name
                        )
                        and
                        teams_match(
                            away,
                            name
                        )
                    ):

                        if (
                            result[
                                "dc_12"
                            ] is None
                            or price
                            > result[
                                "dc_12"
                            ]
                        ):

                            result[
                                "dc_12"
                            ] = price

                            result[
                                "bookmaker_dc_12"
                            ] = bookmaker_name

                    bookmaker_rows.append({
                        "Buchmacher": bookmaker_name,
                        "Markt": "Doppelchance",
                        "Auswahl": name,
                        "Quote": price,
                        "Linie": "",
                    })

    result[
        "bookmaker_rows"
    ] = bookmaker_rows

    return result


# ============================================================
# MARKET PROBABILITIES
# ============================================================

def devig_3way(
    odds_1,
    odds_x,
    odds_2,
):
    odds = [
        odds_1,
        odds_x,
        odds_2,
    ]

    if not all(
        odds_valid(x)
        for x in odds
    ):
        return None

    implied = np.array([
        1 / odds_1,
        1 / odds_x,
        1 / odds_2,
    ])

    total = implied.sum()

    if total <= 0:
        return None

    probs = implied / total

    return {
        "1": float(probs[0]),
        "X": float(probs[1]),
        "2": float(probs[2]),
    }


def devig_2way(
    odd_a,
    odd_b,
):
    if not (
        odds_valid(odd_a)
        and odds_valid(odd_b)
    ):
        return None

    a = 1 / odd_a
    b = 1 / odd_b

    total = a + b

    if total <= 0:
        return None

    return {
        "a": a / total,
        "b": b / total,
    }


# ============================================================
# KELLY
# ============================================================

def kelly_fraction(
    probability,
    odds,
    fraction=0.25,
):
    if (
        probability is None
        or not odds_valid(odds)
    ):
        return 0.0

    b = odds - 1

    if b <= 0:
        return 0.0

    q = 1 - probability

    full = (
        b * probability - q
    ) / b

    return max(
        0.0,
        full
    ) * fraction


# ============================================================
# SPIEL ANALYSE
# ============================================================

def analyze_fixture(
    fixture,
    model,
    odds,
):
    p1 = model["1"]
    px = model["X"]
    p2 = model["2"]

    # ----------------------------------------------
    # 1X2 Markt
    # ----------------------------------------------

    market = devig_3way(
        odds.get("odd_1"),
        odds.get("odd_x"),
        odds.get("odd_2"),
    )

    if market:

        # Modell dominiert den Markt.
        # Der Markt stabilisiert nur.
        final_1 = (
            0.75 * p1
            + 0.25 * market["1"]
        )

        final_x = (
            0.75 * px
            + 0.25 * market["X"]
        )

        final_2 = (
            0.75 * p2
            + 0.25 * market["2"]
        )

    else:

        final_1 = p1
        final_x = px
        final_2 = p2

    final_probs = {
        "1": final_1,
        "X": final_x,
        "2": final_2,
    }

    prediction = max(
        final_probs,
        key=final_probs.get
    )

    confidence = final_probs[
        prediction
    ]

    # ----------------------------------------------
    # Selected Odds
    # ----------------------------------------------

    if prediction == "1":
        selected_odd = odds.get(
            "odd_1"
        )
        bookmaker = odds.get(
            "bookmaker_1"
        )

    elif prediction == "X":
        selected_odd = odds.get(
            "odd_x"
        )
        bookmaker = odds.get(
            "bookmaker_x"
        )

    else:
        selected_odd = odds.get(
            "odd_2"
        )
        bookmaker = odds.get(
            "bookmaker_2"
        )

    # ----------------------------------------------
    # Value
    #
    # WICHTIG:
    # Value wird nur gegen echte Quote berechnet.
    # ----------------------------------------------

    if odds_valid(selected_odd):

        value = (
            confidence
            * selected_odd
            - 1
        )

        kelly = kelly_fraction(
            confidence,
            selected_odd,
            0.25,
        )

        has_real_odds = True

    else:

        value = None
        kelly = 0.0
        has_real_odds = False

    # ----------------------------------------------
    # Risiko
    # ----------------------------------------------

    if not has_real_odds:

        risk = "NO ODDS"

    elif (
        confidence >= 0.64
        and value >= 0.05
    ):

        risk = "LOW"

    elif (
        confidence >= 0.56
        and value >= 0.03
    ):

        risk = "MID"

    else:

        risk = "HIGH"

    # ----------------------------------------------
    # Doppelchance Modell
    # ----------------------------------------------

    dc = {
        "1X": model["1X"],
        "X2": model["X2"],
        "12": model["12"],
    }

    dc_fair = {
        key: (
            1 / prob
            if prob > 0
            else None
        )
        for key, prob in dc.items()
    }

    # ----------------------------------------------
    # O/U
    # ----------------------------------------------

    over25_odd = odds.get(
        "over25"
    )

    under25_odd = odds.get(
        "under25"
    )

    over_value = None
    under_value = None

    if odds_valid(over25_odd):

        over_value = (
            model["over25"]
            * over25_odd
            - 1
        )

    if odds_valid(under25_odd):

        under_value = (
            model["under25"]
            * under25_odd
            - 1
        )

    return {
        **model,

        "p1": p1,
        "px": px,
        "p2": p2,

        "final_1": final_1,
        "final_x": final_x,
        "final_2": final_2,

        "prediction": prediction,
        "confidence": confidence,

        "selected_odd": selected_odd,
        "selected_bookmaker": bookmaker,

        "value": value,
        "kelly": kelly,
        "risk": risk,

        "has_real_odds": has_real_odds,

        "dc_1x_model": dc["1X"],
        "dc_x2_model": dc["X2"],
        "dc_12_model": dc["12"],

        "dc_1x_fair": dc_fair["1X"],
        "dc_x2_fair": dc_fair["X2"],
        "dc_12_fair": dc_fair["12"],

        "over25_value": over_value,
        "under25_value": under_value,

        "over25_odd": over25_odd,
        "under25_odd": under25_odd,

        "odds_bookmaker_over25": odds.get(
            "bookmaker_over25"
        ),

        "odds_bookmaker_under25": odds.get(
            "bookmaker_under25"
        ),
    }


# ============================================================
# LIVE DOPPELCHANCE – EVENT ENDPOINT
# ============================================================

def get_event_double_chance(
    api_key,
    sport_key,
    event_id,
):
    """
    Zusätzlicher API-Aufruf.

    Nur benutzen, wenn der User Live-Doppelchance
    ausdrücklich aktiviert.
    """

    if not api_key or not sport_key or not event_id:
        return {}

    url = (
        f"{ODDS_API_URL}/sports/"
        f"{sport_key}/events/"
        f"{event_id}/odds"
    )

    params = {
        "apiKey": api_key,
        "regions": "eu",
        "markets": "double_chance",
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    result = api_request(
        url,
        params_json=make_params(params)
    )

    if not result["ok"]:
        return {}

    data = result.get(
        "data",
        {}
    )

    return data


def parse_double_chance_event(
    event,
    fixture,
):
    if not event:
        return {}

    output = {
        "dc_1x": None,
        "dc_x2": None,
        "dc_12": None,

        "bookmaker_dc_1x": None,
        "bookmaker_dc_x2": None,
        "bookmaker_dc_12": None,
    }

    home = fixture["home"]
    away = fixture["away"]

    for bookmaker in event.get(
        "bookmakers",
        []
    ):

        bookmaker_name = (
            bookmaker.get("title")
            or bookmaker.get("key")
            or "Buchmacher"
        )

        for market in bookmaker.get(
            "markets",
            []
        ):

            if market.get(
                "key"
            ) != "double_chance":
                continue

            for outcome in market.get(
                "outcomes",
                []
            ):

                name = str(
                    outcome.get(
                        "name",
                        ""
                    )
                )

                lower = name.lower()

                price = safe_float(
                    outcome.get(
                        "price"
                    )
                )

                if not odds_valid(price):
                    continue

                if (
                    "draw" in lower
                    and (
                        teams_match(
                            home,
                            name
                        )
                        or
                        home.lower()
                        in lower
                    )
                ):

                    if (
                        output["dc_1x"]
                        is None
                        or price
                        > output["dc_1x"]
                    ):

                        output["dc_1x"] = price
                        output[
                            "bookmaker_dc_1x"
                        ] = bookmaker_name

                elif (
                    "draw" in lower
                    and (
                        teams_match(
                            away,
                            name
                        )
                        or
                        away.lower()
                        in lower
                    )
                ):

                    if (
                        output["dc_x2"]
                        is None
                        or price
                        > output["dc_x2"]
                    ):

                        output["dc_x2"] = price
                        output[
                            "bookmaker_dc_x2"
                        ] = bookmaker_name

                elif (
                    "draw" not in lower
                    and
                    teams_match(
                        home,
                        name
                    )
                    and
                    teams_match(
                        away,
                        name
                    )
                ):

                    if (
                        output["dc_12"]
                        is None
                        or price
                        > output["dc_12"]
                    ):

                        output["dc_12"] = price
                        output[
                            "bookmaker_dc_12"
                        ] = bookmaker_name

    return output


# ============================================================
# VALUE-KANDIDATEN
# ============================================================

def build_value_candidates(
    df
):
    candidates = []

    if df.empty:
        return pd.DataFrame()

    for idx, row in df.iterrows():

        match_id = row[
            "match_id"
        ]

        # ------------------------------------------
        # 1X2
        # ------------------------------------------

        for selection, odd_col, p_col, bm_col in [
            (
                "1",
                "odd_1",
                "final_1",
                "bookmaker_1"
            ),
            (
                "X",
                "odd_x",
                "final_x",
                "bookmaker_x"
            ),
            (
                "2",
                "odd_2",
                "final_2",
                "bookmaker_2"
            ),
        ]:

            odd = row.get(
                odd_col
            )

            probability = row.get(
                p_col
            )

            if not odds_valid(
                odd
            ):
                continue

            if probability is None:
                continue

            value = (
                probability
                * odd
                - 1
            )

            if value <= 0:
                continue

            candidates.append({
                "match_id": match_id,
                "league": row["league"],
                "home": row["home"],
                "away": row["away"],
                "time": row["local_datetime"],

                "market": "1X2",
                "selection": selection,

                "odds": float(odd),
                "probability": float(
                    probability
                ),

                "value": float(value),

                "bookmaker": row.get(
                    bm_col
                ),

                "source": "LIVE",
            })

        # ------------------------------------------
        # OVER 2.5
        # ------------------------------------------

        odd = row.get(
            "over25_odd"
        )

        probability = row.get(
            "over25"
        )

        if (
            odds_valid(odd)
            and probability is not None
        ):

            value = (
                probability
                * odd
                - 1
            )

            if value > 0:

                candidates.append({
                    "match_id": match_id,
                    "league": row["league"],
                    "home": row["home"],
                    "away": row["away"],
                    "time": row["local_datetime"],

                    "market": "Over/Under 2.5",
                    "selection": "Over 2.5",

                    "odds": float(odd),
                    "probability": float(
                        probability
                    ),

                    "value": float(value),

                    "bookmaker": row.get(
                        "odds_bookmaker_over25"
                    ),

                    "source": "LIVE",
                })

        # ------------------------------------------
        # UNDER 2.5
        # ------------------------------------------

        odd = row.get(
            "under25_odd"
        )

        probability = row.get(
            "under25"
        )

        if (
            odds_valid(odd)
            and probability is not None
        ):

            value = (
                probability
                * odd
                - 1
            )

            if value > 0:

                candidates.append({
                    "match_id": match_id,
                    "league": row["league"],
                    "home": row["home"],
                    "away": row["away"],
                    "time": row["local_datetime"],

                    "market": "Over/Under 2.5",
                    "selection": "Under 2.5",

                    "odds": float(odd),
                    "probability": float(
                        probability
                    ),

                    "value": float(value),

                    "bookmaker": row.get(
                        "odds_bookmaker_under25"
                    ),

                    "source": "LIVE",
                })

    if not candidates:
        return pd.DataFrame()

    result = pd.DataFrame(
        candidates
    )

    result["score"] = (
        result["value"] * 100
        +
        result["probability"] * 15
        -
        np.maximum(
            result["odds"] - 3,
            0
        ) * 2
    )

    return result.sort_values(
        "score",
        ascending=False
    ).reset_index(
        drop=True
    )


# ============================================================
# TOP-5 KOMBI
# ============================================================

def generate_top5_combo(
    candidates,
    legs=5,
):
    if candidates.empty:
        return pd.DataFrame()

    candidates = candidates.copy()

    candidates = candidates[
        candidates["probability"] >= 0.50
    ]

    candidates = candidates[
        candidates["value"] > 0
    ]

    if candidates.empty:
        return pd.DataFrame()

    candidates = candidates.sort_values(
        "score",
        ascending=False
    )

    selected = []

    used_matches = set()
    market_counts = defaultdict(int)

    # ------------------------------------------
    # 1. Erste Runde:
    # maximal 1 Tipp pro Spiel
    # ------------------------------------------

    for _, row in candidates.iterrows():

        match_id = row[
            "match_id"
        ]

        if match_id in used_matches:
            continue

        market = row[
            "market"
        ]

        # Nicht mehr als 3 gleiche Marktarten
        if market_counts[
            market
        ] >= 3:
            continue

        selected.append(
            row.to_dict()
        )

        used_matches.add(
            match_id
        )

        market_counts[
            market
        ] += 1

        if len(selected) >= legs:
            break

    # ------------------------------------------
    # 2. Falls noch nicht genug:
    # weitere Kandidaten
    # ------------------------------------------

    if len(selected) < legs:

        for _, row in candidates.iterrows():

            if len(selected) >= legs:
                break

            match_id = row[
                "match_id"
            ]

            if match_id in used_matches:
                continue

            selected.append(
                row.to_dict()
            )

            used_matches.add(
                match_id
            )

    if not selected:
        return pd.DataFrame()

    return pd.DataFrame(
        selected
    ).reset_index(
        drop=True
    )


def combo_statistics(
    combo
):
    if combo.empty:
        return None

    total_odds = 1.0
    joint_probability = 1.0

    for _, row in combo.iterrows():

        total_odds *= float(
            row["odds"]
        )

        joint_probability *= float(
            row["probability"]
        )

    return {
        "total_odds": total_odds,
        "joint_probability": joint_probability,
    }


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "⚙️ WETT-KI V2.1"
)

football_token = st.sidebar.text_input(
    "football-data.org Token",
    value=st.session_state.football_token,
    type="password",
)

odds_key = st.sidebar.text_input(
    "The Odds API Key",
    value=st.session_state.odds_key,
    type="password",
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
        "Bundesliga",
        "Champions League",
        "Premier League",
        "La Liga",
        "Serie A",
        "Ligue 1",
    ],
)


days_forward = st.sidebar.slider(
    "📅 Spiele voraus",
    min_value=3,
    max_value=21,
    value=10,
)


history_days = st.sidebar.slider(
    "🧠 Historie",
    min_value=60,
    max_value=365,
    value=180,
    step=30,
)


risk_filter = st.sidebar.multiselect(
    "Risiko anzeigen",
    [
        "LOW",
        "MID",
        "HIGH",
        "NO ODDS",
    ],
    default=[
        "LOW",
        "MID",
        "HIGH",
    ],
)


bankroll = st.sidebar.number_input(
    "💰 Bankroll (€)",
    min_value=1.0,
    value=100.0,
    step=10.0,
)


live_double_chance = st.sidebar.checkbox(
    "🎯 Live-Doppelchance abrufen",
    value=False,
    help=(
        "Verwendet zusätzliche Event-API-Aufrufe. "
        "Das Modell zeigt Doppelchance immer kostenlos "
        "als Modellwahrscheinlichkeit/faires Modell-Odd."
    ),
)


st.sidebar.markdown("---")

load_clicked = st.sidebar.button(
    "🔄 DATEN AKTUALISIEREN",
    use_container_width=True,
    type="primary",
)


# ============================================================
# DATEN LADEN
# ============================================================

if load_clicked:

    st.session_state.errors = []
    st.session_state.api_status = {}
    st.session_state.fixtures = (
        pd.DataFrame()
    )

    if not selected_leagues:

        st.error(
            "Bitte mindestens einen Wettbewerb auswählen."
        )

    elif not st.session_state.football_token:

        st.error(
            "football-data.org Token fehlt."
        )

    elif not st.session_state.odds_key:

        st.error(
            "The Odds API Key fehlt."
        )

    else:

        # ----------------------------------------------------
        # 1. ODDS SPORTS KATALOG
        # ----------------------------------------------------

        with st.spinner(
            "Prüfe verfügbare Odds-Sportkeys..."
        ):

            sports_catalog, sports_result = (
                get_odds_sports(
                    st.session_state.odds_key
                )
            )

        if not sports_result["ok"]:

            st.session_state.errors.append(
                "Odds API /sports: "
                f"HTTP {sports_result.get('status')}: "
                f"{sports_result.get('message')}"
            )

        else:

            st.session_state.sports_catalog = (
                sports_catalog
            )

        # ----------------------------------------------------
        # 2. SPORTKEYS RESOLVEN
        # ----------------------------------------------------

        resolved_keys = {}

        if sports_result["ok"]:

            for league in selected_leagues:

                resolved = resolve_sport_key(
                    league,
                    sports_catalog
                )

                resolved_keys[
                    league
                ] = resolved

                if not resolved:

                    st.session_state.errors.append(
                        f"{league}: "
                        "Aktuell kein aktiver Odds-Sport "
                        "im /sports-Katalog gefunden. "
                        "Es wird deshalb kein 400-Request "
                        "mehr blind abgeschickt."
                    )

        # ----------------------------------------------------
        # 3. FOOTBALL-DATA UPCOMING
        # ----------------------------------------------------

        with st.spinner(
            "Lade kommende Spiele..."
        ):

            fixtures, fixture_errors = (
                get_upcoming_fixtures(
                    st.session_state.football_token,
                    selected_leagues,
                    days_forward,
                )
            )

        st.session_state.errors.extend(
            fixture_errors
        )

        # ----------------------------------------------------
        # 4. HISTORIE
        # ----------------------------------------------------

        with st.spinner(
            "Baue stärkeres Modell..."
        ):

            codes = tuple(
                LEAGUES[name][
                    "football_data"
                ]
                for name in selected_leagues
            )

            historical = (
                get_historical_cached(
                    st.session_state.football_token,
                    codes,
                    history_days,
                )
            )

            model_context = (
                build_model_context(
                    historical
                )
            )

        # ----------------------------------------------------
        # 5. ODDS PRO LIGA
        # ----------------------------------------------------

        odds_by_league = {}

        with st.spinner(
            "Lade echte Buchmacherquoten..."
        ):

            leagues_with_fixtures = set(
                f["league"]
                for f in fixtures
            )

            for league in selected_leagues:

                if (
                    league
                    not in leagues_with_fixtures
                ):
                    continue

                sport_key = resolved_keys.get(
                    league
                )

                if not sport_key:

                    odds_by_league[
                        league
                    ] = []

                    continue

                events, odds_status = (
                    get_odds_for_sport(
                        st.session_state.odds_key,
                        sport_key,
                    )
                )

                odds_by_league[
                    league
                ] = events

                st.session_state.api_status[
                    league
                ] = {
                    "sport_key": sport_key,
                    **odds_status,
                }

                if not odds_status["ok"]:

                    st.session_state.errors.append(
                        f"{league} "
                        f"({sport_key}): "
                        f"HTTP {odds_status.get('status')}: "
                        f"{odds_status.get('message')}"
                    )

        # ----------------------------------------------------
        # 6. MATCH + MODEL + ODDS
        # ----------------------------------------------------

        rows = []

        for fixture in fixtures:

            model = calculate_model(
                fixture,
                model_context,
            )

            event = find_odds_event(
                fixture,
                odds_by_league.get(
                    fixture["league"],
                    []
                ),
            )

            if event:

                odds = parse_event_odds(
                    event,
                    fixture,
                )

            else:

                odds = {
                    "odd_1": None,
                    "odd_x": None,
                    "odd_2": None,

                    "bookmaker_1": None,
                    "bookmaker_x": None,
                    "bookmaker_2": None,

                    "over25": None,
                    "under25": None,

                    "bookmaker_over25": None,
                    "bookmaker_under25": None,

                    "dc_1x": None,
                    "dc_x2": None,
                    "dc_12": None,

                    "bookmaker_dc_1x": None,
                    "bookmaker_dc_x2": None,
                    "bookmaker_dc_12": None,

                    "odds_event_id": None,
                    "bookmaker_rows": [],
                }

            analysis = analyze_fixture(
                fixture,
                model,
                odds,
            )

            row = {
                **fixture,
                **odds,
                **analysis,
                "local_datetime": (
                    format_local_datetime(
                        fixture[
                            "utcDate"
                        ]
                    )
                ),
            }

            rows.append(row)

        result_df = pd.DataFrame(
            rows
        )

        # ----------------------------------------------------
        # 7. OPTIONAL LIVE DOUBLE CHANCE
        # ----------------------------------------------------

        if (
            live_double_chance
            and not result_df.empty
        ):

            with st.spinner(
                "Hole Live-Doppelchance..."
            ):

                for idx, row in result_df.iterrows():

                    event_id = row.get(
                        "odds_event_id"
                    )

                    sport_key = resolved_keys.get(
                        row["league"]
                    )

                    if not event_id or not sport_key:
                        continue

                    event_dc = (
                        get_event_double_chance(
                            st.session_state.odds_key,
                            sport_key,
                            event_id,
                        )
                    )

                    dc = (
                        parse_double_chance_event(
                            event_dc,
                            row,
                        )
                    )

                    for key, value in dc.items():

                        result_df.loc[
                            idx,
                            key
                        ] = value

        st.session_state.fixtures = (
            result_df
        )

        st.session_state.last_update = (
            datetime.now()
        )

# ============================================================
# HEADER
# ============================================================

st.title(
    "⚽ WETT-KI V2.1"
)

st.caption(
    "Stärkeres Modell + echte Buchmacherquoten + "
    "Value + 25%-Kelly + Over/Under + Doppelchance + "
    "automatische Top-5-Kombi"
)


# ============================================================
# STATUS
# ============================================================

if st.session_state.last_update:

    st.success(
        "Zuletzt aktualisiert: "
        +
        st.session_state.last_update.strftime(
            "%d.%m.%Y %H:%M:%S"
        )
    )


if st.session_state.errors:

    with st.expander(
        "⚠️ API-Hinweise / Fehler",
        expanded=True,
    ):

        for error in st.session_state.errors:
            st.warning(error)


df_all = (
    st.session_state.fixtures.copy()
)


if df_all.empty:

    st.info(
        "Noch keine Daten geladen. "
        "Links **DATEN AKTUALISIEREN** drücken."
    )

    st.stop()


# ============================================================
# STATUS-KENNZAHLEN
# ============================================================

real_odds_count = int(
    df_all[
        "has_real_odds"
    ].sum()
)

value_candidates = build_value_candidates(
    df_all
)

value_count = len(
    value_candidates
)


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "⚽ Spiele",
    len(df_all)
)

c2.metric(
    "💶 echte Quoten",
    real_odds_count
)

c3.metric(
    "🔥 Value-Kandidaten",
    value_count
)

c4.metric(
    "🏦 Odds-Ligen",
    sum(
        1
        for status in
        st.session_state.api_status.values()
        if status.get("ok")
    )
)


# ============================================================
# TOP-5 KOMBI
# ============================================================

top5 = generate_top5_combo(
    value_candidates,
    legs=5,
)

combo_stats = combo_statistics(
    top5
)


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "🔥 Top Value",
        "🎟️ Top-5 Kombi",
        "📊 Märkte",
        "🏦 Buchmacher",
        "🤖 Modell",
    ]
)


# ============================================================
# TAB 1 – TOP VALUE
# ============================================================

with tab1:

    st.subheader(
        "🔥 Top Value Bets"
    )

    display_df = df_all.copy()

    if risk_filter:

        display_df = display_df[
            display_df["risk"].isin(
                risk_filter
            )
        ]

    top_value = build_value_candidates(
        display_df
    )

    if top_value.empty:

        st.info(
            "Keine positiven Value-Kandidaten "
            "mit echten Quoten gefunden."
        )

    else:

        for _, row in top_value.head(
            15
        ).iterrows():

            st.markdown(
                f"### {row['home']} "
                f"vs {row['away']}"
            )

            st.caption(
                f"{row['league']} · "
                f"{row['time']}"
            )

            a, b, c, d, e = st.columns(
                5
            )

            a.metric(
                "Markt",
                row["market"]
            )

            b.metric(
                "Tipp",
                row["selection"]
            )

            c.metric(
                "Quote",
                f"{row['odds']:.2f}"
            )

            d.metric(
                "Chance",
                f"{row['probability'] * 100:.1f}%"
            )

            e.metric(
                "Value",
                f"{row['value'] * 100:+.2f}%"
            )

            stake = kelly_fraction(
                row["probability"],
                row["odds"],
                0.25,
            ) * bankroll

            st.caption(
                f"Buchmacher: "
                f"{row['bookmaker'] or '—'} · "
                f"25%-Kelly: "
                f"{stake:.2f} €"
            )

            st.divider()


# ============================================================
# TAB 2 – TOP-5 KOMBI
# ============================================================

with tab2:

    st.subheader(
        "🎟️ Automatische Top-5-Kombi"
    )

    if top5.empty:

        st.warning(
            "Noch nicht genug positive "
            "Value-Legs mit echten Quoten."
        )

    else:

        st.success(
            f"{len(top5)} Legs automatisch "
            "nach Value + Wahrscheinlichkeit ausgewählt."
        )

        combo_table = []

        for _, row in top5.iterrows():

            combo_table.append({
                "Liga": row["league"],
                "Spiel": (
                    f"{row['home']} – "
                    f"{row['away']}"
                ),
                "Markt": row["market"],
                "Tipp": row["selection"],
                "Quote": round(
                    row["odds"],
                    2
                ),
                "Chance": (
                    f"{row['probability'] * 100:.1f}%"
                ),
                "Value": (
                    f"{row['value'] * 100:+.2f}%"
                ),
                "Buchmacher": (
                    row["bookmaker"]
                    or "—"
                ),
            })

        st.dataframe(
            pd.DataFrame(
                combo_table
            ),
            use_container_width=True,
            hide_index=True,
        )

        if combo_stats:

            total_odds = combo_stats[
                "total_odds"
            ]

            probability = combo_stats[
                "joint_probability"
            ]

            combo_stake = min(
                bankroll * 0.03,
                10.0
            )

            payout = (
                combo_stake
                * total_odds
            )

            x1, x2, x3, x4 = st.columns(
                4
            )

            x1.metric(
                "Gesamtquote",
                f"{total_odds:.2f}"
            )

            x2.metric(
                "Modell-Kombi-Chance",
                f"{probability * 100:.2f}%"
            )

            x3.metric(
                "Kombi-Einsatz",
                f"{combo_stake:.2f} €"
            )

            x4.metric(
                "Auszahlung",
                f"{payout:.2f} €"
            )

            st.caption(
                "Die Kombi-Wahrscheinlichkeit ist das "
                "Produkt der Einzelwahrscheinlichkeiten "
                "und nimmt Unabhängigkeit der Legs an. "
                "Das ist eine Modellannahme, keine Garantie."
            )


# ============================================================
# TAB 3 – MÄRKTE
# ============================================================

with tab3:

    st.subheader(
        "📊 1X2 · Doppelchance · Over/Under"
    )

    for _, row in df_all.iterrows():

        st.markdown(
            f"### {row['home']} – {row['away']}"
        )

        st.caption(
            f"{row['league']} · "
            f"{row['local_datetime']}"
        )

        a, b, c = st.columns(3)

        a.metric(
            "1",
            f"{row['p1'] * 100:.1f}%"
        )

        b.metric(
            "X",
            f"{row['px'] * 100:.1f}%"
        )

        c.metric(
            "2",
            f"{row['p2'] * 100:.1f}%"
        )

        st.markdown(
            "**🎯 Doppelchance – Modell**"
        )

        dc1, dc2, dc3 = st.columns(3)

        dc1.metric(
            "1X",
            f"{row['dc_1x_model'] * 100:.1f}%",
            f"fair {row['dc_1x_fair']:.2f}"
        )

        dc2.metric(
            "X2",
            f"{row['dc_x2_model'] * 100:.1f}%",
            f"fair {row['dc_x2_fair']:.2f}"
        )

        dc3.metric(
            "12",
            f"{row['dc_12_model'] * 100:.1f}%",
            f"fair {row['dc_12_fair']:.2f}"
        )

        st.markdown(
            "**⚽ Over / Under 2.5**"
        )

        ou1, ou2 = st.columns(2)

        ou1.metric(
            "Over 2.5",
            f"{row['over25'] * 100:.1f}%",
            (
                f"Quote {row['over25_odd']:.2f}"
                if odds_valid(
                    row["over25_odd"]
                )
                else "keine Live-Quote"
            )
        )

        ou2.metric(
            "Under 2.5",
            f"{row['under25'] * 100:.1f}%",
            (
                f"Quote {row['under25_odd']:.2f}"
                if odds_valid(
                    row["under25_odd"]
                )
                else "keine Live-Quote"
            )
        )

        st.divider()


# ============================================================
# TAB 4 – BUCHMACHER
# ============================================================

with tab4:

    st.subheader(
        "🏦 Buchmachervergleich"
    )

    rows = []

    for _, row in df_all.iterrows():

        match_name = (
            f"{row['home']} – "
            f"{row['away']}"
        )

        if odds_valid(
            row["odd_1"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "1X2",
                "Auswahl": "1",
                "Quote": row["odd_1"],
                "Buchmacher": (
                    row["bookmaker_1"]
                    or "—"
                ),
            })

        if odds_valid(
            row["odd_x"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "1X2",
                "Auswahl": "X",
                "Quote": row["odd_x"],
                "Buchmacher": (
                    row["bookmaker_x"]
                    or "—"
                ),
            })

        if odds_valid(
            row["odd_2"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "1X2",
                "Auswahl": "2",
                "Quote": row["odd_2"],
                "Buchmacher": (
                    row["bookmaker_2"]
                    or "—"
                ),
            })

        if odds_valid(
            row["over25_odd"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "Over/Under 2.5",
                "Auswahl": "Over 2.5",
                "Quote": row[
                    "over25_odd"
                ],
                "Buchmacher": (
                    row[
                        "odds_bookmaker_over25"
                    ]
                    or "—"
                ),
            })

        if odds_valid(
            row["under25_odd"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "Over/Under 2.5",
                "Auswahl": "Under 2.5",
                "Quote": row[
                    "under25_odd"
                ],
                "Buchmacher": (
                    row[
                        "odds_bookmaker_under25"
                    ]
                    or "—"
                ),
            })

        if odds_valid(
            row["dc_1x"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "Doppelchance",
                "Auswahl": "1X",
                "Quote": row["dc_1x"],
                "Buchmacher": (
                    row[
                        "bookmaker_dc_1x"
                    ]
                    or "—"
                ),
            })

        if odds_valid(
            row["dc_x2"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "Doppelchance",
                "Auswahl": "X2",
                "Quote": row["dc_x2"],
                "Buchmacher": (
                    row[
                        "bookmaker_dc_x2"
                    ]
                    or "—"
                ),
            })

        if odds_valid(
            row["dc_12"]
        ):

            rows.append({
                "Spiel": match_name,
                "Liga": row["league"],
                "Markt": "Doppelchance",
                "Auswahl": "12",
                "Quote": row["dc_12"],
                "Buchmacher": (
                    row[
                        "bookmaker_dc_12"
                    ]
                    or "—"
                ),
            })

    if rows:

        bookmaker_df = pd.DataFrame(
            rows
        )

        bookmaker_df = (
            bookmaker_df.sort_values(
                "Quote",
                ascending=False
            )
        )

        st.dataframe(
            bookmaker_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Keine echten Buchmacherquoten "
            "gefunden."
        )


# ============================================================
# TAB 5 – MODELL
# ============================================================

with tab5:

    st.subheader(
        "🤖 Modell-Details"
    )

    model_rows = []

    for _, row in df_all.iterrows():

        model_rows.append({
            "Liga": row["league"],
            "Spiel": (
                f"{row['home']} – "
                f"{row['away']}"
            ),
            "1": (
                f"{row['p1'] * 100:.1f}%"
            ),
            "X": (
                f"{row['px'] * 100:.1f}%"
            ),
            "2": (
                f"{row['p2'] * 100:.1f}%"
            ),
            "Over 2.5": (
                f"{row['over25'] * 100:.1f}%"
            ),
            "BTTS": (
                f"{row['btts'] * 100:.1f}%"
            ),
            "Home λ": round(
                row["home_lambda"],
                2
            ),
            "Away λ": round(
                row["away_lambda"],
                2
            ),
            "Home ELO": round(
                row["home_elo"]
            ),
            "Away ELO": round(
                row["away_elo"]
            ),
            "ELO-Heimchance": (
                f"{row['elo_probability'] * 100:.1f}%"
            ),
        })

    st.dataframe(
        pd.DataFrame(
            model_rows
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        "Modellkern: recency-gewichtete Heim/Auswärts-"
        "Leistung + Liga-Torumfeld + ELO + Poisson + "
        "Dixon-Coles-Korrektur. Bundesliga und Champions "
        "League verwenden stärkere ELO-Gewichtung."
    )


# ============================================================
# API DEBUG
# ============================================================

with st.expander(
    "🔧 API-Diagnose",
    expanded=False,
):

    st.write(
        "Aktuell gefundene Odds-Sportkeys:"
    )

    if st.session_state.sports_catalog:

        sports_debug = []

        for league in selected_leagues:

            resolved = resolve_sport_key(
                league,
                st.session_state.sports_catalog
            )

            sports_debug.append({
                "Liga": league,
                "konfiguriert": LEAGUES[
                    league
                ]["odds_key"],
                "aktuell gefunden": (
                    resolved or "NICHT GEFUNDEN"
                ),
            })

        st.dataframe(
            pd.DataFrame(
                sports_debug
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.write(
            "Noch kein /sports-Katalog vorhanden."
        )

    if st.session_state.api_status:

        st.write(
            "Odds-API Status:"
        )

        debug_rows = []

        for league, status in (
            st.session_state.api_status.items()
        ):

            meta = status.get(
                "meta",
                {}
            )

            debug_rows.append({
                "Liga": league,
                "Sport-Key": status.get(
                    "sport_key"
                ),
                "Status": status.get(
                    "status"
                ),
                "OK": status.get(
                    "ok"
                ),
                "Märkte": status.get(
                    "market_mode"
                ),
                "Fehler": status.get(
                    "message"
                ),
                "Remaining": meta.get(
                    "remaining"
                ),
                "Used": meta.get(
                    "used"
                ),
                "Last Cost": meta.get(
                    "last_cost"
                ),
            })

        st.dataframe(
            pd.DataFrame(
                debug_rows
            ),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "WETT-KI V2.1 · Keine Fake-Quoten · "
    "Value/Kelly/Kombi ausschließlich mit echten "
    "Buchmacherquoten. Modellwahrscheinlichkeiten sind "
    "Schätzungen und keine Gewinn- oder Wettgarantie."
        )
