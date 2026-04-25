import logging

from django.dispatch import receiver

logger = logging.getLogger('songs.auth')

# ── OAuth login → auto-provision songs.User + Library ──────────────────────

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


# ── NFR-10: Log authentication failures ────────────────────────────────────

# Django's built-in signal: fires when ModelBackend rejects credentials.
# This covers any direct username/password attempt that fails.
try:
    from django.contrib.auth.signals import user_login_failed

    @receiver(user_login_failed)
    def log_login_failed(sender, credentials, request, **kwargs):
        username = credentials.get('username') or credentials.get('email') or '<unknown>'
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '<unknown>')
        ) if request else '<unknown>'
        logger.warning(
            'AUTH_FAILURE username=%s ip=%s',
            username,
            ip,
        )

except ImportError:
    pass


# allauth social-account login error (OAuth flow failure, e.g. user denies consent).
try:
    from allauth.socialaccount.signals import login_error as social_login_error

    @receiver(social_login_error)
    def log_social_login_error(sender, request, exception, **kwargs):
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', '<unknown>')
        ) if request else '<unknown>'
        logger.warning(
            'SOCIAL_AUTH_FAILURE ip=%s exception=%s',
            ip,
            exception,
        )

except (ImportError, Exception):
    # Signal may not exist in all allauth versions; safe to skip.
    pass
