import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Pascal Gellers",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DEIN FEST EINGEBAUTER API-KEY ---
API_KEY = '9fa7390d10404cdab8fd77d2445655e0'

# --- CUSTOM CSS FÜR PREMIUM DESIGN ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', sans-serif;
    }
    .bet-card {
        background: linear-gradient(135deg, #1e2638 0%, #151b28 100%);
        border: 1px solid #2e3a52;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .bet-card:hover {
        border-color: #00d47e;
        transform: translateY(-2px);
    }
    .owner-tag {
        color: #00d47e;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-size: 0.85rem;
        margin-bottom: 4px;
    }
    .main-title {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 5px;
    }
    .sub-title {
        color: #8b9bb4;
        font-size: 1.0rem;
        margin-bottom: 25px;
    }
    .badge {
        background-color: #00d47e;
        color: #0e1117;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 8px;
    }
    .badge-market {
        background-color: #3b82f6;
        color: #ffffff;
    }
    .odds-tag {
        color: #00d47e;
        font-size: 1.2rem;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- ERWEITERTE TORJÄGER-DATENBANK ---
TOP_STUERMER = {
    "FC Bayern München": "Harry Kane", "Bayern Munich": "Harry Kane",
    "Eintracht Frankfurt": "Omar Marmoush",
    "Borussia Dortmund": "Serhou Guirassy",
    "Bayer Leverkusen": "Victor Boniface",
    "RB Leipzig": "Loïs Openda",
    "VfB Stuttgart": "Deniz Undav",
    "Manchester City": "Erling Haaland",
    "Liverpool": "Mohamed Salah",
    "Arsenal": "Bukayo Saka",
    "Chelsea": "Cole Palmer",
    "Tottenham Hotspur": "Son Heung-min",
    "Real Madrid": "Kylian Mbappé",
    "FC Barcelona": "Robert Lewandowski", "Barcelona": "Robert Lewandowski",
    "Atletico Madrid": "Antoine Griezmann",
    "Inter Milan": "Lautaro Martínez", "Inter": "Lautaro Martínez",
    "Juventus": "Dušan Vlahović",
    "Paris Saint-Germain": "Ousmane Dembélé", "PSG": "Ousmane Dembélé"
}

LIGEN = {
    "🇩🇪 Deutschland (Bundesliga)": "soccer_germany_bundesliga",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England (Premier League)": "soccer_epl",
    "🇪🇸 Spanien (La Liga)": "soccer_spain_la_liga",
    "🇮🇹 Italien (Serie A)": "soccer_italy_serie_a",
    "🇫🇷 Frankreich (Ligue 1)": "soccer_france_ligue_one",
    "🏆 Champions League": "soccer_uefa_champs_league",
    "🇪🇺 Europa League": "soccer_uefa_europa_league",
    "🌍 Conference League": "soccer_uefa_europa_conference_league"
}

DEUTSCHE_ANBIETER = {
    "Tipico": "bwin",
    "Neo.bet": "bwin",
    "bwin (Deutschland)": "bwin",
    "Bet-at-home": "betathome",
    "Bet365 (DE)": "bet365",
    "Betano": "bwin",
    "Oddset": "bwin"
}

# Generiere Liste von Spieltag 1 bis 34
SPIELTAGE = [f"{i}. Spieltag" for i in range(1, 35)] + ["Aktuelle Woche (Standard)"]

def format_datum(date_str):
    if not date_str:
        return "Unbekannt"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%d.%m.%Y um %H:%M Uhr")
    except Exception:
        return date_str

def get_torjaeger_tipp(team_name):
    if team_name in TOP_STUERMER:
        return f"Tor durch {TOP_STUERMER[team_name]}"
    return f"{team_name} erzielt mind. 2 Tore"

def get_best_bookmaker_odds(match_bookmakers, selected_bm_key, home_team, away_team):
    if not match_bookmakers:
        return None, None, None
    
    target_bm = next((bm for bm in match_bookmakers if bm['key'] == selected_bm_key), None)
    if not target_bm:
        target_bm = match_bookmakers[0]
        
    odds = target_bm['markets'][0]['outcomes']
    q_home = next((item['price'] for item in odds if item['name'] == home_team), None)
    q_away = next((item['price'] for item in odds if item['name'] == away_team), None)
    q_draw = next((item['price'] for item in odds if item['name'] == 'Draw'), None)
    
    return q_home, q_away, q_draw

# --- HEADER ---
st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
st.markdown('<div class="main-title">⚽ KI Wettprognosen & Kombi Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Präzise Spieltag-Analyse, freie Ligenauswahl und KI-generierte Wett-Kombinationen</div>', unsafe_allow_html=True)

# --- NAVIGATION TABS ---
tab1, tab2 = st.tabs(["📊 Einzelne Liga & Spieltag", "🎯 Individueller Kombi-Generator"])

# --- TAB 1: EINZELNE LIGA ANALYSE ---
with tab1:
    col_sel, col_sp, col_bm = st.columns([2, 1.5, 1.5])
    with col_sel:
        ausgewaehlte_liga_label = st.selectbox("Wähle Wettbewerb/Liga:", list(LIGEN.keys()))
    with col_sp:
        gewaehlter_spieltag_tab1 = st.selectbox("Spieltag wählen:", SPIELTAGE, index=len(SPIELTAGE)-1, key="sp_tab1")
    with col_bm:
        anbieter_wahl_tab1 = st.selectbox("Wettanbieter:", list(DEUTSCHE_ANBIETER.keys()), key="bm_tab1")
        
    btn_liga = st.button("🔍 Spiele laden", use_container_width=True)
    
    if btn_liga:
        liga_code = LIGEN[ausgewaehlte_liga_label]
        bm_code = DEUTSCHE_ANBIETER[anbieter_wahl_tab1]
        
        url = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
        
        with st.spinner(f"Lade Quoten für {ausgewaehlte_liga_label} ({gewaehlter_spieltag_tab1})..."):
            try:
                res = requests.get(url)
                data = res.json()

                if isinstance(data, list) and len(data) > 0:
                    spiele_liste = []
                    for match in data:
                        match_time = format_datum(match.get('commence_time'))
                        home = match['home_team']
                        away = match['away_team']
                        
                        q_home, q_away, q_draw = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)

                        prob_h = round((1 / q_home) * 100) if q_home else 0
                        prob_d = round((1 / q_draw) * 100) if q_draw else 0
                        prob_a = round((1 / q_away) * 100) if q_away else 0

                        spiele_liste.append({
                            "Anstoßzeit": match_time,
                            "Heim": home,
                            "Auswärts": away,
                            "Quote 1": q_home,
                            "Quote X": q_draw,
                            "Quote 2": q_away,
                            "Chance Heim": f"{prob_h}%",
                            "Chance Auswärts": f"{prob_a}%"
                        })
                    if spiele_liste:
                        df_display = pd.DataFrame(spiele_liste)
                        st.dataframe(df_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("Keine Begegnungen für den gewählten Filter gefunden.")
                else:
                    st.error("Keine Spiele gefunden oder API-Limit erreicht.")
            except Exception as e:
                st.error(f"Fehler beim Abrufen der Daten: {e}")

# --- TAB 2: INDIVIDUELLER KOMBI GENERATOR ---
with tab2:
    st.write("### ⚙️ Eigene Ligen & Einstellungen festlegen")
    
    col_ligen, col_settings = st.columns([2, 1])
    
    with col_ligen:
        ausgewaehlte_ligen = st.multiselect(
            "Wähle deine gewünschten Ligen aus (einzeln oder gemischt):",
            options=list(LIGEN.keys()),
            default=["🇩🇪 Deutschland (Bundesliga)", "🇪🇸 Spanien (La Liga)"]
        )
        
    with col_settings:
        gewaehlter_spieltag_gen = st.selectbox("Spieltag / Zeitraum:", SPIELTAGE, index=len(SPIELTAGE)-1, key="sp_gen")
        anbieter_wahl_gen = st.selectbox("Wettanbieter:", list(DEUTSCHE_ANBIETER.keys()), key="bm_gen")
        anzahl_wetten = st.number_input("Anzahl der Wetten auf dem Schein:", min_value=2, max_value=10, value=3, step=1)
        
    generate_click = st.button("🔄 KI Kombi-Schein jetzt generieren", type="primary", use_container_width=True)

    if generate_click:
        if not ausgewaehlte_ligen:
            st.error("Bitte wähle mindestens eine Liga aus!")
        else:
            bm_code = DEUTSCHE_ANBIETER[anbieter_wahl_gen]
            moegliche_tipps = []
            
            with st.spinner("Analysiere gewählte Ligen & Spieltage..."):
                for liga_label in ausgewaehlte_ligen:
                    code = LIGEN[liga_label]
                    url = f'https://api.the-odds-api.com/v4/sports/{code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
                    try:
                        res = requests.get(url)
                        data = res.json()
                        if isinstance(data, list):
                            for match in data:
                                match_time = format_datum(match.get('commence_time'))
                                home = match['home_team']
                                away = match['away_team']
                                
                                q_home, q_away, _ = get_best_bookmaker_odds(match.get('bookmakers'), bm_code, home, away)
                                
                                if q_home or q_away:
                                    # A) KLARER FAVORIT HEIM
                                    if q_home and 1.25 <= q_home <= 1.65:
                                        tor_tipp = get_torjaeger_tipp(home)
                                        moegliche_tipps.append({
                                            "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                            "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "1X2 Hauptwette 🛡️"
                                        })
                                        moegliche_tipps.append({
                                            "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                            "Tipp": tor_tipp, "Quote": 1.75, "Markt": "Torschütze / Tore ⚽"
                                        })

                                    # B) KLARER FAVORIT AUSWÄRTS
                                    if q_away and 1.25 <= q_away <= 1.65:
                                        tor_tipp = get_torjaeger_tipp(away)
                                        moegliche_tipps.append({
                                            "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                            "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "1X2 Hauptwette 🛡️"
                                        })
                                        moegliche_tipps.append({
                                            "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                            "Tipp": tor_tipp, "Quote": 1.80, "Markt": "Torschütze / Tore ⚽"
                                        })

                                    # C) LEICHTER FAVORIT / VALUE WETTE
                                    if q_home and 1.66 <= q_home <= 2.30 and (not q_away or q_home < q_away):
                                        moegliche_tipps.append({
                                            "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                            "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Value Sieg 🎯"
                                        })

                                    # D) TORMARKT
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": "Über 1.5 Tore im Spiel", "Quote": 1.32, "Markt": "Über 1.5 Tore ⚽"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": "Beide Teams treffen (Ja)", "Quote": 1.68, "Markt": "BTTS 🔥"
                                    })
                    except Exception:
                        pass

            if len(moegliche_tipps) >= anzahl_wetten:
                random.shuffle(moegliche_tipps)
                
                ausgewaehlte_spiele = set()
                kombi_auswahl = []
                
                for tipp in moegliche_tipps:
                    if tipp['Begegnung'] not in ausgewaehlte_spiele:
                        kombi_auswahl.append(tipp)
                        ausgewaehlte_spiele.add(tipp['Begegnung'])
                    if len(kombi_auswahl) == anzahl_wetten:
                        break
                
                st.session_state['kombi_auswahl'] = kombi_auswahl
                st.session_state['gewaehlter_anbieter'] = anbieter_wahl_gen
                st.session_state['gewaehlter_spieltag'] = gewaehlter_spieltag_gen
            else:
                st.warning(f"Für die gewählten Ligen stehen derzeit nur {len(moegliche_tipps)} verwertbare Quoten zur Verfügung.")

    # --- SCHEIN ANZEIGEN UND RECHNER BEREITSTELLEN ---
    if 'kombi_auswahl' in st.session_state and st.session_state['kombi_auswahl']:
        kombi_auswahl = st.session_state['kombi_auswahl']
        anbieter_label = st.session_state.get('gewaehlter_anbieter', 'Anbieter')
        spieltag_label = st.session_state.get('gewaehlter_spieltag', 'Spieltag')
        
        gesamtquote = 1.0
        for item in kombi_auswahl:
            gesamtquote *= item['Quote']
            
        st.markdown(f"### 📜 Dein KI Kombi-Schein ({len(kombi_auswahl)}er Kombi — {spieltag_label})")
        
        cols = st.columns(len(kombi_auswahl))
        for idx, tipp in enumerate(kombi_auswahl):
            with cols[idx]:
                card_html = (
                    f'<div class="bet-card">'
                    f'<span class="badge badge-market">{tipp["Markt"]}</span> '
                    f'<span class="badge" style="background-color: #334155; color: #fff;">{tipp["Liga"]}</span>'
                    f'<h4 style="color: #ffffff; margin: 8px 0 2px 0;">{tipp["Begegnung"]}</h4>'
                    f'<p style="color: #00d47e; font-size: 0.8rem; margin-bottom: 10px;">📅 {tipp["Datum"]}</p>'
                    f'<p style="color: #94a3b8; margin-bottom: 8px;">Tipp: <b style="color: #ffffff;">{tipp["Tipp"]}</b></p>'
                    f'<hr style="border: 0; border-top: 1px solid #2e3a52; margin: 10px 0;">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                    f'<span style="color: #64748b; font-size: 0.85rem;">Quote ({anbieter_label}):</span>'
                    f'<span class="odds-tag">{tipp["Quote"]}</span>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
        
        st.divider()
        
        # --- EINSATZ- & GEWINNRECHNER ---
        st.subheader(f"💰 Einsatz & Gewinn Rechner ({anbieter_label})")
        
        col_q, col_einsatz, col_gewinn = st.columns([1, 1, 1.5])
        
        with col_q:
            st.metric(label="💥 Gesamtquote", value=f"{round(gesamtquote, 2)}")
            
        with col_einsatz:
            einsatz = st.number_input("Dein Einsatz (€):", min_value=1.0, max_value=1000.0, value=10.0, step=5.0)
            
        with col_gewinn:
            moeglicher_gewinn = round(einsatz * gesamtquote, 2)
            st.metric(label="🏆 Möglicher Gewinn", value=f"{moeglicher_gewinn:.2f} €")
