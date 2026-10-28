# Copytrack -- paper-trading signalen van 12 succesvolle Hyperliquid-traders

**Dit is 100% paper trading.** Dit script plaatst geen orders, koppelt met
geen enkele broker, en raakt geen echt geld aan. Het leest alleen publieke,
on-chain positie-informatie van 12 wallet-adressen uit, en meldt je wanneer
een van die traders een positie opent, sluit, sterk vergroot/verkleint, of
van richting omdraait. Wat je daarmee doet (wel/niet als paper-trade volgen,
met welke stop-loss/position-sizing) is helemaal aan jou.

## Hoe de 12 wallets gekozen zijn

Elke wallet stond zowel in de top-100 van de 30-dagen-ranglijst als in de
top-100 van de all-time-ranglijst van Hyperliquid (beide gesorteerd op
winst/PNL). Dat is het filter tegen "toevallig 1 goede week gehad" -- zie
`wallets.py` voor de lijst en de exacte adressen.

**Belangrijke kanttekening, eerlijkheidshalve:** een aantal van deze
top-wallets plaatsen en annuleren orders vele keren per seconde (dat zag ik
toen ik de transactiegeschiedenis van een van de wallets bekeek). Dat is
typisch market-maker-gedrag, geen bewuste "ik denk dat dit omhoog gaat"-
beslissing van een mens. Dit script filtert daarom kleine positie-
aanpassingen eruit (zie `POSITION_CHANGE_THRESHOLD_PCT` in `config.py`),
maar een deel van de "signalen" kan alsnog van geautomatiseerde strategieën
komen in plaats van menselijke discretionaire trades. Neem het dus niet
klakkeloos over -- gebruik het als extra informatie, niet als garantie.

## Waarom geen TradingView-koppeling?

Dat was de eerste vraag: kan dit automatisch een positie in TradingView
openen? Nee -- TradingView heeft geen publieke koppeling waarmee een extern
script een (paper-)positie in hun scherm kan zetten. Dat kan alleen met de
muis, of via een koppeling met een **echte** broker (met echt geld), en dat
laatste willen we niet. In plaats daarvan houdt dit script zélf een paper-
portfolio bij (zie hieronder) -- functioneel hetzelfde resultaat, zonder een
platform nodig te hebben dat het niet ondersteunt.

## De automatische paper-portfolio

Zodra er een `NIEUWE_POSITIE`- of `RICHTING_OMGEDRAAID`-signaal binnenkomt,
"opent" het script automatisch een virtuele positie -- met JOUW eigen
risicomanagement, niet dat van de trader die je volgt:

- Instapprijs = de actuele marktprijs op het moment dat wij het signaal zien.
- Stop-loss op 15%, take-profit op 2x die afstand (2:1 reward:risk) -- exact
  dezelfde regels als in het keuringsapparaat.
- Position sizing: 1% van het (virtuele) kapitaal op het spel bij een
  geraakte stop-loss, niet je hele kapitaal in 1 trade.
- We stappen uit op ONZE eigen stop-loss/take-profit, niet wanneer de
  gevolgde trader zelf uitstapt -- "het maakt niet uit al gaat de koers van
  hen toch verder", zoals je zelf al aangaf.
- Max. 1 open paper-trade per coin, max. 15 tegelijk (voorkomt dat 1 wallet
  met heel veel signalen tegelijk het kapitaal in piepkleine plakjes knipt).

Alles is aan te passen in `config.py` (`PAPER_START_CAPITAL`,
`PAPER_STOP_LOSS_PCT`, `PAPER_TAKE_PROFIT_R`, `PAPER_RISK_PCT_PER_TRADE`,
`MAX_OPEN_PAPER_TRADES`).

## E-mail-meldingen instellen

Je krijgt een e-mail zodra er een nieuw signaal is, een paper-trade wordt
geopend, of een paper-trade wordt gesloten (winst of verlies). Instellen:

1. Ga naar je Google-account -> Beveiliging -> zorg dat **2-stapsverificatie**
   aan staat (verplicht voor de volgende stap).
2. Ga naar Beveiliging -> App-wachtwoorden (of zoek naar "App-wachtwoorden"
   in de Google-accountinstellingen).
3. Maak een nieuw app-wachtwoord aan (naam maakt niet uit, bijv. "copytrack").
   Je krijgt een code van 16 tekens.
4. Open `config.py` **op je eigen pc** (niet delen met mij of in een chat!)
   en vul die code in bij `EMAIL_APP_PASSWORD = ""`.

