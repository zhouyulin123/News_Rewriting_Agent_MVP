from __future__ import annotations

"""抓取节点：负责获取网页 HTML。

策略：
1. 先走静态抓取（httpx）。
2. 若静态结果缺失或疑似前端渲染站点，回退到 Playwright。
3. 仅返回 HTML，不在本文件做正文抽取。
"""

import asyncio

from ..config import AgentConfig
from ..models import AgentState, Article

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover
    async_playwright = None


def fetch_article_node(config: AgentConfig):
    """生成抓取节点函数，供 agent.py 注入到 LangGraph。"""

    async def node(state: AgentState) -> AgentState:
        # 文本模式或已具备内容时，不重复抓取。
        if state.article is not None and (state.article.html or state.article.raw_text):
            return state
        article = await fetch_article_html(state.url, config)
        state.article = article
        return state

    return node


async def fetch_article_html(url: str, config: AgentConfig) -> Article:
    """抓取 URL 并返回仅包含 html 的 Article。"""
    html = None

    if config.fetch.enable_http_fetch:
        html = await _fetch_static_html(url, config)

    if config.fetch.enable_playwright and _needs_render(html):
        rendered_html = await _fetch_rendered_html(url, config)
        if rendered_html:
            html = rendered_html

    return Article(url=url, html=html)


async def _fetch_static_html(url: str, config: AgentConfig) -> str | None:
    """静态抓取：适合 SSR 或直接返回正文的页面。"""
    if httpx is None:
        return None

    headers = {"User-Agent": config.fetch.user_agent}
    timeout = config.fetch.timeout_seconds

    for _ in range(config.fetch.max_retries + 1):
        try:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", ""):
                    return None
                return response.text
        except Exception:
            # 简单重试，避免瞬时网络波动导致任务失败。
            await asyncio.sleep(1)
    return None


async def _fetch_rendered_html(url: str, config: AgentConfig) -> str | None:
    """动态渲染抓取：适合 CSR 页面。"""
    if async_playwright is None:
        return None

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=config.fetch.user_agent)
        try:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=config.fetch.render_timeout_seconds * 1000,
            )
            return await page.content()
        finally:
            await browser.close()


def _needs_render(html: str | None) -> bool:
    """根据常见前端框架信号判断是否需要渲染。"""
    if not html:
        return True
    signals = ("__NEXT_DATA__", "data-reactroot", 'id="app"', "window.__NUXT__")
    return any(signal in html for signal in signals)
