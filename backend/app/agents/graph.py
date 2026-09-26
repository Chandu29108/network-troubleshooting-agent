"""
Wires the nodes into a graph:

                        ┌─────────────┐
                 ┌─────>│ diagnostic  │──┐
    ┌────────┐   │      └─────────────┘  │      ┌───────────┐      ┌────────────┐
    │ router │───┤                       ├─────>│ retrieval │─────>│ synthesis  │──> END
    └────────┘   │                       │      └───────────┘      └────────────┘
                 └──────────────────────>┘
                     (general questions skip the tool-calling diagnostic step)

Compiled once at import time and reused across requests — recompiling per
request would add needless latency.
"""
from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    AgentState,
    diagnostic_node,
    retrieval_node,
    route_decision,
    router_node,
    synthesis_node,
)


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("diagnostic", diagnostic_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("synthesis", synthesis_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "diagnostic": "diagnostic",
            "general": "retrieval",
        },
    )
    graph.add_edge("diagnostic", "retrieval")
    graph.add_edge("retrieval", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()


# Compiled once, imported by the API layer.
agent_graph = build_graph()
