import asyncio
from search_service import search_web, search_hardware_lifecycle
from hardware_service import hardware_service
from llm_engine import LLMEngine

async def test_pipeline():
    print("=" * 60)
    print("🔍 Testing 1: Hardware Matching from hardware.txt")
    print("=" * 60)
    
    devices = hardware_service.get_tracked_devices()
    print(f"Tracked devices in hardware.txt ({len(devices)}): {devices}")
    
    query = "what's the end of life for the fortigate 40f"
    matched = hardware_service.match_device_in_query(query)
    print(f"Query: '{query}' -> Matched Device: '{matched}'")
    assert matched == "FortiGate 40F", f"Expected 'FortiGate 40F', got '{matched}'"
    print("✅ Hardware matching passed!")

    print("\n" + "=" * 60)
    print("🔍 Testing 2: Hardware Search & Caching")
    print("=" * 60)
    sources = await hardware_service.fetch_and_cache(matched)
    print(f"Retrieved {len(sources)} search sources for '{matched}':")
    for s in sources[:2]:
        print(f"  - Title: {s['title']}\n    URL: {s['url']}\n    Snippet: {s['snippet'][:100]}...")
    
    cached = hardware_service.get_cached_info(matched)
    assert cached is not None and len(cached["sources"]) > 0
    print("✅ Hardware caching passed!")

    print("\n" + "=" * 60)
    print("🔍 Testing 3: LLM Structured Response Generation")
    print("=" * 60)
    engine = LLMEngine()
    response = await engine.generate_response(query, search_results=sources)
    print(f"🤖 Bot Response:\n{response}")
    assert len(response) > 50, "Response too short!"
    print("\n✅ End-to-end test passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
