"""First-slice PF2e rules data helpers."""

from __future__ import annotations

from sagasmith.schemas.common import AttackProfile, CombatantState, InventoryItem
from sagasmith.schemas.mechanics import CharacterSheet


def make_first_slice_character() -> CharacterSheet:
    """Return the stable level-1 martial pregen used by the first slice."""

    return CharacterSheet(
        id="pc_valeros_first_slice",
        name="Valeros",
        level=1,
        ancestry="Human",
        background="Guard",
        class_name="Fighter",
        abilities={
            "strength": 18,
            "dexterity": 14,
            "constitution": 14,
            "intelligence": 10,
            "wisdom": 12,
            "charisma": 10,
        },
        proficiencies={
            "perception": "trained",
            "fortitude": "expert",
            "reflex": "trained",
            "will": "trained",
            "athletics": "trained",
            "intimidation": "trained",
            "survival": "trained",
            "acrobatics": "trained",
            "longsword": "trained",
            "shortbow": "trained",
        },
        max_hp=20,
        current_hp=20,
        armor_class=18,
        perception_modifier=5,
        saving_throws={"fortitude": 7, "reflex": 5, "will": 4},
        skills={
            "athletics": 7,
            "intimidation": 3,
            "survival": 4,
            "acrobatics": 5,
        },
        attacks=[
            AttackProfile(
                id="longsword",
                name="longsword",
                modifier=7,
                damage="1d8+4 slashing",
                traits=["versatile piercing"],
            ),
            AttackProfile(
                id="shortbow",
                name="shortbow",
                modifier=5,
                damage="1d6 piercing",
                traits=["deadly d10", "volley 30 feet"],
                range="60 feet",
            ),
        ],
        inventory=[
            InventoryItem(id="longsword", name="longsword", quantity=1, bulk=1.0),
            InventoryItem(id="shortbow", name="shortbow", quantity=1, bulk=1.0),
            InventoryItem(id="adventurers_pack", name="adventurer's pack", quantity=1, bulk=1.0),
        ],
        conditions=[],
    )


def make_first_slice_enemies() -> tuple[CombatantState, CombatantState]:
    """Return the two typed local enemy records supported in the first slice."""

    weak_melee = CombatantState(
        id="enemy_weak_melee",
        name="Weak Melee Foe",
        level=-1,
        current_hp=8,
        max_hp=8,
        armor_class=15,
        perception_modifier=3,
        attacks=[
            AttackProfile(
                id="rusty_blade",
                name="rusty blade",
                modifier=5,
                damage="1d6 slashing",
                traits=["agile"],
            )
        ],
        saving_throws={"fortitude": 4, "reflex": 5, "will": 2},
        xp_value=20,
        conditions=[],
    )
    weak_ranged = CombatantState(
        id="enemy_weak_ranged",
        name="Weak Ranged Foe",
        level=-1,
        current_hp=6,
        max_hp=6,
        armor_class=14,
        perception_modifier=4,
        attacks=[
            AttackProfile(
                id="shortbow",
                name="shortbow",
                modifier=5,
                damage="1d6 piercing",
                traits=["deadly d10"],
                range="60 feet",
            )
        ],
        saving_throws={"fortitude": 2, "reflex": 5, "will": 3},
        xp_value=20,
        conditions=[],
    )
    return weak_melee, weak_ranged
