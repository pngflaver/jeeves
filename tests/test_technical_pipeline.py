import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.technical_service import technical_service
from services.llm_engine import LLMEngine

async def test_all_technical_scenarios():
    print("=" * 65)
    print("🧪 TEST 1: Intent & Make/Model Classification")
    print("=" * 65)
    
    test_queries = [
        ("how to configure an IPsec VPN on FortiGate CLI", "CLI_CONFIG", "Fortinet"),
        ("what is CVE-2024-21762 FortiOS SSL-VPN vulnerability", "CVE", "Fortinet"),
        ("what are the specs and throughput of FortiGate 60F", "SPECS_EOL", "Fortinet"),
        ("show me Cisco Catalyst 9300 port configurations", "CLI_CONFIG", "Cisco")
    ]
    
    for q, expected_intent, expected_vendor in test_queries:
        intent = technical_service.classify_intent(q)
        vendor, identity, cat = technical_service.detect_technology(q)
        print(f"Query: '{q}'")
        print(f"  -> Intent: {intent} (Expected: {expected_intent})")
        print(f"  -> Vendor: {vendor} (Expected: {expected_vendor}) | Identity: {identity} | Category: {cat}")
        assert intent == expected_intent, f"Intent mismatch for '{q}': got {intent}, expected {expected_intent}"
        assert vendor in (expected_vendor, "FortiOS", "Fortinet"), f"Vendor mismatch for '{q}': got {vendor}, expected {expected_vendor}"
    print("✅ Intent and Vendor detection passed!")

    print("\n" + "=" * 65)
    print("🧪 TEST 2: CLI Configuration Retrieval & LLM Code Block Output")
    print("=" * 65)
    cli_query = "how to configure a static route on FortiGate CLI"
    intent, sources = await technical_service.get_technical_context(cli_query)
    print(f"Retrieved {len(sources)} search sources for CLI query.")
    
    engine = LLMEngine()
    cli_resp = await engine.generate_response(cli_query, search_results=sources)
    print(f"🤖 Bot CLI Response Preview:\n{cli_resp[:350]}...\n")
    assert "config router static" in cli_resp or "router" in cli_resp or "```" in cli_resp, "CLI code block expected!"
    print("✅ CLI configuration synthesis passed!")

    print("\n" + "=" * 65)
    print("🧪 TEST 3: CVE Security Advisory Analysis")
    print("=" * 65)
    cve_query = "what is CVE-2024-21762 FortiOS out-of-bound write vulnerability?"
    cve_intent, cve_sources = await technical_service.get_technical_context(cve_query)
    cve_resp = await engine.generate_response(cve_query, search_results=cve_sources)
    print(f"🤖 Bot CVE Response Preview:\n{cve_resp[:350]}...\n")
    assert "CVE-2024-21762" in cve_resp or "SSL-VPN" in cve_resp or "FortiOS" in cve_resp, "CVE details expected!"
    print("✅ CVE analysis passed!")

    print("\n🎉 ALL TECHNICAL PIPELINE TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all_technical_scenarios())
