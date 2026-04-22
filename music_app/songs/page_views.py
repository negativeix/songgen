from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import User as SongsUser, Song


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
        songs = list(songs_user.library.songs.order_by('-created_at'))
    except Exception:
        songs = []
    return render(request, 'library.html', {
        'songs_user': songs_user,
        'songs': songs,
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
    song = get_object_or_404(Song, public_token=token, visibility='PUBLIC')
    return render(request, 'public_share.html', {'song': song})


def how_to_view(request):
    return render(request, 'how_to.html')
