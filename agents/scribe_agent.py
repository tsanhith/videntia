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
SCRIBE_SYSTEM = """You are Videntia's Scribe Agent — a forensic report writer for video intelligence.

Your job is to DIRECTLY ANSWER the user's query using the evidence provided, like a journalist writing a news summary.

CRITICAL RULES:
1. START the Executive Summary by directly answering the query in plain English — do NOT just restate the query.
2. Key Findings must be actual insights, quotes, and facts — NOT a list of segment IDs.
3. Use exact quotes from transcripts. Cite ONLY the timestamp (e.g. "2:10–2:20"), not the full segment ID.
4. Write for a human reader — short, clear sentences.
5. If the evidence doesn't answer the query, say so clearly in the summary.
6. Never repeat the query as the summary. Never list segment IDs as findings.

REPORT STRUCTURE:
### Executive Summary
(2-3 sentences directly answering the query)

### Key Findings
(Bullet points — real facts/quotes from the video with timestamps)

### Emotional Context
(What emotions were detected and when — only if relevant)

### Evidence Details
(Per-segment breakdown: timestamp | key quote)

### Contradictions
(Any conflicting information found)
"""

SCRIBE_HUMAN = """Query: "{query}"

Evidence from the video ({count} segments, confidence {confidence:.1%}):

{evidence_text}

Contradictions Found: {contradictions}

Write a report that DIRECTLY ANSWERS the query above. The Executive Summary must answer the question in plain English. Key Findings must contain real quotes and facts from the transcripts above — not segment IDs.
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

        start = e.get('start_sec', 0)
        end = e.get('end_sec', 0)
        start_fmt = f"{int(start)//60}:{int(start)%60:02d}"
        end_fmt = f"{int(end)//60}:{int(end)%60:02d}"

        lines.append(
            f"Segment {i} (Time: {start_fmt}–{end_fmt})\n"
            f"- Transcript: {e.get('transcript', '')[:300]}\n"
            f"- Detected Emotions: {', '.join(emotion_parts) if emotion_parts else 'none'}\n"
            f"- Emotion Intensity: {intensity:.2f} | Avg Confidence: {avg_conf:.2f}"
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

    print(f"\n[bold magenta][SCR] Scribe Agent -- Generating report on top {len(top_segments)} segments[/bold magenta]")

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
        print(f"  [red][!] LLM error: {e}[/red]")
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
    print(f"  -> Saved: {report_path}")

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
    """Generate a readable report from evidence when LLM is unavailable."""
    top = sorted(evidence, key=lambda x: x.get("rerank_score", 0), reverse=True)[:8]

    # Find the segment whose transcript best overlaps with query keywords
    query_words = set(query.lower().split())
    stop = {"the", "a", "an", "is", "are", "was", "what", "how", "who", "did", "about", "and", "or", "in", "of", "to"}
    query_words -= stop

    best = max(
        top,
        key=lambda e: sum(1 for w in query_words if w in e.get("transcript", "").lower()),
        default=top[0] if top else {},
    )

    best_start = best.get("start_sec", 0)
    best_fmt = f"{int(best_start)//60}:{int(best_start)%60:02d}"
    best_transcript = best.get("transcript", "").strip()

    findings = []
    for e in top:
        start = e.get("start_sec", 0)
        end = e.get("end_sec", 0)
        start_fmt = f"{int(start)//60}:{int(start)%60:02d}"
        end_fmt = f"{int(end)//60}:{int(end)%60:02d}"
        transcript = e.get("transcript", "").strip()
        if transcript:
            findings.append(f"- **{start_fmt}\u2013{end_fmt}:** \"{transcript}\"")

    findings_text = "\n".join(findings) if findings else "- No transcript evidence found."

    lines = [
        "### Executive Summary",
        f"The video addresses: *\"{query}\"*",
        f"",
        f"The most relevant moment is at **{best_fmt}**: \"{best_transcript[:250]}\"",
        f"",
        "### Key Findings",
        findings_text,
        f"",
        "### Contradictions",
        "\n".join(f"- {c}" for c in contradictions) if contradictions else "No contradictions detected.",
    ]

    return "\n".join(lines)
