"""Archivist vault-page-upsert skill.

Deterministic function: vault_page_upsert(vault_service, entity_draft, visibility, session_number)
→ VaultPageUpsertResult(page, relative_path, action)
"""

from .logic import VaultPageUpsertResult, vault_page_upsert

__all__ = ["VaultPageUpsertResult", "vault_page_upsert"]
