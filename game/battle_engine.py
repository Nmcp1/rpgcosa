#battle_engine.py
import random
from .models import ROLE_ORDER

class Battler:
    """
    Representa un personaje o enemigo dentro del combate.
    """

    def __init__(self, name, role, hp, atk, defense, speed, mana=10, is_player=False):
        self.name = name
        self.role = role
        self.max_hp = hp
        self.hp = hp
        self.atk = atk
        self.defense = defense
        self.speed = speed
        self.mana = mana
        self.max_mana = mana
        self.is_player = is_player
        self.alive = True

    def take_damage(self, dmg):
        dmg = max(1, dmg - self.defense)
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def regen_mana(self):
        self.mana = min(self.max_mana, self.mana + 3)


def choose_target(team):
    """Elije el objetivo vivo más cercano (primer vivo en la lista)."""
    alive = [b for b in team if b.alive]
    return alive[0] if alive else None


def healer_target(team):
    """Selecciona aliado con menor porcentaje de vida."""
    alive = [b for b in team if b.alive]
    alive.sort(key=lambda x: x.hp / x.max_hp)
    return alive[0] if alive else None


def action_attack(user, target):
    raw = user.atk
    dmg = target.take_damage(raw)
    return f"{user.name} ataca a {target.name} causando {dmg} daño."


def action_heal(user, target):
    # ❌ No se puede curar si el objetivo está bajo 10% de vida
    if target.max_hp > 0 and (target.hp / target.max_hp) < 0.10:
        return f"{user.name} intenta curar a {target.name}, pero está bajo 10% de vida y no puede curarse."

    heal_amount = int(user.atk * 0.8)
    target.heal(heal_amount)
    return f"{user.name} cura a {target.name} por {heal_amount} HP."



def simulate_battle(players, enemies):
    """
    players: lista de Battler
    enemies: lista de Battler
    """
    log = []
    turn = 1

    while True:
        log.append(f"--- Turno {turn} ---")

        ### FASE 1: PREPARACIÓN (curaciones, buffs)
        all_units = players + enemies
        prep_order = sorted(all_units, key=lambda x: x.speed, reverse=True)

        for unit in prep_order:
            if not unit.alive:
                continue

            unit.regen_mana()

            # Healers curan en fase 1
            if unit.role == "healer":
                target = healer_target(players if unit.is_player else enemies)
                if target and unit.mana >= 5:
                    unit.mana -= 5
                    log.append(action_heal(unit, target))
                    continue

        ### FASE 2: POSICIONAMIENTO
        # Ya lo tenemos implícito con ROLE_ORDER, no se necesita mover nada.

        ### FASE 3: COMBATE
        combat_order = sorted(
            all_units,
            key=lambda x: (ROLE_ORDER.get(x.role, 99), -x.speed)
        )

        for unit in combat_order:
            if not unit.alive:
                continue

            # Elegir objetivo
            if unit.is_player:
                target = choose_target(enemies)
            else:
                target = choose_target(players)

            if not target:
                break  # combate terminó

            log.append(action_attack(unit, target))

        # Evaluar final del combate:
        if not any(p.alive for p in players):
            log.append("¡Los jugadores han sido derrotados!")
            return {"result": "lose", "log": log}

        if not any(e.alive for e in enemies):
            log.append("¡Los jugadores ganaron!")
            return {"result": "win", "log": log}

        turn += 1
        if turn > 50:
            log.append("Empate técnico (50 turnos).")
            return {"result": "draw", "log": log}
