import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from itertools import combinations

# ============================================================
# ⚽ WETT-KI – FUSSBALL 1/X/2
# Nur echte aktuelle Spiele + aktuelle Quoten
# ============================================================

st.set_page_config(
    page_title="⚽ Wett-KI",
    page_icon="⚽",
    layout="wide"
)

# ============================================================
# KONFIGURATION
# ============================================================

APP_TITLE = "⚽ Wett-KI – Fußball 1/X/2"

# ============================================================
# 🔑 API-KEY
# ============================================================
# Deinen API-Key hier eintragen:
API_KEY = "d0d0d6f9c7c493345eee17b80f3ded05"

API_URL = "https://v3.football.api-sports.io"

TIMEZONE = "Europe/Berlin"

# Nur Fußball-Ligen
LEAGUES = {
    39: "Premier League",
    78: "Bundesliga",
    140: "La Liga",
    135: "Serie A",
    61: "Ligue 1",
    2: "Champions League",
    3: "Europa League",
    848: "Conference League",
}

# Maximal so viele Spiele bekommen automatisch Quoten.
# Die Spiele selbst werden trotzdem vollständig angezeigt.
MAX_ODDS_MATCHES = 30

MAX_GOALS = 8

# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #777;
        margin-bottom: 25px;
    }

    .risk-low {
        padding: 8px 14px;
        border-radius: 10px;
        font-weight: bold;
        background-color: #d9f7df;
    }

    .risk-mid {
        padding: 8px 14px;
        border-radius: 10px;
        font-weight: bold;
        background-color: #fff1c7;
    }

    .risk-high {
        padding: 8px 14px;
        border-radius: 10px;
        font-weight: bold;
        background-color: #ffdede;
    }

    .pick-box {
        padding: 12px;
        border-radius: 12px;
        background-color: #f4f4f4;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def now_local():
    return datetime.now(ZoneInfo(TIMEZONE))


def api_headers():
    return {
        "x-apisports-key": API_KEY
    }


def api_get(endpoint, params=None, timeout=20):
    """
    API-Aufruf mit Fehlerbehandlung.
    """
    try:
        response = requests.get(
            f"{API_URL}{endpoint}",
            headers=api_headers(),
            params=params,
            timeout=timeout
        )

        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"

        data = response.json()

        if data.get("errors"):
            return None, str(data["errors"])

        return data, None

    except Exception as e:
        return None, str(e)


def next_friday():
    """
    Liefert den nächsten Freitag.
    """
    today = now_local().date()
    days_until_friday = (4 - today.weekday()) % 7

    # Wenn heute Freitag ist, nehmen wir den nächsten Freitag,
    # damit wir nicht versehentlich bereits vergangene Spiele
    # verwenden.
    if days_until_friday == 0:
        days_until_friday = 7

    return today + timedelta(days=days_until_friday)


def next_friday_thursday():
    """
    Fenster Freitag bis Donnerstag.
    """
    friday = next_friday()
    thursday = friday + timedelta(days=6)

    return friday, thursday


def format_date(dt):
    if pd.isna(dt):
        return ""

    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()

    return dt.strftime("%d.%m.%Y %H:%M")


def poisson_probability(lam, goals):
    if lam <= 0:
        return 0.0

    return math.exp(-lam) * (lam ** goals) / math.factorial(goals)


def poisson_1x2(home_lambda, away_lambda):
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for hg in range(MAX_GOALS + 1):
        for ag in range(MAX_GOALS + 1):
            p = (
                poisson_probability(home_lambda, hg)
                * poisson_probability(away_lambda, ag)
            )

            if hg > ag:
                home_win += p
            elif hg == ag:
                draw += p
            else:
                away_win += p

    total = home_win + draw + away_win

    if total <= 0:
        return {
            "1": 1 / 3,
            "X": 1 / 3,
            "2": 1 / 3
        }

    return {
        "1": home_win / total,
        "X": draw / total,
        "2": away_win / total
    }


# ============================================================
# SPIELE LADEN
# ============================================================

@st.cache_data(ttl=900)
def load_upcoming_fixtures():
    """
    Lädt ausschließlich echte zukünftige Spiele.
    """

    friday, thursday = next_friday_thursday()

    all_matches = []

    errors = []

    for league_id, league_name in LEAGUES.items():

        params = {
            "league": league_id,
            "season": friday.year,
            "from": friday.strftime("%Y-%m-%d"),
            "to": thursday.strftime("%Y-%m-%d"),
            "timezone": TIMEZONE
        }

        data, error = api_get("/fixtures", params)

        if error:
            errors.append(f"{league_name}: {error}")
            continue

        if not data:
            continue

        response = data.get("response", [])

        for item in response:

            fixture = item.get("fixture", {})
            teams = item.get("teams", {})

            fixture_id = fixture.get("id")

            date_string = fixture.get("date")

            if not fixture_id or not date_string:
                continue

            try:
                kickoff = pd.to_datetime(date_string, utc=True)
                kickoff = kickoff.tz_convert(TIMEZONE)
            except Exception:
                continue

            # ==================================================
            # WICHTIG:
            # Nur Spiele, die tatsächlich noch stattfinden.
            # ==================================================

            status = fixture.get("status", {}).get("short")

            allowed_statuses = {
                "NS",
                "TBD"
            }

            if status not in allowed_statuses:
                continue

            # Keine Spiele aus der Vergangenheit.
            current_time = pd.Timestamp.now(tz=TIMEZONE)

            if kickoff <= current_time:
                continue

            home = teams.get("home", {}).get("name")
            away = teams.get("away", {}).get("name")

            if not home or not away:
                continue

            all_matches.append({
                "fixture_id": fixture_id,
                "league_id": league_id,
                "league": league_name,
                "date": kickoff,
                "home_team": home,
                "away_team": away,
                "status": status
            })

    if not all_matches:
        return pd.DataFrame(), errors

    df = pd.DataFrame(all_matches)

    # Doppelte Spiele vermeiden
    df = df.drop_duplicates(subset=["fixture_id"])

    # Nach Datum sortieren
    df = df.sort_values("date").reset_index(drop=True)

    return df, errors


# ============================================================
# HISTORISCHE SPIELE
# ============================================================

@st.cache_data(ttl=3600)
def load_historical_fixtures(league_id, season):
    """
    Lädt abgeschlossene Spiele für das Poisson-Modell.
    """

    params = {
        "league": league_id,
        "season": season,
        "status": "FT"
    }

    data, error = api_get("/fixtures", params)

    if error or not data:
        return pd.DataFrame()

    rows = []

    for item in data.get("response", []):

        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})

        home = teams.get("home", {}).get("name")
        away = teams.get("away", {}).get("name")

        home_goals = goals.get("home")
        away_goals = goals.get("away")

        date_string = fixture.get("date")

        if (
            not home
            or not away
            or home_goals is None
            or away_goals is None
            or not date_string
        ):
            continue

        rows.append({
            "date": pd.to_datetime(date_string, utc=True).tz_convert(TIMEZONE),
            "home_team": home,
            "away_team": away,
            "home_goals": int(home_goals),
            "away_goals": int(away_goals)
        })

    return pd.DataFrame(rows)


