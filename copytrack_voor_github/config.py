"""
Instellingen voor de copy-trading paper-tracker.
"""

import os

# Hyperliquid's publieke, permissionless API -- geen key, geen login nodig.
HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

# Alleen positie-veranderingen groter dan dit percentage tellen als een
# "signaal". Kleinere aanpassingen zijn vaak ruis: bijvoorbeeld market-makers
# die constant hun order een beetje bijstellen, niet een echte nieuwe
# richting-keuze. 0.15 = pas melden bij een verandering van >15%.
POSITION_CHANGE_THRESHOLD_PCT = 0.15

# Posities kleiner dan dit (in USD) negeren we volledig -- "dust", geen
# serieuze trade.
MIN_POSITION_VALUE_USD = 500.0

# Waar we de laatste bekende posities per wallet bewaren tussen runs, en waar
# het signalen-logboek naartoe geschreven wordt.
STATE_FILE = "data/last_state.json"
SIGNALS_LOG_CSV = "output/signals_log.csv"

# Hoeveel seconden wachten tussen requests naar verschillende wallets (om de
# publieke API niet te overvragen -- netjes gedrag, geen rate-limit-gedoe).
SECONDS_BETWEEN_REQUESTS = 1.0

# ---- PAPER-PORTFOLIO (automatisch een paper-positie "openen" als er een ----
# ---- koop-signaal binnenkomt)                                           ----
# Zelfde filosofie als het keuringsapparaat: WIJ bepalen onze eigen stop-loss
# en take-profit, niet de trader die we volgen. "Het maakt niet uit al gaat
# de koers van de gevolgde trader toch verder" -- wij stappen uit op ONZE
# eigen regel (2:1 reward:risk), niet op wat zij daarna doen.
PAPER_START_CAPITAL = 1000.0       # startkapitaal van de paper-portfolio
PAPER_STOP_LOSS_PCT = 0.15         # 15% verlies = automatisch eruit
PAPER_TAKE_PROFIT_R = 2.0          # alleen gebruikt als PAPER_TAKE_PROFIT_ACTIEF = True
# Uitstap (28 okt 2026): de paper-trade sluit mee zodra de gevolgde trader zelf
# sluit of van richting draait. De stop van 15% blijft als vangnet. Een vast
# winstdoel staat uit, zodat winst doorloopt tot de trader eruit gaat.
PAPER_TAKE_PROFIT_ACTIEF = False
PAPER_RISK_PCT_PER_TRADE = 0.01    # riskeer 1% van kapitaal per paper-trade

# Niet meer dan dit aantal gelijktijdig open paper-trades -- voorkomt dat 1
# wallet met heel veel gelijktijdige signalen (zoals we bij trader_12 zagen)
# het hele kapitaal in tientallen piepkleine plakjes knipt.
MAX_OPEN_PAPER_TRADES = 15

# Per coin maar 1 open paper-trade tegelijk, ongeacht hoeveel van de 12
# wallets een signaal geven op diezelfde coin -- de eerste telt, de rest is
# alleen informatief.
PAPER_PORTFOLIO_STATE_FILE = "data/paper_portfolio.json"
PAPER_TRADES_LOG_CSV = "output/paper_trades_log.csv"

# ---- E-MAIL-MELDINGEN ----
# Lokaal op je eigen pc: vul EMAIL_APP_PASSWORD hieronder zelf in -- deel
# deze NOOIT met mij of in een chatgesprek. Dit is geen normaal Gmail-
# wachtwoord maar een "app-wachtwoord": Google Account -> Beveiliging ->
# 2-stapsverificatie (moet aan staan) -> App-wachtwoorden -> nieuwe aanmaken.
# Zie README.md voor de stap-voor-stap-uitleg.
#
# Op GitHub Actions: laat dit op "" staan. Het wachtwoord komt dan automatisch
# uit de GitHub Secret die je zelf in GitHub's eigen scherm invult (Settings ->
# Secrets and variables -> Actions -> New repository secret, naam
# EMAIL_APP_PASSWORD). Zo staat het wachtwoord nooit in dit bestand of in de
# chat, alleen versleuteld bij GitHub zelf.
EMAIL_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# Je e-mailadres staat niet in de code. Op GitHub komt het uit de secret
# EMAIL_ADRES. Lokaal op je pc: zet het hieronder tussen de lege aanhalingstekens.
EMAIL_FROM = os.environ.get("EMAIL_ADRES", "")
EMAIL_TO = EMAIL_FROM
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")
