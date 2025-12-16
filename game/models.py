from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from .balance import (
    CLASS_STATS,
    CLASS_LEVEL_GAINS,
    class_stats_with_level,
    RARITY_MULTIPLIERS,
    RARITY_STAT_MULTIPLIER,
    xp_to_next_level,
)


User = settings.AUTH_USER_MODEL


# ==========================
# Clases de Personaje
# ==========================

class CharacterClass(models.TextChoices):
    TANK = "tank", "Tanque"
    DPS = "dps", "DPS"
    HEALER = "healer", "Healer"
    APPRENTICE = "apprentice", "Aprendiz"



class Character(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="characters")
    name = models.CharField(max_length=32)
    char_class = models.CharField(max_length=16, choices=CharacterClass.choices)

    level = models.PositiveIntegerField(default=1)
    xp = models.PositiveIntegerField(default=0)

    # Stats base
    base_hp = models.IntegerField(default=100)
    base_atk = models.IntegerField(default=10)
    base_def = models.IntegerField(default=5)
    base_speed = models.IntegerField(default=1)
    max_mana = models.IntegerField(default=10)

    # Imagen asociada
    image = models.ImageField(upload_to="characters/", null=True, blank=True)

    # Economía / orbes / vidas (asumo que ya los tienes; si no, añádelos)
    coins = models.IntegerField(default=100)
    gems = models.IntegerField(default=0)
    orbs_bronze = models.IntegerField(default=0)
    orbs_silver = models.IntegerField(default=0)
    orbs_gold = models.IntegerField(default=0)

    lives = models.IntegerField(default=3)
    lives_last_tick = models.DateTimeField(default=timezone.now)

    MAX_LIVES = 3
    LIFE_REGEN_MINUTES = 10

    created_at = models.DateTimeField(auto_now_add=True)

    def set_stats_from_class(self):
        stats = CLASS_STATS[self.char_class]
        self.base_hp = stats["hp"]
        self.base_atk = stats["atk"]
        self.base_def = stats["def"]
        self.base_speed = stats["speed"]
        self.max_mana = stats["mana"]

    def save(self, *args, **kwargs):
        # Si es nuevo, se asignan stats por clase
        if not self.pk:
            self.set_stats_from_class()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_char_class_display()})"

    # ---- XP / nivel (ejemplo simple, ajusta a lo que ya tenías) ----
    def xp_to_next_level(self):
        return xp_to_next_level(self.level)

    def gain_xp(self, amount):
        """Retorna cuántos niveles subió."""
        self.xp += amount
        levels_up = 0
        while True:
            needed = self.xp_to_next_level()
            if self.xp >= needed:
                self.xp -= needed
                self.level += 1
                levels_up += 1
            else:
                break
        self.save()
        return levels_up

    def regen_lives(self, now=None):
        now = now or timezone.now()

        # Si por alguna razón está null o futuro
        if not self.lives_last_tick or self.lives_last_tick > now:
            self.lives_last_tick = now

        if self.lives >= self.MAX_LIVES:
            # full: dejamos tick alineado para no acumular
            self.lives = self.MAX_LIVES
            self.lives_last_tick = now
            self.save(update_fields=["lives", "lives_last_tick"])
            return {"lives": self.lives, "gained": 0, "seconds_to_next": 0}

        interval = timedelta(minutes=self.LIFE_REGEN_MINUTES)
        elapsed = now - self.lives_last_tick
        ticks = int(elapsed.total_seconds() // interval.total_seconds())

        if ticks <= 0:
            # falta para la siguiente
            next_at = self.lives_last_tick + interval
            return {
                "lives": self.lives,
                "gained": 0,
                "seconds_to_next": max(0, int((next_at - now).total_seconds())),
            }

        gained = min(ticks, self.MAX_LIVES - self.lives)
        self.lives += gained

        # avanzamos el tick SOLO por los que “consumimos”
        self.lives_last_tick = self.lives_last_tick + (interval * gained)

        # si quedamos full, reseteamos tick a now para no acumular
        if self.lives >= self.MAX_LIVES:
            self.lives = self.MAX_LIVES
            self.lives_last_tick = now

        self.save(update_fields=["lives", "lives_last_tick"])

        seconds_to_next = 0
        if self.lives < self.MAX_LIVES:
            next_at = self.lives_last_tick + interval
            seconds_to_next = max(0, int((next_at - now).total_seconds()))

        return {"lives": self.lives, "gained": gained, "seconds_to_next": seconds_to_next}

    # ---- Base stats including level scaling ----
    def base_stats_with_level(self):
        """
        Returns base stats including per-level gains for the character class.
        Level 1 uses CLASS_STATS; each additional level adds CLASS_LEVEL_GAINS.
        """
        return class_stats_with_level(self.char_class, self.level)


class EnemyType(models.Model):
    name = models.CharField(max_length=50)
    base_hp = models.IntegerField(default=50)
    base_atk = models.IntegerField(default=8)
    base_def = models.IntegerField(default=3)
    base_speed = models.IntegerField(default=1)
    image = models.ImageField(upload_to="enemies/", null=True, blank=True)

    def __str__(self):
        return self.name


class EnemyRarity(models.TextChoices):
    NORMAL = "normal", "Normal"
    STRONG = "strong", "Fuerte"
    BOSS = "boss", "Jefe"
    LEGEND = "legend", "Leyenda"


class EnemyInstance(models.Model):
    enemy_type = models.ForeignKey(EnemyType, on_delete=models.CASCADE)
    level = models.IntegerField(default=1)
    rarity = models.CharField(max_length=20, choices=EnemyRarity.choices)

    # Stats generados
    hp = models.IntegerField()
    atk = models.IntegerField()
    defense = models.IntegerField()
    speed = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.enemy_type.name} ({self.rarity} lvl {self.level})"


