#!/usr/bin/env python3
"""QNT price alerts, run every 15 minutes by GitHub Actions.

Fetches public market data (Crypto.com Exchange, Bitvavo for EUR), checks the
alert rules against the state saved by the previous run, and sends a push
notification through ntfy.sh when something fires.

Usage:
  python3 alerts/check.py              # normal run (needs NTFY_TOPIC env var)
  python3 alerts/check.py --dry-run    # print alerts instead of sending
  python3 alerts/check.py --test       # send one test notification
"""
import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
STATE_FILE = Path(os.environ.get("ALERT_STATE", HERE / "state.json"))
TARGETS_FILE = HERE / "targets.json"
CDC = "https://api.crypto.com/exchange/v1/public/"
APP_URL = "https://alicetin1905-ux.github.io/QUANT-Tracker/"

FAST_MOVE = 0.05          # rule A: 5% within an hour
STEP = 0.05               # rules B/C: 24h change steps of 5%
VOLUME_X = 3.0            # rule D: hour volume vs 24h average
FAST_COOLDOWN = 3600      # seconds between two fast-move alerts
SMA_BAND = 0.01           # rule F: 1% band around SMA20 to avoid flip-flopping


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "qnt-tracker-alerts"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def cdc(method, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    j = get(f"{CDC}{method}?{q}")
    if j.get("code") != 0:
        raise RuntimeError(f"{method}: code {j.get('code')}")
    return j["result"]["data"]


def candles(inst, tf, count):
    rows = cdc("get-candlestick", instrument_name=inst, timeframe=tf, count=count)
    return sorted(
        ({"t": int(k["t"]), "o": float(k["o"]), "h": float(k["h"]), "l": float(k["l"]),
          "c": float(k["c"]), "v": float(k["v"])} for k in rows),
        key=lambda k: k["t"],
    )


def rsi(closes, p=14):
    ch = [b - a for a, b in zip(closes, closes[1:])]
    if len(ch) < p:
        return float("nan")
    g = sum(max(x, 0) for x in ch[:p]) / p
    l = sum(max(-x, 0) for x in ch[:p]) / p
    for x in ch[p:]:
        g = (g * (p - 1) + max(x, 0)) / p
        l = (l * (p - 1) + max(-x, 0)) / p
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def pct(x):
    return f"{x * 100:+.1f}%"


def step_alert(change, prev):
    """24h change crossing ±5%, ±10%, ... Fires once per new step."""
    k = math.floor(abs(change) / STEP + 1e-9)
    sign = 1 if change >= 0 else -1
    fired = bool(prev) and k >= 1 and (k > prev.get("k", 0) or sign != prev.get("sign", sign))
    return fired, {"k": k, "sign": sign}


def send(topic, title, body, tags, priority, dry):
    if dry or not topic:
        print(f"--- {title} [{tags}, p{priority}]\n{body}\n")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), method="POST",
        headers={"Title": title.encode("utf-8"), "Tags": tags, "Priority": str(priority),
                 "Click": APP_URL, "User-Agent": "qnt-tracker-alerts"},
    )
    urllib.request.urlopen(req, timeout=20).read()