# ============================================================
# FORM / TEAM-STÄRKE
# ============================================================

def calculate_team_strength(history, team):
    """
    Berechnet eine einfache gewichtete Teamstärke.
    """

    if history.empty:
        return {
            "attack_home": 1.35,
            "attack_away": 1.10,
            "defense_home": 1.15,
            "defense_away": 1.15
        }

    team_home = history[history["home_team"] == team]
    team_away = history[history["away_team"] == team]

    if team_home.empty and team_away.empty:
        return {
            "attack_home": 1.35,
            "attack_away": 1.10,
            "defense_home": 1.15,
            "defense_away": 1.15
        }

    home_scored = (
        team_home["home_goals"].mean()
        if not team_home.empty else 1.35
    )

    away_scored = (
        team_away["away_goals"].mean()
        if not team_away.empty else 1.10
    )

    home_conceded = (
        team_home["away_goals"].mean()
        if not team_home.empty else 1.15
    )

    away_conceded = (
        team_away["home_goals"].mean()
        if not team_away.empty else 1.15
    )

    return {
        "attack_home": max(0.2, float(home_scored)),
        "attack_away": max(0.2, float(away_scored)),
        "defense_home": max(0.2, float(home_conceded)),
        "defense_away": max(0.2, float(away_conceded))
    }


