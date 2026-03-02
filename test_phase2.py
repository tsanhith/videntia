# test_phase2.py
from embed.store import dense_search
from embed.bm25_index import bm25_search

print("=== TEST 1: Dense Search (text) ===")
results = dense_search("API key initialization", "text_segments", top_k=3)
for r in results:
    meta = r["metadata"]
    print(f"[{r['segment_id']}] {meta['start_sec']}s-{meta['end_sec']}s | score={r['score']:.3f}")
    print(f"  {r['text'][:120]}")
    print()

print("=== TEST 2: BM25 Search (keywords) ===")
results = bm25_search("API key", top_k=3)
for seg_id, score in results:
    print(f"[{seg_id}] score={score:.3f}")

print()
print("=== TEST 3: Vision Search (cross-modal) ===")
results = dense_search("dark interface search results", "vision_segments", top_k=3)
for r in results:
    meta = r["metadata"]
    print(f"[{r['segment_id']}] {meta['start_sec']}s-{meta['end_sec']}s | score={r['score']:.3f}")
    print(f"  {r['text'][:120]}")
    print()