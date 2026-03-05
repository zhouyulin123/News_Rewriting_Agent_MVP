from __future__ import annotations

"""LLM 客户端封装：模型初始化、文本调用、JSON 解析。"""

import json
import os
import re
from typing import Any

from ..config import AgentConfig

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None


JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def create_chat_model(config: AgentConfig):
    """根据配置和环境变量创建 ChatOpenAI 实例。

    注意：
    - API Key 必须来自环境变量；
    - 若未配置好，返回 None，调用方可走 fallback。
    """
    if not config.llm.enabled or ChatOpenAI is None:
        return None

    api_key = os.getenv(config.llm.api_key_env)
    if not api_key:
        return None

    base_url = os.getenv(config.llm.base_url_env, config.llm.base_url)
    return ChatOpenAI(
        model=config.llm.model,
        base_url=base_url,
        api_key=api_key,
        temperature=config.llm.temperature,
        max_retries=config.llm.max_retries,
        timeout=config.llm.timeout_seconds,
    )


async def invoke_text(llm, system_prompt: str, user_prompt: str) -> str:
    """调用 LLM 并返回纯文本。"""
    if llm is None:
        raise RuntimeError("LLM is not configured")

    response = await llm.ainvoke(
        [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
    )
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content).strip()


async def invoke_json(llm, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], str]:
    """调用 LLM 并将结果解析成 JSON，返回 (parsed, raw_text)。"""
    text = await invoke_text(llm, system_prompt, user_prompt)
    return parse_json_response(text), text


def parse_json_response(text: str) -> dict[str, Any]:
    """尽量稳健地从模型输出中解析 JSON。

    兼容两种常见形式：
    - ```json ... ```
    - 前后带自然语言说明的 JSON 片段
    """
    candidate = text.strip()
    block = JSON_BLOCK_RE.search(candidate)
    if block:
        candidate = block.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(candidate[start : end + 1])
        raise