def model_prediction(home_team, away_team, history):
    """
    Berechnet 1/X/2 Wahrscheinlichkeiten.
    """

    if history.empty:
        return {
            "1": 0.33,
            "X": 0.34,
            "2": 0.33,
            "home_lambda": 1.35,
            "away_lambda": 1.10
        }

    home_games = history[
        history["home_team"] == home_team
    ]

    away_games = history[
        history["away_team"] == away_team
    ]

    if home_games.empty:
        home_attack = history["home_goals"].mean()
        home_defense = history["away_goals"].mean()
    else:
        home_attack = home_games["home_goals"].mean()
        home_defense = home_games["away_goals"].mean()

    if away_games.empty:
        away_attack = history["away_goals"].mean()
        away_defense = history["home_goals"].mean()
    else:
        away_attack = away_games["away_goals"].mean()
        away_defense = away_games["home_goals"].mean()

    league_home_avg = max(
        0.3,
        float(history["home_goals"].mean())
    )

    league_away_avg = max(
        0.3,
        float(history["away_goals"].mean())
    )

    home_lambda = (
        0.65 * home_attack
        + 0.35 * away_defense
    )

    away_lambda = (
        0.65 * away_attack
        + 0.35 * home_defense
    )

    # Nicht unrealistisch groß werden lassen
    home_lambda = max(
        0.15,
        min(home_lambda, 4.5)
    )

    away_lambda = max(
        0.15,
        min(away_lambda, 4.0)
    )

    probs = poisson_1x2(
        home_lambda,
        away_lambda
    )

    return {
        **probs,
        "home_lambda": home_lambda,
        "away_lambda": away_lambda
    }


# ============================================================
# QUOTEN
# ============================================================

def parse_1x2_odds(data):
    """
    Liest Match-Winner-Quoten aus API-Football.
    """

    bookmakers = {}

    if not data:
        return bookmakers

    response = data.get("response", [])

    for bookmaker_block in response:

        bookmaker = bookmaker_block.get("bookmaker", {})

        bookmaker_name = bookmaker.get("name")

        if not bookmaker_name:
            continue

        bets = bookmaker_block.get("bets", [])

        result = {}

        for bet in bets:

            bet_name = str(
                bet.get("name", "")
            ).lower()

            if not any(
                x in bet_name
                for x in [
                    "match winner",
                    "1x2",
                    "winner"
                ]
            ):
                continue

            values = bet.get("values", [])

            for value in values:

                label = str(
                    value.get("value", "")
                ).lower()

                odd = value.get("odd")

                try:
                    odd = float(odd)
                except Exception:
                    continue

                if label in ["home", "1"]:
                    result["1"] = odd

                elif label in ["draw", "x"]:
                    result["X"] = odd

                elif label in ["away", "2"]:
                    result["2"] = odd

        if len(result) == 3:
            bookmakers[bookmaker_name] = result

    return bookmakers


@st.cache_data(ttl=600)
def load_odds_for_fixture(fixture_id):
    """
    Lädt aktuelle Pre-Match-Quoten.
    """

    params = {
        "fixture": int(fixture_id)
    }

    data, error = api_get(
        "/odds",
        params
    )

    if error or not data:
        return {}

    return parse_1x2_odds(data)


def best_odds(bookmakers):
    """
    Beste Quote pro 1/X/2.
    """

    result = {
        "1": None,
        "X": None,
        "2": None
    }

    bookmaker_for = {
        "1": None,
        "X": None,
        "2": None
    }

    for bookmaker, odds in bookmakers.items():

        for outcome in ["1", "X", "2"]:

            odd = odds.get(outcome)

            if odd is None:
                continue

            if (
                result[outcome] is None
                or odd > result[outcome]
            ):
                result[outcome] = odd
                bookmaker_for[outcome] = bookmaker

    return result, bookmaker_for


