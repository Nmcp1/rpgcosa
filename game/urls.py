from django.urls import path
from .views import *

urlpatterns = [
    # Personajes
    path("characters/create/", CreateCharacterView.as_view(), name="create_character"),
    path("characters/mine/", MyCharactersView.as_view(), name="my_characters"),
    path("characters/create-form/", create_character_form, name="create_character_form"),
    path("characters/lose-life/", LoseLifeView.as_view(), name="lose_life"),

    # Mundo
    path("world/", world_page, name="world_page"),
    path("world/move/", world_move, name="world_move"),
    path("world/enemies/", world_enemies, name="world_enemies"),

    # Batalla
    path("battle/start/", StartBattleView.as_view(), name="start_battle"),
    path("battle/sim/", battle_simulator, name="battle_simulator"),

    # Tienda / inventario / gacha / equipar
    path("shop/", shop_page, name="shop_page"),                  # menú de tienda
    path("shop/sell/", shop_sell_page, name="shop_sell_page"),   # vender orbes (HTML)
    path("shop/api/", ShopView.as_view(), name="shop_api"),      # API vender orbes
    path("inventory/", inventory_page, name="inventory_page"),
    path("inventory/api/", InventoryView.as_view(), name="inventory_api"),
    path("gacha/page/", gacha_page, name="gacha_page"),          # página de gacha (HTML)
    path("gacha/", GachaPullView.as_view(), name="gacha_api"),   # API de gacha
    path("equipment/equip/", EquipItemView.as_view(), name="equip_item"),
]
