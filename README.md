# Intake & Spec Agent

Intake & Spec Agent 是一个面向 Codex 的本地需求入口。它负责把用户的原始请求整理为可信的 `RequirementRecord`，并进一步生成可执行、可验证、可交接的 `TaskSpec`。

本项目只负责需求接收、澄清和任务规格生成，不执行产品业务代码，也不承担 Planner、Research、Executor 或 Verifier 的职责。

## 开发环境

- Python 3.11 或更高版本
- 标准 `venv + pip`
- pytest

创建开发环境：

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

## 当前交付范围

- `intake_spec` Custom Agent
- `intake-spec` Skill
- 本地 STDIO MCP
- RequirementRecord 与 TaskSpec 数据契约
- SQLite 版本、幂等、回执和回退
- 写入预检、正式引用规范化，以及新任务受审 v1 → READY v2 的原子初始化
- 面向未来 Planner 的 typed handoff 契约
- 全局及项目级安全安装与卸载

运行数据、SQLite 数据库、日志、虚拟环境和本机真实 Codex 配置不得提交到仓库。

## 使用方式

可以在 Codex 中显式调用：

```text
使用 $intake-spec 澄清这个请求，并生成可验证、可交给 Planner 的 TaskSpec。
```

也可以直接要求“整理成 TaskSpec”“形成任务合同”或“生成 Planner 可消费的规格”。

状态含义：

- `NEEDS_INPUT`：仍有会改变范围、合法性、关键验收或不可逆路径的阻塞问题。
- `PENDING_CONFIRMATION`：规格结构完整，等待用户核验当前 revision 和 checksum。
- `READY`：用户已核验，确定性校验和版本化保存成功，可以交给 Planner；不代表业务任务已经执行。

从 `1.1.0` 起，验证 evidence 与持久化 receipt 明确分离。新任务在用户确认后通过一次原子调用同时保存受审 v1 和 READY v2；已有任务写入前先预检当前版本。TaskSpec 的 `requirement_record_ref` 和 `previous_version_ref` 由存储层规范化为正式地址，内部引用修复不会再要求用户重复确认。

## 1.2.0：维度先行与含糊原话澄清

新流程：分析原话和缺口 → 先列本项目相关维度及逐项建议 → 按维度提问 → 必要信息齐全后推荐继续或停止 → 用户停止后展示完整需求清单 → 单独核验、校验与版本保存 → READY。

- 维度列表标明描述完善程度、必要/可选、丰富建议和理由；不局限于固定维度。
- 对“简单、安全、自动处理”等含糊原话，说明歧义、影响并映射到对应维度；不把模型解释当用户决定。
- 每轮最多五题，可以跨维度，标题标注类型；必要项解决，可选项由用户选择。
- 给出已完善维度及成果、可丰富维度及价值，并推荐是否继续；不强迫无限完善。
- 停止后列完整需求清单、剩余假设和未采纳建议。停止不等于最终确认；核验后才保存并进入 READY，不自动实施。
- 继续时保留当前任务和决定，实际修改后重新核验；只选择继续不增加版本或写入。

本次更新仅调整 Agent/Skill 的交互规则、中文文档和包版本；Python MCP 的存储协议、JSON Schema 和历史数据不变。交互规则测试是静态检查，不能等同于实际模型会话验收。

新会话建议测试：输入“简单、安全、自动处理”的工具需求，检查先列维度再问问题；补齐必要项后选择一个可选维度继续，随后停止，核对完整清单；最后单独确认当前版本。另测直接停止但仍有必要缺口、模糊回复和修改后旧确认失效。

## 安装与卸载

全局安装：

```bash
scripts/install-global.sh
```

项目安装：

```bash
scripts/install-project.sh /ABSOLUTE/PATH/TO/PROJECT
```

普通卸载保留 SQLite 数据：

```bash
scripts/uninstall-global.sh
```

只有明确需要彻底清理本 Agent 数据时使用：

```bash
scripts/uninstall-global.sh --purge-data
```

全局运行数据默认位于 `~/.local/share/intake-spec-agent/`。安装器只管理 `intake_spec` Agent、`intake-spec` Skill、`intake_spec_mcp` 配置区块和本包 runtime，不会移除 Requirement Agent。
