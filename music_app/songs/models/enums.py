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