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
    results = await nrl_service.fetch_accredited_search("PNG Chiefs NRL Joey Manu", max_results=2)
    print(f"Retrieved {len(results)} accredited results:")
    for r in results:
        print(f" - {r.get('title')} ({r.get('url')})")
        assert any(d in r.get('url', '') for d in ["abc.net.au", "thenational.com.pg", "postcourier.com.pg", "nrl.com", "foxsports.com.au", "smh.com.au"])
    print("\n✅ Verified search only returns accredited media outlets!\n")

if __name__ == "__main__":
    asyncio.run(test_nrl_pipeline())
