import asyncio
from services.technical_service import technical_service

async def test_ask_intent_and_search():
    print("=" * 65)
    print("🧠 TEST 1: General Web Query (CPL Medical Center)")
    print("=" * 65)
    q_general = "what does does Cpl medical center and vision city in port moresby close?"
    intent_gen, results_gen = await technical_service.get_technical_context(q_general)
    print(f"Query: '{q_general}'")
    print(f"Intent classified: {intent_gen}")
    print(f"Search results retrieved: {len(results_gen)}")
    for r in results_gen[:2]:
        print(f" - {r.get('title')}: {r.get('snippet')[:100]}")

    assert intent_gen == "GENERAL_WEB", f"Expected GENERAL_WEB but got {intent_gen}"
    assert len(results_gen) > 0, "Expected at least 1 search result"
    print("\n✅ General web search classified and executed cleanly without networking keywords!\n")

    print("=" * 65)
    print("🧠 TEST 2: Technical Software Upgrade Query (FortiGate 60F)")
    print("=" * 65)
    q_tech = "FortiGate 60F upgrade path to 7.4"
    intent_tech, results_tech = await technical_service.get_technical_context(q_tech)
    print(f"Query: '{q_tech}'")
    print(f"Intent classified: {intent_tech}")
    print(f"Search results retrieved: {len(results_tech)}")

    assert intent_tech == "SOFTWARE_UPGRADE", f"Expected SOFTWARE_UPGRADE but got {intent_tech}"
    assert len(results_tech) > 0, "Expected technical search results"
    print("\n✅ Technical software upgrade query formulated and retrieved successfully!\n")

    print("=" * 65)
    print("🧠 TEST 3: Technical CLI Configuration Query (Cisco BGP)")
    print("=" * 65)
    q_cli = "how to configure bgp peer on cisco"
    intent_cli, _ = await technical_service.get_technical_context(q_cli)
    print(f"Query: '{q_cli}' -> Intent: {intent_cli}")
    assert intent_cli == "CLI_CONFIG", f"Expected CLI_CONFIG but got {intent_cli}"
    print("✅ Technical CLI configuration intent verified!\n")

    print("=" * 65)
    print("🧠 TEST 4: General Knowledge Query (Capital of Peru)")
    print("=" * 65)
    q_geo = "what is the capital of Peru?"
    intent_geo, results_geo = await technical_service.get_technical_context(q_geo)
    print(f"Query: '{q_geo}' -> Intent: {intent_geo}")
    assert intent_geo == "GENERAL_WEB", f"Expected GENERAL_WEB but got {intent_geo}"
    print("✅ General knowledge intent verified!\n")

if __name__ == "__main__":
    asyncio.run(test_ask_intent_and_search())
