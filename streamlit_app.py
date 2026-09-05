# ============================================================
# WETT-KI - FOOTBALL 1/X/2 PREDICTOR
# Version 2
#
# Funktionen:
# - 1/X/2 Prognose
# - Poisson-Modell
# - Zeitgewichtung
# - Team-Matching
# - Screenshot/OCR
# - Over/Under
# - BTTS
# - Faire Quoten
# - Value-Berechnung
# - Rolling Backtest
# - CSV Export
#
# Benötigt:
# streamlit
# pandas
# numpy
# pillow
# pytesseract (optional)
# ============================================================

import os
import re
import math
import difflib

import numpy as np
import pandas as pd
import streamlit as st

from PIL import (
    Image,
    ImageOps,
    ImageEnhance,
    ImageFilter,
)


# ============================================================
# OPTIONALES OCR
# ============================================================

try:
    import pytesseract

    OCR_AVAILABLE = True

except Exception:

    pytesseract = None
    OCR_AVAILABLE = False


# ============================================================
# KONFIGURATION
# ============================================================

APP_TITLE = "⚽ Wett-KI – Fußball Predictor"

DATA_FILE = "data/matches.csv"

REQUIRED_COLUMNS = [
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
]

MIN_TRAINING_MATCHES = 20

DEFAULT_DECAY = 0.003

DEFAULT_REGULARIZATION = 0.15

MAX_GOALS = 10


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# ALLGEMEINE HILFSFUNKTIONEN
# ============================================================

def poisson_probability(k, lam):
    """
    Berechnet P(X=k) bei einer Poisson-Verteilung.
    """

    if lam <= 0:
        return 0.0

    try:

        return (
            math.exp(-lam)
            * (lam ** k)
            / math.factorial(k)
        )

    except Exception:

        return 0.0


