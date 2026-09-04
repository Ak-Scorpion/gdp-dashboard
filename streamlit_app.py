import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="KI Wettprognosen Top-Ligen", layout="wide")

st.title("⚽ KI Wettprognosen — Top 5 Ligen")
st.write("Vergleiche KI-Wahrscheinlichkeiten mit den Quoten der Buchmacher.")

# TRAGE HIER DEINEN API-KEY VON THE-ODDS-API.COM EIN:
API_KEY = '9fa7390d10404cdab8fd77d2445655e0'

ligen = {
    "Deutschland (Bundesliga)": "soccer_germany_bundesliga",
    "England (Premier League)": "soccer_epl",
    "Spanien (La Liga)": "soccer_spain_la_liga",
    "Italien (Serie A)": "soccer_italy_serie_a",
    "Frankreich (Ligue 1)": "soccer_france_ligue_one",
    "Champions League": "soccer_uefa_champs_league"
}

ausgewaehlte_liga = st.selectbox("Wähle eine Liga aus:", list(ligen.keys()))

if st.button("Spiele & Quoten laden"):
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
            st.error(f"Fehler: {e}")

