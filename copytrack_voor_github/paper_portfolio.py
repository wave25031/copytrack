"""
De eigen paper-portfolio: doet wat TradingView hier niet automatisch voor ons
kan doen. Zodra er een koop- (of verkoop-)signaal binnenkomt van een van de
gevolgde wallets, "opent" dit een virtuele positie -- met JOUW eigen
risicomanagement (stop-loss, take-profit, position sizing), niet met wat de
gevolgde trader daarna doet. Geen TradingView nodig, geen broker, geen echt
geld: gewoon boekhouding in een JSON-/CSV-bestand.

Regels (bewust simpel gehouden):
  - Hooguit 1 open paper-trade per coin tegelijk. Geeft een 2e wallet een
    signaal op een coin waar we al in zitten, dan wordt dat genegeerd voor
    de portfolio (staat wel gewoon in signals_log.csv).
  - Hooguit MAX_OPEN_PAPER_TRADES open tegelijk, zodat 1 wallet met heel veel
    signalen in 1 keer (zoals we bij trader_12 zagen) niet het hele kapitaal
    in piepkleine plakjes knipt.
  - Instapprijs = de actuele marktprijs op het moment dat WIJ het signaal
    zien (via get_all_mids), niet de -- voor ons toch niet exact te
    achterhalen -- instapprijs van de trader zelf.
  - Uitstap (sinds 28 okt 2026): zodra de gevolgde trader zelf sluit of van
    richting draait, sluit onze paper-trade mee op de actuele prijs. De stop
    van 15% blijft als vangnet. Het vaste winstdoel staat standaard uit
    (PAPER_TAKE_PROFIT_ACTIEF in config.py).
"""

import json
import os
from datetime import datetime, timezone

from config import (
    PAPER_PORTFOLIO_STATE_FILE, PAPER_TRADES_LOG_CSV, PAPER_START_CAPITAL,
    PAPER_STOP_LOSS_PCT, PAPER_TAKE_PROFIT_R, PAPER_RISK_PCT_PER_TRADE,
    MAX_OPEN_PAPER_TRADES, PAPER_TAKE_PROFIT_ACTIEF,
)

CSV_HEADER = [
    "geopend_op", "gesloten_op", "coin", "richting", "bron_wallet",
    "instapprijs", "uitstapprijs", "reden_uitstap", "grootte_usd",
    "resultaat_pct", "resultaat_usd", "kapitaal_na_trade",
]


def _default_portfolio():
    return {"capital": PAPER_START_CAPITAL, "open_trades": []}


