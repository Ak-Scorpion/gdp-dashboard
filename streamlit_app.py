import io
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import cv2
import numpy as np
import pandas as pd
import pytesseract
import streamlit as st
from PIL import Image
from scipy.optimize import minimize
from scipy.stats import poisson


# ============================================================
# WETT-KI 1X2 - SINGLE FILE VERSION
# ============================================================
#
# Funktionen:
# - Historische CSV-Daten laden
# - Poisson-Fußballmodell
# - 1 / X / 2 Wahrscheinlichkeiten
# - Automatische Tippauswahl
# - Faire Quote
# - Screenshot hochladen
# - OCR-Erkennung von Spielen
# - Teamnamen-Matching
# - Backtesting
#
# WICHTIG:
# Diese Software garantiert keine Gewinne.
# Sie ist ein Analyse- und Backtesting-Tool.
# ============================================================


st.set_page_config(
    page_title="Wett-KI 1X2",
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# KONFIGURATION
# ============================================================

MAX_GOALS_DEFAULT = 10
REGULARIZATION_DEFAULT = 0.08
DECAY_DAYS_DEFAULT = 900


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def normalize_team_name(name):
    """
    Vereinheitlicht Teamnamen für das Matching.
    """

    name = str(name)

    name = unicodedata.normalize(
        "NFKD",
        name,
    )

    name = (
        name
        .encode(
            "ascii",
            "ignore",
        )
        .decode()
    )

    name = name.lower()

    name = re.sub(
        r"[^a-z0-9 ]",
        " ",
        name,
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    )

    return name.strip()


def similarity(a, b):
    """
    Ähnlichkeit zweier Teamnamen.
    """

    return SequenceMatcher(
        None,
        normalize_team_name(a),
        normalize_team_name(b),
    ).ratio()


def find_best_team(
    query,
    known_teams,
    threshold=0.65,
):
    """
    Findet den ähnlichsten bekannten Teamnamen.
    """

    if not known_teams:
        return None, 0.0

    scores = []

    for team in known_teams:

        score = similarity(
            query,
            team,
        )

        scores.append(
            (
                score,
                team,
            )
        )

    scores.sort(
        reverse=True
    )

    best_score, best_team = scores[0]

    if best_score < threshold:
        return None, best_score

    return best_team, best_score


# ============================================================
# DATEN
# ============================================================

REQUIRED_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
]


