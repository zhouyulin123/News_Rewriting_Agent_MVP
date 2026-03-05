from __future__ import annotations

"""News Rewriting Agent 的 LangGraph 编排层。"""

from typing import Any, Optional, TypedDict

from .config import AgentConfig
from .models import AgentState, Article, QAResult, ScriptResult, TopicResult
from .services.cleaner import clean_article_node
from .services.classifier import classify_topic_node
from .services.extractor import extract_article_node
from .services.exporter import export_result_node
from .services.fetcher import fetch_article_node
from .services.qa import qa_check_node
from .services.rewriter import rewrite_script_node

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover
    END = START = StateGraph = None


class AgentGraphState(TypedDict, total=False):
    input_mode: str
    url: str
    created_at: str
    article: Optional[Article]
    topic: TopicResult
    script: ScriptResult
    qa: QAResult
    rewrite_attempt: int
    max_rewrite_attempts: int
    qa_feedback: list[str]
    qa_should_retry: bool
    reference_texts: list[str]
    style_example: Optional[str]
    llm_outputs: dict[str, Any]
    logs: list[str]
    errors: list[str]
    output: dict[str, Any]


class NewsRewritingAgent:
    def __init__(self, config: AgentConfig | None = None):
        if StateGraph is None:
            raise ImportError("langgraph is not installed. Run `pip install -r requirements.txt` first.")
        self.config = config or AgentConfig()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentGraphState)

        builder.add_node("route_input", self._route_input_node)
        builder.add_node("prepare_text", self._prepare_text_node)
        builder.add_node("fetcher", self._wrap_node("fetcher", fetch_article_node(self.config)))
        builder.add_node("extractor", self._wrap_node("extractor", extract_article_node(self.config)))
        builder.add_node("cleaner", self._wrap_node("cleaner", clean_article_node(self.config)))
        builder.add_node("classifier", self._wrap_node("classifier", classify_topic_node(self.config)))
        builder.add_node("rewriter", self._wrap_node("rewriter", rewrite_script_node(self.config)))
        builder.add_node("qa", self._wrap_node("qa", qa_check_node(self.config)))
        builder.add_node("qa_decision", self._qa_decision_node)
        builder.add_node("exporter", self._wrap_node("exporter", export_result_node(self.config)))

        builder.add_edge(START, "route_input")
        builder.add_conditional_edges(
            "route_input",
            self._route_input_mode,
            {"url": "fetcher", "text": "prepare_text"},
        )
        builder.add_edge("prepare_text", "cleaner")
        builder.add_edge("fetcher", "extractor")
        builder.add_edge("extractor", "cleaner")
        builder.add_edge("cleaner", "classifier")
        builder.add_edge("classifier", "rewriter")
        builder.add_edge("rewriter", "qa")
        builder.add_edge("qa", "qa_decision")
        builder.add_conditional_edges(
            "qa_decision",
            self._qa_route,
            {"rewrite": "rewriter", "export": "exporter"},
        )
        builder.add_edge("exporter", END)
        return builder.compile()

    def _wrap_node(self, node_name: str, node_func):
        async def runner(state_dict: AgentGraphState) -> AgentGraphState:
            state = _from_graph_state(state_dict)
            state.log(f"start:{node_name}")
            try:
                updated = await node_func(state)
            except Exception as exc:  # pragma: no cover
                state.error(f"{node_name} failed: {exc}")
                state.log(f"end:{node_name}")
                return _to_graph_state(state)
            updated.log(f"end:{node_name}")
            return _to_graph_state(updated)

        return runner

    async def _route_input_node(self, state_dict: AgentGraphState) -> AgentGraphState:
        state = _from_graph_state(state_dict)
        mode = self._route_input_mode(state_dict)
        state.log(f"route_input:{mode}")
        return _to_graph_state(state)

    def _route_input_mode(self, state_dict: AgentGraphState) -> str:
        mode = state_dict.get("input_mode", "url")
        return "text" if mode == "text" else "url"

    async def _prepare_text_node(self, state_dict: AgentGraphState) -> AgentGraphState:
        state = _from_graph_state(state_dict)
        state.log("start:prepare_text")
        article = state.article
        if article is None:
            state.error("prepare_text failed: text mode requires article content")
            state.log("end:prepare_text")
            return _to_graph_state(state)
        if not article.raw_text and article.clean_text:
            article.raw_text = article.clean_text
        if not article.paragraphs and article.clean_text:
            article.paragraphs = [line.strip() for line in article.clean_text.splitlines() if line.strip()]
        state.log("end:prepare_text")
        return _to_graph_state(state)

    async def _qa_decision_node(self, state_dict: AgentGraphState) -> AgentGraphState:
        """QA 未通过时记录原因并累加重写次数。"""
        state = _from_graph_state(state_dict)
        state.log("start:qa_decision")
        if not state.qa.passed:
            state.qa_feedback = list(state.qa.issues)
            if state.rewrite_attempt < state.max_rewrite_attempts:
                state.rewrite_attempt += 1
                state.qa_should_retry = True
                state.log(
                    f"qa_decision:retry_rewrite attempt={state.rewrite_attempt}/{state.max_rewrite_attempts} "
                    f"reasons={state.qa_feedback}"
                )
            else:
                state.qa_should_retry = False
                state.log(
                    f"qa_decision:give_up_rewrite attempt={state.rewrite_attempt}/{state.max_rewrite_attempts} "
                    f"reasons={state.qa_feedback}"
                )
        else:
            state.qa_feedback = []
            state.qa_should_retry = False
            state.log("qa_decision:pass")
        state.log("end:qa_decision")
        return _to_graph_state(state)

    def _qa_route(self, state_dict: AgentGraphState) -> str:
        """决定从 qa_decision 去 rewriter 还是 exporter。"""
        state = _from_graph_state(state_dict)
        if state.qa_should_retry:
            return "rewrite"
        return "export"

    async def run(
        self,
        url: str,
        reference_texts: list[str] | None = None,
        style_example: str | None = None,
    ) -> AgentState:
        initial_state = AgentState(
            input_mode="url",
            url=url,
            reference_texts=reference_texts or [],
            style_example=style_example,
            rewrite_attempt=0,
            max_rewrite_attempts=self.config.rewrite.max_rewrite_attempts,
        )
        result = await self.graph.ainvoke(_to_graph_state(initial_state))
        return _from_graph_state(result)

    async def run_from_text(
        self,
        title: str,
        content: str,
        reference_texts: list[str] | None = None,
        style_example: str | None = None,
        url: str = "manual://input",
        source: str = "manual",
    ) -> AgentState:
        paragraphs = [line.strip() for line in content.splitlines() if line.strip()]
        initial_state = AgentState(
            input_mode="text",
            url=url,
            article=Article(
                url=url,
                title=title,
                source=source,
                raw_text=content,
                clean_text=content,
                paragraphs=paragraphs,
            ),
            reference_texts=reference_texts or [],
            style_example=style_example,
            rewrite_attempt=0,
            max_rewrite_attempts=self.config.rewrite.max_rewrite_attempts,
        )
        result = await self.graph.ainvoke(_to_graph_state(initial_state))
        return _from_graph_state(result)

    async def astream(
        self,
        url: str,
        reference_texts: list[str] | None = None,
        style_example: str | None = None,
    ):
        initial_state = AgentState(
            input_mode="url",
            url=url,
            reference_texts=reference_texts or [],
            style_example=style_example,
            rewrite_attempt=0,
            max_rewrite_attempts=self.config.rewrite.max_rewrite_attempts,
        )
        async for event in self._astream_events(_to_graph_state(initial_state)):
            yield event

    async def astream_from_text(
        self,
        title: str,
        content: str,
        reference_texts: list[str] | None = None,
        style_example: str | None = None,
        url: str = "manual://input",
        source: str = "manual",
    ):
        paragraphs = [line.strip() for line in content.splitlines() if line.strip()]
        initial_state = AgentState(
            input_mode="text",
            url=url,
            article=Article(
                url=url,
                title=title,
                source=source,
                raw_text=content,
                clean_text=content,
                paragraphs=paragraphs,
            ),
            reference_texts=reference_texts or [],
            style_example=style_example,
            rewrite_attempt=0,
            max_rewrite_attempts=self.config.rewrite.max_rewrite_attempts,
        )
        async for event in self._astream_events(_to_graph_state(initial_state)):
            yield event

    async def _astream_events(self, initial_state: AgentGraphState):
        current: AgentGraphState = dict(initial_state)
        async for chunk in self.graph.astream(initial_state, stream_mode="updates"):
            if not isinstance(chunk, dict):
                continue
            for node_name, update in chunk.items():
                prev_log_len = len(current.get("logs", []))
                prev_err_len = len(current.get("errors", []))
                if isinstance(update, dict):
                    current.update(update)
                else:
                    current[node_name] = update
                new_logs = current.get("logs", [])[prev_log_len:]
                new_errors = current.get("errors", [])[prev_err_len:]
                detail = self._build_stream_detail(node_name, current)
                yield {
                    "event": "node_end",
                    "node": node_name,
                    "new_logs": new_logs,
                    "new_errors": new_errors,
                    "detail": detail,
                }

        final_state = _from_graph_state(current)
        yield {
            "event": "graph_end",
            "node": "__end__",
            "new_logs": [],
            "new_errors": final_state.errors,
            "result": {
                "title": final_state.script.title,
                "topic": final_state.topic.label,
                "qa_passed": final_state.qa.passed,
                "issues": final_state.qa.issues,
                "script_text": final_state.script.script_text,
                "rewrite_attempt": final_state.rewrite_attempt,
                "qa_feedback": final_state.qa_feedback,
                "qa_should_retry": final_state.qa_should_retry,
            },
        }

    def _build_stream_detail(self, node_name: str, current: AgentGraphState) -> dict[str, Any] | None:
        """为关键节点构造可读的流式详情。"""
        if node_name == "rewriter":
            script = current.get("script")
            script_title = getattr(script, "title", "") if script is not None else ""
            script_text = getattr(script, "script_text", "") if script is not None else ""
            llm_outputs = current.get("llm_outputs", {})
            rewrite_raw = None
            if isinstance(llm_outputs, dict):
                rewrite_payload = llm_outputs.get("rewrite")
                if isinstance(rewrite_payload, dict):
                    rewrite_raw = rewrite_payload.get("raw")
            return {
                "rewrite_attempt": current.get("rewrite_attempt", 0),
                "title": script_title,
                "script_text": script_text,
                "llm_raw": rewrite_raw,
            }

        if node_name == "qa":
            qa = current.get("qa")
            passed = getattr(qa, "passed", True) if qa is not None else True
            issues = getattr(qa, "issues", []) if qa is not None else []
            return {
                "passed": passed,
                "issues": issues,
            }

        if node_name == "qa_decision":
            return {
                "rewrite_attempt": current.get("rewrite_attempt", 0),
                "max_rewrite_attempts": current.get("max_rewrite_attempts", 0),
                "qa_feedback": current.get("qa_feedback", []),
                "qa_should_retry": current.get("qa_should_retry", False),
            }

        return None


