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

def get_total_api_stats():
    total_remaining = 0
    total_used = 0
    for key in API_KEYS:
        try:
            res = requests.get(f"https://api.the-odds-api.com/v4/sports/?apiKey={key}")
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
            res = requests.get(url)
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
        transition: all 0.2s ease;
    }
    .bet-card:hover {
        border-color: #00d47e;
        transform: translateY(-2px);
    }
    .owner-tag {
        color: #00d47e;
        font-weight: 700;
        letter-spacing: 2.5px;
        text-transform: uppercase;
        font-size: 0.75rem;
        margin-bottom: 4px;
    }
    .main-title {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-bottom: 15px;
    }
    .badge {
        background-color: #00d47e;
        color: #070a13;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 800;
        display: inline-block;
        margin-bottom: 6px;
        text-transform: uppercase;
    }
    .badge-market { background-color: #2563eb; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.25rem; font-weight: 800; }
    .counter-box {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 10px 14px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #0f172a;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #1e293b;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e293b !important;
        color: #00d47e !important;
    }
    </style>
""", unsafe_allow_html=True)

TOP_STUERMER = {
    "FC Bayern München": "Harry Kane", "Bayern Munich": "Harry Kane",
    "Eintracht Frankfurt": "Omar Marmoush", "Borussia Dortmund": "Serhou Guirassy",
    "Bayer Leverkusen": "Victor Boniface", "RB Leipzig": "Loïs Openda",
    "VfB Stuttgart": "Deniz Undav", "Manchester City": "Erling Haaland",
    "Liverpool": "Mohamed Salah", "Arsenal": "Bukayo Saka",
    "Chelsea": "Cole Palmer", "Tottenham Hotspur": "Son Heung-min",
    "Real Madrid": "Kylian Mbappé", "FC Barcelona": "Robert Lewandowski", "Barcelona": "Robert Lewandowski",
    "Atletico Madrid": "Antoine Griezmann", "Inter Milan": "Lautaro Martínez", "Inter": "Lautaro Martínez",
    "Juventus": "Dušan Vlahović", "Paris Saint-Germain": "Ousmane Dembélé", "PSG": "Ousmane Dembélé",
    "Galatasaray": "Victor Osimhen", "Fenerbahce": "Edin Džeko", "Besiktas": "Ciro Immobile"
}

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
    if prob >= 40: return "🟢 Low Risk (Sehr sicher)"
    elif prob >= 22: return "🟡 Medium Risk (Solide Chance)"
    elif prob >= 10: return "🟠 High Risk (Risikoreich)"
    else: return "🔴 Harakiri / Verrückt"

# --- HEADER & COUNTER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Europäische Top-Ligen, 11 API-Keys Gesamt-Tracking & Live-Filter</div>', unsafe_allow_html=True)

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
    st.markdown("💡 Abgelaufene Spiele werden automatisch blockiert.")

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
    st.markdown("### 🎯 Intelligenter KI Kombi-Generator")
    
    with st.expander("⚙️ Ligen- & Ziel-Einstellungen (Hier klicken zum Öffnen)", expanded=True):
        generator_ligen_modus = st.radio(
            "Ligen-Auswahl für diesen Schein:",
            ["🌍 Alle europäischen Top-Ligen nutzen", "📋 Ligen manuell separat auswählen"],
            index=0
        )
        
        if generator_ligen_modus == "📋 Ligen manuell separat auswählen":
            aktive_generator_ligen = st.multiselect(
                "Wähle deine Ligen für den Kombi-Schein:",
                options=list(LIGEN.keys()),
                default=["🇩🇪 Deutschland (Bundesliga)", "🇪🇸 Spanien (La Liga)"]
            )
        else:
            aktive_generator_ligen = list(LIGEN.keys())
            
        st.markdown("---")
        use_target_mode = st.checkbox("🎯 Ziel-Gewinn-Modus aktivieren (Einsatz ➔ Wunsch-Gewinn)", value=False)
        
        if use_target_mode:
            col_e1, col_g1 = st.columns(2)
            with col_e1: einsatz_target = st.number_input("Einsatz (€):", min_value=1.0, max_value=1000.0, value=10.0, step=5.0)
            with col_g1: gewinn_target = st.number_input("Wunsch-Gewinn (€):", min_value=2.0, max_value=2000.0, value=100.0, step=10.0)
            ziel_quote = round(gewinn_target / einsatz_target, 2)
            st.info(f"💡 Benötigte Gesamtquote: **{ziel_quote}**")
        else:
            anzahl_wetten = st.number_input("Anzahl der Wetten (Max. 3):", min_value=2, max_value=3, value=3, step=1)

        st.markdown("<br>", unsafe_allow_html=True)
        generate_click = st.button("🔄 KI Kombi-Schein generieren", type="primary", use_container_width=True)

    if generate_click:
        if not aktive_generator_ligen: 
            st.error("Bitte wähle mindestens eine Liga aus!")
        else:
            bm_code = DEUTSCHE_ANBIETER.get(anbieter_wahl, "bwin")
            offset_w = WOCHEN_OPTIONS[gewaehlte_woche_label]
            moegliche_tipps = []
            
            if use_target_mode:
                soll_einzelquote = ziel_quote ** (1 / 3)
                q_min = max(1.40, soll_einzelquote * 0.70)
                q_max = max(2.50, soll_einzelquote * 1.30)
            else:
                q_min, q_max = (1.40, 2.10)
            
            with st.spinner("Durchsuche die gewählten Ligen..."):
                for liga_label in aktive_generator_ligen:
                    code = LIGEN[liga_label]
                    data = load_league_odds(code)
                    if isinstance(data, list):
                        for match in data:
                            match_time, ist_gueltig = check_und_format_woche_und_zukunft(match.get('commence_time'), offset_w)
                            if not ist_gueltig: continue
                            home, away = match['home_team'], match['away_team']
                            q_home, q_away, q_draw, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                            
                            if q_home or q_away:
                                if q_home and q_min <= q_home <= q_max:
                                    moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Hauptwette 🛡️"})
                                if q_away and q_min <= q_away <= q_max:
                                    moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Hauptwette 🛡️"})
                                if q_home and q_home <= 1.85:
                                    pushed_q_h = round(q_home * 1.42, 2)
                                    if q_min <= pushed_q_h <= q_max * 1.25:
                                        moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {home} & Über 1.5 Tore", "Quote": pushed_q_h, "Markt": "Konfigurator 💥"})
                                if q_away and q_away <= 1.85:
                                    pushed_q_a = round(q_away * 1.45, 2)
                                    if q_min <= pushed_q_a <= q_max * 1.25:
                                        moegliche_tipps.append({"Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time, "Tipp": f"Sieg {away} & Über 1.5 Tore", "Quote": pushed_q_a, "Markt": "Konfigurator 💥"})

            if len(moegliche_tipps) >= 2:
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
                        if len(kombi_auswahl) == anzahl_wetten: break
                    st.session_state['preset_einsatz'] = 10.0

                st.session_state['kombi_auswahl'] = kombi_auswahl
                st.session_state['gewaehlter_anbieter'] = anbieter_wahl
                st.session_state['gewaehlte_woche'] = gewaehlte_woche_label
            else: 
                st.warning("Für die ausgewählten Ligen sind derzeit nicht genügend zukünftige Spiele verfügbar.")

    if 'kombi_auswahl' in st.session_state and st.session_state['kombi_auswahl']:
        kombi_auswahl = st.session_state['kombi_auswahl']
        anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Tipico')
        wochen_label = st.session_state.get('gewaehlte_woche', 'Spielwoche')
        preset_einsatz = st.session_state.get('preset_einsatz', 10.0)
        
        gesamtquote = 1.0
        for item in kombi_auswahl: gesamtquote *= item['Quote']
        schein_wahrscheinlichkeit = max(8, min(85, round((1 / gesamtquote) * 100 * 1.15)))
        risk_text = get_risk_label(schein_wahrscheinlichkeit)
        bookmaker_url = ANBIETER_URLS.get(anbieter_label, "https://www.tipico.de")
            
        st.markdown(f"### 📜 Dein KI Kombi-Schein ({len(kombi_auswahl)}er Kombi — {wochen_label})")
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
        
        col_action1, col_action2 = st.columns(2)
        with col_action1:
            with st.expander("🗂️ Wettscheine-Historie"):
                if st.radio("Speichern?", ["Nein", "Ja"], key="save_rad") == "Ja":
                    t_name = st.text_input("Name:", value=f"Kombi ({wochen_label})")
                    if st.button("💾 Speichern"):
                        st.session_state['saved_tickets'].append({"name": t_name, "date": datetime.now().strftime("%d.%m.%Y %H:%M"), "anbieter": anbieter_label, "quote": round(gesamtquote, 2), "tipps": kombi_auswahl})
                        st.success("Gespeichert!")
        with col_action2:
            with st.expander("📋 WhatsApp Export"):
                share_text = f"🔥 *KI-Kombi-Schein ({anbieter_label})* 🔥\n"
                for t in kombi_auswahl: share_text += f"• {t['Begegnung']} ➔ *{t['Tipp']}* (Q: {t['Quote']})\n"
                share_text += f"💥 *Gesamtquote:* {round(gesamtquote, 2)} ({risk_text})"
                st.code(share_text)

        st.markdown("### 💰 Bankroll-Management")
        col_q, col_prob, col_bank, col_einsatz, col_gewinn = st.columns([1, 1, 1, 1, 1.2])
        with col_q: st.metric(label="💥 Gesamtquote", value=f"{round(gesamtquote, 2)}")
        with col_prob: st.metric(label="📈 Chance", value=f"~{schein_wahrscheinlichkeit}%", delta=risk_text)
        with col_bank:
            tot_b = st.number_input("Guthaben (€):", min_value=10.0, value=100.0, step=10.0)
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
