import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
from datetime import datetime, timedelta, timezone
from itertools import combinations
from collections import defaultdict


# ============================================================
# WETT-KI
# Aktuelle Fußballspiele über ESPN Public API
# Kein API-Football-Key notwendig
# ============================================================

st.set_page_config(
    page_title="WETT-KI",
    page_icon="⚽",
    layout="wide"
)


# ============================================================
# KONFIGURATION
# ============================================================

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LEAGUES = {
    "Premier League": "eng.1",
    "Bundesliga": "ger.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Conference League": "uefa.europa.conf",
}

REQUEST_TIMEOUT = 20


# ============================================================
# SESSION STATE
# ============================================================

if "fixtures" not in st.session_state:
    st.session_state.fixtures = pd.DataFrame()

if "last_update" not in st.session_state:
    st.session_state.last_update = None

if "api_errors" not in st.session_state:
    st.session_state.api_errors = []


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def parse_datetime(value):
    """
    ESPN liefert normalerweise ISO-Zeitstempel.
    """
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except Exception:
        return None


def american_to_decimal(value):
    """
    Wandelt amerikanische Quoten in Dezimalquoten um.
    Beispiel:
    +150 -> 2.50
    -150 -> 1.67
    """

    if value is None:
        return None

    try:
        value = float(str(value).replace("+", ""))

        if value > 0:
            return round(1 + value / 100, 2)

        if value < 0:
            return round(1 + 100 / abs(value), 2)

    except Exception:
        return None

    return None


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


# ============================================================
# ESPN SCOREBOARD
# ============================================================

def get_scoreboard(league_code, date_string):
    """
    Holt ESPN-Daten für EINEN einzelnen Tag.

    Beispiel:
    20260912
    """

    url = f"{ESPN_BASE}/{league_code}/scoreboard"

    params = {
        "dates": date_string,
        "limit": 500,
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        return data, None

    except requests.exceptions.RequestException as e:
        return None, f"HTTP-Fehler: {e}"

    except Exception as e:
        return None, f"Fehler: {e}"


# ============================================================
# SPIELE EINES TAGES
# ============================================================

def parse_events(data, league_name, league_code):
    rows = []

    if not data:
        return rows

    events = data.get("events", [])

    for event in events:

        try:
            event_id = str(event.get("id", ""))

            event_date = parse_datetime(
                event.get("date")
            )

            if event_date is None:
                continue

            competition_list = event.get(
                "competitions",
                []
            )

            if not competition_list:
                continue

            competition = competition_list[0]

            competitors = competition.get(
                "competitors",
                []
            )

            home = None
            away = None

            for team in competitors:

                home_away = team.get(
                    "homeAway"
                )

                if home_away == "home":
                    home = team

                elif home_away == "away":
                    away = team

            if not home or not away:
                continue

            home_team = (
                home.get("team", {})
                .get("displayName", "Unbekannt")
            )

            away_team = (
                away.get("team", {})
                .get("displayName", "Unbekannt")
            )

            status = (
                event
                .get("status", {})
                .get("type", {})
            )

            status_state = status.get(
                "state",
                ""
            )

            status_detail = status.get(
                "detail",
                ""
            )

            completed = status.get(
                "completed",
                False
            )

            # Nur zukünftige Spiele.
            if completed:
                continue

            if event_date <= now_utc():
                continue

            rows.append({
                "event_id": event_id,
                "league": league_name,
                "league_code": league_code,
                "datetime_utc": event_date,
                "home": home_team,
                "away": away_team,
                "status": status_state,
                "status_detail": status_detail,
            })

        except Exception:
            continue

    return rows


# ============================================================
# AKTUELLE SPIELE
# ============================================================

def load_upcoming_fixtures():

    all_rows = []
    errors = []

    today = now_utc().date()

    # Freitag bis Donnerstag
    weekday = today.weekday()

    # Python:
    # Montag = 0
    # Dienstag = 1
    # Mittwoch = 2
    # Donnerstag = 3
    # Freitag = 4
    # Samstag = 5
    # Sonntag = 6

    days_until_friday = (
        4 - weekday
    ) % 7

    start_date = today + timedelta(
        days=days_until_friday
    )

    # Falls heute Freitag ist:
    # heutige Spiele sollen NICHT verloren gehen.
    if weekday == 4:
        start_date = today

    end_date = start_date + timedelta(
        days=6
    )

    # WICHTIG:
    # Wir fragen jeden einzelnen Tag ab.
    dates = []

    current = start_date

    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)

    for league_name, league_code in LEAGUES.items():

        for date_value in dates:

            date_string = date_value.strftime(
                "%Y%m%d"
            )

            data, error = get_scoreboard(
                league_code,
                date_string
            )

            if error:
                errors.append(
                    f"{league_name} {date_string}: {error}"
                )
                continue

            rows = parse_events(
                data,
                league_name,
                league_code
            )

            all_rows.extend(rows)

    df = pd.DataFrame(all_rows)

    if df.empty:
        return df, errors

    # Doppelte Spiele entfernen
    df = df.drop_duplicates(
        subset=["event_id"]
    )

    # Nach Anstoß sortieren
    df = df.sort_values(
        "datetime_utc"
    ).reset_index(drop=True)

    return df, errors


