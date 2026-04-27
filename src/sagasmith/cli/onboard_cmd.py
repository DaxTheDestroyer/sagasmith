"""CLI command: ``sagasmith onboard`` — complete or re-run campaign onboarding."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

from sagasmith.app.campaign import open_campaign
from sagasmith.onboarding.store import OnboardingStore, OnboardingTriple
from sagasmith.onboarding.wizard import OnboardingWizard
from sagasmith.persistence.db import open_campaign_db

_Disposition = Literal["fade_to_black", "avoid_detail", "ask_first"]


def _csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _required_str(value: str | None, *, option: str, prompt: str) -> str:
    if value:
        return value
    if sys.stdin.isatty():
        return typer.prompt(prompt)
    typer.echo(f"{option} is required in non-interactive mode", err=True)
    raise typer.Exit(code=2)


def _required_int(value: int | None, *, option: str, prompt: str) -> int:
    if value is not None:
        return value
    if sys.stdin.isatty():
        return int(typer.prompt(prompt))
    typer.echo(f"{option} is required in non-interactive mode", err=True)
    raise typer.Exit(code=2)


def _parse_soft_limits(raw: str | None) -> dict[str, _Disposition]:
    """Parse comma-separated ``topic:disposition`` pairs."""
    if raw is None or not raw.strip():
        return {}

    parsed: dict[str, _Disposition] = {}
    for item in _csv(raw):
        topic, sep, disposition = item.partition(":")
        if not sep or not topic.strip() or not disposition.strip():
            typer.echo(
                "--soft-limits must use 'topic:fade_to_black|avoid_detail|ask_first'",
                err=True,
            )
            raise typer.Exit(code=2)
        if disposition not in ("fade_to_black", "avoid_detail", "ask_first"):
            typer.echo(
                "--soft-limits dispositions must be fade_to_black, avoid_detail, or ask_first",
                err=True,
            )
            raise typer.Exit(code=2)
        parsed[topic.strip()] = disposition
    return parsed


def onboard_command(
    campaign: Annotated[Path, typer.Option("--campaign", "-c", help="Campaign directory path.")],
    genre: Annotated[str | None, typer.Option("--genre", help="Comma-separated genres.")] = None,
    tone: Annotated[str | None, typer.Option("--tone", help="Comma-separated tone keywords.")] = None,
    touchstones: Annotated[
        str | None,
        typer.Option("--touchstones", help="Comma-separated books/games/films to emulate."),
    ] = None,
    pillar_combat: Annotated[int | None, typer.Option("--pillar-combat", min=0)] = None,
    pillar_exploration: Annotated[int | None, typer.Option("--pillar-exploration", min=0)] = None,
    pillar_social: Annotated[int | None, typer.Option("--pillar-social", min=0)] = None,
    pillar_puzzle: Annotated[int | None, typer.Option("--pillar-puzzle", min=0)] = None,
    pacing: Annotated[
        str | None,
        typer.Option("--pacing", help="slow | medium | fast"),
    ] = None,
    dice_ux: Annotated[
        str | None,
        typer.Option("--dice-ux", help="auto | reveal | hidden"),
    ] = None,
    hard_limits: Annotated[
        str | None,
        typer.Option("--hard-limits", help="Comma-separated hard limits."),
    ] = None,
    soft_limits: Annotated[
        str | None,
        typer.Option("--soft-limits", help="Comma-separated topic:disposition pairs."),
    ] = None,
    preferences: Annotated[
        str | None,
        typer.Option("--preferences", help="Comma-separated content preferences."),
    ] = None,
    campaign_length: Annotated[
        str | None,
        typer.Option("--campaign-length", help="one_shot | arc | open_ended"),
    ] = None,
    death_policy: Annotated[
        str | None,
        typer.Option("--death-policy", help="hardcore | heroic_recovery | retire_and_continue"),
    ] = None,
    per_session_usd: Annotated[
        float | None,
        typer.Option("--per-session-usd", min=0, help="Per-session LLM budget in USD."),
    ] = None,
    hard_stop: Annotated[
        bool,
        typer.Option("--hard-stop/--no-hard-stop", help="Stop before budget would be exceeded."),
    ] = True,
    character_mode: Annotated[
        str | None,
        typer.Option("--character-mode", help="guided | player_led | pregenerated"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Commit the reviewed onboarding records without prompting."),
    ] = False,
) -> None:
    """Complete or re-run onboarding for a local campaign."""
    try:
        paths, manifest = open_campaign(campaign)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from None

    answers: list[dict[str, object]] = [
        {"genre": _csv(_required_str(genre, option="--genre", prompt="Genres"))},
        {
            "tone": _csv(_required_str(tone, option="--tone", prompt="Tone keywords")),
            "touchstones": _csv(
                _required_str(touchstones, option="--touchstones", prompt="Touchstones")
            ),
        },
        {
            "pillar_budget": {
                "combat": _required_int(
                    pillar_combat, option="--pillar-combat", prompt="Combat pillar points"
                ),
                "exploration": _required_int(
                    pillar_exploration,
                    option="--pillar-exploration",
                    prompt="Exploration pillar points",
                ),
                "social": _required_int(
                    pillar_social, option="--pillar-social", prompt="Social pillar points"
                ),
                "puzzle": _required_int(
                    pillar_puzzle, option="--pillar-puzzle", prompt="Puzzle pillar points"
                ),
            },
            "pacing": _required_str(pacing, option="--pacing", prompt="Pacing"),
        },
        {
            "combat_style": "theater_of_mind",
            "dice_ux": _required_str(dice_ux, option="--dice-ux", prompt="Dice UX"),
        },
        {
            "hard_limits": _csv(hard_limits),
            "soft_limits": _parse_soft_limits(soft_limits),
            "preferences": _csv(preferences),
        },
        {
            "campaign_length": _required_str(
                campaign_length, option="--campaign-length", prompt="Campaign length"
            ),
            "death_policy": _required_str(
                death_policy, option="--death-policy", prompt="Death policy"
            ),
        },
        {
            "per_session_usd": per_session_usd
            if per_session_usd is not None
            else float(_required_str(None, option="--per-session-usd", prompt="Per-session USD")),
            "hard_stop": hard_stop,
        },
        {
            "character_mode": _required_str(
                character_mode, option="--character-mode", prompt="Character mode"
            ),
        },
    ]

    wizard = OnboardingWizard()
    for answer in answers:
        result = wizard.step(answer)
        if result.errors:
            for error in result.errors:
                typer.echo(f"error: {error}", err=True)
            raise typer.Exit(code=2)

    review = wizard.review()
    typer.echo("Onboarding review:")
    typer.echo(json.dumps(review, indent=2, sort_keys=True))

    if not yes:
        if not sys.stdin.isatty():
            typer.echo("--yes is required to commit onboarding in non-interactive mode", err=True)
            raise typer.Exit(code=2)
        if not typer.confirm("Commit onboarding records?", default=True):
            typer.echo("Onboarding not committed.")
            raise typer.Exit(code=1)

    result = wizard.step({"review_confirmed": True})
    if result.errors:
        for error in result.errors:
            typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=2)

    profile, policy, rules = wizard.build_records()
    conn = open_campaign_db(paths.db)
    try:
        OnboardingStore(conn).commit(
            manifest.campaign_id,
            OnboardingTriple(
                player_profile=profile,
                content_policy=policy,
                house_rules=rules,
            ),
        )
    finally:
        conn.close()

    typer.echo(f"Onboarding committed for campaign '{manifest.campaign_name}'")
