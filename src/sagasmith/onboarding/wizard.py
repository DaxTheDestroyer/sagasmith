"""Onboarding wizard state machine.

Pure domain logic — no Textual, no CLI, no SQLite.
Drive via ``OnboardingWizard.step()`` with validated answer dicts.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagasmith.schemas.common import BudgetPolicy
from sagasmith.schemas.player import ContentPolicy, HouseRules, PlayerProfile

from .prompts import (
    ONBOARDING_PHASES,
    PHASE_ORDER,
    OnboardingPhase,
    PhasePrompt,
    PromptField,
    parse_answer,
)

# ---------------------------------------------------------------------------
# Draft state (accumulates answers across phases)
# ---------------------------------------------------------------------------


@dataclass
class _DraftState:
    """Mutable answer slots filled incrementally by wizard.step()."""

    # WELCOME
    genre: list[str] | None = None
    # TONE
    tone: list[str] | None = None
    touchstones: list[str] | None = None
    # PILLARS
    pillar_weights: dict[str, float] | None = None  # normalized
    pacing: str | None = None
    # COMBAT_DICE_UX
    combat_style: str | None = None
    dice_ux: str | None = None
    # CONTENT_POLICY
    hard_limits: list[str] | None = None
    soft_limits: dict[str, str] | None = None
    preferences: list[str] | None = None
    # LENGTH_DEATH
    campaign_length: str | None = None
    death_policy: str | None = None
    # BUDGET
    per_session_usd: float | None = None
    hard_stop: bool | None = None
    # CHARACTER_MODE
    character_mode: str | None = None


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepResult:
    """Return value of OnboardingWizard.step()."""

    next_prompt: PhasePrompt | None  # None when phase == DONE
    errors: list[str]
    phase: OnboardingPhase  # current phase after step()


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

_PHASE_INDEX: dict[OnboardingPhase, PhasePrompt] = {p.phase: p for p in ONBOARDING_PHASES}

# Fields that map to _DraftState attributes directly by field.id
_DRAFT_FIELD_MAP: dict[str, str] = {
    "genre": "genre",
    "tone": "tone",
    "touchstones": "touchstones",
    "pillar_budget": "pillar_weights",  # pillar_budget field → pillar_weights slot
    "pacing": "pacing",
    "combat_style": "combat_style",
    "dice_ux": "dice_ux",
    "hard_limits": "hard_limits",
    "soft_limits": "soft_limits",
    "preferences": "preferences",
    "campaign_length": "campaign_length",
    "death_policy": "death_policy",
    "per_session_usd": "per_session_usd",
    "hard_stop": "hard_stop",
    "character_mode": "character_mode",
}

# Field-path prefix → affected record kind for edit() re-validation
_EDIT_RECORD_KINDS = ("profile", "content_policy", "house_rules")

# combat_style is fixed in MVP
_FIXED_COMBAT_STYLE = "theater_of_mind"


class OnboardingWizard:
    """Nine-phase onboarding interview (GAME_SPEC §7.1).

    Usage::

        wizard = OnboardingWizard()
        while not wizard.is_complete:
            prompt = wizard.current_prompt()
            answers = collect_answers(prompt)   # caller's I/O
            result = wizard.step(answers)
            if result.errors:
                show_errors(result.errors)
    """

    def __init__(self) -> None:
        self._phase: OnboardingPhase = OnboardingPhase.WELCOME
        self._draft: _DraftState = _DraftState()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def current_prompt(self) -> PhasePrompt:
        """Return the prompt for the current phase.

        Raises RuntimeError if the wizard is already complete.
        """
        if self._phase == OnboardingPhase.DONE:
            raise RuntimeError("wizard complete")
        return _PHASE_INDEX[self._phase]

    def step(self, answers: dict[str, object]) -> StepResult:
        """Process *answers* for the current phase and advance if valid.

        If validation fails the wizard stays on the same phase and returns
        a StepResult with non-empty *errors*.
        """
        if self._phase == OnboardingPhase.DONE:
            raise RuntimeError("wizard complete")

        prompt = _PHASE_INDEX[self._phase]

        # Special handling: REVIEW confirmation gate
        if self._phase == OnboardingPhase.REVIEW:
            return self._handle_review_step(answers)

        # Parse every declared field
        all_errors: list[str] = []
        parsed: dict[str, object] = {}

        for fld in prompt.fields:
            raw = answers.get(fld.id)
            value, errors = parse_answer(fld, raw)
            if errors:
                all_errors.extend(errors)
            else:
                parsed[fld.id] = value

        if all_errors:
            return StepResult(
                next_prompt=prompt,
                errors=all_errors,
                phase=self._phase,
            )

        # Write parsed values into draft
        for field_id, value in parsed.items():
            draft_attr = _DRAFT_FIELD_MAP.get(field_id, field_id)
            setattr(self._draft, draft_attr, value)

        # Advance phase
        self._phase = _next_phase(self._phase)

        if self._phase == OnboardingPhase.DONE:
            return StepResult(next_prompt=None, errors=[], phase=OnboardingPhase.DONE)

        return StepResult(
            next_prompt=_PHASE_INDEX[self._phase],
            errors=[],
            phase=self._phase,
        )

    def review(self) -> dict[str, object]:
        """Return the current draft as a read-only nested dict.

        Raises RuntimeError if any required draft field is still None.
        """
        _require_complete_draft(self._draft)

        profile, content_policy, house_rules = self.build_records()
        return {
            "profile": profile.model_dump(),
            "content_policy": content_policy.model_dump(),
            "house_rules": house_rules.model_dump(),
        }

    def edit(self, field_path: str, value: object) -> list[str]:
        """Edit a draft field identified by dotted *field_path*.

        Valid paths: ``profile.pacing``, ``content_policy.hard_limits``,
        ``house_rules.dice_ux``, ``profile.budget.per_session_usd``, etc.

        Returns a list of validation error strings (empty on success).
        The draft is NOT modified if errors are returned.
        """
        # MVP: combat_style is fixed
        if "combat_style" in field_path:
            return ["combat_style is fixed to 'theater_of_mind' in MVP"]

        # Map field_path to draft attribute(s)
        errors = self._apply_edit(field_path, value)
        return errors

    def build_records(self) -> tuple[PlayerProfile, ContentPolicy, HouseRules]:
        """Construct and validate the three Pydantic models from accumulated draft state.

        Raises RuntimeError if called before all phases are complete.
        Raises pydantic.ValidationError if a model constraint is violated.
        """
        d = self._draft

        # Validate required fields are present
        _require_complete_draft(d)

        budget = BudgetPolicy(
            per_session_usd=d.per_session_usd,  # type: ignore[arg-type]
            hard_stop=d.hard_stop,  # type: ignore[arg-type]
        )

        profile = PlayerProfile(
            genre=d.genre,  # type: ignore[arg-type]
            tone=d.tone,  # type: ignore[arg-type]
            touchstones=d.touchstones,  # type: ignore[arg-type]
            pillar_weights=d.pillar_weights,  # type: ignore[arg-type]
            pacing=d.pacing,  # type: ignore[arg-type]
            combat_style=d.combat_style,  # type: ignore[arg-type]
            dice_ux=d.dice_ux,  # type: ignore[arg-type]
            campaign_length=d.campaign_length,  # type: ignore[arg-type]
            character_mode=d.character_mode,  # type: ignore[arg-type]
            death_policy=d.death_policy,  # type: ignore[arg-type]
            budget=budget,
        )

        content_policy = ContentPolicy(
            hard_limits=d.hard_limits if d.hard_limits is not None else [],
            soft_limits=d.soft_limits if d.soft_limits is not None else {},  # type: ignore[arg-type]
            preferences=d.preferences if d.preferences is not None else [],
        )

        house_rules = HouseRules(
            dice_ux=d.dice_ux,  # type: ignore[arg-type]
            initiative_visible=True,
            allow_retcon=True,
            auto_save_every_turn=True,
            session_end_trigger="player_command_or_budget",
        )

        return profile, content_policy, house_rules

    @property
    def is_complete(self) -> bool:
        """True when the wizard has advanced through the REVIEW confirmation."""
        return self._phase == OnboardingPhase.DONE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_review_step(self, answers: dict[str, object]) -> StepResult:
        """Process the REVIEW phase: accept/reject confirmation."""
        review_prompt = _PHASE_INDEX[OnboardingPhase.REVIEW]
        confirm_field: PromptField = review_prompt.fields[0]  # review_confirmed
        raw = answers.get("review_confirmed")
        confirmed, errors = parse_answer(confirm_field, raw)

        if errors:
            return StepResult(
                next_prompt=review_prompt,
                errors=errors,
                phase=OnboardingPhase.REVIEW,
            )

        if not confirmed:
            return StepResult(
                next_prompt=review_prompt,
                errors=["review not confirmed"],
                phase=OnboardingPhase.REVIEW,
            )

        # Confirmed → advance to DONE
        self._phase = OnboardingPhase.DONE
        return StepResult(next_prompt=None, errors=[], phase=OnboardingPhase.DONE)

    def _apply_edit(self, field_path: str, value: object) -> list[str]:
        """Attempt to apply an edit to _draft; return errors on failure."""
        parts = field_path.split(".")
        if len(parts) < 2:
            return [f"invalid field_path {field_path!r}: expected 'record.field[.subfield]'"]

        record_name = parts[0]
        if record_name not in _EDIT_RECORD_KINDS:
            return [
                f"unknown record {record_name!r}: must be one of "
                f"{{{', '.join(_EDIT_RECORD_KINDS)}}}"
            ]

        # Map to draft attribute
        if record_name == "profile":
            return self._apply_profile_edit(parts[1:], value)
        if record_name == "content_policy":
            return self._apply_content_policy_edit(parts[1:], value)
        if record_name == "house_rules":
            return self._apply_house_rules_edit(parts[1:], value)

        return [f"unhandled record {record_name!r}"]

    def _apply_profile_edit(self, sub_parts: list[str], value: object) -> list[str]:
        field_name = sub_parts[0]
        d = self._draft

        # Budget sub-fields
        if field_name == "budget":
            if len(sub_parts) < 2:
                return ["expected 'profile.budget.per_session_usd' or 'profile.budget.hard_stop'"]
            sub_field = sub_parts[1]
            if sub_field == "per_session_usd":
                try:
                    float_val = float(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return [f"per_session_usd must be a non-negative float, got {value!r}"]
                if float_val < 0:
                    return [f"per_session_usd must be >= 0, got {float_val}"]
                old = d.per_session_usd
                d.per_session_usd = float_val
                errors = self._validate_profile()
                if errors:
                    d.per_session_usd = old
                return errors
            if sub_field == "hard_stop":
                from .prompts import PromptField, PromptFieldKind
                fld = PromptField(id="hard_stop", label="", kind=PromptFieldKind.BOOL)
                parsed_val, errs = parse_answer(fld, value)
                if errs:
                    return errs
                old = d.hard_stop
                d.hard_stop = parsed_val  # type: ignore[assignment]
                errors = self._validate_profile()
                if errors:
                    d.hard_stop = old
                return errors
            return [f"unknown budget sub-field {sub_field!r}"]

        # Direct profile fields
        _PROFILE_FIELD_DRAFT_MAP: dict[str, str] = {
            "genre": "genre",
            "tone": "tone",
            "touchstones": "touchstones",
            "pillar_weights": "pillar_weights",
            "pacing": "pacing",
            "dice_ux": "dice_ux",
            "campaign_length": "campaign_length",
            "character_mode": "character_mode",
            "death_policy": "death_policy",
        }
        if field_name not in _PROFILE_FIELD_DRAFT_MAP:
            return [
                f"unknown profile field {field_name!r}: valid fields are "
                f"{{{', '.join(_PROFILE_FIELD_DRAFT_MAP)}}}"
            ]
        draft_attr = _PROFILE_FIELD_DRAFT_MAP[field_name]
        old = getattr(d, draft_attr)
        setattr(d, draft_attr, value)
        errors = self._validate_profile()
        if errors:
            setattr(d, draft_attr, old)
        return errors

    def _apply_content_policy_edit(self, sub_parts: list[str], value: object) -> list[str]:
        field_name = sub_parts[0]
        d = self._draft
        valid_fields = {"hard_limits", "soft_limits", "preferences"}
        if field_name not in valid_fields:
            return [
                f"unknown content_policy field {field_name!r}: valid fields are "
                f"{{{', '.join(sorted(valid_fields))}}}"
            ]
        old = getattr(d, field_name)
        setattr(d, field_name, value)
        errors = self._validate_content_policy()
        if errors:
            setattr(d, field_name, old)
        return errors

    def _apply_house_rules_edit(self, sub_parts: list[str], value: object) -> list[str]:
        field_name = sub_parts[0]
        d = self._draft
        valid_fields = {
            "dice_ux": "dice_ux",
        }
        if field_name not in valid_fields:
            return [
                f"unknown house_rules field {field_name!r}: editable fields are "
                f"{{{', '.join(sorted(valid_fields))}}}"
            ]
        old = d.dice_ux
        d.dice_ux = value  # type: ignore[assignment]
        errors = self._validate_house_rules()
        if errors:
            d.dice_ux = old
        return errors

    def _validate_profile(self) -> list[str]:
        """Attempt to build a PlayerProfile; return validation errors."""
        d = self._draft
        if any(
            x is None
            for x in (
                d.genre, d.tone, d.touchstones, d.pillar_weights,
                d.pacing, d.combat_style, d.dice_ux, d.campaign_length,
                d.character_mode, d.death_policy, d.per_session_usd, d.hard_stop,
            )
        ):
            return ["draft incomplete — cannot validate profile"]
        try:
            PlayerProfile(
                genre=d.genre,  # type: ignore[arg-type]
                tone=d.tone,  # type: ignore[arg-type]
                touchstones=d.touchstones,  # type: ignore[arg-type]
                pillar_weights=d.pillar_weights,  # type: ignore[arg-type]
                pacing=d.pacing,  # type: ignore[arg-type]
                combat_style=d.combat_style,  # type: ignore[arg-type]
                dice_ux=d.dice_ux,  # type: ignore[arg-type]
                campaign_length=d.campaign_length,  # type: ignore[arg-type]
                character_mode=d.character_mode,  # type: ignore[arg-type]
                death_policy=d.death_policy,  # type: ignore[arg-type]
                budget=BudgetPolicy(
                    per_session_usd=d.per_session_usd,  # type: ignore[arg-type]
                    hard_stop=d.hard_stop,  # type: ignore[arg-type]
                ),
            )
            return []
        except Exception as exc:
            return [str(exc)]

    def _validate_content_policy(self) -> list[str]:
        d = self._draft
        try:
            ContentPolicy(
                hard_limits=d.hard_limits if d.hard_limits is not None else [],
                soft_limits=d.soft_limits if d.soft_limits is not None else {},  # type: ignore[arg-type]
                preferences=d.preferences if d.preferences is not None else [],
            )
            return []
        except Exception as exc:
            return [str(exc)]

    def _validate_house_rules(self) -> list[str]:
        d = self._draft
        if d.dice_ux is None:
            return ["draft incomplete — cannot validate house_rules"]
        try:
            HouseRules(
                dice_ux=d.dice_ux,  # type: ignore[arg-type]
                initiative_visible=True,
                allow_retcon=True,
                auto_save_every_turn=True,
                session_end_trigger="player_command_or_budget",
            )
            return []
        except Exception as exc:
            return [str(exc)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_phase(current: OnboardingPhase) -> OnboardingPhase:
    """Return the phase after *current* in PHASE_ORDER."""
    idx = PHASE_ORDER.index(current)
    return PHASE_ORDER[idx + 1]


def _require_complete_draft(draft: _DraftState) -> None:
    """Raise RuntimeError if any required draft field is None."""
    required_fields = [
        "genre", "tone", "touchstones", "pillar_weights", "pacing",
        "combat_style", "dice_ux", "campaign_length", "death_policy",
        "per_session_usd", "hard_stop", "character_mode",
    ]
    missing = [f for f in required_fields if getattr(draft, f) is None]
    if missing:
        raise RuntimeError(
            f"review called before all phases filled; missing: {missing}"
        )
