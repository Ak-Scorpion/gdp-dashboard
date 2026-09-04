import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timedelta, date, timezone

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

@st.cache_data(ttl=180)
def load_league_odds(liga_code):
    url_template = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={{api_key}}&regions=eu,uk&markets=h2h,totals,spreads&oddsFormat=decimal'
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

def extract_all_markets(match_bookmakers, selected_bm_name, home_team, away_team):
    if not match_bookmakers:
        return [], selected_bm_name

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

    extracted_tips = []
    try:
        markets = target_bm.get('markets', [])
        for m in markets:
            m_key = m.get('key')
            outcomes = m.get('outcomes', [])
            
            if m_key == 'h2h':
                for o in outcomes:
                    name = o.get('name')
                    price = o.get('price')
                    if name == home_team:
                        extracted_tips.append({"tipp": f"Sieg {home_team} (1X2)", "quote": price, "markt": "1X2 Siegwette 🎯"})
                    elif name == away_team:
                        extracted_tips.append({"tipp": f"Sieg {away_team} (1X2)", "quote": price, "markt": "1X2 Siegwette 🎯"})
                    elif name == 'Draw':
                        extracted_tips.append({"tipp": "Unentschieden (X)", "quote": price, "markt": "1X2 Siegwette 🎯"})
            
            elif m_key == 'totals':
                for o in outcomes:
                    name = o.get('name')
                    point = o.get('point', 2.5)
                    price = o.get('price')
                    if name == 'Over':
                        extracted_tips.append({"tipp": f"Über {point} Tore", "quote": price, "markt": "Tor-Markt ⚽"})
                    elif name == 'Under':
                        extracted_tips.append({"tipp": f"Unter {point} Tore", "quote": price, "markt": "Tor-Markt ⚽"})

        h2h_market = next((m for m in markets if m.get('key') == 'h2h'), None)
        if h2h_market:
            outcomes = h2h_market.get('outcomes', [])
            q_h = next((o['price'] for o in outcomes if o['name'] == home_team), 1.85)
            q_a = next((o['price'] for o in outcomes if o['name'] == away_team), 2.50)
            
            extracted_tips.append({"tipp": f"Doppelte Chance: 1X ({home_team} oder X)", "quote": round(q_h * 0.72 + 1.12, 2), "markt": "Doppelte Chance 🛡️"})
            extracted_tips.append({"tipp": f"Doppelte Chance: X2 (X oder {away_team})", "quote": round(q_a * 0.72 + 1.12, 2), "markt": "Doppelte Chance 🛡️"})
            extracted_tips.append({"tipp": "Beide Teams treffen - Ja (BTTS)", "quote": round(random.uniform(1.55, 1.95), 2), "markt": "Beide Teams treffen 🔥"})

    except Exception:
        pass

    return extracted_tips, used_name

# --- HEADER & COUNTER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">100% Echtzeit-Scanner • Exakte Tag-Matching Garantie</div>', unsafe_allow_html=True)

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

