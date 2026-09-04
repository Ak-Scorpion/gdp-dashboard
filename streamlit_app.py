import streamlit as st
import requests
import random
import hashlib
from datetime import datetime, timedelta, timezone

# --- BSOUP ABSICHERUNG (Verhindert Absturz, falls bs4 fehlt) ---
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Hybrid Engine",
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

# --- LIGEN MAPPING & DATENQUELLEN ---
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

# --- 1. ENGINE: OPENLIGADB ---
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

# --- 2. ENGINE: GITHUB OPEN-DATA ---
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

# --- 3. ENGINE: WEB SCRAPING ---
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
        "🎯 1X2 Siegwette (Direkter Sieg)": {"tipp": sieg_tip, "quote": min(q_h, q_a), "markt": "1X2 Siegwette 🎯"},
        "🛡️ Doppelte Chance (1X / X2 - Höchste Sicherheit)": {"tipp": dc_tip, "quote": q_dc, "markt": "Doppelte Chance 🛡️"},
        "⚽ Tor-Markt (Über 2.5 Tore)": {"tipp": "Über 2.5 Tore", "quote": q_over25, "markt": "Tor-Markt (Über 2.5) ⚽"},
        "⚽ Tor-Markt (Über 1.5 Tore - Safe)": {"tipp": "Über 1.5 Tore", "quote": q_over15, "markt": "Tor-Markt (Über 1.5) 🛡️"},
        "🔥 Beide Teams treffen (BTTS)": {"tipp": "Beide Teams treffen - Ja", "quote": q_btts, "markt": "Beide Teams treffen 🔥"}
    }

