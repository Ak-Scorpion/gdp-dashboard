import streamlit as st

st.set_page_config(page_title="ProBetts - Wettanalysen", page_icon="⚽", layout="centered")

# CSS Styling für den Dark Mode und das Tipico-Design
st.markdown("""
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
        margin-top: 2.5rem;
        font-size: 1.4rem;
        font-weight: bold;
    }
    .match-card {
        background-color: var(--card-bg);
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 1rem;
    }
    .match-header {
        display: flex;
        justify-content: space-between;
        color: var(--text-muted);
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    .match-teams {
        font-size: 1.25rem;
        font-weight: bold;
        color: #f8fafc;
        margin-bottom: 0.5rem;
    }
    .prediction-box {
        background-color: #0f172a;
        padding: 1rem;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 1rem;
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
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .odds {
        background-color: #f8fafc;
        color: #000;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-weight: bold;
    }
    .analysis-text {
        color: var(--text-muted);
        font-size: 0.95rem;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h1 style='text-align: center; color: #f8fafc;'>Pro<span style='color: #ea1d2c;'>Betts</span> Analysis</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>Top-Quoten & Analysen für Champions League, Europa League, Conference League & Top-Ligen</p>", unsafe_allow_html=True)
st.markdown("---")

# Hilfsfunktion für die Match-Karten
def match_card(league, time, conf, teams, analysis, tip, odds):
    st.markdown(f"<div class='league-title'>{league}</div>", unsafe_allow_html=True)
    html_content = f"""
    <div class="match-card">
        <div class="match-header">
            <span>{time}</span>
            <span>Konfidenz: {conf}</span>
        </div>
        <div class="match-teams">{teams}</div>
        <div class="analysis-text">{analysis}</div>
        <div class="prediction-box">
            <div>Tipp: <span class="tip">{tip}</span></div>
            <div class="odds-container">
                <span class="odds-badge">Tipico</span>
                <div class="odds">{odds}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

# Korrigierte Spiele mit offiziellen Begegnungen
match_card("🇪🇺 UEFA Champions League", "Dienstag, 8. Sept., 21:00 Uhr", "🟢 Hoch", "Real Madrid vs. Inter Mailand", 
           "Taktisches Auftaktspiel im Bernabéu. Beide Teams verfügen über enorme Qualität, weshalb ein enges Duell zu erwarten ist.", 
           "Doppelte Chance 1X", "1.42")

match_card("🇪🇺 UEFA Champions League", "Mittwoch, 9. Sept., 18:45 Uhr", "🟢 Hoch", "FC Barcelona vs. Feyenoord Rotterdam", 
           "Barcelona geht als klarer Favorit in das Heimspiel, aber Feyenoord ist über Konter stets gefährlich.", 
           "Sieg Barcelona (1X2)", "1.55")

match_card("🇪🇺 UEFA Champions League", "Donnerstag, 10. Sept., 21:00 Uhr", "🟢 Stark", "FC Bayern München vs. FK Bodø/Glimt", 
           "Der deutsche Rekordmeister startet in der heimischen Allianz Arena und will direkt ein Ausrufezeichen setzen.", 
           "Über 2.5 Tore & Bayern Sieg", "1.78")

match_card("⚽ Bundesliga", "Samstag, 12. Sept., 15:30 Uhr", "🟢 Stark", "Borussia Dortmund vs. SC Paderborn 07", 
           "Dortmund ist im Signal Iduna Park klarer Favorit gegen Paderborn und will vor heimischer Kulisse dominant auftreten.", 
           "Sieg Dortmund (1X2)", "1.35")

# Footer
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 0.85rem;'>Hinweis: Glücksspiel kann süchtig machen. 18+ | Quotenangaben ohne Gewähr (Orientierung an Tipico).</p>", unsafe_allow_html=True)
