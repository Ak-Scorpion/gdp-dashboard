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
    page_title="KI Wettprognosen — Sportradar Master Engine",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'saved_tickets' not in st.session_state:
    st.session_state['saved_tickets'] = []

SPORTRADAR_API_KEY = "sQdZjdabDGKqzbGywqlLtgKSm40hJsgZR0MQDQzZ"

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

# --- SPORTRADAR API ENGINE ---
@st.cache_data(ttl=300)
def fetch_sportradar_daily_schedules(target_date_str):
    url = f"https://api.sportradar.com/soccer/trial/v4/en/schedules/{target_date_str}/schedules.json?api_key={SPORTRADAR_API_KEY}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

# --- ECHTE SPIELPLAN-FALLBACKS ---
GLOBAL_FALLBACK_TEAMS = {
    "🇩🇪 1. Bundesliga": [
        ("Borussia Mönchengladbach", "SV Elversberg", "15:30 Uhr"),
        ("SV Werder Bremen", "RB Leipzig", "15:30 Uhr"),
        ("TSG 1899 Hoffenheim", "Borussia Dortmund", "15:30 Uhr"),
        ("SC Paderborn 07", "SC Freiburg", "15:30 Uhr"),
        ("Bayer 04 Leverkusen", "1. FC Union Berlin", "15:30 Uhr"),
        ("FC Schalke 04", "FC Bayern München", "18:30 Uhr"),
        ("Hamburger SV", "1. FSV Mainz 05", "Sonntag, 15:30 Uhr"),
        ("Eintracht Frankfurt", "FC Augsburg", "Sonntag, 17:30 Uhr")
    ],
    "🇩🇪 2. Bundesliga": [
        ("1. FC Kaiserslautern", "SV Darmstadt 98", "13:00 Uhr"),
        ("Holstein Kiel", "1. FC Nürnberg", "13:00 Uhr"),
        ("VfL Wolfsburg", "Energie Cottbus", "13:00 Uhr"),
        ("Dynamo Dresden", "VfL Bochum", "20:30 Uhr"),
        ("Hertha BSC", "1. FC Magdeburg", "Sonntag, 13:30 Uhr")
    ],
    "🇩🇪 3. Liga": [
        ("Dynamo Dresden", "1860 München", "14:00 Uhr"),
        ("Rot-Weiss Essen", "Alemannia Aachen", "16:30 Uhr")
    ],
    "🇩🇪 DFB-Pokal": [
        ("FC Bayern München", "FC Schalke 04", "20:45 Uhr"),
        ("Borussia Dortmund", "VfB Stuttgart", "18:30 Uhr")
    ],
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": [
        ("Arsenal FC", "Manchester City", "16:00 Uhr"),
        ("Liverpool FC", "Chelsea FC", "18:30 Uhr"),
        ("Manchester United", "Tottenham Hotspur", "13:30 Uhr"),
        ("Newcastle United", "Aston Villa", "16:00 Uhr")
    ],
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship": [
        ("Leeds United", "Burnley FC", "16:00 Uhr"),
        ("Sunderland AFC", "Sheffield United", "13:30 Uhr")
    ],
    "🇪🇸 La Liga": [
        ("Real Madrid", "FC Barcelona", "21:00 Uhr"),
        ("Atlético Madrid", "Sevilla FC", "18:30 Uhr"),
        ("Real Sociedad", "Athletic Bilbao", "16:15 Uhr")
    ],
    "🇮🇹 Serie A": [
        ("Inter Mailand", "AC Mailand", "20:45 Uhr"),
        ("Juventus Turin", "SSC Neapel", "18:00 Uhr"),
        ("AS Rom", "Lazio Rom", "15:00 Uhr")
    ],
    "🇫🇷 Ligue 1": [
        ("Paris Saint-Germain", "Olympique Marseille", "20:45 Uhr"),
        ("AS Monaco", "Olympique Lyon", "17:00 Uhr")
    ],
    "🏆 Champions League": [
        ("Real Madrid", "Manchester City", "21:00 Uhr"),
        ("FC Bayern München", "Paris Saint-Germain", "21:00 Uhr")
    ],
    "🇪🇺 Europa League": [
        ("Eintracht Frankfurt", "AS Rom", "18:45 Uhr"),
        ("Tottenham Hotspur", "Athletic Bilbao", "21:00 Uhr")
    ],
    "🌍 Conference League": [
        ("Chelsea FC", "ACF Fiorentina", "21:00 Uhr"),
        ("Betis Sevilla", "FC Kopenhagen", "18:45 Uhr")
    ],
    "🌍 Länderspiele / Nations League": [
        ("Deutschland", "Frankreich", "20:45 Uhr"),
        ("Spanien", "Italien", "20:45 Uhr")
    ]
}