def load_data(uploaded_file):

    df = pd.read_csv(
        uploaded_file
    )

    df.columns = [
        str(column)
        .strip()
        .lower()
        for column in df.columns
    ]

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Fehlende Spalten: "
            + ", ".join(missing)
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    df["home_team"] = (
        df["home_team"]
        .astype(str)
        .str.strip()
    )

    df["away_team"] = (
        df["away_team"]
        .astype(str)
        .str.strip()
    )

    df["home_goals"] = pd.to_numeric(
        df["home_goals"],
        errors="coerce",
    )

    df["away_goals"] = pd.to_numeric(
        df["away_goals"],
        errors="coerce",
    )

    if df[REQUIRED_COLUMNS].isnull().any().any():

        raise ValueError(
            "Die CSV enthält ungültige oder fehlende Werte."
        )

    if (
        df["home_goals"] < 0
    ).any() or (
        df["away_goals"] < 0
    ).any():

        raise ValueError(
            "Tore dürfen nicht negativ sein."
        )

    df = (
        df
        .sort_values("date")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# POISSON MODELL
# ============================================================

class FootballModel:

    def __init__(
        self,
        max_goals=10,
        regularization=0.08,
        decay_days=900,
    ):

        self.max_goals = max_goals

        self.regularization = (
            regularization
        )

        self.decay_days = (
            decay_days
        )

        self.teams = []

        self.attack = {}

        self.defense = {}

        self.home_advantage = 0.0

        self.fitted = False


    # --------------------------------------------------------
    # TRAINING
    # --------------------------------------------------------

    def fit(self, df):

        data = (
            df
            .sort_values("date")
            .reset_index(drop=True)
            .copy()
        )

        self.teams = sorted(
            set(data["home_team"])
            |
            set(data["away_team"])
        )

        if len(self.teams) < 2:

            raise ValueError(
                "Mindestens zwei Teams benötigt."
            )

        team_index = {
            team: index
            for index, team
            in enumerate(self.teams)
        }

        n = len(self.teams)

        home_goals = (
            data["home_goals"]
            .to_numpy(float)
        )

        away_goals = (
            data["away_goals"]
            .to_numpy(float)
        )

        latest_date = data["date"].max()

        age_days = (
            latest_date
            - data["date"]
        ).dt.days.to_numpy(float)

        weights = np.exp(
            -age_days
            / self.decay_days
        )


        # Parameter:
        #
        # 0             = Heimvorteil
        # 1 ... n       = Angriff
        # n+1 ... 2n    = Verteidigung

        initial = np.zeros(
            1 + 2 * n
        )


        def unpack(params):

            home_advantage = params[0]

            attack = params[
                1 : 1 + n
            ]

            defense = params[
                1 + n :
                1 + 2 * n
            ]

            return (
                home_advantage,
                attack,
                defense,
            )


        def objective(params):

            (
                home_advantage,
                attack,
                defense,
            ) = unpack(params)

            loss = 0.0

            for i, row in enumerate(
                data.itertuples(
                    index=False
                )
            ):

                home_index = team_index[
                    row.home_team
                ]

                away_index = team_index[
                    row.away_team
                ]


                log_home_lambda = (
                    home_advantage
                    + attack[home_index]
                    - defense[away_index]
                )

                log_away_lambda = (
                    attack[away_index]
                    - defense[home_index]
                )


                home_lambda = np.exp(
                    np.clip(
                        log_home_lambda,
                        -4,
                        3,
                    )
                )

                away_lambda = np.exp(
                    np.clip(
                        log_away_lambda,
                        -4,
                        3,
                    )
                )


                log_probability = (
                    poisson.logpmf(
                        home_goals[i],
                        home_lambda,
                    )
                    +
                    poisson.logpmf(
                        away_goals[i],
                        away_lambda,
                    )
                )


                loss -= (
                    weights[i]
                    * log_probability
                )


            # Regularisierung

            loss += (
                self.regularization
                * (
                    np.sum(
                        attack ** 2
                    )
                    +
                    np.sum(
                        defense ** 2
                    )
                    +
                    home_advantage ** 2
                )
            )


            # Angriff und Verteidigung
            # um 0 zentrieren.

            loss += (
                20.0
                * (
                    attack.mean() ** 2
                    +
                    defense.mean() ** 2
                )
            )

            return float(loss)


        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            options={
                "maxiter": 1500,
                "ftol": 1e-10,
            },
        )


        if not result.success:

            raise RuntimeError(
                "Modelltraining fehlgeschlagen: "
                + str(result.message)
            )


        (
            self.home_advantage,
            attack,
            defense,
        ) = unpack(
            result.x
        )


        self.attack = dict(
            zip(
                self.teams,
                attack,
            )
        )

        self.defense = dict(
            zip(
                self.teams,
                defense,
            )
        )

        self.fitted = True

        return self


    # --------------------------------------------------------
    # TEAM FINDEN
    # --------------------------------------------------------

    def resolve_team(
        self,
        name,
    ):

        if name in self.attack:
            return name

        best_team, score = find_best_team(
            name,
            self.teams,
            threshold=0.65,
        )

        if best_team is None:

            raise KeyError(
                f"Team nicht gefunden: {name}"
            )

        return best_team


    # --------------------------------------------------------
    # ERWARTETE TORE
    # --------------------------------------------------------

    def expected_goals(
        self,
        home,
        away,
    ):

        if not self.fitted:

            raise RuntimeError(
                "Modell wurde noch nicht trainiert."
            )

        home = self.resolve_team(
            home
        )

        away = self.resolve_team(
            away
        )


        home_lambda = np.exp(
            np.clip(
                self.home_advantage
                + self.attack[home]
                - self.defense[away],
                -4,
                3,
            )
        )


        away_lambda = np.exp(
            np.clip(
                self.attack[away]
                - self.defense[home],
                -4,
                3,
            )
        )


        return (
            float(home_lambda),
            float(away_lambda),
        )


    # --------------------------------------------------------
    # 1 X 2
    # --------------------------------------------------------

    def predict(
        self,
        home,
        away,
    ):

        (
            home_lambda,
            away_lambda,
        ) = self.expected_goals(
            home,
            away,
        )


        goals = np.arange(
            self.max_goals + 1
        )


        home_distribution = poisson.pmf(
            goals,
            home_lambda,
        )

        away_distribution = poisson.pmf(
            goals,
            away_lambda,
        )


        matrix = np.outer(
            home_distribution,
            away_distribution,
        )


        # Heim gewinnt
        home_win = float(
            np.tril(
                matrix,
                -1,
            ).sum()
        )


        # Unentschieden
        draw = float(
            np.trace(
                matrix
            )
        )


        # Auswärts gewinnt
        away_win = float(
            np.triu(
                matrix,
                1,
            ).sum()
        )


        total = (
            home_win
            + draw
            + away_win
        )


        home_win /= total
        draw /= total
        away_win /= total


        probabilities = {
            "1": home_win,
            "X": draw,
            "2": away_win,
        }


        pick = max(
            probabilities,
            key=probabilities.get,
        )


        confidence = (
            probabilities[pick]
        )


        fair_odds = (
            1.0
            / max(
                confidence,
                1e-12,
            )
        )


        return {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "pick": pick,
            "confidence": confidence,
            "fair_odds": fair_odds,
            "expected_home_goals": home_lambda,
            "expected_away_goals": away_lambda,
        }


