"""Campaign seed generation skill logic for the Oracle agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sagasmith.app.config import DEFAULT_WORLDGEN_MAX_USD
from sagasmith.prompts.oracle import campaign_seed_generation as prompt
from sagasmith.providers import LLMClient, invoke_with_retry
from sagasmith.schemas.campaign_seed import CampaignSeed
from sagasmith.schemas.common import estimate_tokens
from sagasmith.schemas.player import PlayerProfile
from sagasmith.schemas.provider import LLMRequest, Message, ProviderLogRecord
from sagasmith.schemas.world import WorldBible
from sagasmith.services.cost import CostGovernor

DEFAULT_CAMPAIGN_SEED_MODEL = "fake-default"
DEFAULT_CHEAP_MODEL = "fake-cheap"
CAMPAIGN_SEED_MAX_TOKENS = 1400


def generate_campaign_seed(
    *,
    world_bible: WorldBible | dict[str, Any],
    player_profile: PlayerProfile | dict[str, Any],
    llm_client: LLMClient,
    model: str = DEFAULT_CAMPAIGN_SEED_MODEL,
    cheap_model: str = DEFAULT_CHEAP_MODEL,
    turn_id: str | None = None,
    logger: Callable[[ProviderLogRecord], None] | None = None,
    cost_governor: CostGovernor | None = None,
    worldgen_max_usd: float = DEFAULT_WORLDGEN_MAX_USD,
) -> CampaignSeed:
    """Generate and validate the initial `CampaignSeed` with structured JSON output."""

    bible = WorldBible.model_validate(world_bible)
    profile = PlayerProfile.model_validate(player_profile)
    user_prompt = prompt.build_user_prompt(bible, profile)
    request = LLMRequest(
        agent_name="oracle.campaign-seed-generation",
        model=model,
        messages=[
            Message(role="system", content=prompt.SYSTEM_PROMPT),
            Message(role="user", content=user_prompt),
        ],
        response_format="json_schema",
        json_schema=prompt.JSON_SCHEMA,
        temperature=0.7,
        max_tokens=CAMPAIGN_SEED_MAX_TOKENS,
        timeout_seconds=90,
        metadata={"prompt_version": prompt.PROMPT_VERSION, "skill": "campaign-seed-generation"},
    )
    _preflight_budget(
        client=llm_client,
        request=request,
        cost_governor=cost_governor,
        max_tokens=CAMPAIGN_SEED_MAX_TOKENS,
        worldgen_max_usd=worldgen_max_usd,
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
    return CampaignSeed.model_validate(response.parsed_json)


def _preflight_budget(
    *,
    client: LLMClient,
    request: LLMRequest,
    cost_governor: CostGovernor | None,
    max_tokens: int,
    worldgen_max_usd: float,
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
    CostGovernor(session_budget_usd=worldgen_max_usd).preflight(
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
