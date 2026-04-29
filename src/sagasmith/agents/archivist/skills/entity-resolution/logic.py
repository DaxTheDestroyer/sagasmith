"""Logic for entity-resolution skill."""

from __future__ import annotations

from sagasmith.vault import EntityResolver, VaultPage


def resolve_entity(
    name: str,
    entity_type: str | None,
    resolver: EntityResolver,
) -> tuple[VaultPage | None, str]:
    """Resolve an entity name to a vault page or signal creation.

    Args:
        name: Raw entity name (e.g., "Orym the Humble").
        entity_type: Optional type hint (e.g., "npc", "location").
        resolver: The EntityResolver service from the vault.

    Returns:
        (page, "matched") if found, else (None, "create_new").
    """
    page = resolver.resolve(name, entity_type)
    if page is not None:
        return page, "matched"
    return None, "create_new"
