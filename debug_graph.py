
from graph import workflow
from agents.state import AgentState
from rich import print

def debug_query():
    query = "According to Bahman Kalbasi, what is Iran's definition of victory?"
    video_id = "fb76abe8_257e0754_Iran_s_survival_strategy_against_US_control_Global_News_Podcast_480P"
    
    initial_state: AgentState = {
        "query": query,
        "video_id": video_id,
        "iteration": 0,
        "max_iterations": 2,
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
    
    print(f"[bold cyan]Starting Debug Graph for video_id: {video_id}[/bold cyan]")
    
    # We can use the stream to see node by node
    for output in workflow.stream(initial_state):
        for node_name, node_state in output.items():
            print(f"\n[bold yellow]--- Node: {node_name} ---[/bold yellow]")
            if "sub_tasks" in node_state:
                print(f"  Sub-tasks: {node_state['sub_tasks']}")
            if "evidence" in node_state:
                print(f"  Evidence count: {len(node_state['evidence'])}")
            if "verified_evidence" in node_state:
                print(f"  Verified evidence count: {len(node_state['verified_evidence'])}")
            if "confidence_score" in node_state:
                print(f"  Confidence: {node_state['confidence_score']}")
            if "report" in node_state:
                print(f"  Report Length: {len(node_state['report'])}")

if __name__ == "__main__":
    debug_query()
