"""Spoiler-safe one-way visibility promotion heuristics."""

from __future__ import annotations

from typing import Any, Literal, cast

from sagasmith.vault.page import VaultPage

Visibility = Literal["player_known", "foreshadowed", "gm_only"]


def promote_visibility(page: VaultPage, context: dict[str, Any]) -> Visibility:
    """Return the page visibility after applying current turn context.

    Promotion is one-way:
    - Any page whose id/name/alias is present in ``scene_brief.present_entities``
      becomes ``player_known``.
    - A ``gm_only`` page mentioned in narration or player input becomes
      ``foreshadowed``.
    - Existing ``foreshadowed`` and ``player_known`` pages are never demoted.
    """

    current = cast(Visibility, page.frontmatter.visibility)
    if current == "player_known":
        return current

    if _is_present_entity(page, context):
        return "player_known"

    if current == "gm_only" and _is_mentioned(page, context):
        return "foreshadowed"

    return current


def _is_present_entity(page: VaultPage, context: dict[str, Any]) -> bool:
    scene_brief = context.get("scene_brief")
    if not isinstance(scene_brief, dict):
        return False
    values = scene_brief.get("present_entities", [])
    if not isinstance(values, list):
        return False
    needles = _entity_needles(page)
    return any(isinstance(value, str) and value.casefold() in needles for value in values)


def _is_mentioned(page: VaultPage, context: dict[str, Any]) -> bool:
    haystacks: list[str] = []
    player_input = context.get("player_input")
    if isinstance(player_input, str):
        haystacks.append(player_input)
    pending_input = context.get("pending_player_input")
    if isinstance(pending_input, str):
        haystacks.append(pending_input)
    recent_lines = context.get("recent_narration_lines", [])
    if isinstance(recent_lines, list):
        haystacks.extend(value for value in recent_lines if isinstance(value, str))
    pending_narration = context.get("pending_narration", [])
    if isinstance(pending_narration, list):
        haystacks.extend(value for value in pending_narration if isinstance(value, str))

    text = "\n".join(haystacks).casefold()
    if not text:
        return False
    return any(needle and needle in text for needle in _entity_needles(page))


def _entity_needles(page: VaultPage) -> set[str]:
    frontmatter = page.frontmatter
    values = [frontmatter.id, frontmatter.name, *frontmatter.aliases]
    return {value.casefold() for value in values if value}
