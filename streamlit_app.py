import streamlit as st
import requests
import math
from datetime import datetime, timezone, timedelta

# Deutsche Zeitzone
try:
    from zoneinfo import ZoneInfo
    tz_de = ZoneInfo("Europe/Berlin")
except ImportError:
    tz_de = timezone(timedelta(hours=2))

st.set_page_config(page_title="Elite Value Engine", page_icon="⚽", layout="wide")

# --- DEINE NEUEN API KEYS ---
API_KEYS = [
    "f0dc02ac1e10f8e6c0e607698964b5a6",
    "1aa566d1bdb18c77b5c1210904adf5d5",
    "25d237353cf0c5920d358d1e79f9450c",
    "0339fb12fa7a92411c4fe5ca32d3755c",
    "5d317d36dab0f21697792fe154902716",
    "e36dbfffe1a22ab682e2759aea044180",
    "e66bcb054c6ace9de606da63612c8f4c",
    "796a27287d73f08d0257cc838ebb6cd9",
    "a5e0323a0a14698cdeec004e3b9b18c"
]

# --- KI TEAM-RATINGS ---
TEAM_RATINGS = {
    "bayern munich": 96, "borussia dortmund": 87, "bayer leverkusen": 91,
    "rb leipzig": 86, "stuttgart": 83, "eintracht frankfurt": 82,
    "manchester city": 95, "arsenal": 92, "liverpool": 93, "chelsea": 85,
    "real madrid": 96, "barcelona": 93, "atletico madrid": 86,
    "inter": 91, "juventus": 86, "ac milan": 86, "napoli": 86,
    "paris saint germain": 93, "monaco": 82
}
LEAGUE_BASE = 78

def get_rating(team_name):
    clean_name = team_name.lower().replace("-", " ")
    for key, rating in TEAM_RATINGS.items():
        if key in clean_name:
            return rating
    return LEAGUE_BASE

def calc_probs(home, away):
    r_h = get_rating(home) + 4 # Heimvorteil
    r_a = get_rating(away)
    
    xg_h = max(0.5, 1.45 * ((r_h / 75.0) ** 2.5 / (r_a / 75.0) ** 2.5))
    xg_a = max(0.5, 1.05 * ((r_a / 75.0) ** 2.5 / (r_h / 75.0) ** 2.5))
    
    matrix = [[(math.pow(xg_h, h) * math.exp(-xg_h) / math.factorial(h)) * 
               (math.pow(xg_a, a) * math.exp(-xg_a) / math.factorial(a)) 
               for a in range(6)] for h in range(6)]
    
    p_1 = sum(matrix[h][a] for h in range(6) for a in range(6) if h > a)
    p_x = sum(matrix[h][a] for h in range(6) for a in range(6) if h == a)
    p_2 = sum(matrix[h][a] for h in range(6) for a in range(6) if h < a)
    p_over = sum(matrix[h][a] for h in range(6) for a in range(6) if (h + a) > 2.5)
    
    return {"1": p_1, "X": p_x, "2": p_2, "Over2.5": p_over}

