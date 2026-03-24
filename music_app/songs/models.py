from django.db import models
import uuid

class UserStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class GenreType(models.TextChoices):
    POP = "POP", "Pop"
    JAZZ = "JAZZ", "Jazz"
    ROCK = "ROCK", "Rock"
    HIPHOP = "HIPHOP", "HipHop"
    CLASSICAL = "CLASSICAL", "Classical"
    ROMANCE = "ROMANCE", "Romance"


class User(models.Model):
    userId = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=UserStatus.choices)

    def __str__(self):
        return self.username


class Library(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="library")

    def __str__(self):
        return f"{self.user.username}'s Library"


class Song(models.Model):
    songId = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    artist = models.CharField(max_length=100)
    duration = models.IntegerField()
    genre = models.CharField(max_length=20, choices=GenreType.choices)

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="songs")

    def __str__(self):
        return self.title


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