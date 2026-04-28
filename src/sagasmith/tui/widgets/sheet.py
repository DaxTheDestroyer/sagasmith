"""Plain-text character sheet rendering for the Phase 5 TUI surface."""

from __future__ import annotations

from sagasmith.schemas.mechanics import CharacterSheet


_TRAINED_SKILL_ORDER = ("athletics", "intimidation", "survival", "acrobatics")
_SAVE_ORDER = ("fortitude", "reflex", "will")


def _format_modifier(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


def render_character_sheet(sheet: CharacterSheet) -> str:
    """Render a read-only first-slice character sheet as stable plain text."""

    conditions = ", ".join(condition.name for condition in sheet.conditions) if sheet.conditions else "none"
    lines = [
        "Character Sheet",
        "",
        "Identity",
        f"Name: {sheet.name}",
        f"Level: {sheet.level}",
        f"Ancestry: {sheet.ancestry}",
        f"Background: {sheet.background}",
        f"Class: {sheet.class_name}",
        "",
        "Durability",
        f"HP: {sheet.current_hp}/{sheet.max_hp}",
        f"AC: {sheet.armor_class}",
        f"Conditions: {conditions}",
        "",
        "Perception and saves",
        f"Perception: {_format_modifier(sheet.perception_modifier)}",
    ]

    for save in _SAVE_ORDER:
        if save in sheet.saving_throws:
            lines.append(f"{save.title()}: {_format_modifier(sheet.saving_throws[save])}")

    lines.extend(["", "Skills"])
    rendered_skills: set[str] = set()
    for skill in _TRAINED_SKILL_ORDER:
        if skill in sheet.skills:
            lines.append(f"{skill.title()}: {_format_modifier(sheet.skills[skill])}")
            rendered_skills.add(skill)
    for skill in sorted(set(sheet.skills) - rendered_skills):
        lines.append(f"{skill.title()}: {_format_modifier(sheet.skills[skill])}")

    lines.extend(["", "Attacks"])
    for attack in sheet.attacks:
        detail = f"{attack.name}: {_format_modifier(attack.modifier)}, {attack.damage}"
        extras: list[str] = []
        if attack.range is not None:
            extras.append(f"range {attack.range}")
        if attack.traits:
            extras.append("traits " + ", ".join(attack.traits))
        if extras:
            detail += " (" + "; ".join(extras) + ")"
        lines.append(detail)

    lines.extend(["", "Inventory"])
    for item in sheet.inventory:
        lines.append(f"{item.name} x{item.quantity} (Bulk {item.bulk:g})")

    lines.extend(["", "Esc closes sheet. Type an action when ready."])
    return "\n".join(lines)
