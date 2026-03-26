from django.db import models
import uuid
from .user import User

class Library(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="library")

    def __str__(self):
        return f"{self.user.username}'s Library"