from __future__ import annotations

"""质检节点：对最终文案做基础规则检查。"""

from ..config import AgentConfig
from ..models import AgentState, QAResult


def qa_check_node(config: AgentConfig):
    """生成质检节点函数。"""

    async def node(state: AgentState) -> AgentState:
        issues: list[str] = []
        article = state.article
        script = state.script

        if article is None or not article.clean_text:
            issues.append("缺少清洗后的正文")
        if not script.script_text:
            issues.append("未生成口播稿")

        char_count = len(script.script_text.strip())
        if char_count and char_count < config.rewrite.min_chars:
            issues.append(f"口播稿偏短，当前约 {char_count} 字")
        if char_count > config.rewrite.max_chars:
            issues.append(f"口播稿偏长，当前约 {char_count} 字")

        state.qa = QAResult(passed=not issues, issues=issues)
        return state

    return node
