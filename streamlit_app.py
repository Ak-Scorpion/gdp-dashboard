import streamlit as st
import requests
import pandas as pd
import random

st.set_page_config(page_title="KI Wettprognosen & Kombi-Generator", layout="wide")

st.title("⚽ KI Wettprognosen — Safe-Kombi Generator")
st.write("Vergleiche Quoten und erstelle gezielte Favoriten-Kombis für deine Wunsch-Liga.")

# TRAGE HIER DEINEN API-KEY EIN:
API_KEY = '9fa7390d10404cdab8fd77d2445655e0'

ligen = {
    "Deutschland (Bundesliga)": "soccer_germany_bundesliga",
    "England (Premier League)": "soccer_epl",
    "Spanien (La Liga)": "soccer_spain_la_liga",
    "Italien (Serie A)": "soccer_italy_serie_a",
    "Frankreich (Ligue 1)": "soccer_france_ligue_one",
    "Champions League": "soccer_uefa_champs_league"
}

# --- BEREICH 1: LIGA-AUSWAHL ---
ausgewaehlte_liga_name = st.selectbox("Wähle deine Liga aus:", list(ligen.keys()))
liga_code = ligen[ausgewaehlte_liga_name]

col1, col2 = st.columns(2)

# --- BEREICH 2: EINZELNE SPIELE ANZEIGEN ---
with col1:
    st.subheader("1. Übersicht aller Spiele")
    if st.button("Spiele der Liga anzeigen"):
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
                                "Quote Heim": q_home,
                                "Quote X": q_draw,
                                "Quote Auswärts": q_away,
                                "KI Heim %": f"{prob_h}%",
                                "KI Auswärts %": f"{prob_a}%"
                            })
                    df_display = pd.DataFrame(spiele_liste)
                    st.dataframe(df_display, use_container_width=True)
                else:
                    st.error("Keine Spiele gefunden. Überprüfe deinen API-Key.")
            except Exception as e:
                st.error(f"Fehler: {e}")

st.divider()

# --- BEREICH 3: GEZIELTER SAFE-KOMBI GENERATOR ---
st.subheader(f"2. 🛡️ Safe-Kombi erstellen (Nur {ausgewaehlte_liga_name})")
st.write(f"Erstellt einen 3er-Kombi-Schein aus den sichersten Favoriten-Spielen der **{ausgewaehlte_liga_name}**.")

if st.button(f"🎯 3er-Kombi für {ausgewaehlte_liga_name} generieren"):
    sichere_tipps = []
    
    with st.spinner(f"Analysiere Favoriten aus {ausgewaehlte_liga_name}..."):
        url = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
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
                        
                        # Filter für echte Favoriten (Siegquote 1.20 bis 1.85)
                        if q_home and 1.20 <= q_home <= 1.85:
                            prob = round((1 / q_home) * 100)
                            sichere_tipps.append({
                                "Begegnung": f"{home} vs {away}",
                                "Tipp": f"Sieg {home}",
                                "Quote": q_home,
                                "Chance": prob
                            })
                        if q_away and 1.20 <= q_away <= 1.85:
                            prob = round((1 / q_away) * 100)
                            sichere_tipps.append({
                                "Begegnung": f"{home} vs {away}",
                                "Tipp": f"Sieg {away}",
                                "Quote": q_away,
                                "Chance": prob
                            })
        except Exception as e:
            st.error(f"Fehler beim Abrufen der Daten: {e}")

    if len(sichere_tipps) >= 3:
        # Sortiere nach der höchsten Gewinnchance
        sichere_tipps = sorted(sichere_tipps, key=lambda x: x['Chance'], reverse=True)
        kombi_auswahl = random.sample(sichere_tipps[:6], 3)
        
        gesamtquote = 1.0
        st.success(f"### 📜 Dein KI-Safe-Schein ({ausgewaehlte_liga_name}):")
        
        for idx, tipp in enumerate(kombi_auswahl, 1):
            st.write(f"**Wette {idx}:** {tipp['Begegnung']} — **Tipp:** `{tipp['Tipp']}` | **Quote:** `{tipp['Quote']}` | **Siegchance:** `{tipp['Chance']}%`")
            gesamtquote *= tipp['Quote']
        
        st.metric(label="💥 Gesamtquote des Scheins", value=f"{round(gesamtquote, 2)}")
    elif len(sichere_tipps) > 0:
        st.warning(f"In der {ausgewaehlte_liga_name} gibt es aktuell nur {len(sichere_tipps)} klare Favoriten-Spiele. Es werden mindestens 3 Spiele für eine Kombi benötigt.")
    else:
        st.warning(f"Aktuell wurden in der {ausgewaehlte_liga_name} keine eindeutigen Favoriten-Spiele im sicheren Quotenbereich (1.20 - 1.85) gefunden.")



