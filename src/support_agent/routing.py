"""Route derivation (architecture §6). The model never writes ``route``; code derives it [AR-02].

- ``escalate`` if the tripwire forced a reason or the model declared one;
- else ``both`` / ``tool`` if the tool actually ran (``not_found`` counts, A-08), split by
  ``policy_applied``;
- else ``policy`` (including out-of-scope declines, A-09).
"""

from __future__ import annotations

from typing import Literal, cast, get_args

Route = Literal["policy", "tool", "both", "escalate"]
ROUTES: tuple[str, ...] = get_args(Route)


def derive_route(
    *,
    forced_reason: str | None,
    escalation_reason: str | None,
    tool_executed: bool,
    policy_applied: bool,
) -> Route:
    """The route for one case; ``forced_reason`` takes precedence over the model's fields."""
    if forced_reason or (escalation_reason and escalation_reason != "none"):
        return "escalate"
    if tool_executed:
        return "both" if policy_applied else "tool"
    return "policy"


def ensure_route(value: str) -> Route:
    """Enforce the route enum before an answer line is written (SEZ-C04)."""
    if value not in ROUTES:
        raise ValueError(f"invalid route {value!r}; expected one of {ROUTES}")
    return cast(Route, value)
