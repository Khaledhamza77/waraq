from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from waraq.navigation.nodes import check_intent, navigate_level, normalize_query
from waraq.navigation.state import NavigationState


def _route_intent(state: NavigationState) -> str:
    if state.get("status") in ("rejected", "greeting"):
        return END
    return "navigate_level"


def _route_navigate(state: NavigationState) -> str:
    if state.get("status") == "navigating":
        return "navigate_level"
    return END


def build_graph():
    """Build and compile the navigation graph.

    At invocation time, pass index and markdown_dir via RunnableConfig:
        graph.invoke(state, config={"configurable": {"index": ..., "markdown_dir": ...}})
    """
    builder = StateGraph(NavigationState)

    builder.add_node("normalize_query", normalize_query)
    builder.add_node("check_intent", check_intent)
    builder.add_node("navigate_level", navigate_level)

    builder.add_edge(START, "normalize_query")
    builder.add_edge("normalize_query", "check_intent")
    builder.add_conditional_edges(
        "check_intent",
        _route_intent,
        {END: END, "navigate_level": "navigate_level"},
    )
    builder.add_conditional_edges(
        "navigate_level",
        _route_navigate,
        {END: END, "navigate_level": "navigate_level"},
    )

    return builder.compile()
