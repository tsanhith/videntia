"""
Scribe Agent — Forensic Report Generation.

Responsibilities:
  1. Generate a structured Markdown report from verified evidence.
  2. Ensure every claim cites specific evidence (grounding).
  3. Include emotion analysis, temporal context, and confidence metadata.
"""

import json
from datetime import datetime
from pathlib import Path
from rich import print
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agents.state import AgentState
from config import GROQ_API_KEY, GROQ_MODEL, REPORTS_DIR


# ── LLM client (lazy init) ──────────────────────────────────────────────────
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            temperature=0.3,
        )
    return _llm


# ── Prompts ─────────────────────────────────────────────────────────────────
SCRIBE_SYSTEM = """You are Videntia's Scribe Agent — a forensic report writer.

Generate a structured Markdown report answering the user's query based ONLY on the provided evidence.

CRITICAL RULES FOR ANSWER GROUNDING:
1. Only make claims DIRECTLY supported by the evidence
2. Every factual claim MUST cite a specific segment ID and timestamp
3. Use exact quotes from transcripts when possible
4. If evidence is ambiguous, explicitly state the ambiguity
5. For emotion claims, include both transcript AND visual evidence
6. Flag inferences as "inferred from..." rather than stating as fact
7. If evidence doesn't fully answer the query, state what's missing

REPORT STRUCTURE:
### Executive Summary
(2-3 sentence answer)

### Key Findings
(Bullet points with segment citations)

### Emotional Context
(If emotion-related query — confidence scores)

### Evidence Details
(Per-segment breakdown with timestamps)

### Contradictions
(If any detected)

---
**Metadata**
- Confidence: X%
- Evidence Segments: N
- Iterations: N
- Contradictions: N
"""

SCRIBE_HUMAN = """Query: {query}

Verified Evidence ({count} segments, confidence {confidence:.1%}):

{evidence_text}

Contradictions Found: {contradictions}

Generate a complete forensic report following the structure above.
"""


# ── Helper ──────────────────────────────────────────────────────────────────
def _format_evidence(evidence: list[dict]) -> str:
    """Format evidence for LLM report generation."""
    lines = []
    for i, e in enumerate(evidence, 1):
        metadata = e.get("metadata", {})
        emotions = metadata.get("emotions", [])
        emotion_scores = metadata.get("emotion_scores", {})
        visual_emotions = metadata.get("visual_emotions", [])
        intensity = metadata.get("emotion_intensity", 0)
        avg_conf = metadata.get("avg_emotion_confidence", 0)

        # Format emotion strings with confidence
        emotion_parts = []
        for emo in emotions:
            score = emotion_scores.get(emo, 0)
            emotion_parts.append(f"{emo}({score:.2f})")

        visual_captions = e.get("visual_captions", [])
        visual_text = " | ".join(visual_captions[:2]) if visual_captions else "none"

        lines.append(
            f"Segment {i} ({e.get('segment_id', 'unknown')})\n"
            f"- Time: {e.get('start_sec', 0):.0f}s-{e.get('end_sec', 0):.0f}s\n"
            f"- Rerank Score: {e.get('rerank_score', 0):.4f}\n"
            f"- Transcript: {e.get('transcript', '')[:300]}\n"
            f"- Visual: {visual_text}\n"
            f"- Detected Emotions: {', '.join(emotion_parts) if emotion_parts else 'none'}\n"
            f"- Visual Emotions: {', '.join(visual_emotions) if visual_emotions else 'none'}\n"
            f"- Emotion Intensity: {intensity:.2f}\n"
            f"- Avg Emotion Confidence: {avg_conf:.2f}"
        )
    return "\n\n".join(lines)


# ── Node Function ───────────────────────────────────────────────────────────
def scribe_agent_node(state: AgentState) -> dict:
    """LangGraph node: Scribe agent."""

    query = state["query"]
    verified = state.get("verified_evidence", [])
    confidence = state.get("confidence_score", 0.0)
    contradictions = state.get("contradictions", [])
    iteration = state.get("iteration", 0)

    # Sort by relevance to ensure the best segments are reviewed first
    verified = sorted(verified, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    
    # Limit to top 12 segments to prevent LLM context/rate limit errors
    top_segments = verified[:12]

    print(f"\n[bold magenta]📝 Scribe Agent — Generating report on top {len(top_segments)} segments[/bold magenta]")

    evidence_text = _format_evidence(top_segments)
    contra_text = "\n".join(f"- {c}" for c in contradictions) if contradictions else "None"

    prompt = SCRIBE_HUMAN.format(
        query=query,
        count=len(verified),
        confidence=confidence,
        evidence_text=evidence_text,
        contradictions=contra_text,
    )

    try:
        response = _get_llm().invoke([
            SystemMessage(content=SCRIBE_SYSTEM),
            HumanMessage(content=prompt),
        ])
        report = response.content.strip()
    except Exception as e:
        print(f"  [red]⚠ LLM error: {e}[/red]")
        import traceback
        traceback.print_exc()
        # Fallback: generate a basic report
        report = _fallback_report(query, verified, confidence, contradictions, iteration)

    # Append metadata footer
    report += (
        f"\n\n---\n**Metadata**\n"
        f"- Confidence: {confidence:.2%}\n"
        f"- Evidence Segments: {len(verified)}\n"
        f"- Iterations: {iteration}\n"
        f"- Contradictions: {len(contradictions)}\n"
    )

    # Save report to disk
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"analysis_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  → Saved: {report_path}")

    return {
        "report": report,
        "scribe_notes": f"Report generated ({len(report)} chars), saved to {report_path}",
    }


def _fallback_report(
    query: str,
    evidence: list[dict],
    confidence: float,
    contradictions: list[str],
    iteration: int,
) -> str:
    """Generate a basic report when LLM is unavailable."""
    lines = [
        f"### Executive Summary",
        f"Analysis of query: \"{query}\"",
        f"",
        f"### Key Findings",
    ]

    for i, e in enumerate(evidence[:5], 1):
        seg_id = e.get("segment_id", "unknown")
        transcript = e.get("transcript", "")[:150]
        time_range = f"{e.get('start_sec', 0):.0f}s-{e.get('end_sec', 0):.0f}s"
        lines.append(f"- **Segment {i}** ({seg_id}, {time_range}): \"{transcript}...\"")

    if contradictions:
        lines.append(f"\n### Contradictions")
        for c in contradictions:
            lines.append(f"- {c}")

    return "\n".join(lines)
