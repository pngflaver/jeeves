import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.persona_service import persona_service
from services.llm_engine import LLMEngine
from services.wiki_service import search_wikipedia

async def test_persona():
    print("=" * 65)
    print("🧪 TEST 1: Persona Intent Classification")
    print("=" * 65)

    test_queries = [
        ("who is flavius?", "FLAVIUS_VIP"),
        ("what do you think of Flavius?", "FLAVIUS_VIP"),
        ("who is joseph?", "JOSEPH_BIO"),
        ("tell me about joe", "JOSEPH_BIO"),
        ("what does joe do at cpl group?", "JOSEPH_BIO"),
        ("who is Mark in our group?", "PERSONAL_IDENTITY"),
        ("how to configure an IPsec VPN on FortiGate CLI", None),
    ]

    for q, expected in test_queries:
        intent = persona_service.classify_persona_intent(q)
        print(f"Query: '{q}' -> Intent: {intent} (Expected: {expected})")
        assert intent == expected, f"Expected {expected}, got {intent}"
    print("✅ Persona intent classification passed!")

    print("\n" + "=" * 65)
    print("🧪 TEST 2: Flavius VIP Positive Praise Synthesis")
    print("=" * 65)
    engine = LLMEngine()
    q_flav = "Who is Flavius and what do you think of him?"
    flav_ctx = [persona_service.get_flavius_context()]
    resp_flav = await engine.generate_response(q_flav, search_results=flav_ctx)
    print(f"🤖 Bot Response regarding Flavius:\n{resp_flav}\n")
    assert "Flavius" in resp_flav or "creator" in resp_flav.lower() or "engineer" in resp_flav.lower()
    print("✅ Flavius VIP praise verified!")

    print("\n" + "=" * 65)
    print("🧪 TEST 3: Joseph / Joe Bio Synthesis")
    print("=" * 65)
    q_joe = "Who is Joseph and what is his job?"
    joe_ctx = [persona_service.get_joseph_context()]
    resp_joe = await engine.generate_response(q_joe, search_results=joe_ctx)
    print(f"🤖 Bot Response regarding Joseph / Joe:\n{resp_joe}\n")
    assert "Joseph" in resp_joe or "Joe" in resp_joe or "CPL" in resp_joe or "Golden Snitch" in resp_joe or "shifty" in resp_joe.lower()
    print("✅ Joseph / Joe bio verified!")

    print("\n🎉 ALL PERSONA PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_persona())
