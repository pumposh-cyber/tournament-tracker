# 🏐 UVAC Urban Volleyball 15 TS – Tournament Tracker

A Flask-based tournament planning app for Tiya Raina (#13, Middle Blocker) and the UVAC Urban Volleyball 15 TS team (G15UVBAC1NC · Hyacinth Division).

## Features

- **Tournament schedule** — all events with status (upcoming / past / cancelled)
- **Trip Dashboard** — per-tournament hotel + car booking details, timeline, parking guide, coach notes, weather forecast, venue quick reference, confirmation numbers
- **Booking form** — save hotel/car confirmation numbers, perks, cancellation deadlines
- **Live weather** — Open-Meteo API integration with 16-day forecast
- **Drive time + distance** — calculated from Bay Area home base
- **Packing checklist** — per-tournament with 5 categories, check/reset
- **Power League** — rank (#127) and points (163) in header
- **Replit Auth** — Google OAuth via Replit (swap for Flask-Login if self-hosting)

## Quick Start (local dev)

```bash
git clone https://github.com/pumposh-cyber/tournament-tracker.git
cd tournament-tracker
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SESSION_SECRET and DATABASE_URL
python main.py
```

## Deploy to Railway (recommended — free tier available)

1. Push to GitHub: `git push origin main`
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select `tournament-tracker` repo
4. Add a **PostgreSQL** plugin → Railway auto-sets `DATABASE_URL`
5. Set env var: `SESSION_SECRET=<random string>`
6. Set `REPLIT_DOMAINS=your-app.up.railway.app` if using Replit auth
7. Deploy → your app is live in ~2 minutes

## Deploy to Render (alternative)

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service → connect repo
3. Render reads `render.yaml` automatically — creates app + PostgreSQL
4. Set `SESSION_SECRET` in environment variables
5. Deploy

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `SESSION_SECRET` | Yes | Random secret string |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REPLIT_DOMAINS` | If using Replit auth | Your deployed domain |
| `ISSUER_URL` | If using Replit auth | `https://replit.com` |

## Key Routes

| Route | Description |
|---|---|
| `/` | Tournament schedule list |
| `/tournament/<id>` | Tournament detail |
| `/trip/<id>` | **Trip Dashboard** (new) |
| `/trip/<id>/booking` | Add/edit hotel + car details |
| `/checklist/<id>` | Packing checklist |
| `/add` | Add new tournament |

## Tech Stack

- **Backend**: Python 3.11 · Flask · SQLAlchemy · PostgreSQL
- **Auth**: Replit OAuth (flask-dance)
- **Weather**: Open-Meteo API (free, no key needed)
- **Frontend**: Jinja2 templates · Font Awesome · vanilla CSS
- **Deploy**: Railway / Render / Replit

## Current Tournament Data

| Event | Dates | Hotel | Car |
|---|---|---|---|
| NCVA Far Western | Apr 17–19, 2026 | Extended Stay America (Reno South Meadows) | Alamo AWD/4×4 Tahoe |
| NCVA Regional | May 9–10, 2026 | TBA | TBA |
| NCVA Regional Champs | May 9–10, 2026 | TBA | TBA |
