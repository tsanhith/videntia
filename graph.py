"""
LangGraph Workflow — Multi-Agent State Graph.

Defines the 4-node agent graph with conditional edges:
  detective → retriever → verifier → (loop or scribe → END)
"""

from langgraph.graph import StateGraph, END

from agents.state import AgentState
from agents.lead_detective import lead_detective_node
from agents.retriever_agent import retriever_agent_node
from agents.verifier_agent import verifier_agent_node
from agents.scribe_agent import scribe_agent_node
from config import MIN_CONFIDENCE


# ── Routing Logic ───────────────────────────────────────────────────────────
def should_continue(state: AgentState) -> str:
    """
    Conditional edge: decide the next node after detective or verifier.

    Returns 'retriever' to gather more evidence, or 'scribe' to
    generate the final report.
    """
    confidence = state.get("confidence_score", 0.0)
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 5)
    verified = state.get("verified_evidence", [])

    # Confidence threshold met → generate report
    if confidence >= MIN_CONFIDENCE:
        return "scribe"

    # Max iterations reached → generate report with what we have
    if iteration >= max_iter:
        return "scribe"

    # Emergency exit: no evidence after 2+ iterations
    if iteration >= 2 and len(verified) == 0:
        return "scribe"

    # Otherwise, keep investigating
    return "retriever"


# ── Graph Construction ──────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent workflow."""

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("detective", lead_detective_node)
    graph.add_node("retriever", retriever_agent_node)
    graph.add_node("verifier", verifier_agent_node)
    graph.add_node("scribe", scribe_agent_node)

    # Set entry point
    graph.set_entry_point("detective")

    # Edges:
    #   detective → (retriever | scribe)    via should_continue
    #   retriever → verifier                always
    #   verifier  → (detective | scribe)    via should_continue
    #   scribe    → END                     always

    graph.add_conditional_edges(
        "detective",
        should_continue,
        {
            "retriever": "retriever",
            "scribe": "scribe",
        },
    )

    graph.add_edge("retriever", "verifier")

    graph.add_conditional_edges(
        "verifier",
        should_continue,
        {
            "retriever": "detective",  # Loop back via detective for re-decomposition
            "scribe": "scribe",
        },
    )

    graph.add_edge("scribe", END)

    return graph


# ── Compiled Workflow (importable singleton) ────────────────────────────────
workflow = build_graph().compile()