def load_portfolio() -> dict:
    if not os.path.exists(PAPER_PORTFOLIO_STATE_FILE):
        return _default_portfolio()
    with open(PAPER_PORTFOLIO_STATE_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            data.setdefault("capital", PAPER_START_CAPITAL)
            data.setdefault("open_trades", [])
            return data
        except json.JSONDecodeError:
            return _default_portfolio()


def save_portfolio(portfolio: dict):
    os.makedirs(os.path.dirname(PAPER_PORTFOLIO_STATE_FILE), exist_ok=True)
    with open(PAPER_PORTFOLIO_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)


def _ensure_csv_header():
    os.makedirs(os.path.dirname(PAPER_TRADES_LOG_CSV), exist_ok=True)
    if not os.path.exists(PAPER_TRADES_LOG_CSV):
        with open(PAPER_TRADES_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            import csv
            csv.writer(f).writerow(CSV_HEADER)


def _log_closed_trade(row: dict):
    import csv
    _ensure_csv_header()
    with open(PAPER_TRADES_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADER).writerow(row)


def has_open_trade(portfolio: dict, coin: str) -> bool:
    return any(t["coin"] == coin for t in portfolio["open_trades"])


def open_paper_trade(portfolio: dict, coin: str, richting: str, current_price: float,
                      bron_wallet: str, now_iso: str) -> dict | None:
    """
    Opent een paper-trade als dat kan (niet al open op deze coin, portfolio
    niet vol, prijs bekend). Geeft de geopende trade terug, of None als er
    niks geopend is (dan blijft dat stil -- de aanroeper kan zelf beslissen
    of/hoe dat gemeld wordt).
    """
    if current_price is None or current_price <= 0:
        return None
    if has_open_trade(portfolio, coin):
        return None
    if len(portfolio["open_trades"]) >= MAX_OPEN_PAPER_TRADES:
        return None

    position_fraction = min(1.0, PAPER_RISK_PCT_PER_TRADE / PAPER_STOP_LOSS_PCT) if PAPER_STOP_LOSS_PCT else 1.0
    grootte_usd = portfolio["capital"] * position_fraction

    if richting == "LONG":
        stop_price = current_price * (1 - PAPER_STOP_LOSS_PCT)
        tp_price = current_price * (1 + PAPER_STOP_LOSS_PCT * PAPER_TAKE_PROFIT_R)
    else:  # SHORT
        stop_price = current_price * (1 + PAPER_STOP_LOSS_PCT)
        tp_price = current_price * (1 - PAPER_STOP_LOSS_PCT * PAPER_TAKE_PROFIT_R)

    trade = {
        "coin": coin,
        "richting": richting,
        "bron_wallet": bron_wallet,
        "instapprijs": current_price,
        "stop_price": stop_price,
        "tp_price": tp_price,
        "grootte_usd": grootte_usd,
        "geopend_op": now_iso,
    }
    portfolio["open_trades"].append(trade)
    return trade


def _close(portfolio: dict, trade: dict, exit_price: float, reden: str, now_iso: str) -> dict:
    if trade["richting"] == "LONG":
        resultaat_pct = (exit_price - trade["instapprijs"]) / trade["instapprijs"] * 100
    else:
        resultaat_pct = (trade["instapprijs"] - exit_price) / trade["instapprijs"] * 100
    resultaat_usd = trade["grootte_usd"] * (resultaat_pct / 100)
    portfolio["capital"] += resultaat_usd
    closed_trade = {
        "geopend_op": trade["geopend_op"], "gesloten_op": now_iso,
        "coin": trade["coin"], "richting": trade["richting"],
        "bron_wallet": trade["bron_wallet"], "instapprijs": trade["instapprijs"],
        "uitstapprijs": exit_price, "reden_uitstap": reden,
        "grootte_usd": trade["grootte_usd"], "resultaat_pct": resultaat_pct,
        "resultaat_usd": resultaat_usd, "kapitaal_na_trade": portfolio["capital"],
    }
    _log_closed_trade(closed_trade)
    return closed_trade


def close_when_trader_exits(portfolio: dict, positions_per_label: dict, current_prices: dict,
                            now_iso: str) -> list:
    """
    Sluit paper-trades waarvan de bron-trader de positie niet meer heeft (gesloten)
    of nu de andere kant op zit (gedraaid). positions_per_label bevat ALLEEN
    wallets die deze run goed zijn opgehaald; bij een ophaalfout sluiten we niks.
    """
    still_open, closed = [], []
    for trade in portfolio["open_trades"]:
        posities = positions_per_label.get(trade["bron_wallet"])
        price = current_prices.get(trade["coin"])
        if posities is None or price is None:
            still_open.append(trade)
            continue
        pos = posities.get(trade["coin"])
        if pos is None:
            reden = "trader_gesloten"
        else:
            richting_nu = "LONG" if float(pos["szi"]) > 0 else "SHORT"
            reden = None if richting_nu == trade["richting"] else "trader_gedraaid"
        if reden:
            closed.append(_close(portfolio, trade, price, reden, now_iso))
        else:
            still_open.append(trade)
    portfolio["open_trades"] = still_open
    return closed


def check_and_close_trades(portfolio: dict, current_prices: dict, now_iso: str) -> list:
    """
    Loopt alle open paper-trades langs en sluit ze af als de actuele prijs
    de stop-loss of take-profit geraakt heeft. Geeft de lijst van GESLOTEN
    trades terug (met resultaat), voor logging/melding.
    """
    still_open = []
    closed = []

    for trade in portfolio["open_trades"]:
        price = current_prices.get(trade["coin"])
        if price is None:
            still_open.append(trade)  # geen actuele prijs beschikbaar, laat 'm openstaan
            continue

        hit_stop = hit_tp = False
        if trade["richting"] == "LONG":
            hit_stop = price <= trade["stop_price"]
            hit_tp = PAPER_TAKE_PROFIT_ACTIEF and price >= trade["tp_price"]
        else:  # SHORT
            hit_stop = price >= trade["stop_price"]
            hit_tp = PAPER_TAKE_PROFIT_ACTIEF and price <= trade["tp_price"]

        if hit_stop or hit_tp:
            # Bij allebei in dezelfde ronde geraakt (zeer onwaarschijnlijk met
            # periodiek pollen, maar toch): stop-loss telt als eerst geraakt,
            # zelfde voorzichtige aanname als in het keuringsapparaat.
            exit_price = trade["stop_price"] if hit_stop else trade["tp_price"]
            reden = "stop_loss" if hit_stop else "take_profit"

            closed.append(_close(portfolio, trade, exit_price, reden, now_iso))
        else:
            still_open.append(trade)

    portfolio["open_trades"] = still_open
    return closed
