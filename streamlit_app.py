import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timezone, timedelta

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

# --- DESIGNER CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    .bet-card {
        background: linear-gradient(135deg, #111827 0%, #0d1320 100%);
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
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
    .odds-tag { color: #00d47e; font-size: 1.25rem; font-weight: 800; }
    .counter-box {
        background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
        padding: 10px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px; background-color: #0f172a; padding: 6px; border-radius: 12px; border: 1px solid #1e293b;
    }
    .stTabs [data-baseweb="tab"] { height: 42px; border-radius: 8px; color: #94a3b8; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #1e293b !important; color: #00d47e !important; }
    </style>
""", unsafe_allow_html=True)

LIGEN = {
    "🇩🇪 Deutschland (Bundesliga)": "soccer_germany_bundesliga",
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
    "Neo.bet": "https://www.neo.bet/de",
    "bwin (Deutschland)": "https://sports.bwin.de",
    "Bet-at-home": "https://www.bet-at-home.com",
    "Bet365 (DE)": "https://www.bet365.de",
    "Betano": "https://www.betano.de",
    "Oddset": "https://www.oddset.de"
}

DEUTSCHE_ANBIETER = {
    "Tipico": "bwin", "Neo.bet": "bwin", "bwin (Deutschland)": "bwin",
    "Bet-at-home": "betathome", "Bet365 (DE)": "bet365", "Betano": "bwin", "Oddset": "bwin"
}

WOCHEN_OPTIONS = {
    "🟢 Dieses Wochenende (Aktuelle Woche)": 0,
    "⏩ Nächste Woche (+1 Woche)": 1,
    "⏩ Übernächste Woche (+2 Wochen)": 2,
    "⏩ In 3 Wochen (+3 Wochen)": 3,
    "⏩ In 4 Wochen (+4 Wochen)": 4
}

def check_und_format_woche_und_zukunft(date_str, offset_wochen):
    if not date_str: return "Unbekannt", False
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        jetzt = datetime.now(timezone.utc)
        ist_in_zukunft = dt > jetzt
        start_zielwoche = jetzt + timedelta(weeks=offset_wochen)
        end_zielwoche = start_zielwoche + timedelta(days=7)
        ist_in_zielwoche = (dt >= start_zielwoche) and (dt < end_zielwoche)
        return dt.strftime("%d.%m.%Y um %H:%M Uhr"), (ist_in_zielwoche and ist_in_zukunft)
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
    st.markdown('<div class="sub-title">Multi-Ticket Bankroll-Allocation & Low-Risk System</div>', unsafe_allow_html=True)

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

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Steuerungs-Panel")
    anbieter_wahl = st.selectbox("Wettanbieter wählen:", list(ANBIETER_URLS.keys()), key="sidebar_bm")
    gewaehlte_woche_label = st.selectbox("Spielwoche wählen:", list(WOCHEN_OPTIONS.keys()), key="sidebar_woche")
    st.markdown("---")
    st.markdown("💡 Multi-Schein System aktiv.")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📊 1. Einzelne Liga & Value-Bets", "🎯 2. KI Kombi-Generator", "🗂️ 3. Gespeicherte Wettscheine"])

with tab1:
    st.markdown("### 📊 Einzelne Liga & Spielwoche analysieren")
    Einzelne_Liga_Auswahl = st.selectbox("Einzelne Liga für Ansicht wählen:", list(LIGEN.keys()), key="l_tab1_single")
    if st.button("🔍 Spiele & Wahrscheinlichkeiten laden", use_container_width=True, type="primary"):
        liga_code = LIGEN[Einzelne_Liga_Auswahl]
        bm_code = DEUTSCHE_ANBIETER.get(anbieter_wahl, "bwin")
        offset_w = WOCHEN_OPTIONS[gewaehlte_woche_label]
        with st.spinner(f"Analysiere Quoten für {Einzelne_Liga_Auswahl}..."):
            data = load_league_odds(liga_code)
            if isinstance(data, list) and len(data) > 0:
                spiele_liste = []
                for match in data:
                    match_time, ist_gueltig = check_und_format_woche_und_zukunft(match.get('commence_time'), offset_w)
                    if not ist_gueltig: continue
                    home, away = match['home_team'], match['away_team']
                    q_home, q_away, q_draw, is_value = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                    prob_h = round((1 / q_home) * 100) if q_home else 0
                    spiele_liste.append({
                        "Anstoßzeit": match_time, "Heim": home, "Auswärts": away,
                        "Quote 1": q_home, "Quote X": q_draw, "Quote 2": q_away,
                        "Sieg-Chance Heim": f"{prob_h}%", "Markt-Status": "🔥 VALUE-BET" if is_value else "Standard"
                    })
                if spiele_liste:
                    st.dataframe(pd.DataFrame(spiele_liste), use_container_width=True, hide_index=True)
                else: st.info("Keine anstehenden Begegnungen gefunden.")
            else: st.error("Keine Spiele gefunden oder API-Limit erreicht.")

with tab2:
    st.markdown("### 🎯 Intelligenter KI Kombi-Generator & Multi-Ticket System")
    
    with st.expander("⚙️ Ligen- & Budget-Einstellungen (Hier klicken zum Öffnen)", expanded=True):
        generator_ligen_modus = st.radio(
            "Ligen-Auswahl für diesen Schein:",
            ["🌍 Alle europäischen Top-Ligen nutzen", "☑️ Ligen per Häkchen einzeln wählen"],
            index=0
        )
        
        aktive_generator_ligen = []
        if generator_ligen_modus == "☑️ Ligen per Häkchen einzeln wählen":
            st.markdown("<p style='color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px;'>Klicke auf die Häkchen:</p>", unsafe_allow_html=True)
            col_cb1, col_cb2 = st.columns(2)
            temp_selected = []
            for i, liga_name in enumerate(LIGEN.keys()):
                target_col = col_cb1 if i % 2 == 0 else col_cb2
                with target_col:
                    is_checked = st.checkbox(liga_name, value=(i < 2), key=f"chk_liga_{i}")
                    if is_checked:
                        temp_selected.append(liga_name)
            aktive_generator_ligen = temp_selected
        else:
            aktive_generator_ligen = list(LIGEN.keys())
            
        st.markdown("---")
        
        # Generator-Modus Wahl
        gen_typ = st.radio(
            "Generator-Modus wählen:",
            ["Standard (Einzelner Schein nach Wunsch)", "🛡️ Multi-Ticket System (3 separate Scheine aus deinem Budget)"],
            index=0
        )
        
        if gen_typ == "Standard (Einzelner Schein nach Wunsch)":
            use_target_mode = st.checkbox("🎯 Ziel-Gewinn-Modus aktivieren (Einsatz ➔ Wunsch-Gewinn)", value=False)
            if use_target_mode:
                col_e1, col_g1 = st.columns(2)
                with col_e1: einsatz_target = st.number_input("Einsatz (€):", min_value=1.0, max_value=1000.0, value=20.0, step=5.0)
                with col_g1: gewinn_target = st.number_input("Wunsch-Gewinn (€):", min_value=2.0, max_value=2000.0, value=100.0, step=10.0)
                ziel_quote = round(gewinn_target / einsatz_target, 2)
            else:
                anzahl_wetten = st.selectbox("Anzahl der Wetten auf dem Schein:", [2, 3], index=0)
        else:
            multi_budget = st.number_input("Gesamtbudget für alle 3 Scheine (€):", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)

        st.markdown("<br>", unsafe_allow_html=True)
        generate_click = st.button("🔄 KI Kombi-Schein(e) generieren", type="primary", use_container_width=True)

    if generate_click:
        if not aktive_generator_ligen: 
            st.error("Bitte wähle mindestens eine Liga per Häkchen aus!")
        else:
            bm_code = DEUTSCHE_ANBIETER.get(anbieter_wahl, "bwin")
            offset_w = WOCHEN_OPTIONS[gewaehlte_woche_label]
            
            with st.spinner("Durchsuche die gewählten Ligen und optimiere Risiko-Verteilung..."):
                if gen_typ == "Standard (Einzelner Schein nach Wunsch)":
                    moegliche_tipps = []
                    if use_target_mode:
                        anz_spiele = 3 if ziel_quote >= 3.5 else 2
                        soll_einzelquote = ziel_quote ** (1 / anz_spiele)
                        q_min = max(1.30, soll_einzelquote * 0.75)
                        q_max = max(2.20, soll_einzelquote * 1.25)
                    else:
                        anz_spiele = anzahl_wetten
                        q_min, q_max = (1.30, 1.75)
                    
                    for liga_label in aktive_generator_ligen:
                        code = LIGEN[liga_label]
                        data = load_league_odds(code)
                        if isinstance(data, list):
                            for match in data:
                                match_time, ist_gueltig = check_und_format_woche_und_zukunft(match.get('commence_time'), offset_w)
                                if not ist_gueltig: continue
                                home, away = match['home_team'], match['away_team']
                                q_home, q_away, q_draw, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                                if q_home and q_min <= q_home <= q_max:
                                    moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Sicherer Favorit 🛡️"})
                                if q_away and q_min <= q_away <= q_max:
                                    moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Sicherer Favorit 🛡️"})

                    if len(moegliche_tipps) >= anz_spiele:
                        random.shuffle(moegliche_tipps)
                        ausgewaehlte_spiele = set()
                        kombi_auswahl = []
                        if use_target_mode:
                            aktuelle_quote = 1.0
                            for tipp in moegliche_tipps:
                                if tipp['Begegnung'] not in ausgewaehlte_spiele:
                                    kombi_auswahl.append(tipp)
                                    ausgewaehlte_spiele.add(tipp['Begegnung'])
                                    aktuelle_quote *= tipp['Quote']
                                    if aktuelle_quote >= ziel_quote or len(kombi_auswahl) == 3:
                                        break
                            st.session_state['preset_einsatz'] = einsatz_target
                        else:
                            for tipp in moegliche_tipps:
                                if tipp['Begegnung'] not in ausgewaehlte_spiele:
                                    kombi_auswahl.append(tipp)
                                    ausgewaehlte_spiele.add(tipp['Begegnung'])
                                if len(kombi_auswahl) == anz_spiele: break
                            st.session_state['preset_einsatz'] = 20.0

                        st.session_state['multi_mode'] = False
                        st.session_state['kombi_auswahl'] = kombi_auswahl
                        st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                        st.session_state['gewaehlte_woche'] = gewaehlte_woche_label
                    else:
                        st.warning("Nicht genügend Spiele im Zielbereich gefunden.")
                else:
                    # MULTI-TICKET MODUS (3 Scheine)
                    # Wir sammeln alle verfügbaren Spiele
                    alle_spiele_pool = []
                    for liga_label in aktive_generator_ligen:
                        code = LIGEN[liga_label]
                        data = load_league_odds(code)
                        if isinstance(data, list):
                            for match in data:
                                match_time, ist_gueltig = check_und_format_woche_und_zukunft(match.get('commence_time'), offset_w)
                                if not ist_gueltig: continue
                                home, away = match['home_team'], match['away_team']
                                q_home, q_away, q_draw, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                                if q_home: alle_spiele_pool.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home})
                                if q_away: alle_spiele_pool.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away})

                    if len(alle_spiele_pool) >= 6:
                        random.shuffle(alle_spiele_pool)
                        
                        # Budget-Aufteilung (z.B. bei 100€: Schein 1 = 50€, Schein 2 = 30€, Schein 3 = 20€)
                        e1 = round(multi_budget * 0.50, 2)
                        e2 = round(multi_budget * 0.30, 2)
                        e3 = round(multi_budget * 0.20, 2)
                        
                        used_matches = set()
                        
                        def pick_tips(count, q_min_val, q_max_val):
                            picked = []
                            for s in alle_spiele_pool:
                                if s['Begegnung'] not in used_matches and q_min_val <= s['Quote'] <= q_max_val:
                                    picked.append(s)
                                    used_matches.add(s['Begegnung'])
                                    if len(picked) == count: break
                            return picked

                        # Schein 1: Low-Risk Anker (2er Kombi, niedrige Quoten 1.25 - 1.55)
                        schein_1_tipps = pick_tips(2, 1.25, 1.55)
                        # Schein 2: Solide Value-Kombi (2er oder 3er, Quoten 1.45 - 1.85)
                        schein_2_tipps = pick_tips(2, 1.45, 1.85)
                        # Schein 3: High-Reward / System-Tipp (3er Kombi, etwas breiter gestreut)
                        schein_3_tipps = pick_tips(3, 1.40, 2.05)
                        
                        if schein_1_tipps and schein_2_tipps and schein_3_tipps:
                            st.session_state['multi_mode'] = True
                            st.session_state['multi_tickets'] = [
                                {"name": "🛡️ Schein 1: Low-Risk Anker", "einsatz": e1, "tipps": schein_1_tipps},
                                {"name": "⚖️ Schein 2: Solide Value-Kombi", "einsatz": e2, "tipps": schein_2_tipps},
                                {"name": "🚀 Schein 3: High-Reward System-Tipp", "einsatz": e3, "tipps": schein_3_tipps}
                            ]
                            st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                            st.session_state['gewaehlte_woche'] = gewaehlte_woche_label
                        else:
                            st.warning("Nicht genügend passende Spiele für die Multi-Ticket-Staffelung gefunden. Versuche mehr Ligen auszuwählen!")
                    else:
                        st.warning("Zu wenige anstehende Spiele für 3 separate Scheine verfügbar.")

    # ANZEIGE BEI MULTI-TICKET MODUS
    if st.session_state.get('multi_mode', False) and 'multi_tickets' in st.session_state:
        anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Tipico')
        wochen_label = st.session_state.get('gewaehlte_woche', 'Spielwoche')
        bookmaker_url = ANBIETER_URLS.get(anbieter_label, "https://www.tipico.de")
        
        st.markdown(f"### 🛡️ Dein Multi-Ticket System ({wochen_label}) — Aufgeteilt auf 3 separate Scheine")
        st.info("💡 **Profi-Tipp:** Dein Budget wurde intelligent gestaffelt. Sollte ein Schein unglücklich verloren gehen, fangen die anderen beiden Scheine das Risiko ab oder erzielen Gewinn!")
        
        gesamt_moeglicher_gewinn = 0
        gesamt_einsatz = 0
        
        for ticket in st.session_state['multi_tickets']:
            q_schein = 1.0
            for t in ticket['tipps']: q_schein *= t['Quote']
            gewinn_schein = ticket['einsatz'] * q_schein
            gesamt_moeglicher_gewinn += gewinn_schein
            gesamt_einsatz += ticket['einsatz']
            
            st.markdown(f"""
                <div class="bet-card">
                    <span class="badge" style="background-color: #00d47e; color: #070a13;">{ticket['name']}</span>
                    <span class="badge badge-market">Empfohlener Einsatz: {ticket['einsatz']} €</span>
                    <h4 style="color: #ffffff; margin: 10px 0 5px 0;">Gesamtquote: <span style="color: #00d47e;">{round(q_schein, 2)}</span> | Möglicher Gewinn: <span style="color: #00d47e;">{round(gewinn_schein, 2)} €</span></h4>
            """, unsafe_allow_html=True)
            
            for t in ticket['tipps']:
                st.write(f"• **{t['Begegnung']}** (📅 {t['Datum']}) ➔ Tipp: `{t['Tipp']}` (Quote: *{t['Quote']}*)")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.markdown(f"""
            <div style="background-color: #0f172a; border: 1px solid #00d47e; border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 20px;">
                <span style="color: #94a3b8;">Gesamteinsatz:</span> <b>{round(gesamt_einsatz, 2)} €</b> | 
                <span style="color: #94a3b8;">Maximaler Gesamtertrag:</span> <b style="color: #00d47e;">{round(gesamt_moeglicher_gewinn, 2)} €</b>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style="background-color: #0f172a; border: 1px solid #00d47e; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 20px;">
                <h3 style="color: #ffffff; margin-top: 0;">🚀 Direkt zu {anbieter_label}</h3>
                <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block; margin-top: 10px;">🔗 Jetzt {anbieter_label} öffnen & wetten</a>
            </div>
        """, unsafe_allow_html=True)

    # ANZEIGE BEI STANDARD MODUS
    elif not st.session_state.get('multi_mode', False) and 'kombi_auswahl' in st.session_state and st.session_state['kombi_auswahl']:
        kombi_auswahl = st.session_state['kombi_auswahl']
        anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Tipico')
        wochen_label = st.session_state.get('gewaehlte_woche', 'Spielwoche')
        preset_einsatz = st.session_state.get('preset_einsatz', 20.0)
        
        gesamtquote = 1.0
        for item in kombi_auswahl: gesamtquote *= item['Quote']
        schein_wahrscheinlichkeit = max(15, min(85, round((1 / gesamtquote) * 100 * 1.15)))
        risk_text = get_risk_label(schein_wahrscheinlichkeit)
        bookmaker_url = ANBIETER_URLS.get(anbieter_label, "https://www.tipico.de")
            
        st.markdown(f"### 📜 Dein optimierter KI-Schein ({len(kombi_auswahl)}er Kombi — {wochen_label})")
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
                <h3 style="color: #ffffff; margin-top: 0;">🚀 Direkt zu {anbieter_label}</h3>
                <a href="{bookmaker_url}" target="_blank" style="background-color: #00d47e; color: #070a13; padding: 12px 24px; border-radius: 8px; font-weight: 800; text-decoration: none; display: inline-block; margin-top: 10px;">🔗 Jetzt {anbieter_label} öffnen & wetten</a>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### 💰 Bankroll-Management")
        col_q, col_prob, col_bank, col_einsatz, col_gewinn = st.columns([1, 1, 1, 1, 1.2])
        with col_q: st.metric(label="💥 Gesamtquote", value=f"{round(gesamtquote, 2)}")
        with col_prob: st.metric(label="📈 Chance", value=f"~{schein_wahrscheinlichkeit}%", delta=risk_text)
        with col_bank:
            tot_b = st.number_input("Guthaben (€):", min_value=10.0, value=100.0, step=10.0, key="std_bank")
            st.caption(f"2%-Regel: **{round(tot_b * 0.02, 2)} €**")
        with col_einsatz: einsatz = st.number_input("Einsatz (€):", min_value=1.0, max_value=1000.0, value=preset_einsatz, step=5.0, key="rechner_einsatz")
        with col_gewinn: st.metric(label="🏆 Gewinn", value=f"{round(einsatz * gesamtquote, 2):.2f} €")

with tab3:
    st.markdown("### 🗂️ Deine gespeicherten Wettscheine")
    if not st.session_state['saved_tickets']:
        st.info("Bisher keine Scheine hinterlegt.")
    else:
        for idx, ticket in enumerate(st.session_state['saved_tickets']):
            st.markdown(f"**{ticket['name']}** — {ticket['anbieter']} (Gesamtquote: {ticket['quote']})")
            for t in ticket['tipps']: st.write(f"• {t['Begegnung']} ➔ {t['Tipp']} ({t['Quote']})")
            if st.button(f"Löschen #{idx+1}", key=f"del_{idx}"):
                st.session_state['saved_tickets'].pop(idx)
                st.rerun()