# ============================================================
# OCR
# ============================================================

@dataclass
class Fixture:

    home_team: str

    away_team: str


def preprocess_image(
    image,
):

    array = np.array(
        image.convert("RGB")
    )

    gray = cv2.cvtColor(
        array,
        cv2.COLOR_RGB2GRAY,
    )

    # Größer machen

    gray = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2,
        interpolation=cv2.INTER_CUBIC,
    )

    # Entrauschen

    gray = cv2.GaussianBlur(
        gray,
        (3, 3),
        0,
    )

    # Schwarz/Weiß

    processed = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY
        + cv2.THRESH_OTSU,
    )[1]

    return processed


def extract_fixtures(
    image,
):

    processed = preprocess_image(
        image
    )


    try:

        text = pytesseract.image_to_string(
            processed,
            config="--psm 6",
        )

    except Exception as exc:

        raise RuntimeError(
            "OCR konnte nicht ausgeführt werden. "
            "Ist Tesseract installiert?"
        ) from exc


    # Typische Schreibweisen vereinheitlichen

    text = re.sub(
        r"\bvs\.?\b",
        "-",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bv\.?\b",
        "-",
        text,
        flags=re.IGNORECASE,
    )


    lines = [
        line.strip()
        for line
        in text.splitlines()
        if line.strip()
    ]


    fixtures = []


    for line in lines:

        # Verschiedene Trennzeichen

        parts = re.split(
            r"\s+(?:-|–|—)\s+",
            line,
            maxsplit=1,
        )


        if len(parts) != 2:
            continue


        home = parts[0]
        away = parts[1]


        # Ergebnisse entfernen

        home = re.sub(
            r"\b\d{1,2}\s*[:\-]\s*\d{1,2}\b",
            "",
            home,
        )

        away = re.sub(
            r"\b\d{1,2}\s*[:\-]\s*\d{1,2}\b",
            "",
            away,
        )


        # Wettquoten entfernen

        home = re.sub(
            r"\b\d+[.,]\d{1,2}\b",
            "",
            home,
        )

        away = re.sub(
            r"\b\d+[.,]\d{1,2}\b",
            "",
            away,
        )


        home = re.sub(
            r"[|•●]+",
            " ",
            home,
        )

        away = re.sub(
            r"[|•●]+",
            " ",
            away,
        )


        home = re.sub(
            r"\s+",
            " ",
            home,
        ).strip()


        away = re.sub(
            r"\s+",
            " ",
            away,
        ).strip()


        # Plausibilität

        if len(home) < 2:
            continue

        if len(away) < 2:
            continue

        if len(home) > 70:
            continue

        if len(away) > 70:
            continue


        fixtures.append(
            Fixture(
                home_team=home,
                away_team=away,
            )
        )


    # Duplikate entfernen

    unique = []

    seen = set()


    for fixture in fixtures:

        key = (
            normalize_team_name(
                fixture.home_team
            ),
            normalize_team_name(
                fixture.away_team
            ),
        )


        if key in seen:
            continue


        seen.add(key)

        unique.append(
            fixture
        )


    return (
        text,
        unique,
    )


