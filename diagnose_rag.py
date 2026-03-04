"""Quick diagnostic script to check RAG index health."""
import sys
sys.path.insert(0, '.')

# Check BM25
print("=== BM25 Index ===")
try:
    from embed.bm25_index import _load_index
    idx = _load_index()
    if idx:
        print(f"  OK: {len(idx['ids'])} segments indexed")
        print(f"  Sample IDs: {idx['ids'][:3]}")
    else:
        print("  EMPTY or not found!")
except Exception as e:
    print(f"  ERROR: {e}")

# Check ChromaDB
print("\n=== ChromaDB ===")
try:
    import chromadb
    from chromadb.config import Settings
    from config import CHROMA_DIR, TEXT_COLLECTION, VISION_COLLECTION
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
    for cname in [TEXT_COLLECTION, VISION_COLLECTION]:
        try:
            col = client.get_collection(cname)
            print(f"  {cname}: {col.count()} vectors")
        except Exception as e:
            print(f"  {cname}: NOT FOUND ({e})")
except Exception as e:
    print(f"  ERROR: {e}")

# Check records on disk
print("\n=== Records on disk ===")
try:
    from pipeline.ingest import load_records
    records = load_records()
    print(f"  {len(records)} total records")
    if records:
        print(f"  Sample: {records[0].segment_id} | transcript: {records[0].transcript[:80]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Try a live retrieval
print("\n=== Live BM25 Search Test (query: 'talking about') ===")
try:
    from embed.bm25_index import bm25_search
    results = bm25_search("talking about", top_k=3)
    if results:
        for seg_id, score in results:
            print(f"  {seg_id}: {score:.4f}")
    else:
        print("  No results returned!")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== Dense Search Test ===")
try:
    from embed.store import dense_search
    from config import TEXT_COLLECTION
    results = dense_search("what are they talking about", TEXT_COLLECTION, top_k=3)
    if results:
        for r in results:
            print(f"  {r['segment_id']}: score={r['score']:.4f}")
    else:
        print("  No results from dense search!")
except Exception as e:
    print(f"  ERROR: {e}")
