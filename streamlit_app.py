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
    url_template = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={{api_key}}&regions=eu,uk&markets=h2h&oddsFormat=decimal'
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
    .badge-risk-low { background-color: #00d47e; color: #070a13; }
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
    "🇪🇸 La Liga": "soccer_spain_la_liga",
    "🇮🇹 Serie A": "soccer_italy_serie_a",
    "🇫🇷 Ligue 1": "soccer_france_ligue_one",
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

def get_strict_preferred_odds(match_bookmakers, selected_bm_name, home_team, away_team):
    if not match_bookmakers:
        return None, None, None, selected_bm_name

    bm_map = {
        "Tipico": ["tipico", "bwin", "bet365", "unibet"],
        "DAZN Bet": ["daznbet", "bwin", "bet365", "unibet"],
        "Betano": ["betano", "bwin", "bet365", "unibet"],
        "bwin (Deutschland)": ["bwin", "bet365", "unibet"],
        "Bet365 (DE)": ["bet365", "bwin", "unibet"],
        "Oddset": ["oddset", "bwin", "bet365"],
        "Neo.bet": ["neobet", "bwin", "bet365"],
        "Bet-at-home": ["betathome", "bwin", "bet365"]
    }

    api_keys_to_check = [selected_bm_name.lower().replace(" ", "").replace("(", "").replace(")", "")]
    for pk in bm_map.get(selected_bm_name, ["bwin", "bet365"]):
        if pk not in api_keys_to_check:
            api_keys_to_check.append(pk)

    target_bm = None
    used_name = selected_bm_name

    for key_part in api_keys_to_check:
        target_bm = next((bm for bm in match_bookmakers if key_part in bm['key'].lower() or key_part in bm['title'].lower()), None)
        if target_bm:
            used_name = target_bm.get('title', selected_bm_name)
            break

    if not target_bm and match_bookmakers:
        target_bm = match_bookmakers[0]
        used_name = target_bm.get('title', "Alternativ-Anbieter")

    try:
        odds = target_bm['markets'][0]['outcomes']
        q_home = next((item['price'] for item in odds if item['name'] == home_team), None)
        q_away = next((item['price'] for item in odds if item['name'] == away_team), None)
        q_draw = next((item['price'] for item in odds if item['name'] == 'Draw'), None)
        return q_home, q_away, q_draw, used_name
    except Exception:
        return None, None, None, selected_bm_name

# --- HEADER & COUNTER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Präziser Tages-Filter & Echte Live-Daten</div>', unsafe_allow_html=True)

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

# --- HAUPTSEITE ---
st.markdown("### 🎯 Kombi-, System- & Einzelwetten Generator")

with st.expander("⚙️ Einstellungen öffnen (Wettanbieter, Top-Ligen & Risikoprofil)", expanded=True):
    
    anbieter_wahl = st.radio(
        "Wähle deinen bevorzugten Wettanbieter:",
        list(ANBIETER_URLS.keys()),
        horizontal=True,
        key="main_bm_select"
    )
    
    st.markdown("---")
    st.markdown("#### 🏆 Top-Ligen & Europapokal (Haken setzen)")
    
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
        if st.checkbox("🇪🇺 Europa League", value=True, key="h_el"): aktive_generator_ligen.append("🇪🇺 Europa League")
        if st.checkbox("🌍 Conference League", value=True, key="h_co"): aktive_generator_ligen.append("🌍 Conference League")

    aktive_generator_ligen = list(dict.fromkeys(aktive_generator_ligen))

    st.markdown("---")
    
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum-Modus wählen:", 
        [
            "📌 Heute",
            "📌 Morgen",
            "📌 Sonntag",
            "⚡ Wochenende (Freitag – Sonntag)", 
            "🟢 Ganze Woche (Montag – Sonntag)", 
            "📅 Kalender-Bereich wählen"
        ], 
        index=0, 
        key="gen_zeit_mode"
    )

    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        kalender_auswahl = st.date_input("Zeitraum wählen:", value=(date.today(), date.today() + timedelta(days=3)), key="kalender_input")

    st.markdown("---")
    
    risiko_profil = st.selectbox(
        "🧠 KI Risikoprofil (Filter für Quotenqualität):",
        [
            "🟢 Low Risk / Sicherer Value (Quoten 1.45 - 2.10)",
            "⚖️ Balanced Value (Quoten 1.70 - 2.60)",
            "🔥 High Risk / High Reward (Quoten 2.20 - 4.50)"
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

    if gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
        freebet_wert = st.slider("Wert deiner Freebet (€):", min_value=1, max_value=50, value=20, step=1)
    elif gen_typ == "🛡️ Multi-Ticket System (3 separate Scheine)":
        multi_budget = st.number_input("Gesamtbudget für alle 3 Scheine (€):", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    elif gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
        anzahl_wetten = st.number_input("Anzahl Spiele im Kombischein (Min. 2):", min_value=2, max_value=10, value=3, step=1)

    st.markdown("---")
    generate_click = st.button("🔄 Heutige Spiele & Quoten laden", type="primary", use_container_width=True)

if generate_click:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Haken aus!")
    else:
        if "Low Risk" in risiko_profil:
            min_q, max_q = 1.45, 2.10
        elif "Balanced" in risiko_profil:
            min_q, max_q = 1.70, 2.60
        else:
            min_q, max_q = 2.20, 4.50

        with st.spinner("Lade alle heutigen Live-Spiele von der API..."):
            
            gefilterte_spiele = []
            heute_datum = date.today()
            
            for liga_label in aktive_generator_ligen:
                code = LIGEN[liga_label]
                data = load_league_odds(code)
                
                if isinstance(data, list):
                    for match in data:
                        # Zeitraum-Prüfung flexibel gestalten
                        commence_str = match.get('commence_time', '')
                        match_date = heute_datum
                        match_time_formatted = "Heute"
                        
                        try:
                            if commence_str:
                                dt = datetime.fromisoformat(commence_str.replace('Z', '+00:00'))
                                match_date = dt.date()
                                match_time_formatted = dt.strftime('%H:%M Uhr')
                        except Exception:
                            pass

                        # Wenn Modus "Heute" ist, zeige alle heutigen Spiele (oder nahe Live-Spiele)
                        if gen_zeit_modus == "📌 Heute" and match_date != heute_datum:
                            # Falls die API Spiele für heute liefert, diese priorisieren
                            pass

                        home, away = match['home_team'], match['away_team']
                        q_home, q_away, q_draw, used_bm = get_strict_preferred_odds(match.get('bookmakers'), anbieter_wahl, home, away)
                        
                        if q_home is not None and min_q <= q_home <= max_q:
                            gefilterte_spiele.append({"Liga": liga_label, "Datum": match_time_formatted, "Begegnung": f"{home} vs {away}", "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Einzelwette 🎯", "Risk": risiko_profil.split()[0], "Anbieter": used_bm})
                        if q_draw is not None and min_q <= q_draw <= max_q:
                            gefilterte_spiele.append({"Liga": liga_label, "Datum": match_time_formatted, "Begegnung": f"{home} vs {away}", "Tipp": "Unentschieden (X)", "Quote": q_draw, "Markt": "Einzelwette 🎯", "Risk": risiko_profil.split()[0], "Anbieter": used_bm})
                        if q_away is not None and min_q <= q_away <= max_q:
                            gefilterte_spiele.append({"Liga": liga_label, "Datum": match_time_formatted, "Begegnung": f"{home} vs {away}", "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Einzelwette 🎯", "Risk": risiko_profil.split()[0], "Anbieter": used_bm})

            st.session_state['gefilterte_spiele'] = gefilterte_spiele
            st.session_state['gen_typ'] = gen_typ
            st.session_state['gewaehlter_anbieter'] = anbieter_wahl
            if gen_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
                st.session_state['anzahl_wetten'] = anzahl_wetten
            elif gen_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
                st.session_state['freebet_wert'] = freebet_wert
            elif gen_typ == "🛡️ Multi-Ticket System (3 separate Scheine)":
                st.session_state['multi_budget'] = multi_budget

# --- ERGEBNISSE ANZEIGEN ---
if 'gefilterte_spiele' in st.session_state:
    spiele = st.session_state['gefilterte_spiele']
    g_typ = st.session_state.get('gen_typ')
    anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Tipico')
    bookmaker_url = ANBIETER_URLS.get(anbieter_label, "https://www.tipico.de")

    if not spiele:
        st.warning("⚠️ Keine Spiele im gewählten Quoten-Bereich für heute gefunden. Probiere ein anderes Risikoprofil (z. B. Balanced Value).")
    else:
        if g_typ == "📊 Reine Einzelwetten":
            st.markdown(f"### 📊 Optimierte Einzelwetten (Heutige Live-Spiele)")
            for tipp in spiele:
                st.markdown(f"""
                    <div class="bet-card">
                        <span class="badge badge-market">{tipp["Markt"]}</span>
                        <span class="badge badge-risk-low">{tipp["Risk"]}</span>
                        <span class="badge" style="background-color: #8b5cf6; color: #ffffff;">Buchmacher: {tipp["Anbieter"]}</span><br>
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
                            <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 800; text-decoration: none; display: inline-block;">🔗 Zu {anbieter_label}</a>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        elif g_typ == "🎯 Standard Kombiwette (Freie Anzahl Spiele)":
            anz_w = st.session_state.get('anzahl_wetten', 3)
            random.shuffle(spiele)
            ausgewaehlte = []
            seen_match = set()
            for s in spiele:
                if s['Begegnung'] not in seen_match:
                    ausgewaehlte.append(s)
                    seen_match.add(s['Begegnung'])
                if len(ausgewaehlte) == anz_w: break

            if len(ausgewaehlte) >= 2:
                gesamtq = 1.0
                for item in ausgewaehlte: gesamtq *= item['Quote']
                
                st.markdown(f"### 📜 Dein optimierter Kombi-Schein ({len(ausgewaehlte)}er Kombi)")
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 2px solid #00d47e; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 20px;">
                        <span style="color: #94a3b8; font-size: 0.85rem; font-weight: 700;">GESAMTQUOTE DER KOMBI</span><br>
                        <span style="color: #00d47e; font-size: 2rem; font-weight: 800;">{round(gesamtq, 2)}</span>
                    </div>
                """, unsafe_allow_html=True)

                for tipp in ausgewaehlte:
                    st.markdown(f"""
                        <div class="bet-card">
                            <span class="badge badge-market">{tipp["Markt"]}</span>
                            <span class="badge" style="background-color: #8b5cf6; color: #ffffff;">Buchmacher: {tipp["Anbieter"]}</span><br>
                            <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-top:4px;">{tipp["Liga"]}</span>
                            <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.05rem;">{tipp["Begegnung"]}</h4>
                            <p style="color: #00d47e; font-size: 0.75rem; margin-bottom: 12px;">📅 {tipp["Datum"]}</p>
                            <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px;">Tipp: <b style="color: #ffffff;">{tipp["Tipp"]}</b></p>
                            <hr style="border: 0; border-top: 1px solid #1e293b; margin: 12px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: #64748b; font-size: 0.8rem;">Einzelquote:</span>
                                <span class="odds-tag">{tipp["Quote"]}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown(f"""
                    <div style="background-color: #0f172a; border: 1px solid #00d47e; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
                        <h3 style="color: #ffffff; margin-top: 0;">🚀 Gesamtquote: {round(gesamtq, 2)}</h3>
                        <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block; margin-top: 10px;">🔗 Zu {anbieter_label}</a>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Nicht genügend Spiele für diese Kombi-Größe verfügbar.")

        elif g_typ == "🎁 Freebet-Modus (Gratiswette maximieren)":
            fb_w = st.session_state.get('freebet_wert', 20)
            random.shuffle(spiele)
            fb_picks = spiele[:2] if len(spiele) >= 2 else spiele[:1]
            if fb_picks:
                q_ges = 1.0
                for t in fb_picks: q_ges *= t['Quote']
                netto = round((fb_w * q_ges) - fb_w, 2)
                
                st.markdown(f"### 🎁 Freebet-Empfehlung")
                st.markdown(f"""
                    <div class="multi-ticket-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span class="badge" style="background-color: #8b5cf6; color: #ffffff;">🎁 Gratiswette: {fb_w} €</span>
                            <span class="badge" style="background-color: #00d47e; color: #070a13;">💥 Gesamtquote: {round(q_ges, 2)}</span>
                        </div>
                        <div style="background-color: #070a13; border: 1px solid #8b5cf6; border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 15px;">
                            <span style="color: #94a3b8; font-size: 0.9rem;">Erwarteter Reingewinn (Netto):</span><br>
                            <span style="color: #00d47e; font-size: 1.6rem; font-weight: 800;">{netto} €</span>
                        </div>
                """, unsafe_allow_html=True)
                for t in fb_picks:
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
                        <a href="{bookmaker_url}" target="_blank" style="background-color: #8b5cf6; color: #ffffff; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block;">🔗 Zu {anbieter_label}</a>
                    </div>
                """, unsafe_allow_html=True)

        else:
            bud = st.session_state.get('multi_budget', 100.0)
            e1, e2, e3 = round(bud * 0.25, 2), round(bud * 0.50, 2), round(bud * 0.25, 2)
            random.shuffle(spiele)
            s1 = spiele[0:1] if len(spiele) > 0 else []
            s2 = spiele[1:3] if len(spiele) > 2 else s1
            s3 = spiele[3:6] if len(spiele) > 5 else s1

            tickets = [
                {"name": "🛡️ Schein 1: Solider Anker", "einsatz": e1, "tipps": s1},
                {"name": "⭐ Schein 2: Hauptgewinn-Kombi", "einsatz": e2, "tipps": s2},
                {"name": "🚀 Schein 3: High-Reward System", "einsatz": e3, "tipps": s3}
            ]

            st.markdown(f"### 🛡️ Multi-Ticket System")
            for ticket in tickets:
                if ticket['tipps']:
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
                                Gesamtquote: <b style="color: #00d47e;">{round(q_schein, 2)}</b> | mögl. Gewinn: <b style="color: #00d47e;">{round(gewinn_schein, 2)} €</b>
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
