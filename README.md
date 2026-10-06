# QNT Tracker

Live dashboard for Quant (QNT): price, candles, order book, trades, technicals, news and fundamentals.
Prices come from the Crypto.com Exchange public API and refresh about every 15 seconds.

**App:** https://alicetin1905-ux.github.io/QUANT-Tracker/

## Add it to your home screen

- **iPhone / iPad (Safari):** open the link, tap **Share**, then **Add to Home Screen**.
- **Android (Chrome):** open the link, tap the **⋮** menu, then **Install app** or **Add to Home screen**.

The app opens full screen with its own icon. Offline, it shows the last prices it saved on your device.

## Price alerts (free)

GitHub checks QNT every 15 minutes and sends a push notification through the free [ntfy](https://ntfy.sh) app when:

- QNT moves 5% or more within an hour
- the 24h change reaches ±5%, ±10%, ±15% and so on (once per step)
- Bitcoin's 24h change reaches ±5%, ±10% and so on
- trading volume in the last hour is 3x the normal amount
- daily RSI goes above 70 (overbought) or below 30 (oversold)
- price crosses its 20-day average
- price crosses one of your own levels in `alerts/targets.json` (USD or EUR)

Setup: install ntfy, subscribe to your private topic, and save that topic as the repository secret `NTFY_TOPIC`
(Settings → Secrets and variables → Actions). Test it from Actions → QNT price alerts → Run workflow with "Send a test notification" ticked.

## Files

| File | What it is |
|---|---|
| `qnt-dashboard.html` | The source. Also published as a claude.ai artifact, where it uses the Crypto.com connector. |
| `index.html` | The installable app. Generated, don't edit by hand: run `python3 build.py`. |
| `manifest.webmanifest`, `sw.js`, `icons/` | App name, icon and offline support. |
| `alerts/check.py`, `alerts/targets.json` | The price alert script and your price levels. |
| `.github/workflows/price-alerts.yml` | Runs the alert check every 15 minutes. |

Not financial advice.
