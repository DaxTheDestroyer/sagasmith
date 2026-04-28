"""Scene brief composition skill logic for the Oracle agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sagasmith.app.config import DEFAULT_SCENE_BRIEF_MAX_USD
from sagasmith.prompts.oracle import scene_brief_composition as prompt
from sagasmith.providers import LLMClient, invoke_with_retry
from sagasmith.schemas.campaign_seed import CampaignSeed
from sagasmith.schemas.common import estimate_tokens
from sagasmith.schemas.narrative import MemoryPacket, SceneBrief
from sagasmith.schemas.player import ContentPolicy, PlayerProfile
from sagasmith.schemas.provider import LLMRequest, Message, ProviderLogRecord
from sagasmith.schemas.world import WorldBible
from sagasmith.services.cost import CostGovernor

DEFAULT_SCENE_BRIEF_MODEL = "fake-default"
DEFAULT_CHEAP_MODEL = "fake-cheap"
SCENE_BRIEF_MAX_TOKENS = 1200


def compose_scene_brief(
    *,
    player_input: str | None,
    memory_packet: MemoryPacket | dict[str, Any],
    content_policy: ContentPolicy | dict[str, Any],
    player_profile: PlayerProfile | dict[str, Any] | None,
    llm_client: LLMClient,
    scene_intent: str,
    world_bible: WorldBible | dict[str, Any] | None = None,
    campaign_seed: CampaignSeed | dict[str, Any] | None = None,
    prior_scene_brief: SceneBrief | dict[str, Any] | None = None,
    model: str = DEFAULT_SCENE_BRIEF_MODEL,
    cheap_model: str = DEFAULT_CHEAP_MODEL,
    turn_id: str | None = None,
    logger: Callable[[ProviderLogRecord], None] | None = None,
    cost_governor: CostGovernor | None = None,
    scene_brief_max_usd: float = DEFAULT_SCENE_BRIEF_MAX_USD,
) -> SceneBrief:
    """Generate and validate a planning-only SceneBrief with structured JSON output."""

    memory = MemoryPacket.model_validate(memory_packet)
    policy = ContentPolicy.model_validate(content_policy)
    profile = PlayerProfile.model_validate(player_profile) if player_profile is not None else None
    bible = WorldBible.model_validate(world_bible) if world_bible is not None else None
    seed = CampaignSeed.model_validate(campaign_seed) if campaign_seed is not None else None
    prior = SceneBrief.model_validate(prior_scene_brief) if prior_scene_brief is not None else None
    user_prompt = prompt.build_user_prompt(
        player_input=player_input,
        memory_packet=memory,
        content_policy=policy,
        player_profile=profile,
        world_bible=bible,
        campaign_seed=seed,
        prior_scene_brief=prior,
        scene_intent=scene_intent,
    )
    request = LLMRequest(
        agent_name="oracle.scene-brief-composition",
        model=model,
        messages=[
            Message(role="system", content=prompt.SYSTEM_PROMPT),
            Message(role="user", content=user_prompt),
        ],
        response_format="json_schema",
        json_schema=prompt.JSON_SCHEMA,
        temperature=0.6,
        max_tokens=SCENE_BRIEF_MAX_TOKENS,
        timeout_seconds=90,
        metadata={"prompt_version": prompt.PROMPT_VERSION, "skill": "scene-brief-composition"},
    )
    _preflight_budget(
        client=llm_client,
        request=request,
        cost_governor=cost_governor,
        max_tokens=SCENE_BRIEF_MAX_TOKENS,
        scene_brief_max_usd=scene_brief_max_usd,
    )
    response = invoke_with_retry(
        llm_client,
        request,
        cheap_model=cheap_model,
        agent_name="oracle",
        turn_id=turn_id,
        logger=logger or _noop_logger,
    )
    if cost_governor is not None:
        cost_governor.record_usage(
            provider=_client_provider(llm_client), model=request.model, usage=response.usage
        )
    return SceneBrief.model_validate(response.parsed_json)


def _preflight_budget(
    *,
    client: LLMClient,
    request: LLMRequest,
    cost_governor: CostGovernor | None,
    max_tokens: int,
    scene_brief_max_usd: float,
) -> None:
    prompt_tokens = sum(estimate_tokens(message.content) for message in request.messages)
    provider = _client_provider(client)
    if cost_governor is not None:
        cost_governor.preflight(
            provider=provider,
            model=request.model,
            prompt_tokens=prompt_tokens,
            max_tokens_fallback=max_tokens,
        ).raise_if_blocked()
    CostGovernor(session_budget_usd=scene_brief_max_usd).preflight(
        provider=provider,
        model=request.model,
        prompt_tokens=prompt_tokens,
        max_tokens_fallback=max_tokens,
    ).raise_if_blocked()


def _client_provider(client: LLMClient) -> str:
    provider = getattr(client, "provider", "fake")
    return provider if isinstance(provider, str) else "fake"


def _noop_logger(_record: ProviderLogRecord) -> None:
    return None