# ============================================================
# FORM-DATEN
# ============================================================

def poisson_probability(lam, goals):
    try:
        return (
            math.exp(-lam)
            * lam ** goals
            / math.factorial(goals)
        )
    except Exception:
        return 0


def match_probabilities(
    home_strength=1.55,
    away_strength=1.15
):
    """
    Einfaches Poisson-Modell.
    """

    home_win = 0
    draw = 0
    away_win = 0

    max_goals = 8

    for hg in range(max_goals + 1):

        for ag in range(max_goals + 1):

            p_home = poisson_probability(
                home_strength,
                hg
            )

            p_away = poisson_probability(
                away_strength,
                ag
            )

            probability = (
                p_home * p_away
            )

            if hg > ag:
                home_win += probability

            elif hg == ag:
                draw += probability

            else:
                away_win += probability

    total = (
        home_win
        + draw
        + away_win
    )

    if total <= 0:
        return {
            "1": 0.333,
            "X": 0.334,
            "2": 0.333
        }

    return {
        "1": home_win / total,
        "X": draw / total,
        "2": away_win / total
    }


# ============================================================
# QUOTEN
# ============================================================

def extract_odds_from_event(event):

    result = {
        "bookmaker": None,
        "odd_1": None,
        "odd_x": None,
        "odd_2": None,
    }

    try:

        competitions = event.get(
            "competitions",
            []
        )

        if not competitions:
            return result

        competition = competitions[0]

        odds_list = competition.get(
            "odds",
            []
        )

        if not odds_list:
            return result

        # Erstes verfügbares Odds-Angebot
        odds = odds_list[0]

        provider = odds.get(
            "provider",
            {}
        )

        result["bookmaker"] = provider.get(
            "name"
        )

        # ESPN kann verschiedene Strukturen liefern.
        # Wir versuchen mehrere Varianten.

        home_moneyline = odds.get(
            "homeTeamOdds",
            {}
        )

        away_moneyline = odds.get(
            "awayTeamOdds",
            {}
        )

        draw_moneyline = odds.get(
            "drawOdds"
        )

        if isinstance(draw_moneyline, dict):
            draw_moneyline = (
                draw_moneyline.get("moneyLine")
                or draw_moneyline.get("value")
            )

        home_value = None
        away_value = None
        draw_value = None

        if isinstance(
            home_moneyline,
            dict
        ):
            home_value = (
                home_moneyline.get("moneyLine")
                or home_moneyline.get("value")
            )

        if isinstance(
            away_moneyline,
            dict
        ):
            away_value = (
                away_moneyline.get("moneyLine")
                or away_moneyline.get("value")
            )

        if draw_moneyline is None:
            draw_value = (
                odds.get("drawMoneyLine")
            )

        else:
            draw_value = draw_moneyline

        result["odd_1"] = (
            american_to_decimal(home_value)
        )

        result["odd_x"] = (
            american_to_decimal(draw_value)
        )

        result["odd_2"] = (
            american_to_decimal(away_value)
        )

    except Exception:
        pass

    return result


