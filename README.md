# SongGen — AI Music Generation Platform

Web-based AI music generation platform built with Django 5.2.  
Implements the **Strategy Pattern** for AI providers and includes a full dark-mode frontend with Google OAuth.

---

## Features

- **Google OAuth login** via django-allauth (no passwords)
- **Text-to-music generation** using the Suno API (or mock for dev)
- **Personal library** — all songs auto-saved, organised in one place
- **Public sharing** — shareable link, no login required for listeners
- **Strategy Pattern** — swap mock ↔ Suno with one env variable
- **MySQL or SQLite** — configurable via environment

---

## Repository Structure

```
songgen/
├── .env.example          # Template for environment variables
├── .gitignore
├── requirements.txt
└── music_app/            # Django project root
    ├── manage.py
    ├── db.sqlite3
    ├── templates/        # HTML templates (dark-mode Tailwind UI)
    │   ├── base.html
    │   ├── landing.html
    │   ├── library.html
    │   ├── generate.html
    │   ├── song_detail.html
    │   ├── public_share.html
    │   └── how_to.html
    ├── music_app/        # Project settings & root URL conf
    └── songs/            # Main app
        ├── generators/   # Strategy Pattern
        │   ├── base.py           # ABC SongGeneratorStrategy
        │   ├── mock_strategy.py  # MockSongGeneratorStrategy
        │   ├── suno_strategy.py  # SunoSongGeneratorStrategy
        │   └── factory.py        # get_generator() factory
        ├── models/       # User, Library, Song, Folder
        ├── migrations/
        ├── page_views.py # Template-rendering views (frontend pages)
        ├── views.py      # JSON API endpoints
        ├── signals.py    # Auto-create songs.User on OAuth login
        ├── urls.py       # API URL patterns
        └── tests.py      # Unit & integration tests (11/11)
```

---

## Prerequisites

- Python 3.10+
- pip
- (Optional) MySQL 8.0+ with `mysqlclient` driver

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/negativeix/songgen.git
cd songgen
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example music_app/.env
```

Edit `music_app/.env` — see sections below.

### 4. Apply migrations and start

```bash
cd music_app
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000` — you'll see the landing page.

---

## Environment Variables

### SQLite (default, no extra config needed)

```env
GENERATOR_STRATEGY=mock
DEBUG=True
```

### MySQL

```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=songgen
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Create the database first: `CREATE DATABASE songgen CHARACTER SET utf8mb4;`

### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → **APIs & Services → Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Authorised redirect URI: `http://127.0.0.1:8000/accounts/google/callback/`
5. Copy Client ID and Secret to `.env`:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

### Suno API (production generation)

```env
GENERATOR_STRATEGY=suno
SUNO_API_KEY=your_suno_api_key_here
```

> **Security**: `.env` is in `.gitignore`. **Never commit credentials.**

---

## Strategy Pattern

```
┌────────────────────────────────────────┐
│         SongGeneratorStrategy          │  ← ABC (base.py)
│  + generate(request) → result          │
│  + get_status(task_id) → result        │
└──────────────┬─────────────────────────┘
               │ inherits
       ┌───────┴───────┐
       ▼               ▼
MockSongGenerator   SunoSongGenerator
Strategy            Strategy
(offline, instant)  (real API, async)
```

`factory.py` reads `GENERATOR_STRATEGY` from settings — one place, no scattered if/else.

---

## Pages

| URL | Description | Auth |
|-----|-------------|------|
| `/` | Landing / login | Public |
| `/library/` | Personal song library | Required |
| `/generate/` | Generate new song | Required |
| `/song/<id>/` | Song detail + player | Required |
| `/share/<token>/` | Public playback page | Public |
| `/how-to/` | Usage guide | Public |

---

## API Endpoints

### Generation

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/songs/generate/` | Start generation |
| `GET`  | `/songs/<id>/status/` | Poll status |
| `POST` | `/songs/<id>/cancel/` | Cancel |
| `POST` | `/songs/<id>/regenerate/` | Re-generate |
| `POST` | `/songs/<id>/visibility/` | Toggle public/private |
| `GET`  | `/songs/public/<token>/` | Public JSON (no auth) |
| `GET`  | `/songs/admin/metrics/` | Usage metrics |
| `GET`  | `/songs/prompts/` | Example prompts |

### CRUD

| Method | URL | Description |
|--------|-----|-------------|
| `GET`  | `/songs/` | List songs |
| `POST` | `/songs/create/` | Create song |
| `PUT`  | `/songs/<id>/update/` | Update song |
| `DELETE` | `/songs/<id>/delete/` | Delete song |
| `GET`  | `/songs/users/` | List users |
| `POST` | `/songs/users/create/` | Create user |
| `PUT`  | `/songs/users/<id>/update/` | Update user |
| `DELETE` | `/songs/users/<id>/delete/` | Delete user |

---

## Running Tests

```bash
cd music_app
python manage.py test songs.tests
```

Expected: `Ran 11 tests in ~0.0XXs — OK`

---

## SRS Functional Requirements (Exercise 4)

19 / 23 FRs covered = **82.6%** (threshold: ≥ 80% ✓)

| FR | Description | Status |
|----|-------------|--------|
| FR-01–04 | Google OAuth | ✓ (implemented in frontend) |
| FR-05 | Generate from text prompt | ✓ |
| FR-06 | Optional genre, mood, vocal style, lyrics | ✓ |
| FR-07 | Example prompts | ✓ |
| FR-08 | Random suggested prompts | ✓ |
| FR-09 | Real-time status polling | ✓ |
| FR-10 | Generate song | ✓ |
| FR-11 | Auto-save to library | ✓ |
| FR-12 | Play song | ✓ |
| FR-13 | Rename song | ✓ |
| FR-14 | Delete song | ✓ |
| FR-15 | Regenerate | ✓ |
| FR-16 | Private by default | ✓ |
| FR-17 | Public shareable link | ✓ |
| FR-18 | Public access without login | ✓ |
| FR-19 | Public playback page | ✓ |
| FR-20 | Graceful AI failure | ✓ |
| FR-21 | No data loss on interruption | ✓ |
| FR-22–23 | Admin metrics | ✓ |
