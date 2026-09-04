import streamlit as st
import requests
import pandas as pd
import random

st.set_page_config(page_title="KI Wettprognosen & Top-Ligen Mix", layout="wide")

st.title("⚽ KI Wettprognosen — Top-Ligen Safe-Kombi")
st.write("Vergleiche Quoten einzelner Ligen oder erstelle einen perfekten Ligen-Mix Kombi-Schein.")

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

# --- BEREICH 1: EINZELNE LIGA ANALYSIEREN ---
st.subheader("1. Einzelne Liga analysieren")
ausgewaehlte_liga_name = st.selectbox("Wähle eine Liga aus:", list(ligen.keys()))

if st.button("Spiele dieser Liga anzeigen"):
    liga_code = ligen[ausgewaehlte_liga_name]
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

# --- BEREICH 2: LIGEN-MIX SAFE-KOMBI GENERATOR ---
st.subheader("2. 🌍 Perfekten Ligen-Mix Kombi-Schein erstellen")
st.write("Kombiniert automatisch die sichersten Favoriten-Spiele aus **verschiedenen Top-Ligen** zu einem 3er-Schein.")

if st.button("🎯 Top-Ligen-Mix Schein generieren"):
    # Ligen, aus denen gemischt wird
    fokus_ligen = {
        "Bundesliga": "soccer_germany_bundesliga",
        "Premier League": "soccer_epl",
        "La Liga": "soccer_spain_la_liga",
        "Serie A": "soccer_italy_serie_a",
        "Ligue 1": "soccer_france_ligue_one"
    }
    
    sichere_tipps_pro_liga = []
    
    with st.spinner("Durchsuche alle Top-Ligen nach den sichersten Favoriten..."):
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
                            
                            # Nur sichere Favoriten (Quote zwischen 1.20 und 1.85)
                            if q_home and 1.20 <= q_home <= 1.85:
                                prob = round((1 / q_home) * 100)
                                sichere_tipps_pro_liga.append({
                                    "Liga": liga_label,
                                    "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {home}",
                                    "Quote": q_home,
                                    "Chance": prob
                                })
                            if q_away and 1.20 <= q_away <= 1.85:
                                prob = round((1 / q_away) * 100)
                                sichere_tipps_pro_liga.append({
                                    "Liga": liga_label,
                                    "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {away}",
                                    "Quote": q_away,
                                    "Chance": prob
                                })
            except Exception:
                pass

    if len(sichere_tipps_pro_liga) >= 3:
        # Sortiere nach den höchsten Gewinnchancen
        sichere_tipps_pro_liga = sorted(sichere_tipps_pro_liga, key=lambda x: x['Chance'], reverse=True)
        
        # Versuche Spiele aus unterschiedlichen Ligen auszuwählen
        ausgewaehlte_ligen_set = set()
        kombi_auswahl = []
        
        for tipp in sichere_tipps_pro_liga:
            if tipp['Liga'] not in ausgewaehlte_ligen_set:
                kombi_auswahl.append(tipp)
                ausgewaehlte_ligen_set.add(tipp['Liga'])
            if len(kombi_auswahl) == 3:
                break
                
        # Falls weniger als 3 verschiedene Ligen da sind, fülle mit den besten verbleibenden auf
        if len(kombi_auswahl) < 3:
            kombi_auswahl = random.sample(sichere_tipps_pro_liga[:6], 3)
        
        gesamtquote = 1.0
        st.success("### 📜 Dein gemischter KI-Safe-Schein aus den Top-Ligen:")
        
        for idx, tipp in enumerate(kombi_auswahl, 1):
            st.write(f"**Wette {idx} ({tipp['Liga']}):** {tipp['Begegnung']} — **Tipp:** `{tipp['Tipp']}` | **Quote:** `{tipp['Quote']}` | **Siegchance:** `{tipp['Chance']}%`")
            gesamtquote *= tipp['Quote']
        
        st.metric(label="💥 Gesamtquote des Ligen-Mix Scheins", value=f"{round(gesamtquote, 2)}")
        st.info("✅ Dieser Schein kombiniert automatisch klare Favoriten aus verschiedenen europäischen Top-Ligen!")
    else:
        st.warning("Es wurden derzeit nicht genügend klare Favoriten-Spiele in den Ligen gefunden. Versuche es vor dem Spieltag erneut.")




