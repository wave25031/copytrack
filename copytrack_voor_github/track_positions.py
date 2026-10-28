"""
COPY-TRADING PAPER-TRACKER (alleen lezen, geen echt geld, geen broker-koppeling)
=================================================================================

Wat dit doet:
  1. Haalt voor elk van de 12 wallets in wallets.py de huidige open posities
     op via Hyperliquid's publieke API (alleen lezen, geen account nodig).
  2. Vergelijkt dat met de vorige keer dat dit script draaide (data/last_state.json).
  3. Als een positie NIEUW is geopend, GESLOTEN is, of significant van
     grootte/richting is veranderd: dat wordt een "signaal", en komt in
     output/signals_log.csv te staan (en wordt op het scherm getoond).
  4. Slaat de nieuwe situatie op als "laatste stand" voor de volgende run.

Wat dit NIET doet:
  - Geen orders plaatsen, geen broker-koppeling, geen echt geld. Dit is
    puur een signalen-logboek dat je zelf met de hand kunt gebruiken om
    (paper) mee te handelen, met je EIGEN risicomanagement (stop-loss,
    position sizing) zoals we die ook in het keuringsapparaat gebruiken.
  - Geen garantie dat elk "signaal" een bewuste, doordachte trade van een
    mens is. Sommige van deze top-wallets doen zeer snel achter elkaar
    orders plaatsen/annuleren (market-making-gedrag) -- dat is precies
    waarom er een minimum-wijzigingsdrempel (config.POSITION_CHANGE_THRESHOLD_PCT)
    en een minimum-positiewaarde (config.MIN_POSITION_VALUE_USD) in zitten:
    om ruis eruit te filteren en alleen de echt betekenisvolle veranderingen
    te laten zien. Zie ook de opmerking in README.md over marketmakers.

Draaien (met de hand, of periodiek via Windows Taakplanner):
    python track_positions.py

Eerste keer? Draai eerst debug_dump.py om te checken dat alles goed werkt.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

import truststore
truststore.inject_into_ssl()

from wallets import WALLETS
from hyperliquid_client import get_positions, get_all_mids, polite_sleep
from config import (
    STATE_FILE, SIGNALS_LOG_CSV, POSITION_CHANGE_THRESHOLD_PCT,
    MIN_POSITION_VALUE_USD, SECONDS_BETWEEN_REQUESTS,
)
import paper_portfolio as pp
from notifier import send_email_notification

CSV_HEADER = [
    "timestamp_utc", "wallet_label", "wallet_address", "coin", "actie",
    "richting", "oude_grootte", "nieuwe_grootte", "entry_prijs",
    "positie_waarde_usd",
]


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"WAARSCHUWING: {STATE_FILE} kon niet gelezen worden, begin met lege staat.")
            return {}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def ensure_csv_header():
    os.makedirs(os.path.dirname(SIGNALS_LOG_CSV), exist_ok=True)
    if not os.path.exists(SIGNALS_LOG_CSV):
        with open(SIGNALS_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)


def log_signal(row: dict):
    with open(SIGNALS_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writerow(row)


def richting(szi: float) -> str:
    return "LONG" if szi > 0 else "SHORT"


def diff_positions(label: str, address: str, old_positions: dict, new_positions: dict, now_iso: str,
                    first_time_seen: bool = False):
    """
    Vergelijkt oude en nieuwe posities voor 1 wallet, print + logt signalen.

    first_time_seen=True betekent: we hebben deze wallet nog nooit eerder
    bekeken (dus er is geen "oude stand" om eerlijk mee te vergelijken).
    In dat geval loggen we GEEN signalen -- we leggen alleen de huidige
    situatie vast als nulmeting. Zonder deze check zou de allereerste run
    elke bestaande positie ten onrechte als "NIEUWE_POSITIE" melden, terwijl
    de trader die positie misschien al weken had voordat wij begonnen te kijken.
    """
    if first_time_seen:
        aantal = len(new_positions)
        print(f"  Eerste keer dat we {label} bekijken -- nulmeting vastgelegd "
              f"({aantal} open positie{'s' if aantal != 1 else ''}), geen signalen.")
        return []

    signals = []

    all_coins = set(old_positions) | set(new_positions)
    for coin in sorted(all_coins):
        old = old_positions.get(coin)
        new = new_positions.get(coin)

        if old is None and new is not None:
            # Nieuwe positie geopend
            if (new.get("position_value_usd") or 0) < MIN_POSITION_VALUE_USD:
                continue  # te klein, waarschijnlijk niet interessant
            signals.append({
                "wallet_label": label, "wallet_address": address, "coin": coin,
                "actie": "NIEUWE_POSITIE", "richting": richting(new["szi"]),
                "oude_grootte": None, "nieuwe_grootte": new["szi"],
                "entry_prijs": new["entry_px"], "positie_waarde_usd": new["position_value_usd"],
            })

        elif old is not None and new is None:
            # Positie volledig gesloten
            signals.append({
                "wallet_label": label, "wallet_address": address, "coin": coin,
                "actie": "POSITIE_GESLOTEN", "richting": richting(old["szi"]),
                "oude_grootte": old["szi"], "nieuwe_grootte": 0,
                "entry_prijs": old["entry_px"], "positie_waarde_usd": old["position_value_usd"],
            })

        elif old is not None and new is not None:
            old_szi, new_szi = old["szi"], new["szi"]
            flipped = (old_szi > 0 and new_szi < 0) or (old_szi < 0 and new_szi > 0)
            if flipped:
                signals.append({
                    "wallet_label": label, "wallet_address": address, "coin": coin,
                    "actie": "RICHTING_OMGEDRAAID", "richting": f"{richting(old_szi)}->{richting(new_szi)}",
                    "oude_grootte": old_szi, "nieuwe_grootte": new_szi,
                    "entry_prijs": new["entry_px"], "positie_waarde_usd": new["position_value_usd"],
                })
            else:
                rel_change = abs(new_szi - old_szi) / abs(old_szi) if old_szi else 0
                if rel_change >= POSITION_CHANGE_THRESHOLD_PCT:
                    actie = "POSITIE_VERGROOT" if abs(new_szi) > abs(old_szi) else "POSITIE_VERKLEIND"
                    signals.append({
                        "wallet_label": label, "wallet_address": address, "coin": coin,
                        "actie": actie, "richting": richting(new_szi),
                        "oude_grootte": old_szi, "nieuwe_grootte": new_szi,
                        "entry_prijs": new["entry_px"], "positie_waarde_usd": new["position_value_usd"],
                    })

    for sig in signals:
        sig["timestamp_utc"] = now_iso
        log_signal(sig)
        waarde = f"${sig['positie_waarde_usd']:.0f}" if sig["positie_waarde_usd"] else "?"
        print(f"  [SIGNAAL] {label} -- {coin_from_signal(sig)}: {sig['actie']} "
              f"({sig['richting']}), grootte {sig['oude_grootte']} -> {sig['nieuwe_grootte']}, "
              f"waarde {waarde}")

    return signals


def coin_from_signal(sig):
    return sig["coin"]


def _richting_voor_paper_trade(sig: dict) -> str:
    """Bij RICHTING_OMGEDRAAID staat er 'LONG->SHORT' -- wij willen alleen het nieuwe deel."""
    return sig["richting"].split("->")[-1]


def _format_prijs(prijs: float) -> str:
    """2 decimalen voor 'normale' prijzen, meer decimalen voor hele goedkope coins. Alleen om te LEZEN."""
    if prijs is None:
        return "?"
    if abs(prijs) >= 1:
        return f"${prijs:,.2f}"
    return f"${prijs:.6f}"


def _format_prijs_plain(prijs: float) -> str:
    """
    Kaal getal (geen $, geen duizendtal-punt/komma, gewoon punt als decimaal-teken) --
    veilig om direct over te typen in TradingView's prijsvelden. Reden: '$44,511.95'
    (Amerikaans, wat de code gebruikt) en '44.511,95' (Nederlands, wat je zelf zou
    schrijven) zien er bijna hetzelfde uit maar betekenen iets anders -- typ je zo'n
    getal met punten/komma's in een kaal invoerveld, dan leest TradingView het fout
    (bijv. 44511.95 werd 445195.00). Daarom hier altijd de kale versie: 44511.95.
    """
    if prijs is None:
        return "?"
    if abs(prijs) >= 1:
        return f"{prijs:.2f}"
    return f"{prijs:.6f}"


def _tradingview_link(coin: str) -> str:
    """
    Beste-poging link naar de chart van deze coin op TradingView (Binance-pair,
    dezelfde conventie als je paper-trading account al gebruikt). Werkt niet altijd
    perfect voor exotische/voorvoegsel-coins (bijv. kBONK, kSHIB) -- klopt de link
    niet, zoek de coin dan zelf even op in TradingView.
    """
    symbol = coin.upper().strip()
    return f"https://www.tradingview.com/symbols/{symbol}USDT/"


def _format_trade_voor_email(t: dict) -> str:
    """
    Zet 1 geopende paper-trade om in een duidelijke, direct te volgen instructie --
    zodat je 'm zelf snel en zonder gedoe kan overnemen op je eigen TradingView
    paper-trading account.
    """
    link = _tradingview_link(t["coin"])

    if t["richting"] == "LONG":
        actie = "GEKOCHT (LONG)"
        klik_instructie = "Klik op BUY (niet Sell)."
        richting_note = ""
    else:
        actie = "GESHORT (SHORT / verkocht)"
        klik_instructie = ("Klik op SELL (niet Buy) -- TradingView heeft geen aparte 'Short'-knop, "
                            "SELL = short.")
        richting_note = ("    (Bij een SHORT hoort de stop-loss BOVEN en de take-profit ONDER de "
                          "instapprijs -- dat klopt dus, ook al lijkt dat andersom.)\n")

    return (
        f"  {t['coin']}: {t['bron_wallet']} heeft {actie} op {_format_prijs(t['instapprijs'])}\n"
        f"    Zelf volgen op TradingView?\n"
        f"    1. Open de chart: {link}\n"
        f"    2. {klik_instructie}\n"
        f"{richting_note}"
        f"    3. Vul deze prijzen in (kaal overtypen, geen $ en geen duizendtal-teken):\n"
        f"         Entry (huidige marktprijs): {_format_prijs_plain(t['instapprijs'])}\n"
        f"         Stop-loss:                  {_format_prijs_plain(t['stop_price'])}\n"
        f"         Take-profit:                {_format_prijs_plain(t['tp_price'])}\n"
        f"    4. Zorg dat ZOWEL Take-profit ALS Stop-loss aangevinkt staan voordat je op Buy/Sell\n"
        f"       klikt -- anders staat de positie zo open zonder TP/SL. Staan ze er na het openen\n"
        f"       toch niet bij (kijk in het tabblad 'Positions')? Klik dan op het potlood-icoon op\n"
        f"       de regel van deze positie en vul ze daar alsnog in.\n"
        f"    Voorgestelde inzet (1% risico-regel): ${t['grootte_usd']:.2f}\n"
    )


REDEN_TEKST = {
    "stop_loss": "stop-loss geraakt",
    "take_profit": "take-profit geraakt",
    "trader_gesloten": "trader heeft gesloten, mee gesloten",
    "trader_gedraaid": "trader is van richting gedraaid, mee gesloten",
}


def main():
    ensure_csv_header()
    state = load_state()
    portfolio = pp.load_portfolio()
    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"=== Copy-tracker run: {now_iso} ===\n")

    try:
        current_prices = get_all_mids()
    except Exception as e:
        print(f"WAARSCHUWING: kon actuele marktprijzen niet ophalen ({e}). "
              f"Paper-portfolio wordt deze run overgeslagen, signalen worden nog wel gelogd.")
        current_prices = {}

    total_signals = 0
    all_signals = []
    positions_per_label = {}  # alleen wallets die deze run goed zijn opgehaald

    for wallet in WALLETS:
        label, address = wallet["label"], wallet["address"]
        print(f"Ophalen: {label} ({address[:8]}...)")
        try:
            new_positions = get_positions(address)
        except Exception as e:
            print(f"  FOUT bij ophalen van {label}: {e}. Sla deze over, staat blijft ongewijzigd.")
            continue

        first_time_seen = address not in state
        old_positions = state.get(address, {})
        signals = diff_positions(label, address, old_positions, new_positions, now_iso,
                                  first_time_seen=first_time_seen)
        total_signals += len(signals)
        all_signals.extend(signals)
        if not signals and not first_time_seen:
            print("  Geen veranderingen sinds vorige keer.")

        state[address] = new_positions
        positions_per_label[label] = new_positions
        polite_sleep(SECONDS_BETWEEN_REQUESTS)

    save_state(state)

    # --- Paper-portfolio: open nieuwe paper-trades voor koop-/omdraai-signalen ---
    opened_trades = []
    if current_prices:
        for sig in all_signals:
            if sig["actie"] not in ("NIEUWE_POSITIE", "RICHTING_OMGEDRAAID"):
                continue
            coin = sig["coin"]
            price = current_prices.get(coin)
            trade = pp.open_paper_trade(
                portfolio, coin, _richting_voor_paper_trade(sig), price,
                bron_wallet=sig["wallet_label"], now_iso=now_iso,
            )
            if trade:
                opened_trades.append(trade)
                print(f"  [PAPER-TRADE GEOPEND] {coin} {trade['richting']} @ {trade['instapprijs']:.4f} "
                      f"(bron: {sig['wallet_label']}, grootte ${trade['grootte_usd']:.2f}, "
                      f"stop {trade['stop_price']:.4f}, tp {trade['tp_price']:.4f})")

        # --- Eerst: meesluiten als de gevolgde trader zelf sluit of draait ---
        closed_trades = pp.close_when_trader_exits(portfolio, positions_per_label, current_prices, now_iso)
        # --- Daarna: stop-loss (vangnet) en eventueel take-profit ---
        closed_trades += pp.check_and_close_trades(portfolio, current_prices, now_iso)
        for ct in closed_trades:
            print(f"  [PAPER-TRADE GESLOTEN] {ct['coin']} {ct['richting']} -- {ct['reden_uitstap']}, "
                  f"resultaat {ct['resultaat_pct']:.2f}% (${ct['resultaat_usd']:.2f}), "
                  f"kapitaal nu ${ct['kapitaal_na_trade']:.2f}")
    else:
        closed_trades = []

    pp.save_portfolio(portfolio)

    print(f"\n=== Klaar. {total_signals} signa{'al' if total_signals == 1 else 'len'} deze run, "
          f"{len(opened_trades)} paper-trade(s) geopend, {len(closed_trades)} gesloten. "
          f"Kapitaal: ${portfolio['capital']:.2f}, {len(portfolio['open_trades'])} open. "
          f"Zie {SIGNALS_LOG_CSV} en {pp.PAPER_TRADES_LOG_CSV}. ===")

    # --- E-mail: bij ELK signaal van een van de 27 wallets, niet alleen als wij
    # zelf een paper-trade openen -- anders mis je meldingen van wallets zodra
    # de paper-portfolio vol zit (MAX_OPEN_PAPER_TRADES) of er al een positie
    # openstaat op die coin. Sluiten van een eigen paper-trade blijft ook altijd
    # een reden om te mailen.
    meldenswaardige_signalen = [s for s in all_signals if s["actie"] in ("NIEUWE_POSITIE", "RICHTING_OMGEDRAAID")]
    aanpassingen = [s for s in all_signals if s["actie"] in ("POSITIE_VERGROOT", "POSITIE_VERKLEIND", "POSITIE_GESLOTEN")]
    if opened_trades or closed_trades or meldenswaardige_signalen or aanpassingen:
        regels = [f"Copy-tracker update -- {now_iso}", ""]

        if opened_trades:
            regels.append("=== NIEUWE SIGNALEN OM TE VOLGEN ===")
            regels.append("")
            for t in opened_trades:
                regels.append(_format_trade_voor_email(t))

        if closed_trades:
            regels.append("=== AFGESLOTEN (sluit deze zelf ook af, als je 'm volgde) ===")
            regels.append("")
            for ct in closed_trades:
                resultaat_woord = "WINST" if ct["resultaat_usd"] >= 0 else "VERLIES"
                regels.append(
                    f"  {ct['coin']} {ct['richting']} (bron: {ct['bron_wallet']}): "
                    f"{resultaat_woord}, {REDEN_TEKST.get(ct['reden_uitstap'], ct['reden_uitstap'])} op {_format_prijs(ct['uitstapprijs'])} "
                    f"({ct['resultaat_pct']:.2f}%, ${ct['resultaat_usd']:.2f})\n"
                )

        # Overige, kleinere aanpassingen (posities vergroot/verkleind), en signalen
        # waar we zelf geen paper-trade voor openden -- alleen ter info onderaan,
        # niet iets om per se zelf op te volgen. Reden erbij: vol (cap bereikt) of
        # al een positie open op die coin, zodat je begrijpt waarom er geen paper-
        # trade bij zit terwijl de wallet wel duidelijk iets deed.
        overige_signalen = [s for s in meldenswaardige_signalen
                             if not any(t["coin"] == s["coin"] and t["bron_wallet"] == s["wallet_label"]
                                        for t in opened_trades)]
        if overige_signalen:
            portfolio_vol = len(portfolio["open_trades"]) >= pp.MAX_OPEN_PAPER_TRADES
            regels.append("--- ook gezien, maar geen nieuwe paper-trade voor geopend ---")
            for s in overige_signalen:
                if s["actie"] not in ("NIEUWE_POSITIE", "RICHTING_OMGEDRAAID"):
                    continue
                if pp.has_open_trade(portfolio, s["coin"]):
                    reden = "al een positie open op deze coin"
                elif portfolio_vol:
                    reden = f"paper-portfolio zit vol ({pp.MAX_OPEN_PAPER_TRADES} open)"
                else:
                    reden = "geen actuele prijs beschikbaar"
                regels.append(f"  - {s['wallet_label']}: {s['coin']} {s['actie']} ({s['richting']}) -- {reden}")
            regels.append("")

        if aanpassingen:
            woord = {"POSITIE_VERGROOT": "VERGROOT", "POSITIE_VERKLEIND": "VERKLEIND",
                     "POSITIE_GESLOTEN": "GESLOTEN door trader"}
            regels.append("--- aanpassingen van de traders ---")
            for s in aanpassingen:
                oud, nieuw = abs(s["oude_grootte"] or 0), abs(s["nieuwe_grootte"] or 0)
                if s["actie"] == "POSITIE_GESLOTEN":
                    detail = f"was ${(s['positie_waarde_usd'] or 0):,.0f}"
                else:
                    pct = (nieuw - oud) / oud * 100 if oud else 0
                    detail = f"{pct:+.0f}% in grootte, nu ${(s['positie_waarde_usd'] or 0):,.0f}"
                eigen = " (jij volgt deze trade op paper)" if any(t["coin"] == s["coin"] and t.get("bron_wallet") == s["wallet_label"]
                                                         for t in portfolio["open_trades"]) else ""
                regels.append(f"  - {s['wallet_label']}: {s['coin']} {s['richting']} {woord[s['actie']]}, {detail}{eigen}")
            regels.append("")

        regels.append(f"Portfolio-kapitaal nu: ${portfolio['capital']:.2f}")
        regels.append(f"Open paper-trades: {len(portfolio['open_trades'])}")

        verstuurd = send_email_notification(
            subject=f"Copy-tracker: {len(opened_trades)} nieuw signaal om te volgen, "
                    f"{len(closed_trades)} afgesloten, {len(meldenswaardige_signalen)} nieuw/gedraaid, "
                    f"{len(aanpassingen)} aanpassingen",
            body="\n".join(regels),
        )
        if not verstuurd:
            # Markeerbestand: de workflow maakt de run hierdoor ROOD (na het opslaan
            # van de data), zodat een mislukte mail niet meer stil verdwijnt.
            with open("mail_mislukt.txt", "w", encoding="utf-8") as f:
                f.write(now_iso)


if __name__ == "__main__":
    main()
