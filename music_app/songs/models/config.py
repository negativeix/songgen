from django.db import models


class SiteConfig(models.Model):
    """Runtime-adjustable site settings. Change values in the admin panel — no redeploy needed."""
    key = models.CharField(max_length=100, primary_key=True)
    value = models.CharField(max_length=500)
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Site Config"
        verbose_name_plural = "Site Config"

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_int(cls, key, default=0):
        raw = cls.get(key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
