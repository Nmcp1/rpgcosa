from datetime import timedelta
import json
import random

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from .models import (
    Character,
    EnemyInstance,
    EquipmentItem,
    PlayerState,
    EnemySpawn,
    EnemyType,
)
from .serializers import *
from .utils import (
    generate_enemy_pack,
    character_to_battler,
    enemy_to_battler,
    calculate_battle_rewards,
    COIN_VALUES,
    perform_gacha_pulls,
    calculate_enemy_stats,
)
from .battle_engine import simulate_battle

# ✅ mapas
from .maps import MAPS


# ==========================
# Helpers de mapas
# ==========================

def get_current_map(zone: str):
    return MAPS.get(zone) or MAPS["center"]

def get_map_size(map_data):
    rows = len(map_data)
    cols = len(map_data[0]) if rows else 0
    return rows, cols

def is_inside_map(x, y, rows, cols):
    return 0 <= x < cols and 0 <= y < rows

def is_walkable(tile):
    # Igual que tu frontend: wall y tree bloquean
    return tile not in ("wall", "tree","house")

def get_zone_transition(zone: str, x: int, y: int, rows: int, cols: int):
    """
    Si el jugador pisa un BORDE, se cambia de zona según exits del mapa.
    Devuelve (new_zone, new_x, new_y) o (None, None, None).
    """
    exits = get_current_map(zone).get("exits", {})

    # Norte
    if y == 0 and "north" in exits:
        new_zone = exits["north"]
        new_map = get_current_map(new_zone)["map"]
        nrows, ncols = get_map_size(new_map)
        return new_zone, x, nrows - 2  # entras por abajo

    # Sur
    if y == rows - 1 and "south" in exits:
        new_zone = exits["south"]
        new_map = get_current_map(new_zone)["map"]
        return new_zone, x, 1  # entras por arriba

    # Oeste
    if x == 0 and "west" in exits:
        new_zone = exits["west"]
        new_map = get_current_map(new_zone)["map"]
        nrows, ncols = get_map_size(new_map)
        return new_zone, ncols - 2, y  # entras por derecha

    # Este
    if x == cols - 1 and "east" in exits:
        new_zone = exits["east"]
        new_map = get_current_map(new_zone)["map"]
        return new_zone, 1, y  # entras por izquierda

    return None, None, None


# ==========================
# Helpers: vidas + personaje
# ==========================

def get_my_character(user):
    return Character.objects.filter(owner=user).first()

def ensure_lives_and_get_timer(character):
    # regen + timer
    return character.regen_lives(timezone.now())


# ==========================
# Enemigos random por zona (1..4)
# ==========================

ENEMY_RARITY_ROLL = [
    ("normal", 0.80),
    ("strong", 0.15),
    ("boss", 0.04),
    ("legend", 0.01),
]

def roll_rarity(rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for key, p in ENEMY_RARITY_ROLL:
        acc += p
        if r <= acc:
            return key
    return "normal"

import re

_ZONE_RE = re.compile(r"^\s*(-?\d+)\s*-\s*(-?\d+)\s*$")

def parse_zone_xy(zone_key: str):
    m = _ZONE_RE.match(zone_key or "")
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2))

def get_zone_level_from_zonekey(zone_key: str) -> int:
    x, y = parse_zone_xy(zone_key)
    r = max(abs(x), abs(y))

    # 0-0 = safe zone sin enemigos
    if r == 0:
        return 0

    # anillo inmediato alrededor (8 mapas) = lvl 1
    if r == 1:
        return 1

    # r=2 -> lvl 10, r=3 -> lvl 20, etc.
    return (r - 1) * 10


