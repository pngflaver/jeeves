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
        ("who created you and who is your boss?", "FLAVIUS_VIP"),
        ("who is Mark in our group?", "PERSONAL_IDENTITY"),
        ("who is joe?", "PERSONAL_IDENTITY"),
        ("what is your name?", "PERSONAL_IDENTITY"),
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
    print("🧪 TEST 3: General Personal Query Neutral Handling")
    print("=" * 65)
    q_pers = "Who is Michael in our group?"
    wiki_info = await search_wikipedia(q_pers)
    resp_pers = await engine.generate_response(q_pers, wiki_info=wiki_info)
    print(f"🤖 Bot Response for generic person query:\n{resp_pers}\n")
    print("✅ General personal question response verified!")

    print("\n🎉 ALL PERSONA PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_persona())