def get_event_odds(league_code, event_id):

    # ESPN Core API
    url = (
        "https://sports.core.api.espn.com/"
        f"v2/sports/soccer/leagues/"
        f"{league_code}/events/"
        f"{event_id}/competitions/"
        f"{event_id}/odds"
    )

    try:

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return {
                "bookmaker": None,
                "odd_1": None,
                "odd_x": None,
                "odd_2": None,
            }

        data = response.json()

        items = data.get(
            "items",
            []
        )

        if not items:
            return {
                "bookmaker": None,
                "odd_1": None,
                "odd_x": None,
                "odd_2": None,
            }

        odds = items[0]

        provider = odds.get(
            "provider",
            {}
        )

        bookmaker = provider.get(
            "name"
        )

        home_value = None
        away_value = None
        draw_value = None

        # Verschiedene ESPN-Strukturen abfangen

        home = odds.get(
            "homeTeamOdds",
            {}
        )

        away = odds.get(
            "awayTeamOdds",
            {}
        )

        if isinstance(home, dict):
            home_value = (
                home.get("moneyLine")
                or home.get("value")
                or home.get("american")
            )

        if isinstance(away, dict):
            away_value = (
                away.get("moneyLine")
                or away.get("value")
                or away.get("american")
            )

        draw = odds.get(
            "drawOdds"
        )

        if isinstance(draw, dict):
            draw_value = (
                draw.get("moneyLine")
                or draw.get("value")
                or draw.get("american")
            )

        elif draw is not None:
            draw_value = draw

        if draw_value is None:
            draw_value = odds.get(
                "drawMoneyLine"
            )

        return {
            "bookmaker": bookmaker,
            "odd_1": american_to_decimal(
                home_value
            ),
            "odd_x": american_to_decimal(
                draw_value
            ),
            "odd_2": american_to_decimal(
                away_value
            ),
        }

    except Exception:
        return {
            "bookmaker": None,
            "odd_1": None,
            "odd_x": None,
            "odd_2": None,
        }


# ============================================================
# ANALYSE
# ============================================================

def analyze_match(row):

    # Basis-Poisson
    model = match_probabilities()

    p1 = model["1"]
    px = model["X"]
    p2 = model["2"]

    probabilities = {
        "1": p1,
        "X": px,
        "2": p2
    }

    prediction = max(
        probabilities,
        key=probabilities.get
    )

    top_probability = probabilities[
        prediction
    ]

    sorted_probs = sorted(
        probabilities.values(),
        reverse=True
    )

    gap = (
        sorted_probs[0]
        - sorted_probs[1]
    )

    # Risiko
    if (
        top_probability >= 0.62
        and gap >= 0.18
    ):
        risk = "LOW"

    elif (
        top_probability >= 0.52
        and gap >= 0.10
    ):
        risk = "MID"

    else:
        risk = "HIGH"

    return {
        "prediction": prediction,
        "p_1": round(p1, 4),
        "p_x": round(px, 4),
        "p_2": round(p2, 4),
        "confidence": round(
            top_probability,
            4
        ),
        "risk": risk,
    }


# ============================================================
# DATEN LADEN
# ============================================================

def refresh_data():

    with st.spinner(
        "Aktuelle Fußballspiele werden geladen..."
    ):

        fixtures, errors = (
            load_upcoming_fixtures()
        )

        if fixtures.empty:
            st.session_state.fixtures = (
                pd.DataFrame()
            )

        else:

            analyses = []

            for _, row in fixtures.iterrows():

                analysis = analyze_match(
                    row
                )

                analyses.append(
                    analysis
                )

            analysis_df = pd.DataFrame(
                analyses
            )

            fixtures = pd.concat(
                [
                    fixtures.reset_index(
                        drop=True
                    ),
                    analysis_df
                ],
                axis=1
            )

            # Quoten laden
            bookmakers = []
            odds_1 = []
            odds_x = []
            odds_2 = []

            for _, row in fixtures.iterrows():

                odds = get_event_odds(
                    row["league_code"],
                    row["event_id"]
                )

                bookmakers.append(
                    odds["bookmaker"]
                )

                odds_1.append(
                    odds["odd_1"]
                )

                odds_x.append(
                    odds["odd_x"]
                )

                odds_2.append(
                    odds["odd_2"]
                )

            fixtures["bookmaker"] = bookmakers
            fixtures["odd_1"] = odds_1
            fixtures["odd_x"] = odds_x
            fixtures["odd_2"] = odds_2

            # Anzeigezeit Deutschland
            fixtures["datetime_local"] = (
                fixtures["datetime_utc"]
                .dt.tz_convert(
                    "Europe/Berlin"
                )
            )

        st.session_state.fixtures = fixtures
        st.session_state.api_errors = errors
        st.session_state.last_update = (
            datetime.now()
        )