# --- UI STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #030712; color: #f3f4f6; }
    .elite-header { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 1px solid #312e81; border-radius: 16px; padding: 24px; margin-bottom: 24px; }
    .ev-good { color: #10b981; font-weight: bold; }
    .ev-bad { color: #ef4444; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="elite-header">
        <span style="color: #38bdf8; font-weight: 700; font-size: 0.75rem;">SCHRITT 3: VALUE ENGINE</span>
        <h1 style="color: #ffffff; font-size: 2.2rem; margin: 6px 0;">⚽ KI vs. Tipico</h1>
        <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Sucht mathematische Fehler in echten Tipico-Quoten (Expected Value)</p>
    </div>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    sport_key = st.selectbox("Wähle Liga:", [
        ("soccer_germany_bundesliga", "🇩🇪 1. Bundesliga"),
        ("soccer_epl", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League"),
        ("soccer_spain_la_liga", "🇪🇸 La Liga"),
        ("soccer_italy_serie_a", "🇮🇹 Serie A"),
        ("soccer_uefa_champs_league", "🏆 Champions League")
    ], format_func=lambda x: x[1])[0]

# --- KUGELSICHERE API LOGIK (Ohne State-Falle) ---
@st.cache_data(ttl=120, show_spinner=False)
def fetch_api_data(sport, keys_list):
    for idx, key in enumerate(keys_list):
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        params = {
            "apiKey": key, 
            "regions": "eu", 
            "markets": "h2h,totals", # Wir ziehen alle EU Buchmacher und filtern Tipico lokal, das verhindert API-Crashs!
            "oddsFormat": "decimal"
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return {"data": resp.json(), "key_idx": idx}
            elif resp.status_code in [401, 429]:
                continue # Key verbraucht, nächsten probieren
            else:
                return {"error": f"Unerwarteter API Fehler (Code {resp.status_code}): {resp.text}"}
        except Exception as e:
            return {"error": f"Verbindungsfehler: {str(e)}"}
            
    return {"error": "Alle 9 Keys wurden von der API abgelehnt (401 Ungültig oder 429 Limit)."}

# --- HAUPTBEREICH ---
with st.spinner("Prüfe Keys und scanne Tipico nach Value Bets..."):
    result = fetch_api_data(sport_key, API_KEYS)
    
    if "error" in result:
        st.error(result["error"])
        if st.button("🔄 Cache leeren & Neustart"):
            st.cache_data.clear()
            st.rerun()
    else:
        odds_data = result["data"]
        st.success(f"✅ API Verbindung steht! (Verwendet Key #{result['key_idx'] + 1})")
        
        if not odds_data:
            st.info("Keine anstehenden Spiele für diese Liga gefunden.")
        else:
            found_tipico = False
            for match in odds_data:
                h_team, a_team = match['home_team'], match['away_team']
                start = datetime.fromisoformat(match['commence_time'].replace('Z', '+00:00')).astimezone(tz_de).strftime("%d.%m. %H:%M")
                
                # Wir filtern direkt im Code nach Tipico (oder tipico_de), um sicherzugehen
                tipico_bookie = next((b for b in match.get('bookmakers', []) if 'tipico' in b['key'].lower()), None)
                
                if tipico_bookie:
                    found_tipico = True
                    ki_probs = calc_probs(h_team, a_team)
                    markets = tipico_bookie['markets']
                    
                    q_1, q_x, q_2, q_over25 = 0.0, 0.0, 0.0, 0.0
                    for m in markets:
                        if m['key'] == 'h2h':
                            q_1 = next((i['price'] for i in m['outcomes'] if i['name'] == h_team), 0)
                            q_x = next((i['price'] for i in m['outcomes'] if i['name'] == 'Draw'), 0)
                            q_2 = next((i['price'] for i in m['outcomes'] if i['name'] == a_team), 0)
                        elif m['key'] == 'totals':
                            q_over25 = next((i['price'] for i in m['outcomes'] if i['name'] == 'Over' and i['point'] == 2.5), 0)

                    with st.container(border=True):
                        st.markdown(f"#### 🏟️ {h_team} vs {a_team} <span style='font-size:0.8rem; color:gray;'>({start})</span>", unsafe_allow_html=True)
                        c1, c2, c3, c4 = st.columns(4)
                        
                        def render_market(col, label, ki_prob, tipico_q):
                            if tipico_q == 0:
                                col.metric(label, "N/A")
                                return
                            ev = (ki_prob * tipico_q) - 1.0
                            ev_color = "ev-good" if ev > 0 else "ev-bad"
                            sign = "+" if ev > 0 else ""
                            col.markdown(f"**{label}**<br>Tipico: `{tipico_q}`<br>KI: `{ki_prob*100:.1f}%`<br><span class='{ev_color}'>EV: {sign}{ev*100:.1f}%</span>", unsafe_allow_html=True)

                        render_market(c1, "Sieg Heim (1)", ki_probs["1"], q_1)
                        render_market(c2, "Draw (X)", ki_probs["X"], q_x)
                        render_market(c3, "Sieg Ausw (2)", ki_probs["2"], q_2)
                        render_market(c4, "Über 2.5 Tore", ki_probs["Over2.5"], q_over25)

            if not found_tipico:
                st.warning("Spiele gefunden, aber Tipico hat aktuell für diese Liga noch keine Quoten online. (Versuch es später nochmal oder teste eine andere Liga).")
