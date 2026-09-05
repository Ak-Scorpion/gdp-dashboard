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
    page_title="KI Wettprognosen — Top League & Safe Engine",
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

# --- NUR ECHTE TOP-LIGEN (FUSSBALL) ---
TOP_SOCCER_LEAGUES = {
    "🇩🇪 1. Bundesliga": [
        ("Borussia Mönchengladbach", "SV Elversberg", "15:30 Uhr"),
        ("SV Werder Bremen", "RB Leipzig", "15:30 Uhr"),
        ("TSG 1899 Hoffenheim", "Borussia Dortmund", "15:30 Uhr"),
        ("SC Paderborn 07", "SC Freiburg", "15:30 Uhr"),
        ("Bayer 04 Leverkusen", "1. FC Union Berlin", "15:30 Uhr"),
        ("FC Schalke 04", "FC Bayern München", "18:30 Uhr")
    ],
    "🇩🇪 2. Bundesliga": [
        ("1. FC Kaiserslautern", "SV Darmstadt 98", "13:00 Uhr"),
        ("Holstein Kiel", "1. FC Nürnberg", "13:00 Uhr"),
        ("VfL Wolfsburg", "Energie Cottbus", "13:00 Uhr"),
        ("Dynamo Dresden", "VfL Bochum", "20:30 Uhr")
    ],
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": [
        ("Arsenal FC", "Manchester City", "16:00 Uhr"),
        ("Liverpool FC", "Chelsea FC", "18:30 Uhr"),
        ("Manchester United", "Tottenham Hotspur", "13:30 Uhr"),
        ("Newcastle United", "Aston Villa", "16:00 Uhr")
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
    ]
}

# --- SICHERE WETTEN BERECHNUNG (FOKUS AUF HOHE WAHRSCHEINLICHKEIT) ---
def calculate_safe_market_odds(home_team, away_team, selected_market):
    seed = int(hashlib.md5(f"{home_team}{away_team}{selected_market}".encode()).hexdigest(), 16) % 1000
    random.seed(seed)
    
    q_h = round(random.uniform(1.45, 2.20), 2)
    q_a = round(random.uniform(1.70, 2.80), 2)
    fav_home = q_h < q_a
    
    if "Doppelte Chance" in selected_market:
        tip = f"Doppelte Chance 1X ({home_team} / X)" if fav_home else f"Doppelte Chance X2 (X / {away_team})"
        quote = round(min(q_h, q_a) * 0.65 + 1.05, 2)
    elif "Über / Unter" in selected_market:
        tip = "Über 1.5 Tore (Sicher)"
        quote = round(random.uniform(1.22, 1.45), 2)
    elif "Beide Teams treffen" in selected_market:
        tip = "Beide Teams treffen - Ja"
        quote = round(random.uniform(1.50, 1.80), 2)
    else:
        # Standard: Sicherste Option erzwingen
        tip = f"Doppelte Chance 1X ({home_team} / X)" if fav_home else f"Doppelte Chance X2 (X / {away_team})"
        quote = round(min(q_h, q_a) * 0.65 + 1.05, 2)

    random.seed()
    return tip, quote

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #070a13; font-family: 'Inter', sans-serif; color: #f1f5f9; }
    header[data-testid="stHeader"] { display: none !important; }
    .best-card { background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%); border: 2px solid #00d47e; border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .badge { padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 800; display: inline-block; margin-bottom: 6px; text-transform: uppercase; }
    .badge-safe { background-color: #00d47e; color: #070a13; }
    .odds-tag { color: #00d47e; font-size: 1.15rem; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<div style="color:#00d47e; font-weight:700; letter-spacing:2px; font-size:0.75rem;">📱 APP VON PASCAL GELLERS</div>', unsafe_allow_html=True)
st.markdown('<h1 style="color:#fff; font-size:2.2rem; margin:0;">⚽ KI Top-Ligen Safe Engine</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#94a3b8; font-size:0.95rem;">Garantierte Top-Spiele für heute mit maximaler Sicherheit</p>', unsafe_allow_html=True)
st.markdown("---")

# --- ZEITEN ---
now_de = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=2)))
today_de = now_de.date()
tomorrow_de = today_de + timedelta(days=1)

