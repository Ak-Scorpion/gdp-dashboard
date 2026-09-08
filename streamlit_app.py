import random
import streamlit as st

st.set_page_config(
    page_title="ProBetts - Sicherer Schein Generator",
    page_icon="⚽",
    layout="centered",
)

# CSS Styling für den Dark Mode und das Tipico-Design
st.markdown(
    """
<style>
    :root {
        --bg-color: #0f172a;
        --card-bg: #1e293b;
        --accent: #10b981;
        --tipico-red: #ea1d2c;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }
    .stApp {
        background-color: var(--bg-color);
        color: var(--text-main);
    }
    .league-title {
        color: var(--accent);
        border-bottom: 2px solid #334155;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .match-card {
        background-color: var(--card-bg);
        border-radius: 8px;
        padding: 1.2rem;
        margin-top: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 1rem;
    }
    .match-header {
        display: flex;
        justify-content: space-between;
        color: var(--text-muted);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.4rem;
    }
    .match-teams {
        font-size: 1.15rem;
        font-weight: bold;
        color: #f8fafc;
        margin-bottom: 0.4rem;
    }
    .prediction-box {
        background-color: #0f172a;
        padding: 0.8rem;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 0.8rem;
        flex-wrap: wrap;
        gap: 1rem;
    }
    .tip {
        color: var(--accent);
        font-weight: bold;
    }
    .odds-container {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }
    .odds-badge {
        background-color: var(--tipico-red);
        color: #fff;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: bold;
    }
    .odds {
        background-color: #f8fafc;
        color: #000;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-weight: bold;
    }
    .analysis-text {
        color: var(--text-muted);
        font-size: 0.9rem;
        line-height: 1.4;
    }
    .total-box {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 2px solid var(--accent);
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin-top: 2rem;
        margin-bottom: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Erweiterte Datenbank mit Tag-Zuordnung (Heute, Morgen, Tag 3)
safe_matches_db = [
    {
        "league": "🇪🇺 UEFA Champions League",
        "time": "Heute, 21:00 Uhr",
        "day": "Heute",
        "conf": "🟢 Sehr Hoch",
        "teams": "Real Madrid vs. Inter Mailand",
        "analysis": (
            "Taktisches Auftaktspiel. Real im Bernabéu extrem heimstark,"
            " doppelte Chance zur Absicherung ideal."
        ),
        "tip": "Doppelte Chance 1X",
        "odds": 1.32,
    },
    {
        "league": "🇪🇺 UEFA Champions League",
        "time": "Mittwoch, 18:45 Uhr",
        "day": "Morgen",
        "conf": "🟢 Sehr Hoch",
        "teams": "FC Barcelona vs. Feyenoord Rotterdam",
        "analysis": (
            "Barcelona drückt von Minute eins an auf das Tor und ist klarer"
            " Favorit."
        ),
        "tip": "Sieg Barcelona (1X2)",
        "odds": 1.45,
    },
    {
        "league": "🇪🇺 UEFA Champions League",
        "time": "Donnerstag, 21:00 Uhr",
        "day": "Alle 3 Tage",
        "conf": "🟢 Sehr Hoch",
        "teams": "FC Bayern München vs. FK Bodø/Glimt",
        "analysis": (
            "Der Rekordmeister lässt sich daheim gegen Außenseiter selten"
            " die Butter vom Brot nehmen."
        ),
        "tip": "Bayern Sieg & Über 1.5 Tore",
        "odds": 1.35,
    },
    {
        "league": "🇪🇺 UEFA Europa League",
        "time": "Donnerstag, 18:45 Uhr",
        "day": "Alle 3 Tage",
        "conf": "🟢 Hoch",
        "teams": "AS Roma vs. Bayer Leverkusen",
        "analysis": (
            "Ausgeglichenes Duell, Leverkusen spielt auswärts sehr kompakt"
            " und verliert selten."
        ),
        "tip": "Doppelte Chance X2",
        "odds": 1.38,
    },
    {
        "league": "🇪🇺 UEFA Conference League",
        "time": "Donnerstag, 21:00 Uhr",
        "day": "Alle 3 Tage",
        "conf": "🟢 Hoch",
        "teams": "ACF Fiorentina vs. Aston Villa",
        "analysis": (
            "Offener Schlagabtausch mit Chancen auf beiden Seiten, mindestens"
            " 2 Tore sollten fallen."
        ),
        "tip": "Über 1.5 Tore im Spiel",
        "odds": 1.25,
    },
    {
        "league": "⚽ Bundesliga",
        "time": "Samstag, 15:30 Uhr",
        "day": "Alle 3 Tage",
        "conf": "🟢 Sehr Hoch",
        "teams": "Borussia Dortmund vs. SC Paderborn",
        "analysis": (
            "Klarer Klassenunterschied im Signal Iduna Park, Pflichtsieg für"
            " den BVB."
        ),
        "tip": "Sieg Dortmund (1X2)",
        "odds": 1.30,
    },
    {
        "league": "⚽ Premier League",
        "time": "Samstag, 16:00 Uhr",
        "day": "Alle 3 Tage",
        "conf": "🟢 Hoch",
        "teams": "Arsenal FC vs. FC Everton",
        "analysis": (
            "Arsenal defensiv eine Festung und im Titelrennen auf Heimsiege"
            " angewiesen."
        ),
        "tip": "Sieg Arsenal",
        "odds": 1.28,
    },
]

# --- SIDEBAR KONFIGURATION ---
st.sidebar.header("⚙️ Schein Konfigurator")

# Zeitraum-Auswahl (Heute, Morgen, Alle 3 Tage)
time_filter = st.sidebar.radio(
    "📅 Zeitraum wählen:", ["Heute", "Morgen", "Alle 3 Tage"]
)

all_leagues = list(set([m["league"] for m in safe_matches_db]))
selected_leagues = st.sidebar.multiselect(
    "🏆 Ligen filtern:", all_leagues, default=all_leagues
)

combo_size = st.sidebar.slider(
    "🔢 Kombigröße (Anzahl Spiele):", min_value=2, max_value=4, value=3
)

# Reroll Button
reroll_clicked = st.sidebar.button(
    "🎲 Reroll / Neuen sicheren Schein generieren"
)

# --- HAUPTSEITE ---
st.markdown(
    "<h1 style='text-align: center; color: #f8fafc;'>Pro<span"
    " style='color: #ea1d2c;'>Betts</span> Sicherer Schein Generator</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #94a3b8;'>Optimierte"
    " Niedrig-Quoten-Kombinationen mit maximaler statistischer"
    " Wahrscheinlichkeit</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# Filter-Logik nach Zeitraum und Ligen
if time_filter == "Heute":
    time_pool = [
        m for m in safe_matches_db if m["day"] in ["Heute", "Alle 3 Tage"]
    ]
elif time_filter == "Morgen":
    time_pool = [
        m for m in safe_matches_db if m["day"] in ["Morgen", "Alle 3 Tage"]
    ]
else:
    time_pool = safe_matches_db

filtered_pool = [m for m in time_pool if m["league"] in selected_leagues]

if len(filtered_pool) < combo_size:
    st.warning(
        f"⚠️ Zu wenige Spiele für eine {combo_size}er-Kombi im gewählten Zeitraum"
        " / den gewählten Ligen verfügbar! Bitte Filter anpassen."
    )
else:
    # Zufällige Auswahl für den Reroll-System
    selected_slip = random.sample(filtered_pool, combo_size)

    # Gesamte Quote berechnen
    total_odds = 1.0
    for match in selected_slip:
        total_odds *= match["odds"]

    # UI für den Wettschein anzeigen
    st.markdown(
        f"<h3>📋 Dein generierter {combo_size}er-Sicherheits-Schein</h3>",
        unsafe_allow_html=True,
    )

    for match in selected_slip:
        st.markdown(
            f"""
        <div class="match-card">
            <div class="match-header">
                <span>{match['league']} • {match['time']}</span>
                <span>Sicherheit: {match['conf']}</span>
            </div>
            <div class="match-teams">{match['teams']}</div>
            <div class="analysis-text">{match['analysis']}</div>
            <div class="prediction-box">
                <div>Tipp: <span class="tip">{match['tip']}</span></div>
                <div class="odds-container">
                    <span class="odds-badge">Tipico</span>
                    <div class="odds">{match['odds']:.2f}</div>
                </div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Gesamtquote Box
    st.markdown(
        f"""
    <div class="total-box">
        <h2 style="margin: 0; color: #10b981;">Gesamtquote: {total_odds:.2f}</h2>
        <p style="margin: 5px 0 0 0; color: #94a3b8;">Empfohlener Einsatz: Kontrolliert & Verantwortungsvoll</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

# Footer
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: #94a3b8; font-size:"
    " 0.85rem;'>Hinweis: Glücksspiel kann süchtig machen. 18+ | Alle Angaben"
    " ohne Gewähr.</p>",
    unsafe_allow_html=True,
)

