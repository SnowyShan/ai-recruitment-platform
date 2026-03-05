# Cross-Device Testing Setup
*How to expose TalentBridge to a device not on the same LAN (e.g. iPhone over cellular)*

---

## Why Cloudflare Tunnels

Vite's dev server is not reachable from outside the local network. Even `--host 0.0.0.0` only works on the same LAN. For iPhone testing over cellular, we use `cloudflared` to create temporary public HTTPS tunnels.

## Prerequisites

```bash
brew install cloudflared
```

No account needed — tunnels are anonymous and free but expire when the process dies.

---

## Step 1 — Use Production Builds, Not Dev Servers

Vite's HMR WebSocket breaks on Safari through Cloudflare tunnels. Use static production builds instead:

```bash
# TalentBridge frontend
cd frontend && npm run build && npx serve dist -s -l 5173 &

# Interview module frontend
cd interview-module/frontend && npm run build && npx serve dist -s -l 5174 &
```

> **Why `npx serve dist -s`?** The `-s` flag enables SPA mode (serves `index.html` for all routes). Without it, refreshing a deep route returns 404.

---

## Step 2 — Start All 4 Services

```bash
# TalentBridge backend (port 8000)
cd backend && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/tb-backend.log 2>&1 &

# Interview module backend (port 8001)
cd interview-module/backend && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/interview-backend.log 2>&1 &

# TalentBridge frontend (port 5173) — build first
cd frontend && npm run build && npx serve dist -s -l 5173 > /tmp/tb-frontend.log 2>&1 &

# Interview module frontend (port 5174) — build first
cd interview-module/frontend && npm run build && npx serve dist -s -l 5174 > /tmp/interview-frontend.log 2>&1 &
```

---

## Step 3 — Create Cloudflare Tunnels

```bash
cloudflared tunnel --url http://localhost:8000 --no-autoupdate > /tmp/tunnel-tb-backend.log 2>&1 &
cloudflared tunnel --url http://localhost:8001 --no-autoupdate > /tmp/tunnel-interview-backend.log 2>&1 &
cloudflared tunnel --url http://localhost:5173 --no-autoupdate > /tmp/tunnel-tb-frontend.log 2>&1 &
cloudflared tunnel --url http://localhost:5174 --no-autoupdate > /tmp/tunnel-interview-frontend.log 2>&1 &
```

Wait ~10 seconds, then grab the URLs:

```bash
sleep 10
echo "TB backend:      $(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel-tb-backend.log | tail -1)"
echo "Interview back:  $(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel-interview-backend.log | tail -1)"
echo "TB frontend:     $(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel-tb-frontend.log | tail -1)"
echo "Interview front: $(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel-interview-frontend.log | tail -1)"
```

---

## Step 4 — Update .env Files

Tunnel URLs are random and change every time cloudflared restarts. Update all four `.env` files with the new URLs:

### `frontend/.env`
```
VITE_API_URL=<TB backend tunnel>
VITE_INTERVIEW_API_URL=<Interview backend tunnel>
VITE_INTERVIEW_URL=<Interview frontend tunnel>
```

### `interview-module/frontend/.env`
```
VITE_API_URL=<Interview backend tunnel>
VITE_MAIN_API_URL=<TB backend tunnel>
```

### `backend/.env`
```
CORS_ORIGINS=http://localhost:5173,http://localhost:5174,<TB frontend tunnel>,<Interview frontend tunnel>,<TB backend tunnel>,<Interview backend tunnel>
INTERVIEW_MODULE_URL=<Interview frontend tunnel>
INTERVIEW_API_URL=<Interview backend tunnel>
```

> **Note:** `interview-module/backend/.env` does not need tunnel URLs — it only talks to `TALENTBRIDGE_API_URL=http://localhost:8000` (local) and the OpenAI API (internet).

---

## Step 5 — Rebuild Frontends & Restart Backends

After updating `.env` files, the env vars are baked into the frontend builds. Rebuild both frontends:

```bash
pkill -f "node.*serve"     # stop serve processes
pkill -f "uvicorn"         # stop backends (needed to pick up new CORS_ORIGINS)

# Restart backends
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/tb-backend.log 2>&1 &
cd interview-module/backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/interview-backend.log 2>&1 &

# Rebuild and re-serve frontends
cd frontend && npm run build && npx serve dist -s -l 5173 > /tmp/tb-frontend.log 2>&1 &
cd interview-module/frontend && npm run build && npx serve dist -s -l 5174 > /tmp/interview-frontend.log 2>&1 &
```

---

## Step 6 — Test

Open the TB frontend tunnel URL on your iPhone. For direct interview testing, open the Interview frontend tunnel URL.

On **first load** of the interview, Safari will ask for microphone permission — this is by design (we request it upfront on the instructions screen).

---

## Teardown

```bash
pkill cloudflared
pkill -f "node.*serve"
pkill -f "uvicorn"
```

---

## Known Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Blank screen on interview | Old cached JS bundle in Safari | Hard refresh or clear site data |
| CORS errors | Backend not restarted after updating `CORS_ORIGINS` in `.env` | Restart backends — `--reload` watches `.py` files, not `.env` |
| `vite preview` 502 | `preview.allowedHosts` not set | Use `npx serve dist -s` instead |
| Audio not playing on first question | iOS autoplay blocked before user gesture | Fixed: instructions screen + "Start Interview" button acts as user gesture |
| TTS reads previous question | Stale axios response race condition | Fixed: generation counter in `speakThenRecord` discards stale responses |
| Double voiceover on load | Two useEffects both triggering `speakThenRecord` | Fixed: merged into single effect gated on `micReady` + `started` |

---

## Vite Config Changes Required

Both frontends need `preview.allowedHosts` set (not just `server.allowedHosts`):

```js
// vite.config.js
export default defineConfig({
  server: { allowedHosts: ['all', '.trycloudflare.com'] },
  preview: { allowedHosts: ['all', '.trycloudflare.com'] },  // ← required for tunnels
})
```

---

## React Version Note

Pin React to `18.2.0` in `package.json`. React `18.3.x` has a TDZ bug in production builds on Safari that causes a blank white screen with no console error.

```json
"react": "18.2.0",
"react-dom": "18.2.0"
```
