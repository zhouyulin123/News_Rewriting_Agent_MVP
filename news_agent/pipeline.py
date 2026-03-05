from __future__ import annotations

from collections.abc import Awaitable, Callable

from .models import AgentState

AgentNode = Callable[[AgentState], Awaitable[AgentState]]


class AgentPipeline:
    def __init__(self, nodes: list[tuple[str, AgentNode]]):
        self._nodes = nodes

    async def run(self, state: AgentState) -> AgentState:
        for name, node in self._nodes:
            state.log(f"start:{name}")
            try:
                state = await node(state)
            except Exception as exc:  # pragma: no cover
                state.error(f"{name} failed: {exc}")
                break
            state.log(f"end:{name}")
        return state
