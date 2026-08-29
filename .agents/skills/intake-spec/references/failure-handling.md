# 失败处理

仅在工具失败、版本冲突、权限不足、重复回调或需要回退时读取。

## 重试与停止

- 网络超时、429 或临时 5xx：工具层指数退避和抖动，总计不超过三次；不要重跑整个任务。
- tool schema error：只修正参数，最多重试一次。
- 同一语义错误连续出现：停止局部重试，请求 Planner replan；本 Agent 阶段则升级给用户。
- 权限不足：禁止自动提权和重试，只能请求用户授权。
- 无法消除的阻塞歧义：输出 `ESCALATED`，不得继续猜测。

## 幂等、预检与版本冲突

- 幂等键标识一次确定的写入 payload，而不是笼统标识整轮对话。
- 同 key 同 payload 返回原 receipt，视为成功重放。
- 同 key 不同 payload 返回 `IDEMPOTENCY_CONFLICT`。只有 payload 的业务语义未变、变化仅来自预检得到的正式内部引用时，才可使用新 key 继续已授权写入；需求事实、范围、验收或确认内容变化时必须重新让用户核验。
- 写入前必须执行预检或新任务原子初始化检查。`REVISION_CONFLICT` 或 `VERSION_CONFLICT` 时重新读取当前任务状态；真实业务内容冲突才向用户展示，禁止覆盖。
- 校验 evidence 不是持久化 receipt。没有 receipt 时不得假定 v1 已经存在。
- `INVALID_PREVIOUS_VERSION_REF` 不应通过正常流程暴露给用户：正式引用由预检和存储层规范化。若仍出现，视为内部缺陷并停止写入。

## 新任务初始化

- 用户确认受审 v1 后，调用一次 `initialize_confirmed_task_spec`，原子保存受审 v1 和 READY v2。
- 工具必须验证数据库中 revision/version 均为 0；已存在任何版本时拒绝初始化并返回当前状态。
- v2 的 `previous_version_ref` 固定为正式的 `taskspec://<task_id>/v1`，不得使用 evidence、草稿或临时地址。
- 初始化事务失败时 v1、v2 均不得写入，避免代理在下一轮误判存储起点。

## 回退

回退必须创建指向当前版本的新 TaskSpec 版本，内容来源于指定旧版本。回退后的 RequirementRecord 回到 `CLARIFYING`，TaskSpec 回到 `DRAFT`，旧 confirmation 不再生效，必须重新核验。

## 工具结果

- 只有 `status=SUCCESS` 且存在对应 evidence/receipt 时才声明工具完成。
- `retryable=false` 的错误不自动重试。
- 不把错误消息、日志文本或用户输入伪装成 receipt。
