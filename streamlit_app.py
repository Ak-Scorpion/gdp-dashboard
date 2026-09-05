import os
import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ============================================================
# WETT-KI Live – V2.2
# - echte Quoten only
# - robuste API-Fehlerausgabe
# - dynamische The Odds API Sport-Key-Prüfung
# - Bundesliga / Champions League stärker modelliert
# - Top-5-Kombi mit Sicher / Ausgewogen / Value
# - Kombi-Größe + Reroll
# - 1X / X2 / 12, Over/Under 2.5, BTTS
# - Buchmachervergleich
# ============================================================

st.set_page_config(
    page_title="WETT-KI Live",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

FOOTBALL_DATA_URL = "https://api.football-data.org/v4"
ODDS_API_URL = "https://api.the-odds-api.com/v4"

LEAGUES = {
    "Premier League": {
        "fd": "PL",
        "odds": "soccer_epl",
    },
    "Bundesliga": {
        "fd": "BL1",
        "odds": "soccer_germany_bundesliga",
    },
    "La Liga": {
        "fd": "PD",
        "odds": "soccer_spain_la_liga",
    },
    "Serie A": {
        "fd": "SA",
        "odds": "soccer_italy_serie_a",
    },
    "Ligue 1": {
        "fd": "FL1",
        "odds": "soccer_france_ligue_one",
    },
    "Champions League": {
        "fd": "CL",
        "odds": "soccer_uefa_champs_league",
    },
    "Europa League": {
        "fd": "EL",
        "odds": "soccer_uefa_europa_league",
    },
    "Conference League": {
        "fd": "EC",
        "odds": "soccer_uefa_europa_conference_league",
    },
}


# ============================================================
# HELPERS
# ============================================================

def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        return str(value).strip() if value else ""
    except Exception:
        return ""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value):
    if not value:
        return None
    try:
        dt = pd.to_datetime(value, utc=True)
        return dt.to_pydatetime()
    except Exception:
        return None


def fmt_dt(value) -> str:
    dt = parse_dt(value)
    if not dt:
        return "—"
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")


def norm_name(name: str) -> str:
    if not name:
        return ""
    s = str(name).lower().strip()
    replacements = {
        "ö": "o", "ä": "a", "ü": "u", "ß": "ss",
        "é": "e", "è": "e", "ê": "e",
        "á": "a", "à": "a", "â": "a",
        "í": "i", "ì": "i", "î": "i",
        "ó": "o", "ò": "o", "ô": "o",
        "ú": "u", "ù": "u", "û": "u",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    for ch in [".", ",", "'", '"', "-", "_", "/", "\\", "(", ")", "[", "]"]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    aliases = {
        "fc bayern munchen": "bayern munich",
        "bayern munchen": "bayern munich",
        "paris saint germain": "psg",
        "psg": "psg",
        "inter milan": "inter",
        "internazionale": "inter",
        "manchester united": "man utd",
        "manchester city": "man city",
        "tottenham hotspur": "tottenham",
        "atletico madrid": "atletico",
        "athletic club": "athletic bilbao",
        "borussia monchengladbach": "borussia monchengladbach",
        "fc barcelona": "barcelona",
        "real madrid cf": "real madrid",
    }
    return aliases.get(s, s)


def similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    a = norm_name(a)
    b = norm_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.93
    return SequenceMatcher(None, a, b).ratio()


def safe_float(x, default=np.nan):
    try:
        return float(x)
    except Exception:
        return default


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def poisson_pmf(k: int, lam: float) -> float:
    lam = max(float(lam), 1e-6)
    return math.exp(-lam) * lam**k / math.factorial(k)


def fair_odds(prob: float):
    return round(1.0 / prob, 2) if prob and prob > 0 else None


def pct(x):
    return f"{x * 100:.1f}%" if x is not None and np.isfinite(x) else "—"


def odds_str(x):
    return f"{x:.2f}" if x is not None and np.isfinite(x) else "—"


def api_error_text(resp):
    try:
        data = resp.json()
        if isinstance(data, dict):
            if data.get("message"):
                return str(data["message"])
            if data.get("error"):
                return str(data["error"])
            if data.get("errors"):
                return str(data["errors"])
        return resp.text[:500]
    except Exception:
        return resp.text[:500]


# ============================================================
# API
# ============================================================

@st.cache_data(ttl=45, show_spinner=False)
def api_request(
    url: str,
    headers_tuple=(),
    params_tuple=(),
    timeout: int = 20,
):
    headers = dict(headers_tuple)
    params = dict(params_tuple)

    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        meta = {
            "status": r.status_code,
            "ok": r.ok,
            "url": r.url,
            "message": "" if r.ok else api_error_text(r),
            "headers": {
                "x-requests-remaining": r.headers.get("x-requests-remaining"),
                "x-requests-used": r.headers.get("x-requests-used"),
                "x-requests-last": r.headers.get("x-requests-last"),
                "x-ratelimit-remaining": r.headers.get("x-ratelimit-remaining"),
            },
        }

        try:
            data = r.json()
        except Exception:
            data = None

        return {
            "ok": r.ok,
            "status": r.status_code,
            "data": data,
            "message": meta["message"],
            "url": r.url,
            "headers": meta["headers"],
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": f"Netzwerkfehler: {exc}",
            "url": url,
            "headers": {},
        }


def football_data_get(path, token, params=None):
    if not token:
        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": "Kein FOOTBALL_DATA_TOKEN gesetzt.",
            "url": "",
            "headers": {},
        }
    return api_request(
        f"{FOOTBALL_DATA_URL}{path}",
        headers_tuple=(("X-Auth-Token", token),),
        params_tuple=tuple(sorted((params or {}).items())),
    )


def odds_get(path, api_key, params=None):
    if not api_key:
        return {
            "ok": False,
            "status": 0,
            "data": None,
            "message": "Kein ODDS_API_KEY gesetzt.",
            "url": "",
            "headers": {},
        }
    p = dict(params or {})
    p["apiKey"] = api_key
    return api_request(
        f"{ODDS_API_URL}{path}",
        params_tuple=tuple(sorted(p.items())),
    )


@st.cache_data(ttl=300, show_spinner=False)
def discover_odds_sports(api_key):
    res = odds_get("/sports", api_key)
    if not res["ok"]:
        return res, []
    sports = res["data"] if isinstance(res["data"], list) else []
    return res, sports


