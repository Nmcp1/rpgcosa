import random
from django.db import transaction

from .balance import (
    ENEMY_RARITY_CHANCES,
    RARITY_MULTIPLIERS,
    ITEM_GACHA_PROBS,
    RARITY_STAT_MULTIPLIER,
    GACHA_COST_PER_PULL,
    ENEMY_HP_GROWTH,
    ENEMY_ATK_GROWTH,
    ENEMY_DEF_GROWTH,
)
from .models import (
    EnemyType,
    EnemyInstance,
    EnemyRarity,
    Character,
    EquipmentItem,
    ItemRarity,
)

from .battle_engine import Battler

# ====================================================
# Enemigos (instancias para batallas)
# ====================================================

def choose_rarity():
    r = random.random()
    cumulative = 0
    for rarity, chance in ENEMY_RARITY_CHANCES:
        cumulative += chance
        if r <= cumulative:
            return rarity
    return "normal"


def calculate_enemy_stats(enemy_type: EnemyType, level: int, rarity: str):
    """
    Calcula los stats finales de un enemigo según:
    - stats base del EnemyType
    - nivel
    - multiplicador de rareza
    """
    multiplier = RARITY_MULTIPLIERS[rarity]

    return {
        "hp": int(enemy_type.base_hp * (ENEMY_HP_GROWTH ** (level - 1)) * multiplier),
        "atk": int(enemy_type.base_atk * (ENEMY_ATK_GROWTH ** (level - 1)) * multiplier),
        "def": int(enemy_type.base_def * (ENEMY_DEF_GROWTH ** (level - 1)) * multiplier),
        "speed": enemy_type.base_speed,
    }


def generate_enemy_pack(zone_level: int = 1):
    """
    Genera entre 1 y 4 EnemyInstance en BD y los devuelve en una lista.
    """
    enemy_types = list(EnemyType.objects.all())
    if not enemy_types:
        raise ValueError("No hay EnemyTypes registrados en la BD.")

    pack_size = random.randint(1, 4)
    enemies = []

    for _ in range(pack_size):
        etype = random.choice(enemy_types)
        rarity = choose_rarity()
        stats = calculate_enemy_stats(etype, zone_level, rarity)

        enemy = EnemyInstance(
            enemy_type=etype,
            level=zone_level,
            rarity=rarity,
            hp=stats["hp"],
            atk=stats["atk"],
            defense=stats["def"],
            speed=stats["speed"],
        )
        enemy.save()
        enemies.append(enemy)

    return enemies


# ====================================================
# Conversión a Battler (combate)
# ====================================================

def character_to_battler(character: Character) -> Battler:
    """
    Crea un Battler del personaje sumando los stats de los ítems equipados.
    """
    eq_items = character.equipment_items.filter(is_equipped=True)

    base_stats = character.base_stats_with_level()
    total_hp = base_stats["hp"]
    total_atk = base_stats["atk"]
    total_def = base_stats["def"]
    total_speed = base_stats["speed"]

    for item in eq_items:
        stats = item.total_stats()  # usa RARITY_STAT_MULTIPLIER internamente
        total_hp += stats["hp"]
        total_atk += stats["atk"]
        total_def += stats["def"]
        total_speed += stats["speed"]

    return Battler(
        name=character.name,
        role=character.char_class,
        hp=total_hp,
        atk=total_atk,
        defense=total_def,
        speed=total_speed,
        mana=character.max_mana,
        is_player=True,
    )


def enemy_to_battler(enemy_instance: EnemyInstance) -> Battler:
    """
    Crea un Battler desde una instancia EnemyInstance.
    """
    return Battler(
        name=enemy_instance.enemy_type.name,
        role="dps",
        hp=enemy_instance.hp,
        atk=enemy_instance.atk,
        defense=enemy_instance.defense,
        speed=enemy_instance.speed,
        mana=5,
        is_player=False,
    )


# ====================================================
# Recompensas de batalla
# ====================================================

