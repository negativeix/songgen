from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect

from .models import User as SongsUser


def _resolve_songs_user(request):
    if not request.user.is_authenticated:
        return None
    songs_user_id = request.session.get('songs_user_id')
    if songs_user_id:
        try:
            return SongsUser.objects.get(userId=songs_user_id)
        except SongsUser.DoesNotExist:
            pass
    try:
        return SongsUser.objects.get(email=request.user.email)
    except SongsUser.DoesNotExist:
        return None


def admin_required(view_func):
    """Allow access only to authenticated users whose songs.User profile has is_admin=True."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = _resolve_songs_user(request)
        if profile is None or not profile.is_admin:
            # JSON API paths → 403; page views → redirect to library
            if request.headers.get('Accept', '').startswith('application/json') \
               or request.path.startswith('/songs/'):
                return JsonResponse({'error': 'Admin access required'}, status=403)
            return redirect('/library/')
        request.songs_user = profile
        return view_func(request, *args, **kwargs)
    return wrapper
