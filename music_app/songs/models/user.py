from django.db import models
import uuid
from .enums import UserStatus

class User(models.Model):
    userId = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=UserStatus.choices)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.username