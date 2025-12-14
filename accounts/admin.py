from django.contrib import admin
from .models import InvitationCode, PlayerProfile

@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "created_by", "uses", "max_uses", "is_active", "created_at")
    search_fields = ("code", "created_by__username")
    list_filter = ("is_active",)

@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "coins", "rubies", "lives", "created_at")
    search_fields = ("user__username",)
