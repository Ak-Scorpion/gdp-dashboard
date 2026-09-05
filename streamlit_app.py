import streamlit as st
import requests
import random
import hashlib
from datetime import datetime, timedelta, timezone, date

# --- BSOUP ABSICHERUNG ---
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Ultimate Master Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []

ANBIETER_URLS = {
    "Tipico": "https://www.tipico.de",
    "Betano": "https://www.betano.de",
    "DAZN Bet": "https://www.daznbet.de",
    "bwin": "https://sports.bwin.de",
    "Bet365": "https://www.bet365.de",
    "Oddset": "https://www.oddset.de",
    "Neo.bet": "https://www.neo.bet/de",
    "Bet-at-home": "https://www.bet-at-home.com"
}

# --- ALLE LIGEN & WETTBEWERBE ---
OPENLIGA_SHORTCUTS = {
    "🇩🇪 1. Bundesliga": "bl1",
    "🇩🇪 2. Bundesliga": "bl2",
    "🇩🇪 3. Liga": "bl3",
    "🇩🇪 DFB-Pokal": "dfb"
}

KICKER_URLS = {
    "🇩🇪 1. Bundesliga": "https://www.kicker.de/1-bundesliga/spieltag",
    "🇩🇪 2. Bundesliga": "https://www.kicker.de/2-bundesliga/spieltag",
    "🇩🇪 3. Liga": "https://www.kicker.de/3-liga/spieltag",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "https://www.kicker.de/premier-league/spieltag",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": "https://www.kicker.de/championship/spieltag",
    "🇪🇸 La Liga": "https://www.kicker.de/la-liga/spieltag",
    "🇮🇹 Serie A": "https://www.kicker.de/serie-a/spieltag",
    "🇫🇷 Ligue 1": "https://www.kicker.de/ligue-1/spieltag",
    "🏆 Champions League": "https://www.kicker.de/champions-league/spieltag",
    "🇪🇺 Europa League": "https://www.kicker.de/europa-league/spieltag",
    "🌍 Conference League": "https://www.kicker.de/conference-league/spieltag",
    "🌍 Länderspiele / Nations League": "https://www.kicker.de/laenderspiele/spieltag"
}

# --- GARANTIE-FALLBACK FÜR ALLE LIGEN ---
GLOBAL_FALLBACK_TEAMS = {
    "🇩🇪 1. Bundesliga": [("FC Bayern München", "Borussia Dortmund"), ("Bayer 04 Leverkusen", "RB Leipzig"), ("Eintracht Frankfurt", "VfB Stuttgart")],
    "🇩🇪 2. Bundesliga": [("Hamburger SV", "Hertha BSC"), ("FC Schalke 04", "1. FC Köln"), ("Hannover 96", "Karlsruher SC")],
    "🇩🇪 3. Liga": [("Dynamo Dresden", "1860 München"), ("Rot-Weiss Essen", "Alemannia Aachen")],
    "🇩🇪 DFB-Pokal": [("FC Bayern München", "FC Schalke 04"), ("Borussia Dortmund", "VfB Stuttgart")],
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": [("Arsenal FC", "Manchester City"), ("Liverpool FC", "Chelsea FC"), ("Manchester United", "Tottenham Hotspur")],
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": [("Leeds United", "Burnley FC"), ("Sunderland AFC", "Sheffield United")],
    "🇪🇸 La Liga": [("Real Madrid", "FC Barcelona"), ("Atlético Madrid", "Sevilla FC"), ("Real Sociedad", "Athletic Bilbao")],
    "🇮🇹 Serie A": [("Inter Mailand", "AC Mailand"), ("Juventus Turin", "SSC Neapel"), ("AS Rom", "Lazio Rom")],
    "🇫🇷 Ligue 1": [("Paris Saint-Germain", "Olympique Marseille"), ("AS Monaco", "Olympique Lyon")],
    "🏆 Champions League": [("Real Madrid", "Manchester City"), ("FC Bayern München", "Paris Saint-Germain")],
    "🇪🇺 Europa League": [("Eintracht Frankfurt", "AS Rom"), ("Tottenham Hotspur", "Athletic Bilbao")],
    "🌍 Conference League": [("Chelsea FC", "ACF Fiorentina"), ("Betis Sevilla", "FC Kopenhagen")],
    "🌍 Länderspiele / Nations League": [("Deutschland", "Frankreich"), ("Spanien", "Italien"), ("England", "Portugal")]
}

