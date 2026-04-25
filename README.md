# SongGen — AI Music Generation Platform

Web-based AI music generation platform built with **Django 5.2**.  
Describe a song in plain text and SongGen generates it — with genre, mood, vocals, and optional custom lyrics. Songs are saved to a personal library, shareable via public links, and manageable through an admin dashboard.

The generation backend uses the **Strategy Pattern**: swap between an instant mock generator (no API key needed) and the real Suno AI API by changing a single environment variable.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Environment Setup](#environment-setup)
4. [Database Setup](#database-setup)
5. [Running the Project](#running-the-project)
6. [Running Tests](#running-tests)
7. [Key Features](#key-features)
8. [Pages](#pages)
9. [API Endpoints](#api-endpoints)
10. [Admin Dashboard](#admin-dashboard)
11. [Architecture](#architecture)
12. [Notes and Limitations](#notes-and-limitations)

---

## Prerequisites

| Requirement | Version | 
|---|---|
| Python | 3.11 or later |
| pip | bundled with Python |
| SQLite | bundled with Python |
| MySQL / MariaDB | 8.0+ / 10.6+ |
| Git | any recent version |


---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/negativeix/songgen
cd songgen
```

The directory structure after cloning:

```
songgen/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── music_app/
    ├── manage.py
    ├── db.sqlite3          ← created after first migration
    ├── templates/
    ├── music_app/          ← Django project settings
    └── songs/              ← main application
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

| Package | Purpose |
|---|---|
| `django>=5.2` | Web framework |
| `django-allauth[google]>=65.0` | Google OAuth sign-in |
| `requests>=2.31` | HTTP calls to the Suno API |
| `python-dotenv>=1.0` | Loads `.env` into the environment |
| `mysqlclient>=2.2` | MySQL driver (only used if `DB_ENGINE=mysql`) |

> **mysqlclient system libraries** — only needed if you use MySQL. On macOS: `brew install mysql-client pkg-config`. On Ubuntu/Debian: `sudo apt install default-libmysqlclient-dev`. Skip this if you are using SQLite.

---

## Environment Setup

### 1. Create your `.env` file

The `.env` file lives at the root of the repository (next to `requirements.txt`), **not** inside `music_app/`.

```bash
cp .env.example .env
```

### 2. Fill in `.env`

```env
# ── Django Core ──────────────────────────────────────────────────────────────
SECRET_KEY=django-insecure-replace-this-with-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# ── Database ──────────────────────────────────────────────────────────────────
# Leave DB_ENGINE unset (or set to sqlite3) for local development — no extra setup needed.
# Set to django.db.backends.mysql for MySQL/MariaDB.
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=songgen
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306

# ── Google OAuth (django-allauth) ─────────────────────────────────────────────
# Create credentials at https://console.cloud.google.com/
# Authorized redirect URI: http://127.0.0.1:8000/accounts/google/callback/
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# ── Strategy Pattern ──────────────────────────────────────────────────────────
# mock → instant offline generation, no API key required (default)
# suno → real Suno AI API, requires SUNO_API_KEY below
GENERATOR_STRATEGY=mock

# ── Suno API ──────────────────────────────────────────────────────────────────
# Obtain a key at https://api.sunoapi.org — NEVER commit this value
SUNO_API_KEY=
```

### 3. Google OAuth credentials

Google OAuth is required for user login in both mock and Suno modes.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth 2.0 Client ID** (Application type: **Web application**).
3. Under **Authorized redirect URIs**, add:
   ```
   http://127.0.0.1:8000/accounts/google/callback/
   ```
4. Copy the **Client ID** and **Client Secret** into `.env`.

### 4. Suno API key (only for real generation)

1. Sign up at [https://api.sunoapi.org](https://api.sunoapi.org) and obtain an API key.
2. Set `SUNO_API_KEY=<your-key>` in `.env`.
3. Set `GENERATOR_STRATEGY=suno`.

---

## Database Setup

All `manage.py` commands must be run from inside the `music_app/` directory.

```bash
cd music_app
```

### SQLite (default — no extra configuration needed)

```bash
python manage.py migrate
```

This creates `music_app/db.sqlite3` and sets up all tables including songs, users, libraries, folders, audit logs, and allauth social account tables.

### MySQL / MariaDB (optional)

1. Create the database:
   ```sql
   CREATE DATABASE songgen CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. In `.env`, set:
   ```env
   DB_ENGINE=django.db.backends.mysql
   DB_NAME=songgen
   DB_USER=your_mysql_user
   DB_PASSWORD=your_mysql_password
   DB_HOST=127.0.0.1
   DB_PORT=3306
   ```
3. Run migrations:
   ```bash
   python manage.py migrate
   ```

### Configure the Django Site record

allauth requires a `Site` record matching `SITE_ID=3` in `settings.py`. After migrating, run:

```bash
python manage.py shell
```

```python
from django.contrib.sites.models import Site
site, _ = Site.objects.get_or_create(id=3)
site.domain = "127.0.0.1:8000"
site.name = "SongGen"
site.save()
```

> If your database already has a Site with a different ID (visible under `/admin/sites/`), update `SITE_ID` in `music_app/music_app/settings.py` to match, then re-run the snippet above.

### Grant admin access (optional)

The in-app admin dashboard at `/admin-dashboard/` uses a **custom `is_admin` field** on the app's `songs.User` model — separate from Django's `is_staff`. To grant access, the user must have signed in with Google at least once (so their profile exists), then run:

```bash
python manage.py grant_admin their@email.com
```

Expected output:
```
Granted admin to their@email.com (is_admin=True)
```

To revoke:
```bash
python manage.py grant_admin their@email.com --revoke
```

After granting, the **⚙ Admin** link appears in the top navigation bar and `/admin-dashboard/` becomes accessible.

> **Note:** Django's `/admin/` panel (separate) still requires `is_staff=True` via `createsuperuser`. The two are independent.

### Create a Django superuser (optional)

Gives access to Django's built-in `/admin/` panel:

```bash
python manage.py createsuperuser
```

---

## Running the Project

All commands from inside `music_app/`.

### Mock mode — instant generation, no API key needed

```bash
# GENERATOR_STRATEGY=mock is the default
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and sign in with Google.  
Songs generate instantly and return a placeholder audio URL. Use this for development and testing.

### Suno mode — real AI generation

```bash
# In .env:
#   GENERATOR_STRATEGY=suno
#   SUNO_API_KEY=your-key-here
python manage.py runserver
```

Generation takes 20–60 seconds. The page polls automatically — no manual refresh is needed. A toast notification fires when the song is ready, from any page.

## Key Features

| Feature | Description |
|---|---|
| **Text-to-music generation** | Free-text prompt with optional genre, mood, vocal style, duration, and custom lyrics |
| **Instrumental mode** | Toggle to generate music without vocals |
| **Personal library** | Songs auto-saved; organise into nested folders with drag-and-drop |
| **Public sharing** | Toggle any song public; shareable link works without login |
| **Song download** | Direct download of generated audio for owners and public songs |
| **Regenerate** | Pre-fills the generate form with the original song's settings |
| **Admin dashboard** | Per-user metrics, audit log, daily quota control, token management |
| **Daily quota** | Configurable per-day generation limit (`max_songs_per_day`, default: 10) |
| **Theme toggle** | Dark (dark green) / light (soft white) mode, persisted in `localStorage`, anti-FOUC |
| **Cross-page notifications** | Global polling notifies you when any song finishes, from any page |
| **Strategy Pattern** | Swap `mock` ↔ `suno` with one env variable, zero code changes |
| **Google OAuth** | Sign in with Google — no passwords, auto-creates library on first login |

---

## Pages

| URL | Description | Auth required |
|---|---|---|
| `/` | Landing page / sign-in | Public |
| `/library/` | Personal song library with folder tree | Yes |
| `/generate/` | Generate a new song | Yes |
| `/song/<id>/` | Song detail, player, download, regenerate | Yes |
| `/share/<token>/` | Public playback and download | Public |
| `/how-to/` | Usage guide and API reference | Public |
| `/admin-dashboard/` | Metrics, audit log, quota control, token management | Admin only |

---

## API Endpoints

All JSON endpoints are under `/songs/`. Authentication (session cookie) is required unless noted.

### Generation

| Method | Path | Description |
|---|---|---|
| `POST` | `/songs/generate/` | Submit a generation request |
| `GET` | `/songs/<id>/status/` | Poll generation status |
| `POST` | `/songs/<id>/regenerate/` | Regenerate with updated inputs |
| `POST` | `/songs/<id>/cancel/` | Cancel a pending generation |
| `POST` | `/songs/<id>/visibility/` | Toggle public / private |
| `GET` | `/songs/<id>/download/` | Download audio (owner or public song) |
| `GET` | `/songs/public/<token>/` | Public song data — no auth required |
| `GET` | `/songs/pending/` | List songs still generating (used by global poller) |
| `GET` | `/songs/prompts/` | Example prompt suggestions |

**Generation request body:**

```json
{
  "user_id": "uuid",
  "prompt": "An upbeat summer pop song about road trips",
  "title": "Summer Road Trip",
  "genre": "POP",
  "mood": "energetic",
  "vocal_style": "female alto",
  "lyrics": "",
  "instrumental": false,
  "duration": 120
}
```

**Generation response (SUCCESS):**

```json
{
  "status": "SUCCESS",
  "song_id": "uuid",
  "title": "Summer Road Trip",
  "audio_url": "https://cdn.sunoapi.org/...",
  "duration": 118
}
```

### Admin (admin only)

| Method | Path | Description |
|---|---|---|
| `GET` | `/songs/admin/metrics/` | Usage metrics and per-user breakdown |
| `POST` | `/songs/admin/config/` | Update runtime config (`max_songs_per_day`) |
| `POST` | `/songs/admin/tokens/<id>/regenerate/` | Rotate a song's public share token |
| `POST` | `/songs/admin/tokens/<id>/revoke/` | Revoke sharing and make the song private |

### Song / User / Folder CRUD

| Method | Path | Description |
|---|---|---|
| `GET` / `POST` | `/songs/` `/songs/create/` | List / create songs |
| `PUT` / `DELETE` | `/songs/<id>/update/` `/songs/<id>/delete/` | Update / delete song |
| `GET` / `POST` | `/songs/users/` `/songs/users/create/` | List / create users |
| `PUT` / `DELETE` | `/songs/users/<id>/update/` `/songs/users/<id>/delete/` | Update / delete user |
| `POST` | `/songs/folders/create/` | Create folder (pass `parent_id` for nesting) |
| `POST` | `/songs/folders/songs/move/` | Move song to a different folder |
| `PUT` / `DELETE` | `/songs/folders/<id>/update/` `/songs/folders/<id>/delete/` | Update / delete folder |

---

## Admin Dashboard

The in-app dashboard at `/admin-dashboard/` is separate from Django's built-in `/admin/`.

**Requires:** `is_admin=True` on the app's `songs.User` — grant it with:
```bash
python manage.py grant_admin their@email.com
```

| Section | What it shows |
|---|---|
| Active strategy | Which generator (`mock` or `suno`) is currently in use |
| Usage metrics | Total songs, success/failure counts, daily active users |
| Per-user breakdown | Generation count and quota usage per user |
| Audit log | Timestamped records for `generate_started`, `generate_success`, `quota_exceeded`, `config_updated` |
| Quota control | Update `max_songs_per_day` without restarting the server |
| Token management | Rotate or revoke public share tokens for any song |

---

## Architecture

### Strategy Pattern — Primary Design Artifact

```
SongGeneratorStrategy  (songs/generators/base.py)
        │  ABC with two abstract methods:
        │    generate(request: GenerationRequest) → GenerationResult
        │    get_status(task_id: str) → GenerationResult
        ├── MockSongGeneratorStrategy   (mock_strategy.py)  ← dev / test
        └── SunoSongGeneratorStrategy   (suno_strategy.py)  ← production
                        ▲
              get_generator()  (factory.py)
              — reads GENERATOR_STRATEGY from settings
              — single selection point, no if/else in views
```

Swap strategy at runtime with one environment variable — zero code changes:

```env
GENERATOR_STRATEGY=mock    # offline, deterministic, instant
GENERATOR_STRATEGY=suno    # real Suno AI API, async polling
```

### Factory Function

`get_generator()` in `factory.py` is the only place that maps a strategy name to a concrete class. No conditional logic is scattered across views — all views call `get_generator()` and receive the correct implementation.

### RBAC Decorator

`@admin_required` in `songs/decorators.py` is applied once at the view level. For JSON API routes it returns a 403 JSON response; for page routes it redirects to `/library/`.

### Signal-Based Auto-Provisioning

`songs/signals.py` listens for allauth's `user_signed_up` signal. On first Google login:
- A `songs.User` domain profile is created automatically.
- A `Library` is created for that user.

The OAuth layer never imports songs models; the songs app never calls allauth. They communicate only via Django signals.

### Repository Structure

```
songgen/
├── .env                    ← your secrets (not committed)
├── .env.example
├── requirements.txt
└── music_app/
    ├── manage.py
    ├── templates/
    │   ├── base.html               # CSS vars, theme toggle, global polling
    │   ├── landing.html
    │   ├── library.html            # Folder sidebar, drag-and-drop
    │   ├── generate.html
    │   ├── song_detail.html
    │   ├── public_share.html
    │   ├── private_song.html       # 403 page for revoked share links
    │   ├── admin_dashboard.html
    │   ├── how_to.html
    │   └── _folder_tree.html       # Recursive folder include
    ├── music_app/
    │   ├── settings.py
    │   └── urls.py
    └── songs/
        ├── generators/
        │   ├── base.py             # ABC SongGeneratorStrategy + dataclasses
        │   ├── mock_strategy.py    # MockSongGeneratorStrategy
        │   ├── suno_strategy.py    # SunoSongGeneratorStrategy
        │   └── factory.py          # get_generator() — single selection point
        ├── models/
        │   ├── user.py             # songs.User (is_admin flag)
        │   ├── library.py          # Library (one per user)
        │   ├── song.py             # Song (10 fields)
        │   ├── folder.py           # Folder (nested via parent FK)
        │   ├── config.py           # SiteConfig — runtime key/value store
        │   ├── audit_log.py        # AuditLog — immutable event records
        │   └── enums.py            # GenreType, SongStatus, SongVisibility
        ├── migrations/
        ├── context_processors.py   # Injects songs_user into every template
        ├── decorators.py           # @admin_required RBAC decorator
        ├── page_views.py           # HTML-rendering views
        ├── views.py                # JSON API views
        ├── signals.py              # Auto-provision songs.User on OAuth signup
        ├── urls.py
        └── tests.py                
```

---

## Notes and Limitations

- **SQLite is for development only.** Use MySQL/MariaDB for any deployed environment.

- **No audio file storage.** Audio URLs are served directly from Suno's CDN. The app stores the URL, not the file. In mock mode the URL is a static placeholder and will not play real audio.

- **Suno API is a third-party service.** Generation time, availability, and audio quality depend on Suno's infrastructure. The app polls for completion every 5 seconds and handles timeouts gracefully.

- **Google OAuth is the only authentication method.** There is no username/password login. A Google Cloud project with OAuth 2.0 credentials is required even for local development.

- **`SITE_ID=3` must match a row in the `django_site` table.** If you migrate into a fresh database and the auto-created Site has a different ID, either update `SITE_ID` in `settings.py` or create the correct Site record as shown in [Database Setup](#database-setup).

- **Daily quota** defaults to 10 songs per user per day. Adjust it at runtime via the admin dashboard, or from the shell:
  ```bash
  python manage.py shell -c "
  from songs.models import SiteConfig
  SiteConfig.objects.update_or_create(key='max_songs_per_day', defaults={'value': '20'})
  "
  ```

- **No email sending.** `ACCOUNT_EMAIL_VERIFICATION = 'none'` — allauth never sends verification emails.
