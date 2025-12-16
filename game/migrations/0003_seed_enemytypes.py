from django.db import migrations


def seed_enemytypes(apps, schema_editor):
    EnemyType = apps.get_model("game", "EnemyType")
    defaults = [
        {"name": "Goblin", "base_hp": 60, "base_atk": 10, "base_def": 4, "base_speed": 2},
        {"name": "Bandido", "base_hp": 80, "base_atk": 14, "base_def": 5, "base_speed": 3},
        {"name": "Lobo", "base_hp": 70, "base_atk": 12, "base_def": 4, "base_speed": 4},
        {"name": "Orco", "base_hp": 120, "base_atk": 18, "base_def": 8, "base_speed": 2},
        {"name": "Chamán", "base_hp": 90, "base_atk": 16, "base_def": 6, "base_speed": 3},
    ]
    for data in defaults:
        EnemyType.objects.get_or_create(name=data["name"], defaults=data)


def unseed_enemytypes(apps, schema_editor):
    EnemyType = apps.get_model("game", "EnemyType")
    names = ["Goblin", "Bandido", "Lobo", "Orco", "Chamán"]
    EnemyType.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0002_enemytype_character_coins_character_created_at_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_enemytypes, unseed_enemytypes),
    ]