def normalized_market_probabilities(odds):
    """
    Entfernt grob die Buchmacher-Marge.
    """

    values = []

    for outcome in ["1", "X", "2"]:
        odd = odds.get(outcome)

        if odd is not None and odd > 1:
            values.append(
                1 / odd
            )
        else:
            values.append(0)

    total = sum(values)

    if total <= 0:
        return {
            "1": None,
            "X": None,
            "2": None
        }

    return {
        "1": values[0] / total,
        "X": values[1] / total,
        "2": values[2] / total
    }


# ============================================================
# RISIKO
# ============================================================

def classify_risk(probabilities):
    """
    LOW = geringere Modellunsicherheit
    MID = mittlere Unsicherheit
    HIGH = hohe Unsicherheit
    """

    values = [
        probabilities["1"],
        probabilities["X"],
        probabilities["2"]
    ]

    sorted_values = sorted(
        values,
        reverse=True
    )

    top = sorted_values[0]
    second = sorted_values[1]

    gap = top - second

    if top >= 0.62 and gap >= 0.18:
        return "LOW"

    if top >= 0.52 and gap >= 0.10:
        return "MID"

    return "HIGH"


def risk_label(risk):
    if risk == "LOW":
        return "🟢 LOW"

    if risk == "MID":
        return "🟡 MID"

    return "🔴 HIGH"


# ============================================================
# SPIELE ANALYSIEREN
# ============================================================

def analyze_match(match, history):
    home = match["home_team"]
    away = match["away_team"]

    prediction = model_prediction(
        home,
        away,
        history
    )

    model_probs = {
        "1": prediction["1"],
        "X": prediction["X"],
        "2": prediction["2"]
    }

    bookmakers = load_odds_for_fixture(
        match["fixture_id"]
    )

    best, bookmaker_for = best_odds(
        bookmakers
    )

    market_probs = normalized_market_probabilities(
        best
    )

    # --------------------------------------------------------
    # Modell + Markt
    # --------------------------------------------------------

    final_probs = {}

    for outcome in ["1", "X", "2"]:

        model_p = model_probs[outcome]
        market_p = market_probs[outcome]

        if market_p is not None:
            final_probs[outcome] = (
                0.75 * model_p
                + 0.25 * market_p
            )
        else:
            final_probs[outcome] = model_p

    # Normalisieren
    total = sum(final_probs.values())

    final_probs = {
        k: v / total
        for k, v in final_probs.items()
    }

    best_outcome = max(
        final_probs,
        key=final_probs.get
    )

    probability = final_probs[best_outcome]

    fair_odds = (
        1 / probability
        if probability > 0
        else None
    )

    actual_odd = best.get(
        best_outcome
    )

    value = None

    if actual_odd is not None:
        value = (
            probability * actual_odd
            - 1
        )

    risk = classify_risk(
        final_probs
    )

    return {
        **match,
        "p1": final_probs["1"],
        "px": final_probs["X"],
        "p2": final_probs["2"],
        "pick": best_outcome,
        "probability": probability,
        "fair_odds": fair_odds,
        "odds": actual_odd,
        "value": value,
        "risk": risk,
        "best_odds_1": best.get("1"),
        "best_odds_X": best.get("X"),
        "best_odds_2": best.get("2"),
        "bookmaker_1": bookmaker_for.get("1"),
        "bookmaker_X": bookmaker_for.get("X"),
        "bookmaker_2": bookmaker_for.get("2"),
        "bookmakers": bookmakers,
        "home_lambda": prediction["home_lambda"],
        "away_lambda": prediction["away_lambda"]
    }


# ============================================================
# SCHEIN-GENERATOR
# ============================================================

RISK_PROFILES = {
    "LOW": {
        "max_legs": 3,
        "min_probability": 0.60
    },
    "MID": {
        "max_legs": 4,
        "min_probability": 0.52
    },
    "HIGH": {
        "max_legs": 5,
        "min_probability": 0.45
    }
}


