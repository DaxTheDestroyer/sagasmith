"""Settings command implementation: /settings — displays onboarding summary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagasmith.tui.app import SagaSmithApp

from sagasmith.tui.widgets.narration import NarrationArea


def _write(app: SagaSmithApp, line: str) -> None:
    app.query_one(NarrationArea).append_line(line)


@dataclass(frozen=True)
class SettingsCommand:
    name: str = "settings"
    description: str = "Review or adjust onboarding settings (ONBD-05)."

    def handle(self, app: SagaSmithApp, args: tuple[str, ...]) -> None:
        store = app.onboarding_store
        if store is None:
            _write(app, "[system] /settings: onboarding store not bound.")
            return
        triple = store.reload(app.manifest.campaign_id)
        if triple is None:
            _write(
                app,
                "[system] /settings: no onboarding triple found. Run onboarding first "
                "(Phase 4 integration will launch the wizard inline).",
            )
            return
        p = triple.player_profile
        cp = triple.content_policy
        hr = triple.house_rules
        _write(app, "[system] /settings: current campaign profile")
        _write(app, f"  genre={p.genre}  tone={p.tone}  pacing={p.pacing}  dice_ux={p.dice_ux}")
        _write(app, f"  character_mode={p.character_mode}  death_policy={p.death_policy}")
        _write(app, f"  pillar_weights={p.pillar_weights}")
        _write(app, f"  budget=${p.budget.per_session_usd:.2f} hard_stop={p.budget.hard_stop}")
        _write(
            app,
            f"  content_policy: hard_limits={cp.hard_limits} soft_limits={cp.soft_limits} preferences={cp.preferences}",
        )
        _write(
            app,
            f"  house_rules: initiative_visible={hr.initiative_visible} allow_retcon={hr.allow_retcon} auto_save_every_turn={hr.auto_save_every_turn}",
        )
        _write(app, "  (to re-run: Phase 4 will add an interactive wizard re-entry)")
