"""Phase prompt catalog and answer parsers for the onboarding wizard.

No Textual, CLI, or I/O imports. Pure domain functions only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OnboardingPhase(StrEnum):
    """Ordered onboarding phases (mirrors GAME_SPEC §7.1)."""

    WELCOME = "welcome"
    TONE = "tone"
    PILLARS = "pillars"
    COMBAT_DICE_UX = "combat_dice_ux"
    CONTENT_POLICY = "content_policy"
    LENGTH_DEATH = "length_death"
    BUDGET = "budget"
    CHARACTER_MODE = "character_mode"
    REVIEW = "review"
    DONE = "done"


class PromptFieldKind(StrEnum):
    """Supported answer input kinds."""

    FREE_TEXT = "free_text"
    MULTI_TEXT = "multi_text"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    PILLAR_BUDGET = "pillar_budget"
    SOFT_LIMIT_MAP = "soft_limit_map"
    FLOAT = "float"
    BOOL = "bool"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_VALID_SOFT_LIMIT_VALUES = frozenset({"fade_to_black", "avoid_detail", "ask_first"})
_VALID_BOOL_TRUTHY = frozenset({"true", "yes", "y", "1"})
_VALID_BOOL_FALSY = frozenset({"false", "no", "n", "0"})
_PILLAR_KEYS = ("combat", "exploration", "social", "puzzle")


@dataclass(frozen=True)
class PromptField:
    """A single answerable field within a phase prompt."""

    id: str
    label: str
    kind: PromptFieldKind
    choices: tuple[str, ...] = field(default_factory=tuple)
    required: bool = True
    help_text: str = ""


@dataclass(frozen=True)
class PhasePrompt:
    """Immutable description of a single onboarding phase's prompts."""

    phase: OnboardingPhase
    title: str
    description: str
    fields: tuple[PromptField, ...]


# ---------------------------------------------------------------------------
# Phase order (terminal DONE is not in ONBOARDING_PHASES)
# ---------------------------------------------------------------------------

PHASE_ORDER: tuple[OnboardingPhase, ...] = (
    OnboardingPhase.WELCOME,
    OnboardingPhase.TONE,
    OnboardingPhase.PILLARS,
    OnboardingPhase.COMBAT_DICE_UX,
    OnboardingPhase.CONTENT_POLICY,
    OnboardingPhase.LENGTH_DEATH,
    OnboardingPhase.BUDGET,
    OnboardingPhase.CHARACTER_MODE,
    OnboardingPhase.REVIEW,
    OnboardingPhase.DONE,
)


# ---------------------------------------------------------------------------
# Phase prompt catalog
# ---------------------------------------------------------------------------