def normalize_team_name(name):
    """
    Vereinheitlicht Teamnamen.
    """

    if name is None:
        return ""

    name = str(name).lower().strip()

    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }

    for old, new in replacements.items():

        name = name.replace(
            old,
            new
        )

    name = re.sub(
        r"[^a-z0-9\s]",
        " ",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    prefixes = [
        "fc ",
        "cf ",
        "ac ",
        "afc ",
        "sc ",
        "sv ",
        "vfb ",
        "vfl ",
    ]

    for prefix in prefixes:

        if name.startswith(prefix):

            name = name[
                len(prefix):
            ]

            break

    return name.strip()


def safe_float(value, default=0.0):

    try:

        return float(value)

    except Exception:

        return default


# ============================================================
# DATEN
# ============================================================

def create_sample_data():

    os.makedirs(
        "data",
        exist_ok=True
    )

    sample = [

        ["2025-01-05", "Bayern Munich", "Mainz", 3, 1],
        ["2025-01-06", "Dortmund", "Leverkusen", 2, 2],
        ["2025-01-07", "Frankfurt", "Freiburg", 2, 0],
        ["2025-01-08", "Mainz", "Dortmund", 1, 2],
        ["2025-01-09", "Leverkusen", "Frankfurt", 3, 1],
        ["2025-01-10", "Freiburg", "Bayern Munich", 0, 2],
        ["2025-01-11", "Dortmund", "Freiburg", 3, 1],
        ["2025-01-12", "Mainz", "Leverkusen", 1, 3],
        ["2025-01-13", "Frankfurt", "Bayern Munich", 1, 2],
        ["2025-01-14", "Freiburg", "Mainz", 1, 1],
        ["2025-01-15", "Bayern Munich", "Dortmund", 2, 1],
        ["2025-01-16", "Leverkusen", "Freiburg", 2, 0],
        ["2025-01-17", "Mainz", "Frankfurt", 1, 2],
        ["2025-01-18", "Dortmund", "Leverkusen", 1, 2],
        ["2025-01-19", "Frankfurt", "Dortmund", 2, 2],
        ["2025-01-20", "Bayern Munich", "Leverkusen", 2, 2],
        ["2025-01-21", "Freiburg", "Dortmund", 0, 2],
        ["2025-01-22", "Mainz", "Bayern Munich", 0, 3],
        ["2025-01-23", "Leverkusen", "Mainz", 3, 0],
        ["2025-01-24", "Dortmund", "Frankfurt", 2, 1],
        ["2025-01-25", "Bayern Munich", "Freiburg", 4, 0],
        ["2025-01-26", "Frankfurt", "Mainz", 2, 1],
        ["2025-01-27", "Freiburg", "Leverkusen", 1, 3],
        ["2025-01-28", "Dortmund", "Bayern Munich", 1, 3],
        ["2025-01-29", "Mainz", "Freiburg", 1, 0],
        ["2025-01-30", "Leverkusen", "Dortmund", 2, 1],
        ["2025-01-31", "Bayern Munich", "Frankfurt", 3, 1],
        ["2025-02-01", "Freiburg", "Frankfurt", 1, 1],
        ["2025-02-02", "Dortmund", "Mainz", 3, 0],
        ["2025-02-03", "Leverkusen", "Bayern Munich", 1, 2],

    ]

    df = pd.DataFrame(
        sample,
        columns=REQUIRED_COLUMNS
    )

    df.to_csv(
        DATA_FILE,
        index=False
    )

    return df


@st.cache_data
def load_data(uploaded_file=None):

    if uploaded_file is not None:

        df = pd.read_csv(
            uploaded_file
        )

    elif os.path.exists(DATA_FILE):

        df = pd.read_csv(
            DATA_FILE
        )

    else:

        df = create_sample_data()

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    missing = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:

        raise ValueError(
            "Folgende Spalten fehlen: "
            + ", ".join(missing)
        )

    df = df[
        REQUIRED_COLUMNS
    ].copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["home_goals"] = pd.to_numeric(
        df["home_goals"],
        errors="coerce"
    )

    df["away_goals"] = pd.to_numeric(
        df["away_goals"],
        errors="coerce"
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

    df = df.dropna(
        subset=[
            "date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
        ]
    )

    df = df[
        (df["home_goals"] >= 0)
        & (df["away_goals"] >= 0)
    ]

    df = df.sort_values(
        "date"
    ).reset_index(
        drop=True
    )

    return df


def get_team_list(df):

    teams = set()

    for team in df["home_team"]:

        teams.add(team)

    for team in df["away_team"]:

        teams.add(team)

    return sorted(
        teams
    )


# ============================================================
# TEAM MATCHING
# ============================================================

def match_team(
    ocr_name,
    teams,
    threshold=0.50
):

    if not ocr_name:

        return None, 0.0

    normalized_input = (
        normalize_team_name(
            ocr_name
        )
    )

    if not normalized_input:

        return None, 0.0

    best_team = None
    best_score = 0.0

    for team in teams:

        normalized_team = (
            normalize_team_name(
                team
            )
        )

        if (
            normalized_input
            == normalized_team
        ):

            return team, 1.0

        sequence_score = (
            difflib.SequenceMatcher(
                None,
                normalized_input,
                normalized_team
            ).ratio()
        )

        input_words = set(
            normalized_input.split()
        )

        team_words = set(
            normalized_team.split()
        )

        word_score = 0.0

        if input_words and team_words:

            intersection = len(
                input_words
                .intersection(
                    team_words
                )
            )

            word_score = (
                intersection
                / max(
                    len(input_words),
                    len(team_words)
                )
            )

        score = max(
            sequence_score,
            word_score
        )

        if score > best_score:

            best_score = score
            best_team = team

    if best_score >= threshold:

        return (
            best_team,
            best_score
        )

    return (
        None,
        best_score
    )


# ============================================================
# POISSON MODELL
# ============================================================

class PoissonFootballModel:

    def __init__(
        self,
        decay=DEFAULT_DECAY,
        regularization=DEFAULT_REGULARIZATION
    ):

        self.decay = decay

        self.regularization = (
            regularization
        )

        self.attack = {}

        self.defense = {}

        self.home_advantage = 0.15

        self.global_home_goals = 1.40

        self.global_away_goals = 1.10

        self.teams = []

        self.fitted = False

    # --------------------------------------------------------
    # FIT
    # --------------------------------------------------------

    def fit(self, df):

        if len(df) < MIN_TRAINING_MATCHES:

            raise ValueError(
                f"Mindestens "
                f"{MIN_TRAINING_MATCHES} "
                f"Spiele werden benötigt."
            )

        df = (
            df.sort_values("date")
            .reset_index(drop=True)
            .copy()
        )

        self.teams = get_team_list(
            df
        )

        self.global_home_goals = max(
            0.2,
            float(
                df["home_goals"].mean()
            )
        )

        self.global_away_goals = max(
            0.2,
            float(
                df["away_goals"].mean()
            )
        )

        attack_values = {
            team: 1.0
            for team in self.teams
        }

        defense_values = {
            team: 1.0
            for team in self.teams
        }

        max_date = df["date"].max()

        weights = []

        for _, row in df.iterrows():

            days_old = max(
                0,
                (
                    max_date
                    - row["date"]
                ).days
            )

            weight = math.exp(
                -self.decay
                * days_old
            )

            weights.append(
                weight
            )

        df["weight"] = weights

        for _ in range(35):

            new_attack = {}

            new_defense = {}

            # ------------------------------------------------
            # ANGRIFF
            # ------------------------------------------------

            for team in self.teams:

                scored = 0.0

                expected = 0.0

                home_games = df[
                    df["home_team"]
                    == team
                ]

                away_games = df[
                    df["away_team"]
                    == team
                ]

                for _, row in (
                    home_games.iterrows()
                ):

                    opponent = (
                        row["away_team"]
                    )

                    opponent_defense = (
                        defense_values.get(
                            opponent,
                            1.0
                        )
                    )

                    expected_goals = (
                        self.global_home_goals
                        * attack_values.get(
                            team,
                            1.0
                        )
                        * opponent_defense
                    )

                    scored += (
                        row["home_goals"]
                        * row["weight"]
                    )

                    expected += (
                        expected_goals
                        * row["weight"]
                    )

                for _, row in (
                    away_games.iterrows()
                ):

                    opponent = (
                        row["home_team"]
                    )

                    opponent_defense = (
                        defense_values.get(
                            opponent,
                            1.0
                        )
                    )

                    expected_goals = (
                        self.global_away_goals
                        * attack_values.get(
                            team,
                            1.0
                        )
                        * opponent_defense
                    )

                    scored += (
                        row["away_goals"]
                        * row["weight"]
                    )

                    expected += (
                        expected_goals
                        * row["weight"]
                    )

                if expected > 0:

                    ratio = (
                        scored
                        / expected
                    )

                else:

                    ratio = 1.0

                ratio = (
                    ratio
                    * (
                        1
                        - self.regularization
                    )
                    + self.regularization
                )

                new_attack[team] = float(
                    np.clip(
                        ratio,
                        0.35,
                        2.5
                    )
                )

            # ------------------------------------------------
            # VERTEIDIGUNG
            # ------------------------------------------------

            for team in self.teams:

                conceded = 0.0

                expected_conceded = 0.0

                home_games = df[
                    df["home_team"]
                    == team
                ]

                away_games = df[
                    df["away_team"]
                    == team
                ]

                for _, row in (
                    home_games.iterrows()
                ):

                    opponent = (
                        row["away_team"]
                    )

                    opponent_attack = (
                        attack_values.get(
                            opponent,
                            1.0
                        )
                    )

                    expected_goals = (
                        self.global_away_goals
                        * opponent_attack
                        * defense_values.get(
                            team,
                            1.0
                        )
                    )

                    conceded += (
                        row["away_goals"]
                        * row["weight"]
                    )

                    expected_conceded += (
                        expected_goals
                        * row["weight"]
                    )

                for _, row in (
                    away_games.iterrows()
                ):

                    opponent = (
                        row["home_team"]
                    )

                    opponent_attack = (
                        attack_values.get(
                            opponent,
                            1.0
                        )
                    )

                    expected_goals = (
                        self.global_home_goals
                        * opponent_attack
                        * defense_values.get(
                            team,
                            1.0
                        )
                    )

                    conceded += (
                        row["home_goals"]
                        * row["weight"]
                    )

                    expected_conceded += (
                        expected_goals
                        * row["weight"]
                    )

                if expected_conceded > 0:

                    ratio = (
                        conceded
                        / expected_conceded
                    )

                else:

                    ratio = 1.0

                ratio = (
                    ratio
                    * (
                        1
                        - self.regularization
                    )
                    + self.regularization
                )

                new_defense[team] = float(
                    np.clip(
                        ratio,
                        0.35,
                        2.5
                    )
                )

            attack_values = (
                new_attack
            )

            defense_values = (
                new_defense
            )

        self.attack = attack_values

        self.defense = defense_values

        # ----------------------------------------------------
        # DATENBASIERTER HEIMVORTEIL
        # ----------------------------------------------------

        home_mean = (
            df["home_goals"]
            .mean()
        )

        away_mean = (
            df["away_goals"]
            .mean()
        )

        if away_mean > 0:

            calculated_home_advantage = (
                math.log(
                    max(
                        0.5,
                        home_mean
                    )
                    / max(
                        0.5,
                        away_mean
                    )
                )
            )

            self.home_advantage = float(
                np.clip(
                    calculated_home_advantage,
                    0.05,
                    0.30
                )
            )

        self.fitted = True

        return self

    # --------------------------------------------------------
    # EXPECTED GOALS
    # --------------------------------------------------------

    def expected_goals(
        self,
        home_team,
        away_team
    ):

        if not self.fitted:

            raise RuntimeError(
                "Modell wurde noch "
                "nicht trainiert."
            )

        home_attack = (
            self.attack.get(
                home_team,
                1.0
            )
        )

        away_attack = (
            self.attack.get(
                away_team,
                1.0
            )
        )

        home_defense = (
            self.defense.get(
                home_team,
                1.0
            )
        )

        away_defense = (
            self.defense.get(
                away_team,
                1.0
            )
        )

        home_lambda = (
            self.global_home_goals
            * home_attack
            * away_defense
            * math.exp(
                self.home_advantage
            )
        )

        away_lambda = (
            self.global_away_goals
            * away_attack
            * home_defense
        )

        home_lambda = float(
            np.clip(
                home_lambda,
                0.15,
                5.0
            )
        )

        away_lambda = float(
            np.clip(
                away_lambda,
                0.15,
                5.0
            )
        )

        return (
            home_lambda,
            away_lambda
        )

    # --------------------------------------------------------
    # TOR-MATRIX
    # --------------------------------------------------------

    def goal_matrix(
        self,
        home_team,
        away_team
    ):

        home_lambda, away_lambda = (
            self.expected_goals(
                home_team,
                away_team
            )
        )

        matrix = np.zeros(
            (
                MAX_GOALS + 1,
                MAX_GOALS + 1
            )
        )

        for home_goals in range(
            MAX_GOALS + 1
        ):

            for away_goals in range(
                MAX_GOALS + 1
            ):

                matrix[
                    home_goals,
                    away_goals
                ] = (
                    poisson_probability(
                        home_goals,
                        home_lambda
                    )
                    *
                    poisson_probability(
                        away_goals,
                        away_lambda
                    )
                )

        total = matrix.sum()

        if total > 0:

            matrix /= total

        return matrix

    # --------------------------------------------------------
    # 1 X 2
    # --------------------------------------------------------

    def probabilities(
        self,
        home_team,
        away_team
    ):

        matrix = self.goal_matrix(
            home_team,
            away_team
        )

        prob_home = 0.0

        prob_draw = 0.0

        prob_away = 0.0

        for h in range(
            MAX_GOALS + 1
        ):

            for a in range(
                MAX_GOALS + 1
            ):

                probability = (
                    matrix[h, a]
                )

                if h > a:

                    prob_home += (
                        probability
                    )

                elif h == a:

                    prob_draw += (
                        probability
                    )

                else:

                    prob_away += (
                        probability
                    )

        probabilities = {

            "1": float(
                prob_home
            ),

            "X": float(
                prob_draw
            ),

            "2": float(
                prob_away
            ),

        }

        return (
            probabilities,
            matrix
        )

    # --------------------------------------------------------
    # KOMPLETTE PROGNOSE
    # --------------------------------------------------------

    def predict(
        self,
        home_team,
        away_team
    ):

        probabilities, matrix = (
            self.probabilities(
                home_team,
                away_team
            )
        )

        prediction = max(
            probabilities,
            key=probabilities.get
        )

        confidence = (
            probabilities[
                prediction
            ]
        )

        fair_odds = {}

        for key, probability in (
            probabilities.items()
        ):

            if probability > 0:

                fair_odds[key] = (
                    1.0
                    / probability
                )

            else:

                fair_odds[key] = (
                    float("inf")
                )

        best_score = np.unravel_index(
            np.argmax(matrix),
            matrix.shape
        )

        home_lambda, away_lambda = (
            self.expected_goals(
                home_team,
                away_team
            )
        )

        # ----------------------------------------------------
        # OVER / UNDER
        # ----------------------------------------------------

        total_goals = {}

        for threshold in [
            0.5,
            1.5,
            2.5,
            3.5,
            4.5,
        ]:

            over_probability = 0.0

            for h in range(
                MAX_GOALS + 1
            ):

                for a in range(
                    MAX_GOALS + 1
                ):

                    if (
                        h + a
                        > threshold
                    ):

                        over_probability += (
                            matrix[h, a]
                        )

            total_goals[
                threshold
            ] = {
                "over": float(
                    over_probability
                ),
                "under": float(
                    1.0
                    - over_probability
                ),
            }

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        btts_yes = 0.0

        for h in range(
            1,
            MAX_GOALS + 1
        ):

            for a in range(
                1,
                MAX_GOALS + 1
            ):

                btts_yes += (
                    matrix[h, a]
                )

        btts = {

            "yes": float(
                btts_yes
            ),

            "no": float(
                1.0 - btts_yes
            ),

        }

        return {

            "prediction": prediction,

            "probabilities": probabilities,

            "confidence": confidence,

            "fair_odds": fair_odds,

            "expected_home_goals": (
                home_lambda
            ),

            "expected_away_goals": (
                away_lambda
            ),

            "most_likely_score": (
                int(best_score[0]),
                int(best_score[1])
            ),

            "over_under": total_goals,

            "btts": btts,

        }


# ============================================================
# VALUE
# ============================================================

def calculate_value(
    probability,
    bookmaker_odds
):

    probability = safe_float(
        probability
    )

    bookmaker_odds = safe_float(
        bookmaker_odds
    )

    if (
        probability <= 0
        or bookmaker_odds <= 0
    ):

        return None

    fair_odds = (
        1.0
        / probability
    )

    implied_probability = (
        1.0
        / bookmaker_odds
    )

    value_percent = (
        (
            probability
            * bookmaker_odds
        )
        - 1.0
    ) * 100

    return {

        "fair_odds": fair_odds,

        "implied_probability": (
            implied_probability
        ),

        "value_percent": (
            value_percent
        ),

        "positive_value": (
            value_percent > 0
        ),

    }


# ============================================================
# OCR
# ============================================================

def preprocess_image(image):

    img = image.convert(
        "RGB"
    )

    img = ImageOps.grayscale(
        img
    )

    width, height = (
        img.size
    )

    if width < 1800:

        scale = (
            1800
            / width
        )

        img = img.resize(
            (
                int(width * scale),
                int(height * scale)
            ),
            Image.Resampling.LANCZOS
        )

    img = ImageEnhance.Contrast(
        img
    ).enhance(2.2)

    img = ImageEnhance.Sharpness(
        img
    ).enhance(2.0)

    img = img.filter(
        ImageFilter.SHARPEN
    )

    img = ImageOps.autocontrast(
        img
    )

    return img


def run_ocr(image):

    if not OCR_AVAILABLE:

        return ""

    processed = (
        preprocess_image(
            image
        )
    )

    texts = []

    configs = [

        "--psm 6",

        "--psm 11",

        "--psm 12",

    ]

    for config in configs:

        try:

            text = (
                pytesseract
                .image_to_string(
                    processed,
                    config=config
                )
            )

            if text:

                texts.append(
                    text
                )

        except Exception:

            pass

    # Doppelte OCR-Zeilen vermeiden

    lines = []

    seen = set()

    for text in texts:

        for line in text.splitlines():

            line = line.strip()

            if not line:

                continue

            key = line.lower()

            if key not in seen:

                seen.add(key)

                lines.append(
                    line
                )

    return "\n".join(
        lines
    )


# ============================================================
# OCR SPIELE ERKENNEN
# ============================================================

def clean_ocr_line(line):

    line = str(line)

    line = line.replace(
        "\t",
        " "
    )

    line = re.sub(
        r"\s+",
        " ",
        line
    )

    return line.strip()


def extract_possible_matches(
    text
):

    if not text:

        return []

    lines = (
        text.splitlines()
    )

    matches = []

    separators = [
        " vs ",
        " v ",
        " - ",
        " – ",
        " — ",
        " : ",
        " @ ",
    ]

    for raw_line in lines:

        line = clean_ocr_line(
            raw_line
        )

        if len(line) < 5:

            continue

        digit_count = sum(
            c.isdigit()
            for c in line
        )

        if digit_count > 8:

            continue

        for separator in separators:

            if separator in (
                line.lower()
            ):

                parts = re.split(
                    re.escape(
                        separator
                    ),
                    line,
                    maxsplit=1,
                    flags=re.IGNORECASE
                )

                if len(parts) != 2:

                    continue

                home = (
                    parts[0]
                    .strip()
                )

                away = (
                    parts[1]
                    .strip()
                )

                # Zahlen/Quoten aus Teamnamen entfernen

                home = re.sub(
                    r"\b\d+(?:[.,]\d+)?\b",
                    "",
                    home
                ).strip()

                away = re.sub(
                    r"\b\d+(?:[.,]\d+)?\b",
                    "",
                    away
                ).strip()

                if (
                    len(home) >= 2
                    and len(away) >= 2
                ):

                    matches.append(
                        (
                            home,
                            away
                        )
                    )

                break

    unique = []

    seen = set()

    for home, away in matches:

        key = (
            home.lower(),
            away.lower()
        )

        if key not in seen:

            seen.add(key)

            unique.append(
                (
                    home,
                    away
                )
            )

    return unique


# ============================================================
# RESULTAT
# ============================================================

def actual_result(
    home_goals,
    away_goals
):

    if home_goals > away_goals:

        return "1"

    if home_goals < away_goals:

        return "2"

    return "X"


# ============================================================
# ROLLING BACKTEST
# ============================================================

def run_rolling_backtest(
    df,
    decay,
    regularization,
    minimum_training_matches=20
):

    df = (
        df.sort_values("date")
        .reset_index(drop=True)
        .copy()
    )

    if len(df) <= minimum_training_matches:

        return None

    results = []

    for index in range(
        minimum_training_matches,
        len(df)
    ):

        train_df = df.iloc[
            :index
        ].copy()

        test_row = df.iloc[
            index
        ]

        home_team = (
            test_row["home_team"]
        )

        away_team = (
            test_row["away_team"]
        )

        try:

            model = (
                PoissonFootballModel(
                    decay=decay,
                    regularization=(
                        regularization
                    )
                )
            )

            model.fit(
                train_df
            )

        except Exception:

            continue

        if (
            home_team
            not in model.teams
            or away_team
            not in model.teams
        ):

            continue

        try:

            prediction = (
                model.predict(
                    home_team,
                    away_team
                )
            )

        except Exception:

            continue

        predicted = (
            prediction["prediction"]
        )

        actual = actual_result(
            test_row["home_goals"],
            test_row["away_goals"]
        )

        results.append(
            {

                "date": test_row["date"],

                "home_team": home_team,

                "away_team": away_team,

                "prediction": predicted,

                "actual": actual,

                "correct": (
                    predicted == actual
                ),

                "P(1)": (
                    prediction[
                        "probabilities"
                    ]["1"]
                ),

                "P(X)": (
                    prediction[
                        "probabilities"
                    ]["X"]
                ),

                "P(2)": (
                    prediction[
                        "probabilities"
                    ]["2"]
                ),

            }
        )

    if not results:

        return None

    result_df = pd.DataFrame(
        results
    )

    accuracy = (
        result_df["correct"]
        .mean()
    )

    return {

        "results": result_df,

        "accuracy": float(
            accuracy
        ),

        "tested_matches": len(
            result_df
        ),

    }


# ============================================================
# CSV
# ============================================================

def dataframe_to_csv(df):

    return df.to_csv(
        index=False
    ).encode(
        "utf-8-sig"
    )


# ============================================================
# HEADER
# ============================================================

st.title(
    APP_TITLE
)

st.markdown(
    """
    **Statistisches Fußball-Prognosemodell für 1/X/2.**

    Zusätzlich werden erwartete Tore, Over/Under,
    BTTS, faire Quoten und Value berechnet.

    ⚠️ Statistische Prognosen sind keine Garantie
    für Gewinne.
    """
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "⚙️ Einstellungen"
)

decay = st.sidebar.slider(
    "Zeitgewichtung",
    min_value=0.000,
    max_value=0.010,
    value=DEFAULT_DECAY,
    step=0.001
)

regularization = st.sidebar.slider(
    "Regularisierung",
    min_value=0.00,
    max_value=0.50,
    value=DEFAULT_REGULARIZATION,
    step=0.01
)

st.sidebar.header(
    "📊 Historische Daten"
)

uploaded_csv = st.sidebar.file_uploader(
    "CSV hochladen",
    type=["csv"],
    help=(
        "date, home_team, away_team, "
        "home_goals, away_goals"
    )
)


# ============================================================
# DATEN LADEN
# ============================================================

try:

    df = load_data(
        uploaded_file=uploaded_csv
    )

except Exception as e:

    st.error(
        f"Fehler beim Laden der Daten: {e}"
    )

    st.stop()


# ============================================================
# DATEN INFO
# ============================================================

col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:

    st.metric(
        "Spiele",
        len(df)
    )

with col2:

    st.metric(
        "Teams",
        len(
            get_team_list(df)
        )
    )

with col3:

    st.metric(
        "Ø Heimtore",
        f"{df['home_goals'].mean():.2f}"
    )

with col4:

    st.metric(
        "Ø Auswärtstore",
        f"{df['away_goals'].mean():.2f}"
    )


# ============================================================
# MODELL
# ============================================================

try:

    model = PoissonFootballModel(
        decay=decay,
        regularization=regularization
    )

    model.fit(
        df
    )

except Exception as e:

    st.error(
        f"Modell konnte nicht trainiert werden: {e}"
    )

    st.stop()


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🔮 Prognose",
        "📷 Screenshot",
        "📈 Backtest",
        "📚 Daten",
    ]
)


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader(
        "🔮 Fußball-Prognose"
    )

    teams = get_team_list(
        df
    )

    col1, col2 = (
        st.columns(2)
    )

    with col1:

        home_team = st.selectbox(
            "Heimteam",
            teams,
            key="home_team"
        )

    with col2:

        away_options = [
            team
            for team in teams
            if team != home_team
        ]

        if not away_options:

            away_options = teams

        away_team = st.selectbox(
            "Auswärtsteam",
            away_options,
            key="away_team"
        )

    st.divider()

    if st.button(
        "🚀 PROGNOSE BERECHNEN",
        type="primary",
        use_container_width=True
    ):

        if home_team == away_team:

            st.warning(
                "Heim- und Auswärtsteam "
                "dürfen nicht identisch sein."
            )

        else:

            prediction = model.predict(
                home_team,
                away_team
            )

            result = (
                prediction["prediction"]
            )

            labels = {

                "1":
                    "🏠 HEIMSIEG (1)",

                "X":
                    "🤝 UNENTSCHIEDEN (X)",

                "2":
                    "✈️ AUSWÄRTSSIEG (2)",

            }

            st.success(
                f"### KI-Prognose: "
                f"{labels[result]}"
            )

            # ------------------------------------------------
            # 1 X 2
            # ------------------------------------------------

            st.subheader(
                "1/X/2 Wahrscheinlichkeiten"
            )

            c1, c2, c3 = (
                st.columns(3)
            )

            with c1:

                st.metric(
                    "1 – Heimsieg",
                    f"{prediction['probabilities']['1'] * 100:.1f}%"
                )

            with c2:

                st.metric(
                    "X – Unentschieden",
                    f"{prediction['probabilities']['X'] * 100:.1f}%"
                )

            with c3:

                st.metric(
                    "2 – Auswärtssieg",
                    f"{prediction['probabilities']['2'] * 100:.1f}%"
                )

            # ------------------------------------------------
            # KONFIDENZ
            # ------------------------------------------------

            confidence = (
                prediction["confidence"]
            )

            st.subheader(
                "🎯 Modell-Konfidenz"
            )

            st.progress(
                min(
                    max(
                        confidence,
                        0.0
                    ),
                    1.0
                )
            )

            st.write(
                f"**{confidence * 100:.1f}%** "
                "für das wahrscheinlichste 1/X/2-Ergebnis"
            )

            # ------------------------------------------------
            # TORE
            # ------------------------------------------------

            st.subheader(
                "⚽ Erwartete Tore"
            )

            c1, c2 = (
                st.columns(2)
            )

            with c1:

                st.metric(
                    home_team,
                    f"{prediction['expected_home_goals']:.2f}"
                )

            with c2:

                st.metric(
                    away_team,
                    f"{prediction['expected_away_goals']:.2f}"
                )

            score = (
                prediction[
                    "most_likely_score"
                ]
            )

            st.info(
                f"⚽ Wahrscheinlichstes Ergebnis: "
                f"**{score[0]} : {score[1]}**"
            )

            # ------------------------------------------------
            # OVER / UNDER
            # ------------------------------------------------

            st.subheader(
                "📊 Over / Under"
            )

            ou_rows = []

            for threshold in [
                0.5,
                1.5,
                2.5,
                3.5,
                4.5,
            ]:

                data = (
                    prediction[
                        "over_under"
                    ][threshold]
                )

                ou_rows.append(
                    {

                        "Linie":
                            f"{threshold:.1f}",

                        "Over":
                            f"{data['over'] * 100:.1f}%",

                        "Under":
                            f"{data['under'] * 100:.1f}%",

                    }
                )

            st.dataframe(
                pd.DataFrame(
                    ou_rows
                ),
                use_container_width=True,
                hide_index=True
            )

            # ------------------------------------------------
            # BTTS
            # ------------------------------------------------

            st.subheader(
                "⚽ Beide Teams treffen – BTTS"
            )

            btts = prediction[
                "btts"
            ]

            c1, c2 = (
                st.columns(2)
            )

            with c1:

                st.metric(
                    "BTTS Ja",
                    f"{btts['yes'] * 100:.1f}%"
                )

            with c2:

                st.metric(
                    "BTTS Nein",
                    f"{btts['no'] * 100:.1f}%"
                )

            # ------------------------------------------------
            # FAIRE QUOTEN
            # ------------------------------------------------

            st.subheader(
                "💰 Faire Modellquoten"
            )

            fair_rows = []

            for key in [
                "1",
                "X",
                "2"
            ]:

                fair_rows.append(
                    {

                        "Ergebnis":
                            key,

                        "Wahrscheinlichkeit":
                            f"{prediction['probabilities'][key] * 100:.2f}%",

                        "Faire Quote":
                            f"{prediction['fair_odds'][key]:.2f}",

                    }
                )

            st.dataframe(
                pd.DataFrame(
                    fair_rows
                ),
                use_container_width=True,
                hide_index=True
            )

            # ------------------------------------------------
            # VALUE CALCULATOR
            # ------------------------------------------------

            st.subheader(
                "💰 Value-Rechner"
            )

            value_result = st.selectbox(
                "Welches Ergebnis möchtest du prüfen?",
                ["1", "X", "2"],
                key="value_result"
            )

            bookmaker_odds = st.number_input(
                "Buchmacherquote",
                min_value=1.01,
                max_value=100.0,
                value=2.00,
                step=0.01,
                key="bookmaker_odds"
            )

            probability = (
                prediction[
                    "probabilities"
                ][value_result]
            )

            value = calculate_value(
                probability,
                bookmaker_odds
            )

            if value is not None:

                c1, c2, c3 = (
                    st.columns(3)
                )

                with c1:

                    st.metric(
                        "Modell-Wahrscheinlichkeit",
                        f"{probability * 100:.2f}%"
                    )

                with c2:

                    st.metric(
                        "Faire Quote",
                        f"{value['fair_odds']:.2f}"
                    )

                with c3:

                    st.metric(
                        "Value",
                        f"{value['value_percent']:.2f}%"
                    )

                if value[
                    "positive_value"
                ]:

                    st.success(
                        "🟢 POSITIVER VALUE laut Modell"
                    )

                else:

                    st.warning(
                        "🔴 Kein positiver Value laut Modell"
                    )