# ============================================================
# BACKTEST
# ============================================================

def actual_result(
    home_goals,
    away_goals,
):

    if home_goals > away_goals:
        return "1"

    if home_goals < away_goals:
        return "2"

    return "X"


def run_backtest(
    df,
    test_fraction=0.20,
    max_goals=10,
    regularization=0.08,
):

    df = (
        df
        .sort_values("date")
        .reset_index(drop=True)
    )


    split = int(
        len(df)
        * (1 - test_fraction)
    )


    if split < 20:
        raise ValueError(
            "Zu wenige Trainingsspiele."
        )


    train = df.iloc[
        :split
    ].copy()


    test = df.iloc[
        split:
    ].copy()


    model = FootballModel(
        max_goals=max_goals,
        regularization=regularization,
    )


    model.fit(
        train
    )


    rows = []


    for row in test.itertuples(
        index=False
    ):

        try:

            prediction = model.predict(
                row.home_team,
                row.away_team,
            )

        except KeyError:

            continue


        actual = actual_result(
            row.home_goals,
            row.away_goals,
        )


        rows.append(
            {
                "Datum": row.date,
                "Heim": row.home_team,
                "Auswärts": row.away_team,
                "P(1)": prediction["home_win"],
                "P(X)": prediction["draw"],
                "P(2)": prediction["away_win"],
                "Tipp": prediction["pick"],
                "Ergebnis": actual,
                "Richtig": int(
                    prediction["pick"]
                    == actual
                ),
            }
        )


    predictions = pd.DataFrame(
        rows
    )


    if predictions.empty:

        raise ValueError(
            "Keine auswertbaren Testspiele."
        )


    accuracy = float(
        predictions["Richtig"].mean()
    )


    losses = []


    for row in predictions.itertuples(
        index=False
    ):

        if row.Ergebnis == "1":
            probability = row._3

        elif row.Ergebnis == "X":
            probability = row._4

        else:
            probability = row._5

        probability = max(
            min(
                probability,
                1 - 1e-15,
            ),
            1e-15,
        )

        losses.append(
            -np.log(
                probability
            )
        )


    log_loss = float(
        np.mean(losses)
    )


    return {
        "predictions": predictions,
        "accuracy": accuracy,
        "log_loss": log_loss,
    }


# ============================================================
# STREAMLIT APP
# ============================================================

st.title(
    "⚽ Wett-KI – Fußball 1X2"
)

