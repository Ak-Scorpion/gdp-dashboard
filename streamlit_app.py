import import streamlit as st
import requests
import pandas as pd
import random

st.set_page_config(page_title="KI Wettprognosen — Tipico Style", layout="wide")

st.title("⚽ KI Wettprognosen — Tipico-Style Kombi Generator")
st.write("Generiert vielseitige Scheine mit Siegwetten, Torschützen-Tipps, 'Beide treffen' & Doppelter Chance.")

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

# --- BEREICH 1: LIGA ANALYSE ---
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

# --- BEREICH 2: TIPICO-STYLE KOMBI GENERATOR ---
st.subheader("2. 🎯 Tipico-Style Kombi-Schein erstellen")
st.write("Erstellt Kombinationen aus Siegen, Torschützen, 'Beide treffen' & Doppelter Chance.")

if st.button("🔄 Tipico-Mix Schein generieren"):
    fokus_ligen = {
        "Bundesliga": "soccer_germany_bundesliga",
        "Premier League": "soccer_epl",
        "La Liga": "soccer_spain_la_liga",
        "Serie A": "soccer_italy_serie_a",
        "Ligue 1": "soccer_france_ligue_one"
    }
    
    moegliche_tipps = []
    
    with st.spinner("Durchsuche Märkte nach Tipico-Wettoptionen..."):
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
                            
                            # 1. Klarer Favorit -> Sieg oder Torschütze/Sieg+Tore
                            if q_home and 1.20 <= q_home <= 1.65:
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "1X2 Hauptwette 🛡️"
                                })
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Hauptstürmer ({home}) trifft im Spiel", "Quote": 1.75, "Markt": "Torschütze ⚽"
                                })
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {home} & Über 1.5 Tore", "Quote": round(q_home * 1.3, 2), "Markt": "Sieg + Tore 💥"
                                })

                            if q_away and 1.20 <= q_away <= 1.65:
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "1X2 Hauptwette 🛡️"
                                })
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Hauptstürmer ({away}) trifft im Spiel", "Quote": 1.80, "Markt": "Torschütze ⚽"
                                })

                            # 2. Ausgeglichene Partien -> Doppelte Chance oder Beide treffen
                            if (q_home and 1.70 <= q_home <= 2.60) or (q_away and 1.70 <= q_away <= 2.60):
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": "Beide Teams treffen (Ja)", "Quote": 1.65, "Markt": "BTTS 🔥"
                                })
                                moegliche_tipps.append({
                                    "Liga": liga_label, "Begegnung": f"{home} vs {away}",
                                    "Tipp": f"Doppelte Chance (1X {home})", "Quote": 1.35, "Markt": "Doppelte Chance 🔒"
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
        st.success("### 📜 Dein Tipico-Style Kombi-Schein:")
        
        for idx, tipp in enumerate(kombi_auswahl, 1):
            st.write(f"**Wette {idx} ({tipp['Liga']}):** {tipp['Begegnung']} — **Tipp:** `{tipp['Tipp']}` | **Quote:** `{tipp['Quote']}` | **Wettart:** `{tipp['Markt']}`")
            gesamtquote *= tipp['Quote']
        
        st.metric(label="💥 Tipico Gesamtquote", value=f"{round(gesamtquote, 2)}")
        st.info("💡 Drücke erneut auf den Button, um andere Tipico-Kombinationen zu testen!")
    else:
        st.warning("Keine passenden Spiele gefunden. Versuche es vor dem Spieltag erneut.")






