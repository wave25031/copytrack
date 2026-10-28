"""
Haalt de echte trade-geschiedenis van de gevolgde wallets op bij Hyperliquid
(openbare on-chain data) en maakt er een rapport van:
  output/trader_history.md          overzicht per trader
  output/trader_history_trades.csv  alle afgeronde trades (open -> dicht)

Draait via GitHub Actions (workflow "trader-history"), los van de copytrack zelf.
"""
import csv
import os
import traceback
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from wallets import WALLETS

API = "https://api.hyperliquid.xyz/info"
DAGEN = int(os.environ.get("DAGEN", "60"))
EXTRA = [  # ter vergelijking, niet meer gevolgd
    {"address": "0x6859da14835424957a1e6b397d8026b1d9ff7e1e", "label": "trader_19 (verwijderd)"},
]


def post(body, tries=4):
    for i in range(tries):
        try:
            r = requests.post(API, json=body, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3)


def fills(addr, start_ms, end_ms):
    out, s = [], start_ms
    for _ in range(10):  # API geeft max 2000 per keer, max ~10000 in totaal
        batch = post({"type": "userFillsByTime", "user": addr, "startTime": s, "endTime": end_ms})
        if not batch:
            break
        out += batch
        if len(batch) < 2000:
            break
        s = max(f["time"] for f in batch) + 1
        time.sleep(0.6)
    seen, uniq = set(), []
    for f in sorted(out, key=lambda f: (f["time"], f.get("tid", 0))):
        k = (f.get("tid"), f.get("hash"), f["time"], f["coin"], f["sz"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def round_trips(fs):
    """Knipt fills per coin op in trades: van positie 0 (of omdraai) tot weer 0 (of omdraai)."""
    per_coin = {}
    for f in fs:
        per_coin.setdefault(f["coin"], []).append(f)
    trades = []
    for coin, lst in per_coin.items():
        cur = None
        for f in lst:
            start = float(f["startPosition"])
            sz = float(f["sz"]) * (1 if f["side"] == "B" else -1)
            after = start + sz
            if cur is None:
                cur = {"coin": coin, "richting": "LONG" if (start + sz if start == 0 else start) > 0 else "SHORT",
                       "open": f["time"], "pnl": 0.0, "fee": 0.0, "max_usd": 0.0, "half": start != 0}
            cur["pnl"] += float(f.get("closedPnl", 0) or 0)
            cur["fee"] += float(f.get("fee", 0) or 0)
            cur["max_usd"] = max(cur["max_usd"], abs(after) * float(f["px"]))
            flipped = (start > 0 and after < 0) or (start < 0 and after > 0)
            if abs(after) < 1e-12 or flipped:
                cur["close"] = f["time"]
                trades.append(cur)
                cur = None
                if flipped:
                    cur = {"coin": coin, "richting": "LONG" if after > 0 else "SHORT", "open": f["time"],
                           "pnl": 0.0, "fee": 0.0, "max_usd": abs(after) * float(f["px"]), "half": False}
    return trades


def pnl_periods(addr):
    try:
        data = post({"type": "portfolio", "user": addr})
    except Exception:
        return {}
    res = {}
    if not isinstance(data, list):
        return res
    for item in data:
        if not (isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict)):
            continue
        period, d = item
        h = d.get("pnlHistory") or []
        if h:
            res[period] = float(h[-1][1]) - float(h[0][1])
        av = d.get("accountValueHistory") or []
        if period == "allTime" and av:
            res["waarde"] = float(av[-1][1])
    return res


def main():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAGEN)
    s_ms, e_ms = int(start.timestamp() * 1000), int(now.timestamp() * 1000)
    os.makedirs("output", exist_ok=True)
    rows, all_trades = [], []
    for w in list(WALLETS) + EXTRA:
        label, addr = w["label"], w["address"]
        print(f"Ophalen {label}...", flush=True)
        try:
            fs = fills(addr, s_ms, e_ms)
            tr = [t for t in round_trips(fs) if not t["half"]]
        except Exception as e:
            print(f"  fout: {traceback.format_exc()}")
            rows.append({"label": label, "fout": f"{type(e).__name__}: {str(e)[:120]}"})
            continue
        for t in tr:
            t["label"] = label
            t["netto"] = t["pnl"] - t["fee"]
            t["uren"] = (t["close"] - t["open"]) / 3_600_000
        all_trades += tr
        p = pnl_periods(addr)
        n = len(tr)
        wins = sum(1 for t in tr if t["netto"] > 0)
        uren = sorted(t["uren"] for t in tr)
        rows.append({
            "label": label, "fills": len(fs), "trades": n,
            "winrate": f"{wins / n:.0%}" if n else "-",
            "netto": sum(t["netto"] for t in tr),
            "mediaan_uren": uren[n // 2] if n else 0,
            "coins": len({t["coin"] for t in tr}),
            "pnl_maand": p.get("month"), "pnl_alltime": p.get("allTime"), "waarde": p.get("waarde"),
        })
        time.sleep(0.8)

    with open("output/trader_history_trades.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["trader", "coin", "richting", "geopend_utc", "gesloten_utc", "uren", "netto_pnl_usd", "max_positie_usd"])
        for t in sorted(all_trades, key=lambda t: t["close"]):
            wr.writerow([t["label"], t["coin"], t["richting"],
                         datetime.fromtimestamp(t["open"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
                         datetime.fromtimestamp(t["close"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
                         round(t["uren"], 1), round(t["netto"], 2), round(t["max_usd"])])

    def m(x):
        return "-" if x is None else f"${x:,.0f}"

    ok = sorted([r for r in rows if "fout" not in r], key=lambda r: -r["netto"])
    lines = [f"# Echte trade-geschiedenis van de gevolgde wallets ({DAGEN} dagen)", "",
             f"Gemaakt: {now:%Y-%m-%d %H:%M} UTC. Bron: Hyperliquid (openbaar). Alleen trades die in deze periode zijn geopend en gesloten.", "",
             "| Trader | Trades | Winrate | Netto winst | Mediaan duur | Coins | PnL maand | PnL all-time | Accountwaarde |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in ok:
        lines.append(f"| {r['label']} | {r['trades']} | {r['winrate']} | {m(r['netto'])} | {r['mediaan_uren']:.1f} uur | "
                     f"{r['coins']} | {m(r['pnl_maand'])} | {m(r['pnl_alltime'])} | {m(r['waarde'])} |")
    for r in rows:
        if "fout" in r:
            lines.append(f"| {r['label']} | fout: {r['fout']} | | | | | | | |")
    with open("output/trader_history.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        os.makedirs("output", exist_ok=True)
        with open("output/trader_history.md", "w", encoding="utf-8") as f:
            f.write("# Fout bij ophalen\n\n```\n" + traceback.format_exc() + "```\n")
        print(traceback.format_exc())
    sys.exit(0)
