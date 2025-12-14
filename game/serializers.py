from rest_framework import serializers
from .models import (
    Character,
    EquipmentItem,
    PlayerState,
)

# ==========================
# CHARACTER
# ==========================

class CharacterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = [
            "id",
            "name",
            "char_class",
            "level",
            "xp",
            "base_hp",
            "base_atk",
            "base_def",
            "base_speed",
            "max_mana",
            "coins",
            "gems",
            "orbs_bronze",
            "orbs_silver",
            "orbs_gold",
            "lives",
            "image",
        ]


class CharacterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ["name", "char_class", "image"]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        character = Character(
            owner=user,
            name=validated_data["name"],
            char_class=validated_data["char_class"],
            image=validated_data.get("image"),
        )
        character.save()
        return character


# ==========================
# EQUIPMENT ITEM (INVENTARIO)
# ==========================

class EquipmentItemSerializer(serializers.ModelSerializer):
    # 👉 stats finales (con rareza aplicada)
    bonus_hp = serializers.SerializerMethodField()
    bonus_atk = serializers.SerializerMethodField()
    bonus_def = serializers.SerializerMethodField()
    bonus_speed = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentItem
        fields = [
            "id",
            "name",
            "slot",
            "rarity",
            "level",
            "is_equipped",
            "bonus_hp",
            "bonus_atk",
            "bonus_def",
            "bonus_speed",
            "image",
        ]

    def get_bonus_hp(self, obj):
        return obj.total_stats()["hp"]

    def get_bonus_atk(self, obj):
        return obj.total_stats()["atk"]

    def get_bonus_def(self, obj):
        return obj.total_stats()["def"]

    def get_bonus_speed(self, obj):
        return obj.total_stats()["speed"]


# ==========================
# INVENTORY (LISTA)
# ==========================

class InventorySerializer(serializers.ModelSerializer):
    items = EquipmentItemSerializer(many=True, source="equipment_items")

    class Meta:
        model = Character
        fields = ["id", "items"]


# ==========================
# PLAYER STATE (MUNDO)
# ==========================

class PlayerStateSerializer(serializers.ModelSerializer):
    character_name = serializers.CharField(source="character.name", read_only=True)
    character_class = serializers.CharField(source="character.char_class", read_only=True)
    character_image = serializers.ImageField(source="character.image", read_only=True)

    class Meta:
        model = PlayerState
        fields = [
            "x",
            "y",
            "zone",
            "character_name",
            "character_class",
            "character_image",
        ]