st.markdown(
    """
Diese Anwendung analysiert Fußballspiele und wählt automatisch
zwischen **1**, **X** und **2**.

**1 = Heimsieg**  
**X = Unentschieden**  
**2 = Auswärtssieg**
"""
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ Einstellungen"
    )


    max_goals = st.slider(
        "Maximale Tore",
        6,
        15,
        MAX_GOALS_DEFAULT,
    )


    regularization = st.slider(
        "Regularisierung",
        0.01,
        0.50,
        REGULARIZATION_DEFAULT,
        0.01,
    )


    st.divider()


    st.subheader(
        "Historische Daten"
    )


    csv_file = st.file_uploader(
        "CSV hochladen",
        type=["csv"],
    )


    st.divider()


    st.subheader(
        "Screenshot"
    )


    screenshot = st.file_uploader(
        "Spiele-Screenshot hochladen",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
    )


# ============================================================
# DATEN LADEN
# ============================================================

if csv_file is None:

    st.warning(
        """
Bitte lade zunächst eine CSV mit historischen Spielen hoch.

Format:

date,home_team,away_team,home_goals,away_goals
"""
    )

    st.stop()


try:

    matches = load_data(
        csv_file
    )

except Exception as exc:

    st.error(
        f"CSV-Fehler: {exc}"
    )

    st.stop()


# ============================================================
# DATENÜBERSICHT
# ============================================================

st.header(
    "📊 Historische Daten"
)


col1, col2, col3 = st.columns(3)


col1.metric(
    "Spiele",
    len(matches),
)


col2.metric(
    "Teams",
    len(
        set(matches["home_team"])
        |
        set(matches["away_team"])
    ),
)


col3.metric(
    "Letztes Spiel",
    matches["date"]
    .max()
    .strftime("%d.%m.%Y"),
)


with st.expander(
    "Daten anzeigen"
):

    st.dataframe(
        matches,
        width="stretch",
        hide_index=True,
    )


# ============================================================
# MODELL TRAINIEREN
# ============================================================

st.header(
    "🧠 KI trainieren"
)


if st.button(
    "🚀 Modell trainieren",
    type="primary",
):

    if len(matches) < 20:

        st.error(
            "Bitte mindestens 20 historische Spiele verwenden."
        )

    else:

        with st.spinner(
            "KI trainiert..."
        ):

            model = FootballModel(
                max_goals=max_goals,
                regularization=regularization,
                decay_days=DECAY_DAYS_DEFAULT,
            )

            model.fit(
                matches
            )

            st.session_state[
                "model"
            ] = model

            st.session_state[
                "trained"
            ] = True


        st.success(
            "🟢 Modell erfolgreich trainiert."
        )


# ============================================================
# SCREENSHOT
# ============================================================

st.divider()

st.header(
    "📷 Screenshot → Spiele → 1/X/2"
)


if screenshot:

    image = Image.open(
        screenshot
    )


    st.image(
        image,
        caption="Screenshot",
        width="stretch",
    )


    if st.button(
        "🔎 Screenshot analysieren"
    ):

        with st.spinner(
            "Screenshot wird gelesen..."
        ):

            try:

                raw_text, fixtures = (
                    extract_fixtures(
                        image
                    )
                )


                st.session_state[
                    "ocr_text"
                ] = raw_text


                st.session_state[
                    "fixtures"
                ] = fixtures


            except Exception as exc:

                st.error(
                    str(exc)
                )


if "ocr_text" in st.session_state:

    with st.expander(
        "OCR-Rohtext anzeigen"
    ):

        st.text(
            st.session_state[
                "ocr_text"
            ]
        )


# ============================================================
# SPIELE BEARBEITEN
# ============================================================

fixtures = st.session_state.get(
    "fixtures",
    [],
)


