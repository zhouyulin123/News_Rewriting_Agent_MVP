from __future__ import annotations

"""正文抽取节点：把 HTML 转成正文与元数据。"""

from urllib.parse import urlparse

from ..config import AgentConfig
from ..models import AgentState

try:
    import trafilatura
except ImportError:  # pragma: no cover
    trafilatura = None


def extract_article_node(config: AgentConfig):
    """生成正文抽取节点函数。"""

    async def node(state: AgentState) -> AgentState:
        article = state.article
        if article is None:
            state.error("extract skipped: missing article")
            return state
        # 已有 raw_text 时跳过，避免重复抽取。
        if article.raw_text:
            return state
        if not article.html:
            state.error("extract skipped: missing html")
            return state
        if trafilatura is None:
            state.error("extract skipped: trafilatura is not installed")
            return state

        article.raw_text = trafilatura.extract(
            article.html,
            url=article.url,
            include_comments=False,
            include_tables=False,
        )

        # 同步补齐标题、作者、发布时间、站点来源。
        metadata = trafilatura.extract_metadata(article.html, default_url=article.url)
        parsed = urlparse(article.url)
        article.title = metadata.title if metadata and metadata.title else article.title
        article.author = metadata.author if metadata and metadata.author else article.author
        article.publish_time = metadata.date if metadata and metadata.date else article.publish_time
        article.source = metadata.sitename if metadata and metadata.sitename else article.source or parsed.netloc
        return state

    return node
