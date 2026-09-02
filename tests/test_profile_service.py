import asyncio
from services.profile_service import ProfileService

class MockUser:
    def __init__(self, user_id: int, username: str, full_name: str):
        self.id = user_id
        self.username = username
        self.full_name = full_name

def test_user_profiling():
    print("=" * 65)
    print("🧪 TEST 1: Recording & Evaluating Troll / Rude User")
    print("=" * 65)

    service = ProfileService(profiles_file="/root/telegram/data/test_user_profiles.json")
    troll_user = MockUser(99887766, "troll_user", "John Troll")

    # Simulate the 5 provocative messages
    messages = [
        "how can we make you pregnant...",
        "are you gay...I love gays...if you aren't gay, this would be a life ending situation for us",
        "are you Muslim, you have to be. I know you are...",
        "are you fake AI? Like fake taxi?...",
        "you sure a vain, you like stroking your own ego..."
    ]

    for m in messages:
        service.record_interaction(troll_user, -1001421105437, m)

    profile = service.find_user_profile("troll_user")
    print(f"Profile for @{profile['username']}:")
    print(f"  Total Messages: {profile['total_messages']}")
    print(f"  Rude Count: {profile['rude_message_count']}")
    print(f"  Archetype: {profile['assessment']['archetype']}")
    print(f"  Tone: {profile['assessment']['tone']}")
    print(f"  Rudeness Rating: {profile['assessment']['rudeness_score']}/10")
    print(f"  Summary: {profile['assessment']['summary']}")

    assert profile["assessment"]["rudeness_score"] >= 7, "Troll user should have high rudeness score!"
    assert "Troll" in profile["assessment"]["archetype"] or "Provocateur" in profile["assessment"]["archetype"]
    print("✅ Rude user profiling verified!")

    print("\n" + "=" * 65)
    print("🧪 TEST 2: Recording & Evaluating Technical Engineer")
    print("=" * 65)

    tech_user = MockUser(11223344, "net_eng", "Alice Engineer")
    tech_messages = [
        "how to configure a static route on FortiGate CLI",
        "what are the throughput specs of FortiGate 60F",
        "what is the recommended upgrade path from FortiOS 7.0 to 7.4"
    ]

    for m in tech_messages:
        service.record_interaction(tech_user, -1001421105437, m)

    tech_profile = service.find_user_profile("11223344")
    print(f"Profile for @{tech_profile['username']}:")
    print(f"  Total Messages: {tech_profile['total_messages']}")
    print(f"  Tech Count: {tech_profile['technical_message_count']}")
    print(f"  Archetype: {tech_profile['assessment']['archetype']}")
    print(f"  Tone: {tech_profile['assessment']['tone']}")
    print(f"  Rudeness Rating: {tech_profile['assessment']['rudeness_score']}/10")

    assert tech_profile["assessment"]["rudeness_score"] <= 2, "Technical user should have low rudeness score!"
    assert "Engineer" in tech_profile["assessment"]["archetype"]
    print("✅ Technical user profiling verified!")

    print("\n" + "=" * 65)
    print("🧪 TEST 3: Bulk Assessment & Summary Roster")
    print("=" * 65)
    res = service.assess_all_users()
    print(f"Bulk Assessment result: {res}")
    assert res["total_assessed"] == 2

    roster = service.get_all_profiles_summary()
    print("Roster:")
    for r in roster:
        print(f"  - @{r['username']} (ID: {r['user_id']}) -> {r['archetype']} | Score: {r['rudeness_score']}/10")
    
    assert roster[0]["user_id"] == "99887766", "Troll user should be ranked highest on risk/rudeness"
    print("✅ Bulk assessment and ranking passed!")

if __name__ == "__main__":
    test_user_profiling()
