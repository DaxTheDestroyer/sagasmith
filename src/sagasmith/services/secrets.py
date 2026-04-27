"""SecretRef value object and resolver for keyring/env references."""

from __future__ import annotations

import os
from typing import Literal

import keyring
from pydantic import BaseModel, ConfigDict

from sagasmith.services.errors import SecretRefError


class SecretRef(BaseModel):
    """Reference to a secret stored in the OS keyring or an environment variable."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=False)

    kind: Literal["keyring", "env"]
    name: str
    account: str | None = None

    def model_post_init(self, __context: object) -> None:
        if self.kind == "env" and self.account is not None:
            raise ValueError("env secret references must not have an account")
        if self.kind == "keyring" and not self.account:
            raise ValueError("keyring secret references require an account")


def resolve_secret(ref: SecretRef) -> str:
    """Resolve a SecretRef to its plaintext value in-memory only.

    The returned string MUST NOT be logged by the caller.
    """
    if ref.kind == "env":
        value = os.environ.get(ref.name)
        if not value:
            raise SecretRefError(provider="<unknown>", ref_kind="env", reason="env var not set")
        return value

    # keyring
    assert ref.account is not None
    value = keyring.get_password(ref.name, ref.account)
    if not value:
        raise SecretRefError(
            provider="<unknown>", ref_kind="keyring", reason="keyring entry missing"
        )
    return value


def scrub_for_log(value: str | None) -> str:
    """Return a redaction placeholder for logging.

    '<redacted>' if value is non-empty, '<unset>' otherwise.
    """
    if value:
        return "<redacted>"
    return "<unset>"