# ============================================================
# TAB 2 SCREENSHOT
# ============================================================

with tab2:

    st.subheader(
        "📷 Spiele automatisch erkennen"
    )

    st.write(
        """
        Lade einen Screenshot einer Spieleliste hoch.
        Die OCR versucht die Paarungen zu erkennen und
        anschließend mit deinen historischen Teamnamen
        abzugleichen.
        """
    )

    screenshot = st.file_uploader(
        "Screenshot hochladen",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ],
        key="screenshot_upload"
    )

    if not OCR_AVAILABLE:

        st.warning(
            """
            OCR ist aktuell nicht installiert.

            Die restliche App funktioniert trotzdem.
            """
        )

    if screenshot is not None:

        image = Image.open(
            screenshot
        )

        st.image(
            image,
            caption="Screenshot",
            use_container_width=True
        )

        if OCR_AVAILABLE:

            if st.button(
                "🔍 SCREENSHOT ANALYSIEREN",
                type="primary",
                use_container_width=True
            ):

                with st.spinner(
                    "OCR analysiert Screenshot..."
                ):

                    ocr_text = run_ocr(
                        image
                    )

                if not ocr_text.strip():

                    st.error(
                        "Kein Text erkannt."
                    )

                else:

                    st.subheader(
                        "📝 Erkannter Text"
                    )

                    st.text_area(
                        "OCR",
                        ocr_text,
                        height=200
                    )

                    possible_matches = (
                        extract_possible_matches(
                            ocr_text
                        )
                    )

                    if not possible_matches:

                        st.warning(
                            "Keine eindeutigen "
                            "Spielpaarungen gefunden."
                        )

                    else:

                        st.subheader(
                            "🎯 Erkannte Spiele"
                        )

                        all_teams = (
                            get_team_list(
                                df
                            )
                        )

                        predictions = []

                        for index, (
                            raw_home,
                            raw_away
                        ) in enumerate(
                            possible_matches
                        ):

                            st.markdown(
                                f"### Spiel {index + 1}"
                            )

                            matched_home, score_home = (
                                match_team(
                                    raw_home,
                                    all_teams
                                )
                            )

                            matched_away, score_away = (
                                match_team(
                                    raw_away,
                                    all_teams
                                )
                            )

                            c1, c2 = (
                                st.columns(2)
                            )

                            with c1:

                                st.write(
                                    f"**OCR Heim:** "
                                    f"{raw_home}"
                                )

                                if matched_home:

                                    st.success(
                                        f"{matched_home} "
                                        f"– Match "
                                        f"{score_home * 100:.0f}%"
                                    )

                                else:

                                    st.error(
                                        "Heimteam "
                                        "nicht erkannt"
                                    )

                            with c2:

                                st.write(
                                    f"**OCR Auswärts:** "
                                    f"{raw_away}"
                                )

                                if matched_away:

                                    st.success(
                                        f"{matched_away} "
                                        f"– Match "
                                        f"{score_away * 100:.0f}%"
                                    )

                                else:

                                    st.error(
                                        "Auswärtsteam "
                                        "nicht erkannt"
                                    )

                            if (
                                matched_home
                                and matched_away
                                and matched_home
                                != matched_away
                            ):

                                prediction = (
                                    model.predict(
                                        matched_home,
                                        matched_away
                                    )
                                )

                                result = (
                                    prediction[
                                        "prediction"
                                    ]
                                )

                                st.success(
                                    f"### Empfehlung: "
                                    f"**{result}**"
                                )

                                c1, c2, c3 = (
                                    st.columns(3)
                                )

                                with c1:

                                    st.metric(
                                        "1",
                                        f"{prediction['probabilities']['1'] * 100:.1f}%"
                                    )

                                with c2:

                                    st.metric(
                                        "X",
                                        f"{prediction['probabilities']['X'] * 100:.1f}%"
                                    )

                                with c3:

                                    st.metric(
                                        "2",
                                        f"{prediction['probabilities']['2'] * 100:.1f}%"
                                    )

                                predictions.append(
                                    {

                                        "Heimteam":
                                            matched_home,

                                        "Auswärtsteam":
                                            matched_away,

                                        "1":
                                            prediction[
                                                "probabilities"
                                            ]["1"],

                                        "X":
                                            prediction[
                                                "probabilities"
                                            ]["X"],

                                        "2":
                                            prediction[
                                                "probabilities"
                                            ]["2"],

                                        "Prognose":
                                            result,

                                        "Konfidenz":
                                            prediction[
                                                "confidence"
                                            ],

                                    }
                                )

                            st.divider()

                        if predictions:

                            pred_df = pd.DataFrame(
                                predictions
                            )

                            display_df = (
                                pred_df.copy()
                            )

                            for column in [
                                "1",
                                "X",
                                "2",
                                "Konfidenz"
                            ]:

                                display_df[
                                    column
                                ] = display_df[
                                    column
                                ].map(
                                    lambda x:
                                    f"{x * 100:.1f}%"
                                )

                            st.subheader(
                                "📋 Zusammenfassung"
                            )

                            st.dataframe(
                                display_df,
                                use_container_width=True,
                                hide_index=True
                            )

                            st.download_button(
                                "⬇️ Prognosen CSV",
                                data=dataframe_to_csv(
                                    pred_df
                                ),
                                file_name=(
                                    "wett_ki_prognosen.csv"
                                ),
                                mime="text/csv",
                                use_container_width=True
                            )


