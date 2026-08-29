# 路由边界

仅在判断是否应触发 Intake & Spec Agent，或处理与旧 Requirement Agent 的并存冲突时读取。

## 应触发

- 用户显式指定 `intake_spec`、Intake & Spec Agent 或 `$intake-spec`。
- 用户要求 TaskSpec、任务合同、实施就绪规格或 Planner 可消费的输入。
- 用户请求后续实现，但目标、范围、权限或验收存在会改变实现方向的实质歧义。
- Planner 收到未结构化 raw request，需要先形成可信规格。

## 不应触发

- 普通概念解释、状态查询或闲聊。
- 已明确、低风险且可以直接实现的编码任务。
- 资料搜索、代码审查、执行测试或最终产品验收。
- 单纯要求 Requirement Agent 澄清需求且没有 TaskSpec 或交接需求。
- 已有完整 TaskSpec 且用户没有要求修订；此时最多做明确请求的 schema 校验。

## 与 Requirement Agent 并存

- Requirement Agent 保持“需求澄清与最终需求方案”职责。
- Intake & Spec Agent 在用户需要进一步形成可执行 TaskSpec 和 Planner handoff 时使用。
- 用户显式选择其中一个时，以用户当前选择为准。
- 不通过扩大描述或卸载旧 Agent 解决路由重叠；用正负样本测试收窄触发条件。
