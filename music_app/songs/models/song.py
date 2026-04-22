import uuid

from django.db import models

from .library import Library
from .enums import GenreType, SongStatus, SongVisibility


class Song(models.Model):
    songId = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    artist = models.CharField(max_length=100, blank=True, default="")
    duration = models.IntegerField(null=True, blank=True)
    genre = models.CharField(max_length=20, choices=GenreType.choices, blank=True, default="")

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="songs")

    # Generation workflow fields
    status = models.CharField(
        max_length=20, choices=SongStatus.choices, default=SongStatus.PENDING
    )
    task_id = models.CharField(max_length=200, null=True, blank=True)
    audio_url = models.URLField(max_length=500, null=True, blank=True)

    # Generation inputs
    prompt = models.TextField(null=True, blank=True)
    mood = models.CharField(max_length=100, null=True, blank=True)
    vocal_style = models.CharField(max_length=100, null=True, blank=True)
    lyrics = models.TextField(null=True, blank=True)

    # Visibility / sharing
    visibility = models.CharField(
        max_length=20, choices=SongVisibility.choices, default=SongVisibility.PRIVATE
    )
    public_token = models.UUIDField(null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.title