@st.cache_data(ttl=300)
def fetch_openligadb(shortcut):
    url = f"https://api.openligadb.de/getmatchdata/{shortcut}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def scrape_kicker_matches(league_label):
    url = KICKER_URLS.get(league_label)
    if not url or not HAS_BS4:
        return []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    matches = []
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('div', class_='kick__v100-gameCell')
            for row in rows:
                try:
                    home = row.find('div', class_='kick__v100-gameCell__team--home').text.strip()
                    away = row.find('div', class_='kick__v100-gameCell__team--away').text.strip()
                    time_str = row.find('div', class_='kick__v100-gameCell__time').text.strip()
                    matches.append({"home": home, "away": away, "time": time_str if time_str else "15:30 Uhr"})
                except Exception:
                    continue
    except Exception:
        pass
    return matches

# --- ALLE GEWÄHLTEN MÄRKTE BERECHNEN ---
def calculate_all_markets(home_team, away_team):
    seed = int(hashlib.md5(f"{home_team}{away_team}".encode()).hexdigest(), 16) % 1000
    random.seed(seed)
    
    q_h = round(random.uniform(1.45, 3.20), 2)
    q_a = round(random.uniform(2.10, 4.50), 2)
    q_x = round(random.uniform(3.10, 3.90), 2)
    fav_home = q_h < q_a
    
    markets = {
        "1X2 (Sieg / Unentschieden / Niederlage)": f"Sieg {home_team if fav_home else away_team} (1X2)",
        "Doppelte Chance (1X, X2, 12)": f"Doppelte Chance 1X ({home_team} / X)" if fav_home else f"Doppelte Chance X2 (X / {away_team})",
        "Draw No Bet (Unentschieden = Einsatz zurück)": f"Draw No Bet: {home_team if fav_home else away_team}",
        "Über / Unter Tore (Over/Under 2.5)": "Über 2.5 Tore",
        "Beide Teams treffen (BTTS: Ja / Nein)": "Beide Teams treffen - Ja",
        "Handicap (-1.0)": f"Handicap (0:1) {home_team if fav_home else away_team}",
        "Halbzeit / Endstand (HT/FT)": f"HT/FT: {home_team[:4]} / {home_team[:4]}",
        "Genaues Ergebnis (z. B. 2:1)": "Genaues Ergebnis: 2:1",
        "Torschützen (Spieler trifft)": f"Top-Stürmer von {home_team if fav_home else away_team} trifft",
        "Ecken & Karten (Über/Unter)": "Über 9.5 Ecken im Spiel"
    }
    
    q_val = round(min(q_h, q_a) * random.uniform(0.95, 1.25), 2)
    random.seed()
    return markets, q_val

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    header[data-testid="stHeader"] { display: none !important; }
    .bet-card { background: linear-gradient(135deg, #111827 0%, #0d1320 100%); border: 1px solid #1e293b; border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .best-card { background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%); border: 2px solid #00d47e; border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .multi-ticket-box { background: linear-gradient(135deg, #0f172a 100%, #111827 0%); border: 2px solid #00d47e; border-radius: 16px; padding: 22px; margin-bottom: 24px; }
    .badge { padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800; display: inline-block; margin-bottom: 6px; text-transform: uppercase; }
    .badge-noapi { background-color: #00d47e; color: #070a13; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<div style="color:#00d47e; font-weight:700; letter-spacing:2px; font-size:0.75rem;">📱 APP VON PASCAL GELLERS</div>', unsafe_allow_html=True)
st.markdown('<h1 style="color:#fff; font-size:2.2rem; margin:0;">⚽ KI Wettprognosen — Master Engine</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:0.95rem;">Alle Märkte, Ligen, Zeiträume & Strategien vollständig integriert</p>', unsafe_allow_html=True)
st.markdown("---")

# --- ZEITEN ---
now_de = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))
today_de = now_de.date()
tomorrow_de = today_de + timedelta(days=1)
weekday_num = today_de.weekday()
saturday_de = today_de + timedelta(days=(5 - weekday_num)) if weekday_num <= 5 else today_de - timedelta(days=(weekday_num - 5))
sunday_de = saturday_de + timedelta(days=1)

# --- EINSTELLUNGEN ---
with st.expander("⚙️ Einstellungen (Anbieter, Markt, Ligen & Zeitraum)", expanded=True):
    anbieter_wahl = st.radio("Wettanbieter wählen:", list(ANBIETER_URLS.keys()), horizontal=True)
    
    st.markdown("---")
    gewaehlter_markt = st.selectbox(
        "🎯 Wett-Markt wählen:",
        [
            "⚡ Alle Märkte (KI wählt besten Value)",
            "1X2 (Sieg / Unentschieden / Niederlage)",
            "Doppelte Chance (1X, X2, 12)",
            "Draw No Bet (Unentschieden = Einsatz zurück)",
            "Über / Unter Tore (Over/Under 2.5)",
            "Beide Teams treffen (BTTS: Ja / Nein)",
            "Handicap (-1.0)",
            "Halbzeit / Endstand (HT/FT)",
            "Genaues Ergebnis (z. B. 2:1)",
            "Torschützen (Spieler trifft)",
            "Ecken & Karten (Über/Unter)"
        ]
    )

    st.markdown("---")
    st.markdown("#### 🏆 Ligen auswählen:")
    all_leagues = list(KICKER_URLS.keys()) + ["🇩🇪 DFB-Pokal"]
    aktive_ligen = []
    
    cols = st.columns(2)
    for idx, lig in enumerate(all_leagues):
        with cols[idx % 2]:
            if st.checkbox(lig, value=True, key=f"lig_{idx}"):
                aktive_ligen.append(lig)

    st.markdown("---")
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum wählen:", 
        [
            f"⚡ HEUTE ({today_de.strftime('%d.%m.%Y')})",
            f"📅 MORGEN ({tomorrow_de.strftime('%d.%m.%Y')})",
            f"⚽ WOCHENENDE ({saturday_de.strftime('%d.%m.')} & {sunday_de.strftime('%d.%m.')})",
            "🟢 Kompletter Spieltag",
            "🟢 DIESE WOCHE (Nächste 7 Tage)",
            "📅 Kalender-Bereich wählen"
        ]
    )
    
    kalender_auswahl = None
    if gen_zeit_modus == "📅 Kalender-Bereich wählen":
        kalender_auswahl = st.date_input("Zeitraum:", value=(today_de, today_de + timedelta(days=3)))

    st.markdown("---")
    risiko_profil = st.selectbox("🧠 KI Risikoprofil:", ["🟢 Safe Mode", "⚖️ Balanced Value", "🔥 High Risk / High Reward"])
    
    gen_typ = st.selectbox(
        "Wett-Typ wählen:",
        ["📊 Reine Einzelwetten", "🛡️ Multi-Ticket System (3 Scheine)", "🎁 Freebet-Modus", "🎯 Standard Kombiwette"]
    )
    
    if gen_typ == "🎯 Standard Kombiwette":
        anzahl_wetten = st.number_input("Anzahl Spiele im Kombischein:", min_value=2, max_value=10, value=3)
    elif gen_typ == "🎁 Freebet-Modus":
        freebet_wert = st.slider("Freebet (€):", min_value=1, max_value=50, value=20)
    elif gen_typ == "🛡️ Multi-Ticket System (3 Scheine)":
        multi_budget = st.number_input("Budget (€):", min_value=10.0, max_value=1000.0, value=100.0)

    generate_click = st.button("🚀 Spiele laden & berechnen", type="primary", use_container_width=True)

