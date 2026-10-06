# QNT Tracker

Live dashboard for Quant (QNT): price, candles, order book, trades, technicals, news and fundamentals.
Prices come from the Crypto.com Exchange public API and refresh about every 15 seconds.

**App:** https://alicetin1905-ux.github.io/QUANT-Tracker/

## Add it to your home screen

- **iPhone / iPad (Safari):** open the link, tap **Share**, then **Add to Home Screen**.
- **Android (Chrome):** open the link, tap the **⋮** menu, then **Install app** or **Add to Home screen**.

The app opens full screen with its own icon. Offline, it shows the last prices it saved on your device.

## Files

| File | What it is |
|---|---|
| `qnt-dashboard.html` | The source. Also published as a claude.ai artifact, where it uses the Crypto.com connector. |
| `index.html` | The installable app. Generated, don't edit by hand: run `python3 build.py`. |
| `manifest.webmanifest`, `sw.js`, `icons/` | App name, icon and offline support. |

Not financial advice.
