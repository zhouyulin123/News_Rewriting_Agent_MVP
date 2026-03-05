from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_BASE_URL"] = ""

@dataclass
class FetchConfig:
    timeout_seconds: int = 30
    render_timeout_seconds: int = 60
    max_retries: int = 2
    min_content_length: int = 400
    enable_http_fetch: bool = True
    enable_playwright: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    )


@dataclass
class CleanConfig:
    min_paragraph_length: int = 10
    noise_keywords: list[str] = field(
        default_factory=lambda: [
            "责任编辑",
            "免责声明",
            "相关阅读",
            "延伸阅读",
            "推荐阅读",
            "点击查看",
            "点击这里",
            "更多精彩内容",
            "版权声明",
            "广告",
            "订阅",
            "扫码",
            "本文来自",
        ]
    )


@dataclass
class LLMConfig:
    enabled: bool = True
    model: str = ""
    base_url: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    temperature: float = 0.4
    max_retries: int = 2
    timeout_seconds: int = 120


@dataclass
class RewriteConfig:
    tone: str = "口语化新闻解读"
    min_chars: int = 300
    max_chars: int = 600
    max_rewrite_attempts: int = 2
    include_source_line: bool = True
    include_disclaimer: bool = False


@dataclass
class PromptConfig:
    topic_taxonomy: list[str] = field(
        default_factory=lambda: [
            "体育",
            "科技",
            "国际",
            "财经",
            "娱乐",
            "社会",
            "教育",
            "健康",
            "本地",
            "军事",
            "电商",
            "汽车",
            "家居",
            "数码",
        ]
    )
    analysis_system_prompt: str = (
        "你是热点信息解析助手。"
        "你需要从标题和正文中提炼适合短视频口播写作的结构化信息。"
        "只输出 JSON，不要输出解释，不要输出 markdown。"
    )
    rewrite_system_prompt: str = (
        "你是中文短视频口播文案写手，擅长把热点信息改写成自然、口语化、可直接播报的稿子。"
        "请遵守："
        "1) 明确主题，聚焦商品/品牌/消费话题；"
        "2) 开场有悬念；"
        "3) 中间讲清核心信息；"
        "4) 自然延伸相关 query；"
        "5) 字数控制在 300~500；"
        "6) 语气口语化；"
        "7) 不编造事实；"
        "8) 只输出最终文案。"
    )
    built_in_examples: list[str] = field(
        default_factory=lambda: [
            "示例：苹果15改用USB-C，围绕充电、传输、扩展能力做口语化讲解。",
            "示例：松木VS橡胶木，围绕材质差异和选购建议做口语化对比。",
        ]
    )


@dataclass
class ExportConfig:
    output_dir: Path | None = None
    write_json: bool = False
    write_markdown: bool = False


@dataclass
class AgentConfig:
    fetch: FetchConfig = field(default_factory=FetchConfig)
    clean: CleanConfig = field(default_factory=CleanConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rewrite: RewriteConfig = field(default_factory=RewriteConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
