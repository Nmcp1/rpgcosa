from django.db import models
from django.contrib.auth.models import User
import uuid

class InvitationCode(models.Model):
    code = models.CharField(max_length=32, unique=True, editable=False)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitation_codes",
    )
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def can_be_used(self) -> bool:
        return self.is_active and self.uses < self.max_uses

    def register_use(self):
        self.uses += 1
        if self.uses >= self.max_uses:
            self.is_active = False
        self.save(update_fields=["uses", "is_active"])

    def __str__(self):
        return f"{self.code} ({self.uses}/{self.max_uses})"


class PlayerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    coins = models.PositiveIntegerField(default=0)
    rubies = models.PositiveIntegerField(default=0)
    lives = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username
