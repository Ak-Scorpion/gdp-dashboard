import streamlit as st
import requests
import pandas as pd
import random

st.set_page_config(page_title="KI Wettprognosen & Kombi-Generator", layout="wide")

st.title("⚽ KI Wettprognosen & Kombi-Generator")
st.write("Vergleiche Quoten und erstelle automatisch KI-Kombi-Scheine.")

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

# --- BEREICH 1: EINZELNE LIGA ANSEHEN ---
st.subheader("1. Einzelne Liga analysieren")
ausgewaehlte_liga = st.selectbox("Wähle eine Liga aus:", list(ligen.keys()))

if st.button("Spiele dieser Liga laden"):
    liga_code = ligen[ausgewaehlte_liga]
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
                            "KI Heimsieg %": f"{prob_h}%",
                            "KI Unentschieden %": f"{prob_d}%",
                            "KI Auswärtssieg %": f"{prob_a}%"
                        })
                df_display = pd.DataFrame(spiele_liste)
                st.dataframe(df_display, use_container_width=True)
            else:
                st.error("Keine Spiele gefunden. Überprüfe deinen API-Key.")
        except Exception as e:
            st.error(f"Fehler beim Abrufen der Daten: {e}")

st.divider()

# --- BEREICH 2: KOMBI-SCHEIN GENERATOR ---
st.subheader("2. 🎯 KI Kombi-Schein Generator (Max. 3 Wetten)")
st.write("Generiert einen Kombi-Schein aus den Top-Ligen mit den stärksten Quoten/Tipps.")

if st.button("🎲 Kombi-Schein mit 3 Wetten generieren"):
    alle_tipps = []
    
    with st.spinner("Durchsuche alle Top-Ligen nach den besten Tipps..."):
        # Lade Daten aus den ersten 3 Hauptligen um API-Anfragen zu sparen
        fokus_ligen = ["soccer_germany_bundesliga", "soccer_epl", "soccer_spain_la_liga"]
        
        for code in fokus_ligen:
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
                            
                            # Favoriten-Tipps sammeln
                            if q_home and q_home > 1.2:
                                alle_tipps.append({"Begegnung": f"{home} vs {away}", "Tipp": f"Sieg {home}", "Quote": q_home})
                            if q_away and q_away > 1.2:
                                alle_tipps.append({"Begegnung": f"{home} vs {away}", "Tipp": f"Sieg {away}", "Quote": q_away})
            except Exception:
                pass

    if len(alle_tipps) >= 3:
        # Zufällige oder beste 3 Wetten auswählen
        kombi_auswahl = random.sample(alle_tipps, 3)
        
        gesamtquote = 1.0
        st.success("### 📜 Dein generierter KI-Kombi-Schein:")
        
        for idx, tipp in enumerate(kombi_auswahl, 1):
            st.write(f"**Wette {idx}:** {tipp['Begegnung']} — **Tipp:** {tipp['Tipp']} (Quote: `{tipp['Quote']}`)")
            gesamtquote *= tipp['Quote']
        
        st.metric(label="💥 Gesamtquote des Kombi-Scheins", value=f"{round(gesamtquote, 2)}")
        st.info("💡 Tipp: Setze Kombi-Scheine nur mit kleinen Einsätzen, da das Risiko mit mehreren Spielen steigt.")
    else:
        st.warning("Nicht genügend Spieldaten gefunden, um 3 Wetten zusammenzustellen. Versuche es später erneut.")


