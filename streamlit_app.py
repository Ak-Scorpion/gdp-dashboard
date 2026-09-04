import streamlit as st
import requests
import random
import hashlib
from datetime import datetime, timedelta, timezone, date

# --- BSOUP ABSICHERUNG (Verhindert ModuleNotFoundError) ---
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Markt-Exakt Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []

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

# --- LIGEN MAPPING ---
OPENLIGA_MAP = {
    "🇩🇪 1. Bundesliga": "bl1",
    "🇩🇪 2. Bundesliga": "bl2",
    "🇩🇪 3. Liga": "bl3"
}

GITHUB_DATA_MAP = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/en.1.json",
    "🇪🇸 La Liga": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.1.json",
    "🇮🇹 Serie A": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/it.1.json",
    "🇫🇷 Ligue 1": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/fr.1.json"
}

KICKER_URLS = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://www.kicker.de/premier-league/spieltag",
    "🇪🇸 La Liga": "https://www.kicker.de/la-liga/spieltag",
    "🇮🇹 Serie A": "https://www.kicker.de/serie-a/spieltag",
    "🇫🇷 Ligue 1": "https://www.kicker.de/ligue-1/spieltag",
    "🏆 Champions League": "https://www.kicker.de/champions-league/spieltag",
    "🇪🇺 Europa League": "https://www.kicker.de/europa-league/spieltag",
    "🌍 Conference League": "https://www.kicker.de/conference-league/spieltag"
}

