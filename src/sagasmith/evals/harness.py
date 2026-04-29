"""In-process no-paid-call smoke harness."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pydantic

from sagasmith.evals.fixtures import (
    make_fake_llm_response,
    make_valid_character_sheet,
    make_valid_saga_state,
)
from sagasmith.evals.redaction import RedactionCanary
from sagasmith.evals.schema_round_trip import assert_round_trip
from sagasmith.providers import DeterministicFakeClient, invoke_with_retry
from sagasmith.schemas import LLMRequest, Message
from sagasmith.schemas.export import LLM_BOUNDARY_AND_PERSISTED_MODELS, export_all_schemas
from sagasmith.schemas.provider import TokenUsage
from sagasmith.schemas.validation import PersistedStateError, validate_persisted_state
from sagasmith.services.cost import CostGovernor

_MVP_CHECK_NAMES = [
    "mvp.install_entrypoint",
    "mvp.init",
    "mvp.configure_fake",
    "mvp.onboard",
    "mvp.play_skill_challenge",
    "mvp.play_simple_combat",
    "mvp.quit",
    "mvp.resume",
]


@dataclass(frozen=True)
class SmokeCheck:
    """Single smoke-check result line."""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeResult:
    """Collection of smoke checks with stable terminal formatting."""

    checks: list[SmokeCheck] = field(default_factory=list[SmokeCheck])

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def format(self) -> str:
        lines = [
            f"{'OK ' if check.ok else 'FAIL'} {check.name}"
            + (f" — {check.detail}" if check.detail else "")
            for check in self.checks
        ]
        lines.append("")
        lines.append(f"{sum(check.ok for check in self.checks)}/{len(self.checks)} checks passed")
        return "\n".join(lines)


@dataclass
class _MvpSmokeContext:
    root: Path | None = None
    campaign_id: str | None = None
    db_path: Path | None = None
    skill_roll_id: str | None = None
    combat_attack_roll_id: str | None = None


def _safe_smoke_detail(exc: BaseException) -> str:
    detail = str(exc)[:200]
    for token in ("api_key", "authorization", "bearer", "openrouter"):
        detail = detail.replace(token, "[redacted]")
        detail = detail.replace(token.upper(), "[redacted]")
    hits = RedactionCanary().scan(detail)
    if hits:
        return f"redacted secret-shaped detail: {hits[0].label}"
    return detail


def run_mvp_smoke() -> SmokeResult:
    """Run the full MVP smoke path without network calls or provider credentials."""

    result = SmokeResult()
    context = _MvpSmokeContext()
    steps: list[tuple[str, Callable[[_MvpSmokeContext], str]]] = [
        ("mvp.install_entrypoint", _mvp_install_entrypoint),
        ("mvp.init", _mvp_init),
        ("mvp.configure_fake", _mvp_configure_fake),
        ("mvp.onboard", _mvp_onboard),
        ("mvp.play_skill_challenge", _mvp_play_skill_challenge),
        ("mvp.play_simple_combat", _mvp_play_simple_combat),
        ("mvp.quit", _mvp_quit),
        ("mvp.resume", _mvp_resume),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        context.root = Path(tmp) / "mvp-smoke-campaign"
        for name, step in steps:
            try:
                detail = step(context)
                result.checks.append(SmokeCheck(name, True, detail))
            except Exception as exc:
                result.checks.append(SmokeCheck(name, False, _safe_smoke_detail(exc)))
                break

    return result


def _require_context_value[T](value: T | None, label: str) -> T:
    if value is None:
        raise RuntimeError(f"missing smoke context: {label}")
    return value


def _mvp_install_entrypoint(_context: _MvpSmokeContext) -> str:
    import sagasmith
    from sagasmith.cli.main import app

    if not sagasmith.__version__:
        raise RuntimeError("sagasmith.__version__ is empty")
    command_names = {command.name for command in app.registered_commands}
    if "smoke" not in command_names:
        raise RuntimeError("Typer app import did not expose smoke command")
    return f"version={sagasmith.__version__} cli=typer"


def _mvp_init(context: _MvpSmokeContext) -> str:
    from sagasmith.app.campaign import init_campaign, open_campaign

    root = _require_context_value(context.root, "root")
    manifest = init_campaign(name="MVP Smoke", root=root, provider="fake")
    paths, reopened = open_campaign(root)
    if reopened.campaign_id != manifest.campaign_id:
        raise RuntimeError("campaign manifest did not reopen with the same ID")
    context.campaign_id = manifest.campaign_id
    context.db_path = paths.db
    return "campaign storage created"


def _mvp_configure_fake(context: _MvpSmokeContext) -> str:
    from sagasmith.app.config import SettingsRepository
    from sagasmith.persistence.db import open_campaign_db
    from sagasmith.schemas.campaign import ProviderSettings

    campaign_id = _require_context_value(context.campaign_id, "campaign_id")
    db_path = _require_context_value(context.db_path, "db_path")
    conn = open_campaign_db(db_path)
    try:
        settings = ProviderSettings(
            provider="fake",
            api_key_ref=None,
            default_model="fake/mvp-default",
            narration_model="fake/mvp-narration",
            cheap_model="fake/mvp-cheap",
        )
        repo = SettingsRepository(conn)
        with conn:
            repo.put_provider_settings(campaign_id, settings)
        reloaded = repo.get_provider_settings(campaign_id)
    finally:
        conn.close()
    if reloaded is None or reloaded.provider != "fake" or reloaded.api_key_ref is not None:
        raise RuntimeError("fake provider settings did not persist without credentials")
    return "provider=fake"


def _mvp_onboard(context: _MvpSmokeContext) -> str:
    from sagasmith.evals.fixtures import (
        make_valid_content_policy,
        make_valid_house_rules,
        make_valid_player_profile,
    )
    from sagasmith.onboarding.store import OnboardingStore, OnboardingTriple
    from sagasmith.persistence.db import open_campaign_db

    campaign_id = _require_context_value(context.campaign_id, "campaign_id")
    db_path = _require_context_value(context.db_path, "db_path")
    conn = open_campaign_db(db_path)
    try:
        store = OnboardingStore(conn)
        store.commit(
            campaign_id,
            OnboardingTriple(
                player_profile=make_valid_player_profile(),
                content_policy=make_valid_content_policy(),
                house_rules=make_valid_house_rules(),
            ),
        )
        if not store.exists(campaign_id):
            raise RuntimeError("onboarding triple not committed")
    finally:
        conn.close()
    return "onboarding triple committed"


def _mvp_play_skill_challenge(context: _MvpSmokeContext) -> str:
    from sagasmith.rules.first_slice import make_first_slice_character
    from sagasmith.services.dice import DiceService
    from sagasmith.services.rules_engine import RulesEngine

    campaign_id = _require_context_value(context.campaign_id, "campaign_id")
    sheet = make_first_slice_character()
    dice = DiceService(campaign_seed=campaign_id, session_seed="mvp_smoke")
    check = RulesEngine(dice=dice).resolve_check(
        sheet,
        stat="athletics",
        dc=15,
        reason="mvp smoke skill challenge",
        roll_index=0,
    )
    context.skill_roll_id = check.roll_result.roll_id
    return f"roll={check.roll_result.roll_id} degree={check.degree}"


def _mvp_play_simple_combat(context: _MvpSmokeContext) -> str:
    from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
    from sagasmith.services.combat_engine import CombatEngine
    from sagasmith.services.dice import DiceService
    from sagasmith.services.rules_engine import RulesEngine

    campaign_id = _require_context_value(context.campaign_id, "campaign_id")
    sheet = make_first_slice_character()
    dice = DiceService(campaign_seed=campaign_id, session_seed="mvp_smoke")
    rules = RulesEngine(dice=dice)
    combat = CombatEngine(dice=dice, rules=rules)
    combat_state, initiative = combat.start_encounter(
        sheet, make_first_slice_enemies(), roll_index=1
    )
    while combat_state.active_combatant_id != sheet.id:
        combat_state = combat.end_turn(combat_state)
    combat_state, attack, damage = combat.resolve_strike(
        combat_state,
        sheet.id,
        "enemy_weak_melee",
        "longsword",
        roll_index=1 + len(initiative),
    )
    context.combat_attack_roll_id = attack.roll_result.roll_id
    if not combat_state.initiative_order or combat_state.action_counts[sheet.id] != 2:
        raise RuntimeError("simple combat state did not advance after Strike")
    damage_detail = f" damage={damage.roll_id}" if damage is not None else ""
    return f"attack={attack.roll_result.roll_id}{damage_detail}"


def _mvp_quit(context: _MvpSmokeContext) -> str:
    from sagasmith.persistence.db import open_campaign_db
    from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
    from sagasmith.schemas.persistence import CheckpointRef, TranscriptEntry, TurnRecord

    campaign_id = _require_context_value(context.campaign_id, "campaign_id")
    db_path = _require_context_value(context.db_path, "db_path")
    now = datetime.now(UTC).isoformat()
    conn = open_campaign_db(db_path)
    try:
        close_turn(
            conn,
            TurnCloseBundle(
                turn_record=TurnRecord(
                    turn_id="mvp_turn_000001",
                    campaign_id=campaign_id,
                    session_id="session_001",
                    status="complete",
                    started_at=now,
                    completed_at=now,
                    schema_version=1,
                ),
                transcript_entries=[
                    TranscriptEntry(
                        turn_id="mvp_turn_000001",
                        kind="player_input",
                        content="quit after MVP smoke turn",
                        sequence=0,
                        created_at=now,
                    ),
                    TranscriptEntry(
                        turn_id="mvp_turn_000001",
                        kind="narration_final",
                        content="Smoke resumes after quit.",
                        sequence=1,
                        created_at=now,
                    ),
                ],
                roll_results=[],
                provider_logs=[],
                state_deltas=[],
                cost_logs=[],
                checkpoint_refs=[
                    CheckpointRef(
                        checkpoint_id="mvp_final_checkpoint_000001",
                        turn_id="mvp_turn_000001",
                        kind="final",
                        created_at=now,
                    )
                ],
            ),
        )
    finally:
        conn.close()
    return "final checkpoint persisted"


def _mvp_resume(context: _MvpSmokeContext) -> str:
    from sagasmith.tui.runtime import build_app

    root = _require_context_value(context.root, "root")
    app = build_app(root, build_graph_runtime=False)
    try:
        if "Smoke resumes after quit." not in app.initial_scrollback:
            raise RuntimeError("resume scrollback missing completed turn narration")
        if app.current_session_number != 2:
            raise RuntimeError(f"expected session 2 after resume, got {app.current_session_number}")
    finally:
        app.on_unmount()
    return "scrollback restored session=2"


def run_smoke() -> SmokeResult:
    """Run Phase 1 invariant checks without network or provider imports."""

    result = SmokeResult()
    state = make_valid_saga_state()

    try:
        assert_round_trip(state)
        result.checks.append(SmokeCheck("schema.round_trip.saga_state", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("schema.round_trip.saga_state", False, str(exc)))

    bad = state.model_dump(mode="json")
    bad.pop("campaign_id", None)
    try:
        validate_persisted_state(bad)
        result.checks.append(
            SmokeCheck(
                "schema.validation.rejects_missing_field",
                False,
                "Expected PersistedStateError; got none",
            )
        )
    except PersistedStateError:
        result.checks.append(SmokeCheck("schema.validation.rejects_missing_field", True))
    except Exception as exc:
        result.checks.append(
            SmokeCheck(
                "schema.validation.rejects_missing_field",
                False,
                f"Wrong exception type: {type(exc).__name__}",
            )
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = export_all_schemas(Path(temp_dir))
            got = {path.name.removesuffix(".schema.json") for path in paths}
            want = {model.__name__ for model in LLM_BOUNDARY_AND_PERSISTED_MODELS}
            if got == want:
                result.checks.append(SmokeCheck("schema.export.full_coverage", True))
            else:
                result.checks.append(
                    SmokeCheck(
                        "schema.export.full_coverage",
                        False,
                        f"missing={sorted(want - got)} extra={sorted(got - want)}",
                    )
                )
    except Exception as exc:
        result.checks.append(SmokeCheck("schema.export.full_coverage", False, str(exc)))

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = export_all_schemas(Path(temp_dir))
            blob = "\n".join(path.read_text(encoding="utf-8") for path in paths)
            hits = RedactionCanary().scan(blob)
            if hits:
                result.checks.append(
                    SmokeCheck(
                        "redaction.exported_schemas_clean",
                        False,
                        f"{len(hits)} secret-shaped strings; first={hits[0].label}",
                    )
                )
            else:
                result.checks.append(SmokeCheck("redaction.exported_schemas_clean", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("redaction.exported_schemas_clean", False, str(exc)))

    try:
        state_json = json.dumps(state.model_dump(mode="json"))
        if len(state_json) < 20_000:
            result.checks.append(
                SmokeCheck("state.compact_references", True, f"{len(state_json)} bytes")
            )
        else:
            result.checks.append(
                SmokeCheck(
                    "state.compact_references",
                    False,
                    f"SagaState JSON is {len(state_json)} bytes; STATE-05 requires < 20000",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("state.compact_references", False, str(exc)))

    try:
        cs = make_valid_character_sheet()
        try:
            type(cs).model_validate({**cs.model_dump(), "current_hp": cs.max_hp + 1})
            result.checks.append(
                SmokeCheck(
                    "schema.hp_invariant.rejects_over_max",
                    False,
                    "Expected ValidationError for current_hp > max_hp",
                )
            )
        except pydantic.ValidationError:
            result.checks.append(SmokeCheck("schema.hp_invariant.rejects_over_max", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("schema.hp_invariant.rejects_over_max", False, str(exc)))

    try:
        hits = RedactionCanary().scan("sk-proj-aaaabbbbccccddddeeeeffff")
        labels = [h.label for h in hits]
        if labels == ["openai_project_key"]:
            result.checks.append(SmokeCheck("redaction.openai_project_key.labeled", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "redaction.openai_project_key.labeled",
                    False,
                    f"expected 1 openai_project_key hit, got {len(hits)} hits with labels={labels}",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("redaction.openai_project_key.labeled", False, str(exc)))

    try:
        client = DeterministicFakeClient(
            {"default": make_fake_llm_response(text='{"ok":true}', parsed_json={"ok": True})}
        )
        request = LLMRequest(
            agent_name="smoke",
            model="fake-default",
            messages=[Message(role="user", content="ping")],
            response_format="json_schema",
            json_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
            temperature=0.0,
            timeout_seconds=10,
        )
        response = invoke_with_retry(
            client,
            request,
            cheap_model="fake-cheap",
            agent_name="smoke",
            turn_id=None,
            logger=lambda r: None,
        )
        if response.parsed_json == {"ok": True}:
            result.checks.append(SmokeCheck("provider.fake.round_trip", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "provider.fake.round_trip",
                    False,
                    f"parsed_json mismatch: {response.parsed_json}",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("provider.fake.round_trip", False, str(exc)[:200]))

    try:
        gov = CostGovernor(1.0)
        update1 = gov.record_usage(
            provider="fake",
            model="fake-default",
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.75
            ),
        )
        update2 = gov.record_usage(
            provider="fake",
            model="fake-default",
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.10
            ),
        )
        if update1.warnings_fired_this_call == ["70"] and update2.warnings_fired_this_call == []:
            result.checks.append(SmokeCheck("cost.warning.fires_once_per_threshold", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "cost.warning.fires_once_per_threshold",
                    False,
                    f"update1={update1.warnings_fired_this_call} update2={update2.warnings_fired_this_call}",
                )
            )
    except Exception as exc:
        result.checks.append(
            SmokeCheck("cost.warning.fires_once_per_threshold", False, str(exc)[:200])
        )

    try:
        gov = CostGovernor(1.0)
        gov.record_usage(
            provider="fake",
            model="fake-default",
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0, provider_cost_usd=0.95
            ),
        )
        result_preflight = gov.preflight(
            provider="fake",
            model="fake-default",
            prompt_tokens=10000,
            max_tokens_fallback=100000,
        )
        if result_preflight.blocked is True and gov.state.spent_usd_estimate == 0.95:
            result.checks.append(SmokeCheck("cost.hard_stop.before_call", True))
        else:
            result.checks.append(
                SmokeCheck(
                    "cost.hard_stop.before_call",
                    False,
                    f"blocked={result_preflight.blocked} spent={gov.state.spent_usd_estimate}",
                )
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("cost.hard_stop.before_call", False, str(exc)[:200]))

    try:
        from sagasmith.persistence.db import campaign_db
        from sagasmith.persistence.migrations import apply_migrations
        from sagasmith.persistence.repositories import (
            CheckpointRefRepository,
            CostLogRepository,
            ProviderLogRepository,
            RollLogRepository,
            StateDeltaRepository,
            TranscriptRepository,
            TurnRecordRepository,
        )
        from sagasmith.persistence.turn_close import TurnCloseBundle, close_turn
        from sagasmith.schemas.mechanics import RollResult
        from sagasmith.schemas.persistence import (
            CheckpointRef,
            CostLogRecord,
            StateDeltaRecord,
            TranscriptEntry,
            TurnRecord,
        )
        from sagasmith.schemas.provider import ProviderLogRecord

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.db"
            with campaign_db(path) as conn:
                apply_migrations(conn)
                bundle = TurnCloseBundle(
                    turn_record=TurnRecord(
                        turn_id="smoke_t1",
                        campaign_id="c1",
                        session_id="s1",
                        status="complete",
                        started_at="2026-04-26T12:00:00Z",
                        completed_at="2026-04-26T12:00:00Z",
                        schema_version=1,
                    ),
                    transcript_entries=[
                        TranscriptEntry(
                            turn_id="smoke_t1",
                            kind="player_input",
                            content="hello",
                            sequence=0,
                            created_at="2026-04-26T12:00:00Z",
                        )
                    ],
                    roll_results=[
                        (
                            RollResult(
                                roll_id="smoke_r1",
                                seed="s",
                                die="d20",
                                natural=10,
                                modifier=0,
                                total=10,
                                dc=None,
                                timestamp="2026-04-26T12:00:00Z",
                            ),
                            "smoke_t1",
                        )
                    ],
                    provider_logs=[
                        ProviderLogRecord(
                            request_id="smoke_req1",
                            provider="fake",
                            model="m",
                            agent_name="a",
                            turn_id="smoke_t1",
                            failure_kind="none",
                            retry_count=0,
                            latency_ms=0,
                            response_hash="abc",
                            timestamp="2026-04-26T12:00:00Z",
                        )
                    ],
                    state_deltas=[
                        StateDeltaRecord(
                            turn_id="smoke_t1",
                            delta_id="smoke_d1",
                            source="rules",
                            path="hp",
                            operation="set",
                            value_json="10",
                            reason="init",
                            applied_at="2026-04-26T12:00:00Z",
                        )
                    ],
                    cost_logs=[
                        CostLogRecord(
                            turn_id="smoke_t1",
                            provider="fake",
                            model="m",
                            agent_name="a",
                            cost_usd=0.0,
                            cost_is_approximate=True,
                            tokens_prompt=0,
                            tokens_completion=0,
                            warnings_fired=[],
                            spent_usd_after=0.0,
                            timestamp="2026-04-26T12:00:00Z",
                        )
                    ],
                    checkpoint_refs=[
                        CheckpointRef(
                            checkpoint_id="smoke_cp1",
                            turn_id="smoke_t1",
                            kind="final",
                            created_at="2026-04-26T12:00:00Z",
                        )
                    ],
                )
                close_turn(conn, bundle)

                tr = TurnRecordRepository(conn)
                turn = tr.get("smoke_t1")
                ok = (
                    turn is not None
                    and turn.status == "complete"
                    and len(TranscriptRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(RollLogRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(ProviderLogRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(StateDeltaRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(CostLogRepository(conn).list_for_turn("smoke_t1")) == 1
                    and len(CheckpointRefRepository(conn).list_for_turn("smoke_t1")) == 1
                )
                if ok:
                    result.checks.append(
                        SmokeCheck("persistence.turn_close.transaction_ordering", True)
                    )
                else:
                    result.checks.append(
                        SmokeCheck(
                            "persistence.turn_close.transaction_ordering",
                            False,
                            "row counts or turn status mismatch",
                        )
                    )
    except Exception as exc:
        result.checks.append(
            SmokeCheck("persistence.turn_close.transaction_ordering", False, str(exc)[:200])
        )

    # Check #11: CLI init produces a valid campaign layout (CLI-01).
    try:
        with tempfile.TemporaryDirectory() as td:
            from sagasmith.app.campaign import init_campaign, open_campaign

            root = Path(td) / "smoke-campaign"
            init_campaign(name="Smoke Test", root=root, provider="fake")
            paths, manifest = open_campaign(root)
            assert manifest.campaign_name == "Smoke Test"
            assert paths.db.is_file()
            assert paths.player_vault.is_dir()
        result.checks.append(SmokeCheck("cli.init.creates_storage", True))
    except Exception as exc:
        result.checks.append(SmokeCheck("cli.init.creates_storage", False, str(exc)[:200]))

    # Check #12: Phase 5 deterministic rules-first vertical slice (no provider calls).
    try:
        from sagasmith.rules.first_slice import make_first_slice_character, make_first_slice_enemies
        from sagasmith.services.combat_engine import CombatEngine
        from sagasmith.services.dice import DiceService
        from sagasmith.services.rules_engine import RulesEngine

        sheet = make_first_slice_character()
        dice = DiceService(campaign_seed="smoke_rules_first", session_seed="session_001")
        rules = RulesEngine(dice=dice)
        skill = rules.resolve_check(
            sheet,
            stat="athletics",
            dc=15,
            reason="smoke rules-first skill check",
            roll_index=0,
        )
        combat = CombatEngine(dice=dice, rules=rules)
        combat_state, initiative = combat.start_encounter(
            sheet,
            make_first_slice_enemies(),
            roll_index=1,
        )
        while combat_state.active_combatant_id != sheet.id:
            combat_state = combat.end_turn(combat_state)
        combat_state, attack, damage = combat.resolve_strike(
            combat_state,
            sheet.id,
            "enemy_weak_melee",
            "longsword",
            roll_index=len([skill, *initiative]),
        )
        ok = (
            skill.roll_result.roll_id.startswith("roll_")
            and len(initiative) == 3
            and attack.roll_result.roll_id.startswith("roll_attack_longsword_")
            and combat_state.action_counts[sheet.id] == 2
            and combat_state.initiative_order
            and (damage is None or damage.roll_id.startswith("roll_damage_longsword_"))
        )
        if ok:
            detail = f"skill={skill.roll_result.roll_id} attack={attack.roll_result.roll_id}"
            result.checks.append(SmokeCheck("rules_first_vertical_slice", True, detail))
        else:
            result.checks.append(
                SmokeCheck("rules_first_vertical_slice", False, "mechanics state mismatch")
            )
    except Exception as exc:
        result.checks.append(SmokeCheck("rules_first_vertical_slice", False, str(exc)[:200]))

    return result
