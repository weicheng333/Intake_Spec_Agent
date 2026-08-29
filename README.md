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

也可以直接要求“整理成 TaskSpec”“形成任务合同”或“生成 Planner 可消费的规格”。只要求普通需求澄清且不需要 TaskSpec 时，旧 Requirement Agent 可以继续使用。

状态含义：

- `NEEDS_INPUT`：仍有会改变范围、合法性、关键验收或不可逆路径的阻塞问题。
- `PENDING_CONFIRMATION`：规格结构完整，等待用户核验当前 revision 和 checksum。
- `READY`：用户已核验，确定性校验和版本化保存成功，可以交给 Planner；不代表业务任务已经执行。

从 `1.1.0` 起，验证 evidence 与持久化 receipt 明确分离。新任务在用户确认后通过一次原子调用同时保存受审 v1 和 READY v2；已有任务写入前先预检当前版本。TaskSpec 的 `requirement_record_ref` 和 `previous_version_ref` 由存储层规范化为正式地址，内部引用修复不会再要求用户重复确认。

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
