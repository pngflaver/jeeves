import asyncio
from services.places_service import places_service

async def test_places():
    print("=" * 65)
    print("📍 TEST 1: CPL Medical Center Vision City Lookup & Hours")
    print("=" * 65)

    cpl_data = await places_service.lookup_place("CPL medical center vision city port moresby")
    card_cpl = places_service.format_place_card(cpl_data)
    print(card_cpl)

    assert "Cpl" in cpl_data["title"] or "City Pharmacy" in card_cpl or "Medical" in card_cpl
    assert "8:00" in card_cpl or "8am" in card_cpl or "daily" in card_cpl
    assert "google.com/maps" in card_cpl
    assert "openstreetmap.org" in card_cpl
    print("\n✅ CPL Medical Center hours & card verified successfully!\n")

    print("=" * 65)
    print("📍 TEST 2: Airways Hotel OpenStreetMap Coordinates & Contact")
    print("=" * 65)

    airways_data = await places_service.lookup_place("Airways Hotel Port Moresby")
    card_airways = places_service.format_place_card(airways_data)
    print(card_airways)

    assert "Airways" in airways_data["title"]
    assert "324 5200" in airways_data["phone"] or "324" in card_airways
    assert airways_data["lat"] is not None
    assert "openstreetmap.org" in card_airways
    print("\n✅ Airways Hotel OpenStreetMap data verified successfully!\n")

if __name__ == "__main__":
    asyncio.run(test_places())
