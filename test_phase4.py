from main import analyze_video

# Test Phase 4 - Multi-Agent System

print("=" * 80)
print("PHASE 4 TEST: Multi-Agent Video Analysis")
print("=" * 80)

# Test query
test_query = "What API keys were mentioned in the video and what are they used for?"

# Run the analysis (limit to 2 iterations for testing)
result = analyze_video(test_query, max_iterations=2)

if result:
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Iterations: {result['iteration']}")
    print(f"Evidence collected: {len(result['evidence'])}")
    print(f"Verified evidence: {len(result['verified_evidence'])}")
    print(f"Confidence: {result['confidence_score']:.2%}")
    print(f"Contradictions: {len(result['contradictions'])}")
    print("\n✅ Phase 4 test complete!")
else:
    print("\n❌ Test failed")
