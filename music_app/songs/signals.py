from django.dispatch import receiver

try:
    from allauth.account.signals import user_logged_in

    @receiver(user_logged_in)
    def ensure_songs_profile(sender, request, user, **kwargs):
        from .models import User as SongsUser, Library

        profile = SongsUser.objects.filter(email=user.email).first()
        if not profile:
            base = (user.username or user.email.split('@')[0])[:48]
            username = base
            counter = 1
            while SongsUser.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            profile = SongsUser.objects.create(
                email=user.email,
                username=username,
                status='ACTIVE',
            )

        Library.objects.get_or_create(user=profile)
        request.session['songs_user_id'] = str(profile.userId)

except ImportError:
    pass