def main():
    dry = "--dry-run" in sys.argv
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic and not dry:
        print("NTFY_TOPIC is not set; add it as a repository secret. Nothing sent.")
        return

    if "--test" in sys.argv:
        send(topic, "QNT alerts are working", "This is a test notification from your QNT Tracker.",
             "white_check_mark", 3, dry)
        return

    # ---- data ----
    t = cdc("get-tickers", instrument_name="QNT_USD")[0]
    price, ch24 = float(t["a"]), float(t["c"])
    btc_ch24 = float(cdc("get-tickers", instrument_name="BTC_USD")[0]["c"])
    m5 = candles("QNT_USD", "5m", 20)
    h1 = candles("QNT_USD", "1h", 30)
    d1 = candles("QNT_USD", "1D", 60)
    try:
        eur = float(get("https://api.bitvavo.com/v2/ticker/price?market=QNT-EUR")["price"])
    except Exception:
        eur = None

    now = int(time.time())
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    first_run = not state
    new = {}
    alerts = []  # (headline, detail)

    # A. fast move: price now vs ~60 minutes ago (5-minute candles)
    ref = m5[-13]["c"] if len(m5) >= 13 else m5[0]["c"]
    ch1 = price / ref - 1
    new["last_fast_at"] = state.get("last_fast_at", 0)
    if abs(ch1) >= FAST_MOVE and now - state.get("last_fast_at", 0) >= FAST_COOLDOWN:
        word = "jumped" if ch1 > 0 else "dropped"
        alerts.append((f"QNT {word} {pct(ch1)} in 1 hour", f"Fast move: {pct(ch1)} in the last hour"))
        new["last_fast_at"] = now

    # B. QNT 24h change crossing a 5% step
    fired, new["qnt24"] = step_alert(ch24, state.get("qnt24"))
    if fired:
        alerts.append((f"QNT {pct(ch24)} in 24h", f"24h change reached {pct(ch24)}"))

    # C. Bitcoin 24h change crossing a 5% step
    fired, new["btc24"] = step_alert(btc_ch24, state.get("btc24"))
    if fired:
        alerts.append((f"Bitcoin {pct(btc_ch24)} in 24h", f"Bitcoin 24h change reached {pct(btc_ch24)} (market-wide move)"))

    # D. volume spike on the last completed hour
    done = h1[:-1]
    new["last_vol_t"] = state.get("last_vol_t", 0)
    if len(done) >= 25:
        last, prior = done[-1], done[-25:-1]
        avg = sum(k["v"] for k in prior) / len(prior)
        if avg > 0 and last["v"] >= VOLUME_X * avg and last["t"] != state.get("last_vol_t"):
            alerts.append(("QNT volume spike", f"Volume spike: last hour traded {last['v'] / avg:.1f}x the 24h average"))
            new["last_vol_t"] = last["t"]

    # E. daily RSI(14) entering overbought / oversold
    closes = [k["c"] for k in d1]
    closes[-1] = price
    r = rsi(closes)
    zone = "over" if r >= 70 else "under" if r <= 30 else "normal"
    new["rsi_zone"] = zone
    if state.get("rsi_zone") and zone != state["rsi_zone"] and zone != "normal":
        label = "overbought (above 70)" if zone == "over" else "oversold (below 30)"
        alerts.append((f"QNT RSI {label}", f"Daily RSI is {r:.0f}, {label}"))

    # F. price crossing the 20-day average (with a 1% band)
    sma = sum(closes[-20:]) / 20
    side = state.get("sma_side")
    if price > sma * (1 + SMA_BAND):
        side_now = "above"
    elif price < sma * (1 - SMA_BAND):
        side_now = "below"
    else:
        side_now = side
    new["sma_side"] = side_now
    if side and side_now and side_now != side:
        alerts.append((f"QNT crossed {side_now} its 20-day average",
                       f"Price moved {side_now} the 20-day average (${sma:,.2f})"))

    # G. your own price levels
    targets = json.loads(TARGETS_FILE.read_text()) if TARGETS_FILE.exists() else {}
    new["last_usd"], new["last_eur"] = price, eur
    for cur, now_p, prev_p, sym in (("usd", price, state.get("last_usd"), "$"), ("eur", eur, state.get("last_eur"), "€")):
        if now_p is None or prev_p is None:
            continue
        for lvl in targets.get(f"above_{cur}", []):
            if prev_p < lvl <= now_p:
                alerts.append((f"QNT above {sym}{lvl:,}", f"Your level: price rose above {sym}{lvl:,}"))
        for lvl in targets.get(f"below_{cur}", []):
            if prev_p > lvl >= now_p:
                alerts.append((f"QNT below {sym}{lvl:,}", f"Your level: price fell below {sym}{lvl:,}"))

    STATE_FILE.write_text(json.dumps(new, indent=1))

    eur_txt = f" (€{eur:,.2f})" if eur else ""
    summary = f"Price ${price:,.2f}{eur_txt} | 1h {pct(ch1)} | 24h {pct(ch24)} | RSI {r:.0f}"
    print(summary)

    if first_run:
        send(topic, "QNT alerts are on",
             f"You'll get a notification when QNT moves 5%, hits your levels, or an indicator signals.\n{summary}",
             "white_check_mark", 3, dry)
        return
    if not alerts:
        print("No alerts.")
        return

    up = any(w in alerts[0][0] for w in ("jumped", "+", "above", "oversold"))
    title = alerts[0][0] if len(alerts) == 1 else f"{alerts[0][0]} (+{len(alerts) - 1} more)"
    body = "\n".join(f"- {d}" for _, d in alerts) + f"\n{summary}\nNot financial advice."
    big = any("1 hour" in h or "Your level" in d for h, d in alerts)
    send(topic, title, body, "chart_with_upwards_trend" if up else "chart_with_downwards_trend", 4 if big else 3, dry)


if __name__ == "__main__":
    main()
