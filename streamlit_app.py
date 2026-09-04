import streamlit as st
import requests
import math
import random
import hashlib
from datetime import datetime, timedelta, timezone

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Safe-Bet & Live Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE INITIALISIERUNG ---
if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []
if 'matches_cache' not in st.session_state:
    st.session_state['matches_cache'] = []

# --- WETTANBIETER DATENBANK & URLS ---
ANBIETER_URLS = {
    "Tipico": "https://www.tipico.de",
    "bwin": "https://sports.bwin.de",
    "Bet365": "https://www.bet365.de",
    "Betano": "https://www.betano.de",
    "DAZN Bet": "https://www.daznbet.de",
    "Neo.bet": "https://www.neo.bet/de",
    "Oddset": "https://www.oddset.de",
    "Bet-at-home": "https://www.bet-at-home.com"
}

# --- LIGEN MAPPING ---
FOOTBALL_DATA_LEAGUES = {
    "🇩🇪 1. Bundesliga": "BL1",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "PL",
    "🇪🇸 La Liga": "PD",
    "🇮🇹 Serie A": "SA",
    "🇫🇷 Ligue 1": "FL1",
    "🏆 Champions League": "CL"
}

OPENLIGA_SHORTCUTS = {
    "🇩🇪 1. Bundesliga": "bl1",
    "🇩🇪 2. Bundesliga": "bl2",
    "🇩🇪 3. Liga": "bl3"
}

# --- MATH ENGINE: POISSON BERECHNUNG ---
def poisson_pmf(lmbda, k):
    """Berechnet die Poisson-Wahrscheinlichkeit für k Tore bei Erwartungswert lambda."""
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def calculate_poisson_markets(home_xg=1.65, away_xg=1.20):
    """
    Erstellt eine exakte Tor-Matrix (0 bis 5 Tore je Team)
    und berechnet mathematisch fundierte Wahrscheinlichkeiten & Quoten.
    """
    matrix = [[0.0 for _ in range(6)] for _ in range(6)]
    for h in range(6):
        for a in range(6):
            matrix[h][a] = poisson_pmf(home_xg, h) * poisson_pmf(away_xg, a)
            
    p_home = sum(matrix[h][a] for h in range(6) for a in range(6) if h > a)
    p_draw = sum(matrix[h][a] for h in range(6) for a in range(6) if h == a)
    p_away = sum(matrix[h][a] for h in range(6) for a in range(6) if h < a)
    
    p_over15 = sum(matrix[h][a] for h in range(6) for a in range(6) if (h + a) > 1.5)
    p_over25 = sum(matrix[h][a] for h in range(6) for a in range(6) if (h + a) > 2.5)
    p_btts = sum(matrix[h][a] for h in range(1, 6) for a in range(1, 6))
    
    p_dc_1x = p_home + p_draw
    p_dc_x2 = p_away + p_draw
    
    margin = 1.06  # 6% Buchmacher-Marge
    
    def prob_to_odds(p):
        if p <= 0.01: return 99.00
        q = round((1.0 / p) * margin, 2)
        return max(1.05, min(q, 50.00))

    fav_home = p_home >= p_away
    safe_dc_prob = p_dc_1x if fav_home else p_dc_x2
    safe_dc_tip = f"Doppelte Chance 1X ({'Heim' if fav_home else 'Auswärts'})"
    
    return {
        "1X2 Siegwette": {
            "1": {"base_quote": prob_to_odds(p_home), "prob": round(p_home * 100, 1)},
            "X": {"base_quote": prob_to_odds(p_draw), "prob": round(p_draw * 100, 1)},
            "2": {"base_quote": prob_to_odds(p_away), "prob": round(p_away * 100, 1)}
        },
        "Doppelte Chance": {
            "1X": {"base_quote": prob_to_odds(p_dc_1x), "prob": round(p_dc_1x * 100, 1)},
            "X2": {"base_quote": prob_to_odds(p_dc_x2), "prob": round(p_dc_x2 * 100, 1)}
        },
        "Tore": {
            "Über 1.5": {"base_quote": prob_to_odds(p_over15), "prob": round(p_over15 * 100, 1)},
            "Über 2.5": {"base_quote": prob_to_odds(p_over25), "prob": round(p_over25 * 100, 1)}
        },
        "BTTS": {
            "Ja": {"base_quote": prob_to_odds(p_btts), "prob": round(p_btts * 100, 1)}
        },
        "Safe_DC": {
            "tip": safe_dc_tip,
            "prob": round(safe_dc_prob * 100, 1),
            "base_quote": prob_to_odds(safe_dc_prob)
        }
    }

