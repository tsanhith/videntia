"""
Videntia Agent Framework
Multi-agent system for forensic video intelligence.
"""

from agents.state import AgentState

__all__ = [
    "AgentState",
]


def _lazy_imports():
    """Lazy imports for agent node functions (require Groq API etc.)."""
    from agents.lead_detective import lead_detective_node
    from agents.retriever_agent import retriever_agent_node
    from agents.verifier_agent import verifier_agent_node
    from agents.scribe_agent import scribe_agent_node
    return lead_detective_node, retriever_agent_node, verifier_agent_node, scribe_agent_node
