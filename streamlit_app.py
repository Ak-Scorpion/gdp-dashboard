import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from itertools import combinations


# ============================================================
# ⚽ WETT-KI
# Aktuelle Fußballspiele – nur 1/X/2
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

TIMEZONE = "Europe/Berlin"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues"

# Große Fußballligen
LEAGUES = {
    "eng.1": "Premier League",
    "ger.1": "Bundesliga",
    "esp.1": "La Liga",
    "ita.1": "Serie A",
    "fra.1": "Ligue 1",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "uefa.europa.conf": "Conference League",
}

MAX_GOALS = 8


# ============================================================
# DESIGN
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .subtitle {
        color: #888;
        margin-bottom: 20px;
    }

    .game-card {
        padding: 15px;
        border-radius: 14px;
        background: rgba(128,128,128,0.08);
        margin-bottom: 10px;
    }

    .low {
        padding: 6px 10px;
        border-radius: 8px;
        font-weight: 700;
    }

    .mid {
        padding: 6px 10px;
        border-radius: 8px;
        font-weight: 700;
    }

    .high {
        padding: 6px 10px;
        border-radius: 8px;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# ZEIT
# ============================================================

def now_local():
    return datetime.now(
        ZoneInfo(TIMEZONE)
    )


def next_friday():
    today = now_local().date()

    days = (
        4 - today.weekday()
    ) % 7

    if days == 0:
        days = 7

    return today + timedelta(
        days=days
    )


def week_window():
    friday = next_friday()

    thursday = (
        friday
        + timedelta(days=6)
    )

    return friday, thursday


# ============================================================
# HTTP
# ============================================================

def get_json(url, params=None, timeout=20):

    try:

        response = requests.get(
            url,
            params=params,
            timeout=timeout,
            headers={
                "User-Agent":
                    "Wett-KI/1.0"
            }
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:
        return None


# ============================================================
# ESPN SPIELE
# ============================================================

@st.cache_data(ttl=300)
def load_league_fixtures(
    league,
    start_date,
    end_date
):

    url = (
        f"{ESPN_BASE}/"
        f"{league}/scoreboard"
    )

    params = {
        "dates":
            f"{start_date:%Y%m%d}-"
            f"{end_date:%Y%m%d}"
    }

    data = get_json(
        url,
        params
    )

    if not data:
        return []

    return data.get(
        "events",
        []
    )


def parse_fixture(
    event,
    league,
    league_name
):

    try:

        event_id = str(
            event["id"]
        )

        date_string = event[
            "date"
        ]

        kickoff = pd.to_datetime(
            date_string,
            utc=True
        ).tz_convert(
            TIMEZONE
        )

        competition = event[
            "competitions"
        ][0]

        competitors = competition[
            "competitors"
        ]

        home = None
        away = None

        for team in competitors:

            home_away = team.get(
                "homeAway"
            )

            name = team.get(
                "team",
                {}
            ).get(
                "displayName"
            )

            if home_away == "home":
                home = name

            elif home_away == "away":
                away = name

        if not home or not away:
            return None

        return {
            "fixture_id": event_id,
            "league": league_name,
            "league_code": league,
            "date": kickoff,
            "home_team": home,
            "away_team": away,
            "raw_event": event
        }

    except Exception:
        return None


@st.cache_data(ttl=300)
def load_all_upcoming():

    friday, thursday = week_window()

    rows = []

    for league, league_name in LEAGUES.items():

        events = load_league_fixtures(
            league,
            friday,
            thursday
        )

        for event in events:

            parsed = parse_fixture(
                event,
                league,
                league_name
            )

            if parsed is None:
                continue

            kickoff = parsed[
                "date"
            ]

            current = pd.Timestamp.now(
                tz=TIMEZONE
            )

            # =================================================
            # WICHTIG:
            # Nur wirklich zukünftige Spiele.
            # =================================================

            if kickoff <= current:
                continue

            # Nur Pre-Match-Zustände
            status = (
                event
                .get("competitions", [{}])[0]
                .get("status", {})
                .get("type", {})
                .get("state")
            )

            if status not in [
                "pre",
                None
            ]:
                continue

            rows.append(
                parsed
            )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df = df.drop_duplicates(
        subset=["fixture_id"]
    )

    df = df.sort_values(
        "date"
    ).reset_index(
        drop=True
    )

    return df


# ============================================================
# VERGANGENE SPIELE
# ============================================================

@st.cache_data(ttl=1800)
def load_historical_games(
    league,
    days_back=120
):

    end_date = now_local().date()

    start_date = (
        end_date
        - timedelta(days=days_back)
    )

    events = load_league_fixtures(
        league,
        start_date,
        end_date
    )

    rows = []

    for event in events:

        try:

            competition = event[
                "competitions"
            ][0]

            status = (
                competition
                .get("status", {})
                .get("type", {})
                .get("state")
            )

            if status != "post":
                continue

            competitors = competition[
                "competitors"
            ]

            home = None
            away = None
            home_score = None
            away_score = None

            for team in competitors:

                name = team.get(
                    "team",
                    {}
                ).get(
                    "displayName"
                )

                score = team.get(
                    "score"
                )

                if team.get(
                    "homeAway"
                ) == "home":

                    home = name
                    home_score = score

                else:

                    away = name
                    away_score = score

            if (
                not home
                or not away
                or home_score is None
                or away_score is None
            ):
                continue

            rows.append({
                "date": pd.to_datetime(
                    event["date"],
                    utc=True
                ).tz_convert(
                    TIMEZONE
                ),
                "home_team": home,
                "away_team": away,
                "home_goals": float(
                    home_score
                ),
                "away_goals": float(
                    away_score
                )
            })

        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# ============================================================
# TEAM-FORM
# ============================================================

def team_form(
    history,
    team
):

    if history.empty:
        return {
            "games": 0,
            "gf": 1.35,
            "ga": 1.15,
            "points": 1.35
        }

    home = history[
        history["home_team"] == team
    ].copy()

    away = history[
        history["away_team"] == team
    ].copy()

    rows = []

    for _, match in home.iterrows():

        gf = match[
            "home_goals"
        ]

        ga = match[
            "away_goals"
        ]

        if gf > ga:
            points = 3
        elif gf == ga:
            points = 1
        else:
            points = 0

        rows.append(
            (gf, ga, points)
        )

    for _, match in away.iterrows():

        gf = match[
            "away_goals"
        ]

        ga = match[
            "home_goals"
        ]

        if gf > ga:
            points = 3
        elif gf == ga:
            points = 1
        else:
            points = 0

        rows.append(
            (gf, ga, points)
        )

    if not rows:
        return {
            "games": 0,
            "gf": 1.35,
            "ga": 1.15,
            "points": 1.35
        }

    # Neuere Spiele stärker gewichten
    rows = rows[-12:]

    gf = np.mean(
        [x[0] for x in rows]
    )

    ga = np.mean(
        [x[1] for x in rows]
    )

    points = np.mean(
        [x[2] for x in rows]
    )

    return {
        "games": len(rows),
        "gf": float(gf),
        "ga": float(ga),
        "points": float(points)
    }


# ============================================================
# POISSON
# ============================================================

def poisson(
    lam,
    goals
):

    if lam <= 0:
        return 0.0

    return (
        math.exp(-lam)
        * lam ** goals
        / math.factorial(goals)
    )


def poisson_1x2(
    home_lambda,
    away_lambda
):

    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0

    for home_goals in range(
        MAX_GOALS + 1
    ):

        for away_goals in range(
            MAX_GOALS + 1
        ):

            p = (
                poisson(
                    home_lambda,
                    home_goals
                )
                *
                poisson(
                    away_lambda,
                    away_goals
                )
            )

            if home_goals > away_goals:

                p_home += p

            elif home_goals == away_goals:

                p_draw += p

            else:

                p_away += p

    total = (
        p_home
        + p_draw
        + p_away
    )

    if total <= 0:

        return {
            "1": 0.3333,
            "X": 0.3334,
            "2": 0.3333
        }

    return {
        "1": p_home / total,
        "X": p_draw / total,
        "2": p_away / total
    }


# ============================================================
# ESPN ODDS
# ============================================================

def american_to_decimal(
    value
):

    try:
        value = float(value)
    except Exception:
        return None

    if value == 0:
        return None

    if value > 0:

        return (
            1 + value / 100
        )

    return (
        1 + 100 / abs(value)
    )


def numeric_odd(
    value
):

    if value is None:
        return None

    try:

        value = float(
            str(value)
            .replace(",", ".")
        )

        if value > 1:
            return value

    except Exception:
        pass

    return None


def extract_moneyline(
    odds_item
):

    home = None
    draw = None
    away = None

    home_data = odds_item.get(
        "homeTeamOdds",
        {}
    )

    away_data = odds_item.get(
        "awayTeamOdds",
        {}
    )

    # --------------------------------------------------------
    # Direkte Dezimalquoten
    # --------------------------------------------------------

    for key in [
        "moneyLine",
        "moneyline",
        "odds"
    ]:

        if home is None:

            home = numeric_odd(
                home_data.get(key)
            )

        if away is None:

            away = numeric_odd(
                away_data.get(key)
            )

    # --------------------------------------------------------
    # Amerikanische Quoten
    # --------------------------------------------------------

    if home is None:

        home_raw = (
            home_data.get(
                "moneyLine"
            )
        )

        home = american_to_decimal(
            home_raw
        )

    if away is None:

        away_raw = (
            away_data.get(
                "moneyLine"
            )
        )

        away = american_to_decimal(
            away_raw
        )

    # --------------------------------------------------------
    # Draw
    # --------------------------------------------------------

    draw_data = odds_item.get(
        "drawOdds"
    )

    if isinstance(
        draw_data,
        dict
    ):

        draw = numeric_odd(
            draw_data.get(
                "moneyLine"
            )
        )

        if draw is None:

            draw = american_to_decimal(
                draw_data.get(
                    "moneyLine"
                )
            )

    if draw is None:

        draw = numeric_odd(
            odds_item.get(
                "drawMoneyLine"
            )
        )

    return {
        "1": home,
        "X": draw,
        "2": away
    }


@st.cache_data(ttl=300)
def load_event_odds(
    league,
    event_id
):

    url = (
        f"{ESPN_CORE}/"
        f"{league}/events/"
        f"{event_id}/competitions/"
        f"{event_id}/odds"
    )

    data = get_json(
        url
    )

    if not data:
        return {}

    items = data.get(
        "items",
        []
    )

    result = {}

    for item in items:

        provider = item.get(
            "provider",
            {}
        )

        bookmaker = provider.get(
            "name"
        )

        if not bookmaker:
            bookmaker = "ESPN"

        odds = extract_moneyline(
            item
        )

        if any(
            x is not None
            for x in odds.values()
        ):

            result[bookmaker] = odds

    return result


# ============================================================
# BESTE QUOTEN
# ============================================================

def best_odds(
    bookmakers
):

    best = {
        "1": None,
        "X": None,
        "2": None
    }

    source = {
        "1": None,
        "X": None,
        "2": None
    }

    for bookmaker, odds in bookmakers.items():

        for outcome in [
            "1",
            "X",
            "2"
        ]:

            value = odds.get(
                outcome
            )

            if value is None:
                continue

            if (
                best[outcome]
                is None
                or value
                > best[outcome]
            ):

                best[outcome] = value
                source[outcome] = bookmaker

    return best, source


# ============================================================
# MARKT-WAHRSCHEINLICHKEIT
# ============================================================

def market_probabilities(
    odds
):

    inverse = {}

    for outcome in [
        "1",
        "X",
        "2"
    ]:

        odd = odds.get(
            outcome
        )

        if odd is not None and odd > 1:

            inverse[outcome] = (
                1 / odd
            )

        else:

            inverse[outcome] = 0

    total = sum(
        inverse.values()
    )

    if total <= 0:

        return {
            "1": None,
            "X": None,
            "2": None
        }

    return {
        k: v / total
        for k, v
        in inverse.items()
    }


# ============================================================
# SPIEL ANALYSE
# ============================================================

def analyze_game(
    row,
    history
):

    home = row[
        "home_team"
    ]

    away = row[
        "away_team"
    ]

    home_form = team_form(
        history,
        home
    )

    away_form = team_form(
        history,
        away
    )

    # --------------------------------------------------------
    # Erwartete Tore
    # --------------------------------------------------------

    home_lambda = (
        0.55
        * home_form["gf"]
        + 0.25
        * away_form["ga"]
        + 0.20
        * 1.35
    )

    away_lambda = (
        0.55
        * away_form["gf"]
        + 0.25
        * home_form["ga"]
        + 0.20
        * 1.10
    )

    # Heimvorteil
    home_lambda *= 1.08

    home_lambda = max(
        0.20,
        min(
            home_lambda,
            4.5
        )
    )

    away_lambda = max(
        0.20,
        min(
            away_lambda,
            4.0
        )
    )

    model = poisson_1x2(
        home_lambda,
        away_lambda
    )

    # --------------------------------------------------------
    # Quoten
    # --------------------------------------------------------

    bookmakers = load_event_odds(
        row["league_code"],
        row["fixture_id"]
    )

    best, bookmaker_source = best_odds(
        bookmakers
    )

    market = market_probabilities(
        best
    )

    # --------------------------------------------------------
    # Modell + Markt
    # --------------------------------------------------------

    final = {}

    for outcome in [
        "1",
        "X",
        "2"
    ]:

        model_p = model[
            outcome
        ]

        market_p = market[
            outcome
        ]

        if market_p is None:

            final[outcome] = model_p

        else:

            final[outcome] = (
                0.70 * model_p
                + 0.30 * market_p
            )

    total = sum(
        final.values()
    )

    final = {
        k: v / total
        for k, v
        in final.items()
    }

    pick = max(
        final,
        key=final.get
    )

    probability = final[
        pick
    ]

    fair_odds = (
        1 / probability
    )

    actual_odds = best.get(
        pick
    )

    value = None

    if actual_odds is not None:

        value = (
            probability
            * actual_odds
            - 1
        )

    # --------------------------------------------------------
    # Risiko
    # --------------------------------------------------------

    sorted_probs = sorted(
        final.values(),
        reverse=True
    )

    top = sorted_probs[0]
    second = sorted_probs[1]

    gap = top - second

    if (
        top >= 0.62
        and gap >= 0.18
    ):

        risk = "LOW"

    elif (
        top >= 0.52
        and gap >= 0.10
    ):

        risk = "MID"

    else:

        risk = "HIGH"

    return {
        **row,
        "p1": final["1"],
        "px": final["X"],
        "p2": final["2"],
        "pick": pick,
        "probability": probability,
        "fair_odds": fair_odds,
        "odds": actual_odds,
        "value": value,
        "risk": risk,
        "bookmakers": bookmakers,
        "bookmaker": bookmaker_source.get(
            pick
        ),
        "home_lambda": home_lambda,
        "away_lambda": away_lambda,
        "home_games": home_form[
            "games"
        ],
        "away_games": away_form[
            "games"
        ]
    }


# ============================================================
# RISIKO TEXT
# ============================================================

def risk_text(
    risk
):

    if risk == "LOW":
        return "🟢 LOW"

    if risk == "MID":
        return "🟡 MID"

    return "🔴 HIGH"


# ============================================================
# SCHEIN-KANDIDATEN
# ============================================================

def candidates(
    analysis,
    profile
):

    if analysis.empty:
        return analysis

    df = analysis.copy()

    if profile == "LOW":

        df = df[
            df["probability"]
            >= 0.58
        ]

    elif profile == "MID":

        df = df[
            df["probability"]
            >= 0.50
        ]

    else:

        df = df[
            df["probability"]
            >= 0.43
        ]

    # Keine Spiele ohne Quote
    df = df[
        df["odds"].notna()
    ]

    if df.empty:
        return df

    df["score"] = (
        df["probability"] * 100
        +
        df["value"].fillna(
            -0.20
        ) * 25
    )

    return df.sort_values(
        "score",
        ascending=False
    ).head(10)


# ============================================================
# AKKUMULATOR
# ============================================================

def generate_ticket(
    analysis,
    profile
):

    df = candidates(
        analysis,
        profile
    )

    if df.empty:
        return None

    if profile == "LOW":
        max_legs = 3

    elif profile == "MID":
        max_legs = 4

    else:
        max_legs = 5

    # --------------------------------------------------------
    # Echter Kombischein:
    # gleicher Buchmacher
    # --------------------------------------------------------

    bookmaker_games = {}

    for _, row in df.iterrows():

        bookmakers = row[
            "bookmakers"
        ]

        for bookmaker, odds in bookmakers.items():

            if row["pick"] not in odds:
                continue

            odd = odds[
                row["pick"]
            ]

            if odd is None:
                continue

            bookmaker_games.setdefault(
                bookmaker,
                []
            ).append(
                row
            )

    if not bookmaker_games:
        return None

    best_ticket = None

    for bookmaker, games in bookmaker_games.items():

        unique = {}

        for row in games:

            unique[
                row["fixture_id"]
            ] = row

        games = list(
            unique.values()
        )

        games = sorted(
            games,
            key=lambda x:
                x["probability"],
            reverse=True
        )

        games = games[
            :max_legs
        ]

        if len(games) < 2:
            continue

        combined_probability = 1.0
        combined_odds = 1.0

        for game in games:

            combined_probability *= (
                game["probability"]
            )

            combined_odds *= (
                game["bookmakers"]
                [bookmaker]
                [game["pick"]]
            )

        ticket = {
            "profile": profile,
            "bookmaker": bookmaker,
            "games": games,
            "probability":
                combined_probability,
            "odds":
                combined_odds
        }

        if best_ticket is None:

            best_ticket = ticket

        else:

            old_score = (
                best_ticket["probability"]
                * math.log(
                    max(
                        best_ticket["odds"],
                        1.01
                    )
                )
            )

            new_score = (
                ticket["probability"]
                * math.log(
                    max(
                        ticket["odds"],
                        1.01
                    )
                )
            )

            if new_score > old_score:

                best_ticket = ticket

    return best_ticket


# ============================================================
# SYSTEMSCHEIN
# ============================================================

def system_combinations(
    analysis,
    n,
    k
):

    df = candidates(
        analysis,
        "MID"
    )

    if len(df) < n:
        return []

    selected = list(
        df.head(n)
        .to_dict("records")
    )

    result = []

    for combo in combinations(
        selected,
        k
    ):

        probability = 1.0
        odds = 1.0

        valid = True

        for game in combo:

            probability *= (
                game["probability"]
            )

            if game["odds"] is None:

                valid = False
                break

            odds *= game[
                "odds"
            ]

        if valid:

            result.append({
                "games": combo,
                "probability":
                    probability,
                "odds":
                    odds
            })

    return result


# ============================================================
# ANALYSE LADEN
# ============================================================

def create_analysis(
    fixtures
):

    results = []

    progress = st.progress(
        0,
        text="🤖 KI analysiert die aktuellen Spiele ..."
    )

    total = len(fixtures)

    for index, (
        _,
        row
    ) in enumerate(
        fixtures.iterrows()
    ):

        history = load_historical_games(
            row["league_code"]
        )

        result = analyze_game(
            row,
            history
        )

        results.append(
            result
        )

        progress.progress(
            (index + 1) / total,
            text=(
                f"🤖 Analyse "
                f"{index + 1}/{total}"
            )
        )

    progress.empty()

    if not results:

        return pd.DataFrame()

    return pd.DataFrame(
        results
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">⚽ WETT-KI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Aktuelle Fußballspiele · 1/X/2 · KI-Analyse · Quoten'
    '</div>',
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

    st.divider()

    if st.button(
        "🔄 AKTUELLE DATEN LADEN",
        use_container_width=True
    ):

        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.success(
        "✅ Keine API-Football-Verbindung nötig"
    )

    st.caption(
        "Die Spielpläne werden direkt aus "
        "aktuellen ESPN-Sportdaten geladen."
    )

    st.caption(
        "⚠️ Statistische Analyse – keine "
        "Gewinngarantie."
    )


# ============================================================
# SPIELE LADEN
# ============================================================

with st.spinner(
    "⚽ Suche echte kommende Spiele ..."
):

    fixtures = load_all_upcoming()


if fixtures.empty:

    st.error(
        "Es wurden keine kommenden Spiele "
        "für die ausgewählten Wettbewerbe gefunden."
    )

    st.info(
        "Klicke auf „AKTUELLE DATEN LADEN“ "
        "und versuche es erneut."
    )

    st.stop()


# ============================================================
# ANALYSE
# ============================================================

analysis = create_analysis(
    fixtures
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

    friday, thursday = (
        week_window()
    )

    st.subheader(
        "📅 Aktuelle Spielwoche"
    )

    st.write(
        f"{friday.strftime('%d.%m.%Y')}"
        " – "
        f"{thursday.strftime('%d.%m.%Y')}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "⚽ Spiele",
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
                (
                    analysis["risk"]
                    == "LOW"
                ).sum()
            )
        )

        c4.metric(
            "💎 Value",
            int(
                (
                    analysis["value"]
                    .fillna(-1)
                    > 0
                ).sum()
            )
        )

    st.divider()

    st.subheader(
        "🔥 Stärkste KI-Tipps"
    )

    if analysis.empty:

        st.warning(
            "Keine Analyse verfügbar."
        )

    else:

        best = analysis.sort_values(
            "probability",
            ascending=False
        ).head(15)

        for _, row in best.iterrows():

            pick_name = {
                "1": "1 – Heimsieg",
                "X": "X – Unentschieden",
                "2": "2 – Auswärtssieg"
            }[
                row["pick"]
            ]

            odd_text = (
                f"{row['odds']:.2f}"
                if pd.notna(
                    row["odds"]
                )
                else "keine Quote"
            )

            value_text = (
                f"{row['value']:.1%}"
                if pd.notna(
                    row["value"]
                )
                else "—"
            )

            st.markdown(
                f"""
                <div class="game-card">

                <b>
                {row['home_team']}
                –
                {row['away_team']}
                </b>

                <br>

                {row['league']}
                ·
                {row['date'].strftime('%d.%m.%Y %H:%M')}

                <br><br>

                <b>KI-Tipp:</b>
                {pick_name}

                <br>

                <b>Wahrscheinlichkeit:</b>
                {row['probability']:.1%}

                <br>

                <b>Risiko:</b>
                {risk_text(row['risk'])}

                <br>

                <b>Quote:</b>
                {odd_text}

                <br>

                <b>Value:</b>
                {value_text}

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
        "Es werden keine Spiele aus der Vergangenheit "
        "für die Wettliste verwendet."
    )

    games = fixtures.copy()

    games["weekday"] = games[
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

    games["day_de"] = games[
        "weekday"
    ].map(
        german_days
    )

    ordered = [
        "Freitag",
        "Samstag",
        "Sonntag",
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag"
    ]

    for day in ordered:

        day_games = games[
            games["day_de"] == day
        ]

        if day_games.empty:
            continue

        date_text = (
            day_games["date"]
            .iloc[0]
            .strftime(
                "%d.%m.%Y"
            )
        )

        st.markdown(
            f"### 📆 {day}, {date_text}"
        )

        for _, game in day_games.iterrows():

            match_analysis = analysis[
                analysis[
                    "fixture_id"
                ]
                ==
                game[
                    "fixture_id"
                ]
            ]

            if match_analysis.empty:

                st.write(
                    f"**{game['date'].strftime('%H:%M')}** "
                    f"{game['home_team']} – "
                    f"{game['away_team']}"
                )

            else:

                r = match_analysis.iloc[0]

                odd = (
                    f"{r['odds']:.2f}"
                    if pd.notna(
                        r["odds"]
                    )
                    else "—"
                )

                st.write(
                    f"**{game['date'].strftime('%H:%M')}** "
                    f"**{game['home_team']} – "
                    f"{game['away_team']}** "
                    f"| KI: **{r['pick']}** "
                    f"| {r['probability']:.0%} "
                    f"| {risk_text(r['risk'])} "
                    f"| Quote: **{odd}**"
                )


# ============================================================
# SCHEINE
# ============================================================

with tab_tickets:

    st.subheader(
        "🎟️ KI-Schein-Generator"
    )

    st.write(
        f"Budget: **{budget:.2f} €**"
    )

    st.info(
        "LOW = geringere statistische Unsicherheit. "
        "HIGH = höhere Unsicherheit."
    )

    # --------------------------------------------------------
    # BUDGET
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 3 SCHEINE
    # --------------------------------------------------------

    for profile, stake in [
        ("LOW", low_budget),
        ("MID", mid_budget),
        ("HIGH", high_budget)
    ]:

        st.markdown(
            f"### {risk_text(profile)} Schein"
        )

        ticket = generate_ticket(
            analysis,
            profile
        )

        if ticket is None:

            st.warning(
                "Für dieses Risikoprofil "
                "konnte aktuell kein geeigneter "
                "Kombischein erstellt werden."
            )

            continue

        combined_odds = ticket[
            "odds"
        ]

        probability = ticket[
            "probability"
        ]

        payout = (
            stake
            * combined_odds
        )

        st.write(
            f"**Buchmacher:** "
            f"{ticket['bookmaker']}"
        )

        st.write(
            f"**Kombinierte Quote:** "
            f"{combined_odds:.2f}"
        )

        st.write(
            f"**Modell-Wahrscheinlichkeit:** "
            f"{probability:.2%}"
        )

        st.write(
            f"**Einsatz:** "
            f"{stake:.2f} €"
        )

        st.write(
            f"**Mögliche Auszahlung laut Quote:** "
            f"{payout:.2f} €"
        )

        st.write("**Tipps:**")

        for index, game in enumerate(
            ticket["games"],
            start=1
        ):

            odd = game[
                "bookmakers"
            ][
                ticket["bookmaker"]
            ][
                game["pick"]
            ]

            st.write(
                f"{index}. "
                f"{game['home_team']} – "
                f"{game['away_team']} "
                f"→ **{game['pick']}** "
                f"@ {odd:.2f}"
            )

        st.divider()

    # --------------------------------------------------------
    # SYSTEMSCHEINE
    # --------------------------------------------------------

    st.markdown(
        "### 🧩 Systemscheine"
    )

    st.caption(
        "Beispiele: 2 aus 3, 2 aus 4, 3 aus 4."
    )

    system_list = [
        ("2 aus 3", 3, 2),
        ("2 aus 4", 4, 2),
        ("3 aus 4", 4, 3),
        ("3 aus 5", 5, 3)
    ]

    for name, n, k in system_list:

        systems = system_combinations(
            analysis,
            n,
            k
        )

        if not systems:
            continue

        st.write(
            f"**{name}** "
            f"→ {len(systems)} Kombinationen"
        )

        for number, system in enumerate(
            systems[:5],
            start=1
        ):

            names = []

            for game in system[
                "games"
            ]:

                names.append(
                    f"{game['home_team']} – "
                    f"{game['away_team']} "
                    f"({game['pick']})"
                )

            st.write(
                f"{number}. "
                + " | ".join(names)
            )


# ============================================================
# QUOTEN
# ============================================================

with tab_odds:

    st.subheader(
        "📊 Aktuelle 1/X/2-Quoten"
    )

    st.caption(
        "Nur 1/X/2 – keine Over/Under-, "
        "BTTS- oder Handicap-Wetten."
    )

    if analysis.empty:

        st.warning(
            "Keine Quotendaten verfügbar."
        )

    else:

        rows = []

        for _, row in analysis.iterrows():

            rows.append({
                "Datum":
                    row["date"].strftime(
                        "%d.%m.%Y %H:%M"
                    ),

                "Liga":
                    row["league"],

                "Spiel":
                    f"{row['home_team']} – "
                    f"{row['away_team']}",

                "1":
                    (
                        f"{row['bookmakers'].get(
                            row['bookmaker'], {}
                        ).get('1'):.2f}"
                        if row["bookmaker"]
                        and row["bookmakers"].get(
                            row["bookmaker"], {}
                        ).get("1")
                        else "—"
                    ),

                "X":
                    (
                        f"{row['bookmakers'].get(
                            row['bookmaker'], {}
                        ).get('X'):.2f}"
                        if row["bookmaker"]
                        and row["bookmakers"].get(
                            row["bookmaker"], {}
                        ).get("X")
                        else "—"
                    ),

                "2":
                    (
                        f"{row['bookmakers'].get(
                            row['bookmaker'], {}
                        ).get('2'):.2f}"
                        if row["bookmaker"]
                        and row["bookmakers"].get(
                            row["bookmaker"], {}
                        ).get("2")
                        else "—"
                    ),

                "KI":
                    row["pick"],

                "KI %":
                    f"{row['probability']:.1%}",

                "Risiko":
                    row["risk"],

                "Buchmacher":
                    row["bookmaker"]
                    if row["bookmaker"]
                    else "—"
            })

        odds_df = pd.DataFrame(
            rows
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
    "⚽ Wett-KI | Aktuelle zukünftige Spiele | "
    "Nur 1/X/2 | Statistik + Marktquoten"
)

st.caption(
    "⚠️ Quoten können sich ändern. "
    "Die KI kann keine Gewinne garantieren."
    )
