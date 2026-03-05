from __future__ import annotations

"""主题分类节点：LLM 优先，关键词兜底。"""

import json

from ..config import AgentConfig
from ..models import AgentState, TopicResult
from .llm_client import create_chat_model, invoke_json

TOPIC_KEYWORDS = {
    "体育": ["比赛", "联赛", "球队", "球员", "冠军", "进球", "比分"],
    "科技": ["AI", "芯片", "模型", "机器人", "科技", "算法", "软件"],
    "国际": ["总统", "外交", "国际", "联合国", "海外", "欧洲", "美国"],
    "财经": ["股价", "市场", "融资", "营收", "经济", "基金", "利率"],
    "娱乐": ["电影", "明星", "综艺", "票房", "剧集", "演唱会"],
    "教育": ["高考", "学校", "学生", "教育", "课程", "招生"],
    "健康": ["医院", "医生", "疾病", "药物", "健康", "患者"],
    "电商": ["平台", "带货", "直播", "销量", "商品", "品牌", "电商"],
    "家居": ["家具", "木材", "床垫", "沙发", "收纳", "装修"],
    "数码": ["手机", "耳机", "充电", "相机", "笔记本", "平板"],
}


def classify_topic_node(config: AgentConfig):
    """生成主题分类节点函数。"""
    llm = create_chat_model(config)

    async def node(state: AgentState) -> AgentState:
        article = state.article
        if article is None:
            state.error("topic skipped: missing article")
            return state

        text = "\n".join(filter(None, [article.title, article.clean_text or article.raw_text]))
        if not text.strip():
            state.error("topic skipped: empty article text")
            return state

        # 先走 LLM 分类：精度更高，可输出置信度与标签。
        if llm is not None:
            try:
                taxonomy = "、".join(config.prompt.topic_taxonomy)
                user_prompt = (
                    f"请从以下可选主题中选择最合适的一项：{taxonomy}。\n"
                    "返回 JSON，格式为："
                    '{"topic":"主题","confidence":0.0,"tags":["标签1","标签2"]}\n'
                    f"标题：{article.title or ''}\n"
                    f"正文：{text[:3000]}\n"
                )
                payload, raw_text = await invoke_json(llm, config.prompt.analysis_system_prompt, user_prompt)
                state.topic = TopicResult(
                    label=str(payload.get("topic", "社会")),
                    confidence=float(payload.get("confidence", 0.5)),
                    tags=[str(tag) for tag in payload.get("tags", [])],
                )
                state.llm_outputs["topic"] = {"raw": raw_text, "parsed": payload}
                return state
            except Exception as exc:
                state.error(f"topic llm fallback: {exc}")

        # LLM 不可用或失败时，走关键词统计兜底。
        best_topic = "社会"
        best_score = 0
        for topic, keywords in TOPIC_KEYWORDS.items():
            score = sum(text.count(keyword) for keyword in keywords)
            if score > best_score:
                best_topic = topic
                best_score = score
        confidence = min(1.0, 0.2 + best_score * 0.1) if best_score else 0.2
        state.topic = TopicResult(label=best_topic, confidence=confidence, tags=[best_topic])
        state.llm_outputs["topic"] = {"raw": json.dumps({"fallback": True}, ensure_ascii=False)}
        return state

    return node
