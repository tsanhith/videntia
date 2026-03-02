"""
Quick Test Suite for Optimized Emotion Analysis
Run these queries to see the improvements in action!
"""

from main import analyze_video
from rich import print
from rich.console import Console

console = Console()

# Test queries optimized for emotion + reaction analysis
test_queries = [
    # Emotion-focused queries
    ("Emotion Query 1", "Who showed surprise when hearing about 200 pounds daily travel cost?"),
    ("Emotion Query 2", "Compare emotional reactions before and after the 200 pounds statement"),
    ("Emotion Query 3", "Were there any laughing or joking reactions to the travel expense?"),
    
    # Temporal queries
    ("Temporal Query 1", "What was discussed immediately before mentioning the cost?"),
    ("Temporal Query 2", "Show the sequence of reactions after the 200 pounds claim"),
    
    # Speaker queries
    ("Speaker Query 1", "Who made the claim about 200 pounds and who reacted?"),
    ("Speaker Query 2", "Did anyone disagree or question the travel cost?"),
    
    # Complex queries
    ("Complex Query 1", "Find all expressions of disbelief through both words and visual cues"),
    ("Complex Query 2", "What emotions were detected throughout this conversation?"),
]

def run_single_test(name: str, query: str):
    """Run a single test query and display results."""
    print(f"\n{'='*80}")
    print(f"[bold cyan]TEST: {name}[/bold cyan]")
    print(f"Query: {query}")
    print('='*80)
    
    result = analyze_video(query, max_iterations=3)
    
    if result:
        print(f"\n[bold green]✓ Test Complete[/bold green]")
        print(f"  Evidence: {len(result['verified_evidence'])} segments")
        print(f"  Confidence: {result['confidence_score']:.2%}")
        print(f"  Iterations: {result['iteration']}")
    else:
        print(f"\n[bold red]✗ Test Failed[/bold red]")

def run_all_tests():
    """Run all test queries."""
    print("\n[bold yellow]OPTIMIZED EMOTION ANALYSIS - TEST SUITE[/bold yellow]\n")
    
    for i, (name, query) in enumerate(test_queries, 1):
        print(f"\n[dim]Test {i}/{len(test_queries)}[/dim]")
        run_single_test(name, query)
        
        if i < len(test_queries):
            input("\nPress Enter to continue to next test...")
    
    print("\n[bold green]All tests complete![/bold green]")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Run specific test by number
        test_num = int(sys.argv[1]) - 1
        if 0 <= test_num < len(test_queries):
            name, query = test_queries[test_num]
            run_single_test(name, query)
        else:
            print(f"Invalid test number. Choose 1-{len(test_queries)}")
    else:
        # Run all tests
        run_all_tests()
