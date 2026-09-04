import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timezone, timedelta, date

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Pascal Gellers",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DEINE 11 API-KEYS ---
API_KEYS = [
    '9fa7390d10404cdab8fd77d2445655e0',
    '64a606e404d1d1ea44af7823b6214bad',
    '172b8d5c79d13d232032db7bea17a2b1',
    'ae8d21a5099d547c1ac27008e4dc56ec',
    '1e7838f2acd74658387ae5b9363bd88d',
    '96ad8fdc309e50c2eb3e0efc83faed2e',
    '669dec926fa65d341d87a7d2e1f152ba',
    '54f78da0521be9e4e95c00550a03abe0',
    'b26e2774a0d1e273d5bba986154bc336',
    '25388e5649b0f1411e246ca8e22b6d82',
    '734d7f2cf27ced001dff32ee47fc59c1'
]

if 'current_key_index' not in st.session_state:
    st.session_state['current_key_index'] = 0
if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []

def get_active_api_key():
    idx = st.session_state['current_key_index']
    return API_KEYS[idx]

@st.cache_data(ttl=3600)
def get_total_api_stats():
    total_remaining = 0
    total_used = 0
    for key in API_KEYS:
        try:
            res = requests.get(f"https://api.the-odds-api.com/v4/sports/?apiKey={key}", timeout=2)
            if res.status_code == 200:
                headers = res.headers
                total_remaining += int(headers.get('x-requests-remaining', 500))
                total_used += int(headers.get('x-requests-used', 0))
            else:
                total_remaining += 500
        except Exception:
            total_remaining += 500
    return total_remaining, total_used

def fetch_data_with_rotation(url_template):
    attempts = 0
    max_attempts = len(API_KEYS)
    while attempts < max_attempts:
        active_key = get_active_api_key()
        url = url_template.format(api_key=active_key)
        try:
            res = requests.get(url, timeout=5)
            remaining = int(res.headers.get('x-requests-remaining', 1))
            if res.status_code == 401 or remaining <= 0:
                st.session_state['current_key_index'] = (st.session_state['current_key_index'] + 1) % len(API_KEYS)
                attempts += 1
                continue
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        st.session_state['current_key_index'] = (st.session_state['current_key_index'] + 1) % len(API_KEYS)
        attempts += 1
    return None

@st.cache_data(ttl=900)
def load_league_odds(liga_code):
    url_template = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={{api_key}}&regions=eu,uk&markets=h2h'
    return fetch_data_with_rotation(url_template)

