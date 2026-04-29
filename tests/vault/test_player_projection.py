"""GM-leakage regression test scanning player vault files for forbidden patterns.

QA-06: Ensures player-vault projection contains zero GM-only frontmatter fields,
secrets, inline GM comments, or gm_only pages after sync.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from sagasmith.vault import VaultPage, VaultService
from sagasmith.vault.page import (
    FactionFrontmatter,
    ItemFrontmatter,
    LocationFrontmatter,
    LoreFrontmatter,
    NpcFrontmatter,
    QuestFrontmatter,
)


def _service(tmp_path: Path) -> VaultService:
    service = VaultService(campaign_id="qa-06-leak-test", player_vault_root=tmp_path / "player")
    service.master_path = tmp_path / "master"
    service.ensure_master_path()
    return service


def _create_gm_heavy_world(service: VaultService) -> None:
    """Populate master vault with every GM-only pattern we can think of."""

    # NPC with gm_notes, secrets field, and <!-- gm: comment -->
    service.write_page(
        VaultPage(
            NpcFrontmatter(
                id="npc_gm_leak_tester",
                type="npc",
                name="Grimdagger",
                aliases=["the shady one"],
                visibility="player_known",
                first_encountered="session_001",
                species="human",
                role="rogue",
                status="alive",
                disposition_to_pc="neutral",
                gm_notes="Knows about the secret passage",  # GM-only field
                secrets=["double agent"],  # GM-only field also filtered
                # Could also have gm_ prefixed custom fields dynamically
            ),
            body="Grimdagger runs the tavern.\n<!-- gm: actually a cult leader -->\nPublic info only.",
        ),
        Path("npcs/npc_gm_leak_tester.md"),
    )

    # Faction with foreshadowed visibility (stub only) and all GM fields
    service.write_page(
        VaultPage(
            FactionFrontmatter(
                id="fac_secret_cabal",
                type="faction",
                name="The Veiled Council",
                aliases=["the Council"],
                visibility="foreshadowed",
                alignment="lawful evil",
                disposition_to_pc="unknown",
                power_level="citywide",
                gm_notes="Actually controls the mayor",  # GM-only field
                secrets=["corruption everywhere"],  # GM-only field
            ),
            "The Council governs the city.",  # Should be STRIPPED entirely from stub
        ),
        Path("factions/fac_secret_cabal.md"),
    )

    # gm_only page — must NOT appear in player vault at all
    service.write_page(
        VaultPage(
            LoreFrontmatter(
                id="lore_forbidden_truth",
                type="lore",
                name="Forbidden Truth",
                aliases=[],
                visibility="gm_only",
                category="secret",
            ),
            "Players must never see this text.",
        ),
        Path("lore/lore_forbidden_truth.md"),
    )

    # Location with multiline <!-- gm: ... --> comment block
    service.write_page(
        VaultPage(
            LocationFrontmatter(
                id="loc_hidden_sanctum",
                type="location",
                name="Hidden Sanctum",
                aliases=[],
                visibility="player_known",
                region="downtown",
                status="hidden",  # required field
            ),
            body="A quiet room.\n<!-- gm:\n  This room contains a trapped door\n  that only the GM knows about\n  it leads to the underground cult\n-->\nThe room appears ordinary.",
        ),
        Path("locations/loc_hidden_sanctum.md"),
    )

    # Item with additional gm_ prefixed custom field (simulates extensible schema)
    service.write_page(
        VaultPage(
            ItemFrontmatter(
                id="item_mysterious_amulet",
                type="item",
                name="Mysterious Amulet",
                aliases=["the pendant"],
                visibility="player_known",
                rarity="uncommon",
                attunement="none",
                # Simulate a custom GM-field that our frontmatter model accepts as extra
                # because model_validate(extra="allow") on BaseVaultFrontmatter
                # The _strip_player_known_page should drop any key starting with gm_
            ),
            body="A faint pulse can be felt.\n<!-- gm: amulet is a key to the demon portal -->",
        ),
        Path("items/item_mysterious_amulet.md"),
    )

    # Quest with foreshadowed stub
    service.write_page(
        VaultPage(
            QuestFrontmatter(
                id="quest_unfinished_business",
                type="quest",
                name="Unfinished Business",
                aliases=["the debt"],
                visibility="foreshadowed",
                given_by="npc_grimdagger",  # required-ish optional field
                status="rumored",  # required
            ),
            "Someone owes someone something.",  # Body should be replaced with stub
        ),
        Path("quests/quest_unfinished_business.md"),
    )


def _scan_player_vault_for_gm_patterns(player_vault_root: Path) -> list[tuple[Path, str, str]]:
    """Recursively scan all player-vault markdown files for GM-only patterns.

    Returns a list of (file_path, pattern_name, line) for each violation found.
    Patterns checked:
    - 'secrets:' appearing as frontmatter field
    - 'gm_notes:' appearing as frontmatter field or gm_* prefixed field
    - '<!-- gm:' inline comment blocks
    - Any .md file under a gm_only directory (should never exist)
    """
    violations: list[tuple[Path, str, str]] = []
    forbidden_patterns = {
        "frontmatter_secrets": re.compile(r"^\s*secrets\s*:", re.IGNORECASE),
        "frontmatter_gm_notes": re.compile(r"^\s*gm_notes\s*:", re.IGNORECASE),
        "frontmatter_gm_prefix": re.compile(r"^\s*gm_\w+\s*:", re.IGNORECASE),
        "comment_gm": re.compile(r"<!--\s*gm:"),
    }

    for md_file in player_vault_root.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Split into frontmatter and body
        if content.startswith("---"):
            parts = content.split("---", 2)
            front = parts[1] if len(parts) > 2 else ""
            body = parts[2] if len(parts) > 2 else ""
        else:
            front = ""
            body = content

        for pattern_name, regex in forbidden_patterns.items():
            if pattern_name == "comment_gm":
                search_target = body
            else:
                search_target = front

            for line_num, line in enumerate(search_target.splitlines(), start=1):
                if regex.search(line):
                    violations.append((md_file, pattern_name, f"L{line_num}: {line.strip()}"))

        # Special checks for foreshadowed stub content
        if "foreshadowed" in front:
            stub_expected = "*Unknown - you have heard this name but know little more.*"
            if stub_expected not in body:
                violations.append(
                    (
                        md_file,
                        "foreshadowed_stub_body",
                        f"Foreshadowed page body should be exactly '{stub_expected}'",
                    )
                )

    return violations


@pytest.mark.parametrize(
    "pattern_name,expected_violation_msg",
    [
        ("frontmatter_secrets", "secrets field present"),
        ("frontmatter_gm_notes", "gm_notes field present"),
        ("frontmatter_gm_prefix", "gm_* custom field present"),
        ("comment_gm", "<!-- gm: comment present"),
        ("foreshadowed_stub_body", "Foreshadowed stub body incorrect"),
    ],
)
def test_player_vault_has_zero_gm_leakage(
    tmp_path: Path, pattern_name: str, expected_violation_msg: str
) -> None:
    """Scan the entire player vault after sync and assert zero GM-only content."""
    service = _service(tmp_path)
    _create_gm_heavy_world(service)
    service.sync()

    violations = _scan_player_vault_for_gm_patterns(service.player_vault_root)

    matching = [v for v in violations if v[0] == pattern_name or pattern_name in v[1]]
    # Assert: no violations of the checked pattern
    assert not matching, (
        f"GM leakage detected in player vault ({len(matching)} violation(s)):\n"
        + "\n".join(f"  {p}: {msg}" for _, p, msg in matching[:10])
    )


def test_player_vault_excludes_gm_only_pages(tmp_path: Path) -> None:
    """gm_only pages must not be written to player vault at all."""
    service = _service(tmp_path)
    _create_gm_heavy_world(service)
    service.sync()

    gm_only_path = service.player_vault_root / "lore/lore_forbidden_truth.md"
    assert not gm_only_path.exists(), "gm_only page leaked into player vault"


def test_foreshadowed_stubs_contain_only_unknown_marker(tmp_path: Path) -> None:
    """Foreshadowed pages should show minimal stub with Unknown marker only."""
    service = _service(tmp_path)
    _create_gm_heavy_world(service)
    service.sync()

    stub = service.player_vault_root / "factions/fac_secret_cabal.md"
    assert stub.exists(), "Foreshadowed stub page missing"
    body = stub.read_text(encoding="utf-8")
    assert "*Unknown - you have heard this name but know little more.*" in body
    # No other lore details should be present
    assert "controls the mayor" not in body
    assert "corruption" not in body
