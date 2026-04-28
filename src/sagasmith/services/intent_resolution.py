"""Hybrid player-intent resolution for RulesLawyer proposals."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import Field

from sagasmith.prompts.rules_lawyer import intent_resolution as prompt
from sagasmith.providers import LLMClient, invoke_with_retry
from sagasmith.schemas.common import SchemaModel, estimate_tokens
from sagasmith.schemas.provider import LLMRequest, Message, ProviderLogRecord
from sagasmith.services.cost import CostGovernor
from sagasmith.services.errors import BudgetStopError

IntentAction = Literal["skill_check", "start_combat", "strike", "move", "end_turn", "none"]
IntentSource = Literal["deterministic", "llm", "budget_fallback"]

SUPPORTED_STATS = frozenset({"athletics", "acrobatics", "survival", "intimidation", "perception"})
SUPPORTED_TARGETS = frozenset({"enemy_weak_melee", "enemy_weak_ranged"})
SUPPORTED_ATTACKS = frozenset({"longsword", "shortbow"})
SUPPORTED_POSITIONS = frozenset({"close", "near", "far", "behind_cover"})
DEFAULT_INTENT_DC = 15
DEFAULT_INTENT_MODEL = "fake-default"
DEFAULT_CHEAP_MODEL = "fake-cheap"
INTENT_MAX_TOKENS = 500

_STAT_PATTERN = r"(athletics|acrobatics|survival|intimidation|perception)"
_ROLL_CHECK_RE = re.compile(rf"^(?:roll|check)\s+{_STAT_PATTERN}\s+dc\s+(\d+)$")
_PERCEPTION_RE = re.compile(r"^perception\s+dc\s+(\d+)$")
_START_COMBAT_RE = re.compile(r"^start\s+combat$")
_STRIKE_RE = re.compile(r"^strike\s+(enemy_weak_melee|enemy_weak_ranged)\s+with\s+(longsword|shortbow)$")
_MOVE_RE = re.compile(r"^move\s+(close|near|far|behind_cover)$")
_END_TURN_RE = re.compile(r"^end\s+turn$")

_NATURAL_SKILL_PATTERNS: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"\b(climb|force|swim|grapple|shove|athletic)\b"), "athletics", 0.74),
    (re.compile(r"\b(balance|tumble|sneak|acrobat)\b"), "acrobatics", 0.72),
    (re.compile(r"\b(track|forage|survive|trail)\b"), "survival", 0.72),
    (re.compile(r"\b(intimidate|threaten|coerce|frighten)\b"), "intimidation", 0.72),
    (re.compile(r"\b(search|look|listen|notice|spot|perceive)\b"), "perception", 0.70),
)


class IntentCandidate(SchemaModel):
    """Ranked mechanical intent candidate produced before deterministic resolution."""

    action: IntentAction
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    source: IntentSource
    stat: str | None = None
    dc: int | None = Field(default=None, ge=1)
    target_id: str | None = None
    attack_id: str | None = None
    position: str | None = None


def resolve_intents(
    player_input: str,
    *,
    scene_context: dict[str, Any] | None = None,
    llm_client: LLMClient | None = None,
    cost_governor: CostGovernor | None = None,
    model: str = DEFAULT_INTENT_MODEL,
    cheap_model: str = DEFAULT_CHEAP_MODEL,
    turn_id: str | None = None,
    logger: Callable[[ProviderLogRecord], None] | None = None,
) -> list[IntentCandidate]:
    """Resolve player text into ranked intent candidates.

    Deterministic patterns run first. The optional LLM fallback may classify action
    shape only; returned math is ignored and proposals are rebuilt by deterministic
    services later. Budget exhaustion returns a deterministic-only hint candidate.
    """

    normalized = _normalize(player_input)
    deterministic = _deterministic_candidates(normalized, scene_context or {})
    if deterministic:
        return deterministic
    if llm_client is None:
        return []
    try:
        return _llm_candidates(
            player_input,
            scene_context=scene_context or {},
            llm_client=llm_client,
            cost_governor=cost_governor,
            model=model,
            cheap_model=cheap_model,
            turn_id=turn_id,
            logger=logger,
        )
    except BudgetStopError:
        return [
            IntentCandidate(
                action="none",
                confidence=1.0,
                reason="budget exhausted; use explicit `/check athletics 15` syntax",
                source="budget_fallback",
            )
        ]
    except Exception:
        return []


def deterministic_intents(
    player_input: str, *, scene_context: dict[str, Any] | None = None
) -> list[IntentCandidate]:
    """Expose deterministic routing for tests and budget-fallback paths."""

    return _deterministic_candidates(_normalize(player_input), scene_context or {})


def _deterministic_candidates(normalized: str, scene_context: dict[str, Any]) -> list[IntentCandidate]:
    if match := _ROLL_CHECK_RE.match(normalized):
        stat = match.group(1)
        return [_skill(stat=stat, dc=int(match.group(2)), confidence=0.99, reason="explicit check syntax")]
    if match := _PERCEPTION_RE.match(normalized):
        return [_skill(stat="perception", dc=int(match.group(1)), confidence=0.98, reason="explicit perception DC")]
    if _START_COMBAT_RE.match(normalized):
        return [IntentCandidate(action="start_combat", confidence=0.99, reason="explicit combat start", source="deterministic")]
    if match := _STRIKE_RE.match(normalized):
        return [
            IntentCandidate(
                action="strike",
                confidence=0.99,
                reason="explicit strike syntax",
                source="deterministic",
                target_id=match.group(1),
                attack_id=match.group(2),
            )
        ]
    if match := _MOVE_RE.match(normalized):
        return [IntentCandidate(action="move", confidence=0.99, reason="explicit movement", source="deterministic", position=match.group(1))]
    if _END_TURN_RE.match(normalized):
        return [IntentCandidate(action="end_turn", confidence=0.99, reason="explicit end turn", source="deterministic")]
    explicit_dc = _extract_dc(normalized)
    for pattern, stat, confidence in _NATURAL_SKILL_PATTERNS:
        if pattern.search(normalized):
            return [
                _skill(
                    stat=stat,
                    dc=explicit_dc or _context_dc(scene_context, stat),
                    confidence=confidence,
                    reason=f"natural-language {stat} cue",
                )
            ]
    return []


def _llm_candidates(
    player_input: str,
    *,
    scene_context: dict[str, Any],
    llm_client: LLMClient,
    cost_governor: CostGovernor | None,
    model: str,
    cheap_model: str,
    turn_id: str | None,
    logger: Callable[[ProviderLogRecord], None] | None,
) -> list[IntentCandidate]:
    user_prompt = prompt.build_user_prompt(player_input, scene_context)
    request = LLMRequest(
        agent_name="rules_lawyer.intent-resolution",
        model=model,
        messages=[Message(role="system", content=prompt.SYSTEM_PROMPT), Message(role="user", content=user_prompt)],
        response_format="json_schema",
        json_schema=prompt.JSON_SCHEMA,
        temperature=0.0,
        max_tokens=INTENT_MAX_TOKENS,
        timeout_seconds=30,
        metadata={"prompt_version": prompt.PROMPT_VERSION, "skill": "intent-resolution"},
    )
    if cost_governor is not None:
        prompt_tokens = sum(estimate_tokens(message.content) for message in request.messages)
        cost_governor.preflight(
            provider=_client_provider(llm_client),
            model=model,
            prompt_tokens=prompt_tokens,
            max_tokens_fallback=INTENT_MAX_TOKENS,
        ).raise_if_blocked()
    response = invoke_with_retry(
        llm_client,
        request,
        cheap_model=cheap_model,
        agent_name="rules_lawyer",
        turn_id=turn_id,
        logger=logger or _noop_logger,
    )
    if cost_governor is not None:
        cost_governor.record_usage(provider=_client_provider(llm_client), model=model, usage=response.usage)
    parsed = response.parsed_json if isinstance(response.parsed_json, dict) else {}
    raw_candidates = parsed.get("candidates", [])
    candidates = [_sanitize_llm_candidate(item, scene_context) for item in raw_candidates if isinstance(item, dict)]
    return sorted((candidate for candidate in candidates if candidate is not None), key=lambda c: c.confidence, reverse=True)


def _sanitize_llm_candidate(item: dict[str, Any], scene_context: dict[str, Any]) -> IntentCandidate | None:
    action = item.get("action")
    confidence = item.get("confidence")
    if not isinstance(action, str) or not isinstance(confidence, (int, float)):
        return None
    reason = item.get("reason") if isinstance(item.get("reason"), str) else "llm-classified intent"
    if action == "skill_check":
        stat = item.get("stat")
        if stat not in SUPPORTED_STATS:
            return None
        return IntentCandidate(
            action="skill_check",
            confidence=float(confidence),
            reason=reason,
            source="llm",
            stat=stat,
            dc=_context_dc(scene_context, stat),
        )
    if action == "strike":
        target_id = item.get("target_id")
        attack_id = item.get("attack_id")
        if target_id not in SUPPORTED_TARGETS or attack_id not in SUPPORTED_ATTACKS:
            return None
        return IntentCandidate(action="strike", confidence=float(confidence), reason=reason, source="llm", target_id=target_id, attack_id=attack_id)
    if action == "move":
        position = item.get("position")
        if position not in SUPPORTED_POSITIONS:
            return None
        return IntentCandidate(action="move", confidence=float(confidence), reason=reason, source="llm", position=position)
    if action in {"start_combat", "end_turn", "none"}:
        return IntentCandidate(action=action, confidence=float(confidence), reason=reason, source="llm")
    return None


def _skill(*, stat: str, dc: int, confidence: float, reason: str) -> IntentCandidate:
    return IntentCandidate(action="skill_check", confidence=confidence, reason=reason, source="deterministic", stat=stat, dc=dc)


def _context_dc(scene_context: dict[str, Any], stat: str) -> int:
    dcs = scene_context.get("skill_dcs")
    if isinstance(dcs, dict) and isinstance(dcs.get(stat), int):
        return int(dcs[stat])
    if isinstance(scene_context.get("default_dc"), int):
        return int(scene_context["default_dc"])
    return DEFAULT_INTENT_DC


def _extract_dc(normalized: str) -> int | None:
    match = re.search(r"\bdc\s+(\d+)\b", normalized)
    return int(match.group(1)) if match else None


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _client_provider(client: LLMClient) -> str:
    provider = getattr(client, "provider", "fake")
    return provider if isinstance(provider, str) else "fake"


def _noop_logger(_record: ProviderLogRecord) -> None:
    return None
