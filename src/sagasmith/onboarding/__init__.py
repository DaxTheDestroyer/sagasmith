"""SagaSmith onboarding subpackage.

Provides the wizard state machine, phase prompt catalog, and storage layer
for the nine-phase onboarding interview.
"""

from .prompts import (
    ONBOARDING_PHASES,
    PHASE_ORDER,
    OnboardingPhase,
    PhasePrompt,
    PromptField,
    PromptFieldKind,
    parse_answer,
)
from .wizard import OnboardingWizard, StepResult

__all__ = [
    "ONBOARDING_PHASES",
    "PHASE_ORDER",
    "OnboardingPhase",
    "OnboardingWizard",
    "PhasePrompt",
    "PromptField",
    "PromptFieldKind",
    "StepResult",
    "parse_answer",
]
