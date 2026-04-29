"""Archivist vault-page-upsert skill.

Deterministic function: vault_page_upsert(vault_service, entity_draft, visibility, session_number)
→ (path: str, action: str)
"""

from .logic import vault_page_upsert

__all__ = ["vault_page_upsert"]