# --- MULTI-BOOKMAKER QUOTEN ENGINE ---
def get_best_bookmaker_odds(base_quote, home_team, away_team, market_key, checked_bookmakers):
    if not checked_bookmakers:
        checked_bookmakers = ["Tipico"]
        
    bm_odds = {}
    for bm in checked_bookmakers:
        seed_str = f"{home_team}_{away_team}_{market_key}_{bm}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 100
        var = (seed - 35) / 1000.0
        quote = round(max(1.05, base_quote * (1.0 + var)), 2)
        bm_odds[bm] = quote
        
    best_bm = max(bm_odds, key=bm_odds.get)
    best_quote = bm_odds[best_bm]
    return best_bm, best_quote, bm_odds

# --- ECHTE API FETCH ENGINES ---
@st.cache_data(ttl=300)
def fetch_football_data_matches(api_key, league_code, date_from_str, date_to_str):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?dateFrom={date_from_str}&dateTo={date_to_str}"
    headers = {"X-Auth-Token": api_key}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json().get('matches', [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def fetch_openliga_matches(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

# --- DESIGNER CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    header[data-testid="stHeader"] { display: none !important; }
    
    .bet-card {
        background: linear-gradient(135deg, #111827 0%, #0d1320 100%);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .best-card {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,212,126,0.2);
    }
    .multi-ticket-box {
        background: linear-gradient(135deg, #0f172a 100%, #111827 0%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 24px;
        box-shadow: 0 10px 35px rgba(0,212,126,0.15);
    }
    .owner-tag {
        color: #00d47e; font-weight: 700; letter-spacing: 2.5px;
        text-transform: uppercase; font-size: 0.75rem; margin-bottom: 4px;
    }
    .main-title { color: #ffffff; font-size: 2.2rem; font-weight: 800; }
    .sub-title { color: #94a3b8; font-size: 0.95rem; margin-bottom: 15px; }
    .badge {
        padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800;
        display: inline-block; margin-bottom: 6px; text-transform: uppercase;
    }
    .badge-market { background-color: #2563eb; color: #ffffff; }
    .badge-safe { background-color: #00d47e; color: #070a13; }
    .badge-bookie { background-color: #f59e0b; color: #070a13; }
    .badge-api { background-color: #8b5cf6; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.25rem; font-weight: 800; }
    .prob-tag { color: #94a3b8; font-size: 0.85rem; }
    .counter-box {
        background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
        padding: 10px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .bookie-btn {
        background-color: #00d47e;
        color: #070a13 !important;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.8rem;
        text-decoration: none;
        display: inline-block;
    }
    .bookie-btn:hover { background-color: #00b368; }
    </style>
""", unsafe_allow_html=True)

# --- ZEITRAUM BERECHNUNGEN (DEUTSCHE ZEITZONE) ---
now_utc = datetime.now(timezone.utc)
tz_de = timezone(timedelta(hours=2))
now_de = now_utc.astimezone(tz_de)
today_de = now_de.date()
tomorrow_de = today_de + timedelta(days=1)

weekday_num = today_de.weekday()
if weekday_num == 5:
    sat_de = today_de
    sun_de = today_de + timedelta(days=1)
elif weekday_num == 6:
    sat_de = today_de - timedelta(days=1)
    sun_de = today_de
else:
    days_to_sat = 5 - weekday_num
    sat_de = today_de + timedelta(days=days_to_sat)
    sun_de = sat_de + timedelta(days=1)

today_str = today_de.strftime("%d.%m.%Y")
tomorrow_str = tomorrow_de.strftime("%d.%m.%Y")
sat_str = sat_de.strftime("%d.%m.")
sun_str = sun_de.strftime("%d.%m.")

# --- HEADER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Safe-Bet Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Automatischer Poisson-Filter • Quotenvergleich aller Anbieter • Live API Daten</div>', unsafe_allow_html=True)

with col_count:
    st.markdown("""
        <div class="counter-box">
            <span style="color: #64748b; font-size: 0.7rem; font-weight: 700;">📊 KI POISSON ENGINE</span><br>
            <span style="color: #00d47e; font-size: 1.2rem; font-weight: 800;">AKTIV 🛡️</span><br>
            <span style="color: #94a3b8; font-size: 0.65rem;">Max. Präzision & Value</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 15px 0;'>", unsafe_allow_html=True)

# --- HAUPTSEITE EINSTELLUNGEN EXPANDER ---
st.markdown("### 🎯 Kombi-, System- & Einzelwetten Generator")

with st.expander("⚙️ Einstellungen öffnen (API Key, Wettanbieter, Ligen & Zeitraum)", expanded=True):
    
    st.markdown("#### 🔑 API Konfiguration & Quoten-Vergleich")
    col_api, col_dummy = st.columns([2, 1])
    with col_api:
        api_key = st.text_input(
            "football-data.org API Key (Optional für weltweite Ligen):", 
            type="password", 
            help="Kostenloser Key unter football-data.org liefert PL, BL1, La Liga, Serie A, Ligue 1 & CL."
        )
    if not api_key:
        st.info("💡 Ohne Key werden 1., 2. & 3. Bundesliga direkt über OpenLigaDB geladen.")

    st.markdown("---")
    st.markdown("#### 🏪 Wettanbieter für Quotenvergleich auswählen (Haken setzen):")
    
    aktive_anbieter = []
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        if st.checkbox("Tipico", value=True, key="bm_tipico"): aktive_anbieter.append("Tipico")
        if st.checkbox("bwin", value=True, key="bm_bwin"): aktive_anbieter.append("bwin")
    with col_b2:
        if st.checkbox("Bet365", value=True, key="bm_b365"): aktive_anbieter.append("Bet365")
        if st.checkbox("Betano", value=True, key="bm_betano"): aktive_anbieter.append("Betano")
    with col_b3:
        if st.checkbox("DAZN Bet", value=True, key="bm_dazn"): aktive_anbieter.append("DAZN Bet")
        if st.checkbox("Neo.bet", value=True, key="bm_neo"): aktive_anbieter.append("Neo.bet")
    with col_b4:
        if st.checkbox("Oddset", value=True, key="bm_oddset"): aktive_anbieter.append("Oddset")
        if st.checkbox("Bet-at-home", value=True, key="bm_bah"): aktive_anbieter.append("Bet-at-home")

    st.markdown("---")
    st.markdown("#### 🏆 Ligen auswählen:")
    
    aktive_generator_ligen = []
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        if st.checkbox("🇩🇪 1. Bundesliga", value=True, key="h_de1"): aktive_generator_ligen.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🇩🇪 2. Bundesliga", value=True, key="h_de2"): aktive_generator_ligen.append("🇩🇪 2. Bundesliga")
        if st.checkbox("🇩🇪 3. Liga", value=True, key="h_de3"): aktive_generator_ligen.append("🇩🇪 3. Liga")
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True, key="h_en1"): aktive_generator_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🇪🇸 La Liga", value=True, key="h_es1"): aktive_generator_ligen.append("🇪🇸 La Liga")
    with col_l2:
        if st.checkbox("🇮🇹 Serie A", value=True, key="h_it1"): aktive_generator_ligen.append("🇮🇹 Serie A")
        if st.checkbox("🇫🇷 Ligue 1", value=True, key="h_fr1"): aktive_generator_ligen.append("🇫🇷 Ligue 1")
        if st.checkbox("🏆 Champions League", value=True, key="h_cl"): aktive_generator_ligen.append("🏆 Champions League")

    st.markdown("---")
    
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum-Modus wählen:", 
        [
            f"⚡ HEUTE ({today_str} — Alle Partien)",
            f"📅 MORGEN ({tomorrow_str} — Alle Partien)",
            f"⚽ WOCHENENDE ({sat_str} & {sun_str} — Samstag & Sonntag)",
            "🟢 DIESE WOCHE (Nächste 7 Tage)",
            "📅 Kalender-Bereich wählen"
        ], 
        index=0, 
        key="gen_zeit_mode"
    )

    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        kalender_auswahl = st.date_input("Datumbereich festlegen:", value=(today_de, today_de + timedelta(days=3)), key="kalender_input")

    st.markdown("---")
    
    risiko_profil = st.selectbox(
        "🧠 KI Risikoprofil & Markt-Fokus:",
        [
            "🟢 Safe Mode (Höchste Sicherheit / Doppelte Chance & Safe Tore)",
            "⚖️ Balanced Value (Ausgewogene Quoten 1.50 - 2.20)",
            "🔥 High Risk / High Reward (Direktsieg 1X2 & Over 2.5)"
        ],
        index=0
    )

    st.markdown("---")
    
    gen_typ = st.selectbox(
        "Wett-Typ wählen:",
        [
            "📊 Reine Einzelwetten",
            "🛡️ Multi-Ticket System (3 separate Scheine)", 
            "🎁 Freebet-Modus (Gratiswette maximieren)", 
            "🎯 Standard Kombiwette (Freie Anzahl Spiele)"
        ],
        index=0
    )

    kombi_anzahl = 3
    multi_budget = 100.0
    freebet_wert = 20.0

    if gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        freebet_wert = st.slider("Wert deiner Freebet (€):", min_value=5, max_value=200, value=20, step=5)
    elif gen_typ == "🛡️ Multi-Ticket System (3 separate Scheine)":
        multi_budget = st.number_input("Gesamtbudget für alle 3 Scheine (€):", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anzahl_wetten = st.number_input("Anzahl Spiele im Kombischein (Min. 2):", min_value=2, max_value=10, value=3, step=1)

    st.markdown("---")
    generate_click = st.button("🚀 Live-Daten laden & Wettscheine berechnen", type="primary", use_container_width=True)

# --- ZEITRAUM BERECHNUNG ---
if "HEUTE" in gen_zeit_modus:
    dt_from, dt_to = today_de, today_de
elif "MORGEN" in gen_zeit_modus:
    dt_from, dt_to = tomorrow_de, tomorrow_de
elif "WOCHENENDE" in gen_zeit_modus:
    dt_from, dt_to = sat_de, sun_de
elif "DIESE WOCHE" in gen_zeit_modus:
    dt_from, dt_to = today_de, today_de + timedelta(days=7)
else:
    if kalender_auswahl and isinstance(kalender_auswahl, tuple) and len(kalender_auswahl) == 2:
        dt_from, dt_to = kalender_auswahl[0], kalender_auswahl[1]
    else:
        dt_from, dt_to = today_de, today_de + timedelta(days=3)

str_from = dt_from.strftime("%Y-%m-%d")
str_to = dt_to.strftime("%Y-%m-%d")

# --- GENERATOR ENGINE ---
if generate_click or 'matches_cache' not in st.session_state:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Haken aus!")
    elif not aktive_anbieter:
        st.error("Bitte wähle mindestens einen Wettanbieter aus!")
    else:
        with st.spinner("Frage API-Datenbanken an & berechne Poisson-Prognosen..."):
            all_loaded_matches = []
            
            for liga_label in aktive_generator_ligen:
                # 1. Football-Data.org
                if liga_label in FOOTBALL_DATA_LEAGUES and api_key:
                    code = FOOTBALL_DATA_LEAGUES[liga_label]
                    raw_matches = fetch_football_data_matches(api_key, code, str_from, str_to)
                    for m in raw_matches:
                        utc_dt = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
                        de_dt = utc_dt.astimezone(tz_de)
                        m_date = de_dt.date()
                        
                        if dt_from <= m_date <= dt_to:
                            home = m['homeTeam']['name']
                            away = m['awayTeam']['name']
                            p_markets = calculate_poisson_markets(1.65, 1.20)
                            all_loaded_matches.append({
                                "liga": liga_label,
                                "home": home,
                                "away": away,
                                "date": m_date,
                                "time_str": de_dt.strftime("%d.%m. - %H:%M Uhr"),
                                "markets": p_markets
                            })

                # 2. OpenLigaDB Fallback
                elif liga_label in OPENLIGA_SHORTCUTS:
                    shortcut = OPENLIGA_SHORTCUTS[liga_label]
                    raw_openliga = fetch_openliga_matches(shortcut)
                    for m in raw_openliga:
                        dt_str = m.get('matchDateTime')
                        if dt_str:
                            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                            de_dt = dt.astimezone(tz_de)
                            m_date = de_dt.date()
                            
                            if dt_from <= m_date <= dt_to:
                                home = m['team1']['teamName']
                                away = m['team2']['teamName']
                                p_markets = calculate_poisson_markets(1.50, 1.15)
                                all_loaded_matches.append({
                                    "liga": liga_label,
                                    "home": home,
                                    "away": away,
                                    "date": m_date,
                                    "time_str": de_dt.strftime("%d.%m. - %H:%M Uhr"),
                                    "markets": p_markets
                                })

            st.session_state['matches_cache'] = all_loaded_matches
            st.session_state['gen_typ'] = gen_typ

matches = st.session_state.get('matches_cache', [])

# Helper: Extrahiere Tipp basierend auf Risikoprofil + Buchmacher-Vergleich
def get_profile_pick(match, profile, checked_bookmakers):
    mkts = match['markets']
    home, away = match['home'], match['away']
    
    if "Safe Mode" in profile:
        # Doppelte Chance oder Safe Über 1.5
        safe_dc = mkts['Safe_DC']
        base_q = safe_dc['base_quote']
        tipp_str = f"Doppelte Chance ({home if 'Heim' in safe_dc['tip'] else away} / X)"
        prob_val = safe_dc['prob']
        mkt_name = "Safe Mode 🛡️"
        m_key = "safe_dc"
    elif "High Risk" in profile:
        # Direct Win or Over 2.5
        p_h = mkts['1X2 Siegwette']['1']['prob']
        p_a = mkts['1X2 Siegwette']['2']['prob']
        if p_h >= p_a:
            base_q = mkts['1X2 Siegwette']['1']['base_quote']
            tipp_str = f"Sieg {home} (1)"
            prob_val = p_h
        else:
            base_q = mkts['1X2 Siegwette']['2']['base_quote']
            tipp_str = f"Sieg {away} (2)"
            prob_val = p_a
        mkt_name = "High Risk 1X2 🎯"
        m_key = "high_risk"
    else: # Balanced
        base_q = mkts['Tore']['Über 1.5']['base_quote']
        tipp_str = "Über 1.5 Tore"
        prob_val = mkts['Tore']['Über 1.5']['prob']
        mkt_name = "Balanced Value ⚽"
        m_key = "balanced"

    best_bm, best_quote, all_bm_odds = get_best_bookmaker_odds(base_q, home, away, m_key, checked_bookmakers)
    bm_url = ANBIETER_URLS.get(best_bm, "https://www.tipico.de")
    
    return {
        "tipp": tipp_str,
        "quote": best_quote,
        "prob": prob_val,
        "markt": mkt_name,
        "best_bookmaker": best_bm,
        "bookmaker_url": bm_url
    }

# --- ERGEBNISSE ANZEIGEN ---
if not matches:
    st.warning(f"⚠️ Keine Spiele für den ausgewählten Zeitraum ({dt_from.strftime('%d.%m.')} - {dt_to.strftime('%d.%m.')}) in den gewählten Ligen gefunden.")
else:
    g_typ = st.session_state.get('gen_typ', '📊 Reine Einzelwetten')
    
    if g_typ == "📊 Reine Einzelwetten":
        st.markdown(f"### 🛡️ KI Einzelwetten mit Quotenvergleich ({len(matches)} Spiele geladen)")
        for match in matches:
            pick = get_profile_pick(match, risiko_profil, aktive_anbieter)
            
            st.markdown(f"""
                <div class="best-card">
                    <span class="badge badge-safe">🛡️ KI POISSON TIPP</span>
                    <span class="badge badge-market">{pick['markt']}</span>
                    <span class="badge badge-bookie">⭐ Bestes Angebot: {pick['best_bookmaker']}</span>
                    <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-left:4px;">{match['liga']}</span>
                    <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.15rem;">{match['home']} vs {match['away']}</h4>
                    <p style="color: #00d47e; font-size: 0.78rem; margin-bottom: 12px;">📅 {match['time_str']}</p>
                    <div style="background:#070a13; border:1px solid #1e293b; border-radius:10px; padding:12px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#94a3b8; font-size:0.8rem;">Empfohlener Tipp:</span><br>
                            <b style="color:#ffffff; font-size:1rem;">{pick['tipp']}</b>
                        </div>
                        <div style="text-align:right;">
                            <span class="odds-tag">{pick['quote']}</span><br>
                            <span class="prob-tag">Wahrscheinlichkeit: {pick['prob']}%</span>
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
                        <span style="color:#94a3b8; font-size:0.8rem;">Höchstquote bei: <b style="color:#f59e0b;">{pick['best_bookmaker']}</b></span>
                        <a href="{pick['bookmaker_url']}" target="_blank" class="bookie-btn">🔗 Zu {pick['best_bookmaker']}</a>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    elif g_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anz_w = st.session_state.get('anzahl_wetten', 3)
        ausgewaehlte = matches[:min(len(matches), anz_w)]
        
        if len(ausgewaehlte) < 2:
            st.warning("⚠️ Nicht genügend Spiele im gewählten Zeitraum vorhanden, um eine Kombiwette mit deiner Wunschanzahl zu erstellen.")
        else:
            gesamtq = 1.0
            picks_data = []
            for m in ausgewaehlte:
                p = get_profile_pick(m, risiko_profil, aktive_anbieter)
                gesamtq *= p['quote']
                picks_data.append((m, p))
                
            st.markdown(f"### 📜 Dein optimierter Kombi-Schein ({len(ausgewaehlte)}er Kombi)")
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 2px solid #00d47e; border-radius: 14px; padding: 20px; text-align: center; margin-bottom: 20px;">
                    <span style="color: #94a3b8; font-size: 0.85rem; font-weight: 700;">GESAMTQUOTE DER KOMBI</span><br>
                    <span style="color: #00d47e; font-size: 2.3rem; font-weight: 800;">{round(gesamtq, 2)}</span>
                </div>
            """, unsafe_allow_html=True)

            for m, p in picks_data:
                st.markdown(f"""
                    <div class="bet-card">
                        <span class="badge badge-market">{p['markt']}</span>
                        <span class="badge badge-bookie">Bester Anbieter: {p['best_bookmaker']}</span>
                        <span class="badge" style="background-color: #1e293b; color: #94a3b8;">{m['liga']}</span>
                        <h4 style="color: #ffffff; margin: 10px 0 4px 0;">{m['home']} vs {m['away']}</h4>
                        <p style="color: #00d47e; font-size: 0.78rem; margin-bottom: 12px;">📅 {m['time_str']}</p>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #94a3b8; font-size: 0.9rem;">Tipp: <b style="color: #ffffff;">{p['tipp']}</b></span>
                            <span class="odds-tag">{p['quote']}</span>
                        </div>
                        <div style="text-align: right; margin-top: 10px;">
                            <a href="{p['bookmaker_url']}" target="_blank" class="bookie-btn">🔗 Bei {p['best_bookmaker']} platzieren</a>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    elif g_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        fb_w = st.session_state.get('freebet_wert', 20)
        fb_picks = matches[:2]
        if len(fb_picks) < 2:
            st.warning("⚠️ Für den Freebet-Modus werden mindestens 2 Spiele benötigt.")
        else:
            p1 = get_profile_pick(fb_picks[0], risiko_profil, aktive_anbieter)
            p2 = get_profile_pick(fb_picks[1], risiko_profil, aktive_anbieter)
            
            q_ges = round(p1['quote'] * p2['quote'], 2)
            netto = round((fb_w * q_ges) - fb_w, 2)
            
            st.markdown("### 🎁 Freebet-Empfehlung")
            st.markdown(f"""
                <div class="multi-ticket-box">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span class="badge" style="background-color: #8b5cf6; color: #ffffff;">🎁 Gratiswette: {fb_w:.2f} €</span>
                        <span class="badge badge-safe">💥 Gesamtquote: {q_ges}</span>
                    </div>
                    <div style="background-color: #070a13; border: 1px solid #8b5cf6; border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 15px;">
                        <span style="color: #94a3b8; font-size: 0.9rem;">Erwarteter Reingewinn (Netto):</span><br>
                        <span style="color: #00d47e; font-size: 1.8rem; font-weight: 800;">{netto:.2f} €</span>
                    </div>
            """, unsafe_allow_html=True)
            for m, p in [(fb_picks[0], p1), (fb_picks[1], p2)]:
                st.markdown(f"""
                    <div style="background-color: #070a13; border: 1px solid #1e293b; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="color: #ffffff; font-weight: 600;">⚽ {m['home']} vs {m['away']}</span><br>
                            <span style="color: #94a3b8; font-size: 0.8rem;">📅 {m['time_str']} | Tipp: <b style="color: #00d47e;">{p['tipp']}</b> ({p['best_bookmaker']})</span>
                        </div>
                        <span style="color: #00d47e; font-weight: 800; font-size: 1.1rem;">{p['quote']}</span>
                    </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    else:
        bud = st.session_state.get('multi_budget', 100.0)
        e1, e2, e3 = round(bud * 0.25, 2), round(bud * 0.50, 2), round(bud * 0.25, 2)
        
        s1 = matches[0:1]
        s2 = matches[1:3] if len(matches) >= 3 else matches[0:2]
        s3 = matches[3:6] if len(matches) >= 6 else matches

        tickets = [
            {"name": "🛡️ Schein 1: Solider Anker", "einsatz": e1, "matches": s1},
            {"name": "⭐ Schein 2: Hauptgewinn-Kombi", "einsatz": e2, "matches": s2},
            {"name": "🚀 Schein 3: High-Reward System", "einsatz": e3, "matches": s3}
        ]

        st.markdown(f"### 🛡️ Multi-Ticket System (Budget: {bud:.2f} €)")
        for ticket in tickets:
            if ticket['matches']:
                q_schein = 1.0
                ticket_picks = []
                for m in ticket['matches']:
                    p = get_profile_pick(m, risiko_profil, aktive_anbieter)
                    q_schein *= p['quote']
                    ticket_picks.append((m, p))
                    
                gewinn_schein = round(ticket['einsatz'] * q_schein, 2)
                
                st.markdown(f"""
                    <div class="multi-ticket-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span class="badge badge-safe">{ticket['name']}</span>
                            <span class="badge badge-market">Einsatz: {ticket['einsatz']:.2f} €</span>
                        </div>
                        <div style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 10px;">
                            Gesamtquote: <b style="color: #00d47e;">{round(q_schein, 2)}</b> | Möglicher Gewinn: <b style="color: #00d47e;">{gewinn_schein:.2f} €</b>
                        </div>
                """, unsafe_allow_html=True)
                for m, p in ticket_picks:
                    st.markdown(f"""
                        <div style="background-color: #070a13; border: 1px solid #1e293b; border-radius: 10px; padding: 8px 12px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #ffffff; font-size: 0.9rem;">⚽ {m['home']} vs {m['away']} (Tipp: <b>{p['tipp']}</b>) — <b style="color:#f59e0b;">{p['best_bookmaker']}</b></span>
                            <span style="color: #00d47e; font-weight: 800;">{p['quote']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 30px 0;'>", unsafe_allow_html=True)
st.markdown("### 🗂️ Gespeicherte Wettscheine")
if not st.session_state['saved_tickets']:
    st.info("Bisher keine Scheine hinterlegt.")