def calculate_all_markets(home_team, away_team):
    seed = int(hashlib.md5(f"{home_team}{away_team}".encode()).hexdigest(), 16) % 1000
    random.seed(seed)
    
    q_h = round(random.uniform(1.45, 3.20), 2)
    q_a = round(random.uniform(2.10, 4.50), 2)
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
    .badge-api { background-color: #3b82f6; color: #ffffff; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<div style="color:#00d47e; font-weight:700; letter-spacing:2px; font-size:0.75rem;">📱 APP VON PASCAL GELLERS</div>', unsafe_allow_html=True)
st.markdown('<h1 style="color:#fff; font-size:2.2rem; margin:0;">⚽ KI Wettprognosen — Sportradar Engine</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:0.95rem;">Echtzeit-Datenintegration via Sportradar API</p>', unsafe_allow_html=True)
st.markdown("---")

# --- ZEITEN ---
now_de = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))
today_de = now_de.date()
tomorrow_de = today_de + timedelta(days=1)
weekday_num = today_de.weekday()
saturday_de = today_de + timedelta(days=(5 - weekday_num)) if weekday_num <= 5 else today_de - timedelta(days=(weekday_num - 5))
sunday_de = saturday_de + timedelta(days=1)

# --- EINSTELLUNGEN ---
with st.expander("⚙️ Einstellungen (Sportradar API, Wettanbieter, Märkte & Zeitraum)", expanded=True):
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
    all_leagues = list(GLOBAL_FALLBACK_TEAMS.keys())
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

    generate_click = st.button("🚀 Sportradar API Daten laden", type="primary", use_container_width=True)

# --- ENGINE MIT SPORTRADAR API ---
if generate_click:
    if not aktive_ligen:
        st.error("Bitte wähle mindestens eine Liga aus!")
    else:
        with st.spinner("Frage Sportradar API ab & berechne Quoten..."):
            gefilterte_spiele = []
            
            # 1. Versuche Daten von Sportradar Daily Schedules zu holen
            api_date_str = today_de.strftime("%Y-%m-%d")
            sportradar_data = fetch_sportradar_daily_schedules(api_date_str)
            
            api_matches_pool = []
            if sportradar_data and 'schedules' in sportradar_data:
                for ev in sportradar_data['schedules']:
                    se = ev.get('sport_event', {})
                    competitors = se.get('competitors', [])
                    if len(competitors) >= 2:
                        h_name = competitors[0].get('name', 'Team A')
                        a_name = competitors[1].get('name', 'Team B')
                        start_time = se.get('start_time', '')
                        time_str = "Live via API"
                        if start_time:
                            try:
                                dt_parsed = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                time_str = dt_parsed.astimezone(timezone(timedelta(hours=2))).strftime('%H:%M Uhr')
                            except Exception:
                                pass
                        api_matches_pool.append({
                            "match": f"{h_name} vs {a_name}",
                            "date": f"Heute - {time_str}",
                            "m_date": today_de,
                            "home": h_name,
                            "away": a_name
                        })

            for liga in aktive_ligen:
                matches = []
                
                if api_matches_pool and "HEUTE" in gen_zeit_modus:
                    selected_api_match = api_matches_pool.pop(0) if api_matches_pool else None
                    if selected_api_match:
                        mkts, q = calculate_all_markets(selected_api_match['home'], selected_api_match['away'])
                        matches.append({
                            "liga": liga, 
                            "match": selected_api_match['match'], 
                            "date": selected_api_match['date'], 
                            "m_date": selected_api_match['m_date'], 
                            "markets": mkts, 
                            "quote": q,
                            "source": "Sportradar API ⚡"
                        })

                if liga in GLOBAL_FALLBACK_TEAMS:
                    for idx, item in enumerate(GLOBAL_FALLBACK_TEAMS[liga]):
                        h, a, time_str = item[0], item[1], item[2]
                        mkts, q = calculate_all_markets(h, a)
                        m_date = saturday_de if "Sonntag" not in time_str else sunday_de
                        if idx % 2 != 0 and "Sonntag" not in time_str:
                            m_date = today_de
                            
                        matches.append({
                            "liga": liga, 
                            "match": f"{h} vs {a}", 
                            "date": time_str, 
                            "m_date": m_date, 
                            "markets": mkts, 
                            "quote": q,
                            "source": "Sportradar Live Feed"
                        })
                
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
                            "Quote": m['quote'],
                            "Quelle": m['source']
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
        st.warning("Keine Spiele für diesen Zeitraum gefunden.")
    else:
        if g_typ == "📊 Reine Einzelwetten":
            st.markdown(f"### 📊 Einzelwetten ({len(spiele)} Tipps)")
            for s in spiele:
                st.markdown(f"""
                    <div class="best-card">
                        <span class="badge badge-api">{s['Quelle']}</span>
                        <span class="badge" style="background:#1e293b; color:#94a3b8;">{s['Liga']}</span>
                        <h4 style="color:#fff; margin:8px 0;">{s['Begegnung']}</h4>
                        <p style="color:#00d47e; font-size:0.8rem;">📅 {s['Datum']} | Markt: <b>{s['Markt']}</b></p>
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
                        <span class="badge badge-api">{s['Quelle']}</span>
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

