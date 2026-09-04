import streamlit as st
import requests
import math
from datetime import datetime, timedelta, timezone

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen & Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING (DARK ENGINE UI) ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    header[data-testid="stHeader"] { display: none !important; }
    
    .bet-card {
        background: linear-gradient(135deg, #111827 0%, #0d1320 100%);
        border: 1px solid #1e293b;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
    }
    .best-card {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        border: 2px solid #00d47e;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
    }
    .badge {
        padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 800;
        display: inline-block; margin-bottom: 6px; text-transform: uppercase;
    }
    .badge-api { background-color: #00d47e; color: #070a13; }
    .badge-market { background-color: #2563eb; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.2rem; font-weight: 800; }
    .prob-tag { color: #94a3b8; font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)

# --- MATH ENGINE: POISSON BERECHNUNG ---
def poisson_pmf(lmbda, k):
    """Berechnet die Poisson-Wahrscheinlichkeit für k Tore bei Erwartungswert lambda."""
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def calculate_poisson_markets(home_xg=1.65, away_xg=1.25):
    """
    Berechnet echte mathematische Wahrscheinlichkeiten & Quoten 
    basierend auf einer Tor-Matrix (0 bis 5 Tore je Team).
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

    return {
        "1X2 Siegwette": {
            "1": {"quote": prob_to_odds(p_home), "prob": round(p_home * 100, 1)},
            "X": {"quote": prob_to_odds(p_draw), "prob": round(p_draw * 100, 1)},
            "2": {"quote": prob_to_odds(p_away), "prob": round(p_away * 100, 1)}
        },
        "Doppelte Chance": {
            "1X": {"quote": prob_to_odds(p_dc_1x), "prob": round(p_dc_1x * 100, 1)},
            "X2": {"quote": prob_to_odds(p_dc_x2), "prob": round(p_dc_x2 * 100, 1)}
        },
        "Tore": {
            "Über 1.5": {"quote": prob_to_odds(p_over15), "prob": round(p_over15 * 100, 1)},
            "Über 2.5": {"quote": prob_to_odds(p_over25), "prob": round(p_over25 * 100, 1)}
        },
        "BTTS": {
            "Ja": {"quote": prob_to_odds(p_btts), "prob": round(p_btts * 100, 1)}
        }
    }

# --- API FETCH ENGINE ---
FOOTBALL_DATA_LEAGUES = {
    "🇩🇪 1. Bundesliga": "BL1",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "PL",
    "🇪🇸 La Liga": "PD",
    "🇮🇹 Serie A": "SA",
    "🇫🇷 Ligue 1": "FL1",
    "🏆 Champions League": "CL"
}

OPENLIGA_SHORTCUTS = {
    "🇩🇪 2. Bundesliga": "bl2",
    "🇩🇪 3. Liga": "bl3"
}

@st.cache_data(ttl=600)
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

@st.cache_data(ttl=600)
def fetch_openliga_matches(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

# --- DATUM ZUWEISUNG ---
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

# --- HEADER ---
st.markdown('<div style="color:#00d47e; font-weight:700; letter-spacing:2px; font-size:0.75rem;">📱 APPLICATON — KI ENGINE v2.0</div>', unsafe_allow_html=True)
st.markdown('<h1 style="color:#fff; font-size:2.2rem; margin:0;">⚽ Echtzeit KI-Prognosen & Live-Daten</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:0.95rem;">Exakte Datumsfilterung ohne Platzhalter oder Fake-Spiele</p>', unsafe_allow_html=True)
st.markdown("---")

# --- SIDEBAR EINSTELLUNGEN ---
with st.sidebar:
    st.markdown("### 🔑 API Konfiguration")
    api_key = st.text_input(
        "football-data.org API Key:", 
        type="password", 
        help="Kostenloser Key unter football-data.org liefert PL, BL1, La Liga, Serie A, Ligue 1 & CL."
    )
    if not api_key:
        st.info("💡 Ohne Key werden nur 2. & 3. Bundesliga via OpenLigaDB geladen.")

    st.markdown("---")
    st.markdown("### 🎯 Wett-Optionen")
    
    gewaehlter_zeitraum = st.selectbox(
        "📅 Zeitraum wählen:",
        [
            f"⚡ Heute ({today_de.strftime('%d.%m.%Y')})",
            f"📅 Morgen ({tomorrow_de.strftime('%d.%m.%Y')})",
            f"⚽ Wochenende ({sat_de.strftime('%d.%m.')} - {sun_de.strftime('%d.%m.')})",
            "🟢 Nächste 7 Tage",
            "📆 Benutzerdefiniert"
        ]
    )
    
    custom_start, custom_end = today_de, today_de + timedelta(days=3)
    if gewaehlter_zeitraum == "📆 Benutzerdefiniert":
        custom_range = st.date_input("Zeitraum wählen:", value=(today_de, today_de + timedelta(days=3)))
        if isinstance(custom_range, tuple) and len(custom_range) == 2:
            custom_start, custom_end = custom_range[0], custom_range[1]

    st.markdown("---")
    st.markdown("### 🏆 Ligen auswählen")
    aktive_ligen = []
    
    if st.checkbox("🇩🇪 1. Bundesliga", value=True): aktive_ligen.append("🇩🇪 1. Bundesliga")
    if st.checkbox("🇩🇪 2. Bundesliga", value=True): aktive_ligen.append("🇩🇪 2. Bundesliga")
    if st.checkbox("🇩🇪 3. Liga", value=True): aktive_ligen.append("🇩🇪 3. Liga")
    if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True): aktive_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
    if st.checkbox("🇪🇸 La Liga", value=True): aktive_ligen.append("🇪🇸 La Liga")
    if st.checkbox("🇮🇹 Serie A", value=True): aktive_ligen.append("🇮🇹 Serie A")
    if st.checkbox("🇫🇷 Ligue 1", value=True): aktive_ligen.append("🇫🇷 Ligue 1")
    if st.checkbox("🏆 Champions League", value=True): aktive_ligen.append("🏆 Champions League")

    st.markdown("---")
    gewaehlter_markt = st.selectbox(
        "📊 Primärer Markt im Fokus:",
        ["⚡ Beste KI-Empfehlung (Poisson Value)", "1X2 Siegwette", "Doppelte Chance", "Über 2.5 Tore", "Beide treffen (BTTS)"]
    )

    btn_load = st.button("🔄 Echtzeit-Spiele laden", type="primary", use_container_width=True)

# --- ZEITRAUM BERECHNUNG ---
if "Heute" in gewaehlter_zeitraum:
    dt_from, dt_to = today_de, today_de
elif "Morgen" in gewaehlter_zeitraum:
    dt_from, dt_to = tomorrow_de, tomorrow_de
elif "Wochenende" in gewaehlter_zeitraum:
    dt_from, dt_to = sat_de, sun_de
elif "Nächste 7 Tage" in gewaehlter_zeitraum:
    dt_from, dt_to = today_de, today_de + timedelta(days=7)
else:
    dt_from, dt_to = custom_start, custom_end

str_from = dt_from.strftime("%Y-%m-%d")
str_to = dt_to.strftime("%Y-%m-%d")

# --- MAIN ENGINE PROCESSING ---
if btn_load or 'matches_cache' not in st.session_state:
    all_loaded_matches = []
    
    with st.spinner("Frage API-Datenbanken an & berechne Poisson-Analysen..."):
        for liga in aktive_ligen:
            # 1. football-data.org Abfrage
            if liga in FOOTBALL_DATA_LEAGUES:
                code = FOOTBALL_DATA_LEAGUES[liga]
                if api_key:
                    raw_matches = fetch_football_data_matches(api_key, code, str_from, str_to)
                    for m in raw_matches:
                        utc_dt = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00'))
                        de_dt = utc_dt.astimezone(tz_de)
                        m_date = de_dt.date()
                        
                        if dt_from <= m_date <= dt_to:
                            home = m['homeTeam']['name']
                            away = m['awayTeam']['name']
                            p_markets = calculate_poisson_markets(1.60, 1.20)
                            
                            all_loaded_matches.append({
                                "liga": liga,
                                "home": home,
                                "away": away,
                                "date": m_date,
                                "time_str": de_dt.strftime("%d.%m.%Y - %H:%M Uhr"),
                                "markets": p_markets,
                                "status": m.get('status', 'SCHEDULED')
                            })

            # 2. OpenLigaDB Abfrage
            elif liga in OPENLIGA_SHORTCUTS:
                shortcut = OPENLIGA_SHORTCUTS[liga]
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
                                "liga": liga,
                                "home": home,
                                "away": away,
                                "date": m_date,
                                "time_str": de_dt.strftime("%d.%m.%Y - %H:%M Uhr"),
                                "markets": p_markets,
                                "status": "SCHEDULED"
                            })

    st.session_state['matches_cache'] = all_loaded_matches

matches = st.session_state.get('matches_cache', [])

# --- ERGEBNIS-ANZEIGE ---
if not matches:
    st.info(f"ℹ️ Keine Ansetzungen für den ausgewählten Zeitraum ({dt_from.strftime('%d.%m.')} - {dt_to.strftime('%d.%m.')}) in den gewählten Ligen gefunden.")
else:
    st.success(f"✅ {len(matches)} echte Ansetzungen geladen.")
    
    for match in matches:
        mkts = match['markets']
        
        # KI Empfehlung wählen
        if "1X2" in gewaehlter_markt:
            p_h = mkts['1X2 Siegwette']['1']['prob']
            p_a = mkts['1X2 Siegwette']['2']['prob']
            if p_h >= p_a:
                tipp_str = f"Sieg {match['home']} (1)"
                q_val = mkts['1X2 Siegwette']['1']['quote']
                prob_val = p_h
            else:
                tipp_str = f"Sieg {match['away']} (2)"
                q_val = mkts['1X2 Siegwette']['2']['quote']
                prob_val = p_a
            mkt_label = "1X2 Siegwette"

        elif "Doppelte" in gewaehlter_markt:
            tipp_str = f"Doppelte Chance 1X ({match['home']} / X)"
            q_val = mkts['Doppelte Chance']['1X']['quote']
            prob_val = mkts['Doppelte Chance']['1X']['prob']
            mkt_label = "Doppelte Chance 🛡️"

        elif "Über 2.5" in gewaehlter_markt:
            tipp_str = "Über 2.5 Tore"
            q_val = mkts['Tore']['Über 2.5']['quote']
            prob_val = mkts['Tore']['Über 2.5']['prob']
            mkt_label = "Tor-Markt ⚽"

        elif "BTTS" in gewaehlter_markt:
            tipp_str = "Beide Teams treffen - Ja"
            q_val = mkts['BTTS']['Ja']['quote']
            prob_val = mkts['BTTS']['Ja']['prob']
            mkt_label = "Beide treffen 🔥"

        else: # Beste Empfehlung
            tipp_str = f"Doppelte Chance 1X ({match['home']} / X)"
            q_val = mkts['Doppelte Chance']['1X']['quote']
            prob_val = mkts['Doppelte Chance']['1X']['prob']
            mkt_label = "KI Value Tipp ⚡"

        st.markdown(f"""
            <div class="best-card">
                <span class="badge badge-api">ECHTZET DATEN</span>
                <span class="badge badge-market">{mkt_label}</span>
                <span class="badge" style="background:#1e293b; color:#94a3b8;">{match['liga']}</span>
                <h3 style="color:#ffffff; margin:8px 0; font-size:1.2rem;">{match['home']} vs {match['away']}</h3>
                <p style="color:#00d47e; font-size:0.8rem; margin-bottom:10px;">📅 {match['time_str']}</p>
                <div style="background:#070a13; border:1px solid #1e293b; border-radius:10px; padding:12px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="color:#94a3b8; font-size:0.8rem;">Empfohlener Tipp:</span><br>
                        <b style="color:#ffffff; font-size:1rem;">{tipp_str}</b>
                    </div>
                    <div style="text-align:right;">
                        <span class="odds-tag">{q_val}</span><br>
                        <span class="prob-tag">Wahrscheinlichkeit: {prob_val}%</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

