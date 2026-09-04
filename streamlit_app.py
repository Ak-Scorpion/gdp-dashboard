import streamlit as st
import requests
import pandas as pd
import random
from datetime import datetime, timedelta

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
    "🏆 Champions League": "soccer_uefa_champs_league",
    "🇪🇺 Europa League": "soccer_uefa_europa_league",
    "🌍 Conference League": "soccer_uefa_europa_conference_league"
}

def format_datum_and_check_aktuell(date_str):
    if not date_str:
        return "Unbekannt", False
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        jetzt = datetime.utcnow()
        in_einer_woche = jetzt + timedelta(days=7)
        ist_aktuell = jetzt <= dt <= in_einer_woche
        formatted_str = dt.strftime("%d.%m.%Y um %H:%M Uhr")
        return formatted_str, ist_aktuell
    except Exception:
        return date_str, True

# --- HEADER ---
st.markdown('<div class="owner-tag">📱 App von Pascal Gellers</div>', unsafe_allow_html=True)
st.markdown('<div class="main-title">⚽ KI Wettprognosen & Tipico Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Analyse von Live-Quoten, Anstoßzeiten & KI-generierten Kombi-Scheinen für die nächsten Spiele</div>', unsafe_allow_html=True)

# --- NAVIGATION TABS ---
tab1, tab2 = st.tabs(["📊 Liga Analyse & Quoten", "🎯 Tipico Kombi-Generator"])

# --- TAB 1: LIGA ANALYSE ---
with tab1:
    col_sel, col_space = st.columns([1, 2])
    with col_sel:
        ausgewaehlte_liga_label = st.selectbox("Wähle Wettbewerb/Liga:", list(ligen.keys()))
        btn_liga = st.button("🔍 Spiele laden", use_container_width=True)
    
    if btn_liga:
        liga_code = ligen[ausgewaehlte_liga_label]
        url = f'https://api.the-odds-api.com/v4/sports/{liga_code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
        
        with st.spinner("Lade Live-Daten für anstehende Spiele..."):
            try:
                res = requests.get(url)
                data = res.json()

                if isinstance(data, list) and len(data) > 0:
                    spiele_liste = []
                    for match in data:
                        match_time, ist_aktuell = format_datum_and_check_aktuell(match.get('commence_time'))
                        if not ist_aktuell:
                            continue
                            
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
                        st.info("Keine anstehenden Spiele für die nächsten 7 Tage in dieser Liga gefunden.")
                else:
                    st.error("Keine Spiele gefunden oder API-Limit erreicht.")
            except Exception as e:
                st.error(f"Fehler beim Abrufen der Daten: {e}")

