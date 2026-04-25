from .models import User as SongsUser


def songs_user(request):
    if not request.user.is_authenticated:
        return {"songs_user": None}
    songs_user_id = request.session.get("songs_user_id")
    profile = None
    if songs_user_id:
        try:
            profile = SongsUser.objects.get(userId=songs_user_id)
        except SongsUser.DoesNotExist:
            pass
    if profile is None:
        try:
            profile = SongsUser.objects.get(email=request.user.email)
            request.session["songs_user_id"] = str(profile.userId)
        except SongsUser.DoesNotExist:
            pass
    return {"songs_user": profile}
