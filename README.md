# SongGen
## Repository Structure

```id="9s4n2a"
songgen/            # root repository
└── music_app/      # Django project root
    ├── music_app/  # project settings (settings.py, urls.py)
    ├── songs/      # app (models, views, URLs, migrations)
    ├── manage.py
    └── db.sqlite3
```

## Prerequisites

* Python 3.10+
* pip

## Setup Instructions

### 1. Clone the repository

```bash id="xj9a0m"
git clone https://github.com/negativeix/songgen.git
cd songgen/music_app
```

### 2. Setup virtual environment

```bash id="w3h2qk"
python -m venv .venv
```

Activate:

* Windows:

```bash id="9mcz1o"
.venv\Scripts\activate
```

* macOS/Linux:

```bash id="d0e4pl"
source .venv/bin/activate
```

### 3. Install dependencies

```bash id="u6yxyt"
pip install django
```

### 4. Run the project

```bash id="6tcl0d"
python manage.py migrate
python manage.py runserver
```

Server runs at: http://127.0.0.1:8000

## Domain Model

### Entities

* User
* Library
* Song
* Folder

### Relationships

* User has one Library (One-to-One)
* Library contains many Songs (One-to-Many)
* Library contains many Folders (One-to-Many)
* Folder supports nested structure (recursive)
* Folder contains multiple Songs (Many-to-Many)

## API Endpoints

CRUD operations are implemented using Django views and return JSON responses.

* GET `/songs/` → Retrieve all songs
* POST `/songs/create/` → Create a new song
* PUT `/songs/<id>/update/` → Update a song
* DELETE `/songs/<id>/delete/` → Delete a song

## Testing

All endpoints are tested using Postman by sending JSON requests.

Example request (Create Song):

```json id="6s5n4b"
{
  "title": "Test Song",
  "artist": "AI Generator",
  "duration": 120,
  "genre": "POP"
}
```

