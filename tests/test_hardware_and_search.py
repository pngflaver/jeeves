import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.search_service import search_web, search_hardware_lifecycle
from services.hardware_service import hardware_service
from services.llm_engine import LLMEngine

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
        print(f"  • [{s.get('title')}] -> {s.get('url')}")
    assert len(sources) > 0, "Expected at least 1 search source!"
    print("✅ Hardware search passed!")

    print("\n" + "=" * 60)
    print("🔍 Testing 3: LLM Synthesis with Live Hardware Context")
    print("=" * 60)
    engine = LLMEngine()
    resp = await engine.generate_response(query, search_results=sources)
    print(f"🤖 Bot LLM Response:\n{resp}")
    print("=" * 60)
    print("✅ LLM response generation passed!")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
