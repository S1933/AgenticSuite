"""Provider adapters (ADR 0005 D3, kind model/cli/api).

``base`` — role → provider resolution and the closed role/capability sets.
``model_evaluator`` — the separate-process judge invoked by the runner
through AGENTIC_EVALUATOR_CMD. It reads its own machine config — the API
key never travels through the evaluator env (which is stripped of
secrets) nor through argv beyond its config-file path.
"""

from agentic_suite.providers.base import (
    ALLOWED_KINDS,
    ALLOWED_ROLES,
    ROLE_CAPABILITIES,
    ProviderCapabilityError,
    ProviderLoadError,
    RoleAssignmentMissing,
    resolve_role_provider,
)

__all__ = [
    "ALLOWED_KINDS",
    "ALLOWED_ROLES",
    "ROLE_CAPABILITIES",
    "ProviderCapabilityError",
    "ProviderLoadError",
    "RoleAssignmentMissing",
    "resolve_role_provider",
]