def generate_enemy_pack_instances(zone_key: str, seed_key: str, count_min=1, count_max=4):
    """
    Crea 1..4 EnemyInstance en BD, con enemy types aleatorios y level según zona.
    """
    enemy_types = list(EnemyType.objects.all())
    if not enemy_types:
        return []

    zone_lvl = get_zone_level_from_zonekey(zone_key)
    if zone_lvl <= 0:
        return []

    rng = random.Random(hash(seed_key) & 0xffffffff)
    pack_size = rng.randint(count_min, count_max)

    enemies = []
    for _ in range(pack_size):
        et = rng.choice(enemy_types)
        rarity = roll_rarity(rng)
        stats = calculate_enemy_stats(et, level=zone_lvl, rarity=rarity)

        enemies.append(
            EnemyInstance.objects.create(
                enemy_type=et,
                level=zone_lvl,
                rarity=rarity,
                hp=stats["hp"],
                atk=stats["atk"],
                defense=stats["def"],
                speed=stats["speed"],
            )
        )
    return enemies


# ==========================
# Enemigos persistentes por zona (EnemySpawn)
# ==========================

def ensure_enemy_spawns_for_zone(zone: str):
    """
    Crea EnemySpawn en la BD para cada casilla 'enemy' del mapa de esa zona,
    si aún no existe.
    """
    enemy_type = EnemyType.objects.first()
    if not enemy_type:
        return

    zone_map = get_current_map(zone)["map"]
    rows, cols = get_map_size(zone_map)

    for y, row in enumerate(zone_map):
        for x, tile in enumerate(row):
            if tile == "enemy":
                if not EnemySpawn.objects.filter(zone=zone, x=x, y=y).exists():
                    EnemySpawn.objects.create(
                        zone=zone,
                        x=x,
                        y=y,
                        enemy_type=enemy_type,
                        respawn_seconds=300,
                        is_alive=True,
                        next_respawn_at=None,
                    )

def refresh_respawns(zone: str):
    now = timezone.now()
    spawns = EnemySpawn.objects.filter(zone=zone)
    for sp in spawns:
        if not sp.is_alive and sp.next_respawn_at and sp.next_respawn_at <= now:
            sp.is_alive = True
            sp.next_respawn_at = None
            sp.save(update_fields=["is_alive", "next_respawn_at"])

def get_trigger_enemy_spawn(x, y, zone: str):
    """
    Retorna EnemySpawn asociado a:
    - tile == enemy: spawn exacto
    - tile == enemy_zone: cualquier spawn vivo cerca (radio 1)
    """
    ensure_enemy_spawns_for_zone(zone)
    refresh_respawns(zone)

    zone_map = get_current_map(zone)["map"]
    tile = zone_map[y][x]
    spawns = EnemySpawn.objects.filter(zone=zone)

    target = None
    if tile == "enemy":
        target = spawns.filter(x=x, y=y, is_alive=True).first()
    elif tile == "enemy_zone":
        for sp in spawns.filter(is_alive=True):
            if abs(sp.x - x) <= 1 and abs(sp.y - y) <= 1:
                target = sp
                break

    return target


# ==========================
# Personajes
# ==========================

class CreateCharacterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CharacterCreateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            character = serializer.save()
            return Response(CharacterSerializer(character).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyCharactersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        chars = Character.objects.filter(owner=request.user)
        return Response(CharacterSerializer(chars, many=True).data)


@login_required
def create_character_form(request):
    errors = {}

    if request.method == "POST":
        data = request.POST.copy()
        if "image" in request.FILES:
            data["image"] = request.FILES["image"]

        serializer = CharacterCreateSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            serializer.save()
            return redirect("start_menu")
        else:
            errors = serializer.errors

    return render(request, "create_character.html", {"errors": errors})

# ==========================
# Batalla
# ==========================

class StartBattleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        char_id = request.data.get("character_id")
        enemy_ids = request.data.get("enemy_ids")

        if not char_id or not enemy_ids:
            return Response({"error": "Debes enviar character_id y enemy_ids"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            character = Character.objects.get(id=char_id, owner=request.user)
        except Character.DoesNotExist:
            return Response({"error": "Personaje no válido"}, status=status.HTTP_404_NOT_FOUND)

        enemies = list(EnemyInstance.objects.filter(id__in=enemy_ids))
        if not enemies:
            return Response({"error": "No se encontraron enemigos válidos"}, status=status.HTTP_404_NOT_FOUND)

        player_battlers = [character_to_battler(character)]
        enemy_battlers = [enemy_to_battler(e) for e in enemies]

        result = simulate_battle(player_battlers, enemy_battlers)
        player_battler = player_battlers[0]

        rewards = {"xp": 0, "orbs_bronze": 0, "orbs_silver": 0, "orbs_gold": 0}
        levels_up = 0

        if result["result"] == "win":
            rewards = calculate_battle_rewards(enemies)
            levels_up = character.gain_xp(rewards["xp"])
            character.orbs_bronze += rewards["orbs_bronze"]
            character.orbs_silver += rewards["orbs_silver"]
            character.orbs_gold += rewards["orbs_gold"]
            character.save()

        def get_image_url(image_field):
            if not image_field:
                return None
            try:
                return image_field.url
            except ValueError:
                return None

        player_data = {
            "id": character.id,
            "name": character.name,
            "max_hp": player_battler.max_hp,
            "atk": player_battler.atk,
            "defense": player_battler.defense,
            "speed": player_battler.speed,
            "image": get_image_url(character.image),
            "level": character.level,
            "xp": character.xp,
            "coins": character.coins,
            "orbs_bronze": character.orbs_bronze,
            "orbs_silver": character.orbs_silver,
            "orbs_gold": character.orbs_gold,
        }

        enemies_data = []
        for e in enemies:
            enemies_data.append({
                "id": e.id,
                "name": e.enemy_type.name,
                "max_hp": e.hp,
                "atk": e.atk,
                "defense": e.defense,
                "speed": e.speed,
                "image": get_image_url(e.enemy_type.image),
                "rarity": e.rarity,
                "level": e.level,
            })

        return Response({
            "fight_result": result["result"],
            "log": result["log"],
            "player": player_data,
            "enemies": enemies_data,
            "rewards": rewards,
            "levels_up": levels_up,
        })


# ==========================
# Tienda (vender orbes)
# ==========================

class ShopView(APIView):
    permission_classes = [IsAuthenticated]

    def get_character(self, request):
        char_id = request.query_params.get("character_id") or request.data.get("character_id")
        if not char_id:
            return None, Response({"error": "Debes enviar character_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            character = Character.objects.get(id=char_id, owner=request.user)
        except Character.DoesNotExist:
            return None, Response({"error": "Personaje no válido"}, status=status.HTTP_404_NOT_FOUND)
        return character, None

    def get(self, request):
        character, error_response = self.get_character(request)
        if error_response:
            return error_response

        data = {
            "character_id": character.id,
            "character_name": character.name,
            "coins": character.coins,
            "orbs": {
                "bronze": character.orbs_bronze,
                "silver": character.orbs_silver,
                "gold": character.orbs_gold,
            },
            "prices": COIN_VALUES,
        }
        return Response(data)

    def post(self, request):
        character, error_response = self.get_character(request)
        if error_response:
            return error_response

        def to_non_negative_int(value, field_name):
            if value is None or value == "":
                return 0
            try:
                v = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{field_name} debe ser un número entero.")
            if v < 0:
                raise ValueError(f"{field_name} no puede ser negativo.")
            return v

        try:
            sell_bronze = to_non_negative_int(request.data.get("sell_bronze"), "sell_bronze")
            sell_silver = to_non_negative_int(request.data.get("sell_silver"), "sell_silver")
            sell_gold = to_non_negative_int(request.data.get("sell_gold"), "sell_gold")
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if sell_bronze > character.orbs_bronze:
            return Response({"error": "No tienes suficientes orbes de bronce."}, status=status.HTTP_400_BAD_REQUEST)
        if sell_silver > character.orbs_silver:
            return Response({"error": "No tienes suficientes orbes de plata."}, status=status.HTTP_400_BAD_REQUEST)
        if sell_gold > character.orbs_gold:
            return Response({"error": "No tienes suficientes orbes de oro."}, status=status.HTTP_400_BAD_REQUEST)

        coins_gained = (
            sell_bronze * COIN_VALUES["bronze"]
            + sell_silver * COIN_VALUES["silver"]
            + sell_gold * COIN_VALUES["gold"]
        )

        character.orbs_bronze -= sell_bronze
        character.orbs_silver -= sell_silver
        character.orbs_gold -= sell_gold
        character.coins += coins_gained
        character.save()

        return Response({
            "character_id": character.id,
            "character_name": character.name,
            "coins_gained": coins_gained,
            "coins_total": character.coins,
            "orbs_bronze": character.orbs_bronze,
            "orbs_silver": character.orbs_silver,
            "orbs_gold": character.orbs_gold,
        })


# ==========================
# Inventario
# ==========================

class InventoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        char_id = request.query_params.get("character_id")
        if not char_id:
            return Response({"error": "Debes enviar character_id"}, status=400)

        try:
            character = Character.objects.get(id=char_id, owner=request.user)
        except Character.DoesNotExist:
            return Response({"error": "Personaje no válido"}, status=404)

        items = character.equipment_items.all().order_by("-created_at")
        return Response(EquipmentItemSerializer(items, many=True).data)


# ==========================
# Gacha
# ==========================

class GachaPullView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        char_id = request.data.get("character_id")
        pulls = request.data.get("pulls", 1)

        if not char_id:
            return Response({"error": "Debes enviar character_id"}, status=400)

        try:
            character = Character.objects.get(id=char_id, owner=request.user)
        except Character.DoesNotExist:
            return Response({"error": "Personaje no válido"}, status=404)

        try:
            pulls_int = int(pulls)
        except (TypeError, ValueError):
            return Response({"error": "pulls debe ser un entero"}, status=400)

        try:
            items, total_cost = perform_gacha_pulls(character, pulls_int)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        return Response({
            "character_id": character.id,
            "character_name": character.name,
            "pulls": len(items),
            "coins_spent": total_cost,
            "coins_remaining": character.coins,
            "items": EquipmentItemSerializer(items, many=True).data,
        })


# ==========================
# Equipar / desequipar
# ==========================

class EquipItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        char_id = request.data.get("character_id")
        item_id = request.data.get("item_id")
        equip_flag = request.data.get("equip", True)

        if not char_id or not item_id:
            return Response({"error": "Debes enviar character_id e item_id"}, status=400)

        try:
            character = Character.objects.get(id=char_id, owner=request.user)
        except Character.DoesNotExist:
            return Response({"error": "Personaje no válido"}, status=404)

        try:
            item = EquipmentItem.objects.get(id=item_id, owner=character)
        except EquipmentItem.DoesNotExist:
            return Response({"error": "Ítem no válido para este personaje"}, status=404)

        equip_bool = bool(equip_flag)

        if equip_bool:
            EquipmentItem.objects.filter(owner=character, slot=item.slot, is_equipped=True).update(is_equipped=False)
            item.is_equipped = True
            item.save()
        else:
            item.is_equipped = False
            item.save()

        equipped_items = character.equipment_items.filter(is_equipped=True)
        return Response({
            "character_id": character.id,
            "equipped_items": EquipmentItemSerializer(equipped_items, many=True).data,
            "changed_item": EquipmentItemSerializer(item).data,
        })


# ==========================
# Vidas: perder vida + safe zone + timer
# ==========================

class LoseLifeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        char_id = request.data.get("character_id")
        if not char_id:
            return Response({"error": "Debes enviar character_id"}, status=400)

        try:
            character = Character.objects.get(id=char_id, owner=request.user)
        except Character.DoesNotExist:
            return Response({"error": "Personaje no válido"}, status=404)

        # regen antes de descontar (para que sea justo)
        character.regen_lives()

        if character.lives > 0:
            character.lives -= 1
            character.save(update_fields=["lives"])

        sent_to_safe = False

        # si quedó sin vidas -> mover a 0-0
        if character.lives <= 0:
            state, _ = PlayerState.objects.get_or_create(
                character=character,
                defaults={"x": 9, "y": 9, "zone": "0-0"},
            )
            state.zone = "0-0"
            state.x = 9
            state.y = 9
            state.save(update_fields=["zone", "x", "y"])
            sent_to_safe = True

        info = character.regen_lives()
        return Response({
            "character_id": character.id,
            "lives": character.lives,
            "sent_to_safe_zone": sent_to_safe,
            "seconds_to_next_life": info["seconds_to_next"],
        })


# ==========================
# Vistas HTML simples
# ==========================

@login_required
def battle_simulator(request):
    return render(request, "battle_simulator.html")


@login_required
def shop_page(request):
    character = get_my_character(request.user)
    if not character:
        return render(request, "no_character.html")
    return render(request, "shop_menu.html", {"character": character})


@login_required
def shop_sell_page(request):
    character = get_my_character(request.user)
    if not character:
        return render(request, "no_character.html")
    return render(request, "shop.html", {"character": character})


@login_required
def gacha_page(request):
    character = get_my_character(request.user)
    if not character:
        return render(request, "no_character.html")
    return render(request, "gacha.html", {"character": character})


@login_required
def inventory_page(request):
    character = get_my_character(request.user)
    if not character:
        return render(request, "no_character.html")
    return render(request, "inventory.html", {"character": character})


# ==========================
# Mundo compartido (HTML)
# ==========================

@login_required
def world_page(request):
    character = get_my_character(request.user)
    if not character:
        return render(request, "no_character.html")

    # ✅ regen y bloqueo si 0 vidas
    info = ensure_lives_and_get_timer(character)
    if character.lives <= 0:
        return redirect("start_menu")

    state, _ = PlayerState.objects.get_or_create(
        character=character,
        defaults={"x": 3, "y": 15, "zone": "center"},
    )

    current = get_current_map(state.zone)
    world_map = current["map"]

    ensure_enemy_spawns_for_zone(state.zone)

    others_qs = (
        PlayerState.objects
        .filter(zone=state.zone)
        .exclude(pk=state.pk)
        .select_related("character")
    )
    other_players = []
    for ps in others_qs:
        c = ps.character
        if not c:
            continue
        img_url = c.image.url if c.image else settings.STATIC_URL + "img/player_placeholder.png"
        other_players.append({
            "id": c.id,
            "name": c.name,
            "class": c.get_char_class_display(),
            "x": ps.x,
            "y": ps.y,
            "imgUrl": img_url,
        })

    return render(request, "world.html", {
        "character": character,
        "player_state": state,
        "current_zone": state.zone,
        "world_map_json": json.dumps(world_map),
        "other_players_json": json.dumps(other_players),
        "tiles_base_url": settings.STATIC_URL + "tiles/",
        "media_tiles_base_url": settings.MEDIA_URL + "tiles/",
        "static_tiles_base_url": settings.STATIC_URL + "tiles/",
    })


# ==========================
# Mundo compartido (MOVE)
# ==========================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def world_move(request):
    character = get_my_character(request.user)
    if not character:
        return Response({"error": "No tienes personaje"}, status=400)

    # ✅ regen y bloqueo en API
    info = ensure_lives_and_get_timer(character)
    if character.lives <= 0:
        return Response({
            "no_lives": True,
            "seconds_to_next_life": info["seconds_to_next"],
            "redirect_url": reverse("start_menu"),
        }, status=403)

    state, _ = PlayerState.objects.get_or_create(
        character=character,
        defaults={"x": 3, "y": 15, "zone": "center"},
    )

    x = request.data.get("x")
    y = request.data.get("y")

    try:
        x = int(x)
        y = int(y)
    except (TypeError, ValueError):
        return Response({"error": "Coordenadas inválidas"}, status=400)

    current = get_current_map(state.zone)
    world_map = current["map"]
    rows, cols = get_map_size(world_map)

    if not is_inside_map(x, y, rows, cols):
        return Response({"error": "Fuera del mapa"}, status=400)

    tile = world_map[y][x]
    if not is_walkable(tile):
        return Response({"error": "Tile bloqueado"}, status=400)

    state.x = x
    state.y = y
    state.save(update_fields=["x", "y"])

    # transición por borde
    new_zone, new_x, new_y = get_zone_transition(state.zone, x, y, rows, cols)
    if new_zone:
        state.zone = new_zone
        state.x = new_x
        state.y = new_y
        state.save(update_fields=["zone", "x", "y"])

        return Response({
            "map_changed": True,
            "new_zone": state.zone,
            "position": {"x": state.x, "y": state.y},
            "character": {
                "id": character.id,
                "level": character.level,
                "lives": character.lives,
                "coins": character.coins,
                "xp": character.xp,
                "xp_to_next": character.xp_to_next_level(),
            },
        })

    ensure_enemy_spawns_for_zone(state.zone)

    start_battle = False
    enter_shop = False
    enemy_ids = []

    if tile == "shop":
        enter_shop = True

    spawn = None
    if tile in ("enemy", "enemy_zone"):
        spawn = get_trigger_enemy_spawn(x, y, zone=state.zone)

    if spawn:
        now = timezone.now()
        spawn.is_alive = False
        spawn.next_respawn_at = now + timedelta(seconds=spawn.respawn_seconds)
        spawn.save(update_fields=["is_alive", "next_respawn_at"])

        enemies = generate_enemy_pack_instances(
            zone_key=state.zone,
            seed_key=f"{state.zone}:{x}:{y}:{now.timestamp()}",
            count_min=1,
            count_max=4,
        )

        if enemies:
            enemy_ids = [e.id for e in enemies]
            start_battle = True

    others_qs = (
        PlayerState.objects
        .filter(zone=state.zone)
        .exclude(pk=state.pk)
        .select_related("character")
    )

    other_players = []
    for ps in others_qs:
        c = ps.character
        if not c:
            continue
        img_url = c.image.url if c.image else settings.STATIC_URL + "img/player_placeholder.png"
        other_players.append({
            "id": c.id,
            "name": c.name,
            "class": c.get_char_class_display(),
            "x": ps.x,
            "y": ps.y,
            "imgUrl": img_url,
        })

    return Response({
        "position": {"x": state.x, "y": state.y},
        "character": {
            "id": character.id,
            "level": character.level,
            "lives": character.lives,
            "coins": character.coins,
            "xp": character.xp,
            "xp_to_next": character.xp_to_next_level(),
        },
        "start_battle": start_battle,
        "enter_shop": enter_shop,
        "character_id": character.id,
        "enemy_ids": enemy_ids,
        "other_players": other_players,
    })


# ==========================
# Mundo - enemigos vivos (por zona)
# ==========================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def world_enemies(request):
    character = get_my_character(request.user)
    if not character:
        return Response({"error": "No tienes personaje"}, status=400)

    state = PlayerState.objects.filter(character=character).first()
    if not state:
        return Response({"error": "No existe PlayerState"}, status=400)

    ensure_enemy_spawns_for_zone(state.zone)
    refresh_respawns(state.zone)

    spawns = EnemySpawn.objects.filter(zone=state.zone, is_alive=True)
    alive_list = [{"x": s.x, "y": s.y} for s in spawns]

    return Response({"alive_enemies": alive_list})