def select_candidates(matches, profile):
    settings = RISK_PROFILES[profile]

    df = matches.copy()

    df = df[
        df["risk"].isin(
            ["LOW", "MID", "HIGH"]
        )
    ]

    if profile == "LOW":
        df = df[
            df["probability"]
            >= settings["min_probability"]
        ]

    elif profile == "MID":
        df = df[
            df["probability"]
            >= settings["min_probability"]
        ]

    else:
        df = df[
            df["probability"]
            >= settings["min_probability"]
        ]

    # Value bevorzugen
    df["score"] = (
        df["probability"] * 100
        + df["value"].fillna(-0.2) * 20
    )

    df = df.sort_values(
        "score",
        ascending=False
    )

    return df.head(10)


def generate_accumulator(matches, profile):
    """
    Erstellt einen Schein mit einem gemeinsamen Buchmacher.

    Wichtig:
    Ein echter Kombischein muss beim gleichen Buchmacher
    gespielt werden.
    """

    candidates = select_candidates(
        matches,
        profile
    )

    if candidates.empty:
        return None

    max_legs = RISK_PROFILES[profile]["max_legs"]

    # --------------------------------------------------------
    # Kandidaten nach Buchmacher gruppieren
    # --------------------------------------------------------

    bookmaker_groups = {}

    for _, row in candidates.iterrows():

        bookmakers = row["bookmakers"]

        for bookmaker, odds in bookmakers.items():

            if row["pick"] not in odds:
                continue

            bookmaker_groups.setdefault(
                bookmaker,
                []
            ).append(row)

    if not bookmaker_groups:
        return None

    best_ticket = None

    # --------------------------------------------------------
    # Alle Buchmacher prüfen
    # --------------------------------------------------------

    for bookmaker, rows in bookmaker_groups.items():

        unique = {}

        for row in rows:
            unique[row["fixture_id"]] = row

        rows = list(
            unique.values()
        )

        rows = sorted(
            rows,
            key=lambda x: (
                x["probability"]
                + max(
                    0,
                    x["value"]
                    if pd.notna(x["value"])
                    else 0
                )
            ),
            reverse=True
        )

        rows = rows[:max_legs]

        if not rows:
            continue

        # Für LOW maximal 3, MID 4, HIGH 5
        legs = rows

        combined_probability = 1.0
        combined_odds = 1.0

        for row in legs:

            combined_probability *= row[
                "probability"
            ]

            combined_odds *= row[
                "bookmakers"
            ][bookmaker][
                row["pick"]
            ]

        ticket = {
            "profile": profile,
            "bookmaker": bookmaker,
            "legs": legs,
            "combined_probability": combined_probability,
            "combined_odds": combined_odds
        }

        if best_ticket is None:
            best_ticket = ticket
        else:
            # Primär Wahrscheinlichkeit,
            # sekundär Quote
            score_old = (
                best_ticket["combined_probability"]
                * math.log(
                    max(
                        best_ticket["combined_odds"],
                        1.01
                    )
                )
            )

            score_new = (
                ticket["combined_probability"]
                * math.log(
                    max(
                        ticket["combined_odds"],
                        1.01
                    )
                )
            )

            if score_new > score_old:
                best_ticket = ticket

    return best_ticket


def calculate_payout(stake, odds):
    return stake * odds


# ============================================================
# SYSTEMSCHEINE
# ============================================================

def generate_system(rows, k, n):
    """
    Beispiel:
    3 aus 4
    = alle Kombinationen aus 3 Spielen.
    """

    if len(rows) < n:
        return []

    selected = rows[:n]

    combinations_list = list(
        combinations(
            selected,
            k
        )
    )

    systems = []

    for combo in combinations_list:

        probability = 1.0
        odds = 1.0

        for row in combo:

            probability *= row[
                "probability"
            ]

            if row["odds"] is not None:
                odds *= row["odds"]
            else:
                odds = None

        systems.append({
            "legs": combo,
            "probability": probability,
            "odds": odds
        })

    return systems


# ============================================================
# API-STATUS
# ============================================================

