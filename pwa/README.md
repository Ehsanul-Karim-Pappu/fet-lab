# FET Lab — installable web app

Everything is in this folder. It needs to be served over http(s) for Android to offer
"Install app" — opening `index.html` straight off the filesystem works, but Chrome will
not install it.

## Put it on your phone

**Option 1 — from your laptop, over wifi (30 seconds)**

```bash
cd pwa
python3 -m http.server 8000
```

Find your laptop's LAN address (`ipconfig getifaddr en0` on macOS, `hostname -I` on Linux),
then on the phone open `http://<that-address>:8000`. Chrome menu → **Add to Home screen** /
**Install app**. After the first load it is cached and works with the laptop switched off.

**Option 2 — host it anywhere static**

Drop the folder on GitHub Pages, Netlify, Cloudflare Pages, or any static host and open the
URL on the phone. Same install flow. This is the one to use if you want it on more than one
device.

**Option 3 — no install**

Just open `index.html` in any browser. Everything works except the home-screen install and
offline caching.

## What you get

Installed, it runs fullscreen with no browser chrome, keeps working offline, and shows up in
the launcher like any other app. It is the same page as the desktop viewer, with touch
gestures: one finger orbits, two fingers pan and pinch-zoom, tap identifies a layer.
