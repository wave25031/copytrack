"""
Top-traders (sinds 13 nov 2026): de traders die de BTC-daling van 12 nov
met grote shorts meepakten. Twee dingen:

1. Een APARTE paper-portfolio die alleen deze traders kopieert, zodat
   trader_25 (scalper) de plekken niet kan opvullen.
     data/top_portfolio.json, output/top_trades_log.csv
   Zelfde regels als de gewone portfolio: instap op marktprijs bij een
   nieuwe positie of omdraai, mee sluiten als de trader sluit/draait,
   stop 15% als vangnet.

2. Een entry-logboek om hun instapmomenten later te bestuderen:
     output/top_entries.csv   elke nieuwe positie, omdraai en bijkoop
     output/top_posities.md   wat ze NU open hebben (bijgewerkt elke run)
"""
import csv
import os

import paper_portfolio as pp

TOP_TRADERS = ["trader_09", "trader_03", "trader_04", "trader_24", "trader_08"]
TOP_PORTFOLIO_FILE = "data/top_portfolio.json"
TOP_TRADES_LOG = "output/top_trades_log.csv"
TOP_ENTRIES_LOG = "output/top_entries.csv"
TOP_POSITIES_MD = "output/top_posities.md"
TOP_MAX_OPEN = 15

ENTRY_ACTIES = ("NIEUWE_POSITIE", "RICHTING_OMGEDRAAID", "POSITIE_VERGROOT")


def _richting(sig):
    r = sig["richting"]
    return r.split("->")[-1] if "->" in r else r


def _log_entries(signals, prices, now_iso):
    rows = [s for s in signals if s["wallet_label"] in TOP_TRADERS and s["actie"] in ENTRY_ACTIES]
    if not rows:
        return
    nieuw = not os.path.exists(TOP_ENTRIES_LOG)
    os.makedirs("output", exist_ok=True)
    with open(TOP_ENTRIES_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nieuw:
            w.writerow(["tijd_utc", "trader", "coin", "actie", "richting", "gem_instap_trader",
                        "marktprijs_nu", "positie_usd", "btc_prijs_nu"])
        for s in rows:
            w.writerow([now_iso[:16].replace("T", " "), s["wallet_label"], s["coin"], s["actie"], _richting(s),
                        s.get("entry_prijs"), prices.get(s["coin"]), round(s.get("positie_waarde_usd") or 0),
                        prices.get("BTC")])


def _schrijf_posities(positions_per_label, prices, now_iso):
    regels = [f"# Open posities van de top-traders", "", f"Bijgewerkt: {now_iso[:16].replace('T', ' ')} UTC", "",
              "| Trader | Coin | Richting | Gem. instap | Prijs nu | Grootte | Resultaat |", "|---|---|---|---|---|---|---|"]
    for label in TOP_TRADERS:
        pos = positions_per_label.get(label)
        if pos is None:
            regels.append(f"| {label} | (niet opgehaald deze run) | | | | | |")
            continue
        for coin, p in sorted(pos.items(), key=lambda kv: -(kv[1].get("position_value_usd") or 0)):
            nu, inst = prices.get(coin), p.get("entry_px")
            richting = "LONG" if p["szi"] > 0 else "SHORT"
            res = ""
            if nu and inst:
                pct = (nu - inst) / inst * 100 * (1 if p["szi"] > 0 else -1)
                res = f"{pct:+.1f}%"
            regels.append(f"| {label} | {coin} | {richting} | {inst} | {nu} | ${(p.get('position_value_usd') or 0):,.0f} | {res} |")
    with open(TOP_POSITIES_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(regels) + "\n")


def run(all_signals, positions_per_label, prices, now_iso):
    """Geeft (geopend, gesloten, portfolio) terug voor de top-portfolio."""
    portfolio = pp.load_portfolio(TOP_PORTFOLIO_FILE)
    geopend, gesloten = [], []
    try:
        _log_entries(all_signals, prices, now_iso)
        _schrijf_posities(positions_per_label, prices, now_iso)
    except Exception as e:
        print(f"  [TOP] logboek bijwerken mislukt: {e}")
    if not prices:
        return geopend, gesloten, portfolio
    for sig in all_signals:
        if sig["wallet_label"] not in TOP_TRADERS or sig["actie"] not in ("NIEUWE_POSITIE", "RICHTING_OMGEDRAAID"):
            continue
        t = pp.open_paper_trade(portfolio, sig["coin"], _richting(sig), prices.get(sig["coin"]),
                                bron_wallet=sig["wallet_label"], now_iso=now_iso, max_open=TOP_MAX_OPEN)
        if t:
            geopend.append(t)
            print(f"  [TOP PAPER-TRADE GEOPEND] {t['coin']} {t['richting']} @ {t['instapprijs']} ({t['bron_wallet']})")
    gesloten = pp.close_when_trader_exits(portfolio, positions_per_label, prices, now_iso, log=TOP_TRADES_LOG)
    gesloten += pp.check_and_close_trades(portfolio, prices, now_iso, log=TOP_TRADES_LOG)
    pp.save_portfolio(portfolio, TOP_PORTFOLIO_FILE)
    return geopend, gesloten, portfolio
