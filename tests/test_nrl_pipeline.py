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

    print("=" * 65)
    print("🏉 TEST 6: On-Demand Player Statistics Resolution & Card")
    print("=" * 65)
    stats_card = await nrl_service.query_specific_nrl("what are cobbo's latest stats ?")
    print(stats_card)
    assert "Selwyn Cobbo" in stats_card
    assert "The Dolphins" in stats_card
    assert "Tries Scored" in stats_card
    assert "12" in stats_card
    assert "2,740 m" in stats_card
    print("✅ Verified on-demand player statistics card output!\n")

    print("=" * 65)
    print("🏉 TEST 7: 17-Team Registry Lookup & Aliases")
    print("=" * 65)
    assert len(nrl_service.teams_registry.get("teams", {})) >= 18, "Expected 18 teams in registry"
    broncos_match = nrl_service.find_team_in_registry("broncos")
    assert broncos_match is not None, "Failed to match broncos"
    assert broncos_match[0] == "brisbane_broncos"

    dolphins_match = nrl_service.find_team_in_registry("what are dolphins stats?")
    assert dolphins_match is not None, "Failed to match dolphins"
    assert dolphins_match[0] == "the_dolphins"

    storm_match = nrl_service.find_team_in_registry("melbourne storm record")
    assert storm_match is not None, "Failed to match storm"
    assert storm_match[0] == "melbourne_storm"

    chiefs_match = nrl_service.find_team_in_registry("png chiefs")
    assert chiefs_match is not None, "Failed to match png chiefs"
    assert chiefs_match[0] == "png_chiefs"
    print("✅ Verified team registry matches and alias lookups!\n")

    print("=" * 65)
    print("🏉 TEST 8: Team Statistics & Ladder Form Card (Ladder & Form Only)")
    print("=" * 65)
    broncos_card = nrl_service.format_team_stats_card(broncos_match[1])
    print(broncos_card)
    assert "Brisbane Broncos" in broncos_card
    assert "12th" in broncos_card
    assert "26 Comp Points" in broncos_card
    assert "24 Played | 10 Wins | 14 Losses | 0 Draws | 3 Byes" in broncos_card
    assert "Differential: -78" in broncos_card
    assert "W - L - L - W - W" in broncos_card

    chiefs_card = nrl_service.format_team_stats_card(chiefs_match[1])
    print(chiefs_card)
    assert "PNG Chiefs" in chiefs_card
    assert "2028 NRL Expansion Franchise" in chiefs_card
    assert "Joey Manu" in chiefs_card
    print("✅ Verified team ladder record & win/loss form card outputs!\n")

    print("=" * 65)
    print("🏉 TEST 9: Full 17-Team NRL Ladder Standings")
    print("=" * 65)
    ladder_text = nrl_service.format_full_ladder()
    assert "Melbourne Storm" in ladder_text
    assert "Penrith Panthers" in ladder_text
    assert "Brisbane Broncos" in ladder_text
    assert "Wests Tigers" in ladder_text
    print(ladder_text[:300] + "...\n")
    print("✅ Verified full 17-team NRL ladder standings output!\n")

    print("=" * 65)
    print("🏉 TEST 10: Weekly Round Finalization & Sync Trigger")
    print("=" * 65)
    sync_res = await nrl_service.sync_weekly_round_finalization()
    print("Sync Result:", sync_res)
    assert sync_res["status"] == "success"
    assert sync_res["teams_count"] >= 18
    assert sync_res["players_count"] >= 27
    assert sync_res["briefing_refreshed"] is True
    print("✅ Verified weekly round finalization & registry synchronization!\n")

if __name__ == "__main__":
    from services.nrl_service import NRL_VALIDATION_SYSTEM_PROMPT
    assert "CRITICAL FACT-CHECKING & TEMPORAL RULES" in NRL_VALIDATION_SYSTEM_PROMPT
    asyncio.run(test_nrl_pipeline())
