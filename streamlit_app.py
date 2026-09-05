import streamlit as st
import requests
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

# ============================================================
# KONFIGURATION
# ============================================================

st.set_page_config(
    page_title="KI Fußballanalyse",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

FOOTBALL_API_BASE = "https://v3.football.api-sports.io"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Bekannte Odds-API Fußball-Sportkeys.
# Die App versucht diese nacheinander.
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
    "Bet-at-home": ["bet-at-home", "bet at home", "betathome"],
}

MARKET_LABELS = {
    "Doppelte Chance": "double_chance",
    "Über 1.5 Tore": "over_1_5",
    "Über 2.5 Tore": "over_2_5",
    "Beide Teams treffen": "btts",
    "1X2": "h2h",
}

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
            color: #00