def _to_graph_state(state: AgentState) -> AgentGraphState:
    return {
        "input_mode": state.input_mode,
        "url": state.url,
        "created_at": state.created_at,
        "article": state.article,
        "topic": state.topic,
        "script": state.script,
        "qa": state.qa,
        "rewrite_attempt": state.rewrite_attempt,
        "max_rewrite_attempts": state.max_rewrite_attempts,
        "qa_feedback": state.qa_feedback,
        "qa_should_retry": state.qa_should_retry,
        "reference_texts": state.reference_texts,
        "style_example": state.style_example,
        "llm_outputs": state.llm_outputs,
        "logs": state.logs,
        "errors": state.errors,
        "output": state.output,
    }


def _from_graph_state(state: AgentGraphState) -> AgentState:
    return AgentState(
        input_mode=state.get("input_mode", "url"),
        url=state.get("url", ""),
        created_at=state.get("created_at", ""),
        article=state.get("article"),
        topic=state.get("topic") or TopicResult(),
        script=state.get("script") or ScriptResult(),
        qa=state.get("qa") or QAResult(),
        rewrite_attempt=state.get("rewrite_attempt", 0),
        max_rewrite_attempts=state.get("max_rewrite_attempts", 2),
        qa_feedback=state.get("qa_feedback", []),
        qa_should_retry=state.get("qa_should_retry", False),
        reference_texts=state.get("reference_texts", []),
        style_example=state.get("style_example"),
        llm_outputs=state.get("llm_outputs", {}),
        logs=state.get("logs", []),
        errors=state.get("errors", []),
        output=state.get("output", {}),
    )
