from django.db import models


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


class SongStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    TEXT_SUCCESS = "TEXT_SUCCESS", "Text Success"
    FIRST_SUCCESS = "FIRST_SUCCESS", "First Success"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


class SongVisibility(models.TextChoices):
    PRIVATE = "PRIVATE", "Private"
    PUBLIC = "PUBLIC", "Public"