# --- TAB 2: KOMBI GENERATOR ---
with tab2:
    st.write("### Einstellungen für deinen KI-Kombi-Schein")
    
    col_fokus, col_anzahl = st.columns([2, 1])
    with col_fokus:
        fokus_wahl = st.selectbox(
            "Wähle den Fokus der Spiele:",
            ["🌍 Alle Ligen & Europapokale (Gemischt)", "🏆 Nur Europapokal (Champions League, Europa League, ECL)", "🏟️ Nur Top 5 Ligen (Wochenende)"]
        )
    with col_anzahl:
        anzahl_wetten = st.slider("Anzahl der Wetten auf dem Schein:", min_value=2, max_value=5, value=3)
        
    generate_click = st.button("🔄 KI Kombi-Schein jetzt generieren", type="primary", use_container_width=True)

    if generate_click:
        if "Europapokal" in fokus_wahl:
            fokus_ligen = {
                "Champions League": "soccer_uefa_champs_league",
                "Europa League": "soccer_uefa_europa_league",
                "Conference League": "soccer_uefa_europa_conference_league"
            }
        elif "Top 5" in fokus_wahl:
            fokus_ligen = {
                "Bundesliga": "soccer_germany_bundesliga", "Premier League": "soccer_epl",
                "La Liga": "soccer_spain_la_liga", "Serie A": "soccer_italy_serie_a",
                "Ligue 1": "soccer_france_ligue_one"
            }
        else:
            fokus_ligen = {
                "Bundesliga": "soccer_germany_bundesliga", "Premier League": "soccer_epl",
                "La Liga": "soccer_spain_la_liga", "Serie A": "soccer_italy_serie_a",
                "Ligue 1": "soccer_france_ligue_one", "Champions League": "soccer_uefa_champs_league",
                "Europa League": "soccer_uefa_europa_league", "Conference League": "soccer_uefa_europa_conference_league"
            }

        moegliche_tipps = []
        
        with st.spinner("Analysiere Favoriten & erstelle ausgewogene Quoten-Kombination..."):
            for liga_label, code in fokus_ligen.items():
                url = f'https://api.the-odds-api.com/v4/sports/{code}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h'
                try:
                    res = requests.get(url)
                    data = res.json()
                    if isinstance(data, list):
                        for match in data:
                            match_time, ist_aktuell = format_datum_and_check_aktuell(match.get('commence_time'))
                            if not ist_aktuell:
                                continue
                                
                            home = match['home_team']
                            away = match['away_team']
                            
                            if match.get('bookmakers'):
                                odds = match['bookmakers'][0]['markets'][0]['outcomes']
                                q_home = next((item['price'] for item in odds if item['name'] == home), None)
                                q_away = next((item['price'] for item in odds if item['name'] == away), None)
                                
                                # LOGIK: Immer das favorisierte Team unterstützen (Siegchance > Außenseiter)
                                
                                # A) Klare Favoriten (Quote 1.25 bis 1.65) -> Hohe Gewinnchance
                                if q_home and 1.25 <= q_home <= 1.65:
                                    stuermer = TOP_STUERGME.get(home, f"Top-Torjäger ({home})")
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "1X2 Hauptwette 🛡️"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Tor durch {stuermer}", "Quote": 1.75, "Markt": "Torschütze ⚽"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Sieg {home} & Über 1.5 Tore", "Quote": round(q_home * 1.30, 2), "Markt": "Sieg + Tore 💥"
                                    })

                                if q_away and 1.25 <= q_away <= 1.65:
                                    stuermer = TOP_STUERGME.get(away, f"Top-Torjäger ({away})")
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "1X2 Hauptwette 🛡️"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Tor durch {stuermer}", "Quote": 1.80, "Markt": "Torschütze ⚽"
                                    })

                                # B) Moderate Favoriten / Ausgeglichene Top-Spiele (Quote 1.66 bis 2.30)
                                if q_home and 1.66 <= q_home <= 2.30 and (not q_away or q_home < q_away):
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Sieg {home}", "Quote": q_home, "Markt": "Value Sieg 🎯"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Doppelte Chance (1X {home})", "Quote": round(q_home * 0.70, 2) if q_home * 0.70 >= 1.25 else 1.28, "Markt": "Doppelte Chance 🔒"
                                    })

                                if q_away and 1.66 <= q_away <= 2.30 and (not q_home or q_away < q_home):
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Sieg {away}", "Quote": q_away, "Markt": "Value Sieg 🎯"
                                    })
                                    moegliche_tipps.append({
                                        "Liga": liga_label, "Begegnung": f"{home} vs {away}", "Datum": match_time,
                                        "Tipp": f"Doppelte Chance (X2 {away})", "Quote": round(q_away * 0.70, 2) if q_away * 0.70 >= 1.25 else 1.28, "Markt": "Doppelte Chance 🔒"
                                    })

                                # C) Allgemeine Tore-Märkte für Torgefährliche Spiele
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
            
            gesamtquote = 1.0
            st.markdown(f"### 📜 Dein KI Tipico-Kombi-Schein ({len(kombi_auswahl)}er Kombi)")
            
            cols = st.columns(len(kombi_auswahl))
            for idx, tipp in enumerate(kombi_auswahl):
                gesamtquote *= tipp['Quote']
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
                        f'<span style="color: #64748b; font-size: 0.85rem;">Quote:</span>'
                        f'<span class="odds-tag">{tipp["Quote"]}</span>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
            
            st.divider()
            
            col_m1, col_m2 = st.columns([1, 2])
            with col_m1:
                st.metric(label="💥 Tipico Gesamtquote", value=f"{round(gesamtquote, 2)}")
            with col_m2:
                st.success("✅ Schein erfolgreich generiert! Du kannst die Einstellungen anpassen oder erneut generieren.")
        else:
            st.warning("Für die ausgewählten Filter stehen derzeit nicht genügend Spiele in den nächsten 7 Tagen zur Verfügung.")