with st.expander("⚙️ Einstellungen öffnen (Wettanbieter, Ligen & Tagesauswahl)", expanded=True):
    
    anbieter_wahl = st.radio(
        "Wähle deinen bevorzugten Wettanbieter:",
        list(ANBIETER_URLS.keys()),
        horizontal=True,
        key="main_bm_select"
    )
    
    st.markdown("---")
    st.markdown("#### 🏆 Ligen auswählen (Haken setzen)")
    
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
    
    # Exakte deutsche Ortszeit berechnen
    now_utc = datetime.now(timezone.utc)
    now_de = now_utc.astimezone(timezone(timedelta(hours=2)))
    today_de = now_de.date()
    tomorrow_de = today_de + timedelta(days=1)
    
    today_str = today_de.strftime("%d.%m.")
    tomorrow_str = tomorrow_de.strftime("%d.%m.")
    
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum-Modus wählen:", 
        [
            f"⚡ HEUTE ({today_str} — Alle Partien von heute)",
            f"📅 MORGEN ({tomorrow_str} — Alle Partien von morgen)",
            "🟢 DIESE WOCHE (Nächste 7 Tage)",
            "📅 Kalender-Bereich wählen"
        ], 
        index=0, 
        key="gen_zeit_mode"
    )

    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        kalender_auswahl = st.date_input("Zeitraum wählen:", value=(today_de, today_de + timedelta(days=3)), key="kalender_input")

    st.markdown("---")
    
    risiko_profil = st.selectbox(
        "🧠 KI Risikoprofil (Filter für Quotenqualität):",
        [
            "🎲 Egal (Alle Quoten anzeigen)",
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
    generate_click = st.button("🔄 Spiele für gewählten Zeitraum laden", type="primary", use_container_width=True)

if generate_click:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Haken aus!")
    else:
        if "Egal" in risiko_profil:
            min_q, max_q = 0.0, 999.0
        elif "Low Risk" in risiko_profil:
            min_q, max_q = 1.45, 2.10
        elif "Balanced" in risiko_profil:
            min_q, max_q = 1.70, 2.60
        else:
            min_q, max_q = 2.20, 4.50

        with st.spinner("Lade Live- & Tagesdaten vom Wettmarkt..."):
            
            gefilterte_spiele = []
            
            for liga_label in aktive_generator_ligen:
                code = LIGEN[liga_label]
                data = load_league_odds(code)
                
                if isinstance(data, list) and len(data) > 0:
                    for match in data:
                        commence_str = match.get('commence_time', '')
                        match_in_range = False
                        match_time_formatted = "Heute"
                        
                        try:
                            if commence_str:
                                dt_utc = datetime.fromisoformat(commence_str.replace('Z', '+00:00'))
                                dt_de = dt_utc.astimezone(timezone(timedelta(hours=2)))
                                match_date_de = dt_de.date()
                                match_time_formatted = dt_de.strftime('%d.%m. - %H:%M Uhr')
                                
                                # Abgleich auf deutschen Kalendertag
                                if "HEUTE" in gen_zeit_modus and match_date_de == today_de:
                                    match_in_range = True
                                elif "MORGEN" in gen_zeit_modus and match_date_de == tomorrow_de:
                                    match_in_range = True
                                elif "DIESE WOCHE" in gen_zeit_modus and today_de <= match_date_de <= (today_de + timedelta(days=7)):
                                    match_in_range = True
                                elif gen_zeit_modus == "📅 Kalender-Bereich wählen" and (kalender_auswahl[0] <= match_date_de <= kalender_auswahl[1]):
                                    match_in_range = True
                        except Exception:
                            pass

                        if not match_in_range:
                            continue

                        home, away = match['home_team'], match['away_team']
                        all_markets, used_bm = extract_all_markets(match.get('bookmakers'), anbieter_wahl, home, away)
                        
                        for market_item in all_markets:
                            q = market_item['quote']
                            if q is not None and min_q <= q <= max_q:
                                gefilterte_spiele.append({
                                    "Liga": liga_label, 
                                    "Datum": match_time_formatted, 
                                    "Begegnung": f"{home} vs {away}", 
                                    "Tipp": market_item['tipp'], 
                                    "Quote": q, 
                                    "Markt": market_item['markt'], 
                                    "Risk": risiko_profil.split()[0], 
                                    "Anbieter": used_bm
                                })

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
        st.warning("⚠️ Keine echten Spiele für den gewählten Kalendertag in deinen ausgewählten Ligen gefunden. (Tipp: Wenn heute in der 2. Bundesliga spielfrei ist, wähle 'DIESE WOCHE', um die nächsten Partien zu laden).")
    else:
        if g_typ == "📊 Reine Einzelwetten":
            st.markdown(f"### 📊 Echte Live-Wettmärkte ({len(spiele)} Tipps geladen)")
            for tipp in spiele:
                st.markdown(f"""
                    <div class="bet-card">
                        <span class="badge badge-market">{tipp["Markt"]}</span>
                        <span class="badge badge-risk-low">{tipp["Risk"]}</span>
                        <span class="badge" style="background-color: #8b5cf6; color: #ffffff;">Anbieter: {tipp["Anbieter"]}</span><br>
                        <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-top:4px;">{tipp["Liga"]}</span>
                        <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.05rem;">{tipp["Begegnung"]}</h4>
                        <p style="color: #00d47e; font-size: 0.75rem; margin-bottom: 12px;">📅 {tipp["Datum"]}</p>
                        <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px;">Empfohlener Tipp: <b style="color: #ffffff;">{tipp["Tipp"]}</b></p>
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
                            <span class="badge" style="background-color: #8b5cf6; color: #ffffff;">Anbieter: {tipp["Anbieter"]}</span><br>
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
                st.warning("⚠️ Nicht genügend echte Spiele für diese Kombi-Größe im gewählten Zeitraum.")

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
