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
    '9fa7390d10404cdab8fd77d2445655e0',  # Key 1
    '64a606e404d1d1ea44af7823b6214bad',  # Key 2
    '172b8d5c79d13d232032db7bea17a2b1',  # Key 3
    'ae8d21a5099d547c1ac27008e4dc56ec',  # Key 4
    '1e7838f2acd74658387ae5b9363bd88d',  # Key 5
    '96ad8fdc309e50c2eb3e0efc83faed2e',  # Key 6
    '669dec926fa65d341d87a7d2e1f152ba',  # Key 7
    '54f78da0521be9e4e95c00550a03abe0',  # Key 8
    'b26e2774a0d1e273d5bba986154bc336',  # Key 9
    '25388e5649b0f1411e246ca8e22b6d82',  # Key 10
    '734d7f2cf27ced001dff32ee47fc59c1'   # Key 11
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

# --- DESIGNER CSS (VOLLSTÄNDIGE AUSBLENDUNG DER OBEREN LEISTE & TASTATUR-SPERRE) ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    input[aria-label*="Zeitraum"], input[aria-label*="Datum"], input[aria-expanded] {
        caret-color: transparent !important;
        pointer-events: auto !important;
    }
    div[data-baseweb="input"] input {
        caret-color: transparent !important;
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
    .badge-freebet { background-color: #8b5cf6; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    .counter-box {
        background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
        padding: 10px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# Alle Ligen inklusive deutscher Unterligen
LIGEN = {
    "🇩🇪 Deutschland (1. Bundesliga)": "soccer_germany_bundesliga",
    "🇩🇪 Deutschland (2. Bundesliga)": "soccer_germany_liga2",
    "🇩🇪 Deutschland (3. Liga)": "soccer_germany_liga3",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England (Premier League)": "soccer_epl",
    "🇪🇸 Spanien (La Liga)": "soccer_spain_la_liga",
    "🇮🇹 Italien (Serie A)": "soccer_italy_serie_a",
    "🇫🇷 Frankreich (Ligue 1)": "soccer_france_ligue_one",
    "🇹🇷 Türkei (Süper Lig)": "soccer_turkey_super_lig",
    "🇳🇱 Niederlande (Eredivisie)": "soccer_netherlands_eredivisie",
    "🇵🇹 Portugal (Primeira Liga)": "soccer_portugal_primeira_liga",
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

def check_spiel_im_zeitraum(date_str, zeit_modus, datum_auswahl, spieltag_filter, match_index, total_matches):
    if not date_str: return "Unbekannt", False
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        jetzt = datetime.now(timezone.utc)
        
        if dt <= jetzt:
            return dt.strftime("%d.%m.%Y um %H:%M Uhr"), False
            
        if spieltag_filter > 0:
            erwarteter_spieltag = (match_index // 10) + 1
            if erwarteter_spieltag != spieltag_filter:
                return dt.strftime("%d.%m.%Y um %H:%M Uhr"), False

        heute_date = jetzt.date()

        if zeit_modus == "📅 Kalender-Bereich wählen":
            if isinstance(datum_auswahl, tuple) and len(datum_auswahl) == 2:
                start_date, end_date = datum_auswahl
                if start_date and end_date:
                    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
                    ist_passend = (dt >= start_dt) and (dt <= end_dt)
                    return dt.strftime("%d.%m.%Y um %H:%M Uhr"), ist_passend
            elif isinstance(datum_auswahl, date):
                start_dt = datetime.combine(datum_auswahl, datetime.min.time()).replace(tzinfo=timezone.utc)
                end_dt = datetime.combine(datum_auswahl, datetime.max.time()).replace(tzinfo=timezone.utc)
                ist_passend = (dt >= start_dt) and (dt <= end_dt)
                return dt.strftime("%d.%m.%Y um %H:%M Uhr"), ist_passend
            return dt.strftime("%d.%m.%Y um %H:%M Uhr"), True
            
        elif zeit_modus == "⚡ Wochenende (Freitag – Sonntag)":
            tage_bis_freitag = (4 - heute_date.weekday()) % 7
            freitag = heute_date + timedelta(days=tage_bis_freitag)
            sonntag = freitag + timedelta(days=2)
            
            start_dt = datetime.combine(freitag, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(sonntag, datetime.max.time()).replace(tzinfo=timezone.utc)
            ist_passend = (dt >= start_dt) and (dt <= end_dt)
            return dt.strftime("%d.%m.%Y um %H:%M Uhr"), ist_passend
            
        elif zeit_modus == "🟢 Ganze Woche (Montag – Sonntag)":
            montag = heute_date - timedelta(days=heute_date.weekday())
            sonntag = montag + timedelta(days=6)
            
            start_dt = datetime.combine(montag, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(sonntag, datetime.max.time()).replace(tzinfo=timezone.utc)
            ist_passend = (dt >= start_dt) and (dt <= end_dt)
            return dt.strftime("%d.%m.%Y um %H:%M Uhr"), ist_passend
            
        else: # Nächste Woche (Montag bis Sonntag)
            aktueller_montag = heute_date - timedelta(days=heute_date.weekday())
            naechster_montag = aktueller_montag + timedelta(days=7)
            naechster_sonntag = naechster_montag + timedelta(days=6)
            
            start_dt = datetime.combine(naechster_montag, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(naechster_sonntag, datetime.max.time()).replace(tzinfo=timezone.utc)
            ist_passend = (dt >= start_dt) and (dt <= end_dt)
            return dt.strftime("%d.%m.%Y um %H:%M Uhr"), ist_passend
    except Exception: 
        return date_str, True

def get_best_bookmaker_odds(match_bookmakers, selected_bm_key, home_team, away_team):
    if not match_bookmakers: return None, None, None, None
    target_bm = next((bm for bm in match_bookmakers if bm['key'] == selected_bm_key), None)
    if not target_bm: target_bm = match_bookmakers[0]
    odds = target_bm['markets'][0]['outcomes']
    q_home = next((item['price'] for item in odds if item['name'] == home_team), None)
    q_away = next((item['price'] for item in odds if item['name'] == away_team), None)
    q_draw = next((item['price'] for item in odds if item['name'] == 'Draw'), None)
    all_prices = [item['price'] for bm in match_bookmakers for item in bm['markets'][0]['outcomes'] if item['name'] in [home_team, away_team]]
    avg_price = sum(all_prices) / len(all_prices) if all_prices else q_home
    is_value = q_home and avg_price and (q_home > avg_price * 1.05)
    return q_home, q_away, q_draw, is_value

def get_risk_label(prob):
    if prob >= 45: return "🟢 Low Risk (Sehr sicher)"
    elif prob >= 25: return "🟡 Medium Risk (Solide Chance)"
    elif prob >= 12: return "🟠 High Risk (Risikoreich)"
    else: return "🔴 Harakiri / Verrückt"

# --- HEADER & COUNTER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Inkl. DAZN Bet, 1./2./3. Liga, Spieltag-Filter & Kalender</div>', unsafe_allow_html=True)

with col_count:
    total_rem, total_used = get_total_api_stats()
    max_gesamt_klicks = len(API_KEYS) * 500
    st.markdown(f"""
        <div class="counter-box">
            <span style="color: #64748b; font-size: 0.7rem; font-weight: 700;">📊 ALLE 11 API-KEYS GESAMT</span><br>
            <span style="color: #00d47e; font-size: 1.3rem; font-weight: 800;">{total_rem}</span>
            <span style="color: #ffffff; font-size: 0.8rem;">/ {max_gesamt_klicks} übrig</span><br>
            <span style="color: #475569; font-size: 0.65rem;">Verbraucht: {total_used} Klicks</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 15px 0;'>", unsafe_allow_html=True)

# --- SIDEBAR (LEER / MINIMAL) ---
with st.sidebar:
    st.markdown("### 🎛️ Info")
    st.markdown("Alle Einstellungen (Wettanbieter, Spieltag, Zeitraum & Ligen) befinden sich zentral auf der Hauptseite.")

# --- HAUPTSEITE (ALLES IN EINEM BEREICH) ---
st.markdown("### 🎯 Kombi-, System- & Einzelwetten Generator")

with st.expander("⚙️ Wettanbieter, Spieltag, Zeitraum & Ligen einstellen (Hier klicken)", expanded=True):
    
    st.markdown("#### 🏢 1. Wettanbieter auswählen (Inkl. DAZN Bet)")
    anbieter_wahl = st.radio(
        "Wähle deinen Wettanbieter:",
        list(ANBIETER_URLS.keys()),
        horizontal=True,
        key="main_bm_select"
    )
    
    st.markdown("---")
    st.markdown("#### 🔢 2. Spieltag auswählen (Optional)")
    spieltag_auswahl = st.selectbox(
        "Spieltag wählen (0 = Alle Spieltage ignorieren):",
        [0] + list(range(1, 39)),
        format_func=lambda x: "Alle Spieltage (Standard)" if x == 0 else f"Spieltag {x}",
        key="spieltag_select"
    )

    st.markdown("---")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        gen_zeit_modus = st.radio(
            "Zeitraum-Modus:", 
            [
                "⚡ Wochenende (Freitag – Sonntag)", 
                "🟢 Ganze Woche (Montag – Sonntag)", 
                "⏭️ Nächste Woche (Montag – Sonntag)", 
                "📅 Kalender-Bereich wählen"
            ], 
            index=0, 
            key="gen_zeit_mode"
        )
    with col_e2:
        gen_typ = st.selectbox(
            "Wett-Typ & Strategie wählen:",
            [
                "🛡️ Multi-Ticket System (3 separate Scheine)", 
                "🎁 Freebet-Modus (Gratiswette maximieren)", 
                "🎯 Standard Kombiwette (Freie Anzahl Spiele)",
                "📊 Einzelwetten & Value-Bets (Tabelle)"
            ],
            index=0
        )

    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        st.markdown("<p style='color: #94a3b8; font-size: 0.85rem;'>Tippe auf das Datumsfeld, um den Kalender zu öffnen:</p>", unsafe_allow_html=True)
        kalender_auswahl = st.date_input("Zeitraum für Wetten auswählen:", value=(date.today(), date.today() + timedelta(days=3)), key="kalender_input")

    st.markdown("---")
    st.markdown("#### 🏆 Ligen-Auswahl per Häkchen & Aufklapp-System")
    
    # AUFKLAPP-SYSTEM FÜR DEUTSCHLAND (1., 2., 3. Bundesliga) & RESTLICHE LIGEN
    aktive_generator_ligen = []
    
    with st.expander("🇩🇪 Deutschland (1. Bundesliga, 2. Bundesliga, 3. Liga)", expanded=True):
        chk_bundesliga = st.checkbox("🇩🇪 Deutschland (1. Bundesliga)", value=True, key="chk_BL1")
        chk_liga2 = st.checkbox("🇩🇪 Deutschland (2. Bundesliga)", value=False, key="chk_BL2")
        chk_liga3 = st.checkbox("🇩🇪 Deutschland (3. Liga)", value=False, key="chk_BL3")
        
        if chk_bundesliga: aktive_generator_ligen.append("🇩🇪 Deutschland (1. Bundesliga)")
        if chk_liga2: aktive_generator_ligen.append("🇩🇪 Deutschland (2. Bundesliga)")
        if chk_liga3: aktive_generator_ligen.append("🇩🇪 Deutschland (3. Liga)")

    with st.expander("🌍 Internationale Top-Ligen & Europa", expanded=False):
        inter_ligen = [
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England (Premier League)",
            "🇪🇸 Spanien (La Liga)",
            "🇮🇹 Italien (Serie A)",
            "🇫🇷 Frankreich (Ligue 1)",
            "🇹🇷 Türkei (Süper Lig)",
            "🇳🇱 Niederlande (Eredivisie)",
            "🇵🇹 Portugal (Primeira Liga)",
            "🏆 Champions League",
            "🇪🇺 Europa League",
            "🌍 Conference League"
        ]
        
        col_il1, col_il2 = st.columns(2)
        for idx, l_name in enumerate(inter_ligen):
            target_col = col_il1 if idx % 2 == 0 else col_il2
            with target_col:
                is_chk = st.checkbox(l_name, value=False, key=f"chk_inter_{idx}")
                if is_chk: aktive_generator_ligen.append(l_name)

    st.markdown("---")
    if gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        freebet_wert = st.slider("Wert deiner Freebet (€):", min_value=1, max_value=50, value=20, step=1)
    elif gen_typ == "🛡️ Multi-Ticket System (3 separate Scheine)":
        multi_budget = st.number_input("Gesamtbudget für alle 3 Scheine (€):", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anzahl_wetten = st.number_input("Anzahl der Spiele im Kombischein (Minimum 2):", min_value=2, max_value=10, value=2, step=1)

    generate_click = st.button("🔄 Wetten & Quoten jetzt laden / generieren", type="primary", use_container_width=True)

if generate_click:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Häkchen aus den Aufklapp-Menüs aus!")
    else:
        bm_code = DEUTSCHE_ANBIETER.get(anbieter_wahl, "bwin")
        
        with st.spinner(f"Analysiere Quoten bei {anbieter_wahl} (Spieltag {spieltag_auswahl if spieltag_auswahl > 0 else 'Alle'})..."):
            
            # 1. EINZELWETTEN / VALUE-BETS MODUS
            if gen_typ == "📊 Einzelwetten & Value-Bets (Tabelle)":
                spiele_liste = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        total_m = len(data)
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_auswahl, idx, total_m)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw, is_value = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            prob_h = round((1 / q_home) * 100) if q_home else 0
                            spiele_liste.append({
                                "Liga": liga_label, "Anstoßzeit": match_time, "Heim": home, "Auswärts": away,
                                "Quote 1": q_home, "Quote X": q_draw, "Quote 2": q_away,
                                "Heim-Chance": f"{prob_h}%", "Status": "🔥 VALUE-BET" if is_value else "Standard"
                            })
                st.session_state['mode_type'] = 'einzel'
                st.session_state['einzel_tabelle'] = spiele_liste
                st.session_state['gewaehlter_anbieter'] = anbieter_wahl

            # 2. STANDARD KOMBIWETTE
            elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
                moegliche_tipps = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        total_m = len(data)
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_auswahl, idx, total_m)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            if q_home and 1.30 <= q_home <= 1.80:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Kombi-Favorit 🎯"})
                            if q_away and 1.30 <= q_away <= 1.80:
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
                    st.warning("Nicht genügend Spiele für eine Kombi in dieser Anzahl im gewählten Spieltag/Zeitraum gefunden.")

            # 3. FREEBET MODUS
            elif gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
                moegliche_tipps = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        total_m = len(data)
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_auswahl, idx, total_m)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            if q_home and 1.60 <= q_home <= 2.40:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Freebet Value 🎁"})
                            if q_away and 1.60 <= q_away <= 2.40:
                                moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Freebet Value 🎁"})

                if len(moegliche_tipps) >= 2:
                    random.shuffle(moegliche_tipps)
                    ausgewaehlte_spiele = set()
                    freebet_kombi = []
                    aktuelle_q = 1.0
                    for tipp in moegliche_tipps:
                        if tipp['Begegnung'] not in ausgewaehlte_spiele:
                            freebet_kombi.append(tipp)
                            ausgewaehlte_spiele.add(tipp['Begegnung'])
                            aktuelle_q *= tipp['Quote']
                            if aktuelle_q >= 2.20 or len(freebet_kombi) == 2: break
                    
                    st.session_state['mode_type'] = 'freebet'
                    st.session_state['freebet_wert'] = freebet_wert
                    st.session_state['freebet_kombi'] = freebet_kombi
                    st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                else:
                    st.warning("Keine Freebet-Spiele für diesen Spieltag/Zeitraum gefunden.")

            # 4. MULTI-TICKET SYSTEM
            else:
                alle_spiele_pool = []
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        total_m = len(data)
                        for idx, match in enumerate(data):
                            match_time, ist_gueltig = check_spiel_im_zeitraum(match.get('commence_time'), gen_zeit_modus, kalender_auswahl, spieltag_auswahl, idx, total_m)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            if q_home: alle_spiele_pool.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home})
                            if q_away: alle_spiele_pool.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away})

                if len(alle_spiele_pool) >= 6:
                    random.shuffle(alle_spiele_pool)
                    e1 = round(multi_budget * 0.25, 2)
                    e2 = round(multi_budget * 0.50, 2)
                    e3 = round(multi_budget * 0.25, 2)
                    
                    used_matches = set()
                    def pick_tips(count, q_min_val, q_max_val):
                        picked = []
                        for s in alle_spiele_pool:
                            if s['Begegnung'] not in used_matches and q_min_val <= s['Quote'] <= q_max_val:
                                picked.append(s)
                                used_matches.add(s['Begegnung'])
                                if len(picked) == count: break
                        return picked

                    s1_tipps = pick_tips(2, 1.25, 1.55)
                    s2_tipps = pick_tips(2, 1.40, 1.75)
                    s3_tipps = pick_tips(3, 1.45, 2.00)
                    
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
                    st.warning("Zu wenige Spiele für 3 separate Scheine im gewählten Spieltag/Zeitraum.")

# --- DARSTELLUNG DER ERGEBNISSE AUF DER HAUPTSEITE ---
mode = st.session_state.get('mode_type', None)
anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Tipico')
bookmaker_url = ANBIETER_URLS.get(anbieter_label, "https://www.tipico.de")

if mode == 'einzel' and 'einzel_tabelle' in st.session_state:
    st.markdown(f"### 📊 Einzelwetten & Value-Bets bei {anbieter_label}")
    if st.session_state['einzel_tabelle']:
        st.dataframe(pd.DataFrame(st.session_state['einzel_tabelle']), use_container_width=True, hide_index=True)
    else:
        st.info("Keine Spiele für diesen Spieltag/Zeitraum gefunden.")

elif mode == 'standard' and 'kombi_auswahl' in st.session_state:
    kombi_auswahl = st.session_state['kombi_auswahl']
    gesamtquote = 1.0
    for item in kombi_auswahl: gesamtquote *= item['Quote']
    schein_wahrscheinlichkeit = max(15, min(85, round((1 / gesamtquote) * 100 * 1.15)))
    risk_text = get_risk_label(schein_wahrscheinlichkeit)
        
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
            <h3 style="color: #ffffff; margin-top: 0;">🚀 Jetzt bei {anbieter_label} wetten</h3>
            <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block; margin-top: 10px;">🔗 {anbieter_label} öffnen</a>
        </div>
    """, unsafe_allow_html=True)

elif mode == 'freebet' and 'freebet_kombi' in st.session_state:
    fb_wert = st.session_state.get('freebet_wert', 20)
    fb_kombi = st.session_state['freebet_kombi']
    q_gesamt = 1.0
    for t in fb_kombi: q_gesamt *= t['Quote']
    reingewinn = round((fb_wert * q_gesamt) - fb_wert, 2)
    brutto_gewinn = round(fb_wert * q_gesamt, 2)
    
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
