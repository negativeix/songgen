from django.db import models
import uuid
from .library import Library
from .enums import GenreType

class Song(models.Model):
    songId = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    artist = models.CharField(max_length=100)
    duration = models.IntegerField()
    genre = models.CharField(max_length=20, choices=GenreType.choices)

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="songs")

    def __str__(self):
        return self.title