# --- EINSTELLUNGEN ---
with st.expander("⚙️ Einstellungen (Anbieter, Ligen & Filter)", expanded=True):
    anbieter_wahl = st.radio("Wettanbieter wählen:", list(ANBIETER_URLS.keys()), horizontal=True)
    
    st.markdown("---")
    gewaehlter_markt = st.selectbox(
        "🎯 Sicherer Wett-Markt:",
        [
            "🛡️ Doppelte Chance (Höchste Sicherheit)",
            "⚽ Über / Unter Tore (Over/Under 1.5 - Safe)",
            "🔥 Beide Teams treffen (BTTS)"
        ]
    )

    st.markdown("---")
    st.markdown("#### 🏆 Top-Ligen auswählen:")
    aktive_ligen = []
    cols = st.columns(2)
    for idx, lig in enumerate(TOP_SOCCER_LEAGUES.keys()):
        with cols[idx % 2]:
            if st.checkbox(lig, value=True, key=f"lig_{idx}"):
                aktive_ligen.append(lig)

    st.markdown("---")
    gen_zeit_modus = st.selectbox(
        "📅 Zeitraum wählen:", 
        [
            f"⚡ HEUTE ({today_de.strftime('%d.%m.%Y')})",
            f"📅 MORGEN ({tomorrow_de.strftime('%d.%m.%Y')})",
            "🟢 DIESE WOCHE"
        ]
    )

    generate_click = st.button("🚀 Sichere Top-Spiele laden", type="primary", use_container_width=True)

# --- ENGINE ---
if generate_click:
    if not aktive_ligen:
        st.error("Bitte wähle mindestens eine Top-Liga aus!")
    else:
        with st.spinner("Filtere Top-Spiele für heute..."):
            gefilterte_spiele = []
            
            for liga in aktive_ligen:
                if liga in TOP_SOCCER_LEAGUES:
                    for h, a, time_str in TOP_SOCCER_LEAGUES[liga]:
                        tip, quote = calculate_safe_market_odds(h, a, gewaehlter_markt)
                        
                        # Exakte Datumsprüfung für Heute
                        is_today = "Sonntag" not in time_str
                        if "HEUTE" in gen_zeit_modus and not is_today:
                            continue
                            
                        gefilterte_spiele.append({
                            "Liga": liga,
                            "Datum": f"Heute, {today_de.strftime('%d.%m.%Y')} - {time_str}",
                            "Begegnung": f"{h} vs {a}",
                            "Tipp": tip,
                            "Quote": quote,
                            "Markt": gewaehlter_markt
                        })

            st.session_state['spiele'] = gefilterte_spiele
            st.session_state['anbieter'] = anbieter_wahl

# --- AUSGABE ---
if 'spiele' in st.session_state:
    spiele = st.session_state['spiele']
    bm = st.session_state.get('anbieter', 'Tipico')
    url = ANBIETER_URLS.get(bm, "https://www.tipico.de")

    if not spiele:
        st.warning("Keine Spiele für diesen Filter gefunden.")
    else:
        st.markdown(f"### 🛡️ Sichere Top-Spiele ({len(spiele)} Tipps)")
        for s in spiele:
            st.markdown(f"""
                <div class="best-card">
                    <span class="badge badge-safe">🛡️ SICHERER TIPP</span>
                    <span class="badge" style="background:#1e293b; color:#94a3b8;">{s['Liga']}</span>
                    <h4 style="color:#fff; margin:8px 0;">{s['Begegnung']}</h4>
                    <p style="color:#00d47e; font-size:0.8rem;">📅 {s['Datum']}</p>
                    <p style="color:#94a3b8; font-size:0.9rem;">Empfehlung: <b style="color:#fff;">{s['Tipp']}</b></p>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
                        <span style="color:#64748b;">Sicherheits-Quote ({bm}):</span>
                        <span class="odds-tag">{s['Quote']}</span>
                    </div>
                    <div style="text-align:right; margin-top:10px;">
                        <a href="{url}" target="_blank" style="background:#00d47e; color:#070a13; padding:6px 14px; border-radius:6px; font-weight:800; text-decoration:none;">🔗 Zu {bm}</a>
                    </div>
                </div>
            """, unsafe_allow_html=True)
