"""Secret-shaped string canary for schemas, fixtures, and smoke output."""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openrouter_key", re.compile(r"sk-or-v1-[A-Za-z0-9]{16,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("bearer_header", re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._\-]{16,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("high_entropy_hex", re.compile(r"\b[a-f0-9]{48,}\b")),
)


@dataclass(frozen=True)
class RedactionHit:
    """A single secret-shaped canary match."""

    label: str
    match: str
    index: int


@dataclass(frozen=True)
class RedactionCanary:
    """Scan displayable or persisted text for secret-shaped strings."""

    patterns: tuple[tuple[str, re.Pattern[str]], ...] = DEFAULT_SECRET_PATTERNS

    def scan(self, text: str) -> list[RedactionHit]:
        """Return every canary hit in text."""

        hits: list[RedactionHit] = []
        for label, pattern in self.patterns:
            for match in pattern.finditer(text):
                hits.append(RedactionHit(label=label, match=match.group(0), index=match.start()))
        return hits
