import asyncio
from services.movie_service import movie_service

async def test_pipeline():
    print("=" * 65)
    print("🎬 TEST 1: Movie Lookups & {id} + Endpoint URL Extraction")
    print("=" * 65)

    movie_tests = ["Inception", "Interstellar 2014", "The Matrix", "back to the future 2"]
    for title in movie_tests:
        print(f"\n🔍 Searching Movie: '{title}'...")
        data = await movie_service.lookup_movie(title)
        assert data is not None and data.get("imdb_id").startswith("tt")
        
        card = movie_service.format_movie_card(data)
        print(f"  Title:    {data['title']} ({data['year']})")
        print(f"  IMDb ID:  {data['imdb_id']}")
        print(f"  Endpoint: {movie_service.build_movie_url(data['imdb_id'])}")
        assert "{id}" in card
        assert data["imdb_id"] in card
        assert "https://111movies.net/movie/" in card

    print("\n" + "=" * 65)
    print("📺 TEST 2: TV Show Lookups & {id}, {season}, {episode} + Endpoint")
    print("=" * 65)

    tv_tests = [
        ("Breaking Bad s02e05", "Breaking Bad", 2, 5),
        ("The Boys season 3 episode 2", "The Boys", 3, 2),
        ("Game of Thrones 4 8", "Game of Thrones", 4, 8),
        ("lanterns season 1 episode 2", "Lanterns", 1, 2)
    ]

    for raw_q, expected_title, exp_season, exp_ep in tv_tests:
        print(f"\n🔍 Searching TV Query: '{raw_q}'...")
        data, season, episode = await movie_service.lookup_tv(raw_q)
        assert data is not None
        assert season == exp_season, f"Expected season {exp_season}, got {season}"
        assert episode == exp_ep, f"Expected episode {exp_ep}, got {episode}"
        assert data.get("imdb_id").startswith("tt")

        card = movie_service.format_tv_card(data, season, episode)
        ep_url = movie_service.build_tv_url(data["imdb_id"], season, episode)
        print(f"  Parsed Title:   {data['title']}")
        print(f"  IMDb ID:        {data['imdb_id']}")
        print(f"  Season/Episode: S{season:02d}E{episode:02d}")
        print(f"  Endpoint URL:   {ep_url}")
        assert "{id}" in card
        assert "{season}" in card
        assert "{episode}" in card
        assert f"S{season:02d}E{episode:02d}" in card
        assert ep_url in card

    print("\n✅ All Movie and TV endpoint tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
