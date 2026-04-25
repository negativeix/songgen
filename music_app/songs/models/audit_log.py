from django.db import models


class AuditLog(models.Model):
    """Immutable record of AI usage events. One row per significant action."""
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user_email = models.CharField(max_length=254, db_index=True)
    action = models.CharField(max_length=60)
    song_id = models.UUIDField(null=True, blank=True)
    task_id = models.CharField(max_length=200, blank=True)
    strategy = models.CharField(max_length=50, blank=True)
    detail = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user_email} — {self.action}"