def resolve_active_sport_key(configured_key, sports):
    if not configured_key:
        return None

    for s in sports:
        if s.get("key") == configured_key and s.get("active", True):
            return configured_key

    # Falls ein Anbieter-Key geändert wurde: Titel/Details durchsuchen.
    target = configured_key.lower()
    for s in sports:
        blob = " ".join(
            str(s.get(k, "")) for k in ("key", "title", "description")
        ).lower()
        if target in blob and s.get("active", True):
            return s.get("key")

    return None


@st.cache_data(ttl=60, show_spinner=False)
def get_odds_for_sport(sport_key, api_key, start_dt, end_dt, include_totals=True):
    markets = "h2h,totals" if include_totals else "h2h"
    params = {
        "regions": "eu",
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
        "commenceTimeFrom": start_dt,
        "commenceTimeTo": end_dt,
    }
    res = odds_get(f"/sports/{sport_key}/odds", api_key, params)

    # Wenn ein Account/Markt keine kombinierten Markets akzeptiert,
    # h2h als sichere Rückfallebene versuchen.
    if (
        not res["ok"]
        and res["status"] == 400
        and "INVALID_MARKET" in str(res["message"]).upper()
        and include_totals
    ):
        res = odds_get(
            f"/sports/{sport_key}/odds",
            api_key,
            {
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
                "commenceTimeFrom": start_dt,
                "commenceTimeTo": end_dt,
            },
        )
        res["fallback_used"] = "h2h-only"

    return res


