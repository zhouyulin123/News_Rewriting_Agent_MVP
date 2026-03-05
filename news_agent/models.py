from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Article:
    """文章对象：抓取、提取、清洗阶段共享的数据载体。"""

    url: str
    title: str | None = None
    author: str | None = None
    publish_time: str | None = None
    source: str | None = None
    html: str | None = None
    raw_text: str | None = None
    clean_text: str | None = None
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class TopicResult:
    """主题分类结果。"""

    label: str = ""
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class ScriptResult:
    """最终口播文案结果。"""

    title: str = ""
    script_text: str = ""
    segments: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)


@dataclass
class QAResult:
    """质检结果。"""

    passed: bool = True
    issues: list[str] = field(default_factory=list)


@dataclass
class AgentState:
    """全流程状态对象。"""

    url: str
    input_mode: str = "url"  # "url": 抓网页, "text": 直接用外部文本
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # 核心产物
    article: Article | None = None
    topic: TopicResult = field(default_factory=TopicResult)
    script: ScriptResult = field(default_factory=ScriptResult)
    qa: QAResult = field(default_factory=QAResult)

    # QA -> Rewriter 反馈闭环字段
    rewrite_attempt: int = 0
    max_rewrite_attempts: int = 2
    qa_feedback: list[str] = field(default_factory=list)
    qa_should_retry: bool = False

    # LLM 输入上下文
    reference_texts: list[str] = field(default_factory=list)
    style_example: str | None = None

    # 观测与调试
    llm_outputs: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        self.logs.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
