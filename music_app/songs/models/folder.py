from django.db import models
import uuid
from .library import Library
from .song import Song

class Folder(models.Model):
    folderId = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="folders")

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subfolders'
    )

    songs = models.ManyToManyField(Song, related_name="folders", blank=True)

    def __str__(self):
        return self.name