def test_api():
    """
    Kleiner API-Test.
    """

    data, error = api_get(
        "/status"
    )

    if error:
        return False, error

    return True, "API-Verbindung funktioniert."


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">⚽ WETT-KI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Fußball 1/X/2 – aktuelle Spiele, Quoten und KI-Analyse</div>',
    unsafe_allow_html=True
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Einstellungen")

    budget = st.number_input(
        "💰 Budget (€)",
        min_value=1.0,
        max_value=10000.0,
        value=20.0,
        step=1.0
    )

    odds_limit = st.slider(
        "Anzahl Spiele mit automatischen Quoten",
        min_value=5,
        max_value=MAX_ODDS_MATCHES,
        value=MAX_ODDS_MATCHES
    )

    st.divider()

    if st.button(
        "🔄 Daten aktualisieren",
        use_container_width=True
    ):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.caption(
        "⚠️ Die Berechnungen sind statistische Einschätzungen "
        "und keine Gewinn- oder Wettgarantie."
    )


# ============================================================
# API TEST
# ============================================================

with st.spinner("🔎 Suche aktuelle Fußballspiele ..."):

    fixtures, fixture_errors = load_upcoming_fixtures()


if fixture_errors:
    with st.expander(
        "⚠️ API-Hinweise"
    ):
        for error in fixture_errors:
            st.write(error)


if fixtures.empty:

    st.error(
        "Es wurden keine kommenden Spiele gefunden."
    )

    st.info(
        "Prüfe deinen API-Key und klicke anschließend auf "
        "„Daten aktualisieren“."
    )

    st.stop()


# ============================================================
# ODDS LIMIT
# ============================================================

# Alle echten Spiele bleiben sichtbar.
# Nur die ersten X bekommen automatisch Quoten.
fixtures_for_odds = fixtures.head(
    odds_limit
)


# ============================================================
# HISTORISCHE DATEN + ANALYSE
# ============================================================

analysis_rows = []

progress = st.progress(
    0,
    text="🤖 KI analysiert Spiele ..."
)

total = len(fixtures_for_odds)

for index, (_, match) in enumerate(
    fixtures_for_odds.iterrows()
):

    league_id = int(
        match["league_id"]
    )

    season = int(
        match["date"].year
    )

    history = load_historical_fixtures(
        league_id,
        season
    )

    result = analyze_match(
        match,
        history
    )

    analysis_rows.append(
        result
    )

    if total > 0:
        progress.progress(
            (index + 1) / total,
            text=f"🤖 Analysiere {index + 1}/{total}"
        )

progress.empty()

analysis = pd.DataFrame(
    analysis_rows
)


# ============================================================
# TABS
# ============================================================

tab_dashboard, tab_games, tab_tickets, tab_odds = st.tabs(
    [
        "🏠 Dashboard",
        "📅 Spiele",
        "🎟️ Scheine",
        "📊 Quoten"
    ]
)


# ============================================================
# DASHBOARD
# ============================================================

with tab_dashboard:

    friday, thursday = next_friday_thursday()

    st.subheader(
        "📅 Kommende Spielwoche"
    )

    st.write(
        f"{friday.strftime('%d.%m.%Y')} – "
        f"{thursday.strftime('%d.%m.%Y')}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "⚽ Echte Spiele",
        len(fixtures)
    )

    c2.metric(
        "🤖 Analysiert",
        len(analysis)
    )

    if not analysis.empty:

        c3.metric(
            "🟢 LOW",
            int(
                (analysis["risk"] == "LOW").sum()
            )
        )

        c4.metric(
            "💎 Value",
            int(
                (
                    analysis["value"].fillna(-1)
                    > 0
                ).sum()
            )
        )

    st.divider()

    st.subheader(
        "🔥 Beste aktuellen Tipps"
    )

    if analysis.empty:

        st.warning(
            "Noch keine Spiele analysiert."
        )

    else:

        display = analysis.copy()

        display = display.sort_values(
            [
                "probability",
                "value"
            ],
            ascending=False
        )

        display = display.head(15)

        for _, row in display.iterrows():

            outcome_text = {
                "1": "1 – Heimsieg",
                "X": "X – Unentschieden",
                "2": "2 – Auswärtssieg"
            }[row["pick"]]

            st.markdown(
                f"""
                <div class="pick-box">
                <b>{row['home_team']} – {row['away_team']}</b><br>
                {row['league']} · {format_date(row['date'])}<br><br>
                <b>KI-Tipp:</b> {outcome_text}<br>
                <b>Wahrscheinlichkeit:</b> {row['probability']:.1%}<br>
                <b>Risiko:</b> {risk_label(row['risk'])}<br>
                <b>Quote:</b> {row['odds'] if row['odds'] else 'keine Quote'}<br>
                <b>Value:</b> {
                    f"{row['value']:.1%}"
                    if row['value'] is not None
                    else "nicht verfügbar"
                }
                </div>
                """,
                unsafe_allow_html=True
            )


