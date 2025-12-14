# game/maps.py

import random

G = "ground"
W = "wall"
T = "tree"
S = "shop"
E = "enemy"
Z = "enemy_zone"
P = "portal"
H = "house"

CHAR = {"G": G, "W": W, "T": T, "S": S, "E": E, "Z": Z, "P": P,"H":H}

def parse(rows):
    # rows: lista de strings, cada string largo 18
    return [[CHAR[c] for c in r] for r in rows]

SIZE = 18
MIN_C = -10
MAX_C = 10

def clamp_wrap(v: int) -> int:
    if v < MIN_C:
        return MAX_C
    if v > MAX_C:
        return MIN_C
    return v

def zone_key(x: int, y: int) -> str:
    return f"{x}-{y}"

def parse_zone_key(key: str) -> tuple[int, int]:
    # "3--7" => (3, -7)
    x_str, y_str = key.split("-", 1)
    return int(x_str), int(y_str)

def ring_distance(x: int, y: int) -> int:
    return max(abs(x), abs(y))

def zone_level(x: int, y: int) -> int:
    """
    r=max(|x|,|y|)
    r=0 => SAFE (0-0)
    r=1 => lvl 1
    r=2 => lvl 10
    r=3 => lvl 20 ...
    """
    r = ring_distance(x, y)
    if r == 0:
        return 0
    if r == 1:
        return 1
    return (r - 1) * 10

def exits_for_zone(x: int, y: int) -> dict:
    north = zone_key(x, clamp_wrap(y + 1))
    south = zone_key(x, clamp_wrap(y - 1))
    east  = zone_key(clamp_wrap(x + 1), y)
    west  = zone_key(clamp_wrap(x - 1), y)
    return {"north": north, "south": south, "east": east, "west": west}

def make_base_canvas() -> list[list[str]]:
    rows = [["G"] * SIZE for _ in range(SIZE)]
    for i in range(SIZE):
        rows[0][i] = "W"
        rows[SIZE - 1][i] = "W"
        rows[i][0] = "W"
        rows[i][SIZE - 1] = "W"
    return rows

def carve_portals(rows: list[list[str]]) -> None:
    mid = SIZE // 2  # 9
    rows[0][mid] = "P"
    rows[SIZE - 1][mid] = "P"
    rows[mid][0] = "P"
    rows[mid][SIZE - 1] = "P"

def ensure_border_walls(rows: list[list[str]]) -> None:
    mid = SIZE // 2
    for i in range(SIZE):
        if rows[0][i] != "P": rows[0][i] = "W"
        if rows[SIZE-1][i] != "P": rows[SIZE-1][i] = "W"
        if rows[i][0] != "P": rows[i][0] = "W"
        if rows[i][SIZE-1] != "P": rows[i][SIZE-1] = "W"
    rows[0][mid] = "P"
    rows[SIZE-1][mid] = "P"
    rows[mid][0] = "P"
    rows[mid][SIZE-1] = "P"

def place_random_trees(rows: list[list[str]], rng: random.Random, density: int) -> None:
    """
    density: 0..N, mientras más grande más árboles.
    No coloca en bordes ni sobre portales/tiendas.
    """
    if density <= 0:
        return

    attempts = 200 + density * 60
    placed = 0
    target = 12 + density * 10  # aprox

    for _ in range(attempts):
        if placed >= target:
            break
        x = rng.randint(1, SIZE - 2)
        y = rng.randint(1, SIZE - 2)

        if rows[y][x] != "G":
            continue

        # no tocar portales ni bloquear el centro total
        if rows[y][x] in ("P", "S"):
            continue

        rows[y][x] = "T"
        placed += 1

        # cluster chico
        if placed < target and rng.random() < 0.65:
            for dx, dy in [(1,0), (0,1), (-1,0), (0,-1)]:
                nx, ny = x + dx, y + dy
                if 1 <= nx <= SIZE-2 and 1 <= ny <= SIZE-2 and rows[ny][nx] == "G" and rng.random() < 0.45:
                    rows[ny][nx] = "T"
                    placed += 1
                    if placed >= target:
                        break

