"""交互规则静态回归；不替代真实会话中的模型行为验收。"""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_final_plan_offers_scoped_continuation() -> None:
    skill = (ROOT / ".agents/skills/intake-spec/SKILL.md").read_text()
    for rule in (
        "继续完善的主决策点在完整需求清单之前", "是否继续完善当前需求",
        "保留当前任务和已有决定", "可选完善不应伪装成阻塞项",
        "不增加版本、不写入", "旧确认不得用于新方案",
        "不等于确认", "先用一个简短问题澄清意图",
        "不强迫额外澄清", "不代表授权实施", "未修改前原定稿仍保留",
    ):
        assert rule in skill


def test_dimension_analysis_covers_ambiguous_user_words() -> None:
    skill = (ROOT / ".agents/skills/intake-spec/SKILL.md").read_text()
    reference = (ROOT / ".agents/skills/intake-spec/references/clarification-flow.md").read_text()
    for rule in (
        "用户已经说过但不清晰", "引用原话", "提问前先展示",
        "每轮最多五题", "必要项必须解决", "可选项由用户选择",
        "推荐继续或停止", "当前完整需求清单",
    ):
        assert rule in skill
    for rule in (
        "用户已明确", "暂定假设", "尚未涉及", "不建议重复补充",
        "不声称已经穷尽", "推荐不能作为", "没有预算或截止日期保持 null",
    ):
        # 维度相关性的不穷尽约束位于入口；详细方法位于按需引用。
        assert rule in reference or rule in skill


def test_custom_agent_preserves_confirmation_gate() -> None:
    agent = tomllib.loads((ROOT / ".codex/agents/intake_spec.toml").read_text())
    instructions = agent["developer_instructions"]
    assert "继续需求澄清" in instructions
    assert "不继续”不等于确认" in instructions
    assert "仅选择继续不增加版本或写入" in instructions
    assert "只有用户确认当前 revision" in instructions
    assert "initialize_confirmed_task_spec" in instructions