# ============================================================
# SPIELE
# ============================================================

with tab_games:

    st.subheader(
        "📅 Alle echten kommenden Spiele"
    )

    st.caption(
        "Es werden ausschließlich Spiele angezeigt, deren "
        "Anstoßzeit aktuell noch in der Zukunft liegt."
    )

    # --------------------------------------------------------
    # Nach Wochentagen
    # --------------------------------------------------------

    all_days = fixtures.copy()

    all_days["weekday"] = all_days[
        "date"
    ].dt.strftime("%A")

    german_days = {
        "Monday": "Montag",
        "Tuesday": "Dienstag",
        "Wednesday": "Mittwoch",
        "Thursday": "Donnerstag",
        "Friday": "Freitag",
        "Saturday": "Samstag",
        "Sunday": "Sonntag"
    }

    all_days["day_de"] = all_days[
        "weekday"
    ].map(german_days)

    ordered_days = [
        "Freitag",
        "Samstag",
        "Sonntag",
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag"
    ]

    for day in ordered_days:

        day_df = all_days[
            all_days["day_de"] == day
        ]

        if day_df.empty:
            continue

        first_date = day_df[
            "date"
        ].iloc[0].strftime("%d.%m.%Y")

        st.markdown(
            f"### 📆 {day}, {first_date}"
        )

        for _, row in day_df.iterrows():

            matching = analysis[
                analysis["fixture_id"]
                == row["fixture_id"]
            ]

            if not matching.empty:

                analyzed_row = matching.iloc[0]

                pick = analyzed_row["pick"]

                probability = (
                    analyzed_row["probability"]
                )

                risk = analyzed_row["risk"]

                odd = analyzed_row["odds"]

                if odd:
                    odds_text = f"{odd:.2f}"
                else:
                    odds_text = "—"

                st.write(
                    f"**{row['date'].strftime('%H:%M')}**  "
                    f"{row['home_team']} – {row['away_team']}  |  "
                    f"KI: **{pick}** "
                    f"({probability:.0%}) | "
                    f"{risk_label(risk)} | "
                    f"Quote: **{odds_text}**"
                )

            else:

                st.write(
                    f"**{row['date'].strftime('%H:%M')}**  "
                    f"{row['home_team']} – {row['away_team']}  |  "
                    "Quoten/Analyse noch nicht geladen"
                )


# ============================================================
# SCHEINE
# ============================================================