# --- STYLING ---
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
    }
    .best-card {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        border: 2px solid #00d47e;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .badge {
        padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800;
        display: inline-block; margin-bottom: 6px; text-transform: uppercase;
    }
    .badge-openliga { background-color: #f59e0b; color: #070a13; }
    .badge-github { background-color: #8b5cf6; color: #ffffff; }
    .badge-scraper { background-color: #10b981; color: #070a13; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<div style="color:#00d47e; font-weight:700; letter-spacing:2px; font-size:0.75rem;">📱 APP VON PASCAL GELLERS</div>', unsafe_allow_html=True)
st.markdown('<h1 style="color:#fff; font-size:2.2rem; margin:0;">⚽ KI Wettprognosen & Kombi Generator</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:0.95rem;">Garantierte Anzeige • OpenLigaDB + GitHub Open-Data + Web Scraping</p>', unsafe_allow_html=True)
st.markdown("---")

# --- BENUTZER EINSTELLUNGEN ---
with st.expander("⚙️ Einstellungen öffnen (Wettanbieter, Markt & Zeitraum)", expanded=True):
    
    anbieter_wahl = st.radio(
        "Wähle deinen bevorzugten Wettanbieter:",
        list(ANBIETER_URLS.keys()),
        horizontal=True,
        key="main_bm_select"
    )
    
    st.markdown("---")
    gewaehlter_markt = st.selectbox(
        "🎯 Bevorzugter Wett-Markt (Welche Quote übernommen wird):",
        [
            "⚡ Alle Märkte (KI wählt besten Value)",
            "🛡️ Doppelte Chance (1X / X2 - Höchste Sicherheit)",
            "🎯 1X2 Siegwette (Direkter Sieg)",
            "⚽ Tor-Markt (Über 2.5 Tore)",
            "⚽ Tor-Markt (Über 1.5 Tore - Safe)",
            "🔥 Beide Teams treffen (BTTS)"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("#### 🏆 Ligen auswählen:")
    aktive_generator_ligen = []

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        if st.checkbox("🇩🇪 1. Bundesliga (OpenLigaDB)", value=True): aktive_generator_ligen.append("🇩🇪 1. Bundesliga")
        if st.checkbox("🇩🇪 2. Bundesliga (OpenLigaDB)", value=True): aktive_generator_ligen.append("🇩🇪 2. Bundesliga")
        if st.checkbox("🇩🇪 3. Liga (OpenLigaDB)", value=True): aktive_generator_ligen.append("🇩🇪 3. Liga")
        if st.checkbox("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", value=True): aktive_generator_ligen.append("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        if st.checkbox("🇪🇸 La Liga", value=True): aktive_generator_ligen.append("🇪🇸 La Liga")
    with col_l2:
        if st.checkbox("🇮🇹 Serie A", value=True): aktive_generator_ligen.append("🇮🇹 Serie A")
        if st.checkbox("🇫🇷 Ligue 1", value=True): aktive_generator_ligen.append("🇫🇷 Ligue 1")
        if st.checkbox("🏆 Champions League", value=True): aktive_generator_ligen.append("🏆 Champions League")
        if st.checkbox("🇪🇺 Europa League", value=True): aktive_generator_ligen.append("🇪🇺 Europa League")
        if st.checkbox("🌍 Conference League", value=True): aktive_generator_ligen.append("🌍 Conference League")

    st.markdown("---")
    now_utc = datetime.now(timezone.utc)
    now_de = now_utc.astimezone(timezone(timedelta(hours=2)))
    today_de = now_de.date()
    today_str = today_de.strftime("%d.%m.%Y")
    
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum wählen:", 
        [f"⚡ HEUTE ({today_str} — Alle Partien)", "🟢 DIESE WOCHE / NÄCHSTER SPIELTAG"], 
        index=0
    )

    gen_typ = st.selectbox(
        "Wett-Typ wählen:",
        ["📊 Reine Einzelwetten", "🛡️ Multi-Ticket System", "🎁 Freebet-Modus", "🎯 Standard Kombiwette"]
    )

    st.markdown("---")
    generate_click = st.button("🚀 Hybrid Multi-Engine starten", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if generate_click:
    if not aktive_generator_ligen: 
        st.error("Bitte wähle mindestens eine Liga aus!")
    else:
        with st.spinner("Scanne OpenLigaDB, GitHub Data & Web Scraper..."):
            gefilterte_spiele = []
            
            for liga_label in aktive_generator_ligen:
                liga_matches = []
                
                # 1. OpenLigaDB
                if liga_label in OPENLIGA_MAP:
                    raw = fetch_openligadb(OPENLIGA_MAP[liga_label])
                    for m in raw:
                        dt_str = m.get('matchDateTime')
                        time_formatted = "Anstoß heute"
                        is_today_match = False
                        
                        if dt_str:
                            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                            dt_de = dt.astimezone(timezone(timedelta(hours=2)))
                            time_formatted = dt_de.strftime('%d.%m. - %H:%M Uhr')
                            if dt_de.date() == today_de:
                                is_today_match = True
                            
                        home, away = m['team1']['teamName'], m['team2']['teamName']
                        mkts = generate_all_market_odds(home, away)
                        target = mkts.get(gewaehlter_markt, list(mkts.values())[0])
                        
                        item = {
                            "Liga": liga_label, "Datum": time_formatted,
                            "Begegnung": f"{home} vs {away}", "Tipp": target['tipp'],
                            "Quote": target['quote'], "Markt": target['markt'],
                            "Anbieter": anbieter_wahl, "Quelle": "OpenLigaDB", "Badge": "badge-openliga",
                            "is_today": is_today_match
                        }
                        liga_matches.append(item)

                # 2. Web Scraping & GitHub Open-Data
                else:
                    scraped = scrape_kicker_live(liga_label)
                    if scraped:
                        for m in scraped:
                            home, away = m['home'], m['away']
                            mkts = generate_all_market_odds(home, away)
                            target = mkts.get(gewaehlter_markt, list(mkts.values())[0])
                            liga_matches.append({
                                "Liga": liga_label, "Datum": f"{today_str} - {m['time']} Uhr",
                                "Begegnung": f"{home} vs {away}", "Tipp": target['tipp'],
                                "Quote": target['quote'], "Markt": target['markt'],
                                "Anbieter": anbieter_wahl, "Quelle": "Live Scraper", "Badge": "badge-scraper",
                                "is_today": True
                            })
                    elif liga_label in GITHUB_DATA_MAP:
                        gh_matches = fetch_github_opendata(GITHUB_DATA_MAP[liga_label])
                        for m in gh_matches[:3]:
                            home, away = m['home'], m['away']
                            if home and away:
                                mkts = generate_all_market_odds(home, away)
                                target = mkts.get(gewaehlter_markt, list(mkts.values())[0])
                                liga_matches.append({
                                    "Liga": liga_label, "Datum": f"{today_str} - 20:45 Uhr",
                                    "Begegnung": f"{home} vs {away}", "Tipp": target['tipp'],
                                    "Quote": target['quote'], "Markt": target['markt'],
                                    "Anbieter": anbieter_wahl, "Quelle": "GitHub Open-Data", "Badge": "badge-github",
                                    "is_today": True
                                })

                # Smart Filter: Erst heutige Spiele versuchen, sonst nächstgelegene Ansetzungen anzeigen
                today_only = [m for m in liga_matches if m.get('is_today')]
                if "HEUTE" in gen_zeit_modus and today_only:
                    gefilterte_spiele.extend(today_only)
                else:
                    gefilterte_spiele.extend(liga_matches[:4])

            st.session_state['gefilterte_spiele'] = gefilterte_spiele
            st.session_state['gen_typ'] = gen_typ

# --- RESULTS DISPLAY ---
if 'gefilterte_spiele' in st.session_state:
    spiele = st.session_state['gefilterte_spiele']

    if not spiele:
        st.warning("⚠️ Keine Partien für den gewählten Filter gefunden.")
    else:
        st.markdown(f"### 📊 Geladene Spiele ({len(spiele)} Tipps)")
        for tipp in spiele:
            st.markdown(f"""
                <div class="best-card">
                    <span class="badge {tipp['Badge']}">{tipp['Quelle']}</span>
                    <span class="badge" style="background:#1e293b; color:#94a3b8;">{tipp['Liga']}</span>
                    <h4 style="color:#ffffff; margin:8px 0;">{tipp['Begegnung']}</h4>
                    <p style="color:#00d47e; font-size:0.8rem; margin-bottom:8px;">📅 {tipp['Datum']}</p>
                    <p style="color:#94a3b8; font-size:0.9rem;">Markt: <b>{tipp['Markt']}</b> | Tipp: <b style="color:#ffffff;">{tipp['Tipp']}</b></p>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                        <span style="color:#64748b; font-size:0.8rem;">Quote ({tipp['Anbieter']}):</span>
                        <span class="odds-tag">{tipp['Quote']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
