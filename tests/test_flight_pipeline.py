import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.flight_service import flight_service
from services.llm_engine import LLMEngine

async def test_flight():
    print("=" * 65)
    print("✈️ TEST 1: Flight Route & Airport Code Resolution")
    print("=" * 65)

    test_queries = [
        "find the next flight from pom to bne and which airlines",
        "flights from Port Moresby to Sydney",
        "airline schedule from POM to SIN",
        "flights from Brisbane to Port Moresby"
    ]

    for q in test_queries:
        is_flight = flight_service.is_flight_query(q)
        orig_code, orig_name, dest_code, dest_name = flight_service.extract_route(q)
        print(f"Query: '{q}'")
        print(f"  -> Is Flight: {is_flight} | Origin: {orig_code} ({orig_name}) -> Dest: {dest_code} ({dest_name})")
        assert is_flight is True
        assert orig_code is not None and dest_code is not None
    print("✅ Route extraction passed!")

    print("\n" + "=" * 65)
    print("✈️ TEST 2: POM to BNE Flight Context & Live Search")
    print("=" * 65)
    query = "find the next flight from pom to bne and which airlines"
    has_ctx, sources = await flight_service.get_flight_context(query)
    print(f"Retrieved {len(sources)} sources for POM -> BNE:")
    for s in sources[:2]:
        print(f"  • [{s.get('title')}] -> {s.get('url')}")
    assert has_ctx is True
    assert len(sources) > 0

    print("\n" + "=" * 65)
    print("✈️ TEST 3: LLM Synthesis for Flight Query")
    print("=" * 65)
    engine = LLMEngine()
    resp = await engine.generate_response(query, search_results=sources)
    print(f"🤖 Bot Flight Response:\n{resp}\n")
    assert "Air Niugini" in resp or "Qantas" in resp or "POM" in resp or "BNE" in resp or "Brisbane" in resp
    print("✅ Flight LLM synthesis verified!")

    print("\n🎉 ALL FLIGHT PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_flight())
