"""Content policy violation fixtures for safety testing.

Provides deterministic text samples for hard limits, soft limits, boundary
cases, and multilingual variations.  Used by QA-05 regression tests and
safety service unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViolationFixture:
    """A single content-policy violation test fixture."""

    label: str
    text: str
    expected_kind: str  # "hard" | "soft" | "boundary" | "safe"
    matching_terms: tuple[str, ...]
    description: str


# ---------------------------------------------------------------------------
# Hard limit fixtures
# ---------------------------------------------------------------------------

HARD_LIMIT_FIXTURES: tuple[ViolationFixture, ...] = (
    ViolationFixture(
        label="hard_graphic_sexual_direct",
        text="The scene contains graphic sexual content that is explicitly described.",
        expected_kind="hard",
        matching_terms=("graphic_sexual_content",),
        description="Direct hard-limit term match (graphic_sexual_content).",
    ),
    ViolationFixture(
        label="hard_harm_to_children_direct",
        text="A child is seriously harmed during the raid on the village.",
        expected_kind="hard",
        matching_terms=("harm_to_children",),
        description="Direct hard-limit term match (harm_to_children).",
    ),
    ViolationFixture(
        label="hard_sexual_assault_synonym",
        text="The NPC threatens sexual assault against the prisoner.",
        expected_kind="hard",
        matching_terms=("graphic_sexual_content",),
        description="Hard-limit synonym match via sexual assault.",
    ),
    ViolationFixture(
        label="hard_explicit_sex_synonym",
        text="The narrative describes explicit sex between the characters.",
        expected_kind="hard",
        matching_terms=("graphic_sexual_content",),
        description="Hard-limit synonym match via explicit sex.",
    ),
    ViolationFixture(
        label="hard_child_corpse_synonym",
        text="They found a child corpse in the basement of the old mill.",
        expected_kind="hard",
        matching_terms=("harm_to_children",),
        description="Hard-limit synonym match via child corpse.",
    ),
    ViolationFixture(
        label="hard_graphic_violence_as_hard_limit",
        text="The scene contains graphic violence with viscera and gore everywhere.",
        expected_kind="hard",
        matching_terms=("graphic_violence",),
        description="graphic_violence when configured as hard limit.",
    ),
)


# ---------------------------------------------------------------------------
# Soft limit fixtures
# ---------------------------------------------------------------------------

SOFT_LIMIT_FIXTURES: tuple[ViolationFixture, ...] = (
    ViolationFixture(
        label="soft_graphic_violence_fade",
        text="The battle involves graphic violence as blades cut through armor.",
        expected_kind="soft",
        matching_terms=("graphic_violence",),
        description="Soft-limit match for fade_to_black action.",
    ),
    ViolationFixture(
        label="soft_gore_synonym",
        text="Gore covers the floor of the ruined shrine.",
        expected_kind="soft",
        matching_terms=("graphic_violence",),
        description="Soft-limit synonym match via gore.",
    ),
    ViolationFixture(
        label="soft_dismember_synonym",
        text="The troll attempts to dismember the fallen warrior.",
        expected_kind="soft",
        matching_terms=("graphic_violence",),
        description="Soft-limit synonym match via dismember.",
    ),
    ViolationFixture(
        label="soft_ask_first",
        text="The scene hints at harm a child might witness.",
        expected_kind="soft",
        matching_terms=("harm_to_children",),
        description="Soft-limit ask_first when configured as soft limit.",
    ),
)


# ---------------------------------------------------------------------------
# Boundary case fixtures
# ---------------------------------------------------------------------------

BOUNDARY_FIXTURES: tuple[ViolationFixture, ...] = (
    ViolationFixture(
        label="boundary_partial_match_no_word_boundary",
        text="The graphics artist paints a violent mural on the wall.",
        expected_kind="safe",
        matching_terms=(),
        description="Partial match: 'graphic' in 'graphics' should not trigger 'graphic_violence'.",
    ),
    ViolationFixture(
        label="boundary_case_insensitive",
        text="GRAPHIC VIOLENCE erupted in the arena as the crowd watched.",
        expected_kind="soft",
        matching_terms=("graphic_violence",),
        description="Case-insensitive matching for policy terms.",
    ),
    ViolationFixture(
        label="boundary_underscore_vs_space",
        text="The topic of graphic sexual content was raised in discussion.",
        expected_kind="hard",
        matching_terms=("graphic_sexual_content",),
        description="Underscore/space normalization for policy terms.",
    ),
    ViolationFixture(
        label="boundary_adjacent_words",
        text="The child-corpse was hidden beneath the floorboards.",
        expected_kind="hard",
        matching_terms=("harm_to_children",),
        description="Hyphenated variant should match child corpse synonym.",
    ),
    ViolationFixture(
        label="boundary_safe_content",
        text="The hero enters the tavern and orders a drink from the barkeep.",
        expected_kind="safe",
        matching_terms=(),
        description="Completely safe content — no policy terms present.",
    ),
    ViolationFixture(
        label="boundary_vis_synonym",
        text="Viscera spills from the wounded creature onto the stone floor.",
        expected_kind="soft",
        matching_terms=("graphic_violence",),
        description="Low-frequency synonym (viscera) for graphic_violence.",
    ),
)


# ---------------------------------------------------------------------------
# Multilingual / encoding boundary fixtures
# ---------------------------------------------------------------------------

MULTILINGUAL_FIXTURES: tuple[ViolationFixture, ...] = (
    ViolationFixture(
        label="ml_safe_french",
        text="Le héros entre dans la taverne et commande une boisson.",
        expected_kind="safe",
        matching_terms=(),
        description="French text — no policy terms should match.",
    ),
    ViolationFixture(
        label="ml_safe_emoji_heavy",
        text="The hero 🗡️ enters the tavern 🍺 and greets the barkeep 👋.",
        expected_kind="safe",
        matching_terms=(),
        description="Emoji-heavy text — no policy terms should match.",
    ),
    ViolationFixture(
        label="ml_mixed_english_term",
        text="La escena contiene graphic violence in the arena.",
        expected_kind="soft",
        matching_terms=("graphic_violence",),
        description="Mixed Spanish/English — English policy term should still match.",
    ),
)


# ---------------------------------------------------------------------------
# All fixtures combined
# ---------------------------------------------------------------------------

ALL_FIXTURES: tuple[ViolationFixture, ...] = (
    HARD_LIMIT_FIXTURES + SOFT_LIMIT_FIXTURES + BOUNDARY_FIXTURES + MULTILINGUAL_FIXTURES
)


def fixtures_by_kind(kind: str) -> tuple[ViolationFixture, ...]:
    """Return all fixtures matching the given expected_kind."""
    return tuple(f for f in ALL_FIXTURES if f.expected_kind == kind)
