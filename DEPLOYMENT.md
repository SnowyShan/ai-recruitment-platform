# TalentBridge Deployment Guide

**Server:** `148.100.78.222`  
**User:** `linux1`  
**App dir:** `~/ai-recruitment-platform-main`  
**SSH:** `ssh linux1@148.100.78.222`  
**Live URL:** `https://148.100.78.222` (self-signed cert — click through browser warning)

---

## Deploying New Changes

Follow these steps every time you deploy an update.

### 1. Create the zip (on your Mac)

```bash
cd ~/Documents/projects
rm -f /tmp/ai-recruitment-platform-main.zip
zip -r /tmp/ai-recruitment-platform-main.zip ai-recruitment-platform \
  --exclude "*/node_modules/*" \
  --exclude "*/.git/*" \
  --exclude "*/venv/*" \
  --exclude "*/__pycache__/*" \
  --exclude "*/dist/*" \
  --exclude "*.webm" \
  --exclude "*.mp4" \
  --exclude "*/backend/audio/*" \
  --exclude "*/backend/uploads/*" \
  --exclude "*.db"
```

### 2. Upload to server

```bash
scp /tmp/ai-recruitment-platform-main.zip linux1@148.100.78.222:/home/linux1/
```

### 3. Deploy on server

SSH in, then run:

```bash
cd ~
unzip -o ai-recruitment-platform-main.zip
# The zip extracts to "ai-recruitment-platform" — copy into the live directory
cp -r ai-recruitment-platform/. ai-recruitment-platform-main/
rm -rf ai-recruitment-platform
```

### 4. Rebuild frontends

**Main frontend:**
```bash
cd ~/ai-recruitment-platform-main/frontend
npm install --force
npm run build
```

**Interview module frontend:**
```bash
cd ~/ai-recruitment-platform-main/interview-module/frontend
npm install --force
npm run build
```

> ⚠️ If `npm run build` segfaults, run `npm install vite@5 --save-dev --force` first, then retry.

### 5. Restart backend services

```bash
sudo systemctl restart talentbridge interview-module
sudo systemctl status talentbridge interview-module --no-pager
```

Both should show `active (running)`.

### 6. Verify

- Open `https://148.100.78.222` — click through SSL warning, check login works
- Open interview link — mic permission should be requested, audio should play
- Try creating a job and submitting an application

---

## Environment Files

`.env` files are **not** in the zip. They live permanently on the server and never need to be touched after initial setup.

Locations:
- `~/ai-recruitment-platform-main/backend/.env`
- `~/ai-recruitment-platform-main/interview-module/backend/.env`
- `~/ai-recruitment-platform-main/interview-module/frontend/.env` (contains VITE URLs)

### backend/.env
```
DATABASE_URL=sqlite:///./talentbridge.db
SECRET_KEY=beb40203620b17b742f67edb7f1df75363efed55341d9d1dbba7867437a2c8cb
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEBUG=True
BYPASS_CAPTCHA=true
APP_NAME=TalentBridge AI
APP_VERSION=1.0.0
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760
GMAIL_USER=talentbridgerecruiterai@gmail.com
GMAIL_APP_PASSWORD=nqlk wgvc rqiz jxib
CORS_ORIGINS=http://148.100.78.222,https://148.100.78.222,http://localhost:5173,http://localhost:5174
INTERVIEW_MODULE_URL=https://148.100.78.222
INTERVIEW_API_URL=http://localhost:8001
ANTHROPIC_API_KEY=<indrajit's anthropic key>
```

### interview-module/backend/.env
```
ANTHROPIC_API_KEY=<indrajit's anthropic key>
OPENAI_API_KEY=<indrajit's openai key>
DB_PATH=./interview.db
TALENTBRIDGE_API_URL=http://localhost:8000
```

### frontend/.env (main frontend)
```
VITE_API_URL=https://148.100.78.222
VITE_INTERVIEW_API_URL=http://localhost:8001
VITE_INTERVIEW_URL=https://148.100.78.222/interview
VITE_BYPASS_CAPTCHA=true
```

### interview-module/frontend/.env
```
VITE_API_URL=https://148.100.78.222
VITE_MAIN_API_URL=https://148.100.78.222
```

---

## Nginx Configuration

