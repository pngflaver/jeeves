import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.flight_service import flight_service
from services.llm_engine import LLMEngine

async def test_flight():
    print("=" * 65)
    print("✈️ TEST 1: Flight Number & Code Detection")
    print("=" * 65)
    f_info = flight_service.detect_flight_number("is PX3 active right now?")
    print("Flight number detection 'PX3':", f_info)
    assert f_info == ("PX3", "PX", "3")

    f_info2 = flight_service.detect_flight_number("track flight QF57 to port moresby")
    print("Flight number detection 'QF57':", f_info2)
    assert f_info2 == ("QF57", "QF", "57")
    print("✅ Flight code detection passed!")

    print("\n" + "=" * 65)
    print("✈️ TEST 2: All International PX Flights Query")
    print("=" * 65)
    q_px = "show me all international px flights"
    has_ctx, px_sources = await flight_service.get_flight_context(q_px)
    print(f"Retrieved {len(px_sources)} sources for PX international network:")
    for s in px_sources[:2]:
        print(f"  • [{s.get('title')}] -> {s.get('url')}")
    assert has_ctx is True
    assert any("PX003" in s.get("snippet", "") or "Air Niugini" in s.get("snippet", "") for s in px_sources)
    print("✅ PX international network search passed!")

    print("\n" + "=" * 65)
    print("✈️ TEST 3: All QF Domestic Flights Leaving Brisbane")
    print("=" * 65)
    q_qf = "list all qf domestic flights leaving brisbane"
    has_ctx, qf_sources = await flight_service.get_flight_context(q_qf)
    print(f"Retrieved {len(qf_sources)} sources for QF BNE domestic:")
    for s in qf_sources[:2]:
        print(f"  • [{s.get('title')}] -> {s.get('url')}")
    assert has_ctx is True
    assert any("QF500" in s.get("snippet", "") or "Brisbane" in s.get("snippet", "") for s in qf_sources)
    print("✅ QF Brisbane domestic search passed!")

    print("\n" + "=" * 65)
    print("✈️ TEST 4: LLM Synthesis with Live Radar Tracking Link (PX3)")
    print("=" * 65)
    q_track = "is there an active flight for PX3 and where can i track it?"
    has_ctx, track_sources = await flight_service.get_flight_context(q_track)
    engine = LLMEngine()
    resp_track = await engine.generate_response(q_track, search_results=track_sources)
    print(f"🤖 Bot Flight Tracking Response:\n{resp_track}\n")
    assert "PX3" in resp_track or "FlightRadar24" in resp_track or "flightradar24" in resp_track or "Air Niugini" in resp_track
    print("✅ Flight tracking synthesis passed!")

    print("\n🎉 ALL FLIGHT PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_flight())