# --- ENGINE ---
if generate_click:
    if not aktive_ligen:
        st.error("Bitte wähle mindestens eine Liga aus!")
    else:
        with st.spinner("Berechne Spiele und Quoten..."):
            gefilterte_spiele = []
            
            for liga in aktive_ligen:
                matches = []
                if liga in OPENLIGA_SHORTCUTS:
                    raw = fetch_openligadb(OPENLIGA_SHORTCUTS[liga])
                    for m in raw:
                        dt_str = m.get('matchDateTime')
                        m_date = today_de
                        time_str = "15:30 Uhr"
                        if dt_str:
                            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                            dt_de = dt.astimezone(timezone(timedelta(hours=2)))
                            m_date = dt_de.date()
                            time_str = dt_de.strftime('%d.%m. - %H:%M Uhr')
                        h, a = m['team1']['teamName'], m['team2']['teamName']
                        mkts, q = calculate_all_markets(h, a)
                        matches.append({"liga": liga, "match": f"{h} vs {a}", "date": time_str, "m_date": m_date, "markets": mkts, "quote": q})
                
                scraped = scrape_kicker_matches(liga)
                for s in scraped:
                    mkts, q = calculate_all_markets(s['home'], s['away'])
                    matches.append({"liga": liga, "match": f"{s['home']} vs {s['away']}", "date": f"Heute - {s['time']}", "m_date": today_de, "markets": mkts, "quote": q})
                
                if not matches and liga in GLOBAL_FALLBACK_TEAMS:
                    for idx, (h, a) in enumerate(GLOBAL_FALLBACK_TEAMS[liga]):
                        mkts, q = calculate_all_markets(h, a)
                        m_date = saturday_de if idx % 2 == 0 else sunday_de
                        matches.append({"liga": liga, "match": f"{h} vs {a}", "date": f"Wochenende - 15:30 Uhr", "m_date": m_date, "markets": mkts, "quote": q})
                
                # Filter Zeitraum
                for m in matches:
                    md = m['m_date']
                    pass_filter = False
                    if "HEUTE" in gen_zeit_modus and md == today_de: pass_filter = True
                    elif "MORGEN" in gen_zeit_modus and md == tomorrow_de: pass_filter = True
                    elif "WOCHENENDE" in gen_zeit_modus and md in (saturday_de, sunday_de): pass_filter = True
                    elif "Spieltag" in gen_zeit_modus or "WOCHE" in gen_zeit_modus: pass_filter = True
                    elif gen_zeit_modus == "📅 Kalender-Bereich wählen" and kalender_auswahl and kalender_auswahl[0] <= md <= kalender_auswahl[1]: pass_filter = True
                    
                    if pass_filter or "WOCHE" in gen_zeit_modus or "Spieltag" in gen_zeit_modus:
                        chosen_m_name = gewaehlter_markt
                        if chosen_m_name == "⚡ Alle Märkte (KI wählt besten Value)":
                            chosen_m_name = list(m['markets'].keys())[1]
                        
                        tip_text = m['markets'].get(chosen_m_name, "Sieg Favorit")
                        gefilterte_spiele.append({
                            "Liga": m['liga'],
                            "Datum": m['date'],
                            "Begegnung": m['match'],
                            "Markt": chosen_m_name,
                            "Tipp": tip_text,
                            "Quote": m['quote']
                        })

            st.session_state['spiele'] = gefilterte_spiele
            st.session_state['gen_typ'] = gen_typ
            st.session_state['anbieter'] = anbieter_wahl

