from rag.retriever import hybrid_retrieve

print("=" * 60)
print("TEST 1: Query about API keys")
print("=" * 60)
results = hybrid_retrieve("Who mentioned the API key?", top_k=3)
for r in results:
    print(f"\n[{r['segment_id']}] {r['start_sec']:.0f}s-{r['end_sec']:.0f}s")
    print(f"  RRF score:    {r['rrf_score']:.4f}")
    print(f"  Rerank score: {r['rerank_score']:.4f}")
    print(f"  Transcript:   {r['transcript'][:120]}")

print("\n" + "=" * 60)
print("TEST 2: Visual query (cross-modal)")
print("=" * 60)
results = hybrid_retrieve("dark screen with search results", top_k=3)
for r in results:
    print(f"\n[{r['segment_id']}] {r['start_sec']:.0f}s-{r['end_sec']:.0f}s")
    print(f"  Rerank score: {r['rerank_score']:.4f}")
    if r['visual_captions']:
        print(f"  Captions:     {r['visual_captions'][0][:100]}")

print("\n" + "=" * 60)
print("TEST 3: Forensic query")
print("=" * 60)
results = hybrid_retrieve("what tools or systems were demonstrated?", top_k=3)
for r in results:
    print(f"\n[{r['segment_id']}] {r['start_sec']:.0f}s-{r['end_sec']:.0f}s")
    print(f"  Rerank score: {r['rerank_score']:.4f}")
    print(f"  Transcript:   {r['transcript'][:120]}")
