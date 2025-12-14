from django.contrib import admin
from .models import (
    Character, EnemyType, EnemyInstance,
    EquipmentItem, PlayerState, EnemySpawn
)


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "char_class", "level", "coins", "lives")
    search_fields = ("name", "owner__username")


admin.site.register(EnemyType)
admin.site.register(EnemyInstance)
admin.site.register(EquipmentItem)
admin.site.register(PlayerState)
admin.site.register(EnemySpawn)
