from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from news_agent import AgentConfig, NewsRewritingAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="News rewriting agent")
    parser.add_argument("url", nargs="?", help="Article URL")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    parser.add_argument("--stream", action="store_true", help="Run in LangGraph stream mode")
    parser.add_argument("--title", help="Hot topic title for direct text mode")
    parser.add_argument("--content", help="Hot topic content for direct text mode")
    parser.add_argument("--content-file", help="Path to a text file with hot topic content")
    parser.add_argument(
        "--reference-file",
        action="append",
        default=[],
        help="Path to one reference writing sample file. Can be passed multiple times.",
    )
    parser.add_argument("--style-file", help="Path to your own style example file")
    return parser


async def _run(args: argparse.Namespace) -> None:
    agent = NewsRewritingAgent(AgentConfig())
    reference_texts = [_read_text(path) for path in args.reference_file]
    style_example = _read_text(args.style_file) if args.style_file else None

    if args.stream:
        payload = await _run_stream(agent, args, reference_texts, style_example)
    else:
        payload = await _run_once(agent, args, reference_texts, style_example)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    _print_compact(payload)


async def _run_once(
    agent: NewsRewritingAgent,
    args: argparse.Namespace,
    reference_texts: list[str],
    style_example: str | None,
) -> dict:
    if args.title and (args.content or args.content_file):
        content = args.content or _read_text(args.content_file)
        result = await agent.run_from_text(
            title=args.title,
            content=content,
            reference_texts=reference_texts,
            style_example=style_example,
        )
    elif args.url:
        result = await agent.run(
            url=args.url,
            reference_texts=reference_texts,
            style_example=style_example,
        )
    else:
        raise SystemExit("Provide either a URL or --title with --content/--content-file.")

    return result.to_dict()


async def _run_stream(
    agent: NewsRewritingAgent,
    args: argparse.Namespace,
    reference_texts: list[str],
    style_example: str | None,
) -> dict:
    if args.title and (args.content or args.content_file):
        content = args.content or _read_text(args.content_file)
        stream_iter = agent.astream_from_text(
            title=args.title,
            content=content,
            reference_texts=reference_texts,
            style_example=style_example,
        )
    elif args.url:
        stream_iter = agent.astream(
            url=args.url,
            reference_texts=reference_texts,
            style_example=style_example,
        )
    else:
        raise SystemExit("Provide either a URL or --title with --content/--content-file.")

    final_payload: dict = {}
    async for event in stream_iter:
        if event.get("event") == "graph_end":
            final_payload = event.get("result", {}) or {}
    return final_payload


def _print_compact(payload: dict) -> None:
    # 支持 run() 的完整状态字典和 stream 的 graph_end result 两种结构。
    script = payload.get("script", {}) or {}
    topic = payload.get("topic", {}) or {}
    qa = payload.get("qa", {}) or {}

    title = payload.get("title") or script.get("title", "")
    topic_label = payload.get("topic") if isinstance(payload.get("topic"), str) else topic.get("label", "")
    qa_passed = payload.get("qa_passed")
    if qa_passed is None:
        qa_passed = qa.get("passed", False)
    issues = payload.get("issues")
    if issues is None:
        issues = qa.get("issues", [])
    script_text = payload.get("script_text") or script.get("script_text", "")
    rewrite_attempt = payload.get("rewrite_attempt", payload.get("rewrite_attempt", 0))

    print(f"标题: {title}")
    print(f"主题: {topic_label}")
    print(f"质检: {'通过' if qa_passed else '未通过'}")
    print(f"问题: {'；'.join(issues) if issues else ''}")
    print("口播稿:")
    print(script_text)
    print(f"重新尝试次数：{rewrite_attempt}")


def _read_text(path_str: str | None) -> str:
    if not path_str:
        return ""
    return Path(path_str).read_text(encoding="utf-8")


def main() -> None:
    # Windows 下规避 Proactor 事件循环退出时的管道析构告警。
    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
