import streamlit as st
import requests
import pandas as pd
import random

st.set_page_config(page_title="KI Wettprognosen & Multi-Kombi", layout="wide")

st.title("⚽ KI Wettprognosen — Variabler Kombi-Generator")
st.write("Generiert vielseitige Scheine mit Siegwetten, Über-1.5-Tore-Tipps und Match-Kombis.")

# DEIN FEST EINGEBAUTER API-KEY:
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

# --- BEREICH 2: VIELSEITIGER KOMBI-GENERATOR ---
st.subheader("2. 🎲 Abwechslungsreichen Kombi-Schein erstellen")
st.write("Generiert Scheine mit einem Mix aus Siegwetten, Über 1.5 Tore & Kombi-Tipps.")

if st.button("🔄 Neuen Multi-Wett-Schein generieren"):
    fokus_ligen = {
        "Bundesliga": "soccer_germany_bundesliga",
        "Premier League": "soccer_epl",
        "La Liga": "soccer_spain_la_liga",
        "Serie A": "soccer_italy_serie_a",
        "Ligue 1": "soccer_france_ligue_one"
    }
    
    moegliche_tipps = []
    
    with st.spinner("Analysiere Spiele & erstelle abwechslungsreiche Wett-Varianten..."):
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
                            
                            # Option A: Klarer Favoritensieg (1.20 bis 1.70)
                            if q_home and 1.20 <= q_home <= 1.70:
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}", 
                                    "Tipp": f"Sieg {home}", "Quote": q_home, "Art": "Einfacher Sieg 🛡️"
                                })
                                # Zusätzliche Variante: Sieg + Über 1.5 Tore (Quote leicht erhöht)
                                combi_q = round(q_home * 1.25, 2)
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}", 
                                    "Tipp": f"Sieg {home} & Über 1.5 Tore", "Quote": combi_q, "Art": "Sieg + Tore ⚽"
                                })

                            if q_away and 1.20 <= q_away <= 1.70:
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}", 
                                    "Tipp": f"Sieg {away}", "Quote": q_away, "Art": "Einfacher Sieg 🛡️"
                                })
                                combi_q = round(q_away * 1.25, 2)
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}", 
                                    "Tipp": f"Sieg {away} & Über 1.5 Tore", "Quote": combi_q, "Art": "Sieg + Tore ⚽"
                                })

                            # Option B: Reines "Über 1.5 Tore" für ausgeglichene/torreiche Partien (1.71 bis 2.50)
                            if (q_home and 1.71 <= q_home <= 2.50) or (q_away and 1.71 <= q_away <= 2.50):
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}", 
                                    "Tipp": "Über 1.5 Tore im Spiel", "Quote": 1.30, "Art": "Tore-Wette 🔥"
                                })
            except Exception:
                pass

    if len(moegliche_tipps) >= 3:
        # Zufällige Auswahl aus verschiedenen Kategorien für maximale Abwechslung
        random.shuffle(moegliche_tipps)
        
        # Stelle sicher, dass nicht 2 verschiedene Tipps für exakt dasselbe Spiel ausgewählt werden
        ausgewaehlte_spiele = set()
        kombi_auswahl = []
        
        for tipp in moegliche_tipps:
            if tipp['Begegnung'] not in ausgewaehlte_spiele:
                kombi_auswahl.append(tipp)
                ausgewaehlte_spiele.add(tipp['Begegnung'])
            if len(kombi_auswahl) == 3:
                break
        
        gesamtquote = 1.0
        st.success("### 📜 Dein vielseitiger KI-Mix-Schein:")
        
        for idx, tipp in enumerate(kombi_auswahl, 1):
            st.write(f"**Wette {idx} ({tipp['Liga']}):** {tipp['Begegnung']} — **Tipp:** `{tipp['Tipp']}` | **Quote:** `{tipp['Quote']}` | **Typ:** `{tipp['Art']}`")
            gesamtquote *= tipp['Quote']
        
        st.metric(label="💥 Gesamtquote des Kombi-Scheins", value=f"{round(gesamtquote, 2)}")
        st.info("💡 Drücke einfach erneut auf den Button, um weitere Variationen (Tore, Siege, Kombis) auszuprobieren!")
    else:
        st.warning("Aktuell stehen nicht genügend Spiele zur Verfügung. Versuche es kurz vor dem nächsten Spieltag erneut.")





