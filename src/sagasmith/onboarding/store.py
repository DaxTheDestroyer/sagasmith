"""OnboardingStore — SQLite persistence for the three-part onboarding triple.

Commits PlayerProfile, ContentPolicy, and HouseRules atomically into the
campaign DB (schema v3, migration 0003_onboarding_records.sql).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from sagasmith.evals.redaction import RedactionCanary
from sagasmith.schemas.player import ContentPolicy, HouseRules, PlayerProfile
from sagasmith.services.errors import TrustServiceError

# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingTriple:
    """The validated onboarding output committed as a single unit."""

    player_profile: PlayerProfile
    content_policy: ContentPolicy
    house_rules: HouseRules


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingStore:
    """Read/write access to the three onboarding tables.

    Accepts an open ``sqlite3.Connection`` from ``open_campaign_db``.
    All mutations use ``with self.conn:`` for SQLite implicit transactions —
    either all three rows land or none do.
    """

    conn: sqlite3.Connection

    def commit(self, campaign_id: str, triple: OnboardingTriple) -> None:
        """Write all three onboarding records atomically.

        Uses ``INSERT OR REPLACE`` so calling commit() twice with different
        triples overwrites cleanly without raising a UNIQUE constraint error
        (ONBD-05 re-run support).

        Raises:
            TrustServiceError: If any field in the triple contains a
                secret-shaped string (RedactionCanary hit). This enforces the
                project-wide invariant that all free-form text is scanned before
                being persisted.
        """
        _canary = RedactionCanary()
        for label, payload in [
            ("player_profile", triple.player_profile.model_dump_json()),
            ("content_policy", triple.content_policy.model_dump_json()),
            ("house_rules", triple.house_rules.model_dump_json()),
        ]:
            hits = _canary.scan(payload)
            if hits:
                raise TrustServiceError(
                    f"onboarding commit rejected by redaction canary: "
                    f"record={label} label={hits[0].label}"
                )
        now = datetime.now(UTC).isoformat()
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO onboarding_player_profile "
                "(campaign_id, profile_json, committed_at) VALUES (?, ?, ?)",
                (campaign_id, triple.player_profile.model_dump_json(), now),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO onboarding_content_policy "
                "(campaign_id, policy_json, committed_at) VALUES (?, ?, ?)",
                (campaign_id, triple.content_policy.model_dump_json(), now),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO onboarding_house_rules "
                "(campaign_id, rules_json, committed_at) VALUES (?, ?, ?)",
                (campaign_id, triple.house_rules.model_dump_json(), now),
            )

    def reload(self, campaign_id: str) -> OnboardingTriple | None:
        """Return the committed triple for *campaign_id*, or None if absent.

        Raises:
            TrustServiceError: If only 1 or 2 of the 3 rows are present,
                indicating a partial write or manual DB corruption.
        """
        profile_row = self.conn.execute(
            "SELECT profile_json FROM onboarding_player_profile WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()

        policy_row = self.conn.execute(
            "SELECT policy_json FROM onboarding_content_policy WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()

        rules_row = self.conn.execute(
            "SELECT rules_json FROM onboarding_house_rules WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()

        present = [
            (profile_row is not None, "onboarding_player_profile"),
            (policy_row is not None, "onboarding_content_policy"),
            (rules_row is not None, "onboarding_house_rules"),
        ]

        found_count = sum(1 for flag, _ in present if flag)

        if found_count == 0:
            return None

        if found_count < 3:
            missing = [name for flag, name in present if not flag]
            raise TrustServiceError(
                f"partial onboarding state for {campaign_id!r}: missing {missing}"
            )

        # All three rows present — deserialize
        profile = PlayerProfile.model_validate_json(profile_row[0])  # type: ignore[index]
        content_policy = ContentPolicy.model_validate_json(policy_row[0])  # type: ignore[index]
        house_rules = HouseRules.model_validate_json(rules_row[0])  # type: ignore[index]

        return OnboardingTriple(
            player_profile=profile,
            content_policy=content_policy,
            house_rules=house_rules,
        )

    def exists(self, campaign_id: str) -> bool:
        """Return True if all three rows are present for *campaign_id*."""
        counts = [
            self.conn.execute(
                "SELECT COUNT(*) FROM onboarding_player_profile WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()[0],
            self.conn.execute(
                "SELECT COUNT(*) FROM onboarding_content_policy WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()[0],
            self.conn.execute(
                "SELECT COUNT(*) FROM onboarding_house_rules WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()[0],
        ]
        return all(c == 1 for c in counts)
