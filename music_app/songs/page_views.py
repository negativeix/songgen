from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import User as SongsUser, Song, Folder, SiteConfig, AuditLog
from .models.enums import SongVisibility, SongStatus
from .decorators import admin_required


def _get_songs_user(request):
    if not request.user.is_authenticated:
        return None
    songs_user_id = request.session.get('songs_user_id')
    if songs_user_id:
        try:
            return SongsUser.objects.get(userId=songs_user_id)
        except SongsUser.DoesNotExist:
            pass
    try:
        profile = SongsUser.objects.get(email=request.user.email)
        request.session['songs_user_id'] = str(profile.userId)
        return profile
    except SongsUser.DoesNotExist:
        return None


def landing_view(request):
    if request.user.is_authenticated:
        return redirect('/library/')
    return render(request, 'landing.html')


@login_required
def library_view(request):
    songs_user = _get_songs_user(request)
    if not songs_user:
        return redirect('/')

    try:
        library = songs_user.library
    except Exception:
        return render(request, 'library.html', {
            'songs_user': songs_user, 'songs': [], 'folders': [], 'selected_folder': None,
        })

    # Top-level folders for the sidebar
    top_folders = list(Folder.objects.filter(library=library, parent=None).prefetch_related('subfolders', 'songs'))

    # Filter by folder if ?folder=<id> is provided
    folder_id = request.GET.get('folder')
    selected_folder = None
    if folder_id:
        try:
            selected_folder = Folder.objects.get(pk=folder_id, library=library)
            songs = list(selected_folder.songs.order_by('-created_at'))
        except (Folder.DoesNotExist, Exception):
            songs = list(library.songs.order_by('-created_at'))
    else:
        songs = list(library.songs.order_by('-created_at'))

    return render(request, 'library.html', {
        'songs_user': songs_user,
        'songs': songs,
        'folders': top_folders,
        'selected_folder': selected_folder,
        'all_folders': list(Folder.objects.filter(library=library).order_by('name')),
    })


@login_required
def generate_view(request):
    songs_user = _get_songs_user(request)
    if not songs_user:
        return redirect('/')

    prefill = {}
    from_id = request.GET.get('from')
    if from_id:
        try:
            source = Song.objects.get(songId=from_id, library=songs_user.library)
            prefill = {
                'prompt':      source.prompt      or '',
                'title':       source.title       or '',
                'genre':       source.genre       or '',
                'mood':        source.mood        or '',
                'vocal_style': source.vocal_style or '',
                'lyrics':      source.lyrics      or '',
                'duration':    str(source.duration) if source.duration else '',
            }
        except Song.DoesNotExist:
            pass

    return render(request, 'generate.html', {
        'songs_user': songs_user,
        'prefill': prefill,
    })


@login_required
def song_detail_view(request, song_id):
    songs_user = _get_songs_user(request)
    if not songs_user:
        return redirect('/')
    try:
        song = get_object_or_404(Song, songId=song_id, library=songs_user.library)
    except Exception:
        return redirect('/library/')
    return render(request, 'song_detail.html', {
        'song': song,
        'songs_user': songs_user,
    })


def public_share_page_view(request, token):
    from django.http import Http404
    try:
        song = Song.objects.get(public_token=token)
    except Song.DoesNotExist:
        raise Http404
    if song.visibility != SongVisibility.PUBLIC:
        return render(request, 'private_song.html', status=403)
    return render(request, 'public_share.html', {'song': song})


def how_to_view(request):
    return render(request, 'how_to.html')


@admin_required
def admin_dashboard_view(request):
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings

    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    per_user = []
    for user in SongsUser.objects.all().order_by('email'):
        try:
            lib = user.library
        except Exception:
            continue
        total = Song.objects.filter(library=lib).count()
        success = Song.objects.filter(library=lib, status=SongStatus.SUCCESS).count()
        recent = Song.objects.filter(library=lib, created_at__gte=last_24h).count()
        per_user.append({
            "user": user,
            "total_songs": total,
            "success_count": success,
            "last_24h": recent,
        })

    public_songs = Song.objects.filter(
        visibility=SongVisibility.PUBLIC
    ).select_related('library__user').order_by('-created_at')

    quota_limit = SiteConfig.get_int('max_songs_per_day', default=10)
    recent_audit = AuditLog.objects.order_by('-timestamp').select_related()[:50]

    return render(request, 'admin_dashboard.html', {
        "active_strategy": getattr(settings, 'GENERATOR_STRATEGY', 'mock'),
        "total_songs": Song.objects.count(),
        "total_users": SongsUser.objects.count(),
        "songs_last_24h": Song.objects.filter(created_at__gte=last_24h).count(),
        "success_songs": Song.objects.filter(status=SongStatus.SUCCESS).count(),
        "public_songs_count": public_songs.count(),
        "per_user": per_user,
        "public_songs": public_songs,
        "quota_limit": quota_limit,
        "recent_audit": recent_audit,
        "songs_user": _get_songs_user(request),
    })