ONBOARDING_PHASES: tuple[PhasePrompt, ...] = (
    PhasePrompt(
        phase=OnboardingPhase.WELCOME,
        title="Welcome + Premise",
        description=(
            "Let's set up your campaign. First, tell me about the genre "
            "of story you want to experience."
        ),
        fields=(
            PromptField(
                id="genre",
                label="Genre",
                kind=PromptFieldKind.MULTI_TEXT,
                help_text="Name 1-3 genres, e.g. high_fantasy, cosmic_horror",
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.TONE,
        title="Tone & Touchstones",
        description="Describe the emotional tone and narrative touchstones for your campaign.",
        fields=(
            PromptField(
                id="tone",
                label="Tone Keywords",
                kind=PromptFieldKind.MULTI_TEXT,
                help_text="1-5 tone keywords",
            ),
            PromptField(
                id="touchstones",
                label="Touchstones",
                kind=PromptFieldKind.MULTI_TEXT,
                help_text="Name 3 books/games/films the story should feel like",
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.PILLARS,
        title="Pillars & Pacing",
        description=(
            "Distribute 10 points among the four adventure pillars, then choose your "
            "preferred campaign pacing."
        ),
        fields=(
            PromptField(
                id="pillar_budget",
                label="Pillar Budget",
                kind=PromptFieldKind.PILLAR_BUDGET,
                choices=("combat", "exploration", "social", "puzzle"),
                help_text="Allocate 10 points across combat, exploration, social, puzzle",
            ),
            PromptField(
                id="pacing",
                label="Pacing",
                kind=PromptFieldKind.SINGLE_CHOICE,
                choices=("slow", "medium", "fast"),
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.COMBAT_DICE_UX,
        title="Combat Style & Dice UX",
        description="Configure combat resolution and dice display preferences.",
        fields=(
            PromptField(
                id="combat_style",
                label="Combat Style",
                kind=PromptFieldKind.SINGLE_CHOICE,
                choices=("theater_of_mind",),
                help_text="MVP only offers theater-of-mind combat",
            ),
            PromptField(
                id="dice_ux",
                label="Dice UX",
                kind=PromptFieldKind.SINGLE_CHOICE,
                choices=("auto", "reveal", "hidden"),
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.CONTENT_POLICY,
        title="Content Policy",
        description=(
            "Define your content safety preferences. All fields are optional. "
            "You must explicitly name any soft limits you want applied."
        ),
        fields=(
            PromptField(
                id="hard_limits",
                label="Hard Limits",
                kind=PromptFieldKind.MULTI_TEXT,
                required=False,
                help_text="Topics to redline entirely",
            ),
            PromptField(
                id="soft_limits",
                label="Soft Limits",
                kind=PromptFieldKind.SOFT_LIMIT_MAP,
                required=False,
                help_text=(
                    "Map topic → fade_to_black | avoid_detail | ask_first. "
                    "No default values; you must state each one explicitly."
                ),
            ),
            PromptField(
                id="preferences",
                label="Preferences",
                kind=PromptFieldKind.MULTI_TEXT,
                required=False,
                help_text="Positive content preferences",
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.LENGTH_DEATH,
        title="Campaign Length & Death Policy",
        description="Choose how long the campaign runs and how character death is handled.",
        fields=(
            PromptField(
                id="campaign_length",
                label="Campaign Length",
                kind=PromptFieldKind.SINGLE_CHOICE,
                choices=("one_shot", "arc", "open_ended"),
            ),
            PromptField(
                id="death_policy",
                label="Death Policy",
                kind=PromptFieldKind.SINGLE_CHOICE,
                choices=("hardcore", "heroic_recovery", "retire_and_continue"),
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.BUDGET,
        title="Session Budget",
        description="Set an AI cost cap to keep spending in check.",
        fields=(
            PromptField(
                id="per_session_usd",
                label="Per-Session USD Cap",
                kind=PromptFieldKind.FLOAT,
                help_text="Per-session USD cap, e.g. 2.50",
            ),
            PromptField(
                id="hard_stop",
                label="Hard Stop on Budget",
                kind=PromptFieldKind.BOOL,
                help_text="If True, refuse the next call that would exceed budget",
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.CHARACTER_MODE,
        title="Character Mode",
        description="Choose how your character is created.",
        fields=(
            PromptField(
                id="character_mode",
                label="Character Mode",
                kind=PromptFieldKind.SINGLE_CHOICE,
                choices=("guided", "player_led", "pregenerated"),
            ),
        ),
    ),
    PhasePrompt(
        phase=OnboardingPhase.REVIEW,
        title="Review & Confirm",
        description=(
            "Review your choices. Confirm to commit, or use edit() to adjust any field "
            "before proceeding."
        ),
        fields=(
            PromptField(
                id="review_confirmed",
                label="Confirm Choices",
                kind=PromptFieldKind.BOOL,
                help_text="Set to True to commit your choices, False to continue editing",
            ),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Answer parser
# ---------------------------------------------------------------------------

# Raw answer type accepted by parse_answer before parsing
RawAnswer = str | int | float | bool | list[object] | dict[str, object] | None


def parse_answer(
    field: PromptField, raw: object
) -> tuple[object, list[str]]:
    """Parse and validate a raw answer against a PromptField definition.

    Returns ``(parsed_value, errors)`` where *errors* is empty on success.
    If *required* is False and *raw* is None/empty-string/empty-list/empty-dict,
    returns a sensible empty value with no errors.
    """
    kind = field.kind

    if kind == PromptFieldKind.FREE_TEXT:
        return _parse_free_text(field, raw)
    if kind == PromptFieldKind.MULTI_TEXT:
        return _parse_multi_text(field, raw)
    if kind == PromptFieldKind.SINGLE_CHOICE:
        return _parse_single_choice(field, raw)
    if kind == PromptFieldKind.MULTI_CHOICE:
        return _parse_multi_choice(field, raw)
    if kind == PromptFieldKind.PILLAR_BUDGET:
        return _parse_pillar_budget(field, raw)
    if kind == PromptFieldKind.SOFT_LIMIT_MAP:
        return _parse_soft_limit_map(field, raw)
    if kind == PromptFieldKind.FLOAT:
        return _parse_float(field, raw)
    if kind == PromptFieldKind.BOOL:
        return _parse_bool(field, raw)

    return raw, [f"unknown field kind: {kind}"]


# ---------------------------------------------------------------------------
# Per-kind parsers
# ---------------------------------------------------------------------------


def _parse_free_text(field: PromptField, raw: object) -> tuple[object, list[str]]:
    if not isinstance(raw, str):
        raw = "" if raw is None else str(raw)
    value = raw.strip()
    if field.required and not value:
        return value, [f"'{field.id}' is required"]
    return value, []


def _parse_multi_text(field: PromptField, raw: object) -> tuple[object, list[str]]:
    if raw is None:
        items: list[str] = []
    elif isinstance(raw, list):
        items = [str(x).strip() for x in raw]
    elif isinstance(raw, str):
        items = [x.strip() for x in raw.split(",")]
    else:
        items = [str(raw).strip()]

    # Remove blank entries
    items = [x for x in items if x]

    if field.required and not items:
        return items, [f"'{field.id}' requires at least one value"]
    return items, []


def _parse_single_choice(field: PromptField, raw: object) -> tuple[object, list[str]]:
    value = str(raw).strip() if raw is not None else ""
    if value not in field.choices:
        choices_str = ", ".join(field.choices)
        return value, [f"'{field.id}' must be one of {{{choices_str}}}"]
    return value, []


def _parse_multi_choice(field: PromptField, raw: object) -> tuple[object, list[str]]:
    if raw is None:
        selected: list[str] = []
    elif isinstance(raw, list):
        selected = [str(x).strip() for x in raw]
    elif isinstance(raw, str):
        selected = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        selected = [str(raw).strip()]

    invalid = [x for x in selected if x not in field.choices]
    if invalid:
        choices_str = ", ".join(field.choices)
        return selected, [
            f"'{field.id}' values {invalid!r} are not in allowed choices {{{choices_str}}}"
        ]
    return selected, []


def _parse_pillar_budget(field: PromptField, raw: object) -> tuple[object, list[str]]:
    """Accept dict[str, int]; validate 4 required keys, all ≥ 0, sum == 10.

    Returns normalized ``dict[str, float]`` (each / 10.0) on success.
    """
    if not isinstance(raw, dict):
        return {}, ["pillar_budget must be a dict with keys: combat, exploration, social, puzzle"]

    required_keys = set(_PILLAR_KEYS)
    actual_keys = set(raw.keys())
    if actual_keys != required_keys:
        missing = sorted(required_keys - actual_keys)
        extra = sorted(actual_keys - required_keys)
        return {}, [
            f"pillar_budget must have exactly keys {sorted(required_keys)}; "
            f"missing={missing}, extra={extra}"
        ]

    errors: list[str] = []
    int_values: dict[str, int] = {}
    for key in _PILLAR_KEYS:
        raw_val = raw[key]
        if not isinstance(raw_val, (int, float)) or isinstance(raw_val, bool):
            errors.append(f"pillar_budget[{key!r}] must be a non-negative integer, got {raw_val!r}")
            continue
        int_val = int(raw_val)
        if int_val < 0:
            errors.append(f"pillar_budget[{key!r}] must be >= 0, got {int_val}")
        else:
            int_values[key] = int_val

    if errors:
        return {}, errors

    total = sum(int_values.values())
    if total != 10:
        return {}, [f"pillar points must sum to 10, got {total}"]

    normalized = {k: int_values[k] / 10.0 for k in _PILLAR_KEYS}
    return normalized, []


def _parse_soft_limit_map(field: PromptField, raw: object) -> tuple[object, list[str]]:
    """Accept dict[str, str]; each value must be a valid SoftLimitDisposition."""
    if raw is None or raw == {}:
        return {}, []
    if not isinstance(raw, dict):
        return {}, [
            "soft_limits must be a dict mapping topic strings to "
            "'fade_to_black', 'avoid_detail', or 'ask_first'"
        ]

    errors: list[str] = []
    validated: dict[str, str] = {}
    for key, val in raw.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"soft_limits key {key!r} must be a non-empty string")
            continue
        if val not in _VALID_SOFT_LIMIT_VALUES:
            allowed = ", ".join(sorted(_VALID_SOFT_LIMIT_VALUES))
            errors.append(
                f"soft_limits[{key!r}] value {val!r} must be one of {{{allowed}}}"
            )
            continue
        validated[key.strip()] = val

    if errors:
        return {}, errors
    return validated, []


def _parse_float(field: PromptField, raw: object) -> tuple[object, list[str]]:
    if isinstance(raw, bool):
        return 0.0, [f"'{field.id}' must be a non-negative number, got bool"]
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0, [f"'{field.id}' must be a non-negative number, got {raw!r}"]
    if value < 0:
        return value, [f"'{field.id}' must be >= 0, got {value}"]
    return value, []


def _parse_bool(field: PromptField, raw: object) -> tuple[object, list[str]]:
    if isinstance(raw, bool):
        return raw, []
    if isinstance(raw, str):
        lower = raw.strip().lower()
        if lower in _VALID_BOOL_TRUTHY:
            return True, []
        if lower in _VALID_BOOL_FALSY:
            return False, []
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw), []
    return False, [
        f"'{field.id}' must be a boolean or one of "
        f"{{true, false, yes, no, y, n, 1, 0}}, got {raw!r}"
    ]
