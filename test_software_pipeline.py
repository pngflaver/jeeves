import asyncio
from technical_service import technical_service
from software_service import software_service
from llm_engine import LLMEngine

async def test_software():
    print("=" * 65)
    print("🧪 TEST 1: Software Classification & Technology Detection")
    print("=" * 65)
    
    test_cases = [
        ("what is the upgrade path from FortiOS 7.0 to 7.4?", "SOFTWARE_UPGRADE", "FortiOS"),
        ("when is Ubuntu 20.04 LTS end of life?", "SPECS_EOL", "Ubuntu"),
        ("how to install docker on Debian 12 with systemd", "SOFTWARE_INSTALL", "Docker")
    ]
    
    for q, exp_intent, exp_vendor in test_cases:
        intent = technical_service.classify_intent(q)
        vendor, identity, cat = technical_service.detect_technology(q)
        print(f"Query: '{q}'")
        print(f"  -> Intent: {intent} (Expected: {exp_intent}) | Tech: {vendor} | Identity: {identity} | Category: {cat}")
        assert intent == exp_intent, f"Expected intent {exp_intent}, got {intent}"
        assert vendor in (exp_vendor, "Debian", "Docker"), f"Expected tech {exp_vendor}, got {vendor}"
    print("✅ Software classification passed!")

    print("\n" + "=" * 65)
    print("🧪 TEST 2: Software Inventory Tracking (`software.txt`)")
    print("=" * 65)
    tracked = software_service.get_tracked_software()
    print(f"Tracked software entries ({len(tracked)}): {tracked[:5]}...")
    assert len(tracked) >= 5, "Expected tracked software entries"
    
    matched = software_service.match_software_in_query("tell me about FortiOS 7.2 support lifecycle")
    print(f"Query matched software: '{matched}'")
    assert matched == "FortiOS 7.2", f"Expected 'FortiOS 7.2', got '{matched}'"
    print("✅ Software inventory matching passed!")

    print("\n" + "=" * 65)
    print("🧪 TEST 3: Software Upgrade Path & EOL Synthesis")
    print("=" * 65)
    query = "what is the recommended upgrade path from FortiOS 7.0 to 7.4"
    intent, sources = await technical_service.get_technical_context(query)
    print(f"Retrieved {len(sources)} search sources for upgrade path.")
    
    engine = LLMEngine()
    resp = await engine.generate_response(query, search_results=sources)
    print(f"🤖 Bot Software Upgrade Response Preview:\n{resp[:350]}...\n")
    assert len(resp) > 50
    print("✅ Software synthesis passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_software())
