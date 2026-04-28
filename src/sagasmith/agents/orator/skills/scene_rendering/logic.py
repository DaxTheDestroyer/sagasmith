"""Scene rendering logic — buffered stream-after-classify pipeline (D-06.1).

This module implements the core Orator scene rendering pipeline:
1. Build prompt with CheckResult constraint tokens
2. Budget preflight (D-06.6)
3. Stream LLM tokens into a private buffer
4. Run inline hard-limit matcher on each accumulated window
5. Run post-gate classifier on completed buffer
6. Run mechanical-consistency audit (D-06.2)
7. Playback validated tokens to pending_narration
8. Two-rewrite ladder; fallback on exhaustion
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sagasmith.agents.orator.dice_ux import DiceUxMode, prepare_dice_ux
from sagasmith.agents.orator.mechanics_consistency import (
    AuditResult,
    audit_mechanical_consistency,
)
from sagasmith.prompts.orator.scene_rendering import build_user_prompt
from sagasmith.providers.client import LLMClient
from sagasmith.schemas.mechanics import CheckResult
from sagasmith.schemas.narrative import MemoryPacket, SceneBrief
from sagasmith.schemas.player import ContentPolicy, PlayerProfile
from sagasmith.schemas.provider import (
    CompletedEvent,
    FailedEvent,
    LLMRequest,
    Message,
    TokenEvent,
)
from sagasmith.schemas.safety_cost import SafetyEvent
from sagasmith.services.cost import CostGovernor
from sagasmith.services.errors import BudgetStopError
from sagasmith.services.safety_inline_matcher import SafetyInlineMatcher
from sagasmith.services.safety_post_gate import (
    BlockFallback,
    Rewrite,
    SafetyPostGate,
)

# Constants
_FALLBACK_NARRATION = "The scene shifts. A new detail draws your attention."
_MAX_REWRITES = 2
_PLAYBACK_TOKENS_PER_SEC = 45  # middle of 30-60 range
_STREAM_CHECK_INTERVAL = 50  # check inline matcher every N chars
_SYSTEM_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class RenderResult:
    """Result of the buffered stream-after-classify pipeline."""

    narration_lines: list[str]
    resolved_beat_ids: list[str]
    safety_events: list[dict[str, Any]]
    used_fallback: bool


def render_scene(
    *,
    scene_brief: SceneBrief,
    check_results: list[CheckResult],
    memory_packet: MemoryPacket,
    content_policy: ContentPolicy | None,
    player_profile: PlayerProfile | None,
    house_rules_dice_ux: DiceUxMode | None,
    llm_client: LLMClient | None,
    narration_model: str,
    cheap_model: str,
    cost_governor: CostGovernor | None,
    provider: str = "fake",
    turn_id: str = "unknown",
    campaign_id: str = "",
    safety_svc: Any = None,
) -> RenderResult:
    """Execute the buffered stream-after-classify pipeline.

    Returns a RenderResult with validated narration lines, resolved beat IDs,
    safety events, and whether fallback was used.
    """
    dice_ux_mode = house_rules_dice_ux or player_profile.dice_ux if player_profile else "auto"
    dice_ctx = prepare_dice_ux(dice_ux_mode, check_results)

    # Build prompt
    user_prompt_text = build_user_prompt(
        scene_brief=scene_brief,
        check_results=check_results,
        memory_packet=memory_packet,
        content_policy=content_policy,
        player_profile=player_profile,
        dice_ux_instruction=dice_ctx.prompt_instruction,
        dice_ux_constraints=dice_ctx.constraint_payload,
        beat_ids=scene_brief.beat_ids,
    )

    # No LLM client — use deterministic fallback
    if llm_client is None:
        return RenderResult(
            narration_lines=[_FALLBACK_NARRATION],
            resolved_beat_ids=[],
            safety_events=[],
            used_fallback=True,
        )

    # Prepare safety services
    inline_matcher = SafetyInlineMatcher(content_policy)
    post_gate = SafetyPostGate(llm_client=llm_client, cheap_model=cheap_model)

    # Rewrite ladder: initial attempt + up to _MAX_REWRITES rewrites
    safety_events: list[dict[str, Any]] = []

    for attempt in range(_MAX_REWRITES + 1):
        # Budget preflight (D-06.6)
        if cost_governor is not None:
            try:
                cost_governor.preflight(
                    provider=provider,
                    model=narration_model,
                    prompt_tokens=len(user_prompt_text) // 4,
                    max_tokens_fallback=1024,
                ).raise_if_blocked()
            except BudgetStopError:
                return RenderResult(
                    narration_lines=[_FALLBACK_NARRATION],
                    resolved_beat_ids=[],
                    safety_events=_make_safety_events(
                        safety_events, turn_id, "fallback", "budget_stop"
                    ),
                    used_fallback=True,
                )

        # Build messages
        system_msg = Message(role="system", content=_build_system_prompt_with_rewrite_hint(attempt))
        user_msg = Message(role="user", content=user_prompt_text)
        request = LLMRequest(
            agent_name="orator.scene-rendering",
            model=narration_model,
            messages=[system_msg, user_msg],
            response_format="text",
            temperature=0.7,
            max_tokens=1024,
            timeout_seconds=_SYSTEM_TIMEOUT_SECONDS,
        )

        # Stream into buffer
        buffer: list[str] = []
        cancelled = False
        try:
            for event in llm_client.stream(request):
                if isinstance(event, TokenEvent):
                    buffer.append(event.text)
                    # Check inline hard-limit matcher periodically
                    if len(buffer) % _STREAM_CHECK_INTERVAL == 0:
                        combined = "".join(buffer)
                        hit = inline_matcher.match(combined)
                        if hit is not None:
                            cancelled = True
                            safety_events.append(
                                _make_event(
                                    turn_id, "fallback",
                                    hit.term,
                                    f"inline hard-limit match: {hit.matched_text}",
                                )
                            )
                            break
                elif isinstance(event, CompletedEvent):
                    break
                elif isinstance(event, FailedEvent):
                    # Stream failed — fall through to fallback
                    return RenderResult(
                        narration_lines=[_FALLBACK_NARRATION],
                        resolved_beat_ids=[],
                        safety_events=_make_safety_events(
                            safety_events, turn_id, "fallback", f"stream_failed:{event.failure_kind}"
                        ),
                        used_fallback=True,
                    )
        except Exception:
            return RenderResult(
                narration_lines=[_FALLBACK_NARRATION],
                resolved_beat_ids=[],
                safety_events=_make_safety_events(
                    safety_events, turn_id, "fallback", "stream_exception"
                ),
                used_fallback=True,
            )

        if cancelled:
            # Inline matcher hit — try rewrite
            continue

        narration = "".join(buffer).strip()
        if not narration:
            narration = _FALLBACK_NARRATION

        # Run post-gate classifier
        post_verdict = post_gate.scan(narration, content_policy)
        if isinstance(post_verdict, BlockFallback):
            safety_events.append(
                _make_event(
                    turn_id, "fallback",
                    post_verdict.violated_term or "unknown",
                    post_verdict.reason or "blocked",
                )
            )
            if attempt < _MAX_REWRITES:
                continue
            # Exhausted — use fallback
            _log_safety_event(safety_svc, campaign_id, turn_id, "fallback", post_verdict.reason or "blocked")
            return RenderResult(
                narration_lines=[_FALLBACK_NARRATION],
                resolved_beat_ids=[],
                safety_events=_make_safety_events(
                    safety_events, turn_id, "fallback", "post_gate_exhausted"
                ),
                used_fallback=True,
            )

        if isinstance(post_verdict, Rewrite):
            safety_events.append(
                _make_event(
                    turn_id, "post_gate_rewrite",
                    post_verdict.violated_term or "unknown",
                    post_verdict.reason or "rewrite",
                )
            )
            _log_safety_event(
                safety_svc, campaign_id, turn_id,
                "post_gate_rewrite", post_verdict.reason or "rewrite",
            )
            if attempt < _MAX_REWRITES:
                continue
            # Exhausted — use fallback
            return RenderResult(
                narration_lines=[_FALLBACK_NARRATION],
                resolved_beat_ids=[],
                safety_events=_make_safety_events(
                    safety_events, turn_id, "fallback", "rewrite_exhausted"
                ),
                used_fallback=True,
            )

        # Run mechanical-consistency audit (D-06.2)
        if check_results:
            audit: AuditResult = audit_mechanical_consistency(narration, check_results)
            if not audit.ok:
                safety_events.append(
                    _make_event(
                        turn_id, "post_gate_rewrite",
                        "mechanical_consistency",
                        f"audit violations: {'; '.join(audit.violations)}",
                    )
                )
                if attempt < _MAX_REWRITES:
                    continue
                # Exhausted — use fallback
                return RenderResult(
                    narration_lines=[_FALLBACK_NARRATION],
                    resolved_beat_ids=[],
                    safety_events=_make_safety_events(
                        safety_events, turn_id, "fallback", "mechanics_exhausted"
                    ),
                    used_fallback=True,
                )

        # All gates passed — playback validated narration
        resolved = _detect_resolved_beats(narration, scene_brief)
        return RenderResult(
            narration_lines=[narration],
            resolved_beat_ids=resolved,
            safety_events=safety_events,
            used_fallback=False,
        )

    # Should not reach here, but safety fallback
    return RenderResult(
        narration_lines=[_FALLBACK_NARRATION],
        resolved_beat_ids=[],
        safety_events=_make_safety_events(
            safety_events, turn_id, "fallback", "rewrite_loop_exhausted"
        ),
        used_fallback=True,
    )


def _build_system_prompt_with_rewrite_hint(attempt: int) -> str:
    """Build system prompt, adding rewrite context on retry attempts."""
    from sagasmith.prompts.orator.scene_rendering import SYSTEM_PROMPT

    if attempt == 0:
        return SYSTEM_PROMPT
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"REWRITE ATTEMPT {attempt}/{_MAX_REWRITES}: "
        "Your previous narration was flagged for policy or consistency issues. "
        "Please revise to avoid the flagged content while preserving the scene intent."
    )


def _detect_resolved_beats(narration: str, brief: SceneBrief) -> list[str]:
    """Heuristic: detect which beat_ids the narration likely advanced.

    Uses simple keyword matching against the beat text.
    Returns the beat_ids whose corresponding beat text has significant
    keyword overlap with the narration.
    """
    if not brief.beat_ids:
        return []

    narration_lower = narration.lower()
    resolved: list[str] = []

    for beat_text, beat_id in zip(brief.beats, brief.beat_ids, strict=False):
        # Extract significant words from beat text (> 4 chars)
        beat_words = {
            w.lower()
            for w in beat_text.split()
            if len(w) > 4 and w.isalpha()
        }
        if not beat_words:
            # If beat text has no long words, consider it resolved if narration is substantial
            if len(narration) > 100:
                resolved.append(beat_id)
            continue

        # Count how many beat words appear in narration
        matches = sum(1 for w in beat_words if w in narration_lower)
        if matches >= max(1, len(beat_words) // 3):
            resolved.append(beat_id)

    # If no beats resolved but narration is substantial, mark the first beat
    if not resolved and brief.beat_ids and len(narration) > 100:
        resolved.append(brief.beat_ids[0])

    return resolved


def _make_event(
    turn_id: str,
    kind: str,
    policy_ref: str | None,
    reason: str,
) -> dict[str, Any]:
    """Create a SafetyEvent dict."""
    return SafetyEvent(
        id=f"safety_{turn_id}_render_{kind}",
        turn_id=turn_id,
        kind=kind,  # type: ignore[arg-type]
        policy_ref=policy_ref,
        action_taken=reason[:200],
    ).model_dump()


def _make_safety_events(
    existing: list[dict[str, Any]],
    turn_id: str,
    kind: str,
    reason: str,
) -> list[dict[str, Any]]:
    """Append a safety event to the list and return it."""
    return [*existing, _make_event(turn_id, kind, None, reason)]


def _log_safety_event(
    safety_svc: Any,
    campaign_id: str,
    turn_id: str,
    event_kind: str,
    reason: str,
) -> None:
    """Log safety event to SafetyEventService if available."""
    if safety_svc is None:
        return
    try:
        if event_kind == "fallback":
            safety_svc.log_fallback(
                campaign_id=campaign_id,
                reason=reason,
                turn_id=turn_id,
            )
        elif event_kind == "post_gate_rewrite":
            safety_svc.log_post_gate_rewrite(
                campaign_id=campaign_id,
                policy_ref=None,
                reason=reason,
                turn_id=turn_id,
            )
    except Exception:
        try:  # noqa: SIM105 — matches safety_post_gate rollback pattern
            safety_svc.conn.rollback()
        except Exception:
            pass
