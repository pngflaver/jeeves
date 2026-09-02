import re
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
import httpx
import config
from services.search_service import search_web

logger = logging.getLogger(__name__)

class MovieService:
    """
    Search and look up Movie and TV Show metadata, extracting IMDb parameters:
    - For Movies: {id} (IMDb ID with 'tt' prefix)
    - For TV Shows: {id}, {season}, {episode}
    """

    def parse_tv_query(self, query: str) -> Tuple[str, int, int]:
        """
        Parse raw TV query into (show_title, season_number, episode_number).
        Supports:
          - 'Lanterns season 1 episode 2'
          - 'Breaking Bad s02e05' / 's2 e5' / 's02.e05'
          - 'The Boys 2 5'
          - 'Stranger Things' (defaults to season 1, episode 1)
        """
        q = query.strip()

        # 1. Pattern: s02e05 or s2 e5 or s02.e05
        m1 = re.search(r'[\s._-]*[sS](\d{1,3})[\s._-]*[eE](\d{1,3})', q)
        if m1:
            title = q[:m1.start()].strip(' -_.')
            season = int(m1.group(1))
            episode = int(m1.group(2))
            return title, season, episode

        # 2. Pattern: season 1 episode 2
        m2 = re.search(r'[\s._-]*season\s*(\d{1,3})[\s._-]*episode\s*(\d{1,3})', q, re.IGNORECASE)
        if m2:
            title = q[:m2.start()].strip(' -_.')
            season = int(m2.group(1))
            episode = int(m2.group(2))
            return title, season, episode

        # 3. Pattern: trailing two numbers e.g. 'Lanterns 1 2'
        m3 = re.search(r'\s+(\d{1,3})\s+(\d{1,3})$', q)
        if m3:
            title = q[:m3.start()].strip(' -_.')
            season = int(m3.group(1))
            episode = int(m3.group(2))
            return title, season, episode

        # 4. Pattern: single season number e.g. 'Lanterns season 1' or 'Lanterns s1'
        m4 = re.search(r'[\s._-]*(?:season\s*|[sS])(\d{1,3})$', q, re.IGNORECASE)
        if m4:
            title = q[:m4.start()].strip(' -_.')
            season = int(m4.group(1))
            return title, season, 1

        return q, 1, 1

    async def search_imdb_suggestion(self, query: str) -> List[Dict[str, Any]]:
        """
        Query public IMDb suggestion endpoint for instant title & IMDb ID lookup.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        first_char = clean_q[0].lower() if clean_q[0].isalnum() else "a"
        url = f"https://v2.sg.media-imdb.com/suggestion/{first_char}/{clean_q.lower()}.json"
        
        results = []
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("d", []):
                        imdb_id = str(item.get("id", ""))
                        # Filter to only valid title IDs (starts with tt)
                        if not imdb_id.startswith("tt"):
                            continue

                        title = item.get("l", "")
                        year = item.get("y", "")
                        cast = item.get("s", "")
                        media_type = str(item.get("q", "feature")).lower()
                        
                        # Normalize type
                        if "series" in media_type or "tv" in media_type:
                            type_label = "TV Series"
                        elif "mini" in media_type:
                            type_label = "TV Mini-Series"
                        else:
                            type_label = "Movie"

                        image_info = item.get("i", {})
                        poster_url = image_info.get("imageUrl", "") if isinstance(image_info, dict) else ""

                        if imdb_id and title:
                            results.append({
                                "title": title,
                                "year": str(year) if year else "",
                                "imdb_id": imdb_id,
                                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                                "cast": cast,
                                "type": type_label,
                                "is_tv": "TV" in type_label,
                                "poster_url": poster_url
                            })
        except Exception as e:
            logger.error(f"IMDb suggestion lookup error for '{query}': {e}")
        return results

    async def _smart_imdb_search(self, query: str, prefer_tv: bool = False) -> List[Dict[str, Any]]:
        """
        Search IMDb suggestion with smart sequel normalization and TV show prioritization.
        """
        clean_q = query.strip()
        candidates = await self.search_imdb_suggestion(clean_q)

        # 1. Check if query ends with sequel digit e.g. '2', '3', '4'
        m = re.search(r'\b(2|3|4|5|6|7|8|9)\b$', clean_q)
        if m:
            digit = m.group(1)
            roman_map = {'2': 'ii', '3': 'iii', '4': 'iv', '5': 'v', '6': 'vi'}
            roman = roman_map.get(digit, '')
            
            if not candidates or (digit not in candidates[0].get("title", "").lower() and f"part {roman}" not in candidates[0].get("title", "").lower()):
                part_q = re.sub(rf'\b{digit}\b$', f'part {digit}', clean_q)
                alt_candidates = await self.search_imdb_suggestion(part_q)
                if alt_candidates:
                    candidates = alt_candidates

        # 2. If searching for TV, prioritize candidates marked as TV Series
        if prefer_tv and candidates:
            tv_candidates = [c for c in candidates if c.get("is_tv")]
            if tv_candidates:
                candidates = tv_candidates + [c for c in candidates if not c.get("is_tv")]
            else:
                # If no TV candidates found directly, try querying with 'TV series' suffix
                tv_query_candidates = await self.search_imdb_suggestion(f"{clean_q} series")
                tv_only = [c for c in tv_query_candidates if c.get("is_tv")]
                if tv_only:
                    candidates = tv_only + candidates

        return candidates

    async def lookup_movie(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Lookup movie and extract IMDb metadata.
        """
        clean_q = query.strip()
        if not clean_q:
            return None

        candidates = await self._smart_imdb_search(clean_q, prefer_tv=False)
        if not candidates:
            return None

        top_match = candidates[0]
        return {
            "title": top_match.get("title", clean_q),
            "year": top_match.get("year", ""),
            "type": top_match.get("type", "Movie"),
            "imdb_id": top_match.get("imdb_id", ""),
            "imdb_url": top_match.get("imdb_url", ""),
            "cast": top_match.get("cast", ""),
            "poster_url": top_match.get("poster_url", "")
        }

    async def lookup_tv(self, query: str) -> Tuple[Optional[Dict[str, Any]], int, int]:
        """
        Lookup TV series prioritizing TV shows over movies, and extract season/episode.
        """
        title, season, episode = self.parse_tv_query(query)
        clean_title = title.strip()
        if not clean_title:
            return None, season, episode

        candidates = await self._smart_imdb_search(clean_title, prefer_tv=True)
        if not candidates:
            return None, season, episode

        top_match = candidates[0]
        data = {
            "title": top_match.get("title", clean_title),
            "year": top_match.get("year", ""),
            "type": top_match.get("type", "TV Series"),
            "imdb_id": top_match.get("imdb_id", ""),
            "imdb_url": top_match.get("imdb_url", ""),
            "cast": top_match.get("cast", ""),
            "poster_url": top_match.get("poster_url", "")
        }
        return data, season, episode

    def build_movie_url(self, imdb_id: str) -> str:
        """Inject IMDb {id} into movie endpoint template."""
        template = getattr(config, "MOVIE_ENDPOINT_TEMPLATE", "https://111movies.net/movie/{id}")
        return template.format(id=imdb_id)

    def build_tv_url(self, imdb_id: str, season: int, episode: int) -> str:
        """Inject IMDb {id}, {season}, and {episode} into TV endpoint template."""
        template = getattr(config, "TV_ENDPOINT_TEMPLATE", "https://111movies.net/tv/{id}/{season}/{episode}")
        return template.format(id=imdb_id, season=season, episode=episode)

    def format_movie_card(self, data: Dict[str, Any]) -> str:
        """
        Format Movie card with IMDb parameters and generated API endpoint.
        """
        title = data.get("title", "Unknown Title")
        year_str = f" ({data.get('year')})" if data.get("year") else ""
        imdb_id = data.get("imdb_id", "N/A")
        cast = data.get("cast", "")
        api_url = self.build_movie_url(imdb_id) if imdb_id != "N/A" else ""

        lines = [
            f"🎬 **Movie: {title}{year_str}**\n",
            f"📌 **Extracted Parameters (`movie`):**",
            f"• `{{id}}` = `{imdb_id}`",
        ]

        if api_url:
            lines.append(f"• 🎥 **Movie URL:** {api_url}")

        lines.extend([
            f"\n📊 **Details:**",
            f"• **Type:** `{data.get('type', 'Movie')}`",
            f"• **IMDb ID:** `{imdb_id}`"
        ])

        if cast:
            lines.append(f"• **Starring:** {cast}")

        if data.get("imdb_url"):
            lines.append(f"\n🔗 **IMDb Link:** {data.get('imdb_url')}")

        return "\n".join(lines)

    def format_tv_card(self, data: Dict[str, Any], season: int, episode: int) -> str:
        """
        Format TV card with IMDb parameters: {id}, {season}, {episode} and generated API endpoint.
        """
        title = data.get("title", "Unknown Title")
        year_str = f" ({data.get('year')})" if data.get("year") else ""
        imdb_id = data.get("imdb_id", "N/A")
        cast = data.get("cast", "")
        ep_code = f"S{season:02d}E{episode:02d}"
        api_url = self.build_tv_url(imdb_id, season, episode) if imdb_id != "N/A" else ""

        lines = [
            f"📺 **TV Show: {title}{year_str}**\n",
            f"📌 **Extracted Parameters (`tv`):**",
            f"• `{{id}}` = `{imdb_id}`",
            f"• `{{season}}` = `{season}`",
            f"• `{{episode}}` = `{episode}`",
            f"• **Code:** `{ep_code}`",
        ]

        if api_url:
            lines.append(f"• **Endpoint URL:** {api_url}")

        lines.extend([
            f"\n📊 **Details:**",
            f"• **Type:** `{data.get('type', 'TV Series')}`",
            f"• **IMDb ID:** `{imdb_id}`",
            f"• **Season:** `{season}` | **Episode:** `{episode}`"
        ])

        if cast:
            lines.append(f"• **Starring:** {cast}")

        if data.get("imdb_url"):
            lines.append(f"\n🔗 **IMDb Link:** {data.get('imdb_url')}")

        return "\n".join(lines)

movie_service = MovieService()