with tab_tickets:

    st.subheader(
        "🎟️ KI-Schein-Generator"
    )

    st.write(
        f"Dein Budget: **{budget:.2f} €**"
    )

    st.info(
        "LOW bedeutet geringere statistische Unsicherheit. "
        "HIGH bedeutet höhere Unsicherheit."
    )

    if analysis.empty:

        st.warning(
            "Keine analysierten Spiele verfügbar."
        )

    else:

        # ----------------------------------------------------
        # Budget-Aufteilung
        # ----------------------------------------------------

        st.markdown(
            "### 💰 Empfohlene Budgetaufteilung"
        )

        low_budget = budget * 0.60
        mid_budget = budget * 0.30
        high_budget = budget * 0.10

        b1, b2, b3 = st.columns(3)

        b1.metric(
            "🟢 LOW",
            f"{low_budget:.2f} €"
        )

        b2.metric(
            "🟡 MID",
            f"{mid_budget:.2f} €"
        )

        b3.metric(
            "🔴 HIGH",
            f"{high_budget:.2f} €"
        )

        st.divider()

        # ----------------------------------------------------
        # LOW
        # ----------------------------------------------------

        for profile, stake in [
            ("LOW", low_budget),
            ("MID", mid_budget),
            ("HIGH", high_budget)
        ]:

            st.markdown(
                f"### {risk_label(profile)} Schein"
            )

            ticket = generate_accumulator(
                analysis,
                profile
            )

            if ticket is None:

                st.warning(
                    f"Für {profile} konnte kein sinnvoller "
                    "gemeinsamer Buchmacher-Schein erstellt werden."
                )

                continue

            bookmaker = ticket[
                "bookmaker"
            ]

            combined_probability = ticket[
                "combined_probability"
            ]

            combined_odds = ticket[
                "combined_odds"
            ]

            potential_payout = calculate_payout(
                stake,
                combined_odds
            )

            st.write(
                f"**Buchmacher:** {bookmaker}"
            )

            st.write(
                f"**Kombinierte Quote:** "
                f"{combined_odds:.2f}"
            )

            st.write(
                f"**Modell-Wahrscheinlichkeit:** "
                f"{combined_probability:.2%}"
            )

            st.write(
                f"**Einsatz:** {stake:.2f} €"
            )

            st.write(
                f"**Theoretischer Brutto-Gewinn:** "
                f"{potential_payout:.2f} €"
            )

            for number, row in enumerate(
                ticket["legs"],
                start=1
            ):

                st.write(
                    f"{number}. "
                    f"**{row['home_team']} – "
                    f"{row['away_team']}** | "
                    f"Tipp: **{row['pick']}** | "
                    f"Quote: "
                    f"{row['bookmakers'][bookmaker][row['pick']]:.2f}"
                )

            st.divider()

        # ----------------------------------------------------
        # SYSTEMSCHEINE
        # ----------------------------------------------------

        st.markdown(
            "### 🧩 System-Scheine"
        )

        candidates = select_candidates(
            analysis,
            "MID"
        )

        if len(candidates) >= 4:

            system_options = [
                ("2 aus 3", 2, 3),
                ("2 aus 4", 2, 4),
                ("3 aus 4", 3, 4),
                ("3 aus 5", 3, 5),
            ]

            for name, k, n in system_options:

                if len(candidates) < n:
                    continue

                systems = generate_system(
                    candidates,
                    k,
                    n
                )

                if not systems:
                    continue

                st.write(
                    f"**{name}** – "
                    f"{len(systems)} Kombinationen"
                )

                for system_index, system in enumerate(
                    systems[:5],
                    start=1
                ):

                    names = [
                        f"{r['home_team']}–{r['away_team']} ({r['pick']})"
                        for r in system["legs"]
                    ]

                    st.write(
                        f"{system_index}. "
                        + " | ".join(names)
                    )

        else:

            st.info(
                "Für Systemscheine werden mindestens "
                "4 gute Kandidaten benötigt."
            )


# ============================================================
# QUOTEN
# ============================================================

with tab_odds:

    st.subheader(
        "📊 Aktuelle 1/X/2-Quoten"
    )

    st.caption(
        "Die App verwendet ausschließlich den 1/X/2-Markt."
    )

    if analysis.empty:

        st.warning(
            "Keine Quoten verfügbar."
        )

    else:

        odds_rows = []

        for _, row in analysis.iterrows():

            odds_rows.append({
                "Datum": format_date(row["date"]),
                "Liga": row["league"],
                "Spiel": (
                    f"{row['home_team']} – "
                    f"{row['away_team']}"
                ),
                "1": (
                    f"{row['best_odds_1']:.2f}"
                    if row["best_odds_1"]
                    else "—"
                ),
                "X": (
                    f"{row['best_odds_X']:.2f}"
                    if row["best_odds_X"]
                    else "—"
                ),
                "2": (
                    f"{row['best_odds_2']:.2f}"
                    if row["best_odds_2"]
                    else "—"
                ),
                "KI": row["pick"],
                "KI-Wahrscheinlichkeit": (
                    f"{row['probability']:.1%}"
                ),
                "Risiko": row["risk"]
            })

        odds_df = pd.DataFrame(
            odds_rows
        )

        st.dataframe(
            odds_df,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "⚽ Wett-KI | Nur Fußball 1/X/2 | "
    "Aktuelle zukünftige Spiele | "
    "Statistische Modellierung + Marktquoten"
)

st.caption(
    "⚠️ Keine Gewinn-Garantie. Wettquoten und "
    "Spielinformationen können sich jederzeit ändern."
)