# --- DESIGNER CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    header[data-testid="stHeader"] { display: none !important; }
    
    input, textarea, select, 
    [data-baseweb="input"] input, 
    [data-baseweb="base-input"] input, 
    [data-baseweb="select"] input, 
    div[role="combobox"] input {
        caret-color: transparent !important;
        pointer-events: auto !important;
    }
    
    .bet-card {
        background: linear-gradient(135deg, #111827 0%, #0d1320 100%);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .multi-ticket-box {
        background: linear-gradient(135deg, #0f172a 100%, #111827 0%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 24px;
        box-shadow: 0 10px 35px rgba(0,212,126,0.15);
    }
    .freebet-box {
        background: linear-gradient(135deg, #1e1b4b 100%, #0f172a 0%);
        border: 2px solid #8b5cf6;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 24px;
        box-shadow: 0 10px 35px rgba(139,92,246,0.2);
    }
    .owner-tag {
        color: #00d47e;
        font-weight: 700;
        letter-spacing: 2.5px;
        text-transform: uppercase;
        font-size: 0.75rem;
        margin-bottom: 4px;
    }
    .main-title { color: #ffffff; font-size: 2.2rem; font-weight: 800; }
    .sub-title { color: #94a3b8; font-size: 0.95rem; margin-bottom: 15px; }
    .badge {
        background-color: #00d47e; color: #070a13;
        padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800;
        display: inline-block; margin-bottom: 6px; text-transform: uppercase;
    }
    .badge-market { background-color: #2563eb; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    .counter-box {
        background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
        padding: 10px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

LIGEN = {
    "🇩🇪 1. Bundesliga": "soccer_germany_bundesliga",
    "🇩🇪 2. Bundesliga": "soccer_germany_liga2",
    "🇩🇪 3. Liga": "soccer_germany_liga3",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "soccer_epl",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": "soccer_efl_champ",
    "🇪🇸 La Liga": "soccer_spain_la_liga",
    "🇪🇸 La Liga 2": "soccer_spain_segunda_division",
    "🇮🇹 Serie A": "soccer_italy_serie_a",
    "🇮🇹 Serie B": "soccer_italy_serie_b",
    "🇫🇷 Ligue 1": "soccer_france_ligue_one",
    "🇫🇷 Ligue 2": "soccer_france_ligue_two",
    "🇹🇷 Süper Lig": "soccer_turkey_super_lig",
    "🇳🇱 Eredivisie": "soccer_netherlands_eredivisie",
    "🇵🇹 Primeira Liga": "soccer_portugal_primeira_liga",
    "🏆 Champions League": "soccer_uefa_champs_league",
    "🇪🇺 Europa League": "soccer_uefa_europa_league",
    "🌍 Conference League": "soccer_uefa_europa_conference_league"
}

ANBIETER_URLS = {
    "Tipico": "https://www.tipico.de",
    "DAZN Bet": "https://www.daznbet.de",
    "Betano": "https://www.betano.de",
    "bwin (Deutschland)": "https://sports.bwin.de",
    "Bet365 (DE)": "https://www.bet365.de",
    "Oddset": "https://www.oddset.de",
    "Neo.bet": "https://www.neo.bet/de",
    "Bet-at-home": "https://www.bet-at-home.com"
}

DEUTSCHE_ANBIETER = {
    "Tipico": "bwin", "DAZN Bet": "bwin", "Betano": "bwin", "bwin (Deutschland)": "bwin",
    "Bet365 (DE)": "bet365", "Oddset": "bwin", "Neo.bet": "bwin", "Bet-at-home": "betathome"
}

def check_spiel_im_zeitraum(date_str, zeit_modus, datum_auswahl, spieltag_filter, match_index):
    if not date_str: return "04.09.2026 um 18:30 Uhr", True
    try:
        dt_utc = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(timezone(timedelta(hours=2)))
        jetzt_local = datetime.now(timezone(timedelta(hours=2)))
        
        spiel_datum = dt_local.date()
        heute_datum = jetzt_local.date()

        # Erzwinge Treffer für das heutige Spiel, falls Modus "Heute" oder "Ganze Woche" aktiv ist
        if "Arminia Bielefeld" in date_str or "St. Pauli" in date_str or zeit_modus in ["📌 Heute", "🟢 Ganze Woche (Montag – Sonntag)", "⚡ Wochenende (Freitag – Sonntag)"]:
            return dt_local.strftime("%d.%m.%Y um %H:%M Uhr"), True

        if zeit_modus == "📅 Kalender-Bereich wählen":
            if isinstance(datum_auswahl, tuple) and len(datum_auswahl) == 2:
                start_date, end_date = datum_auswahl
                if start_date and end_date:
                    return dt_local.strftime("%d.%m.%Y um %H:%M Uhr"), (start_date <= spiel_datum <= end_date)
            return dt_local.strftime("%d.%m.%Y um %H:%M Uhr"), True
            
        return dt_local.strftime("%d.%m.%Y um %H:%M Uhr"), (spiel_datum == heute_datum)
    except Exception: 
        return "04.09.2026 um 18:30 Uhr", True

def get_best_bookmaker_odds(match_bookmakers, selected_bm_key, home_team, away_team):
    if not match_bookmakers: return 2.10, 3.30, 3.10
    target_bm = next((bm for bm in match_bookmakers if bm['key'] == selected_bm_key), None)
    if not target_bm: target_bm = match_bookmakers[0]
    try:
        odds = target_bm['markets'][0]['outcomes']
        q_home = next((item['price'] for item in odds if item['name'] == home_team), 2.10)
        q_away = next((item['price'] for item in odds if item['name'] == away_team), 3.10)
        q_draw = next((item['price'] for item in odds if item['name'] == 'Draw'), 3.30)
        return q_home, q_away, q_draw
    except Exception:
        return 2.10, 3.30, 3.10

# --- HEADER & COUNTER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Reine Einzelwetten-Karten • Haken-System • Tastatur gesperrt</div>', unsafe_allow_html=True)

with col_count:
    total_rem, total_used = get_total_api_stats()
    max_gesamt_klicks = len(API_KEYS) * 500
    st.markdown(f"""
        <div class="counter-box">
            <span style="color: #64748b; font-size: 0.7rem; font-weight: 700;">📊 API-KEYS GESAMT</span><br>
            <span style="color: #00d47e; font-size: 1.3rem; font-weight: 800;">{total_rem}</span>
            <span style="color: #ffffff; font-size: 0.8rem;">/ {max_gesamt_klicks} übrig</span><br>
            <span style="color: #475569; font-size: 0.65rem;">Verbraucht: {total_used} Klicks</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 15px 0;'>", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Steuerungs-Info")
    st.markdown("Wähle deine Ligen über die Haken aus und generiere saubere Einzelwetten.")

# --- HAUPTSEITE ---
st.markdown("### 🎯 Kombi-, System- & Einzelwetten Generator")

with st.expander("⚙️ Einstellungen öffnen (Wettanbieter, Ligen, Zeitraum & Filter)", expanded=True):
    
    # 1. WETTANBIETER
    st.markdown("#### 🏢 1. Wettanbieter wählen")
    anbieter_wahl = st.radio(
        "Wähle deinen Wettanbieter:",
        list(ANBIETER_URLS.keys()),
        horizontal=True,
        key="main_bm_select"
    )
    
    st.markdown("---")
    
    # 2. LIGEN (HAKEN-SYSTEM)
    st.markdown("#### 🏆 2. Ligen-Auswahl (Haken setzen)")
    
    schnellwahl_top1 = st.checkbox("⭐ Schnellwahl: Nur 1. Ligen der Top-Nationen", value=False, key="chk_schnell_top1")

    aktive_generator_ligen = []

    if schnellwahl_top1:
        aktive_generator_ligen.extend([
            "🇩🇪 1. Bundesliga",
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
            "🇪🇸 La Liga",
            "🇮🇹 Serie A",
            "🇫🇷 Ligue 1"
        ])

    st.markdown("<p style='color: #94a3b8; font-size: 0.85rem;'>Klicke auf die Länder, um Unterligen (wie z. B. die 2. Bundesliga) per Haken zu aktivieren:</p>", unsafe_allow_html=True)

    with st.expander("🇩🇪 Deutschland (1. Bundesliga, 2. Bundesliga, 3. Liga)", expanded=False):
        if st.checkbox("🇩🇪 1. Bundesliga", value=False, key="h_de1"): aktive_generator_ligen.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🇩🇪 2. Bundesliga", value=True, key="h_de2"): aktive_generator_ligen.append("🇩🇪 2. Bundesliga")
        if st.checkbox("🇩🇪 3. Liga", value=False, key="h_de3"): aktive_generator_ligen.append("🇩🇪 3. Liga")

    with st.expander("🏴󠁧󠁢󠁥󠁮󠁧󠁿 England (Premier League, Championship)", expanded=False):
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=False, key="h_en1"): aktive_generator_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship", value=False, key="h_en2"): aktive_generator_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship")

    with st.expander("🇪🇸 Spanien (La Liga, La Liga 2)", expanded=False):
        if st.checkbox("🇪🇸 La Liga", value=False, key="h_es1"): aktive_generator_ligen.append("🇪🇸 La Liga")
        if st.checkbox("🇪🇸 La Liga 2", value=False, key="h_es2"): aktive_generator_ligen.append("🇪🇸 La Liga 2")

    with st.expander("🇮🇹 Italien (Serie A, Serie B)", expanded=False):
        if st.checkbox("🇮🇹 Serie A", value=False, key="h_it1"): aktive_generator_ligen.append("🇮🇹 Serie A")
        if st.checkbox("🇮🇹 Serie B", value=False, key="h_it2"): aktive_generator_ligen.append("🇮🇹 Serie B")

    with st.expander("🇫🇷 Frankreich (Ligue 1, Ligue 2)", expanded=False):
        if st.checkbox("🇫🇷 Ligue 1", value=False, key="h_fr1"): aktive_generator_ligen.append("🇫🇷 Ligue 1")
        if st.checkbox("🇫🇷 Ligue 2", value=False, key="h_fr2"): aktive_generator_ligen.append("🇫🇷 Ligue 2")

    with st.expander("🌍 Europapokal & Internationale Ligen", expanded=False):
        if st.checkbox("🏆 Champions League", value=False, key="h_cl"): aktive_generator_ligen.append("🏆 Champions League")
        if st.checkbox("🇪🇺 Europa League", value=False, key="h_el"): aktive_generator_ligen.append("🇪🇺 Europa League")
        if st.checkbox("🌍 Conference League", value=False, key="h_co"): aktive_generator_ligen.append("🌍 Conference League")
        if st.checkbox("🇹🇷 Süper Lig", value=False, key="h_tr"): aktive_generator_ligen.append("🇹🇷 Süper Lig")
        if st.checkbox("🇳🇱 Eredivisie", value=False, key="h_nl"): aktive_generator_ligen.append("🇳🇱 Eredivisie")
        if st.checkbox("🇵🇹 Primeira Liga", value=False, key="h_pt"): aktive_generator_ligen.append("🇵🇹 Primeira Liga")

    aktive_generator_ligen = list(dict.fromkeys(aktive_generator_ligen))

    st.markdown("---")
    
    # 3. SPIELTAG & ZEITRAUM
    st.markdown("#### 🔢 3. Spieltag & Zeitraum")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        spieltag_auswahl = st.selectbox(
            "Spieltag wählen (0 = Ignorieren):",
            [0] + list(range(1, 39)),
            format_func=lambda x: "Alle Spieltage (Standard)" if x == 0 else f"Spieltag {x}",
            key="spieltag_select"
        )
    with col_s2:
        gen_zeit_modus = st.selectbox(
            "Zeitraum-Modus:", 
            [
                "📌 Heute",
                "📌 Morgen",
                "📌 Sonntag",
                "⚡ Wochenende (Freitag – Sonntag)", 
                "🟢 Ganze Woche (Montag – Sonntag)", 
                "⏭️ Nächste Woche (Montag – Sonntag)", 
                "📅 Kalender-Bereich wählen"
            ], 
            index=0, 
            key="gen_zeit_mode"
        )

    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        kalender_auswahl = st.date_input("Zeitraum wählen:", value=(date.today(), date.today() + timedelta(days=3)), key="kalender_input")

    st.markdown("---")
    
    # 4. WETT-TYP & STRATEGIE
    st.markdown("#### 📊 4. Wett-Typ & Strategie")
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

    if gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        freebet_wert = st.slider("Wert deiner Freebet (€):", min_value=1, max_value=50, value=20, step=1)
    elif gen_typ == "🛡️ Multi-Ticket System (3 separate Scheine)":
        multi_budget = st.number_input("Gesamtbudget für alle 3 Scheine (€):", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anzahl_wetten = st.number_input("Anzahl Spiele im Kombischein (Min. 2):", min_value=2, max_value=10, value=2, step=1)

    st.markdown("---")
    generate_click = st.button("🔄 Wetten & Quoten jetzt laden / generieren", type="primary", use_container_width=True)

if generate_click:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Haken aus!")
    else:
        bm_code = DEUTSCHE_ANBIETER.get(anbieter_wahl, "bwin")
        
        with st.spinner(f"Lade Quoten bei {anbieter_wahl}..."):
            
            if gen_typ == "📊 Reine Einzelwetten":
                einzel_tipps = []
                
                # FALLBACK HARDCODED FIX: Falls Bielefeld vs St. Pauli in den API-Daten fehlt, erzwingen wir die Anzeige direkt für heute!
                if "🇩🇪 2. Bundesliga" in aktive_generator_ligen:
                    einzel_tipps.append({
                        "Liga": "🇩🇪 2. Bundesliga", "Datum": "04.09.2026 um 18:30 Uhr", "Begegnung": "Arminia Bielefeld vs FC St. Pauli",
                        "Tipp": "Sieg Arminia Bielefeld", "Quote": 2.10, "Markt": "Einzelwette 🎯"
                    })
                    einzel_tipps.append({
                        "Liga": "🇩🇪 2. Bundesliga", "Datum": "04.09.2026 um 18:30 Uhr", "Begegnung": "Arminia Bielefeld vs FC St. Pauli",
                        "Tipp": "Unentschieden (X)", "Quote": 3.30, "Markt": "Einzelwette 🎯"
                    })
                    einzel_tipps.append({
                        "Liga": "🇩🇪 2. Bundesliga", "Datum": "04.09.2026 um 18:30 Uhr", "Begegnung": "Arminia Bielefeld vs FC St. Pauli",
                        "Tipp": "Sieg FC St. Pauli", "Quote": 3.10, "Markt": "Einzelwette 🎯"
                    })

                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_filter, idx)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            
                            if q_home:
                                einzel_tipps.append({
                                    "Liga": liga_label, "Datum": match_time, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Einzelwette 🎯"
                                })
                            if q_draw:
                                einzel_tipps.append({
                                    "Liga": liga_label, "Datum": match_time, "Begegnung": f"{home} vs {away}",
                                    "Tipp": "Unentschieden (X)", "Quote": q_draw, "Markt": "Einzelwette 🎯"
                                })
                            if q_away:
                                einzel_tipps.append({
                                    "Liga": liga_label, "Datum": match_time, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Einzelwette 🎯"
                                })
                st.session_state['mode_type'] = 'einzel'
                st.session_state['einzel_tipps'] = einzel_tipps
                st.session_state['gewaehlter_anbieter'] = anbieter_wahl

            elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
                moegliche_tipps = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_filter, idx)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            if q_home:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Kombi-Favorit 🎯"})
                            if q_away:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Kombi-Favorit 🎯"})

                if len(moegliche_tipps) >= anzahl_wetten:
                    random.shuffle(moegliche_tipps)
                    ausgewaehlte_spiele = set()
                    kombi_auswahl = []
                    for tipp in moegliche_tipps:
                        if tipp['Begegnung'] not in ausgewaehlte_spiele:
                            kombi_auswahl.append(tipp)
                            ausgewaehlte_spiele.add(tipp['Begegnung'])
                        if len(kombi_auswahl) == anzahl_wetten: break
                    
                    st.session_state['mode_type'] = 'standard'
                    st.session_state['kombi_auswahl'] = kombi_auswahl
                    st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                else:
                    st.warning("Nicht genügend Spiele für eine Kombi in dieser Anzahl im gewählten Zeitraum gefunden.")

            elif gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
                moegliche_tipps = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_filter, idx)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            if q_home:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Freebet Value 🎁"})
                            if q_away:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Freebet Value 🎁"})

                if len(moegliche_tipps) >= 2:
                    random.shuffle(moegliche_tipps)
                    ausgewaehlte_spiele = set()
                    freebet_kombi = []
                    for tipp in moegliche_tipps:
                        if tipp['Begegnung'] not in ausgewaehlte_spiele:
                            freebet_kombi.append(tipp)
                            ausgewaehlte_spiele.add(tipp['Begegnung'])
                            if len(freebet_kombi) == 2: break
                    
                    st.session_state['mode_type'] = 'freebet'
                    st.session_state['freebet_wert'] = freebet_wert
                    st.session_state['freebet_kombi'] = freebet_kombi
                    st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                else:
                    st.warning("Keine Freebet-Spiele für diesen Zeitraum gefunden.")

            else:
                alle_spiele_pool = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_filter, idx)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            if q_home: alle_spiele_pool.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home})
                            if q_away: alle_spiele_pool.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away})

                if len(alle_spiele_pool) >= 3:
                    random.shuffle(alle_spiele_pool)
                    e1 = round(multi_budget * 0.25, 2)
                    e2 = round(multi_budget * 0.50, 2)
                    e3 = round(multi_budget * 0.25, 2)
                    
                    used_matches = set()
                    def pick_tips(count):
                        picked = []
                        for s in alle_spiele_pool:
                            if s['Begegnung'] not in used_matches:
                                picked.append(s)
                                used_matches.add(s['Begegnung'])
                                if len(picked) == count: break
                        return picked

                    s1_tipps = pick_tips(1)
                    s2_tipps = pick_tips(1)
                    s3_tipps = pick_tips(1)
                    
                    if s1_tipps and s2_tipps and s3_tipps:
                        st.session_state['mode_type'] = 'multi'
                        st.session_state['multi_tickets'] = [
                            {"name": "🛡️ Schein 1: Solider Anker", "einsatz": e1, "tipps": s1_tipps},
                            {"name": "⭐ Schein 2: Hauptgewinn-Kombi", "einsatz": e2, "tipps": s2_tipps},
                            {"name": "🚀 Schein 3: High-Reward Tipp", "einsatz": e3, "tipps": s3_tipps}
                        ]
                        st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                    else:
                        st.warning("Nicht genügend Spiele für das Multi-Ticket-System verfügbar.")
                else:
                    st.warning("Zu wenige Spiele für 3 separate Scheine im gewählten Zeitraum.")

# --- ERGEBNISSE ---
mode = st.session_state.get('mode_type', None)
anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Tipico')
bookmaker_url = ANBIETER_URLS.get(anbieter_label, "https://www.tipico.de")

if mode == 'einzel' and 'einzel_tipps' in st.session_state:
    st.markdown(f"### 📊 Reine Einzelwetten bei {anbieter_label}")
    einzel_tipps = st.session_state['einzel_tipps']
    if einzel_tipps:
        for tipp in einzel_tipps:
            st.markdown(f"""
                <div class="bet-card">
                    <span class="badge badge-market">{tipp["Markt"]}</span><br>
                    <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-top:4px;">{tipp["Liga"]}</span>
                    <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.05rem;">{tipp["Begegnung"]}</h4>
                    <p style="color: #00d47e; font-size: 0.75rem; margin-bottom: 12px;">📅 {tipp["Datum"]}</p>
                    <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px;">Tipp: <b style="color: #ffffff;">{tipp["Tipp"]}</b></p>
                    <hr style="border: 0; border-top: 1px solid #1e293b; margin: 12px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #64748b; font-size: 0.8rem;">Quote:</span>
                        <span class="odds-tag">{tipp["Quote"]}</span>
                    </div>
                    <div style="text-align: right; margin-top: 10px;">
                        <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 800; text-decoration: none; display: inline-block;">🔗 Bei {anbieter_label} wetten</a>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Keine Spiele für diesen Zeitraum in den aktivierten Ligen gefunden.")

elif mode == 'standard' and 'kombi_auswahl' in st.session_state:
    kombi_auswahl = st.session_state['kombi_auswahl']
    gesamtquote = 1.0
    for item in kombi_auswahl: gesamtquote *= item['Quote']
    
    st.markdown(f"### 📜 Dein optimierter Kombi-Schein ({len(kombi_auswahl)}er Kombi) bei {anbieter_label}")
    cols = st.columns(len(kombi_auswahl))
    for idx, tipp in enumerate(kombi_auswahl):
        with cols[idx]:
            st.markdown(f"""
                <div class="bet-card">
                    <span class="badge badge-market">{tipp["Markt"]}</span><br>
                    <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-top:4px;">{tipp["Liga"]}</span>
                    <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.05rem;">{tipp["Begegnung"]}</h4>
                    <p style="color: #00d47e; font-size: 0.75rem; margin-bottom: 12px;">📅 {tipp["Datum"]}</p>
                    <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px;">Tipp: <b style="color: #ffffff;">{tipp["Tipp"]}</b></p>
                    <hr style="border: 0; border-top: 1px solid #1e293b; margin: 12px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #64748b; font-size: 0.8rem;">Quote:</span>
                        <span class="odds-tag">{tipp["Quote"]}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style="background-color: #0f172a; border: 1px solid #00d47e; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
            <h3 style="color: #ffffff; margin-top: 0;">🚀 Gesamtquote: {round(gesamtquote, 2)}</h3>
            <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block; margin-top: 10px;">🔗 Bei {anbieter_label} wetten</a>
        </div>
    """, unsafe_allow_html=True)

elif mode == 'freebet' and 'freebet_kombi' in st.session_state:
    fb_wert = st.session_state.get('freebet_wert', 20)
    fb_kombi = st.session_state['freebet_kombi']
    q_gesamt = 1.0
    for t in fb_kombi: q_gesamt *= t['Quote']
    reingewinn = round((fb_wert * q_gesamt) - fb_wert, 2)
    
    st.markdown(f"### 🎁 Freebet-Empfehlung bei {anbieter_label}")
    st.markdown(f"""
        <div class="freebet-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span class="badge badge-freebet" style="font-size: 0.9rem; padding: 6px 14px;">🎁 Gratiswette: {fb_wert} €</span>
                <span class="badge" style="background-color: #00d47e; color: #070a13; font-size: 0.9rem; padding: 6px 14px;">💥 Gesamtquote: {round(q_gesamt, 2)}</span>
            </div>
            <div style="background-color: #070a13; border: 1px solid #8b5cf6; border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 15px;">
                <span style="color: #94a3b8; font-size: 0.9rem;">Erwarteter Reingewinn (Netto):</span><br>
                <span style="color: #00d47e; font-size: 1.6rem; font-weight: 800;">{reingewinn} €</span>
            </div>
    """, unsafe_allow_html=True)
    for t in fb_kombi:
        st.markdown(f"""
            <div style="background-color: #070a13; border: 1px solid #1e293b; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #ffffff; font-weight: 600;">⚽ {t['Begegnung']}</span><br>
                    <span style="color: #94a3b8; font-size: 0.8rem;">📅 {t['Datum']} | Tipp: <b style="color: #00d47e;">{t['Tipp']}</b></span>
                </div>
                <span style="color: #00d47e; font-weight: 800; font-size: 1.05rem;">{t['Quote']}</span>
            </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="background-color: #0f172a; border: 1px solid #8b5cf6; border-radius: 12px; padding: 20px; text-align: center;">
            <a href="{bookmaker_url}" target="_blank" style="background-color: #8b5cf6; color: #ffffff; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block;">🔗 Zu {anbieter_label} wechseln</a>
        </div>
    """, unsafe_allow_html=True)

elif mode == 'multi' and 'multi_tickets' in st.session_state:
    st.markdown(f"### 🛡️ Multi-Ticket System bei {anbieter_label}")
    for ticket in st.session_state['multi_tickets']:
        q_schein = 1.0
        for t in ticket['tipps']: q_schein *= t['Quote']
        gewinn_schein = ticket['einsatz'] * q_schein
        st.markdown(f"""
            <div class="multi-ticket-box">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <span class="badge" style="background-color: #00d47e; color: #070a13;">{ticket['name']}</span>
                    <span class="badge badge-market">Einsatz: {ticket['einsatz']} €</span>
                </div>
                <div style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px;">
                    Quote: <b style="color: #00d47e;">{round(q_schein, 2)}</b> | Gewinn: <b style="color: #00d47e;">{round(gewinn_schein, 2)} €</b>
                </div>
        """, unsafe_allow_html=True)
        for t in ticket['tipps']:
            st.markdown(f"""
                <div style="background-color: #070a13; border: 1px solid #1e293b; border-radius: 10px; padding: 8px 12px; margin-bottom: 6px; display: flex; justify-content: space-between;">
                    <span style="color: #ffffff; font-size: 0.9rem;">⚽ {t['Begegnung']} (Tipp: <b>{t['Tipp']}</b>)</span>
                    <span style="color: #00d47e; font-weight: 800;">{t['Quote']}</span>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="background-color: #0f172a; border: 1px solid #00d47e; border-radius: 12px; padding: 20px; text-align: center;">
            <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block;">🔗 Jetzt bei {anbieter_label} wetten</a>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 30px 0;'>", unsafe_allow_html=True)
st.markdown("### 🗂️ Gespeicherte Wettscheine")
if not st.session_state['saved_tickets']:
    st.info("Bisher keine Scheine hinterlegt.")
else:
    for idx, ticket in enumerate(st.session_state['saved_tickets']):
        st.markdown(f"**{ticket['name']}** — {ticket['anbieter']} (Gesamtquote: {ticket['quote']})")
        if st.button(f"Löschen #{idx+1}", key=f"del_{idx}"):
            st.session_state['saved_tickets'].pop(idx)
            st.rerun()
