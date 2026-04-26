"""Enumerations for SagaSmith runtime schemas."""

from __future__ import annotations

from enum import StrEnum


class Phase(StrEnum):
    """Graph lifecycle phases."""

    ONBOARDING = "onboarding"
    CHARACTER_CREATION = "character_creation"
    PLAY = "play"
    COMBAT = "combat"
    PAUSED = "paused"
    SESSION_END = "session_end"


class ProficiencyRank(StrEnum):
    """PF2e proficiency ranks used by character sheets."""

    UNTRAINED = "untrained"
    TRAINED = "trained"
    EXPERT = "expert"
    MASTER = "master"
    LEGENDARY = "legendary"


class DeltaSource(StrEnum):
    """Allowed authority sources for state deltas."""

    RULES = "rules"
    ORACLE = "oracle"
    ARCHIVIST = "archivist"
    SAFETY = "safety"
    USER = "user"


class DeltaOperation(StrEnum):
    """Replayable state-delta operations."""

    SET = "set"
    INCREMENT = "increment"
    APPEND = "append"
    REMOVE = "remove"


class DegreeOfSuccess(StrEnum):
    """PF2e degree-of-success values."""

    CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"


class CheckKind(StrEnum):
    """Supported first-slice check proposal kinds."""

    SKILL = "skill"
    ATTACK = "attack"
    SAVE = "save"
    INITIATIVE = "initiative"
    FLAT = "flat"


class PositionTag(StrEnum):
    """Theater-of-mind position tags."""

    CLOSE = "close"
    NEAR = "near"
    FAR = "far"
    BEHIND_COVER = "behind_cover"


class SafetyEventKind(StrEnum):
    """Player-visible safety event kinds."""

    PAUSE = "pause"
    LINE = "line"
    SOFT_LIMIT_FADE = "soft_limit_fade"
    POST_GATE_REWRITE = "post_gate_rewrite"
    FALLBACK = "fallback"


class PacingMode(StrEnum):
    """Onboarding pacing choices."""

    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class CombatStyle(StrEnum):
    """Combat presentation styles; MVP accepts theater-of-mind only."""

    THEATER_OF_MIND = "theater_of_mind"
    GRID = "grid"


class DiceUxMode(StrEnum):
    """Dice-result presentation modes."""

    AUTO = "auto"
    REVEAL = "reveal"
    HIDDEN = "hidden"


class CampaignLength(StrEnum):
    """Onboarding campaign length preferences."""

    ONE_SHOT = "one_shot"
    ARC = "arc"
    OPEN_ENDED = "open_ended"


class CharacterMode(StrEnum):
    """Character creation modes."""

    GUIDED = "guided"
    PLAYER_LED = "player_led"
    PREGENERATED = "pregenerated"


class DeathPolicy(StrEnum):
    """Player-selected death/failure handling policy."""

    HARDCORE = "hardcore"
    HEROIC_RECOVERY = "heroic_recovery"
    RETIRE_AND_CONTINUE = "retire_and_continue"


class ConflictCategory(StrEnum):
    """Canon conflict categories."""

    RETCON_INTENT = "retcon_intent"
    PC_MISBELIEF = "pc_misbelief"
    NARRATOR_ERROR = "narrator_error"


class ConflictSeverity(StrEnum):
    """Canon conflict severity levels."""

    MINOR = "minor"
    MAJOR = "major"
