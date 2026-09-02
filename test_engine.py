import asyncio
import time
from llm_engine import LLMEngine
from wiki_service import search_wikipedia

async def test_expanded_engine():
    print("🤖 Initializing Expanded LLMEngine & Wikipedia test...")
    engine = LLMEngine()

    test_cases = [
        {"type": "IT / Tech", "query": "How do I use the ping command to test connectivity with 3 packets?"},
        {"type": "IT / Tech", "query": "How to check open listening ports in Linux using ss?"},
        {"type": "General Knowledge", "query": "What is the James Webb Space Telescope?"},
        {"type": "General Knowledge", "query": "Who was Ada Lovelace?"},
    ]

    for item in test_cases:
        q = item["query"]
        q_type = item["type"]
        print("\n" + "=" * 60)
        print(f"[{q_type}] ❓ Query: {q}")

        wiki_info = None
        if q_type == "General Knowledge":
            wiki_info = await search_wikipedia(q)
            if wiki_info:
                print(f"📚 Wiki Found: {wiki_info['title']} -> {wiki_info['url']}")

        t0 = time.perf_counter()
        resp = await engine.generate_response(q, wiki_info=wiki_info)
        duration = time.perf_counter() - t0

        print(f"⚡ Time: {duration:.2f}s | Word count: {len(resp.split())}")
        print(f"💬 Bot Output:\n{resp}")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_expanded_engine())
