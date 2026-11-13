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
BTC_DAG = os.environ.get("BTC_DAG", "")  # bv. 2026-11-12: wie zat die dag hoe in BTC
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


def pos_op(fs, t_ms, huidig):
    """BTC-positie (in BTC) op tijdstip t_ms, afgeleid uit de fills."""
    voor = [f for f in fs if f["time"] < t_ms]
    na = [f for f in fs if f["time"] >= t_ms]
    if voor:
        f = voor[-1]
        return float(f["startPosition"]) + float(f["sz"]) * (1 if f["side"] == "B" else -1)
    if na:
        return float(na[0]["startPosition"])
    return huidig


def btc_dag(label, addr, fs):
    d0 = int(datetime.strptime(BTC_DAG, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    d1 = d0 + 86_400_000
    btc = [f for f in fs if f["coin"] == "BTC"]
    try:
        st = post({"type": "clearinghouseState", "user": addr})
        huidig = 0.0
        for ap in st.get("assetPositions", []):
            if ap["position"]["coin"] == "BTC":
                huidig = float(ap["position"]["szi"])
    except Exception:
        huidig = 0.0
    p0, p1 = pos_op(btc, d0, huidig), pos_op(btc, d1, huidig)
    dag = [f for f in btc if d0 <= f["time"] < d1]
    gerealiseerd = sum(float(f.get("closedPnl", 0) or 0) - float(f.get("fee", 0) or 0) for f in dag)
    return {"label": label, "begin": p0, "eind": p1, "fills": len(dag), "gerealiseerd": gerealiseerd, "nu": huidig}


def main():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAGEN)
    s_ms, e_ms = int(start.timestamp() * 1000), int(now.timestamp() * 1000)
    os.makedirs("output", exist_ok=True)
    rows, all_trades, btc_rows = [], [], []
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
        if BTC_DAG:
            btc_rows.append(btc_dag(label, addr, fs))
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
            "pnl_week": p.get("week"), "pnl_maand": p.get("month"), "pnl_alltime": p.get("allTime"), "waarde": p.get("waarde"),
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
             "| Trader | Trades | Winrate | Netto winst | Mediaan duur | Coins | PnL week | PnL maand | PnL all-time | Accountwaarde |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in ok:
        lines.append(f"| {r['label']} | {r['trades']} | {r['winrate']} | {m(r['netto'])} | {r['mediaan_uren']:.1f} uur | "
                     f"{r['coins']} | {m(r['pnl_week'])} | {m(r['pnl_maand'])} | {m(r['pnl_alltime'])} | {m(r['waarde'])} |")
    for r in rows:
        if "fout" in r:
            lines.append(f"| {r['label']} | fout: {r['fout']} | | | | | | | | |")
    if BTC_DAG:
        try:
            d0 = int(datetime.strptime(BTC_DAG, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
            c = post({"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1d", "startTime": d0, "endTime": d0 + 86_399_000}})[0]
            o, cl, hi, lo = float(c["o"]), float(c["c"]), float(c["h"]), float(c["l"])
            lines += ["", f"## BTC op {BTC_DAG} (UTC): open ${o:,.0f}, hoog ${hi:,.0f}, laag ${lo:,.0f}, slot ${cl:,.0f}", ""]
        except Exception as e:
            o = cl = None
            lines += ["", f"## BTC op {BTC_DAG}: koers ophalen mislukt ({e})", ""]
        lines += ["| Trader | Positie begin dag | Positie eind dag | Fills die dag | Gerealiseerd | Geschat resultaat dag | Positie nu |", "|---|---|---|---|---|---|---|"]
        def ps(x, px):
            if abs(x) < 1e-9:
                return "geen"
            return f"{'LONG' if x > 0 else 'SHORT'} {abs(x):.2f} BTC" + (f" (${abs(x) * px:,.0f})" if px else "")
        for b in btc_rows:
            if abs(b["begin"]) < 1e-9 and abs(b["eind"]) < 1e-9 and b["fills"] == 0:
                continue
            # schatting: open positie gedurende de dag x koersverandering + gerealiseerd
            schat = b["gerealiseerd"] + (b["eind"] * (cl - o) if o else 0) if b["fills"] == 0 else None
            schat_txt = m(schat) if schat is not None else "zie gerealiseerd"
            lines.append(f"| {b['label']} | {ps(b['begin'], o)} | {ps(b['eind'], cl)} | {b['fills']} | {m(b['gerealiseerd'])} | {schat_txt} | {ps(b['nu'], cl)} |")
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
