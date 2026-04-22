import json
import random
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Song, Library, User, Folder
from .models.enums import SongStatus, SongVisibility
from .generators import GenerationRequest, get_generator


# ── Prompt suggestions ────────────────────────────────────────────────────────

EXAMPLE_PROMPTS = [
    "An upbeat summer pop song about road trips and freedom",
    "A melancholic jazz ballad about rainy city nights",
    "An energetic hip-hop track about chasing your dreams",
    "A peaceful classical piece inspired by a mountain sunrise",
    "A romantic bossa nova song about a first meeting",
    "A heavy rock anthem about overcoming obstacles",
    "A dreamy lo-fi beat perfect for late-night studying",
    "A festive pop song celebrating friendship and memories",
    "A soulful R&B track about long-distance love",
    "An acoustic folk song about returning to your hometown",
]


def prompt_suggestions(request):
    """
    GET /songs/prompts/
    Returns example prompts to guide users (FR-07) and a shuffled random
    selection to inspire them (FR-08).
    """
    shuffled = EXAMPLE_PROMPTS.copy()
    random.shuffle(shuffled)
    return JsonResponse({
        "examples": EXAMPLE_PROMPTS,
        "suggested": shuffled[:3],
    })


# ── Song Generation ────────────────────────────────────────────────────────────

@csrf_exempt
def song_generate(request):
    """
    POST /songs/generate/
    Starts AI song generation and immediately saves a PENDING record (FR-21).
    Body: { prompt*, title, genre, mood, vocal_style, lyrics, instrumental, user_id }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return JsonResponse({"error": "prompt is required"}, status=400)

    # Resolve the user's library
    user_id = data.get("user_id")
    library = None
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
            library = user.library
        except (User.DoesNotExist, Library.DoesNotExist):
            return JsonResponse({"error": "User not found"}, status=404)

    if library is None:
        library = Library.objects.first()
        if library is None:
            return JsonResponse({"error": "No library found. Create a user first."}, status=400)

    # NFR-03: prevent duplicate concurrent generation per library
    if Song.objects.filter(library=library, status=SongStatus.PENDING).exists():
        return JsonResponse(
            {"error": "A generation is already in progress for this library"},
            status=409,
        )

    # Persist immediately as PENDING so no data is lost on crash (FR-21)
    song = Song.objects.create(
        title=data.get("title") or "Untitled",
        artist=data.get("vocal_style") or "",
        genre=data.get("genre") or "",
        library=library,
        status=SongStatus.PENDING,
        prompt=prompt,
        mood=data.get("mood"),
        vocal_style=data.get("vocal_style"),
        lyrics=data.get("lyrics"),
        visibility=SongVisibility.PRIVATE,
    )

    gen_request = GenerationRequest(
        prompt=prompt,
        title=song.title,
        genre=song.genre or None,
        mood=song.mood,
        vocal_style=song.vocal_style,
        lyrics=song.lyrics,
        instrumental=bool(data.get("instrumental", False)),
    )

    try:
        generator = get_generator()
        result = generator.generate(gen_request)
    except Exception as exc:
        song.status = SongStatus.FAILED
        song.save()
        return JsonResponse(
            {"error": f"Generator error: {exc}", "song_id": str(song.songId)},
            status=500,
        )

    # Update song with the result from the strategy (FR-20: graceful failure)
    song.task_id = result.task_id
    song.status = result.status
    if result.status == SongStatus.SUCCESS:
        song.audio_url = result.audio_url
        if result.duration:
            song.duration = result.duration
        if result.title:
            song.title = result.title
    elif result.status == SongStatus.FAILED:
        pass  # status already set to FAILED

    song.save()

    return JsonResponse({
        "song_id": str(song.songId),
        "task_id": result.task_id or "",
        "status": song.status,
        "audio_url": song.audio_url,
        "message": "Generation complete" if song.status == SongStatus.SUCCESS else "Generation started",
    })


def song_status(request, song_id):
    """
    GET /songs/<id>/status/
    Returns current generation status. Polls the strategy if still in-progress (FR-09).
    """
    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    terminal_statuses = {SongStatus.SUCCESS, SongStatus.FAILED}
    if song.status not in terminal_statuses and song.task_id:
        try:
            generator = get_generator()
            result = generator.get_status(song.task_id)
            song.status = result.status
            if result.status == SongStatus.SUCCESS:
                song.audio_url = result.audio_url
                if result.duration:
                    song.duration = result.duration
                if result.title:
                    song.title = result.title
            song.save()
        except Exception:
            pass  # Return last known DB state on unexpected errors

    return JsonResponse({
        "song_id": str(song.songId),
        "status": song.status,
        "audio_url": song.audio_url,
        "title": song.title,
        "duration": song.duration,
    })


@csrf_exempt
def song_cancel(request, song_id):
    """
    POST /songs/<id>/cancel/
    Cancels a PENDING generation, keeping the song record (FR-21).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if song.status != SongStatus.PENDING:
        return JsonResponse({"error": "Song is not currently generating"}, status=400)

    song.status = SongStatus.FAILED
    song.save()
    return JsonResponse({"message": "Generation cancelled", "song_id": str(song.songId)})


