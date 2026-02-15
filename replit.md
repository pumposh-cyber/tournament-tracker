# Tournament Tracker

## Overview
A Python Flask web application for tracking the UVAC Urban Volleyball 15 TS (G15UVBAC1NC) tournament schedule. Uses PostgreSQL via SQLAlchemy for data storage, with Excel (.xlsx) and CSV import capability. Includes team standings, weather forecasts, distance/drive time from home, NCVA Power League links, travel checklists, and multi-parent login via Replit Auth.

## Team Info
- **Team**: UVAC Urban Volleyball 15 TS
- **Code**: G15UVBAC1NC
- **Age Group**: 15s
- **Division**: Hyacinth
- **Rank**: 127 | **Points**: 163
- **Power League Standings**: [Google Sheets](https://docs.google.com/spreadsheets/d/1_Xog0a8Lqf6COYTfp0B8575teSsfQoy5/edit?gid=486749021#gid=486749021)
- **NCVA Points Page**: [ncva.com/girls-power-league-points](https://ncva.com/girls-power-league-points/)
- Team info is stored as TEAM_INFO dict in routes.py and injected into all templates via context_processor

## Recent Changes
- 2026-02-15: Added travel checklist feature with 5 categories (gear, nutrition, recovery, travel, family logistics)
- 2026-02-15: Changed default schedule view to show upcoming events instead of all
- 2026-02-15: Added ChecklistItem model with per-tournament tracking, toggle, and reset
- 2026-02-15: Added team identity (UVAC Urban Volleyball 15 TS) with rank, points, division, Power League links
- 2026-02-15: Added team banner on schedule page showing rank #127, 163 points, Hyacinth division
- 2026-02-15: Added Power League standings links to nav, detail page resources, and footer
- 2026-02-15: Added multi-parent login with Replit Auth (Google, GitHub, Apple, email/password)
- 2026-02-15: Migrated from SQLite to PostgreSQL database
- 2026-02-15: Added landing page for logged-out users, protected all routes with login
- 2026-02-15: Restructured app into app.py (config), routes.py (routes), replit_auth.py (auth), models.py (models)
- 2026-02-15: Added tournament cancellation feature with reason presets and restore capability
- 2026-02-15: Added weather forecasts (Open-Meteo API), distance from home, drive time, NCVA links, and resource links
- 2026-02-15: Initial project creation with Flask, SQLAlchemy

## Project Architecture
- **app.py** - Flask app initialization, database config (PostgreSQL), SQLAlchemy setup
- **main.py** - Entry point, imports routes and starts server on port 5000
- **routes.py** - All route handlers + TEAM_INFO config + DEFAULT_CHECKLIST data + context_processor
- **replit_auth.py** - Replit Auth integration (OAuth2, login/logout, session management)
- **models.py** - SQLAlchemy models: User (auth), OAuth (tokens), Tournament (schedule data), ChecklistItem (travel checklists)
- **utils.py** - Utility functions: weather API, geocoding, distance calculation, drive time
- **import_csv.py** - Script to import tournament data from Excel (.xlsx) or CSV files
- **attached_assets/** - User-uploaded files (original Excel spreadsheet, team screenshots)
- **templates/** - Jinja2 HTML templates (base, landing, index, detail, add, edit, checklist, 403)
- **static/style.css** - Stylesheet with team banner, auth UI, landing page, status tags, weather cards, checklist styles

## Database Schema (PostgreSQL)
### Users table (Replit Auth - do not drop)
- id (string, primary key), email, first_name, last_name, profile_image_url
- created_at, updated_at

### OAuth table (Replit Auth - do not drop)
- user_id, browser_session_key, provider, token

### Tournament table
- event, dates_display, date_start (datetime for sorting/filtering)
- days, city, venue
- hotel_recommendation, hotel_link_notes, car_rental_recommendation
- hotel_booking_status, car_booking_status, notes
- is_cancelled (boolean), cancellation_reason (text)

### ChecklistItem table
- id, tournament_id (FK to tournaments), category, item_text
- is_checked (boolean), sort_order (integer)
- Auto-populated with DEFAULT_CHECKLIST items on first access per tournament

## Key Features
- **Default to upcoming events** - Schedule page shows current/upcoming tournaments by default
- **Travel checklist** - Per-tournament packing/travel checklist with 5 categories:
  1. Essential Volleyball Gear (jerseys, shoes, knee pads, etc.)
  2. Hydration and Nutrition (water, snacks, cooler)
  3. Recovery and Injury Prevention (foam roller, first aid, ice packs)
  4. Travel and Comfort Items (bag, charger, schedule, cash)
  5. Parent / Family Logistics (directions, hotel confirm, sibling snacks)
- Checklist has progress tracking (X/Y packed), per-category completion indicators
- Checklist items toggle with one click, reset option to start fresh
- Team identity banner with rank, points, division, and Power League quick links
- Multi-parent login via Replit Auth (Google, GitHub, Apple, email/password)
- Landing page showing team name and code for logged-out users
- User avatar and name displayed in navigation bar
- Tournament cancellation with reason (NCVA schedule change, venue change, weather, etc.)
- Cancel/restore tournaments with one click; cancelled events shown with strikethrough
- Filter tournaments by All / Upcoming / Past / Cancelled
- Color-coded booking status tags (Completed, Booked, In Progress, Pending, etc.)
- Weather forecast for upcoming events (Open-Meteo free API, no key needed)
- Distance from home and estimated drive time (home: Bay Area, CA)
- Google Maps directions link
- NCVA and Power League links in navigation, detail page, and footer
- WhatsApp Parents Group link in navigation
- Venue map link on detail page
- Add, edit, delete tournaments via web forms with dropdown status selectors
- Excel and CSV import with flexible date parsing
- Responsive design with Font Awesome icons

## Tech Stack
- Python 3.11, Flask, Flask-SQLAlchemy, PostgreSQL
- Flask-Dance (OAuth2), Flask-Login (session management), PyJWT (token decoding)
- openpyxl (Excel import), requests (API calls)
- Open-Meteo API (free, no API key) for weather
- Font Awesome 6.5 for icons

## Configuration
- Team info stored in TEAM_INFO dict in routes.py (name, code, division, rank, points, URLs)
- Default checklist items stored in DEFAULT_CHECKLIST dict in routes.py
- Home location set in utils.py: Bay Area, CA (37.5585, -122.2711)
- City coordinates cache in utils.py for common tournament cities
- SESSION_SECRET environment variable required for secure sessions
- DATABASE_URL environment variable for PostgreSQL connection

## User Preferences
- Team: UVAC Urban Volleyball 15 TS (G15UVBAC1NC), Hyacinth Division
- Tracks volleyball tournaments (NCVA events, Power League)
- Data includes hotel/car booking logistics
- Home base: Bay Area, CA
- Multiple parents need login access to view shared team schedule
- Wants travel checklists for tournament preparation