ROLE_ORDER = {
    "tank": 1,
    "dps": 2,
    "apprentice": 3,
    "healer": 4,
}


# ==========================
# Ítems (asumo que ya tienes este modelo)
# ==========================

class EquipmentSlot(models.TextChoices):
    HELMET = "helmet", "Casco"
    CHEST = "chest", "Pechera"
    PANTS = "pants", "Pantalones"
    BOOTS = "boots", "Botas"
    MAIN_HAND = "main_hand", "Mano Principal"
    OFF_HAND = "off_hand", "Mano Secundaria"
    AMULET = "amulet", "Amuleto"
    RING = "ring", "Anillo"
    PET = "pet", "Mascota"


class ItemRarity(models.TextChoices):
    BASIC = "basic", "Básica"
    UNCOMMON = "uncommon", "Poco Común"
    RARE = "rare", "Rara"
    EPIC = "epic", "Épica"
    LEGENDARY = "legendary", "Legendaria"
    MYTHIC = "mythic", "Mítica"
    ASCENDED = "ascended", "Ascendida"


class EquipmentItem(models.Model):
    owner = models.ForeignKey(Character, on_delete=models.CASCADE, related_name="equipment_items")
    name = models.CharField(max_length=64)
    slot = models.CharField(max_length=16, choices=EquipmentSlot.choices)
    rarity = models.CharField(max_length=16, choices=ItemRarity.choices, default=ItemRarity.BASIC)
    level = models.IntegerField(default=1)

    base_hp = models.IntegerField(default=0)
    base_atk = models.IntegerField(default=0)
    base_def = models.IntegerField(default=0)
    base_speed = models.IntegerField(default=0)

    is_equipped = models.BooleanField(default=False)
    image = models.ImageField(upload_to="items/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_stats(self):
        mult = RARITY_STAT_MULTIPLIER[self.rarity]
        return {
            "hp": int(self.base_hp * mult),
            "atk": int(self.base_atk * mult),
            "def": int(self.base_def * mult),
            "speed": int(self.base_speed * mult),
        }

    def __str__(self):
        return f"{self.name} ({self.get_rarity_display()})"


# ==========================
# Mundo compartido
# ==========================

class PlayerState(models.Model):
    character = models.OneToOneField(Character, on_delete=models.CASCADE, related_name="state")
    x = models.IntegerField(default=2)
    y = models.IntegerField(default=7)
    zone = models.CharField(max_length=32, default="main_city")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.character.name} @({self.x},{self.y}) [{self.zone}]"


class EnemySpawn(models.Model):
    """
    Enemigo persistente en el mundo, compartido para todos los jugadores.
    """
    zone = models.CharField(max_length=32, default="main_city")
    x = models.IntegerField()
    y = models.IntegerField()
    enemy_type = models.ForeignKey(EnemyType, on_delete=models.CASCADE)
    respawn_seconds = models.IntegerField(default=300)  # 5 minutos
    is_alive = models.BooleanField(default=True)
    next_respawn_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.enemy_type.name} spawn @({self.x},{self.y}) [{self.zone}]"
