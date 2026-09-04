import streamlit as st
import requests
import pandas as pd
import random

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="KI Wettprognosen — Tipico Premium UI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DEIN FEST EINGEBAUTER API-KEY ---
API_KEY = '9fa7390d10404cdab8fd77d2445655e0'

# --- CUSTOM CSS FÜR PREMIUM DESIGN ---
st.markdown("""
    <style>
    /* Haupt-Hintergrund & Schriftarten */
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', sans-serif;
    }
    
    /* Wett-Karte Styling */
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
    
    /* Header & Titel */
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
    
    /* Badges / Kategorien */
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
    
    /* Quoten-Text */
    .odds-tag {
        color: #00d47e;
        font-size: 1.2rem;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=unsafe_allow_html=True)

# --- DATENBANKEN ---
TOP_STUERGME = {
    "FC Bayern München": "Harry Kane",
    "Bayern Munich": "Harry Kane",
    "Eintracht Frankfurt": "Omar Marmoush",
    "Borussia Dortmund": "Serhou Guirassy",
    "Bayer Leverkusen": "Victor Boniface",
    "RB Leipzig": "Loïs Openda",
    "Manchester City": "Erling Haaland",
    "Liverpool": "Mohamed Salah",
    "Arsenal": "Bukayo Saka",
    "Chelsea": "Cole Palmer",
    "Tottenham Hotspur": "Son Heung-min",
    "Real Madrid": "Kylian Mbappé",
    "FC Barcelona": "Robert Lewandowski",
    "Barcelona": "Robert Lewandowski",
    "Atletico Madrid": "Antoine Griezmann",
    "Inter Milan": "Lautaro Martínez",
    "Inter": "Lautaro Martínez",
    "Juventus": "Dušan Vlahović",
    "Paris Saint-Germain": "Ousmane Dembélé",
    "PSG": "Ousmane Dembélé",
    "Sporting CP": "Viktor Gyökeres"
}

ligen = {
    "🇩🇪 Deutschland (Bundesliga)": "soccer_germany_bundesliga",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England (Premier League)": "soccer_epl",
    "🇪🇸 Spanien (La Liga)": "soccer_spain_la_liga",
    "🇮🇹 Italien (Serie A)": "soccer_italy_serie_a",
    "🇫🇷 Frankreich (Ligue 1)": "soccer_france_ligue_one",
    "🏆 Champions League": "soccer_uefa_champs_league"
}

# --- HEADER ---
st.markdown('<div class="main-title">⚽ KI Wettprognosen & Tipico Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Analyse von Live-Quoten, Match-Wahrscheinlichkeiten und KI-generierten Kombi-Scheinen</div>', unsafe_allow_html=True)

# --- NAVIGATION TABS ---
tab1, tab2 = st.tabs(["📊 Liga Analyse & Quoten", "🎯 Tipico Kombi-Generator"])

# --- TAB 1: LIGA ANALYSE ---
with tab1:
    col_sel, col_space = st.columns([1, 2])
    with col_sel:
        ausgewaehlte_liga_label = st.selectbox("Wähle eine Liga aus:", list(ligen.keys()))
        btn_liga = st.button("🔍 Spiele laden", use_container_width=True)
    
    if btn_liga:
        liga_code = ligen[ausgewaehlte_liga_label]
        url = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
        
        with st.spinner("Lade Live-Daten..."):
            try:
                res = requests.get(url)
                data = res.json()

                if isinstance(data, list) and len(data) > 0:
                    spiele_liste = []
                    for match in data:
                        home = match['home_team']
                        away = match['away_team']
                        if match.get('bookmakers'):
                            odds = match['bookmakers'][0]['markets'][0]['outcomes']
                            q_home = next((item['price'] for item in odds if item['name'] == home), None)
                            q_away = next((item['price'] for item in odds if item['name'] == away), None)
                            q_draw = next((item['price'] for item in odds if item['name'] == 'Draw'), None)

                            prob_h = round((1 / q_home) * 100) if q_home else 0
                            prob_d = round((1 / q_draw) * 100) if q_draw else 0
                            prob_a = round((1 / q_away) * 100) if q_away else 0

                            spiele_liste.append({
                                "Heim": home,
                                "Auswärts": away,
                                "Quote 1": q_home,
                                "Quote X": q_draw,
                                "Quote 2": q_away,
                                "Chance Heim": f"{prob_h}%",
                                "Chance Auswärts": f"{prob_a}%"
                            })
                    df_display = pd.DataFrame(spiele_liste)
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.error("Keine Spiele gefunden oder API-Limit erreicht.")
            except Exception as e:
                st.error(f"Fehler beim Abrufen der Daten: {e}")

# --- TAB 2: KOMBI GENERATOR ---
with tab2:
    st.write("Generiere mit einem Klick deinen vielseitigen Tipico-Kombi-Schein aus den besten europäischen Ligen.")
    
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        generate_click = st.button("🔄 Neuen Tipico-Mix Schein generieren", type="primary", use_container_width=True)
        
    if generate_click:
        fokus_ligen = {
            "Bundesliga": "soccer_germany_bundesliga",
            "Premier League": "soccer_epl",
            "La Liga": "soccer_spain_la_liga",
            "Serie A": "soccer_italy_serie_a",
            "Ligue 1": "soccer_france_ligue_one"
        }
        
        moegliche_tipps = []
        
        with st.spinner("Analysiere Märkte & berechne beste Kombinationen..."):
            for liga_label, code in fokus_ligen.items():
                url = f'https://api.the-odds-api.com/v4/sports/{code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
                try:
                    res = requests.get(url)
                    data = res.json()
                    if isinstance(data, list):
                        for match in data:
                            home = match['home_team']
                            away = match['away_team']
                            if match.get('bookmakers'):
                                odds = match['bookmakers'][0]['markets'][0]['outcomes']
                                q_home = next((item['price'] for item in odds if item['name'] == home), None)
                                q_away = next((item['price'] for item in odds if item['name'] == away), None)
                                
                                # 1. Favorit Heim
                                if q_home and 1.20 <= q_home <= 1.45:
                                    stuermer = TOP_STUERGME.get(home, f"Top-Torjäger ({home})")
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": f"Tor durch {stuermer}", "Quote": 1.70, "Markt": "Torschütze ⚽"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": "Über 2.5 Tore im Spiel", "Quote": 1.55, "Markt": "Über 2.5 Tore 🔥"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": f"Sieg {home} & Über 2.5 Tore", "Quote": round(q_home * 1.45, 2), "Markt": "Sieg + Tore 💥"
                                    })

                                if q_away and 1.20 <= q_away <= 1.45:
                                    stuermer = TOP_STUERGME.get(away, f"Top-Torjäger ({away})")
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": f"Tor durch {stuermer}", "Quote": 1.75, "Markt": "Torschütze ⚽"
                                    })

                                # 2. Moderate Matches
                                if q_home and 1.46 <= q_home <= 1.85:
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "1X2 Hauptwette 🛡️"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": "Über 1.5 Tore im Spiel", "Quote": 1.30, "Markt": "Über 1.5 Tore ⚽"
                                    })

                                # 3. Ausgeglichene Matches
                                if (q_home and q_home > 1.85) or (q_away and q_away > 1.85):
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": "Beide Teams treffen (Ja)", "Quote": 1.65, "Markt": "BTTS 🔥"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                        "Tipp": f"Doppelte Chance (1X {home})", "Quote": 1.38, "Markt": "Doppelte Chance 🔒"
                                    })
                except Exception:
                    pass

        if len(moegliche_tipps) >= 3:
            random.shuffle(moegliche_tipps)
            
            ausgewaehlte_spiele = set()
            kombi_auswahl = []
            
            for tipp in moegliche_tipps:
                if tipp['Begegnung'] not in ausgewaehlte_spiele:
                    kombi_auswahl.append(tipp)
                    ausgewaehlte_spiele.add(tipp['Begegnung'])
                if len(kombi_auswahl) == 3:
                    break
            
            gesamtquote = 1.0
            st.markdown("### 📜 Dein KI Tipico-Kombi-Schein")
            
            # WETT-KARTEN ANZEIGEN
            cols = st.columns(3)
            for idx, tipp in enumerate(kombi_auswahl):
                gesamtquote *= tipp['Quote']
                with cols[idx]:
                    st.markdown(f"""
                        <div class="bet-card">
                            <span class="badge badge-market">{tipp['Markt']}</span>
                            <span class="badge" style="background-color: #334155; color: #fff;">{tipp['Liga']}</span>
                            <h4 style="color: #ffffff; margin: 8px 0;">{tipp['Begegnung']}</h4>
                            <p style="color: #94a3b8; margin-bottom: 8px;">Tipp: <b style="color: #ffffff;">{tipp['Tipp']}</b></p>
                            <hr style="border: 0; border-top: 1px solid #2e3a52; margin: 10px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: #64748b; font-size: 0.85rem;">Quote:</span>
                                <span class="odds-tag">{tipp['Quote']}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            
            st.divider()
            
            # TOTAL QUOTE HIGHLIGHT METRIC
            col_m1, col_m2 = st.columns([1, 2])
            with col_m1:
                st.metric(label="💥 Tipico Gesamtquote", value=f"{round(gesamtquote, 2)}")
            with col_m2:
                st.success("✅ Schein erfolgreich generiert! Klicke erneut auf den Button oben, um neue Variationen zu sehen.")
        else:
            st.warning("Momentan stehen nicht genügend Spiele zur Verfügung. Versuche es vor dem Spieltag erneut.")