Zonder deze stap blijft alles verder gewoon werken (signalen loggen,
paper-portfolio bijhouden) -- je krijgt dan alleen geen e-mail, en het
script laat in het scherm zien dat `EMAIL_APP_PASSWORD` nog leeg is.

## Bestanden

- `wallets.py` -- de 12 gevolgde wallets (was 13, trader_12 is eruit gehaald omdat hij tientallen coins tegelijk shortte -- typisch bot-gedrag).
- `config.py` -- instellingen (drempel voor "significante" wijziging, paper-portfolio-regels, e-mail-instellingen).
- `hyperliquid_client.py` -- praat met Hyperliquid's publieke API (alleen lezen).
- `paper_portfolio.py` -- houdt de virtuele paper-portfolio bij (zie hierboven).
- `notifier.py` -- verstuurt de e-mail-melding.
- `debug_dump.py` -- **draai dit als eerste**, 1 keer, om te checken dat alles werkt.
- `track_positions.py` -- het hoofdscript. Elke keer dat je dit draait,
  vergelijkt het de huidige posities met de vorige keer, opent/sluit
  paper-trades, en stuurt een e-mail als er iets te melden is.
- `data/last_state.json` -- (automatisch) laatst bekende posities per wallet.
- `data/paper_portfolio.json` -- (automatisch) huidig kapitaal + open paper-trades.
- `output/signals_log.csv` -- (automatisch) logboek van alle gedetecteerde signalen.
- `output/paper_trades_log.csv` -- (automatisch) logboek van alle GESLOTEN paper-trades, met resultaat.

## Installeren (1x)

```
pip install requests truststore
```

## Gebruiken

Eerste keer:
```
python debug_dump.py
```
Controleer dat de output er logisch uitziet (vergelijk met wat je op
https://app.hyperliquid.xyz/explorer/address/<adres> ziet voor die wallet).

Daarna, elke keer dat je wil checken of er iets veranderd is:
```
python track_positions.py
```

## Automatisch periodiek laten draaien (optioneel)

Dit script is met opzet **niet** een oneindige loop die non-stop moet
blijven draaien -- dat is kwetsbaarder (crash = alles stopt) en dwingt je om
een terminal-venster open te houden. In plaats daarvan kun je Windows
Taakplanner gebruiken om het bijvoorbeeld elke 15-30 minuten automatisch te
laten draaien:

1. Open "Taakplanner" (Task Scheduler) in Windows.
2. Maak een nieuwe taak aan.
3. Trigger: "Herhaal taak elke 15 minuten" (of wat je zelf prettig vindt --
   hou er rekening mee dat je bij hele korte intervallen ook meer "ruis"-
   signalen kunt krijgen).
4. Actie: programma starten -> `python.exe`, argumenten:
   `track_positions.py`, starten in: de map waar deze bestanden staan.
5. Elke keer dat de taak draait, wordt `output/signals_log.csv` verder
   aangevuld -- die kun je gewoon openen in Excel om te zien wat er is
   gebeurd, ook als je even niet hebt gekeken.

## Wat een regel in signals_log.csv betekent

| Kolom | Betekenis |
|---|---|
| `actie` | `NIEUWE_POSITIE`, `POSITIE_GESLOTEN`, `RICHTING_OMGEDRAAID`, `POSITIE_VERGROOT` of `POSITIE_VERKLEIND` |
| `richting` | `LONG` of `SHORT` (bij een omdraaiing: `LONG->SHORT` of andersom) |
| `oude_grootte` / `nieuwe_grootte` | positiegrootte in de coin zelf (bijv. 0.5 BTC) |
| `entry_prijs` | de instapprijs die Hyperliquid voor deze positie noteert |
| `positie_waarde_usd` | huidige waarde van de positie in dollar |

## Wat een regel in paper_trades_log.csv betekent

| Kolom | Betekenis |
|---|---|
| `bron_wallet` | welke van de 12 wallets dit signaal gaf |
| `instapprijs` / `uitstapprijs` | onze eigen (virtuele) prijzen, niet die van de bron-trader |
| `reden_uitstap` | `stop_loss` of `take_profit` |
| `grootte_usd` | hoeveel van het paper-kapitaal in deze trade zat |
| `resultaat_pct` / `resultaat_usd` | winst of verlies op deze ene trade |
| `kapitaal_na_trade` | totale paper-kapitaal na afsluiten van deze trade |