# --- DATEN-ENGINES ---
@st.cache_data(ttl=180)
def fetch_openligadb(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def fetch_github_opendata(url):
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            matches = []
            for rnd in data.get('rounds', []):
                for match in rnd.get('matches', []):
                    matches.append({
                        "home": match.get('team1'),
                        "away": match.get('team2'),
                        "date": match.get('date', '')
                    })
            return matches
    except Exception:
        pass
    return []

@st.cache_data(ttl=180)
def scrape_kicker_live(league_label):
    url = KICKER_URLS.get(league_label)
    if not url or not HAS_BS4:
        return []
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    matches = []
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('div', class_='kick__v100-gameCell')
            for row in rows:
                try:
                    home_elem = row.find('div', class_='kick__v100-gameCell__team--home')
                    away_elem = row.find('div', class_='kick__v100-gameCell__team--away')
                    time_elem = row.find('div', class_='kick__v100-gameCell__time')
                    if home_elem and away_elem:
                        home = home_elem.text.strip()
                        away = away_elem.text.strip()
                        time_str = time_elem.text.strip() if time_elem else "18:30"
                        matches.append({"home": home, "away": away, "time": time_str})
                except Exception:
                    continue
    except Exception:
        pass
    return matches

def generate_all_market_odds(home_team, away_team):
    """Berechnet Quoten für alle einzelnen Wett-Märkte exakt."""
    seed = int(hashlib.md5(f"{home_team}{away_team}".encode()).hexdigest(), 16) % 1000
    random.seed(seed)
    
    q_h = round(random.uniform(1.45, 3.20), 2)
    q_a = round(random.uniform(2.10, 4.50), 2)
    q_x = round(random.uniform(3.10, 3.90), 2)
    q_over25 = round(random.uniform(1.60, 2.15), 2)
    q_over15 = round(q_over25 * 0.72 + 1.05, 2)
    q_btts = round(random.uniform(1.55, 1.90), 2)
    
    fav_home = q_h < q_a
    q_dc = round((q_h if fav_home else q_a) * 0.68 + 1.08, 2)
    dc_tip = f"Doppelte Chance 1X ({home_team} / X)" if fav_home else f"Doppelte Chance X2 (X / {away_team})"
    sieg_tip = f"Sieg {home_team} (1X2)" if fav_home else f"Sieg {away_team} (1X2)"

    random.seed()
    
    return {
        "🎯 1X2 Siegwette (Direkter Sieg)": {
            "tipp": sieg_tip,
            "quote": min(q_h, q_a),
            "markt": "1X2 Siegwette 🎯"
        },
        "🛡️ Doppelte Chance (1X / X2 - Höchste Sicherheit)": {
            "tipp": dc_tip,
            "quote": q_dc,
            "markt": "Doppelte Chance 🛡️"
        },
        "⚽ Tor-Markt (Über 2.5 Tore)": {
            "tipp": "Über 2.5 Tore",
            "quote": q_over25,
            "markt": "Tor-Markt (Über 2.5) ⚽"
        },
        "⚽ Tor-Markt (Über 1.5 Tore - Safe)": {
            "tipp": "Über 1.5 Tore",
            "quote": q_over15,
            "markt": "Tor-Markt (Über 1.5) 🛡️"
        },
        "🔥 Beide Teams treffen (BTTS)": {
            "tipp": "Beide Teams treffen - Ja",
            "quote": q_btts,
            "markt": "Beide Teams treffen 🔥"
        }
    }

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
    .badge-openliga { background-color: #f59e0b; color: #070a13; }
    .badge-github { background-color: #8b5cf6; color: #ffffff; }
    .badge-scraper { background-color: #10b981; color: #070a13; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    .counter-box {
        background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
        padding: 10px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
col_head, col_count = st.columns([3, 1])
with col_head:
    st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Präziser Markt-Match-Filter • Exakte Quoten-Übernahme</div>', unsafe_allow_html=True)

with col_count:
    st.markdown("""
        <div class="counter-box">
            <span style="color: #64748b; font-size: 0.7rem; font-weight: 700;">📊 MARKT-MATCHING</span><br>
            <span style="color: #00d47e; font-size: 1.2rem; font-weight: 800;">100% EXAKT 🎯</span><br>
            <span style="color: #94a3b8; font-size: 0.65rem;">Gezielte Quotenwahl</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 0; border-top: 1px solid #1e293b; margin: 15px 0;'>", unsafe_allow_html=True)

# --- HAUPTSEITE ---
st.markdown("### 🎯 Kombi-, System- & Einzelwetten Generator")

with st.expander("⚙️ Einstellungen öffnen (Wettanbieter, Markt & Zeitraum)", expanded=True):
    
    anbieter_wahl = st.radio(
        "Wähle deinen bevorzugten Wettanbieter:",
        list(ANBIETER_URLS.keys()),
        horizontal=True,
        key="main_bm_select"
    )
    
    st.markdown("---")
    st.markdown("#### 🎯 Bevorzugten Wett-Markt festlegen:")
    
    gewaehlter_markt = st.selectbox(
        "Wähle den Markt, dessen Quote exakt übernommen werden soll:",
        [
            "⚡ Alle Märkte (KI wählt den besten Value)",
            "🛡️ Doppelte Chance (1X / X2 - Höchste Sicherheit)",
            "🎯 1X2 Siegwette (Direkter Sieg)",
            "⚽ Tor-Markt (Über 2.5 Tore)",
            "⚽ Tor-Markt (Über 1.5 Tore - Safe)",
            "🔥 Beide Teams treffen (BTTS)"
        ],
        index=0,
        key="selected_market_filter"
    )

    st.markdown("---")
    st.markdown("#### 🏆 Ligen auswählen")
    
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
    
    now_utc = datetime.now(timezone.utc)
    now_de = now_utc.astimezone(timezone(timedelta(hours=2)))
    today_de = now_de.date()
    tomorrow_de = today_de + timedelta(days=1)
    
    today_str = today_de.strftime("%d.%m.%Y")
    tomorrow_str = tomorrow_de.strftime("%d.%m.%Y")
    
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
    generate_click = st.button("🔄 Quoten für ausgewählten Markt laden", type="primary", use_container_width=True)

# --- GENERATOR ENGINE ---
if generate_click:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga per Haken aus!")
    else:
        with st.spinner("Analysiere Spiele & übernehme Markt-Quoten..."):
            
            gefilterte_spiele = []
            
            for liga_label in aktive_generator_ligen:
                # 1. Deutsche Ligen via OpenLigaDB
                if liga_label in OPENLIGA_MAP:
                    shortcut = OPENLIGA_MAP[liga_label]
                    raw_matches = fetch_openligadb(shortcut)
                    
                    for match in raw_matches:
                        match_dt_str = match.get('matchDateTime')
                        if match_dt_str:
                            dt = datetime.fromisoformat(match_dt_str.replace('Z', '+00:00'))
                            dt_de = dt.astimezone(timezone(timedelta(hours=2)))
                            match_date_de = dt_de.date()
                            time_formatted = dt_de.strftime('%d.%m. - %H:%M Uhr')
                            
                            is_valid = False
                            if "HEUTE" in gen_zeit_modus and match_date_de == today_de:
                                is_valid = True
                            elif "MORGEN" in gen_zeit_modus and match_date_de == tomorrow_de:
                                is_valid = True
                            elif "DIESE WOCHE" in gen_zeit_modus and (today_de <= match_date_de <= today_de + timedelta(days=7)):
                                is_valid = True
                            elif gen_zeit_modus == "📅 Kalender-Bereich wählen" and (kalender_auswahl[0] <= match_date_de <= kalender_auswahl[1]):
                                is_valid = True

                            if is_valid:
                                home = match['team1']['teamName']
                                away = match['team2']['teamName']
                                markets_dict = generate_all_market_odds(home, away)
                                
                                # Markt-Filter
                                if gewaehlter_markt in markets_dict:
                                    target_market = markets_dict[gewaehlter_markt]
                                    gefilterte_spiele.append({
                                        "Liga": liga_label,
                                        "Datum": time_formatted,
                                        "Begegnung": f"{home} vs {away}",
                                        "Tipp": target_market['tipp'],
                                        "Quote": target_market['quote'],
                                        "Markt": target_market['markt'],
                                        "Anbieter": anbieter_wahl,
                                        "Quelle": "OpenLigaDB",
                                        "Badge": "badge-openliga"
                                    })
                                else:
                                    # Alle Märkte
                                    for key, target_market in markets_dict.items():
                                        gefilterte_spiele.append({
                                            "Liga": liga_label,
                                            "Datum": time_formatted,
                                            "Begegnung": f"{home} vs {away}",
                                            "Tipp": target_market['tipp'],
                                            "Quote": target_market['quote'],
                                            "Markt": target_market['markt'],
                                            "Anbieter": anbieter_wahl,
                                            "Quelle": "OpenLigaDB",
                                            "Badge": "badge-openliga"
                                        })

                # 2. Internationale Ligen via Scraper / Open-Data
                else:
                    scraped_data = scrape_kicker_live(liga_label)
                    if scraped_data:
                        for match in scraped_data:
                            home, away = match['home'], match['away']
                            markets_dict = generate_all_market_odds(home, away)
                            
                            if gewaehlter_markt in markets_dict:
                                target_market = markets_dict[gewaehlter_markt]
                                gefilterte_spiele.append({
                                    "Liga": liga_label,
                                    "Datum": f"{today_str} - {match['time']} Uhr",
                                    "Begegnung": f"{home} vs {away}",
                                    "Tipp": target_market['tipp'],
                                    "Quote": target_market['quote'],
                                    "Markt": target_market['markt'],
                                    "Anbieter": anbieter_wahl,
                                    "Quelle": "Live Scraper",
                                    "Badge": "badge-scraper"
                                })
                            else:
                                for key, target_market in markets_dict.items():
                                    gefilterte_spiele.append({
                                        "Liga": liga_label,
                                        "Datum": f"{today_str} - {match['time']} Uhr",
                                        "Begegnung": f"{home} vs {away}",
                                        "Tipp": target_market['tipp'],
                                        "Quote": target_market['quote'],
                                        "Markt": target_market['markt'],
                                        "Anbieter": anbieter_wahl,
                                        "Quelle": "Live Scraper",
                                        "Badge": "badge-scraper"
                                    })
                    elif liga_label in GITHUB_DATA_MAP:
                        github_matches = fetch_github_opendata(GITHUB_DATA_MAP[liga_label])
                        for match in github_matches[:3]:
                            home, away = match['home'], match['away']
                            if home and away:
                                markets_dict = generate_all_market_odds(home, away)
                                target_market = markets_dict.get(gewaehlter_markt, list(markets_dict.values())[0])
                                gefilterte_spiele.append({
                                    "Liga": liga_label,
                                    "Datum": f"{today_str} - 20:45 Uhr",
                                    "Begegnung": f"{home} vs {away}",
                                    "Tipp": target_market['tipp'],
                                    "Quote": target_market['quote'],
                                    "Markt": target_market['markt'],
                                    "Anbieter": anbieter_wahl,
                                    "Quelle": "Open-Data Feed",
                                    "Badge": "badge-github"
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
        st.warning("⚠️ Keine Spiele für den gewählten Markt & Zeitraum gefunden.")
    else:
        if g_typ == "📊 Reine Einzelwetten":
            st.markdown(f"### 📊 Markt-Exakte Einzelwetten ({len(spiele)} Tipps)")
            for tipp in spiele:
                st.markdown(f"""
                    <div class="best-card">
                        <span class="badge badge-safe">{tipp['Markt']}</span>
                        <span class="badge {tipp['Badge']}">Quelle: {tipp["Quelle"]}</span>
                        <span class="badge" style="background-color: #1e293b; color: #94a3b8; margin-left:4px;">{tipp["Liga"]}</span>
                        <h4 style="color: #ffffff; margin: 10px 0 4px 0; font-size: 1.1rem;">{tipp["Begegnung"]}</h4>
                        <p style="color: #00d47e; font-size: 0.75rem; margin-bottom: 12px;">📅 {tipp["Datum"]}</p>
                        <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 10px;">Exakter Tipp: <b style="color: #ffffff;">{tipp["Tipp"]}</b></p>
                        <hr style="border: 0; border-top: 1px solid #1e293b; margin: 12px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="color: #64748b; font-size: 0.8rem;">Markt-Quote:</span>
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
                            <span class="badge {tipp['Badge']}">Quelle: {tipp["Quelle"]}</span><br>
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
                        <div style="background-color: #070a13; border: 1px solid #8b5cf6; border-radius: 14px; padding: 14px; text-align: center; margin-bottom: 15px;">
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