@csrf_exempt
def song_regenerate(request, song_id):
    """
    POST /songs/<id>/regenerate/
    Re-runs generation for an existing song, optionally overriding the prompt (FR-15).
    Body (all optional): { prompt, genre, mood, vocal_style, lyrics, instrumental }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    try:
        data = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    # Apply overrides
    song.prompt = data.get("prompt", song.prompt)
    song.mood = data.get("mood", song.mood)
    song.genre = data.get("genre", song.genre)
    song.vocal_style = data.get("vocal_style", song.vocal_style)
    song.lyrics = data.get("lyrics", song.lyrics)
    song.status = SongStatus.PENDING
    song.audio_url = None
    song.task_id = None
    song.save()

    gen_request = GenerationRequest(
        prompt=song.prompt or "",
        title=song.title,
        genre=song.genre or None,
        mood=song.mood,
        vocal_style=song.vocal_style,
        lyrics=song.lyrics,
        instrumental=bool(data.get("instrumental", False)),
    )

    try:
        generator = get_generator()
        result = generator.generate(gen_request)
    except Exception as exc:
        song.status = SongStatus.FAILED
        song.save()
        return JsonResponse(
            {"error": f"Generator error: {exc}", "song_id": str(song.songId)},
            status=500,
        )

    song.task_id = result.task_id
    song.status = result.status
    if result.status == SongStatus.SUCCESS:
        song.audio_url = result.audio_url
        if result.duration:
            song.duration = result.duration
        if result.title:
            song.title = result.title
    song.save()

    return JsonResponse({
        "song_id": str(song.songId),
        "task_id": result.task_id or "",
        "status": song.status,
        "audio_url": song.audio_url,
    })


@csrf_exempt
def song_visibility(request, song_id):
    """
    POST /songs/<id>/visibility/
    Toggles song between PRIVATE and PUBLIC. On first PUBLIC, mints a public_token (FR-16/17).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if song.visibility == SongVisibility.PRIVATE:
        song.visibility = SongVisibility.PUBLIC
        if not song.public_token:
            song.public_token = uuid.uuid4()
    else:
        song.visibility = SongVisibility.PRIVATE

    song.save()

    public_url = None
    if song.visibility == SongVisibility.PUBLIC:
        public_url = f"/songs/public/{song.public_token}/"

    return JsonResponse({
        "song_id": str(song.songId),
        "visibility": song.visibility,
        "public_url": public_url,
    })


def song_public(request, token):
    """
    GET /songs/public/<token>/
    Returns minimal song data for public playback — no authentication required (FR-18/19).
    """
    try:
        song = Song.objects.get(public_token=token, visibility=SongVisibility.PUBLIC)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    return JsonResponse({
        "song_id": str(song.songId),
        "title": song.title,
        "artist": song.artist,
        "genre": song.genre,
        "duration": song.duration,
        "audio_url": song.audio_url,
    })


