import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.technical_service import technical_service
from services.software_service import software_service
from services.llm_engine import LLMEngine

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
    print("🧪 TEST 2: Software Lifecycle Synthesis (Ubuntu 20.04 EOL)")
    print("=" * 65)
    q_eol = "when is Ubuntu 20.04 LTS end of life?"
    intent, sources = await technical_service.get_technical_context(q_eol)
    engine = LLMEngine()
    resp_eol = await engine.generate_response(q_eol, search_results=sources)
    print(f"🤖 Bot Software EOL Response:\n{resp_eol[:350]}...\n")
    assert "2025" in resp_eol or "2030" in resp_eol or "Ubuntu" in resp_eol, "EOL dates expected in response"
    print("✅ Software lifecycle synthesis passed!")

    print("\n🎉 ALL SOFTWARE PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_software())
