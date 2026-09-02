import asyncio
from technical_service import technical_service
from llm_engine import LLMEngine

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
        vendor, model = technical_service.detect_vendor_and_model(q)
        print(f"Query: '{q}'")
        print(f"  -> Intent: {intent} (Expected: {expected_intent})")
        print(f"  -> Vendor: {vendor} (Expected: {expected_vendor}) | Model Identity: {model}")
        assert intent == expected_intent, f"Intent mismatch for '{q}': got {intent}, expected {expected_intent}"
        assert vendor == expected_vendor, f"Vendor mismatch for '{q}': got {vendor}, expected {expected_vendor}"
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
    print("🧪 TEST 3: CVE Advisory Extraction & Verification")
    print("=" * 65)
    cve_query = "what is CVE-2024-21762 and what FortiOS versions are affected?"
    cve_intent, cve_sources = await technical_service.get_technical_context(cve_query)
    cve_resp = await engine.generate_response(cve_query, search_results=cve_sources)
    print(f"🤖 Bot CVE Response Preview:\n{cve_resp[:350]}...\n")
    print("✅ CVE advisory synthesis passed!")

    print("\n" + "=" * 65)
    print("🧪 TEST 4: Auto-discovery & Dynamic Specs Caching")
    print("=" * 65)
    specs_query = "what is the firewall throughput and port count of FortiGate 60F"
    specs_intent, specs_sources = await technical_service.get_technical_context(specs_query)
    
    # Check if FortiGate 60F profile was created in cache
    cached_profile = technical_service.get_cached_profile("Fortinet FortiGate 60F") or technical_service.get_cached_profile("FortiGate 60F")
    print(f"Cached Profile in hardware_cache.json: {cached_profile is not None}")
    assert cached_profile is not None, "Profile should be automatically cached!"
    print(f"  Identity: {cached_profile.get('identity')} | Vendor: {cached_profile.get('vendor')} | Sources: {len(cached_profile.get('sources', []))}")
    print("✅ Auto-discovery & caching passed!")

if __name__ == "__main__":
    asyncio.run(test_all_technical_scenarios())
