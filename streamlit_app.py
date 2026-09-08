<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Probetts - Deine Wettanalysen & Tipps</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent: #10b981;
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
            border-bottom: 1px solid #334155;
        }
        header h1 {
            margin: 0;
            color: var(--accent);
            font-size: 2rem;
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
        h2 {
            border-bottom: 2px solid var(--accent);
            padding-bottom: 0.5rem;
            margin-top: 2rem;
        }
        .match-card {
            background-color: var(--card-bg);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
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
        .odds {
            background-color: var(--accent);
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
        <h1>ProBetts Analysis</h1>
        <p>Ttägliche Sportanalysen, Statistiken & Wett-Tipps</p>
    </header>

    <div class="container">
        <h2>Aktuelle Analysen</h2>

        <!-- Beispiel Spiel 1 -->
        <div class="match-card">
            <div class="match-header">
                <span>Bundesliga • Heute, 20:30 Uhr</span>
                <span>Konfidenz: 🟢 Hoch</span>
            </div>
            <div class="match-teams">
                FC Bayern München vs. Borussia Dortmund
            </div>
            <div class="analysis-text">
                Beide Teams zeigen sich offensiv extrem stark, lassen defensiv jedoch regelmäßig Räume zu. Die letzten 4 direkten Duelle endeten jeweils mit über 3.5 Toren. Aufgrund der aktuellen Formkurve ist ein torreiches Spiel sehr wahrscheinlich.
            </div>
            <div class="prediction-box">
                <div>
                    Tipp: <span class="tip">Über 2.5 Tore & Beide treffen</span>
                </div>
                <div class="odds">Quote: 1.85</div>
            </div>
        </div>

        <!-- Beispiel Spiel 2 -->
        <div class="match-card">
            <div class="match-header">
                <span>Premier League • Morgen, 16:00 Uhr</span>
                <span>Konfidenz: 🟡 Mittel</span>
            </div>
            <div class="match-teams">
                Arsenal FC vs. Chelsea FC
            </div>
            <div class="analysis-text">
                Arsenal ist zu Hause eine Macht und hat die letzten 5 Heimspiele zu Null gewonnen. Chelsea plagt sich aktuell mit Verletzungssorgen im Mittelfeld. 
            </div>
            <div class="prediction-box">
                <div>
                    Tipp: <span class="tip">Sieg Arsenal (1X2)</span>
                </div>
                <div class="odds">Quote: 1.72</div>
            </div>
        </div>

    </div>

    <footer>
        <p>Hinweis: Glücksspiel kann süchtig machen. 18+ | Dies sind reine Analysen und keine finanzielle Beratung.</p>
    </footer>

</body>
</html>