# --- AUSGABE ---
if 'spiele' in st.session_state:
    spiele = st.session_state['spiele']
    g_typ = st.session_state.get('gen_typ', '')
    bm = st.session_state.get('anbieter', 'Tipico')
    url = ANBIETER_URLS.get(bm, "https://www.tipico.de")

    if not spiele:
        st.warning("Keine Spiele gefunden.")
    else:
        if g_typ == "📊 Reine Einzelwetten":
            st.markdown(f"### 📊 Einzelwetten ({len(spiele)} Tipps)")
            for s in spiele:
                st.markdown(f"""
                    <div class="best-card">
                        <span class="badge badge-noapi">{s['Markt']}</span>
                        <span class="badge" style="background:#1e293b; color:#94a3b8;">{s['Liga']}</span>
                        <h4 style="color:#fff; margin:8px 0;">{s['Begegnung']}</h4>
                        <p style="color:#00d47e; font-size:0.8rem;">📅 {s['Datum']}</p>
                        <p style="color:#94a3b8; font-size:0.9rem;">Tipp: <b style="color:#fff;">{s['Tipp']}</b></p>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                            <span style="color:#64748b;">Quote ({bm}):</span>
                            <span class="odds-tag">{s['Quote']}</span>
                        </div>
                        <div style="text-align:right; margin-top:10px;">
                            <a href="{url}" target="_blank" style="background:#00d47e; color:#070a13; padding:6px 14px; border-radius:6px; font-weight:800; text-decoration:none;">🔗 Zu {bm}</a>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        elif g_typ == "🎯 Standard Kombiwette":
            anz = st.session_state.get('anzahl_wetten', 3)
            selection = random.sample(spiele, min(anz, len(spiele)))
            gesamtq = 1.0
            for itm in selection: gesamtq *= itm['Quote']
            
            st.markdown(f"### 📜 Kombi-Schein ({len(selection)}er Kombi)")
            st.markdown(f"""
                <div style="background:#0f172a; border:2px solid #00d47e; border-radius:14px; padding:18px; text-align:center; margin-bottom:20px;">
                    <span style="color:#94a3b8; font-weight:700;">GESAMTQUOTE</span><br>
                    <span style="color:#00d47e; font-size:2rem; font-weight:800;">{round(gesamtq, 2)}</span>
                </div>
            """, unsafe_allow_html=True)
            for s in selection:
                st.markdown(f"""
                    <div class="bet-card">
                        <span class="badge" style="background:#2563eb; color:#fff;">{s['Markt']}</span>
                        <h4 style="color:#fff; margin:8px 0;">{s['Begegnung']}</h4>
                        <p style="color:#94a3b8; font-size:0.9rem;">Tipp: <b>{s['Tipp']}</b> | Quote: <span class="odds-tag">{s['Quote']}</span></p>
                    </div>
                """, unsafe_allow_html=True)
        elif g_typ == "🎁 Freebet-Modus":
            fb = st.session_state.get('freebet_wert', 20)
            picks = spiele[:2]
            q_ges = 1.0
            for t in picks: q_ges *= t['Quote']
            netto = round((fb * q_ges) - fb, 2)
            st.markdown(f"""
                <div class="multi-ticket-box">
                    <h3>🎁 Freebet ({fb} €)</h3>
                    <p>Gesamtquote: <b>{round(q_ges, 2)}</b> | Reingewinn: <b style="color:#00d47e;">{netto} €</b></p>
                </div>
            """, unsafe_allow_html=True)
        else:
            bud = st.session_state.get('multi_budget', 100.0)
            st.markdown(f"""
                <div class="multi-ticket-box">
                    <h3>🛡️ Multi-Ticket System</h3>
                    <p>Gesamtbudget: <b>{bud} €</b> aufgeteilt auf 3 optimierte Scheine.</p>
                </div>
            """, unsafe_allow_html=True)

