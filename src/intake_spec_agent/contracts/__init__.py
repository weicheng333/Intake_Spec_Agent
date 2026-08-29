"""Intake & Spec Agent 的公开数据契约。"""

from .handoff import AgentMessage, HandoffEnvelope, IntakeSpecRoleOutput
from .requirement_record import RequirementRecord
from .task_spec import TaskSpec

__all__ = [
    "AgentMessage",
    "HandoffEnvelope",
    "IntakeSpecRoleOutput",
    "RequirementRecord",
    "TaskSpec",
]