# ============================================================
# TITEL
# ============================================================

st.title("⚽ WETT-KI")

st.caption(
    "Aktuelle Fußballspiele · 1/X/2 · KI-Analyse · Quoten"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "⚙️ Einstellungen"
)

selected_leagues = st.sidebar.multiselect(
    "Wettbewerbe",
    list(LEAGUES.keys()),
    default=list(LEAGUES.keys())
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
    refresh_data()


# ============================================================
# DATEN
# ============================================================

df = st.session_state.fixtures

if not df.empty:

    df = df[
        df["league"].isin(
            selected_leagues
        )
    ].copy()


# ============================================================
# LEER
# ============================================================

if df.empty:

    st.error(
        "Es wurden keine kommenden Spiele "
        "für die ausgewählten Wettbewerbe gefunden."
    )

    st.info(
        "Klicke auf „AKTUELLE DATEN LADEN“ "
        "und versuche es erneut."
    )

    st.markdown(
        """
        ### 🔎 Datenquelle

        Die App verwendet die öffentliche
        ESPN-Fußballschnittstelle.

        Es werden ausschließlich Spiele angezeigt,
        deren Anstoßzeit noch in der Zukunft liegt.

        **Keine alten Beispieldaten werden als
        kommende Spiele verwendet.**
        """
    )

    if st.session_state.api_errors:

        with st.expander(
            "🔧 Technische Abruffehler anzeigen"
        ):

            for error in (
                st.session_state.api_errors
            ):
                st.write(error)

    st.stop()


# ============================================================
# ÜBERSICHT
# ============================================================

st.success(
    f"{len(df)} aktuelle kommende Spiele gefunden."
)

if st.session_state.last_update:

    st.caption(
        "Letzte Aktualisierung: "
        + st.session_state.last_update.strftime(
            "%d.%m.%Y %H:%M:%S"
        )
    )


# ============================================================
# TABS
# ============================================================

tab_dashboard, tab_spiele, tab_scheine, tab_quoten = (
    st.tabs(
        [
            "🏠 Dashboard",
            "📅 Spiele",
            "🎟️ Scheine",
            "📊 Quoten",
        ]
    )
)


# ============================================================
# DASHBOARD
# ============================================================

with tab_dashboard:

    st.subheader(
        "🔥 Beste aktuelle Tipps"
    )

    dashboard = df.copy()

    dashboard["confidence_pct"] = (
        dashboard["confidence"] * 100
    ).round(1)

    dashboard = dashboard.sort_values(
        [
            "risk",
            "confidence"
        ],
        ascending=[
            True,
            False
        ]
    )

    display_columns = [
        "datetime_local",
        "league",
        "home",
        "away",
        "prediction",
        "confidence_pct",
        "risk",
        "odd_1",
        "odd_x",
        "odd_2",
    ]

    dashboard_view = dashboard[
        display_columns
    ].copy()

    dashboard_view.columns = [
        "Anstoß",
        "Liga",
        "Heim",
        "Auswärts",
        "Tipp",
        "Sicherheit %",
        "Risiko",
        "Quote 1",
        "Quote X",
        "Quote 2",
    ]

    st.dataframe(
        dashboard_view,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# SPIELE
# ============================================================

with tab_spiele:

    st.subheader(
        "📅 Kommende Spiele"
    )

    df["datum"] = (
        df["datetime_local"]
        .dt.date
    )

    dates = sorted(
        df["datum"].unique()
    )

    for date_value in dates:

        day_df = df[
            df["datum"] == date_value
        ].copy()

        day_df = day_df.sort_values(
            "datetime_local"
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

        weekday = weekday_names[
            date_value.weekday()
        ]

        st.markdown(
            f"### {weekday}, "
            f"{date_value.strftime('%d.%m.%Y')}"
        )

        for _, row in day_df.iterrows():

            kickoff = (
                row["datetime_local"]
                .strftime("%H:%M")
            )

            prediction = row[
                "prediction"
            ]

            if prediction == "1":
                tip_text = "🏠 1"
            elif prediction == "X":
                tip_text = "🤝 X"
            else:
                tip_text = "✈️ 2"

            confidence = (
                row["confidence"] * 100
            )

            st.write(
                f"**{kickoff}** · "
                f"{row['league']} · "
                f"**{row['home']}** – "
                f"**{row['away']}** · "
                f"**{tip_text}** · "
                f"{confidence:.1f}% · "
                f"**{row['risk']}**"
            )


# ============================================================
# SCHEINE
# ============================================================

with tab_scheine:

    st.subheader(
        "🎟️ Automatischer Schein-Generator"
    )

    st.write(
        f"Budget: **{budget:.2f} €**"
    )

    low = df[
        df["risk"] == "LOW"
    ].sort_values(
        "confidence",
        ascending=False
    )

    mid = df[
        df["risk"] == "MID"
    ].sort_values(
        "confidence",
        ascending=False
    )

    high = df[
        df["risk"] == "HIGH"
    ].sort_values(
        "confidence",
        ascending=False
    )

    # --------------------------------------------------------
    # SICHERER SCHEIN
    # --------------------------------------------------------

    st.markdown(
        "### 🟢 LOW – sicherer Schein"
    )

    if len(low) >= 2:

        safe = low.head(2)

        total_probability = (
            safe["confidence"].prod()
        )

        st.write(
            f"Geschätzte Kombiwahrscheinlichkeit: "
            f"**{total_probability * 100:.1f}%**"
        )

        for _, row in safe.iterrows():

            st.write(
                f"- {row['home']} – "
                f"{row['away']} → "
                f"**{row['prediction']}** "
                f"({row['confidence']*100:.1f}%)"
            )

    else:

        st.info(
            "Aktuell sind nicht genügend LOW-Spiele vorhanden."
        )


    # --------------------------------------------------------
    # BALANCED
    # --------------------------------------------------------

    st.markdown(
        "### 🟡 MID – ausgewogener Schein"
    )

    balanced_candidates = pd.concat(
        [
            low.head(1),
            mid.head(2)
        ]
    )

    if len(balanced_candidates) >= 2:

        balanced = (
            balanced_candidates
            .head(3)
        )

        probability = (
            balanced["confidence"].prod()
        )

        st.write(
            f"Geschätzte Kombiwahrscheinlichkeit: "
            f"**{probability * 100:.1f}%**"
        )

        for _, row in balanced.iterrows():

            st.write(
                f"- {row['home']} – "
                f"{row['away']} → "
                f"**{row['prediction']}** "
                f"({row['confidence']*100:.1f}%)"
            )

    else:

        st.info(
            "Aktuell sind nicht genügend passende Spiele vorhanden."
        )


    # --------------------------------------------------------
    # AGGRESSIVE
    # --------------------------------------------------------

    st.markdown(
        "### 🔴 HIGH – aggressiver Schein"
    )

    aggressive = pd.concat(
        [
            mid.head(1),
            high.head(2)
        ]
    ).head(3)

    if len(aggressive) >= 2:

        probability = (
            aggressive["confidence"].prod()
        )

        st.write(
            f"Geschätzte Kombiwahrscheinlichkeit: "
            f"**{probability * 100:.1f}%**"
        )

        for _, row in aggressive.iterrows():

            st.write(
                f"- {row['home']} – "
                f"{row['away']} → "
                f"**{row['prediction']}** "
                f"({row['confidence']*100:.1f}%)"
            )

    else:

        st.info(
            "Aktuell sind nicht genügend HIGH-Spiele vorhanden."
        )


# ============================================================
# QUOTEN
# ============================================================

with tab_quoten:

    st.subheader(
        "📊 Aktuelle Quoten"
    )

    odds_view = df[
        [
            "datetime_local",
            "league",
            "home",
            "away",
            "bookmaker",
            "odd_1",
            "odd_x",
            "odd_2",
            "prediction",
            "risk",
        ]
    ].copy()

    odds_view.columns = [
        "Anstoß",
        "Liga",
        "Heim",
        "Auswärts",
        "Bookmaker",
        "1",
        "X",
        "2",
        "KI-Tipp",
        "Risiko",
    ]

    st.dataframe(
        odds_view,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Wenn bei einem Spiel keine Quote verfügbar "
        "ist, wird nichts erfunden und das Feld bleibt leer."
    )


# ============================================================
# TECHNISCHE INFOS
# ============================================================

if st.session_state.api_errors:

    with st.expander(
        "🔧 Technische Abruffehler"
    ):

        for error in (
            st.session_state.api_errors
        ):
            st.write(error)
