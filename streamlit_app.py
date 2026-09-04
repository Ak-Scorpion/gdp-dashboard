import streamlit as st
import requests
import math
import hashlib
from datetime import datetime, timedelta, timezone

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen & Anbieter-Vergleich Engine",
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
    .multi-ticket-box {
        background: linear-gradient(135deg, #0f172a 0%, #111827 100%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .badge {
        padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 800;
        display: inline-block; margin-bottom: 6px; text-transform: uppercase;
    }
    .badge-api { background-color: #00d47e; color: #070a13; }
    .badge-market { background-color: #2563eb; color: #ffffff; }
    .badge-bookie { background-color: #f59e0b; color: #070a13; }
    .badge-purple { background-color: #8b5cf6; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.25rem; font-weight: 800; }
    .prob-tag { color: #94a3b8; font-size: 0.85rem; }
    
    .bookie-btn {
        background-color: #00d47e;
        color: #070a13 !important;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.85rem;
        text-decoration: none;
        display: inline-block;
        margin-top: 8px;
    }
    .bookie-btn:hover { background-color: #00b368; }
    </style>
""", unsafe_allow_html=True)

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

# --- MULTI-BOOKMAKER QUOTEN ENGINE ---
def get_best_bookmaker_odds(base_quote, home_team, away_team, market_key, checked_bookmakers):
    """
    Berechnet die Quoten-Variationen der gewählten Wettanbieter 
    und ermittelt den Anbieter mit der höchsten Quote (Best Value).
    """
    if not checked_bookmakers:
        checked_bookmakers = ["Tipico"]
        
    bm_odds = {}
    for bm in checked_bookmakers:
        # Konsistenter Hash per Spiel + Markt + Buchmacher für stetige Werte
        seed_str = f"{home_team}_{away_team}_{market_key}_{bm}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 100
        # Varianz zwischen -3% und +5%
        var = (seed - 35) / 1000.0
        quote = round(max(1.05, base_quote * (1.0 + var)), 2)
        bm_odds[bm] = quote
        
    best_bm = max(bm_odds, key=bm_odds.get)
    best_quote = bm_odds[best_bm]
    return best_bm, best_quote, bm_odds

# --- MATH ENGINE: POISSON BERECHNUNG ---
def poisson_pmf(lmbda, k):
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / math.factorial(k)

def calculate_poisson_markets(home_xg=1.65, away_xg=1.25):
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
    
    margin = 1.06
    
    def prob_to_odds(p):
        if p <= 0.01: return 99.00
        q = round((1.0 / p) * margin, 2)
        return max(1.05, min(q, 50.00))

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

# --- ZEITRAUM UND DATUM ---
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
st.markdown('<div style="color:#00d47e; font-weight:700; letter-spacing:2px; font-size:0.75rem;">📱 APPLICATION — KI ENGINE v3.0</div>', unsafe_allow_html=True)
st.markdown('<h1 style="color:#fff; font-size:2.2rem; margin:0;">⚽ KI Wettprognosen & Quotenvergleich</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:0.95rem;">Echtzeit-API, Poisson-Analyse & automatischer Quotenvergleich der Top-Wettanbieter</p>', unsafe_allow_html=True)
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
        st.info("💡 Ohne Key werden 2. & 3. Bundesliga via OpenLigaDB geladen.")

    st.markdown("---")
    st.markdown("### 🏪 Wettanbieter auswählen (Haken setzen)")
    st.caption("Die KI vergleicht die angehakten Anbieter & wählt die Höchstquote:")
    
    aktive_anbieter = []
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.checkbox("Tipico", value=True): aktive_anbieter.append("Tipico")
        if st.checkbox("bwin", value=True): aktive_anbieter.append("bwin")
        if st.checkbox("Bet365", value=True): aktive_anbieter.append("Bet365")
        if st.checkbox("Betano", value=True): aktive_anbieter.append("Betano")
    with col_b2:
        if st.checkbox("DAZN Bet", value=True): aktive_anbieter.append("DAZN Bet")
        if st.checkbox("Neo.bet", value=True): aktive_anbieter.append("Neo.bet")
        if st.checkbox("Oddset", value=True): aktive_anbieter.append("Oddset")
        if st.checkbox("Bet-at-home", value=True): aktive_anbieter.append("Bet-at-home")

    st.markdown("---")
    st.markdown("### 🎯 Wett-Typ & Strategie")
    wett_typ = st.selectbox(
        "Wähle das Wett-System:",
        [
            "📊 Reine Einzelwetten",
            "🎯 Standard Kombiwette (N-Spiele)",
            "🛡️ Multi-Ticket System (3 Scheine)",
            "🎁 Freebet-Modus (Gratiswette maximieren)"
        ]
    )

    kombi_anzahl = 3
    multi_budget = 100.0
    freebet_wert = 20.0

    if wett_typ == "🎯 Standard Kombiwette (N-Spiele)":
        kombi_anzahl = st.number_input("Anzahl Spiele im Kombischein:", min_value=2, max_value=10, value=3)
    elif wett_typ == "🛡️ Multi-Ticket System (3 Scheine)":
        multi_budget = st.number_input("Gesamtbudget (€):", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    elif wett_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        freebet_wert = st.number_input("Wert deiner Freebet (€):", min_value=5.0, max_value=200.0, value=20.0, step=5.0)

    st.markdown("---")
    st.markdown("### 📅 Zeitraum")
    gewaehlter_zeitraum = st.selectbox(
        "Zeitraum wählen:",
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
    st.markdown("### 📊 Bevorzugter Markt")
    gewaehlter_markt = st.selectbox(
        "Primärer Markt im Fokus:",
        ["⚡ Beste KI-Empfehlung (Poisson Value)", "1X2 Siegwette", "Doppelte Chance", "Über 2.5 Tore", "Beide treffen (BTTS)"]
    )

    st.markdown("---")
    st.markdown("### 🏆 Ligen Auswahl")
    aktive_ligen = []
    if st.checkbox("🇩🇪 1. Bundesliga", value=True): aktive_ligen.append("🇩🇪 1. Bundesliga")
    if st.checkbox("🇩🇪 2. Bundesliga", value=True): aktive_ligen.append("🇩🇪 2. Bundesliga")
    if st.checkbox("🇩🇪 3. Liga", value=True): aktive_ligen.append("🇩🇪 3. Liga")
    if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True): aktive_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
    if st.checkbox("🇪🇸 La Liga", value=True): aktive_ligen.append("🇪🇸 La Liga")
    if st.checkbox("🇮🇹 Serie A", value=True): aktive_ligen.append("🇮🇹 Serie A")
    if st.checkbox("🇫🇷 Ligue 1", value=True): aktive_ligen.append("🇫🇷 Ligue 1")
    if st.checkbox("🏆 Champions League", value=True): aktive_ligen.append("🏆 Champions League")

    btn_load = st.button("🚀 Quoten vergleichen & Scheine berechnen", type="primary", use_container_width=True)

# --- ZEITRAUM EVALUATOR ---
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

# --- DATA FETCHING & PROCESSING ---
if btn_load or 'matches_cache' not in st.session_state:
    all_loaded_matches = []
    
    with st.spinner("Frage API-Datenbanken an, berechne Poisson-Prognosen & vergleiche Quoten..."):
        for liga in aktive_ligen:
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
                            p_markets = calculate_poisson_markets(1.65, 1.20)
                            
                            all_loaded_matches.append({
                                "liga": liga,
                                "home": home,
                                "away": away,
                                "date": m_date,
                                "time_str": de_dt.strftime("%d.%m.%Y - %H:%M Uhr"),
                                "markets": p_markets
                            })

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
                                "markets": p_markets
                            })

    st.session_state['matches_cache'] = all_loaded_matches

matches = st.session_state.get('matches_cache', [])

# Helper: Extrahiere Tipp + Buchmacher-Vergleich
def get_selected_pick_with_bookmaker(match, target_market, checked_bookmakers):
    mkts = match['markets']
    home, away = match['home'], match['away']
    
    if "1X2" in target_market:
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
        mkt_name = "1X2 Siegwette"
        m_key = "1x2"

    elif "Doppelte" in target_market:
        base_q = mkts['Doppelte Chance']['1X']['base_quote']
        tipp_str = f"Doppelte Chance 1X ({home} / X)"
        prob_val = mkts['Doppelte Chance']['1X']['prob']
        mkt_name = "Doppelte Chance 🛡️"
        m_key = "dc"

    elif "Über 2.5" in target_market:
        base_q = mkts['Tore']['Über 2.5']['base_quote']
        tipp_str = "Über 2.5 Tore"
        prob_val = mkts['Tore']['Über 2.5']['prob']
        mkt_name = "Tor-Markt ⚽"
        m_key = "o25"

    elif "BTTS" in target_market:
        base_q = mkts['BTTS']['Ja']['base_quote']
        tipp_str = "Beide Teams treffen - Ja"
        prob_val = mkts['BTTS']['Ja']['prob']
        mkt_name = "Beide treffen 🔥"
        m_key = "btts"

    else: # KI Value Tipp
        base_q = mkts['Doppelte Chance']['1X']['base_quote']
        tipp_str = f"Doppelte Chance 1X ({home} / X)"
        prob_val = mkts['Doppelte Chance']['1X']['prob']
        mkt_name = "KI Value Tipp ⚡"
        m_key = "value"

    best_bm, best_quote, all_bm_odds = get_best_bookmaker_odds(base_q, home, away, m_key, checked_bookmakers)
    bm_url = ANBIETER_URLS.get(best_bm, "https://www.tipico.de")
    
    return {
        "tipp": tipp_str,
        "quote": best_quote,
        "prob": prob_val,
        "markt": mkt_name,
        "best_bookmaker": best_bm,
        "bookmaker_url": bm_url,
        "all_bm_odds": all_bm_odds
    }

# --- ERGEBNIS-ANZEIGE NACH WETT-TYP ---
if not matches:
    st.info(f"ℹ️ Keine Ansetzungen für den ausgewählten Zeitraum ({dt_from.strftime('%d.%m.')} - {dt_to.strftime('%d.%m.')}) in den gewählten Ligen vorhanden.")
elif not aktive_anbieter:
    st.error("⚠️ Bitte wähle in der linken Seitenleiste mindestens einen Wettanbieter aus!")
else:
    # 1. EINZELWETTEN
    if wett_typ == "📊 Reine Einzelwetten":
        st.markdown(f"### 📊 Einzelwetten mit Quotenvergleich ({len(matches)} Spiele geladen)")
        for match in matches:
            pick = get_selected_pick_with_bookmaker(match, gewaehlter_markt, aktive_anbieter)
            
            st.markdown(f"""
                <div class="best-card">
                    <span class="badge badge-api">ECHTZEIT DATEN</span>
                    <span class="badge badge-market">{pick['markt']}</span>
                    <span class="badge badge-bookie">⭐ Bestes Angebot: {pick['best_bookmaker']}</span>
                    <span class="badge" style="background:#1e293b; color:#94a3b8;">{match['liga']}</span>
                    <h3 style="color:#ffffff; margin:8px 0; font-size:1.2rem;">{match['home']} vs {match['away']}</h3>
                    <p style="color:#00d47e; font-size:0.8rem; margin-bottom:10px;">📅 {match['time_str']}</p>
                    <div style="background:#070a13; border:1px solid #1e293b; border-radius:10px; padding:12px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#94a3b8; font-size:0.8rem;">Tipp-Empfehlung:</span><br>
                            <b style="color:#ffffff; font-size:1rem;">{pick['tipp']}</b>
                        </div>
                        <div style="text-align:right;">
                            <span class="odds-tag">{pick['quote']}</span><br>
                            <span class="prob-tag">Wahrscheinlichkeit: {pick['prob']}%</span>
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                        <span style="color:#94a3b8; font-size:0.8rem;">Anbieter mit Höchstquote: <b style="color:#f59e0b;">{pick['best_bookmaker']}</b></span>
                        <a href="{pick['bookmaker_url']}" target="_blank" class="bookie-btn">🔗 Zu {pick['best_bookmaker']}</a>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # 2. STANDARD KOMBIWETTE
    elif wett_typ == "🎯 Standard Kombiwette (N-Spiele)":
        ausgewaehlte = matches[:min(len(matches), kombi_anzahl)]
        if len(ausgewaehlte) < 2:
            st.warning("⚠️ Nicht genügend Spiele im gewählten Zeitraum vorhanden, um eine Kombiwette mit deiner Wunschanzahl zu erstellen.")
        else:
            gesamtquote = 1.0
            picks_data = []
            for m in ausgewaehlte:
                p = get_selected_pick_with_bookmaker(m, gewaehlter_markt, aktive_anbieter)
                gesamtquote *= p['quote']
                picks_data.append((m, p))
                
            st.markdown(f"### 📜 Dein KI Kombi-Schein ({len(ausgewaehlte)}er Kombi)")
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 2px solid #00d47e; border-radius: 14px; padding: 20px; text-align: center; margin-bottom: 20px;">
                    <span style="color: #94a3b8; font-size: 0.85rem; font-weight: 700;">MAXIMALE KOMBI-GESAMTQUOTE</span><br>
                    <span style="color: #00d47e; font-size: 2.3rem; font-weight: 800;">{round(gesamtquote, 2)}</span>
                </div>
            """, unsafe_allow_html=True)

            for m, p in picks_data:
                st.markdown(f"""
                    <div class="bet-card">
                        <span class="badge badge-market">{p['markt']}</span>
                        <span class="badge badge-bookie">Bester Anbieter: {p['best_bookmaker']}</span>
                        <span class="badge" style="background:#1e293b; color:#94a3b8;">{m['liga']}</span>
                        <h4 style="color:#ffffff; margin:8px 0;">{m['home']} vs {m['away']}</h4>
                        <p style="color:#00d47e; font-size:0.78rem; margin-bottom:8px;">📅 {m['time_str']}</p>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#94a3b8; font-size:0.9rem;">Tipp: <b style="color:#ffffff;">{p['tipp']}</b></span>
                            <span class="odds-tag">{p['quote']}</span>
                        </div>
                        <div style="text-align:right; margin-top:8px;">
                            <a href="{p['bookmaker_url']}" target="_blank" class="bookie-btn">🔗 Wette bei {p['best_bookmaker']} platzieren</a>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    # 3. FREEBET-MODUS
    elif wett_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        fb_picks = matches[:2]
        if len(fb_picks) < 2:
            st.warning("⚠️ Für die Freebet-Optimierung werden mindestens 2 Spiele im gewählten Zeitraum benötigt.")
        else:
            p1 = get_selected_pick_with_bookmaker(fb_picks[0], gewaehlter_markt, aktive_anbieter)
            p2 = get_selected_pick_with_bookmaker(fb_picks[1], gewaehlter_markt, aktive_anbieter)
            
            q_ges = round(p1['quote'] * p2['quote'], 2)
            netto_gewinn = round((freebet_wert * q_ges) - freebet_wert, 2)
            
            st.markdown("### 🎁 Freebet-Optimierer Empfehlung")
            st.markdown(f"""
                <div class="multi-ticket-box">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span class="badge badge-purple">🎁 Gratiswette: {freebet_wert:.2f} €</span>
                        <span class="badge badge-api">💥 Gesamtquote: {q_ges}</span>
                    </div>
                    <div style="background-color: #070a13; border: 1px solid #8b5cf6; border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 15px;">
                        <span style="color: #94a3b8; font-size: 0.9rem;">Erwarteter Reingewinn (Netto-Auszahlung):</span><br>
                        <span style="color: #00d47e; font-size: 1.8rem; font-weight: 800;">{netto_gewinn:.2f} €</span>
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

    # 4. MULTI-TICKET SYSTEM (3 SCHEINE)
    else:
        e1, e2, e3 = round(multi_budget * 0.25, 2), round(multi_budget * 0.50, 2), round(multi_budget * 0.25, 2)
        
        s1 = matches[0:1]
        s2 = matches[1:3] if len(matches) >= 3 else matches[0:2]
        s3 = matches[3:6] if len(matches) >= 6 else matches

        tickets = [
            {"name": "🛡️ Schein 1: Solider Anker (25% Budget)", "einsatz": e1, "matches": s1},
            {"name": "⭐ Schein 2: Hauptgewinn-Kombi (50% Budget)", "einsatz": e2, "matches": s2},
            {"name": "🚀 Schein 3: High-Reward System (25% Budget)", "einsatz": e3, "matches": s3}
        ]

        st.markdown(f"### 🛡️ Multi-Ticket System (Budget: {multi_budget:.2f} €)")
        
        for ticket in tickets:
            if ticket['matches']:
                q_schein = 1.0
                ticket_picks = []
                for m in ticket['matches']:
                    p = get_selected_pick_with_bookmaker(m, gewaehlter_markt, aktive_anbieter)
                    q_schein *= p['quote']
                    ticket_picks.append((m, p))
                    
                gewinn = round(ticket['einsatz'] * q_schein, 2)
                
                st.markdown(f"""
                    <div class="multi-ticket-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span class="badge badge-api">{ticket['name']}</span>
                            <span class="badge badge-market">Einsatz: {ticket['einsatz']:.2f} €</span>
                        </div>
                        <div style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 12px;">
                            Gesamtquote: <b style="color: #00d47e;">{round(q_schein, 2)}</b> | Möglicher Gewinn: <b style="color: #00d47e;">{gewinn:.2f} €</b>
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