# Valor en monedas de cada tipo de orbe (para la tienda)
COIN_VALUES = {
    "bronze": 1,
    "silver": 15,
    "gold": 100,
}


def calculate_battle_rewards(enemies):
    """
    Calcula XP y orbes que se entregan por ganar una batalla.

    Enemies: lista de EnemyInstance.
    Retorna un dict:
    {
        "xp": int,
        "orbs_bronze": int,
        "orbs_silver": int,
        "orbs_gold": int,
    }
    """
    total_xp = 0
    bronze = 0
    silver = 0
    gold = 0

    for e in enemies:
        # XP base por nivel
        base_xp = 20 + e.level * 5

        if e.rarity == EnemyRarity.NORMAL:
            total_xp += base_xp
            bronze += 1
        elif e.rarity == EnemyRarity.STRONG:
            total_xp += int(base_xp * 1.2)
            bronze += 2
            silver += 1
        elif e.rarity == EnemyRarity.BOSS:
            total_xp += int(base_xp * 1.6)
            silver += 2
            gold += 1
        elif e.rarity == EnemyRarity.LEGEND:
            total_xp += int(base_xp * 2.0)
            gold += 2

    return {
        "xp": total_xp,
        "orbs_bronze": bronze,
        "orbs_silver": silver,
        "orbs_gold": gold,
    }


# ====================================================
# Gacha de ítems
# ====================================================

def choose_item_rarity():
    r = random.random()
    cumulative = 0.0
    for rarity, prob in ITEM_GACHA_PROBS:
        cumulative += prob
        if r <= cumulative:
            return rarity if isinstance(rarity, str) else rarity
    return ItemRarity.BASIC


def random_slot():
    """
    Devuelve un slot aleatorio de EquipmentSlot
    (podrías sesgarlo si quieres).
    """
    slots = [choice[0] for choice in EquipmentItem._meta.get_field("slot").choices]
    return random.choice(slots)


def base_stats_for_slot(slot):
    """
    Stats "base" para un ítem según el slot.
    Luego se multiplican por el multiplicador de rareza (RARITY_STAT_MULTIPLIER).
    """
    # Valores simples, puedes tunearlos
    if slot in ("helmet", "chest", "pants", "boots"):
        return {"hp": 10, "atk": 0, "def": 4, "speed": 0}
    elif slot in ("main_hand", "off_hand"):
        return {"hp": 0, "atk": 6, "def": 2, "speed": 0}
    elif slot in ("amulet", "ring"):
        return {"hp": 4, "atk": 3, "def": 2, "speed": 1}
    elif slot == "pet":
        return {"hp": 8, "atk": 4, "def": 1, "speed": 1}
    else:
        # fallback
        return {"hp": 5, "atk": 3, "def": 2, "speed": 0}


@transaction.atomic
def perform_gacha_pulls(character: Character, pulls: int):
    """
    Realiza 'pulls' tiradas de gacha para 'character'.
    Verifica monedas, descuenta el coste y crea EquipmentItem.
    Retorna (items_creados, total_cost).
    """
    if pulls <= 0:
        raise ValueError("El número de tiradas debe ser mayor que 0.")

    total_cost = pulls * GACHA_COST_PER_PULL
    if character.coins < total_cost:
        raise ValueError("No tienes suficientes monedas para hacer el gacha.")

    character.coins -= total_cost
    character.save()

    created_items = []

    for _ in range(pulls):
        rarity = choose_item_rarity()
        slot = random_slot()
        base_stats = base_stats_for_slot(slot)

        item = EquipmentItem.objects.create(
            owner=character,
            name=f"Item {rarity} {slot}",
            slot=slot,
            rarity=rarity,
            level=1,
            base_hp=base_stats["hp"],
            base_atk=base_stats["atk"],
            base_def=base_stats["def"],
            base_speed=base_stats["speed"],
        )
        created_items.append(item)

    return created_items, total_cost
