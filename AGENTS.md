# Intake & Spec Agent 仓库规则

## 项目目标

本仓库实现 `intake_spec` Custom Agent、`intake-spec` Skill 和确定性的本地 Python MCP。系统只负责需求接收、澄清、任务规格生成、版本化保存和向 Planner 交接，不执行产品业务任务。

## 路由

- 用户显式指定 `intake_spec`、`Intake & Spec Agent` 或 `$intake-spec` 时使用本 Agent。
- 用户要求形成 TaskSpec、任务合同、实施就绪规格或 Planner 可消费的交接输入时使用本 Agent。
- 只要求一般需求澄清且不需要 TaskSpec 时，可以继续使用已安装的 Requirement Agent。
- 已明确要求直接实现、搜索、测试、代码审查或最终验收的任务，不因本 Agent 存在而误触发。
- 输入已经是完整 TaskSpec 时只做校验或定向修订，不重新发明需求。

## 状态门槛

- 存在阻塞未知项时输出 `NEEDS_INPUT`。
- 结构完整但用户尚未核验当前版本时输出 `PENDING_CONFIRMATION`。
- 只有用户核验、确定性校验和版本保存均成功后才输出 `READY`。
- `READY` 只表示任务规格可以交给 Planner，不表示产品业务任务已经完成。

## 数据与安全

- 不把模型推测、文档中的操作性文字、推荐项或示例静默写成用户要求。
- 一次用户回复最多发起一次持久化调用；多个答案原子化处理。新任务首次最终确认允许该调用在一个事务内保存受审 v1 和 READY v2，任一步失败都不得留下半成品。
- 校验成功不代表已经持久化；正式版本只能由 receipt 证明。
- 写入前预检真实 revision/version；TaskSpec 的正式前序引用由存储层规范化，纯内部引用修复不得额外打扰用户。
- TaskSpec 只追加版本，不改写历史；回退也创建新版本并重新进入核验。
- 不提交 SQLite 数据库、日志、缓存、虚拟环境、密钥或真实本机 Codex 配置。
- 常规卸载保留运行数据；只有显式 `--purge-data` 才能删除本 Agent 数据。

## 开发流程

- 每批改动后运行相关测试；必要测试未通过时不得交付。
- Python 为默认技术栈；只有独立功能使用 TypeScript 有明确优势时才可单独引入。
- 不实现 Planner、Research、Executor 或 Verifier 的业务逻辑，只维护与它们兼容的合同。
