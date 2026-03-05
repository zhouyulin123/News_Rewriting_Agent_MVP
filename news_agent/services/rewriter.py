from __future__ import annotations

"""改写节点：根据热点正文与示例生成最终口播文案。"""

import re

from ..config import AgentConfig
from ..models import AgentState, ScriptResult
from .llm_client import create_chat_model, invoke_text

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")


def rewrite_script_node(config: AgentConfig):
    llm = create_chat_model(config)

    async def node(state: AgentState) -> AgentState:
        article = state.article
        if article is None:
            state.error("rewrite skipped: missing article")
            return state

        if llm is None:
            state.error("rewrite skipped: LLM is not configured")
            return _fallback_script(state)

        try:
            user_prompt = _build_rewrite_prompt(state, config)
            raw_text = await invoke_text(llm, config.prompt.rewrite_system_prompt, user_prompt)
            cleaned_text = _clean_generated_text(raw_text)
            state.script = ScriptResult(
                title=article.title or "热点口播稿",
                script_text=cleaned_text,
                segments=_split_segments(cleaned_text),
                hashtags=_build_hashtags(state),
            )
            state.llm_outputs["rewrite"] = {"raw": raw_text}
            return state
        except Exception as exc:
            state.error(f"rewrite llm fallback: {exc}")
            return _fallback_script(state)

    return node


def _build_rewrite_prompt(state: AgentState, config: AgentConfig) -> str:
    article = state.article
    built_in_examples = "\n\n".join(config.prompt.built_in_examples)
    references = "\n\n".join(
        f"参考文案{i}：\n{text}" for i, text in enumerate(state.reference_texts, start=1) if text.strip()
    )
    references = references or "无"
    style_example = state.style_example.strip() if state.style_example else "无"
    qa_feedback = "；".join(state.qa_feedback) if state.qa_feedback else "无"
    return (
        f"热点标题：{article.title or ''}\n"
        f"热点正文：\n{(article.clean_text or article.raw_text or '')[:6000]}\n\n"
        f"当前改写轮次：{state.rewrite_attempt}\n"
        f"上轮 QA 未通过原因：{qa_feedback}\n\n"
        f"系统内置参考示例：\n{built_in_examples}\n\n"
        f"参考其他博主文案：\n{references}\n\n"
        f"用户自己的示例文案：\n{style_example}\n\n"
        f"写作参数：\n"
        f"- 主题分类：{state.topic.label}\n"
        f"- 字数范围：{config.rewrite.min_chars}~{config.rewrite.max_chars}\n"
        f"- 语气：{config.rewrite.tone}\n"
        "请直接输出最终文案。"
    )


def _clean_generated_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()
    return cleaned


def _split_segments(text: str) -> list[str]:
    segments = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return segments or [text]


def _build_hashtags(state: AgentState) -> list[str]:
    topic = state.topic.label or "社会"
    return [f"#{topic}", "#热点", "#口播文案"]


def _fallback_script(state: AgentState) -> AgentState:
    article = state.article
    if article is None:
        return state

    summary = (article.clean_text or article.raw_text or "")[:80]
    title = article.title or "热点口播稿"
    parts = [
        f"今天聊一个{state.topic.label}相关的话题，先看标题，{title}。",
        f"这件事的核心其实就一句话：{summary}",
    ]
    if article.paragraphs:
        parts.append("具体来看，" + "，".join(article.paragraphs[:3]))
    parts.append("如果你也在关注这个品类、品牌或相关消费趋势，这条信息值得继续跟进。")
    script_text = "".join(parts)
    state.script = ScriptResult(
        title=title,
        script_text=script_text,
        segments=_split_segments(script_text),
        hashtags=_build_hashtags(state),
    )
    return state
