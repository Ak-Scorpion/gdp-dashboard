<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProBetts - Deine Wettanalysen & Tipps</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent: #10b981;
            --tipico-red: #ea1d2c;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 0;
        }
        header {
            background-color: var(--card-bg);
            padding: 2rem;
            text-align: center;
            border-bottom: 2px solid var(--tipico-red);
        }
        header h1 {
            margin: 0;
            color: var(--text-main);
            font-size: 2rem;
        }
        header h1 span {
            color: var(--tipico-red);
        }
        header p {
            color: var(--text-muted);
            margin-top: 0.5rem;
        }
        .container {
            max-width: 900px;
            margin: 2rem auto;
            padding: 0 1rem;
        }
        .league-title {
            color: var(--accent);
            border-bottom: 2px solid #334155;
            padding-bottom: 0.5rem;
            margin-top: 2.5rem;
            font-size: 1.4rem;
        }
        .match-card {
            background-color: var(--card-bg);
            border-radius: 8px;
            padding: 1.5rem;
            margin-top: 1rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .match-header {
            display: flex;
            justify-content: space-between;
            color: var(--text-muted);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .match-teams {
            font-size: 1.25rem;
            font-weight: bold;
        }
        .prediction-box {
            background-color: #0f172a;
            padding: 1rem;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
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
            background-color: var(--text-main);
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
        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid #334155;
            margin-top: 4rem;
        }
    </style>
</head>
<body>

    <header>
        <h1>Pro<span>Betts</span> Analysis</h1>
        <p>Top-Quoten & Analysen für Champions League, Europa League, Conference League & Top-Ligen</p>
    </header>

    <div class="container">

        <!-- UEFA Champions League -->
        <div class="league-title">🇪🇺 UEFA Champions League</div>
        
        <div class="match-card">
            <div class="match-header">
                <span>Morgen, 21:00 Uhr</span>
                <span>Konfidenz: 🟢 Hoch</span>
            </div>
            <div class="match-teams">Real Madrid vs. Manchester City</div>
            <div class="analysis-text">Taktisches Spitzenspiel im Bernabéu. Beide Mannschaften verfügen über absolute Weltklasse-Offensiven. Ein torreicher Schlagabtausch ist vorprogrammiert.</div>
            <div class="prediction-box">
                <div>Tipp: <span class="tip">Beide Teams treffen (BTTS)</span></div>
                <div class="odds-container">
                    <span class="odds-badge">Tipico</span>
                    <div class="odds">1.67</div>
                </div>
            </div>
        </div>

        <!-- UEFA Europa League -->
        <div class="league-title">🇪🇺 UEFA Europa League</div>
        
        <div class="match-card">
            <div class="match-header">
                <span>Donnerstag, 18:45 Uhr</span>
                <span>Konfidenz: 🟡 Mittel</span>
            </div>
            <div class="match-teams">AS Roma vs. Bayer Leverkusen</div>
            <div class="analysis-text">Leverkusen agiert auswärts extrem kompakt, während Rom im eigenen Stadion enorm druckvoll auftritt. Ein enges Spiel, in dem Details entscheiden.</div>
            <div class="prediction-box">
                <div>Tipp: <span class="tip">Unentschieden (X)</span></div>
                <div class="odds-container">
                    <span class="odds-badge">Tipico</span>
                    <div class="odds">3.40</div>
                </div>
            </div>
        </div>

        <!-- UEFA Conference League -->
        <div class="league-title">🇪🇺 UEFA Conference League</div>
        
        <div class="match-card">
            <div class="match-header">
                <span>Donnerstag, 21:00 Uhr</span>
                <span>Konfidenz: 🟢 Hoch</span>
            </div>
            <div class="match-teams">ACF Fiorentina vs. Aston Villa</div>
            <div class="analysis-text">Aston Villa geht als Favorit in dieses Auswärtsspiel, aber Florenz ist international heimstark. Wir erwarten Tore auf beiden Seiten.</div>
            <div class="prediction-box">
                <div>Tipp: <span class="tip">Über 2.5 Tore</span></div>
                <div class="odds-container">
                    <span class="odds-badge">Tipico</span>
                    <div class="odds">1.85</div>
                </div>
            </div>
        </div>

        <!-- Top Ligen -->
        <div class="league-title">⚽ Bundesliga & Premier League</div>
        
        <div class="match-card">
            <div class="match-header">
                <span>Samstag, 15:30 Uhr</span>
                <span>Konfidenz: 🟢 Stark</span>
            </div>
            <div class="match-teams">Borussia Dortmund vs. RB Leipzig</div>
            <div class="analysis-text">Dortmund mit Heimvorteil und starker Kulisse im Rücken. Leipzig jedoch mit schnellem Umschaltspiel brandgefährlich.</div>
            <div class="prediction-box">
                <div>Tipp: <span class="tip">Sieg Dortmund (1X2)</span></div>
                <div class="odds-container">
                    <span class="odds-badge">Tipico</span>
                    <div class="odds">2.10</div>
                </div>
            </div>
        </div>

    </div>

    <footer>
        <p>Hinweis: Glücksspiel kann süchtig machen. 18+ | Quotenangaben ohne Gewähr (Orientierung an Tipico).</p>
    </footer>

</body>
</html>
