"""
Verifier Agent — Quality Assurance & Contradiction Detection.

Responsibilities:
  1. Check relevance of each evidence segment to the query.
  2. Enforce evidence diversity (deduplicate by segment_id, keep best score).
  3. Detect contradictions between segments.
  4. Calculate diversity-adjusted confidence score.
"""

import json
from rich import print
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agents.state import AgentState
from config import GROQ_API_KEY, GROQ_MODEL


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
VERIFIER_SYSTEM = """You are Videntia's Verifier Agent responsible for evidence quality control.

Your tasks:
1. Evaluate how well the evidence answers the query
2. Identify any contradictions between evidence segments
3. Assign a confidence score (0.0 to 1.0)

Output valid JSON:
{
  "confidence": 0.0-1.0,
  "contradictions": ["contradiction 1", ...],
  "reasoning": "Brief assessment of evidence quality"
}
"""

VERIFIER_HUMAN = """Query: {query}

Evidence Segments ({count} total, {unique_count} unique):
{evidence_text}

Evaluate:
1. Does the evidence sufficiently answer the query?
2. Are there contradictions between segments?
3. What is your confidence level (0.0-1.0)?
"""


# ── Helper Functions ────────────────────────────────────────────────────────
def _enforce_diversity(evidence: list[dict]) -> list[dict]:
    """Keep only the highest-scored instance of each segment_id."""
    unique = {}
    for e in evidence:
        seg_id = e.get("segment_id", "")
        score = e.get("rerank_score", 0.0)

        if seg_id not in unique or score > unique[seg_id].get("rerank_score", 0.0):
            unique[seg_id] = e

    return list(unique.values())


def _format_evidence_for_llm(evidence: list[dict], max_segments: int = 10) -> str:
    """Format evidence for LLM consumption."""
    lines = []
    for i, e in enumerate(evidence[:max_segments], 1):
        transcript = e.get("transcript", "")[:200]
        emotions = e.get("metadata", {}).get("emotions", [])
        time_range = f"{e.get('start_sec', 0):.0f}s-{e.get('end_sec', 0):.0f}s"
        score = e.get("rerank_score", 0.0)

        lines.append(
            f"Segment {i} ({e.get('segment_id', 'unknown')})\n"
            f"  Time: {time_range} | Score: {score:.4f}\n"
            f"  Transcript: {transcript}\n"
            f"  Emotions: {', '.join(emotions) if emotions else 'none'}"
        )
    return "\n\n".join(lines)


def _adjusted_confidence(
    base_confidence: float,
    unique_count: int,
    total_count: int,
    avg_rerank: float,
    iteration: int,
) -> float:
    """
    Compute diversity-adjusted confidence.

    Formula:
        diversity_factor = unique / total
        adjusted = base × (0.7 + 0.3 × diversity_factor)
        Penalize by iteration (-5% each loop)
    """
    if total_count == 0:
        return 0.0

    diversity = unique_count / max(1, total_count)
    iter_penalty = max(0.0, 1.0 - 0.05 * iteration)

    weighted = (
        0.4 * base_confidence
        + 0.3 * diversity
        + 0.2 * min(1.0, avg_rerank)
        + 0.1 * iter_penalty
    )
    return round(min(1.0, max(0.0, weighted)), 4)


# ── Node Function ───────────────────────────────────────────────────────────
def verifier_agent_node(state: AgentState) -> dict:
    """LangGraph node: Verifier agent."""

    query = state["query"]
    raw_evidence = state.get("evidence", [])
    iteration = state.get("iteration", 0)

    print(f"\n[bold yellow]✓ Verifier Agent — {len(raw_evidence)} raw segments[/bold yellow]")

    # ── Step 1: Enforce diversity ───────────────────────────────────────
    verified = _enforce_diversity(raw_evidence)
    unique_count = len(verified)
    total_count = len(raw_evidence)
    print(f"  Unique segments: {unique_count}/{total_count}")

    # ── Step 2: Calculate average rerank score ──────────────────────────
    scores = [e.get("rerank_score", 0.0) for e in verified]
    avg_rerank = sum(scores) / max(1, len(scores))

    # ── Step 3: LLM quality assessment ──────────────────────────────────
    evidence_text = _format_evidence_for_llm(verified)
    prompt = VERIFIER_HUMAN.format(
        query=query,
        count=total_count,
        unique_count=unique_count,
        evidence_text=evidence_text,
    )

    base_confidence = 0.5  # Default
    contradictions = []

    try:
        response = _get_llm().invoke([
            SystemMessage(content=VERIFIER_SYSTEM),
            HumanMessage(content=prompt),
        ])

        text = response.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)
        base_confidence = float(result.get("confidence", 0.5))
        contradictions = result.get("contradictions", [])
        reasoning = result.get("reasoning", "")

        print(f"  LLM confidence: {base_confidence:.1%}")
        print(f"  Reasoning: {reasoning}")

    except Exception as e:
        print(f"  [red]⚠ LLM error (using heuristic): {e}[/red]")
        # Heuristic fallback
        if unique_count >= 3:
            base_confidence = 0.7
        elif unique_count >= 1:
            base_confidence = 0.5

    # ── Step 4: Compute adjusted confidence ─────────────────────────────
    confidence = _adjusted_confidence(
        base_confidence, unique_count, total_count, avg_rerank, iteration
    )

    if contradictions:
        print(f"  ⚠ Contradictions: {len(contradictions)}")
        for c in contradictions:
            print(f"    - {c}")

    print(f"  [bold]Final confidence: {confidence:.1%}[/bold]")

    return {
        "verified_evidence": verified,
        "confidence_score": confidence,
        "contradictions": contradictions,
        "verifier_notes": (
            f"Verified {unique_count}/{total_count} unique segments. "
            f"Confidence: {confidence:.1%}. "
            f"Contradictions: {len(contradictions)}."
        ),
    }