def place_houses_center(rows: list[list[str]]) -> None:
    """
    0-0: varias tiendas, sin árboles, sin enemigos.
    """
    # zona de tiendas tipo “market”
    shop_blocks = [
        (4, 4), (7, 4), (10, 4),
        (4, 7),         (10, 7),
        (4,10), (7,10), (10,10),
    ]
    for sx, sy in shop_blocks:
        for dy in range(2):
            for dx in range(2):
                rows[sy+dy][sx+dx] = "H"

def place_shops_center(rows: list[list[str]]) -> None:
    """
    0-0: varias tiendas, sin árboles, sin enemigos.
    """
    # zona de tiendas tipo “market”
    shop_blocks = [
        (7,7)
    ]
    for sx, sy in shop_blocks:
        for dy in range(1):
            for dx in range(2):
                rows[sy+dy][sx+dx] = "S"

def place_shops_random(rows: list[list[str]], rng: random.Random, count: int) -> None:
    for _ in range(count):
        x = rng.randint(2, SIZE - 4)
        y = rng.randint(2, SIZE - 4)
        # bloque 2x2
        ok = True
        for dy in range(2):
            for dx in range(2):
                if rows[y+dy][x+dx] != "G":
                    ok = False
        if not ok:
            continue
        for dy in range(1):
            for dx in range(2):
                rows[y+dy][x+dx] = "S"

def place_enemy_zones(rows: list[list[str]], rng: random.Random, packs: int) -> None:
    """
    Pone zonas Z + un E en el centro de cada pack.
    Esto es “decoración” del mapa. La batalla real se genera en backend.
    """
    for _ in range(packs):
        cx = rng.randint(4, SIZE - 5)
        cy = rng.randint(4, SIZE - 5)

        # no encima de tiendas
        if rows[cy][cx] != "G":
            continue

        # Z 3x3
        for y in range(cy-1, cy+2):
            for x in range(cx-1, cx+2):
                if rows[y][x] == "G":
                    rows[y][x] = "Z"
        # E centro
        rows[cy][cx] = "E"

def build_map_for_zone(x: int, y: int) -> list[list[str]]:
    rows = make_base_canvas()
    carve_portals(rows)

    # RNG determinista por zona => “aleatorio” pero fijo por coordenada
    seed = (x * 73856093) ^ (y * 19349663) ^ 0xA5A5A5
    rng = random.Random(seed)

    zlvl = zone_level(x, y)

    # 0-0: SAFE
    if x == 0 and y == 0:
        # sin árboles ni enemigos
        place_houses_center(rows)
        place_shops_center(rows)
        ensure_border_walls(rows)
        return parse(["".join(r) for r in rows])

    # resto: árboles y tiendas random
    # densidad árboles sube con distancia
    r = ring_distance(x, y)
    tree_density = 1
    if r >= 3: tree_density = 2
    if r >= 6: tree_density = 3
    if r >= 9: tree_density = 4

    place_random_trees(rows, rng, tree_density)

    # tiendas: pocas, pero aparecen
    shop_count = 0
    if (x % 5 == 0 and y % 5 == 0):
        shop_count = 1
    if r >= 7 and (x % 4 == 0 and y % 4 == 0):
        shop_count = max(shop_count, 2)

    place_shops_random(rows, rng, shop_count)

    # enemigos decorativos: más lejos, más “packs”
    enemy_packs = 1
    if zlvl >= 10: enemy_packs = 2
    if zlvl >= 20: enemy_packs = 3
    if zlvl >= 40: enemy_packs = 4

    place_enemy_zones(rows, rng, enemy_packs)

    ensure_border_walls(rows)
    return parse(["".join(r) for r in rows])

MAPS = {}

for yy in range(MIN_C, MAX_C + 1):
    for xx in range(MIN_C, MAX_C + 1):
        key = zone_key(xx, yy)
        MAPS[key] = {
            "name": key,
            "level": zone_level(xx, yy),   # <-- MUY ÚTIL para el backend
            "exits": exits_for_zone(xx, yy),
            "map": build_map_for_zone(xx, yy),
        }

# alias opcional (compatibilidad)
MAPS["center"] = MAPS["0-0"]
