"""供未来 orchestrator 使用的确定性路由信号。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RequestKind(StrEnum):
    REQUIREMENT = "requirement"
    SPECIFICATION = "specification"
    IMPLEMENTATION = "implementation"
    RESEARCH = "research"
    TEST = "test"
    REVIEW = "review"
    QUESTION = "question"


class ExplicitTarget(StrEnum):
    NONE = "none"
    INTAKE_SPEC = "intake_spec"
    REQUIREMENT_CLARIFIER = "requirement_clarifier"
    OTHER = "other"


class RouteDecision(StrEnum):
    INVOKE = "INVOKE"
    VALIDATE_ONLY = "VALIDATE_ONLY"
    SKIP = "SKIP"


class RoutingSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_kind: RequestKind
    explicit_target: ExplicitTarget = ExplicitTarget.NONE
    wants_task_spec: bool = False
    needs_planner_handoff: bool = False
    has_complete_task_spec: bool = False
    wants_spec_revision_or_validation: bool = False


def decide_route(signals: RoutingSignals) -> RouteDecision:
    """根据上游已提取的结构化信号决定是否进入 intake_spec。"""
    if signals.explicit_target == ExplicitTarget.INTAKE_SPEC:
        return RouteDecision.INVOKE
    if signals.explicit_target != ExplicitTarget.NONE:
        return RouteDecision.SKIP
    if signals.has_complete_task_spec:
        return (
            RouteDecision.VALIDATE_ONLY
            if signals.wants_spec_revision_or_validation
            else RouteDecision.SKIP
        )
    if signals.wants_task_spec or signals.needs_planner_handoff:
        return RouteDecision.INVOKE
    if signals.request_kind == RequestKind.SPECIFICATION:
        return RouteDecision.INVOKE
    return RouteDecision.SKIP
