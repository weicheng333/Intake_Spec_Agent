# 数据合同

仅在生成、修订或解释 RequirementRecord、TaskSpec、role output 或 handoff 时读取本文件。确定性约束以 MCP 校验结果和包内 `contracts/*.schema.json` 为准。

## RequirementRecord

记录用户真正确认的需求事实，不是执行计划。核心字段包括：

- `task_id`、`revision`、`status`
- `goal`、`success_definition`
- `user_stated_facts`
- `constraints`、`preferences`
- `assumptions`
- `unknowns.blocking`、`unknowns.non_blocking`
- `risks`、`scope`
- `actors`、`data_requirements`、`permissions`
- `exception_cases`、`acceptance_expectations`
- `open_questions`
- `final_confirmation`

`READY` 必须没有 blocking unknown 和 open question，并包含用户最终核验记录。确认记录的 `reviewed_revision` 早于当前 `confirmed_revision`，checksum 必须对应用户看到的最终草案。

## TaskSpec

TaskSpec 是交给 Planner 的执行合同。核心字段包括：

- `task_id`、`version`、`status`
- `objective`、`scope`
- `deliverables`
- `acceptance_criteria`、`evidence_requirements`
- `constraints`
- `allowed_actions`、`prohibited_actions`、`permissions`
- `assumptions`、`blocking_unknowns`、`risks`
- `budget`、`deadline`、`retry_limits`
- `handoff_target`
- `requirement_record_ref`、`previous_version_ref`

每个 deliverable 至少引用一个存在的验收标准。关键验收标准必须引用证据要求。允许动作、禁止动作和权限分组不得冲突。用户没有提供预算或截止日期时保留 `null`。

## 状态

- RequirementRecord：`DRAFT | CLARIFYING | READY`
- TaskSpec：`DRAFT | BLOCKED | READY_FOR_PLANNING | SUPERSEDED`
- Role output：`NEEDS_INPUT | READY`

存在 blocking unknown 时 TaskSpec 使用 `BLOCKED`；用户最终核验前使用 `DRAFT`；只有核验并保存成功后使用 `READY_FOR_PLANNING`。

## Typed handoff

面向 Planner 的 handoff 必须包含 WHO、WHAT、WHY、INPUT、CONSTRAINTS、OUTPUT、DONE WHEN、EVIDENCE 和 FAILURE：

- sender 固定为 `intake_spec`
- recipient 固定为 `planner_orchestrator`
- message_type 固定为 `TASK`
- 初始 status 固定为 `PENDING`
- `task_spec_ref` 必须同时出现在 `input_refs`
- 只传 TaskSpec ref、相关 evidence/artifact refs 和最小权限，不复制完整聊天记录