def admin_metrics(request):
    """
    GET /songs/admin/metrics/
    Usage metrics for the product owner (FR-22/23).
    """
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    return JsonResponse({
        "active_strategy": getattr(__import__('django.conf', fromlist=['settings']).settings, 'GENERATOR_STRATEGY', 'mock'),
        "total_songs": Song.objects.count(),
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(status="ACTIVE").count(),
        "songs_generated_last_24h": Song.objects.filter(created_at__gte=last_24h).count(),
        "songs_by_status": {
            s: Song.objects.filter(status=s).count()
            for s in ["PENDING", "SUCCESS", "FAILED", "TEXT_SUCCESS", "FIRST_SUCCESS"]
        },
        "songs_by_genre": {
            g: Song.objects.filter(genre=g).count()
            for g in ["POP", "JAZZ", "ROCK", "HIPHOP", "CLASSICAL", "ROMANCE"]
        },
        "public_songs": Song.objects.filter(visibility=SongVisibility.PUBLIC).count(),
    })


# ── Song CRUD (from Exercise 3) ────────────────────────────────────────────────

def song_list(request):
    songs = list(Song.objects.values())
    return JsonResponse(songs, safe=False)


@csrf_exempt
def song_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        library = Library.objects.first()
        if library is None:
            return JsonResponse({"error": "No library found"}, status=400)

        song = Song.objects.create(
            title=data.get("title"),
            artist=data.get("artist", ""),
            duration=data.get("duration"),
            genre=data.get("genre", ""),
            library=library,
            status=SongStatus.SUCCESS,
        )

        return JsonResponse({"message": "Song created", "id": str(song.songId)})


@csrf_exempt
def song_update(request, song_id):
    if request.method == "PUT":
        try:
            song = Song.objects.get(pk=song_id)
        except Song.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        data = json.loads(request.body)

        song.title = data.get("title", song.title)
        song.artist = data.get("artist", song.artist)
        song.duration = data.get("duration", song.duration)
        song.genre = data.get("genre", song.genre)
        song.save()

        return JsonResponse({"message": "Song updated"})


@csrf_exempt
def song_delete(request, song_id):
    if request.method == "DELETE":
        try:
            song = Song.objects.get(pk=song_id)
        except Song.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        song.delete()
        return JsonResponse({"message": "Song deleted"})


# ── User CRUD (from Exercise 3) ────────────────────────────────────────────────

def user_list(request):
    users = list(User.objects.values())
    return JsonResponse(users, safe=False)


@csrf_exempt
def user_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        user = User.objects.create(
            username=data.get("username"),
            email=data.get("email"),
            status=data.get("status", "ACTIVE"),
        )

        # Auto-create library for the new user (FR-02 analogue)
        Library.objects.get_or_create(user=user)

        return JsonResponse({"message": "User created", "id": str(user.userId)})


@csrf_exempt
def user_update(request, user_id):
    if request.method == "PUT":
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        data = json.loads(request.body)

        user.username = data.get("username", user.username)
        user.email = data.get("email", user.email)
        user.status = data.get("status", user.status)
        user.save()

        return JsonResponse({"message": "User updated"})


@csrf_exempt
def user_delete(request, user_id):
    if request.method == "DELETE":
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        user.delete()
        return JsonResponse({"message": "User deleted"})


# ── Folder CRUD (from Exercise 3) ──────────────────────────────────────────────

def folder_list(request):
    folders = list(Folder.objects.values())
    return JsonResponse(folders, safe=False)


@csrf_exempt
def folder_create(request):
    if request.method == "POST":
        data = json.loads(request.body)

        library = Library.objects.first()
        if library is None:
            return JsonResponse({"error": "No library found"}, status=400)

        folder = Folder.objects.create(
            name=data.get("name"),
            library=library,
        )

        return JsonResponse({"message": "Folder created", "id": str(folder.folderId)})


@csrf_exempt
def folder_update(request, folder_id):
    if request.method == "PUT":
        try:
            folder = Folder.objects.get(pk=folder_id)
        except Folder.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        data = json.loads(request.body)

        folder.name = data.get("name", folder.name)
        folder.save()

        return JsonResponse({"message": "Folder updated"})


@csrf_exempt
def folder_delete(request, folder_id):
    if request.method == "DELETE":
        try:
            folder = Folder.objects.get(pk=folder_id)
        except Folder.DoesNotExist:
            return JsonResponse({"error": "Not found"}, status=404)

        folder.delete()
        return JsonResponse({"message": "Folder deleted"})
