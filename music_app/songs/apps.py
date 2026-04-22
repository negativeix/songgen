from django.apps import AppConfig


class SongsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'songs'

    def ready(self):
        try:
            import songs.signals  # noqa: F401
        except Exception:
            pass