# ============================================================
# TAB 3 BACKTEST
# ============================================================

with tab3:

    st.subheader(
        "📈 Rolling Backtest"
    )

    st.write(
        """
        Bei diesem Backtest wird jedes Spiel nur mit den
        Daten vorheriger Spiele vorhergesagt. Das entspricht
        deutlich besser einem echten zukünftigen Einsatz.
        """
    )

    if len(df) < 30:

        st.warning(
            f"Aktuell sind nur {len(df)} Spiele vorhanden. "
            "Für einen aussagekräftigen Backtest werden "
            "deutlich mehr historische Spiele empfohlen."
        )

    if st.button(
        "📊 ROLLING BACKTEST STARTEN",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Backtest läuft..."
        ):

            result = (
                run_rolling_backtest(
                    df,
                    decay,
                    regularization
                )
            )

        if result is None:

            st.error(
                "Backtest konnte nicht durchgeführt werden."
            )

        else:

            accuracy = (
                result["accuracy"]
            )

            tested_matches = (
                result[
                    "tested_matches"
                ]
            )

            c1, c2 = (
                st.columns(2)
            )

            with c1:

                st.metric(
                    "Trefferquote",
                    f"{accuracy * 100:.2f}%"
                )

            with c2:

                st.metric(
                    "Testspiele",
                    tested_matches
                )

            backtest_df = (
                result["results"]
                .copy()
            )

            display_df = (
                backtest_df.copy()
            )

            for column in [
                "P(1)",
                "P(X)",
                "P(2)"
            ]:

                display_df[
                    column
                ] = display_df[
                    column
                ].map(
                    lambda x:
                    f"{x * 100:.1f}%"
                )

            display_df[
                "correct"
            ] = display_df[
                "correct"
            ].map(
                lambda x:
                "✅"
                if x
                else "❌"
            )

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "⬇️ Backtest CSV",
                data=dataframe_to_csv(
                    backtest_df
                ),
                file_name=(
                    "wett_ki_backtest.csv"
                ),
                mime="text/csv"
            )


# ============================================================
# TAB 4 DATEN
# ============================================================

with tab4:

    st.subheader(
        "📚 Historische Daten"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇️ matches.csv herunterladen",
        data=dataframe_to_csv(
            df
        ),
        file_name="matches.csv",
        mime="text/csv"
    )

    st.subheader(
        "CSV-Format"
    )

    st.code(
        """
date,home_team,away_team,home_goals,away_goals
2026-01-01,Bayern Munich,Dortmund,3,1
2026-01-02,Leverkusen,Frankfurt,2,0
        """.strip()
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    """
    Wett-KI | Poisson Football Predictor

    Das Modell verwendet historische Ergebnisse.
    Es berücksichtigt nicht automatisch Verletzungen,
    Aufstellungen, Sperren, Motivation, Wetter,
    Marktbewegungen oder kurzfristige Ereignisse.

    Keine Gewinn-Garantie.
    """
    )
