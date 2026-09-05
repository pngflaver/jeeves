import asyncio
from services.nrl_service import nrl_service

async def test_nrl_pipeline():
    print("=" * 65)
    print("🏉 TEST 1: NRL Query Detection")
    print("=" * 65)
    assert nrl_service.is_nrl_query("what is the latest nrl news?"), "Failed to detect NRL query"
    assert nrl_service.is_nrl_query("did the broncos win?"), "Failed to detect Broncos query"
    assert nrl_service.is_nrl_query("who did the png chiefs sign?"), "Failed to detect PNG Chiefs query"
    assert nrl_service.is_nrl_query("queensland maroons state of origin team"), "Failed to detect Maroons query"
    assert not nrl_service.is_nrl_query("how to install docker on ubuntu"), "False positive on docker"
    print("✅ NRL query detection patterns verified!\n")

    print("=" * 65)
    print("🏉 TEST 2: Instant Priority Briefing Cache")
    print("=" * 65)
    briefing = await nrl_service.get_priority_briefing()
    print(briefing)
    assert "PNG Chiefs" in briefing, "Expected PNG Chiefs in priority briefing"
    assert "Broncos" in briefing, "Expected Broncos in priority briefing"
    assert "Maroons" in briefing, "Expected Maroons in priority briefing"
    print("\n✅ Verified priority briefing with PNG Chiefs, Broncos, and Maroons validated!\n")

    print("=" * 65)
    print("🏉 TEST 3: Accredited Tier-1 Search Formulation")
    print("=" * 65)
    results, tier = await nrl_service.fetch_tiered_search("PNG Chiefs NRL Joey Manu", max_results=2)
    print(f"Retrieved {len(results)} accredited results with tier: '{tier}':")
    for r in results:
        print(f" - {r.get('age_tier', '')} {r.get('title')} ({r.get('url')})")
        assert any(d in r.get('url', '') for d in ["abc.net.au", "thenational.com.pg", "postcourier.com.pg", "nrl.com", "foxsports.com.au", "smh.com.au"])
    print("\n✅ Verified search only returns accredited media outlets with age tiers!\n")

    print("=" * 65)
    print("🏉 TEST 4: Ground-Truth Season Memory & Cobbo Contract Status")
    print("=" * 65)
    grounding = nrl_service._build_season_grounding_context()
    print(grounding)
    assert "Brisbane Broncos Status: Finished 12th" in grounding
    assert "Current Club: The Dolphins" in grounding
    assert "Cobbo left the Broncos to join the Dolphins" in grounding
    print("✅ Ground-truth season memory verified successfully!\n")

    print("=" * 65)
    print("🏉 TEST 5: fetch_accredited_search with Ground-Truth Injection")
    print("=" * 65)
    acc_results = await nrl_service.fetch_accredited_search("is selwyn cobbo returning to the broncos")
    assert len(acc_results) > 0, "Expected search results"
    assert "GROUND TRUTH" in acc_results[0]["title"], "Expected ground truth in first source"
    assert "Current Club: The Dolphins" in acc_results[0]["snippet"]
    print(f"✅ Injected Ground Truth + {len(acc_results)-1} accredited live search sources successfully!\n")

if __name__ == "__main__":
    from services.nrl_service import NRL_VALIDATION_SYSTEM_PROMPT
    assert "CRITICAL FACT-CHECKING & TEMPORAL RULES" in NRL_VALIDATION_SYSTEM_PROMPT
    asyncio.run(test_nrl_pipeline())
