"""
Lead Detective Agent — Query Orchestrator & Loop Controller.

Responsibilities:
  1. Decompose complex queries into 2–5 concrete sub-tasks.
  2. Decide whether further investigation is needed based on confidence.
  3. Control loop termination (max iterations or confidence threshold).
"""

import json
from rich import print
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agents.state import AgentState
from config import GROQ_API_KEY, GROQ_MODEL, MIN_CONFIDENCE


# ── LLM client (lazy init) ──────────────────────────────────────────────────
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            temperature=0.1,
        )
    return _llm


# ── Prompts ─────────────────────────────────────────────────────────────────
DETECTIVE_SYSTEM = """You are Videntia's Lead Detective coordinating a forensic video investigation.

Your role:
- Decompose complex questions into 2-5 concrete, actionable sub-tasks
- Each sub-task should target a specific piece of evidence
- Consider temporal, emotional, and speaker dimensions when relevant

RULES:
1. Always output valid JSON matching the schema below
2. Generate 2-5 sub-tasks only (never more)
3. Sub-tasks must be specific and searchable
4. If previous evidence exists, refine the sub-tasks to fill gaps

Output JSON schema:
{
  "decision": "INVESTIGATE" | "CONCLUDE",
  "sub_tasks": ["task1", "task2", ...],
  "reasoning": "Brief explanation of your strategy"
}
"""

DETECTIVE_HUMAN = """Query: {query}

Current Status:
- Iteration: {iteration} / {max_iterations}
- Evidence collected: {evidence_count} segments
- Verified evidence: {verified_count} segments
- Confidence: {confidence:.1%}
- Contradictions: {contradiction_count}

Previous Sub-Tasks: {prev_tasks}

Instructions:
- If confidence >= 75% OR iteration >= max: set decision = "CONCLUDE"
- If confidence < 75% AND iteration < max: set decision = "INVESTIGATE" and provide sub_tasks
- If iterating again, refine sub-tasks based on gaps in evidence
"""


# ── Node Function ───────────────────────────────────────────────────────────
def lead_detective_node(state: AgentState) -> dict:
    """LangGraph node: Lead Detective agent."""

    query = state["query"]
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 5)
    evidence = state.get("evidence", [])
    verified = state.get("verified_evidence", [])
    confidence = state.get("confidence_score", 0.0)
    contradictions = state.get("contradictions", [])
    prev_tasks = state.get("sub_tasks", [])

    print(f"\n[bold blue]🔍 Lead Detective — Iteration {iteration}[/bold blue]")

    # ── Fast-path: already above threshold or max iterations ────────────
    if confidence >= MIN_CONFIDENCE or iteration >= max_iter:
        print(f"  → Concluding (confidence={confidence:.1%}, iter={iteration})")
        return {
            "detective_notes": f"Concluding at iteration {iteration}, confidence {confidence:.1%}",
            "sub_tasks": prev_tasks,
        }

    # ── Ask LLM to decompose ────────────────────────────────────────────
    prompt = DETECTIVE_HUMAN.format(
        query=query,
        iteration=iteration,
        max_iterations=max_iter,
        evidence_count=len(evidence),
        verified_count=len(verified),
        confidence=confidence,
        contradiction_count=len(contradictions),
        prev_tasks=json.dumps(prev_tasks) if prev_tasks else "None (first iteration)",
    )

    try:
        response = _get_llm().invoke([
            SystemMessage(content=DETECTIVE_SYSTEM),
            HumanMessage(content=prompt),
        ])

        # Parse JSON from response
        text = response.content.strip()
        # Handle markdown code blocks
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)
        sub_tasks = result.get("sub_tasks", [])[:5]  # Cap at 5
        reasoning = result.get("reasoning", "")

        print(f"  → Strategy: {reasoning}")
        for i, task in enumerate(sub_tasks, 1):
            print(f"    {i}. {task}")

        return {
            "sub_tasks": sub_tasks,
            "detective_notes": f"Iteration {iteration}: {reasoning}",
            "iteration": iteration + 1,
        }

    except Exception as e:
        print(f"  [red]⚠ LLM error: {e}[/red]")
        # Fallback: use query directly as single sub-task
        return {
            "sub_tasks": [query],
            "detective_notes": f"Fallback to direct query (LLM error: {e})",
            "iteration": iteration + 1,
        }
