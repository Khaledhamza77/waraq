from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from waraq.navigation.nodes import classify_and_normalize, navigate_level
from waraq.navigation.state import NavigationState


def _route_classify(state: NavigationState) -> str:
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

    builder.add_node("classify_and_normalize", classify_and_normalize)
    builder.add_node("navigate_level", navigate_level)

    builder.add_edge(START, "classify_and_normalize")
    builder.add_conditional_edges(
        "classify_and_normalize",
        _route_classify,
        {END: END, "navigate_level": "navigate_level"},
    )
    builder.add_conditional_edges(
        "navigate_level",
        _route_navigate,
        {END: END, "navigate_level": "navigate_level"},
    )

    return builder.compile()
