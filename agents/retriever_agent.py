"""
Retriever Agent — Evidence Gathering via Hybrid RAG.

Responsibilities:
  1. Execute hybrid retrieval for each sub-task from the Lead Detective.
  2. Aggregate results across all sub-tasks.
  3. Deduplicate early to avoid wasting Verifier time.
"""

from rich import print
from agents.state import AgentState
from rag.retriever import hybrid_retrieve


def retriever_agent_node(state: AgentState) -> dict:
    """LangGraph node: Retriever agent."""

    sub_tasks = state.get("sub_tasks", [])
    existing_evidence = state.get("evidence", [])
    existing_ids = {e["segment_id"] for e in existing_evidence}

    print(f"\n[bold green][RET] Retriever Agent -- {len(sub_tasks)} sub-tasks[/bold green]")

    all_evidence = list(existing_evidence)  # Carry forward

    for i, task in enumerate(sub_tasks, 1):
        print(f"  [{i}/{len(sub_tasks)}] Searching: {task[:80]}...")

        try:
            results = hybrid_retrieve(task, video_id=state.get("video_id"), top_k=8)

            new_count = 0
            for result in results:
                seg_id = result.get("segment_id", "")
                if seg_id not in existing_ids:
                    all_evidence.append(result)
                    existing_ids.add(seg_id)
                    new_count += 1

            print(f"    -> Found {len(results)} results, {new_count} new")

        except Exception as e:
            print(f"    [red][!] Retrieval error: {e}[/red]")

    print(f"  Total evidence: {len(all_evidence)} segments")

    return {
        "evidence": all_evidence,
        "retriever_notes": (
            f"Retrieved for {len(sub_tasks)} sub-tasks. "
            f"Total evidence: {len(all_evidence)} segments."
        ),
    }
