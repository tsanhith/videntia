"""
Videntia — CLI Entry Point.

Usage:
    python main.py "Who showed surprise when hearing about 200 pounds?"
    python main.py "What emotions were detected?" --max-iter 3
"""

import sys
import argparse
from datetime import datetime

from rich import print
from rich.console import Console

from agents.state import AgentState
from graph import workflow
from config import MAX_ITERATIONS

console = Console()


def analyze_video(query: str, max_iterations: int = MAX_ITERATIONS, video_id: str | None = None) -> dict | None:
    """
    Run the multi-agent analysis workflow.

    Parameters
    ----------
    query : str
        Natural language question about the video.
    max_iterations : int
        Maximum number of investigation loops.

    Returns
    -------
    dict or None
        Final AgentState with report, evidence, and metadata.
        None if the analysis fails.
    """
    console.print(f"\n[bold cyan]{'=' * 80}[/bold cyan]")
    console.print(f"[bold cyan]VIDENTIA — Forensic Video Analysis[/bold cyan]")
    console.print(f"[bold cyan]{'=' * 80}[/bold cyan]")
    console.print(f"Query: {query}")
    console.print(f"Max iterations: {max_iterations}")
    console.print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print()

    # Build initial state
    initial_state: AgentState = {
        "query": query,
        "video_id": video_id,
        "iteration": 0,
        "max_iterations": max_iterations,
        "sub_tasks": [],
        "evidence": [],
        "verified_evidence": [],
        "confidence_score": 0.0,
        "contradictions": [],
        "detective_notes": "",
        "retriever_notes": "",
        "verifier_notes": "",
        "scribe_notes": "",
        "report": "",
    }

    try:
        # Run the LangGraph workflow
        final_state = workflow.invoke(initial_state)

        console.print(f"\n[bold green]{'=' * 80}[/bold green]")
        console.print(f"[bold green]ANALYSIS COMPLETE[/bold green]")
        console.print(f"[bold green]{'=' * 80}[/bold green]")
        console.print(f"Iterations: {final_state.get('iteration', 0)}")
        console.print(f"Evidence: {len(final_state.get('verified_evidence', []))} segments")
        console.print(f"Confidence: {final_state.get('confidence_score', 0):.2%}")
        console.print(f"Contradictions: {len(final_state.get('contradictions', []))}")

        report = final_state.get("report", "")
        if report:
            console.print(f"\n[bold]Report:[/bold]")
            console.print(report)

        return dict(final_state)

    except Exception as e:
        console.print(f"\n[bold red]Analysis failed: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return None


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Videntia — Forensic Video Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Who showed surprise at the 200 pounds?"
  python main.py "What API keys were mentioned?" --max-iter 2
  python main.py "Compare emotional reactions" --max-iter 3
        """,
    )
    parser.add_argument(
        "query",
        type=str,
        help="Natural language query about the video",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=MAX_ITERATIONS,
        help=f"Maximum agent iterations (default: {MAX_ITERATIONS})",
    )

    args = parser.parse_args()
    result = analyze_video(args.query, args.max_iter, None)

    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
