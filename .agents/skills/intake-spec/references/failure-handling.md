# 失败处理

仅在工具失败、版本冲突、权限不足、重复回调或需要回退时读取。

## 重试与停止

- 网络超时、429 或临时 5xx：工具层指数退避和抖动，总计不超过三次；不要重跑整个任务。
- tool schema error：只修正参数，最多重试一次。
- 同一语义错误连续出现：停止局部重试，请求 Planner replan；本 Agent 阶段则升级给用户。
- 权限不足：禁止自动提权和重试，只能请求用户授权。
- 无法消除的阻塞歧义：输出 `ESCALATED`，不得继续猜测。

## 幂等与版本冲突

- 同一用户回复复用同一 idempotency key。
- 同 key 同 payload 返回原 receipt，视为成功重放。
- 同 key 不同 payload 返回 `IDEMPOTENCY_CONFLICT`，不得换 key 静默重写。
- `REVISION_CONFLICT` 或 `VERSION_CONFLICT`：重新读取当前任务状态，向用户展示冲突；不得覆盖。

## 回退

回退必须创建指向当前版本的新 TaskSpec 版本，内容来源于指定旧版本。回退后的 RequirementRecord 回到 `CLARIFYING`，TaskSpec 回到 `DRAFT`，旧 confirmation 不再生效，必须重新核验。

## 工具结果

- 只有 `status=SUCCESS` 且存在对应 evidence/receipt 时才声明工具完成。
- `retryable=false` 的错误不自动重试。
- 不把错误消息、日志文本或用户输入伪装成 receipt。