if fixtures:

    st.subheader(
        "⚽ Erkannte Spiele"
    )


    edited = []


    for index, fixture in enumerate(
        fixtures
    ):

        col1, col2 = st.columns(2)


        home = col1.text_input(
            "Heim",
            fixture.home_team,
            key=f"home_team_{index}",
        )


        away = col2.text_input(
            "Auswärts",
            fixture.away_team,
            key=f"away_team_{index}",
        )


        edited.append(
            (
                home.strip(),
                away.strip(),
            )
        )


    if "trained" not in st.session_state:

        st.warning(
            "Trainiere zuerst die KI."
        )

    elif st.session_state[
        "trained"
    ]:

        if st.button(
            "🎯 KI soll automatisch 1 / X / 2 auswählen",
            type="primary",
        ):

            model = (
                st.session_state[
                    "model"
                ]
            )


            results = []


            for home, away in edited:

                try:

                    prediction = model.predict(
                        home,
                        away,
                    )


                    results.append(
                        {
                            "Heim": home,
                            "Auswärts": away,

                            "1": (
                                prediction[
                                    "home_win"
                                ]
                                * 100
                            ),

                            "X": (
                                prediction[
                                    "draw"
                                ]
                                * 100
                            ),

                            "2": (
                                prediction[
                                    "away_win"
                                ]
                                * 100
                            ),

                            "KI-Tipp": prediction[
                                "pick"
                            ],

                            "Sicherheit": (
                                prediction[
                                    "confidence"
                                ]
                                * 100
                            ),

                            "Faire Quote": prediction[
                                "fair_odds"
                            ],

                            "Erwartete Heimtore": prediction[
                                "expected_home_goals"
                            ],

                            "Erwartete Auswärtstore": prediction[
                                "expected_away_goals"
                            ],
                        }
                    )


                except Exception as exc:

                    results.append(
                        {
                            "Heim": home,
                            "Auswärts": away,
                            "1": None,
                            "X": None,
                            "2": None,
                            "KI-Tipp": f"Fehler: {exc}",
                            "Sicherheit": None,
                            "Faire Quote": None,
                            "Erwartete Heimtore": None,
                            "Erwartete Auswärtstore": None,
                        }
                    )


            predictions = pd.DataFrame(
                results
            )


            st.session_state[
                "predictions"
            ] = predictions


# ============================================================
# ERGEBNISSE
# ============================================================

if st.session_state.get(
    "predictions"
) is not None:

    st.divider()

    st.header(
        "🎯 KI-Auswahl"
    )


    predictions = (
        st.session_state[
            "predictions"
        ]
        .copy()
    )


    st.dataframe(
        predictions.round(2),
        width="stretch",
        hide_index=True,
    )


    st.success(
        """
Die Spalte **KI-Tipp** enthält automatisch 1, X oder 2.

Die Auswahl basiert auf der höchsten vom Modell
geschätzten Wahrscheinlichkeit.
"""
    )


    csv_output = (
        predictions
        .to_csv(
            index=False
        )
        .encode("utf-8")
    )


    st.download_button(
        "⬇️ Prognosen herunterladen",
        csv_output,
        "prognosen.csv",
        "text/csv",
    )


# ============================================================
# BACKTEST
# ============================================================

st.divider()

st.header(
    "📈 Backtesting"
)


test_fraction = st.slider(
    "Anteil Testdaten",
    0.10,
    0.40,
    0.20,
    0.05,
)


if st.button(
    "📊 Backtest durchführen"
):

    if len(matches) < 30:

        st.error(
            "Mindestens 30 Spiele für einen Backtest."
        )

    else:

        with st.spinner(
            "Backtest läuft..."
        ):

            try:

                result = run_backtest(
                    matches,
                    test_fraction=test_fraction,
                    max_goals=max_goals,
                    regularization=regularization,
                )


                col1, col2 = st.columns(2)


                col1.metric(
                    "Accuracy",
                    f"{result['accuracy'] * 100:.2f}%",
                )


                col2.metric(
                    "Log Loss",
                    f"{result['log_loss']:.4f}",
                )


                st.dataframe(
                    result[
                        "predictions"
                    ].round(4),
                    width="stretch",
                    hide_index=True,
                )


            except Exception as exc:

                st.error(
                    f"Backtest-Fehler: {exc}"
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Wett-KI 1X2 • Analyse- und Forschungssoftware • "
    "Keine Gewinn- oder Ergebnisgarantie."
)
