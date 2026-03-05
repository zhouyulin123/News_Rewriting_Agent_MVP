from __future__ import annotations

"""导出节点：聚合结果并按配置写入文件。"""

import json
from pathlib import Path

from ..config import AgentConfig
from ..models import AgentState


def export_result_node(config: AgentConfig):
    """生成导出节点函数。"""

    async def node(state: AgentState) -> AgentState:
        # output 字段是对外统一结果视图，便于 API/CLI/后续存储直接复用。
        state.output = {
            "url": state.url,
            "article": state.article,
            "topic": state.topic,
            "script": state.script,
            "qa": state.qa,
            "errors": state.errors,
            "logs": state.logs,
        }
        if config.export.output_dir:
            await _write_outputs(state, config.export.output_dir, config)
        return state

    return node


async def _write_outputs(state: AgentState, output_dir: Path, config: AgentConfig) -> None:
    """将结果按配置写成 json / markdown 文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(state.url)
    payload = state.to_dict()

    if config.export.write_json:
        (output_dir / f"{safe_name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if config.export.write_markdown:
        markdown = _to_markdown(state)
        (output_dir / f"{safe_name}.md").write_text(markdown, encoding="utf-8")


def _safe_filename(url: str) -> str:
    """把 URL 转成可落盘的文件名。"""
    return "".join(char if char.isalnum() else "_" for char in url)[:80]


def _to_markdown(state: AgentState) -> str:
    """将结果转换为便于阅读的 Markdown。"""
    article = state.article
    script = state.script
    qa = state.qa
    lines = [
        f"# {script.title or '新闻口播稿'}",
        "",
        f"- URL: {state.url}",
        f"- Topic: {state.topic.label}",
        f"- QA: {'pass' if qa.passed else 'fail'}",
        "",
        "## Script",
        "",
        script.script_text,
    ]
    if article and article.clean_text:
        lines.extend(["", "## Clean Text", "", article.clean_text])
    if qa.issues:
        lines.extend(["", "## QA Issues", "", *[f"- {issue}" for issue in qa.issues]])
    return "\n".join(lines)