@st.cache_data(ttl=60, show_spinner=False)
def get_double_chance_event_odds(sport_key, event_id, api_key):
    return odds_get(
        f"/sports/{sport_key}/events/{event_id}/odds",
        api_key,
        {
            "regions": "eu",
            "markets": "double_chance",
            "oddsFormat": "decimal",
        },
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_upcoming_matches(token, competitions, date_from, date_to):
    params = {
        "competitions": ",".join(competitions),
        "dateFrom": date_from,
        "dateTo": date_to,
    }
    return football_data_get("/matches", token, params)


@st.cache_data(ttl=300, show_spinner=False)
def get_history(token, competitions, date_from, date_to):
    params = {
        "competitions": ",".join(competitions),
        "dateFrom": date_from,
        "dateTo": date_to,
        "status": "FINISHED",
    }
    return football_data_get("/matches", token, params)


# ============================================================
# FOOTBALL-DATA NORMALIZATION
# ============================================================

def normalize_match(m, league_name=None):
    score = m.get("score") or {}
    full = score.get("fullTime") or {}
    return {
        "id": str(m.get("id")),
        "competition": league_name or (m.get("competition") or {}).get("name", ""),
        "competition_code": (m.get("competition") or {}).get("code", ""),
        "utcDate": m.get("utcDate"),
        "status": m.get("status"),
        "home": (m.get("homeTeam") or {}).get("name", ""),
        "away": (m.get("awayTeam") or {}).get("name", ""),
        "home_id": str((m.get("homeTeam") or {}).get("id", "")),
        "away_id": str((m.get("awayTeam") or {}).get("id", "")),
        "home_goals": full.get("home"),
        "away_goals": full.get("away"),
    }


def make_fixture_df(data, selected_names):
    rows = []
    selected_codes = {LEAGUES[n]["fd"]: n for n in selected_names}
    for m in (data or {}).get("matches", []):
        code = (m.get("competition") or {}).get("code")
        league = selected_codes.get(code, (m.get("competition") or {}).get("name", code))
        rows.append(normalize_match(m, league))
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["dt"] = pd.to_datetime(df["utcDate"], utc=True, errors="coerce")
    df = df.sort_values("dt").reset_index(drop=True)
    return df


def make_history_df(data, selected_names):
    return make_fixture_df(data, selected_names)


# ============================================================
# MODEL
# ============================================================

def competition_profile(league):
    if league == "Bundesliga":
        return {"poisson": 0.72, "elo": 0.20, "form": 0.08, "k": 25}
    if league == "Champions League":
        return {"poisson": 0.55, "elo": 0.37, "form": 0.08, "k": 28}
    if league in ("Europa League", "Conference League"):
        return {"poisson": 0.60, "elo": 0.32, "form": 0.08, "k": 27}
    return {"poisson": 0.68, "elo": 0.24, "form": 0.08, "k": 24}


def weighted_mean(values, weights, fallback=np.nan):
    if not values:
        return fallback
    arr = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    mask = np.isfinite(arr) & np.isfinite(w) & (w > 0)
    if not mask.any():
        return fallback
    return float(np.average(arr[mask], weights=w[mask]))


def recency_weight(match_dt, reference_dt, half_life=60):
    age = max(0.0, (reference_dt - match_dt).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age / half_life)


def build_team_stats(history_df, reference_dt):
    stats = {}

    if history_df.empty:
        return stats

    for _, r in history_df.sort_values("dt").iterrows():
        if pd.isna(r.get("dt")):
            continue
        if r.get("home_goals") is None or r.get("away_goals") is None:
            continue

        hg = safe_float(r["home_goals"])
        ag = safe_float(r["away_goals"])
        if not np.isfinite(hg) or not np.isfinite(ag):
            continue

        home = r["home"]
        away = r["away"]
        league = r["competition"]
        dt = r["dt"].to_pydatetime()

        w = recency_weight(dt, reference_dt)

        for team, gf, ga, venue, points in [
            (home, hg, ag, "home", 3 if hg > ag else 1 if hg == ag else 0),
            (away, ag, hg, "away", 3 if ag > hg else 1 if hg == ag else 0),
        ]:
            key = norm_name(team)
            if key not in stats:
                stats[key] = {
                    "name": team,
                    "matches": 0.0,
                    "gf": [], "ga": [], "w": [],
                    "home_gf": [], "home_ga": [], "home_w": [],
                    "away_gf": [], "away_ga": [], "away_w": [],
                    "points": [], "points_w": [],
                    "leagues": {},
                }

            s = stats[key]
            s["matches"] += 1
            s["gf"].append(gf)
            s["ga"].append(ga)
            s["w"].append(w)
            s["points"].append(points)
            s["points_w"].append(w)

            if venue == "home":
                s["home_gf"].append(gf)
                s["home_ga"].append(ga)
                s["home_w"].append(w)
            else:
                s["away_gf"].append(gf)
                s["away_ga"].append(ga)
                s["away_w"].append(w)

            s["leagues"][league] = s["leagues"].get(league, 0) + w

    for s in stats.values():
        s["gf_avg"] = weighted_mean(s["gf"], s["w"], 1.35)
        s["ga_avg"] = weighted_mean(s["ga"], s["w"], 1.35)
        s["home_gf_avg"] = weighted_mean(s["home_gf"], s["home_w"], s["gf_avg"])
        s["home_ga_avg"] = weighted_mean(s["home_ga"], s["home_w"], s["ga_avg"])
        s["away_gf_avg"] = weighted_mean(s["away_gf"], s["away_w"], s["gf_avg"])
        s["away_ga_avg"] = weighted_mean(s["away_ga"], s["away_w"], s["ga_avg"])
        s["form"] = weighted_mean(s["points"], s["points_w"], 1.0) / 3.0
    return stats


def build_elo(history_df):
    elo = {}
    last_league = {}

    if history_df.empty:
        return elo

    for _, r in history_df.sort_values("dt").iterrows():
        hg = safe_float(r.get("home_goals"))
        ag = safe_float(r.get("away_goals"))
        if not np.isfinite(hg) or not np.isfinite(ag):
            continue

        home = norm_name(r["home"])
        away = norm_name(r["away"])
        league = r["competition"]

        elo.setdefault(home, 1500.0)
        elo.setdefault(away, 1500.0)

        prof = competition_profile(league)
        k = prof["k"]

        # moderate home advantage
        home_adv = 55.0
        expected_home = 1 / (1 + 10 ** (-((elo[home] + home_adv) - elo[away]) / 400))
        actual_home = 1.0 if hg > ag else 0.5 if hg == ag else 0.0

        # small margin-of-victory multiplier
        margin = abs(hg - ag)
        mov = 1.0 + min(margin, 3.0) * 0.12

        elo[home] += k * mov * (actual_home - expected_home)
        elo[away] -= k * mov * (actual_home - expected_home)
        last_league[home] = league
        last_league[away] = league

    return elo


def league_goal_averages(history_df, league, reference_dt):
    df = history_df[history_df["competition"] == league].copy()
    if df.empty:
        df = history_df.copy()

    vals_h, vals_a, ws = [], [], []
    for _, r in df.iterrows():
        hg = safe_float(r.get("home_goals"))
        ag = safe_float(r.get("away_goals"))
        dt = r.get("dt")
        if not np.isfinite(hg) or not np.isfinite(ag) or pd.isna(dt):
            continue
        dt = dt.to_pydatetime()
        if dt > reference_dt:
            continue
        w = recency_weight(dt, reference_dt)
        vals_h.append(hg)
        vals_a.append(ag)
        ws.append(w)

    return (
        weighted_mean(vals_h, ws, 1.45),
        weighted_mean(vals_a, ws, 1.15),
    )


def poisson_matrix(lam_h, lam_a, max_goals=8):
    mat = np.zeros((max_goals + 1, max_goals + 1))
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            mat[h, a] = poisson_pmf(h, lam_h) * poisson_pmf(a, lam_a)

    # normalize after truncation
    total = mat.sum()
    if total > 0:
        mat /= total
    return mat


def dixon_coles_adjust(matrix, lam_h, lam_a, rho=-0.07):
    # Low-score correction for 0-0, 0-1, 1-0, 1-1.
    out = matrix.copy()
    if matrix.shape[0] >= 2:
        out[0, 0] *= 1 - lam_h * lam_a * rho
        out[0, 1] *= 1 + lam_h * rho
        out[1, 0] *= 1 + lam_a * rho
        out[1, 1] *= 1 - rho
        s = out.sum()
        if s > 0:
            out /= s
    return out


def matrix_probs(mat):
    home = np.tril(mat, -1).sum()  # row home goals > away goals
    draw = np.trace(mat)
    away = np.triu(mat, 1).sum()
    over25 = sum(mat[h, a] for h in range(mat.shape[0]) for a in range(mat.shape[1]) if h + a >= 3)
    under25 = 1 - over25
    btts = sum(mat[h, a] for h in range(1, mat.shape[0]) for a in range(1, mat.shape[1]))
    return {
        "home": home,
        "draw": draw,
        "away": away,
        "over25": over25,
        "under25": under25,
        "btts_yes": btts,
        "btts_no": 1 - btts,
    }


def elo_probs(home_elo, away_elo):
    home_adv = 55.0
    x = ((home_elo + home_adv) - away_elo) / 400.0
    p_home = 1 / (1 + 10 ** (-x))

    # Convert binary Elo edge to a three-way distribution with a draw band.
    draw = 0.27 * math.exp(-abs(x) * 1.25)
    draw = clamp(draw, 0.18, 0.29)
    decisive = 1 - draw
    p_home3 = decisive * p_home
    p_away3 = decisive * (1 - p_home)
    total = p_home3 + draw + p_away3
    return {
        "home": p_home3 / total,
        "draw": draw / total,
        "away": p_away3 / total,
    }


def team_lookup(stats, team_name):
    key = norm_name(team_name)
    if key in stats:
        return stats[key]

    # fuzzy fallback
    best_key, best_score = None, 0.0
    for k in stats:
        score = similarity(team_name, k)
        if score > best_score:
            best_key, best_score = k, score

    if best_key and best_score >= 0.82:
        return stats[best_key]
    return None


def model_fixture(home, away, league, stats, elo):
    hs = team_lookup(stats, home)
    aws = team_lookup(stats, away)

    ref = competition_profile(league)
    avg_h, avg_a = league_goal_averages(
        HISTORY_DF,
        league,
        now_utc(),
    )

    if hs:
        home_attack_raw = hs["home_gf_avg"] / max(avg_h, 0.3)
        home_def_raw = hs["home_ga_avg"] / max(avg_a, 0.3)
        home_form = hs["form"]
        home_n = hs["matches"]
    else:
        home_attack_raw, home_def_raw, home_form, home_n = 1.0, 1.0, 0.5, 0

    if aws:
        away_attack_raw = aws["away_gf_avg"] / max(avg_a, 0.3)
        away_def_raw = aws["away_ga_avg"] / max(avg_h, 0.3)
        away_form = aws["form"]
        away_n = aws["matches"]
    else:
        away_attack_raw, away_def_raw, away_form, away_n = 1.0, 1.0, 0.5, 0

    # Shrink small samples toward neutral.
    def shrink(value, n, strength=8):
        return (value * n + 1.0 * strength) / (n + strength)

    ha = shrink(home_attack_raw, home_n)
    hd = shrink(home_def_raw, home_n)
    aa = shrink(away_attack_raw, away_n)
    ad = shrink(away_def_raw, away_n)

    lam_h = clamp(avg_h * ha * ad, 0.20, 4.20)
    lam_a = clamp(avg_a * aa * hd, 0.15, 3.80)

    mat = poisson_matrix(lam_h, lam_a)
    mat = dixon_coles_adjust(mat, lam_h, lam_a, rho=-0.055)
    pp = matrix_probs(mat)

    he = elo.get(norm_name(home), 1500.0)
    ae = elo.get(norm_name(away), 1500.0)
    ep = elo_probs(he, ae)

    # Form nudges, deliberately small so it cannot dominate the model.
    form_edge = home_form - away_form
    form_nudge = clamp(form_edge * 0.05, -0.05, 0.05)

    final_home = ref["poisson"] * pp["home"] + ref["elo"] * ep["home"] + ref["form"] * clamp(0.5 + form_nudge, 0.1, 0.9)
    final_draw = ref["poisson"] * pp["draw"] + ref["elo"] * ep["draw"] + ref["form"] * 0.25
    final_away = ref["poisson"] * pp["away"] + ref["elo"] * ep["away"] + ref["form"] * clamp(0.5 - form_nudge, 0.1, 0.9)

    total = final_home + final_draw + final_away
    final_home /= total
    final_draw /= total
    final_away /= total

    # Market-independent secondary markets are taken from the goal matrix.
    return {
        "home_prob": final_home,
        "draw_prob": final_draw,
        "away_prob": final_away,
        "over25_prob": pp["over25"],
        "under25_prob": pp["under25"],
        "btts_yes_prob": pp["btts_yes"],
        "btts_no_prob": pp["btts_no"],
        "dc_1x_prob": final_home + final_draw,
        "dc_x2_prob": final_draw + final_away,
        "dc_12_prob": final_home + final_away,
        "lambda_home": lam_h,
        "lambda_away": lam_a,
        "home_elo": he,
        "away_elo": ae,
        "home_matches": home_n,
        "away_matches": away_n,
    }


# ============================================================
# ODDS PARSING / MATCHING
# ============================================================

def best_fixture_match(fixture, odds_events):
    best = None
    best_score = 0.0
    fdt = parse_dt(fixture["utcDate"])

    for e in odds_events:
        eh = e.get("home_team", "")
        ea = e.get("away_team", "")
        score = (similarity(fixture["home"], eh) + similarity(fixture["away"], ea)) / 2

        edt = parse_dt(e.get("commence_time"))
        if fdt and edt:
            hours = abs((fdt - edt).total_seconds()) / 3600
            if hours <= 12:
                score += 0.06
            elif hours <= 36:
                score += 0.02
            else:
                score -= 0.05

        if score > best_score:
            best_score = score
            best = e

    return best if best_score >= 0.78 else None


def parse_h2h_bookmakers(event):
    rows = []
    for bm in event.get("bookmakers", []) or []:
        title = bm.get("title") or bm.get("key") or "Unbekannt"
        market = next((m for m in bm.get("markets", []) if m.get("key") == "h2h"), None)
        if not market:
            continue

        outcomes = {}
        for o in market.get("outcomes", []) or []:
            name = str(o.get("name", ""))
            price = safe_float(o.get("price"))
            if np.isfinite(price) and price > 1:
                outcomes[name] = price

        rows.append({
            "bookmaker": title,
            "outcomes": outcomes,
        })
    return rows


def parse_totals_bookmakers(event):
    rows = []
    for bm in event.get("bookmakers", []) or []:
        title = bm.get("title") or bm.get("key") or "Unbekannt"
        market = next((m for m in bm.get("markets", []) if m.get("key") == "totals"), None)
        if not market:
            continue

        vals = {}
        for o in market.get("outcomes", []) or []:
            name = str(o.get("name", "")).lower()
            point = safe_float(o.get("point"))
            price = safe_float(o.get("price"))
            if np.isfinite(price) and price > 1 and np.isfinite(point):
                vals[(name, round(point, 2))] = price

        rows.append({
            "bookmaker": title,
            "outcomes": vals,
        })
    return rows


def parse_double_chance_bookmakers(event_data):
    rows = []
    for bm in event_data.get("bookmakers", []) or []:
        title = bm.get("title") or bm.get("key") or "Unbekannt"
        market = next((m for m in bm.get("markets", []) if m.get("key") == "double_chance"), None)
        if not market:
            continue

        outcomes = {}
        for o in market.get("outcomes", []) or []:
            name = str(o.get("name", "")).lower().replace(" ", "")
            price = safe_float(o.get("price"))
            if not np.isfinite(price) or price <= 1:
                continue

            if name in ("home/draw", "1x", "homeordraw", "1xd"):
                key = "1X"
            elif name in ("draw/away", "x2", "draworaway", "x2"):
                key = "X2"
            elif name in ("home/away", "12", "homeoraway"):
                key = "12"
            else:
                key = str(o.get("name", ""))

            outcomes[key] = price

        if outcomes:
            rows.append({"bookmaker": title, "outcomes": outcomes})
    return rows


def h2h_price(outcomes, home, away, selection):
    if selection == "1":
        names = [home, "Home"]
    elif selection == "X":
        names = ["Draw", "Tie"]
    else:
        names = [away, "Away"]

    best = None
    for n in names:
        if n in outcomes:
            best = outcomes[n]
            break

    if best is None:
        for key, price in outcomes.items():
            nk = norm_name(key)
            if selection == "1" and similarity(home, nk) >= 0.86:
                best = price
            elif selection == "2" and similarity(away, nk) >= 0.86:
                best = price
            elif selection == "X" and nk in ("draw", "tie"):
                best = price
    return best


def build_odds_snapshot(fixtures, odds_events):
    snapshots = []

    for _, f in fixtures.iterrows():
        event = best_fixture_match(f, odds_events)
        if not event:
            continue

        h2h = parse_h2h_bookmakers(event)
        totals = parse_totals_bookmakers(event)

        best_h2h = {}
        for sel in ("1", "X", "2"):
            offers = []
            for bm in h2h:
                price = h2h_price(bm["outcomes"], f["home"], f["away"], sel)
                if price:
                    offers.append((price, bm["bookmaker"]))
            if offers:
                best_h2h[sel] = max(offers, key=lambda x: x[0])

        best_totals = {}
        for side in ("Over", "Under"):
            offers = []
            for bm in totals:
                price = bm["outcomes"].get((side.lower(), 2.5))
                if price:
                    offers.append((price, bm["bookmaker"]))
            if offers:
                best_totals[side] = max(offers, key=lambda x: x[0])

        snapshots.append({
            "fixture_id": str(f["id"]),
            "event_id": event.get("id"),
            "sport_key": event.get("sport_key"),
            "home": f["home"],
            "away": f["away"],
            "league": f["competition"],
            "commence_time": event.get("commence_time"),
            "h2h_bookmakers": h2h,
            "totals_bookmakers": totals,
            "best_h2h": best_h2h,
            "best_totals": best_totals,
        })

    return snapshots


# ============================================================
# CANDIDATES / COMBO
# ============================================================

STRATEGY_PROFILES = {
    "Sicher": {
        "prob_weight": 0.65,
        "ev_weight": 0.20,
        "odds_weight": 0.15,
        "min_prob": 0.62,
        "min_ev": 0.00,
        "max_odds": 1.80,
    },
    "Ausgewogen": {
        "prob_weight": 0.45,
        "ev_weight": 0.40,
        "odds_weight": 0.15,
        "min_prob": 0.52,
        "min_ev": 0.00,
        "max_odds": 2.50,
    },
    "Value": {
        "prob_weight": 0.25,
        "ev_weight": 0.60,
        "odds_weight": 0.15,
        "min_prob": 0.42,
        "min_ev": 0.02,
        "max_odds": 5.00,
    },
}


def candidate_score(c, profile):
    p = c["probability"]
    ev = c["ev"]
    odds = c["odds"]

    ev_norm = clamp((ev + 0.05) / 0.30, 0, 1)
    odds_component = clamp(1 / max(odds, 1.01), 0, 1)

    return (
        profile["prob_weight"] * p
        + profile["ev_weight"] * ev_norm
        + profile["odds_weight"] * odds_component
    )


def build_top_combo(candidates, strategy="Ausgewogen", legs=5, reroll=0):
    profile = STRATEGY_PROFILES[strategy]
    valid = [
        c for c in candidates
        if c["probability"] >= profile["min_prob"]
        and c["ev"] >= profile["min_ev"]
        and c["odds"] <= profile["max_odds"]
        and c["odds"] > 1.0
    ]

    for c in valid:
        c["combo_score"] = candidate_score(c, profile)

    valid.sort(
        key=lambda x: (
            x["combo_score"],
            x["probability"],
            x["ev"],
        ),
        reverse=True,
    )

    if not valid:
        return []

    # Deterministischer Reroll: nur aus dem oberen Kandidaten-Pool,
    # damit ein Reroll nicht plötzlich schwache Legs hineinzieht.
    pool_size = min(len(valid), max(legs * 3, 10))
    pool = valid[:pool_size]

    if reroll > 0:
        rng = random.Random(1000 + reroll)
        rng.shuffle(pool)
        pool.sort(
            key=lambda x: x["combo_score"] + rng.uniform(-0.035, 0.035),
            reverse=True,
        )

    selected = []
    used_matches = set()

    for c in pool:
        match_id = str(c["match_id"])
        if match_id in used_matches:
            continue
        selected.append(c)
        used_matches.add(match_id)
        if len(selected) >= legs:
            break

    return selected


def combo_stats(combo):
    if not combo:
        return None
    odds = 1.0
    p = 1.0
    for c in combo:
        odds *= c["odds"]
        p *= c["probability"]
    return {
        "odds": odds,
        "probability": p,
        "fair_odds": fair_odds(p),
    }


def make_candidates(fixtures, model_rows, odds_snapshots, dc_rows=None):
    odds_map = {x["fixture_id"]: x for x in odds_snapshots}
    dc_map = {x["fixture_id"]: x for x in (dc_rows or [])}
    candidates = []

    for _, f in fixtures.iterrows():
        fid = str(f["id"])
        o = odds_map.get(fid)
        if not o:
            continue

        m = model_rows.get(fid)
        if not m:
            continue

        for sel, label, prob_key in [
            ("1", f'{f["home"]} gewinnt', "home_prob"),
            ("X", "Unentschieden", "draw_prob"),
            ("2", f'{f["away"]} gewinnt', "away_prob"),
        ]:
            best = o["best_h2h"].get(sel)
            if not best:
                continue
            price, bookmaker = best
            prob = m[prob_key]
            ev = prob * price - 1
            candidates.append({
                "match_id": fid,
                "home": f["home"],
                "away": f["away"],
                "league": f["competition"],
                "market": "1X2",
                "selection": label,
                "probability": prob,
                "odds": price,
                "ev": ev,
                "bookmaker": bookmaker,
                "kickoff": f["utcDate"],
            })

        for side, prob_key, label in [
            ("Over", "over25_prob", "Over 2.5"),
            ("Under", "under25_prob", "Under 2.5"),
        ]:
            best = o["best_totals"].get(side)
            if not best:
                continue
            price, bookmaker = best
            prob = m[prob_key]
            ev = prob * price - 1
            candidates.append({
                "match_id": fid,
                "home": f["home"],
                "away": f["away"],
                "league": f["competition"],
                "market": "O/U 2.5",
                "selection": label,
                "probability": prob,
                "odds": price,
                "ev": ev,
                "bookmaker": bookmaker,
                "kickoff": f["utcDate"],
            })

        dc = dc_map.get(fid)
        if dc:
            for sel, prob_key, label in [
                ("1X", "dc_1x_prob", "1X"),
                ("X2", "dc_x2_prob", "X2"),
                ("12", "dc_12_prob", "12"),
            ]:
                best = dc.get("best", {}).get(sel)
                if not best:
                    continue
                price, bookmaker = best
                prob = m[prob_key]
                ev = prob * price - 1
                candidates.append({
                    "match_id": fid,
                    "home": f["home"],
                    "away": f["away"],
                    "league": f["competition"],
                    "market": "Doppelchance",
                    "selection": label,
                    "probability": prob,
                    "odds": price,
                    "ev": ev,
                    "bookmaker": bookmaker,
                    "kickoff": f["utcDate"],
                })

    return candidates


# ============================================================
# UI
# ============================================================

st.title("⚽ WETT-KI Live")
st.caption("V2.2 · echte Buchmacherquoten · Poisson + Dixon-Coles + Elo + Form")

with st.sidebar:
    st.header("⚙️ Einstellungen")

    fd_token = st.text_input(
        "FOOTBALL_DATA_TOKEN",
        value=get_secret("FOOTBALL_DATA_TOKEN"),
        type="password",
        help="Empfohlen: in .streamlit/secrets.toml hinterlegen.",
    )

    odds_key = st.text_input(
        "ODDS_API_KEY",
        value=get_secret("ODDS_API_KEY"),
        type="password",
        help="Empfohlen: in .streamlit/secrets.toml hinterlegen.",
    )

    selected_leagues = st.multiselect(
        "Ligen",
        list(LEAGUES.keys()),
        default=["Bundesliga", "Champions League", "Premier League"],
    )

    days_forward = st.slider(
        "Vorschau",
        min_value=1,
        max_value=14,
        value=7,
        help="Wie viele Tage nach vorne geladen werden.",
    )

    history_days = st.slider(
        "Historie",
        min_value=30,
        max_value=180,
        value=90,
        step=15,
        help="Mehr Historie = stabileres Elo; Recency-Gewichtung reduziert alte Spiele.",
    )

    st.divider()

    st.subheader("🎯 Kombi")
    combo_strategy = st.selectbox(
        "Kombi-Strategie",
        ["Sicher", "Ausgewogen", "Value"],
        index=1,
        help=(
            "Sicher = höhere Trefferwahrscheinlichkeit, "
            "Ausgewogen = Mix aus Sicherheit und Value, "
            "Value = stärker auf positive erwartete Rendite."
        ),
    )

    combo_legs = st.selectbox(
        "Kombi-Größe",
        [2, 3, 4, 5, 6, 7, 8],
        index=3,
    )

    if "combo_reroll" not in st.session_state:
        st.session_state.combo_reroll = 0

    if st.button("🎲 Kombi neu würfeln", use_container_width=True):
        st.session_state.combo_reroll += 1
        st.rerun()

    st.divider()

    live_dc = st.checkbox(
        "Doppelchance-Quoten live abrufen",
        value=False,
        help="Verbraucht zusätzliche Odds-API-Credits, da Doppelchance eventweise abgefragt wird.",
    )

    dc_limit = st.number_input(
        "Max. Spiele für Live-Doppelchance",
        min_value=1,
        max_value=20,
        value=5,
        disabled=not live_dc,
    )

    load = st.button("🔄 Daten aktualisieren", use_container_width=True)

if not selected_leagues:
    st.info("Bitte mindestens eine Liga auswählen.")
    st.stop()

if not fd_token or not odds_key:
    st.warning(
        "Bitte beide API-Keys setzen. Für produktiven Betrieb am besten "
        "FOOTBALL_DATA_TOKEN und ODDS_API_KEY in `.streamlit/secrets.toml` speichern."
    )
    st.stop()

if load:
    st.cache_data.clear()
    st.session_state.combo_reroll = 0
    st.rerun()


# ============================================================
# LOAD DATA
# ============================================================

today = now_utc()
start_future = today
end_future = today + timedelta(days=days_forward)
hist_start = today - timedelta(days=history_days)

future_from = start_future.strftime("%Y-%m-%d")
future_to = end_future.strftime("%Y-%m-%d")
hist_from = hist_start.strftime("%Y-%m-%d")
hist_to = today.strftime("%Y-%m-%d")

codes = [LEAGUES[n]["fd"] for n in selected_leagues]

with st.spinner("⚽ Lade Spielplan, Historie und echte Quoten …"):
    future_res = get_upcoming_matches(fd_token, codes, future_from, future_to)
    history_res = get_history(fd_token, codes, hist_from, hist_to)

if not future_res["ok"]:
    st.error(
        f"Football-Data Spielplan: HTTP {future_res['status']} · "
        f"{future_res['message']}"
    )
    st.stop()

if not history_res["ok"]:
    st.warning(
        f"Football-Data Historie: HTTP {history_res['status']} · "
        f"{history_res['message']}"
    )

FIXTURES_DF = make_fixture_df(future_res["data"], selected_leagues)
HISTORY_DF = make_history_df(history_res["data"], selected_leagues)

if FIXTURES_DF.empty:
    st.info("Keine kommenden Spiele im gewählten Zeitraum gefunden.")
    st.stop()

# Nur echte zukünftige Spiele.
FIXTURES_DF = FIXTURES_DF[
    FIXTURES_DF["dt"].notna() & (FIXTURES_DF["dt"] >= pd.Timestamp(today))
].copy()

if FIXTURES_DF.empty:
    st.info("Keine zukünftigen Spiele verfügbar.")
    st.stop()


# ============================================================
# ODDS DISCOVERY + LOAD
# ============================================================

sports_res, sports = discover_odds_sports(odds_key)

if not sports_res["ok"]:
    st.error(
        f"The Odds API /sports: HTTP {sports_res['status']} · "
        f"{sports_res['message']}"
    )
    st.stop()

odds_events_all = []
odds_errors = []

for league in selected_leagues:
    configured_key = LEAGUES[league]["odds"]
    active_key = resolve_active_sport_key(configured_key, sports)

    if not active_key:
        odds_errors.append({
            "Liga": league,
            "Sport-Key": configured_key,
            "Status": "nicht aktiv/verfügbar",
            "Fehler": "Sport-Key wurde von /v4/sports nicht als aktiver Sport zurückgegeben.",
        })
        continue

    res = get_odds_for_sport(
        active_key,
        odds_key,
        today.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_future.strftime("%Y-%m-%dT%H:%M:%SZ"),
        include_totals=True,
    )

    if not res["ok"]:
        odds_errors.append({
            "Liga": league,
            "Sport-Key": active_key,
            "Status": f"HTTP {res['status']}",
            "Fehler": res["message"],
        })
        continue

    events = res["data"] if isinstance(res["data"], list) else []
    for e in events:
        e["_configured_league"] = league
        odds_events_all.append(e)


# ============================================================
# MODEL + MATCH ODDS
# ============================================================

TEAM_STATS = build_team_stats(HISTORY_DF, today)
ELO = build_elo(HISTORY_DF)

model_rows = {}
for _, f in FIXTURES_DF.iterrows():
    model_rows[str(f["id"])] = model_fixture(
        f["home"],
        f["away"],
        f["competition"],
        TEAM_STATS,
        ELO,
    )

odds_snapshots = build_odds_snapshot(FIXTURES_DF, odds_events_all)

# Optional live DC.
dc_rows = []
if live_dc:
    snapshot_by_id = {x["fixture_id"]: x for x in odds_snapshots}
    for _, f in FIXTURES_DF.head(int(dc_limit)).iterrows():
        fid = str(f["id"])
        snap = snapshot_by_id.get(fid)
        if not snap or not snap.get("event_id") or not snap.get("sport_key"):
            continue

        dc_res = get_double_chance_event_odds(
            snap["sport_key"],
            snap["event_id"],
            odds_key,
        )
        if not dc_res["ok"]:
            odds_errors.append({
                "Liga": f["competition"],
                "Sport-Key": snap["sport_key"],
                "Status": f"HTTP {dc_res['status']}",
                "Fehler": f"Doppelchance {f['home']} – {f['away']}: {dc_res['message']}",
            })
            continue

        rows = parse_double_chance_bookmakers(dc_res["data"] or {})
        best = {}
        for sel in ("1X", "X2", "12"):
            offers = [
                (r["outcomes"][sel], r["bookmaker"])
                for r in rows if sel in r["outcomes"]
            ]
            if offers:
                best[sel] = max(offers, key=lambda x: x[0])

        if best:
            dc_rows.append({"fixture_id": fid, "best": best, "bookmakers": rows})


candidates = make_candidates(
    FIXTURES_DF,
    model_rows,
    odds_snapshots,
    dc_rows,
)

top_combo = build_top_combo(
    candidates,
    strategy=combo_strategy,
    legs=combo_legs,
    reroll=st.session_state.combo_reroll,
)

combo_info = combo_stats(top_combo)


# ============================================================
# TOP VALUE
# ============================================================

st.subheader("🔥 Top Value")

if candidates:
    value_df = pd.DataFrame(candidates)
    value_df["EV"] = value_df["ev"] * 100
    value_df["Wahrscheinlichkeit"] = value_df["probability"] * 100
    value_df = value_df.sort_values(
        ["EV", "Wahrscheinlichkeit"],
        ascending=False,
    ).head(10)

    cols = st.columns(min(5, len(value_df)))
    for i, (_, r) in enumerate(value_df.iterrows()):
        with cols[i % len(cols)]:
            st.metric(
                label=f"{r['selection']} · {r['home']} – {r['away']}",
                value=f"@ {r['odds']:.2f}",
                delta=f"EV {r['EV']:+.1f}%",
            )
            st.caption(
                f"{r['league']} · Modell {r['Wahrscheinlichkeit']:.1f}% · "
                f"{r['bookmaker']}"
            )
else:
    st.info(
        "Keine Value-Kandidaten mit echten Buchmacherquoten gefunden. "
        "Es werden bewusst keine Fake-/Fallback-Quoten verwendet."
    )


# ============================================================
# TABS
# ============================================================

tab_combo, tab_markets, tab_books, tab_model, tab_debug = st.tabs(
    ["🎟️ Top-Kombi", "📈 Märkte", "🏦 Buchmacher", "🤖 Modell", "🧾 Debug"]
)


with tab_combo:
    st.subheader(f"🎟️ Top-{combo_legs}-Kombi · {combo_strategy}")

    profile = STRATEGY_PROFILES[combo_strategy]
    st.caption(
        f"Filter: ≥ {profile['min_prob']*100:.0f}% Modellwahrscheinlichkeit · "
        f"EV ≥ {profile['min_ev']*100:.0f}% · "
        f"Quote ≤ {profile['max_odds']:.2f} · "
        f"max. 1 Tipp pro Spiel"
    )

    if not top_combo:
        st.warning(
            "Für diese Strategie konnten nicht genug geeignete Legs gefunden werden. "
            "Versuche „Ausgewogen“ oder „Value“, erweitere den Zeitraum oder wähle mehr Ligen."
        )
    else:
        for i, c in enumerate(top_combo, 1):
            c1, c2, c3, c4, c5 = st.columns([0.6, 3.0, 1.2, 1.2, 1.3])
            c1.write(f"**{i}**")
            c2.write(
                f"**{c['selection']}**  \n"
                f"{c['home']} – {c['away']} · {c['league']}"
            )
            c3.metric("Quote", f"{c['odds']:.2f}")
            c4.metric("Modell", pct(c["probability"]))
            c5.metric("EV", f"{c['ev']*100:+.1f}%")
            st.caption(f"Buchmacher: {c['bookmaker']} · Anstoß: {fmt_dt(c['kickoff'])}")

        if combo_info:
            st.divider()
            a, b, c = st.columns(3)
            a.metric("Gesamtquote", f"{combo_info['odds']:.2f}")
            b.metric("Modell-Kombi-Wahrscheinlichkeit", pct(combo_info["probability"]))
            c.metric("Modell-Fair-Quote", odds_str(combo_info["fair_odds"]))

            st.caption(
                "Die Kombi-Wahrscheinlichkeit ist eine vereinfachte Multiplikation der "
                "Einzelwahrscheinlichkeiten und setzt Unabhängigkeit der Legs voraus. "
                "In der Realität sind Fußballmärkte nicht vollständig unabhängig."
            )


with tab_markets:
    st.subheader("📈 Marktübersicht")

    market_rows = []
    snap_map = {x["fixture_id"]: x for x in odds_snapshots}

    for _, f in FIXTURES_DF.iterrows():
        fid = str(f["id"])
        m = model_rows.get(fid)
        snap = snap_map.get(fid)
        if not m:
            continue

        market_rows.append({
            "Liga": f["competition"],
            "Spiel": f"{f['home']} – {f['away']}",
            "Anstoß": fmt_dt(f["utcDate"]),
            "1": pct(m["home_prob"]),
            "X": pct(m["draw_prob"]),
            "2": pct(m["away_prob"]),
            "1X": pct(m["dc_1x_prob"]),
            "X2": pct(m["dc_x2_prob"]),
            "12": pct(m["dc_12_prob"]),
            "Over 2.5": pct(m["over25_prob"]),
            "Under 2.5": pct(m["under25_prob"]),
            "BTTS Ja": pct(m["btts_yes_prob"]),
            "BTTS Nein": pct(m["btts_no_prob"]),
            "λ Heim": f"{m['lambda_home']:.2f}",
            "λ Gast": f"{m['lambda_away']:.2f}",
            "Echte Quoten": "Ja" if snap else "Nein",
        })

    if market_rows:
        st.dataframe(
            pd.DataFrame(market_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Keine Modelldaten verfügbar.")


with tab_books:
    st.subheader("🏦 Buchmachervergleich")

    if not odds_snapshots:
        st.info("Keine echten Buchmacherquoten für die gefundenen Spiele verfügbar.")
    else:
        all_rows = []

        for s in odds_snapshots:
            for bm in s["h2h_bookmakers"]:
                for sel, label in [("1", "1"), ("X", "X"), ("2", "2")]:
                    price = h2h_price(
                        bm["outcomes"],
                        s["home"],
                        s["away"],
                        sel,
                    )
                    if price:
                        all_rows.append({
                            "Liga": s["league"],
                            "Spiel": f"{s['home']} – {s['away']}",
                            "Markt": "1X2",
                            "Auswahl": label,
                            "Buchmacher": bm["bookmaker"],
                            "Quote": price,
                        })

            for bm in s["totals_bookmakers"]:
                for side in ("Over", "Under"):
                    price = bm["outcomes"].get((side.lower(), 2.5))
                    if price:
                        all_rows.append({
                            "Liga": s["league"],
                            "Spiel": f"{s['home']} – {s['away']}",
                            "Markt": "O/U 2.5",
                            "Auswahl": side,
                            "Buchmacher": bm["bookmaker"],
                            "Quote": price,
                        })

        if all_rows:
            bdf = pd.DataFrame(all_rows)
            bdf = bdf.sort_values(
                ["Spiel", "Markt", "Auswahl", "Quote"],
                ascending=[True, True, True, False],
            )
            st.dataframe(
                bdf,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "Die API liefert für diese Spiele keine verwertbaren h2h/totals-Quoten."
            )

        if dc_rows:
            st.divider()
            st.subheader("Doppelchance – echte Quoten")
            dc_display = []
            for d in dc_rows:
                snap = snap_map.get(d["fixture_id"])
                if not snap:
                    continue
                for sel, pair in d["best"].items():
                    dc_display.append({
                        "Spiel": f"{snap['home']} – {snap['away']}",
                        "Auswahl": sel,
                        "Buchmacher": pair[1],
                        "Quote": pair[0],
                    })
            if dc_display:
                st.dataframe(pd.DataFrame(dc_display), use_container_width=True, hide_index=True)
        else:
            st.caption(
                "Doppelchance wird hier nur als echte Buchmacherquote angezeigt, "
                "wenn der Live-DC-Schalter aktiviert wurde. Sonst sind 1X/X2/12 "
                "im Markt-Tab reine Modellwahrscheinlichkeiten/Fair-Quoten."
            )


with tab_model:
    st.subheader("🤖 Modell")

    model_display = []
    for _, f in FIXTURES_DF.iterrows():
        fid = str(f["id"])
        m = model_rows.get(fid)
        if not m:
            continue

        best = max(
            [
                ("1", m["home_prob"]),
                ("X", m["draw_prob"]),
                ("2", m["away_prob"]),
            ],
            key=lambda x: x[1],
        )

        model_display.append({
            "Liga": f["competition"],
            "Spiel": f"{f['home']} – {f['away']}",
            "Top-Prognose": best[0],
            "Top-Wahrscheinlichkeit": f"{best[1]*100:.1f}%",
            "1": f"{m['home_prob']*100:.1f}%",
            "X": f"{m['draw_prob']*100:.1f}%",
            "2": f"{m['away_prob']*100:.1f}%",
            "Over 2.5": f"{m['over25_prob']*100:.1f}%",
            "Under 2.5": f"{m['under25_prob']*100:.1f}%",
            "BTTS": f"{m['btts_yes_prob']*100:.1f}%",
            "λ": f"{m['lambda_home']:.2f} : {m['lambda_away']:.2f}",
            "Elo": f"{m['home_elo']:.0f} : {m['away_elo']:.0f}",
            "Historie H/G": f"{m['home_matches']:.0f}/{m['away_matches']:.0f}",
        })

    if model_display:
        st.dataframe(
            pd.DataFrame(model_display),
            use_container_width=True,
            hide_index=True,
        )

    st.info(
        "Modellkern: recency-gewichtete Heim-/Auswärtsdaten, Poisson-Tore, "
        "Dixon-Coles-Korrektur für niedrige Spielstände, sequenzielles Elo und "
        "eine kleine Form-Komponente. Bundesliga und europäische Wettbewerbe "
        "bekommen eigene Gewichtungen; kleine Stichproben werden Richtung neutral "
        "geschrumpft."
    )


with tab_debug:
    st.subheader("🧾 Debug / API-Status")

    st.write("**Football-Data Spielplan**")
    st.json({
        "status": future_res["status"],
        "ok": future_res["ok"],
        "message": future_res["message"],
        "url": future_res["url"],
        "matches": len((future_res.get("data") or {}).get("matches", []))
        if isinstance(future_res.get("data"), dict) else None,
    })

    st.write("**Football-Data Historie**")
    st.json({
        "status": history_res["status"],
        "ok": history_res["ok"],
        "message": history_res["message"],
        "url": history_res["url"],
        "matches": len((history_res.get("data") or {}).get("matches", []))
        if isinstance(history_res.get("data"), dict) else None,
    })

    st.write("**The Odds API /sports**")
    st.json({
        "status": sports_res["status"],
        "ok": sports_res["ok"],
        "message": sports_res["message"],
        "url": sports_res["url"],
        "active_sports": len([s for s in sports if s.get("active", True)]),
    })

    if odds_errors:
        st.warning("Fehler beim Quotenabruf")
        st.dataframe(
            pd.DataFrame(odds_errors),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("Keine API-Fehler beim Quotenabruf.")

    st.write("**Quoten-Matching**")
    st.metric("Football-Data Spiele", len(FIXTURES_DF))
    st.metric("Spiele mit echten Odds", len(odds_snapshots))
    st.metric("Value-Kandidaten", len(candidates))
    st.metric("Kombi-Legs", len(top_combo))

    if odds_snapshots:
        remaining = []
        used = []
        for s in odds_snapshots:
            # Quoten-Responses tragen die Header nicht hierher; daher nur Hinweis.
            pass
        st.caption(
            "Wichtig: Die genaue HTTP-Fehlermeldung wird jetzt aus dem Response-Body "
            "angezeigt. Bei HTTP 400 bitte zuerst den hier sichtbaren Fehlertext und "
            "den aktiven Sport-Key prüfen."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption(
    "⚠️ WETT-KI ist eine statistische Analyse und keine Gewinn-Garantie. "
    "Value/EV basiert auf Modellwahrscheinlichkeiten und kann falsch sein. "
    "Nur echte, von der Odds-API gelieferte Quoten werden für Wettkandidaten verwendet."
)

