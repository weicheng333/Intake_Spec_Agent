from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).parents[1] / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))


def _unknown(identifier: str = "unknown_scope") -> dict:
    return {
        "id": identifier,
        "question": "是否包含管理员审批流程？",
        "impact": "不同答案会改变权限范围和验收标准。",
        "primary_dimension": "权限",
        "related_dimensions": ["范围", "验收标准"],
    }


@pytest.fixture
def ready_requirement_payload() -> dict:
    return {
        "schema_version": "1.0.0",
        "task_id": "TASK-DEMO-001",
        "revision": 2,
        "status": "READY",
        "goal": "制作 Intake & Spec Agent。",
        "success_definition": "生成通过确定性校验且可交给 Planner 的 TaskSpec。",
        "user_stated_facts": [
            {
                "id": "fact_python",
                "statement": "整套 Agent 系统优先使用 Python。",
                "source": "user",
            }
        ],
        "constraints": [
            {
                "id": "constraint_python",
                "category": "technical",
                "statement": "使用 Python 3.11 或更高版本。",
                "source_fact_ids": ["fact_python"],
            }
        ],
        "preferences": [],
        "assumptions": [],
        "unknowns": {"blocking": [], "non_blocking": []},
        "risks": [
            {
                "id": "risk_routing",
                "statement": "新旧 Agent 的触发条件可能重叠。",
                "likelihood": "medium",
                "impact": "high",
                "mitigation": "使用正向和负向路由测试收窄触发条件。",
            }
        ],
        "scope": {
            "included": ["Intake & Spec Agent"],
            "excluded": ["Planner 业务逻辑"],
        },
        "actors": [
            {
                "id": "actor_user",
                "name": "Codex 用户",
                "role": "需求提出者",
                "needs": ["核验最终需求方案"],
            }
        ],
        "data_requirements": [],
        "permissions": [],
        "exception_cases": [],
        "acceptance_expectations": [
            {
                "id": "expect_schema",
                "statement": "TaskSpec 必须通过 schema 校验。",
                "verification_hint": "运行契约测试。",
            }
        ],
        "open_questions": [],
        "final_confirmation": {
            "confirmed_at": "2026-08-29T09:00:00+08:00",
            "confirmed_by": "user",
            "reviewed_revision": 1,
            "confirmed_revision": 2,
            "checksum_sha256": "98da184163a707a70423ce71a3a6a1d4c7ef8b8c4426a70ad5313743986fe492",
        },
        "created_at": "2026-08-29T08:00:00+08:00",
        "updated_at": "2026-08-29T09:00:00+08:00",
    }


@pytest.fixture
def ready_task_spec_payload() -> dict:
    return {
        "schema_version": "1.0.0",
        "task_id": "TASK-DEMO-001",
        "version": 1,
        "status": "READY_FOR_PLANNING",
        "objective": "实现 Intake & Spec Agent 数据契约。",
        "scope": {
            "included": ["RequirementRecord", "TaskSpec"],
            "excluded": ["Planner 业务逻辑"],
        },
        "deliverables": [
            {
                "id": "deliverable_contracts",
                "description": "Python 数据模型和 JSON Schema。",
                "artifact_type": "source_code",
                "acceptance_criterion_ids": ["criterion_validation"],
            }
        ],
        "acceptance_criteria": [
            {
                "id": "criterion_validation",
                "statement": "合法输入通过且非法输入失败。",
                "observable_outcome": "契约测试全部通过。",
                "verification_method": "automated",
                "critical": True,
                "evidence_requirement_ids": ["evidence_tests"],
            }
        ],
        "evidence_requirements": [
            {
                "id": "evidence_tests",
                "description": "pytest 测试报告。",
                "acceptable_evidence": ["pytest exit code 0"],
                "acceptance_criterion_ids": ["criterion_validation"],
            }
        ],
        "constraints": ["Python 3.11+"],
        "allowed_actions": ["读取当前任务上下文"],
        "prohibited_actions": ["执行产品业务代码"],
        "permissions": {
            "granted": ["读取当前任务上下文"],
            "requires_approval": ["修改全局 Codex 配置"],
            "denied": ["发送邮件"],
        },
        "assumptions": [],
        "blocking_unknowns": [],
        "risks": [],
        "budget": {
            "deadline_ms": None,
            "max_tool_calls": None,
            "max_tokens": None,
            "max_cost": None,
        },
        "deadline": None,
        "retry_limits": {
            "max_agent_hops": 12,
            "max_same_agent_retries": 2,
            "max_verifier_cycles": 2,
            "max_replans": 2,
            "max_schema_retries": 1,
        },
        "handoff_target": "planner_orchestrator",
        "requirement_record_ref": "requirement://TASK-DEMO-001/v2",
        "previous_version_ref": None,
        "created_at": "2026-08-29T09:00:00+08:00",
    }


@pytest.fixture
def handoff_payload(ready_task_spec_payload: dict) -> dict:
    task_spec_ref = "taskspec://TASK-DEMO-001/v1"
    return {
        "schema_version": "1.0.0",
        "trace_id": "TRACE-DEMO-001",
        "task_id": "TASK-DEMO-001",
        "parent_task_id": None,
        "sender": "intake_spec",
        "recipient": "planner_orchestrator",
        "message_type": "TASK",
        "status": "PENDING",
        "objective": ready_task_spec_payload["objective"],
        "input_refs": [task_spec_ref],
        "constraints": ["不得扩大已确认范围"],
        "permissions": ["只读任务上下文"],
        "budget": ready_task_spec_payload["budget"],
        "acceptance_criteria": ["输出满足 Planner 输入 schema"],
        "evidence_refs": [],
        "payload": {},
        "error": None,
        "next_action": "Planner 读取 TaskSpec 并制定执行计划。",
        "task_spec_ref": task_spec_ref,
        "reason_for_delegation": "需求与任务规格已完成，可以进入规划阶段。",
        "expected_output_schema": "schema://planner/task-plan/v1",
        "artifact_refs": [],
        "failure_policy": {
            "retry_limits": ready_task_spec_payload["retry_limits"],
            "permission_denied_action": "REQUEST_APPROVAL",
            "semantic_failure_action": "REQUEST_REPLAN",
            "terminal_failure_action": "ESCALATE_TO_HUMAN",
        },
    }


@pytest.fixture
def blocking_unknown_payload() -> dict:
    return deepcopy(_unknown())
