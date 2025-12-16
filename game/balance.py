"""
Central place for balance constants and simple helpers.
Tweak values here to adjust player, enemy, and item scaling.
"""

# Player classes base stats
CLASS_STATS = {
    "tank": {"hp": 100, "atk": 10, "def": 8, "speed": 1, "mana": 10},
    "dps": {"hp": 90, "atk": 14, "def": 4, "speed": 1, "mana": 10},
    "healer": {"hp": 80, "atk": 8, "def": 4, "speed": 1, "mana": 12},
    "apprentice": {"hp": 95, "atk": 11, "def": 5, "speed": 1, "mana": 10},
}

# Per-level gains by class
CLASS_LEVEL_GAINS = {
    "tank": {"hp": 20, "atk": 3, "def": 2, "speed": 1},
    "dps": {"hp": 5, "atk": 5, "def": 1, "speed": 1},
    "healer": {"hp": 2, "atk": 2, "def": 1, "speed": 1},
    "apprentice": {"hp": 10, "atk": 4, "def": 1, "speed": 1},
}

# XP curve
XP_BASE = 100
XP_GROWTH = 1.10


def xp_to_next_level(level: int) -> int:
    if level <= 1:
        return XP_BASE
    needed = XP_BASE
    for _ in range(1, level):
        needed = int(needed * XP_GROWTH)
    return needed


def class_stats_with_level(char_class: str, level: int):
    base = CLASS_STATS.get(char_class)
    gains = CLASS_LEVEL_GAINS.get(char_class)
    if not base or not gains:
        raise ValueError(f"Unknown char_class '{char_class}'")
    base = base.copy()
    lvl_minus_one = max(0, level - 1)
    base["hp"] += gains["hp"] * lvl_minus_one
    base["atk"] += gains["atk"] * lvl_minus_one
    base["def"] += gains["def"] * lvl_minus_one
    base["speed"] += gains["speed"] * lvl_minus_one
    return base


# Enemy rarities and multipliers
RARITY_MULTIPLIERS = {
    "normal": 1.0,
    "strong": 1.4,
    "boss": 1.8,
    "legend": 2.2,
}

ENEMY_RARITY_CHANCES = [
    ("normal", 0.80),
    ("strong", 0.15),
    ("boss",   0.04),
    ("legend", 0.01),
]

# Enemy per-level growth (reduce if scaling is too steep)
ENEMY_HP_GROWTH = 1.06
ENEMY_ATK_GROWTH = 1.05
ENEMY_DEF_GROWTH = 1.04

# Item rarities
RARITY_STAT_MULTIPLIER = {
    "basic": 1.0,
    "uncommon": 1.8,
    "rare": 3.0,
    "epic": 5.0,
    "legendary": 8.0,
    "mythic": 10.0,
    "ascended": 10.0,
}

ITEM_GACHA_PROBS = [
    ("basic",     0.50),
    ("uncommon",  0.25),
    ("rare",      0.15),
    ("epic",      0.07),
    ("legendary", 0.02),
    ("mythic",    0.009),
    ("ascended",  0.001),
]

GACHA_COST_PER_PULL = 20
