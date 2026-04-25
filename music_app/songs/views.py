import json
import logging
import random
import uuid

from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Song, Library, User, Folder, SiteConfig, AuditLog
from .models.enums import SongStatus, SongVisibility
from .generators import GenerationRequest, get_generator
from .decorators import admin_required, _resolve_songs_user

logger = logging.getLogger('songs')


def _active_strategy():
    from django.conf import settings
    return getattr(settings, 'GENERATOR_STRATEGY', 'mock')


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
    Enforces per-user daily quota from SiteConfig (NFR-17).
    Writes AuditLog entries at each stage (NFR-19).
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
            user_obj = User.objects.get(pk=user_id)
            library = user_obj.library
        except (User.DoesNotExist, Library.DoesNotExist):
            return JsonResponse({"error": "User not found"}, status=404)

    if library is None:
        library = Library.objects.first()
        if library is None:
            return JsonResponse({"error": "No library found. Create a user first."}, status=400)

    user_email = library.user.email if hasattr(library, 'user') else 'unknown'

    # Parse requested duration
    raw_duration = data.get("duration")
    requested_duration = None
    if raw_duration:
        try:
            requested_duration = int(raw_duration)
            if requested_duration <= 0:
                requested_duration = None
        except (TypeError, ValueError):
            requested_duration = None

    # ── NFR-17: per-user daily quota ─────────────────────────────────────────
    max_per_day = SiteConfig.get_int('max_songs_per_day', default=10)
    if max_per_day > 0:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        songs_today = Song.objects.filter(library=library, created_at__gte=today_start).count()
        if songs_today >= max_per_day:
            AuditLog.objects.create(
                user_email=user_email,
                action='quota_exceeded',
                strategy=_active_strategy(),
                detail=f'Daily limit {max_per_day} reached ({songs_today} songs today)',
            )
            logger.warning('Quota exceeded for %s: %d/%d songs today', user_email, songs_today, max_per_day)
            return JsonResponse(
                {
                    "error": f"Daily generation limit reached ({max_per_day} songs per day). Try again tomorrow.",
                    "quota_limit": max_per_day,
                    "quota_used": songs_today,
                },
                status=429,
            )

    # ── NFR-03: no duplicate concurrent generation ───────────────────────────
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
        duration=requested_duration,
    )

    strategy_name = _active_strategy()

    # ── NFR-19: log generation start ────────────────────────────────────────
    AuditLog.objects.create(
        user_email=user_email,
        action='generate_started',
        song_id=song.songId,
        strategy=strategy_name,
        detail=f'prompt="{prompt[:120]}"',
    )
    logger.info('generate_started user=%s song=%s strategy=%s', user_email, song.songId, strategy_name)

    gen_request = GenerationRequest(
        prompt=prompt,
        title=song.title,
        genre=song.genre or None,
        mood=song.mood,
        vocal_style=song.vocal_style,
        lyrics=song.lyrics,
        instrumental=bool(data.get("instrumental", False)),
        duration=requested_duration,
    )

    try:
        generator = get_generator()
        result = generator.generate(gen_request)
    except Exception as exc:
        song.status = SongStatus.FAILED
        song.save()
        AuditLog.objects.create(
            user_email=user_email,
            action='generate_failed',
            song_id=song.songId,
            strategy=strategy_name,
            detail=f'exception: {exc}',
        )
        logger.error('generate_failed user=%s song=%s error=%s', user_email, song.songId, exc)
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
    song.save()

    # ── NFR-19: log generation outcome ──────────────────────────────────────
    if result.status == SongStatus.SUCCESS:
        outcome = 'generate_success'
    elif result.status == SongStatus.FAILED:
        outcome = 'generate_failed'
    else:
        outcome = 'generate_pending'

    detail = f'status={song.status}'
    if result.error:
        detail += f', error={result.error}'

    AuditLog.objects.create(
        user_email=user_email,
        action=outcome,
        song_id=song.songId,
        task_id=result.task_id or '',
        strategy=strategy_name,
        detail=detail,
    )
    logger.info('%s user=%s song=%s task=%s', outcome, user_email, song.songId, result.task_id)

    resp_data = {
        "song_id": str(song.songId),
        "task_id": result.task_id or "",
        "status": song.status,
        "audio_url": song.audio_url,
        "message": "Generation complete" if song.status == SongStatus.SUCCESS else "Generation started",
    }
    if result.error:
        resp_data["error"] = result.error
    return JsonResponse(resp_data)


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

    raw_dur = data.get("duration")
    regen_duration = None
    if raw_dur:
        try:
            regen_duration = int(raw_dur)
            if regen_duration <= 0:
                regen_duration = None
        except (TypeError, ValueError):
            pass

    gen_request = GenerationRequest(
        prompt=song.prompt or "",
        title=song.title,
        genre=song.genre or None,
        mood=song.mood,
        vocal_style=song.vocal_style,
        lyrics=song.lyrics,
        instrumental=bool(data.get("instrumental", False)),
        duration=regen_duration or song.duration,
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


def song_download(request, song_id):
    """
    GET /songs/<id>/download/
    Redirects to the audio_url for download. Owner or public song only (SRS §2.2.4).
    """
    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    # Access check: public songs are open to all; private songs need the owner
    if song.visibility != SongVisibility.PUBLIC:
        profile = _resolve_songs_user(request)
        if profile is None or song.library.user != profile:
            return JsonResponse({"error": "Forbidden"}, status=403)

    if not song.audio_url:
        return JsonResponse({"error": "Audio not yet available"}, status=404)

    return HttpResponseRedirect(song.audio_url)


@admin_required
def admin_metrics(request):
    """
    GET /songs/admin/metrics/
    Usage metrics — admin only (FR-22/23, NFR-19).
    """
    from datetime import timedelta

    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    per_user = []
    for user in User.objects.all().order_by('email'):
        try:
            lib = user.library
        except Exception:
            continue
        total = Song.objects.filter(library=lib).count()
        success = Song.objects.filter(library=lib, status=SongStatus.SUCCESS).count()
        last_24h_user = Song.objects.filter(library=lib, created_at__gte=last_24h).count()
        per_user.append({
            "user_id": str(user.userId),
            "email": user.email,
            "username": user.username,
            "total_songs": total,
            "success_count": success,
            "last_24h": last_24h_user,
            "is_admin": user.is_admin,
        })

    recent_audit = list(
        AuditLog.objects.order_by('-timestamp').values(
            'timestamp', 'user_email', 'action', 'song_id', 'task_id', 'strategy', 'detail'
        )[:50]
    )

    return JsonResponse({
        "active_strategy": _active_strategy(),
        "total_songs": Song.objects.count(),
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(status="ACTIVE").count(),
        "songs_generated_last_24h": Song.objects.filter(created_at__gte=last_24h).count(),
        "quota_limit": SiteConfig.get_int('max_songs_per_day', default=10),
        "songs_by_status": {
            s: Song.objects.filter(status=s).count()
            for s in ["PENDING", "SUCCESS", "FAILED", "TEXT_SUCCESS", "FIRST_SUCCESS"]
        },
        "songs_by_genre": {
            g: Song.objects.filter(genre=g).count()
            for g in ["POP", "JAZZ", "ROCK", "HIPHOP", "CLASSICAL", "ROMANCE"]
        },
        "public_songs": Song.objects.filter(visibility=SongVisibility.PUBLIC).count(),
        "per_user": per_user,
        "recent_audit": recent_audit,
    })


@csrf_exempt
@admin_required
def admin_config_update(request):
    """
    POST /songs/admin/config/
    Update a SiteConfig value at runtime — no redeploy needed (NFR-20).
    Body: { key, value }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _parse_json(request)
    key = (data.get("key") or "").strip()
    value = (data.get("value") or "").strip()

    if not key:
        return JsonResponse({"error": "key is required"}, status=400)

    # Whitelist allowed keys to prevent arbitrary config injection
    ALLOWED_KEYS = {"max_songs_per_day"}
    if key not in ALLOWED_KEYS:
        return JsonResponse({"error": f"Unknown config key '{key}'"}, status=400)

    obj, created = SiteConfig.objects.get_or_create(key=key, defaults={"value": value})
    if not created:
        obj.value = value
        obj.save()

    logger.info('admin_config_update key=%s value=%s by=%s', key, value, request.songs_user.email)
    AuditLog.objects.create(
        user_email=request.songs_user.email,
        action='config_updated',
        strategy=_active_strategy(),
        detail=f'{key}={value}',
    )

    return JsonResponse({"key": key, "value": obj.value, "updated": True})


# ── Pending songs (for global notification polling) ───────────────────────────

def song_pending_list(request):
    """
    GET /songs/pending/
    Returns non-terminal songs for the current user's library.
    Used by base.html to poll for completion toasts on any page.
    """
    profile = _resolve_songs_user(request)
    if profile is None:
        return JsonResponse({"songs": []})
    try:
        library = profile.library
    except Library.DoesNotExist:
        return JsonResponse({"songs": []})

    qs = Song.objects.filter(library=library).exclude(
        status__in=[SongStatus.SUCCESS, SongStatus.FAILED]
    ).values("songId", "title", "status")

    return JsonResponse({
        "songs": [
            {"song_id": str(s["songId"]), "title": s["title"], "status": s["status"]}
            for s in qs
        ]
    })


# ── Admin: public share token management ──────────────────────────────────────

@csrf_exempt
@admin_required
def admin_token_regenerate(request, song_id):
    """
    POST /songs/admin/tokens/<song_id>/regenerate/
    Rotate the public_token on a shared song; old share links break.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    song.public_token = uuid.uuid4()
    song.save()
    return JsonResponse({
        "song_id": str(song.songId),
        "public_token": str(song.public_token),
        "message": "Token regenerated; old public links are now broken.",
    })


@csrf_exempt
@admin_required
def admin_token_revoke(request, song_id):
    """
    POST /songs/admin/tokens/<song_id>/revoke/
    Force the song back to PRIVATE and clear its public_token.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        song = Song.objects.get(pk=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    song.visibility = SongVisibility.PRIVATE
    song.public_token = None
    song.save()
    return JsonResponse({
        "song_id": str(song.songId),
        "visibility": song.visibility,
        "message": "Sharing revoked.",
    })


# ── Folder: song assignment ───────────────────────────────────────────────────

def _parse_json(request):
    try:
        return json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return {}


@csrf_exempt
def folder_add_song(request, folder_id):
    """POST /songs/folders/<id>/songs/add/ body {song_id}"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    profile = _resolve_songs_user(request)
    if profile is None:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    try:
        folder = Folder.objects.get(pk=folder_id, library=profile.library)
    except Folder.DoesNotExist:
        return JsonResponse({"error": "Folder not found"}, status=404)

    data = _parse_json(request)
    song_id = data.get("song_id")
    try:
        song = Song.objects.get(pk=song_id, library=profile.library)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Song not found"}, status=404)

    folder.songs.add(song)
    return JsonResponse({"folder_id": str(folder.folderId), "song_id": str(song.songId), "added": True})


@csrf_exempt
def folder_remove_song(request, folder_id):
    """POST /songs/folders/<id>/songs/remove/ body {song_id}"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    profile = _resolve_songs_user(request)
    if profile is None:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    try:
        folder = Folder.objects.get(pk=folder_id, library=profile.library)
    except Folder.DoesNotExist:
        return JsonResponse({"error": "Folder not found"}, status=404)

    data = _parse_json(request)
    song_id = data.get("song_id")
    try:
        song = Song.objects.get(pk=song_id, library=profile.library)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Song not found"}, status=404)

    folder.songs.remove(song)
    return JsonResponse({"folder_id": str(folder.folderId), "song_id": str(song.songId), "removed": True})


@csrf_exempt
def folder_move_song(request):
    """
    POST /songs/folders/songs/move/
    body {song_id, target_folder_id (nullable — null unassigns)}
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    profile = _resolve_songs_user(request)
    if profile is None:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    data = _parse_json(request)
    try:
        song = Song.objects.get(pk=data.get("song_id"), library=profile.library)
    except Song.DoesNotExist:
        return JsonResponse({"error": "Song not found"}, status=404)

    target_id = data.get("target_folder_id")
    # Remove from any current folders first
    song.folders.clear()
    if target_id:
        try:
            target = Folder.objects.get(pk=target_id, library=profile.library)
        except Folder.DoesNotExist:
            return JsonResponse({"error": "Target folder not found"}, status=404)
        target.songs.add(song)
        return JsonResponse({"song_id": str(song.songId), "target_folder_id": str(target.folderId)})

    return JsonResponse({"song_id": str(song.songId), "target_folder_id": None})


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
        profile = _resolve_songs_user(request)
        data = _parse_json(request)

        if profile:
            try:
                library = profile.library
            except Library.DoesNotExist:
                library = Library.objects.first()
        else:
            library = Library.objects.first()

        if library is None:
            return JsonResponse({"error": "No library found"}, status=400)

        parent = None
        parent_id = data.get("parent_id")
        if parent_id:
            try:
                parent = Folder.objects.get(pk=parent_id, library=library)
            except Folder.DoesNotExist:
                pass

        folder = Folder.objects.create(
            name=data.get("name") or "New Folder",
            library=library,
            parent=parent,
        )

        return JsonResponse({"message": "Folder created", "id": str(folder.folderId), "name": folder.name})


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
