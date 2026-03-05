from __future__ import annotations

"""正文清洗节点：去除噪声段并生成 clean_text。"""

import re

from ..config import AgentConfig
from ..models import AgentState

WHITESPACE_RE = re.compile(r"\s+")
SYMBOL_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)


def clean_article_node(config: AgentConfig):
    """生成清洗节点函数。"""

    async def node(state: AgentState) -> AgentState:
        article = state.article
        if article is None or not article.raw_text:
            state.error("clean skipped: missing raw_text")
            return state

        paragraphs = [part.strip() for part in article.raw_text.splitlines() if part.strip()]
        cleaned: list[str] = []

        for paragraph in paragraphs:
            normalized = WHITESPACE_RE.sub(" ", paragraph).strip()
            if _is_noise(normalized, config):
                continue
            cleaned.append(normalized)

        article.paragraphs = cleaned
        article.clean_text = "\n".join(cleaned)
        return state

    return node


def _is_noise(paragraph: str, config: AgentConfig) -> bool:
    """规则判定噪声段落。"""
    if len(paragraph) < config.clean.min_paragraph_length:
        return True
    if SYMBOL_ONLY_RE.fullmatch(paragraph):
        return True
    if any(keyword in paragraph for keyword in config.clean.noise_keywords):
        return True
    # 纯链接导向段落通常不属于正文。
    if paragraph.count("http") >= 1:
        return True
    return False
