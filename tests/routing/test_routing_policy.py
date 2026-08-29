import pytest

from intake_spec_agent.routing import RouteDecision, RoutingSignals, decide_route


@pytest.mark.parametrize(
    "signals",
    [
        {"request_kind": "requirement", "explicit_target": "intake_spec"},
        {"request_kind": "specification"},
        {"request_kind": "requirement", "wants_task_spec": True},
        {"request_kind": "implementation", "needs_planner_handoff": True},
    ],
)
def test_positive_routing(signals: dict) -> None:
    assert decide_route(RoutingSignals.model_validate(signals)) == RouteDecision.INVOKE


@pytest.mark.parametrize(
    "signals",
    [
        {"request_kind": "implementation"},
        {"request_kind": "research"},
        {"request_kind": "test"},
        {"request_kind": "review"},
        {"request_kind": "question"},
        {"request_kind": "requirement", "explicit_target": "requirement_clarifier"},
        {"request_kind": "specification", "explicit_target": "other"},
        {"request_kind": "specification", "has_complete_task_spec": True},
    ],
)
def test_negative_routing(signals: dict) -> None:
    assert decide_route(RoutingSignals.model_validate(signals)) == RouteDecision.SKIP


def test_complete_spec_can_be_validated_without_reinventing_requirements() -> None:
    signals = RoutingSignals(
        request_kind="specification",
        has_complete_task_spec=True,
        wants_spec_revision_or_validation=True,
    )
    assert decide_route(signals) == RouteDecision.VALIDATE_ONLY