Full config at `/etc/nginx/sites-enabled/talentbridge`:

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;

    root /home/linux1/ai-recruitment-platform-main/frontend/dist;
    index index.html;

    # Interview module API — must come before /api/ to take priority
    location ^~ /api/interview/ {
        proxy_pass http://127.0.0.1:8001/api/interview/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }

    # Main backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 20M;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    # Interview module frontend
    location /interview/ {
        alias /home/linux1/ai-recruitment-platform-main/interview-module/frontend/dist/;
        try_files $uri $uri/ /interview/index.html;
    }

    # Interview module API (legacy path)
    location /interview-api/ {
        proxy_pass http://127.0.0.1:8001/api/interview/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }

    # Pre-generated question audio files
    location /audio/ {
        alias /home/linux1/ai-recruitment-platform-main/interview-module/backend/audio/;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## Troubleshooting

### Port already in use
```bash
sudo fuser -k 8000/tcp
sudo fuser -k 8001/tcp
sudo systemctl restart talentbridge interview-module
```

### Backend crashes — check logs
```bash
sudo journalctl -u talentbridge -n 30 --no-pager | grep -i error
sudo journalctl -u interview-module -n 30 --no-pager | grep -i error
```

### Missing database columns
```bash
cd ~/ai-recruitment-platform-main/backend
source venv/bin/activate
python3 -c "
from app.database import engine, Base
from app import models
Base.metadata.create_all(bind=engine)
print('Done')
"
deactivate
sudo systemctl restart talentbridge
```

### venv missing or broken
```bash
# Main backend
cd ~/ai-recruitment-platform-main/backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
deactivate
sudo systemctl restart talentbridge

# Interview module
cd ~/ai-recruitment-platform-main/interview-module/backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart interview-module
```

### Build segfaults (out of memory / Vite version)
```bash
# Add swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Downgrade Vite (Vite 6 segfaults on this server)
npm install vite@5 --save-dev --force
npm run build
```

### Interview audio not playing
- Must use **HTTPS** — mic and audio APIs require secure context
- Check `/audio/` Nginx block is present
- Check `interview-module/frontend/.env` has `VITE_API_URL=https://148.100.78.222`
- Rebuild frontend after any .env change

### Interview invite links return 404
Check Nginx has `location /interview/` block pointing to the interview frontend dist folder.

### No mic permission prompt
Site must be served over HTTPS. Plain HTTP blocks `navigator.mediaDevices.getUserMedia`.

---

## SSL Certificate (self-signed)

Already set up. Valid for 1 year. To renew:
```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/nginx.key \
  -out /etc/nginx/ssl/nginx.crt \
  -subj "/CN=148.100.78.222"
sudo systemctl reload nginx
```

> Note: Self-signed cert causes browser warnings. Users must click "Advanced → Proceed". For production with a real domain, use Let's Encrypt (`certbot`).

---

## Server Notes

- **Architecture:** s390x (IBM Z) — not amd64. Some Linux binaries won't work (e.g. cloudflared amd64).
- **RAM:** 4GB, no swap by default. Always ensure swap is active before building.
- **Swap:** `/swapfile` (2GB). Check with `free -h`. If missing, recreate (see above).
- **Node:** v20. Vite 6 segfaults — always use Vite 5 for interview module frontend.
- **Python:** 3.10. torch must be installed with CPU-only index URL.

---

## Key Lessons Learned

1. **HTTPS is required** for mic access and audio playback. Plain HTTP blocks both.
2. **Nginx location order matters** — `^~ /api/interview/` must come before `/api/` or it gets swallowed.
3. **Audio files need their own Nginx route** — `/audio/` must alias to `backend/audio/`.
4. **Frontend .env must use https://** — rebuild after changing VITE_API_URL.
5. **Browser cache is aggressive** — always test in incognito after a rebuild.
6. **Never use `cp -r` to replace a Python project** — venvs break. Recreate with pip install.
7. **torch won't install normally** — use CPU-only: `pip install torch --index-url https://download.pytorch.org/whl/cpu`.
8. **Vite 6 segfaults on s390x** — use Vite 5.
9. **The zip extracts to `ai-recruitment-platform`** not `ai-recruitment-platform-main` — use `cp -r` to merge.
10. **Database schema changes need manual migrations** — `create_all` only creates new tables, not columns.
11. **Both frontends need `VITE_API_URL=https://...`** — without it they default to `localhost` which fails from the browser on a remote server.
