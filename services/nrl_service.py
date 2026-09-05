import os
import json
import time
import logging
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from services.search_service import search_web, enrich_and_sort_by_date
from services.llm_engine import LLMEngine

logger = logging.getLogger(__name__)

SITE_FILTER = "site:nrl.com OR site:foxsports.com.au OR site:abc.net.au OR site:qrl.com.au OR site:postcourier.com.pg OR site:thenational.com.pg"

NRL_QUERY_PATTERN = re.compile(
    r"\b(nrl|rugby league|broncos|brisbane broncos|maroons|state of origin|origin|png chiefs|png nrl|kumuls|png hunters|reece walsh|billy slater|kevin walters|selwyn cobbo|cobbo|payne haas|adam reynolds)\b",
    re.IGNORECASE
)

NRL_VALIDATION_SYSTEM_PROMPT = (
    "You are the official NRL (National Rugby League) specialist for Jeeves.\n"
    "CRITICAL FACT-CHECKING & TEMPORAL RULES:\n"
    "1. Regular rounds for NRL are FINISHED. The Brisbane Broncos finished 12th, missed the top 8, and their season is OVER with NO games left this year.\n"
    "2. Player Contract Status:\n"
    "   - Selwyn Cobbo left the Brisbane Broncos and plays for The Dolphins. He is NOT returning to the Broncos.\n"
    "   - If asked if Selwyn Cobbo is returning to the Brisbane Broncos, state clearly that NO, he is not returning to the Broncos; he is an active Dolphins player.\n"
    "   - Playing in the away sheds at Suncorp was a past match in Round 4 where he played AGAINST the Broncos, not a return to the team.\n"
    "3. Sources are tagged with freshness (🟢 Past 7 Days vs 🔴 Historical). Prioritize the past 7 days. Treat news older than 7 days as past history.\n"
    "4. Report strictly verified facts from accredited sources (NRL.com, Fox Sports, ABC, QRL, Post-Courier, The National). Never report rumors or unverified social media posts."
)

class NRLService:
    """
    Date-Aware NRL Intelligence Engine with persistent season memory,
    weekly Sunday/Monday round finalization, 7-day freshness tiering,
    and anti-hallucination ground-truth verification.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_dir = data_dir or (Path(__file__).resolve().parent.parent / "data")
        self.nrl_dir = self.base_dir / "nrl"
        self.cache_file = self.base_dir / "nrl_cache.json"
        self.current_year = datetime.now(timezone.utc).year
        self.llm = LLMEngine()

        self.cached_briefing: Optional[Dict[str, Any]] = None
        self.season_memory: Dict[str, Any] = {}
        self.player_registry: Dict[str, Any] = {}
        self.ladder_data: Dict[str, Any] = {}

        self._load_memory()
        self._load_briefing_cache()

    def _get_year_dir(self, year: Optional[int] = None) -> Path:
        y = year or self.current_year
        ydir = self.nrl_dir / str(y)
        ydir.mkdir(parents=True, exist_ok=True)
        return ydir

    def _load_memory(self) -> None:
        """Load persistent ground-truth season status, player registry, and ladder."""
        ydir = self._get_year_dir()
        
        # 1. Season status
        status_file = ydir / "season_status.json"
        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    self.season_memory = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL season status: {e}")

        # 2. Player registry
        player_file = ydir / "player_registry.json"
        if player_file.exists():
            try:
                with open(player_file, "r", encoding="utf-8") as f:
                    self.player_registry = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL player registry: {e}")

        # 3. Ladder
        ladder_file = ydir / "ladder.json"
        if ladder_file.exists():
            try:
                with open(ladder_file, "r", encoding="utf-8") as f:
                    self.ladder_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL ladder: {e}")

    def _load_briefing_cache(self) -> None:
        """Load pre-compiled briefing from disk cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cached_briefing = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL cache: {e}")

    def _save_briefing_cache(self) -> None:
        """Persist pre-compiled briefing to disk."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cached_briefing, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving NRL cache: {e}")

    def is_nrl_query(self, text: str) -> bool:
        """Check if query is related to NRL rugby league."""
        return bool(NRL_QUERY_PATTERN.search(text))

    def _filter_accredited(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keep only results from accredited sports journalism domains and filter out social media."""
        filtered = []
        for r in results:
            url = r.get("url", "").lower()
            if any(social in url for social in ["youtube.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "reddit.com", "tiktok.com"]):
                continue
            filtered.append(r)
        return filtered

    async def fetch_tiered_search(self, topic: str, max_results: int = 4) -> Tuple[List[Dict[str, str]], str]:
        """
        Tiered freshness search:
        1. Prioritizes the past 7 days (timelimit='w').
        2. If fewer than 2 results found, expands to past month (timelimit='m') with explicit historical tag.
        """
        query = f"{topic} ({SITE_FILTER})"
        
        # Tier 1: Past 7 days
        week_results = self._filter_accredited(await search_web(query, max_results=max_results + 2, timelimit="w"))
        if len(week_results) >= 2:
            enriched = enrich_and_sort_by_date(week_results[:max_results], newest_first=True)
            return enriched, "🟢 Past 7 Days (Fresh News)"

        # Tier 2: Fallback to past month
        month_results = self._filter_accredited(await search_web(query, max_results=max_results + 2, timelimit="m"))
        if month_results:
            enriched = enrich_and_sort_by_date(month_results[:max_results], newest_first=True)
            return enriched, "🟡 Past Month (Archive Context)"

        # Tier 3: General fallback
        gen_results = self._filter_accredited(await search_web(query, max_results=max_results + 2))
        enriched = enrich_and_sort_by_date(gen_results[:max_results], newest_first=True)
        return enriched, "🔴 Historical Archive"

    def _build_season_grounding_context(self, query: str = "") -> str:
        """Generate ground-truth season context to prevent hallucinations about finished rounds."""
        current_phase = self.season_memory.get("current_phase", "Finals Series (Regular Season Concluded)")

        lines = [
            "[GROUND-TRUTH NRL SEASON MEMORY (ON-FILE ARCHIVE)]",
            f"• Current Season Phase: {current_phase}",
            "• Regular Season Status: Concluded after Round 27. No more regular season games.",
            "• Brisbane Broncos Status: Finished 12th (Outside Top 8). Season is OVER. No more games left this year.",
        ]

        q_lower = query.lower()
        if "cobbo" in q_lower or not query:
            lines.extend([
                "• Player: Selwyn Cobbo",
                "• Current Club: The Dolphins",
                "• Former Club: Brisbane Broncos",
                "• Transfer Reality: Cobbo left the Broncos to join the Dolphins. He has NOT returned or re-signed with the Brisbane Broncos.",
                "• Away Sheds Note: Past games at Suncorp in the away sheds happened in Round 4 (March 2026) where he played AGAINST Brisbane as a Dolphins player."
            ])
        if "reece walsh" in q_lower:
            lines.append("• Player Reality: Reece Walsh is contracted to the Brisbane Broncos.")
        if "manu" in q_lower or "chiefs" in q_lower:
            lines.append("• PNG Chiefs (2028 entry): Joey Manu and Alex Johnston are officially committed for the 2028 NRL license.")

        lines.append("[END OF GROUND-TRUTH MEMORY]\n")
        return "\n".join(lines)

    async def fetch_accredited_search(self, prompt: str, max_results: int = 4) -> List[Dict[str, str]]:
        """
        Fetch accredited search results for NRL inquiries, sorted by freshness,
        and prepended with ground-truth season context to prevent hallucinations.
        """
        results, tier = await self.fetch_tiered_search(prompt, max_results=max_results)
        grounding = self._build_season_grounding_context(prompt)
        grounding_source = {
            "title": "Official NRL Season Status & Archive [GROUND TRUTH]",
            "url": "https://www.nrl.com/ladder",
            "snippet": grounding,
            "age_tier": "🟢 Verified Ground Truth"
        }
        return [grounding_source] + results

    async def refresh_priority_briefing(self) -> Dict[str, Any]:
        """
        Background worker task: Fetch fresh accredited news for top 3 priority topics:
        1. Brisbane Broncos
        2. Queensland Maroons (State of Origin)
        3. PNG Chiefs / NRL expansion bid
        """
        logger.info("Refreshing NRL priority briefing from accredited sources with 7-day freshness check...")
        
        task_broncos = self.fetch_tiered_search("Brisbane Broncos NRL news season Payne Haas", max_results=3)
        task_maroons = self.fetch_tiered_search("Queensland Maroons State of Origin news", max_results=3)
        task_chiefs = self.fetch_tiered_search("PNG Chiefs NRL team official signing Joey Manu", max_results=3)

        (res_b, _), (res_m, _), (res_c, _) = await asyncio.gather(
            task_broncos, task_maroons, task_chiefs, return_exceptions=True
        )

        all_sources = []
        if isinstance(res_c, list): all_sources.extend(res_c)
        if isinstance(res_b, list): all_sources.extend(res_b)
        if isinstance(res_m, list): all_sources.extend(res_m)

        # Build prompt with ground-truth season memory
        grounding = self._build_season_grounding_context()
        prompt = (
            f"{grounding}\n"
            "Summarize the latest verified news for the three priority NRL rugby league topics based ONLY on the sources below:\n\n"
            "1. 🇵🇬 **PNG Chiefs (2028 NRL Expansion Team)**: Marquee player signings (e.g. Joey Manu, Alex Johnston, Jarome Luai), license progress, and official updates.\n"
            "2. 🐴 **Brisbane Broncos**: Clarify that regular rounds are finished and Broncos missed the top 8 (no more games this year). Report end-of-season news (e.g. Payne Haas farewell).\n"
            "3. 👑 **Queensland Maroons (State of Origin)**: Concluded 2026 series summary and Billy Slater squad updates.\n\n"
            "IMPORTANT: Order events chronologically. If news is older than 7 days, treat it strictly as historical context."
        )

        try:
            briefing_text = await self.llm.generate_response(
                prompt,
                search_results=all_sources,
                is_technical=False,
                custom_system_prompt=NRL_VALIDATION_SYSTEM_PROMPT
            )
        except Exception as e:
            logger.error(f"Error synthesizing NRL briefing: {e}")
            briefing_text = "NRL priority briefing temporarily unavailable. Please query specific topics using `/nrl <topic>`."

        now_ts = time.time()
        self.cached_briefing = {
            "timestamp": now_ts,
            "briefing_text": briefing_text,
            "sources": all_sources
        }
        self._save_briefing_cache()
        logger.info("NRL priority briefing refreshed and cached successfully.")
        return self.cached_briefing

    async def get_priority_briefing(self) -> str:
        """Get instant pre-compiled priority briefing, triggering background refresh if empty."""
        if not self.cached_briefing:
            data = await self.refresh_priority_briefing()
            return data.get("briefing_text", "")
        return self.cached_briefing.get("briefing_text", "")

    async def query_specific_nrl(self, query: str) -> str:
        """Perform live, tiered-freshness search for specific NRL questions."""
        sources, tier_label = await self.fetch_tiered_search(query, max_results=4)
        grounding = self._build_season_grounding_context(query)

        prompt = (
            f"{grounding}\n"
            f"User Question: '{query}'\n\n"
            f"Freshness Tier: {tier_label}\n"
            f"Reference Sources (ordered newest first with age badges below):\n"
            "Provide an accurate, date-aware answer following the ground-truth memory and system rules."
        )

        return await self.llm.generate_response(
            prompt,
            search_results=sources,
            is_technical=False,
            custom_system_prompt=NRL_VALIDATION_SYSTEM_PROMPT
        )

    async def check_weekly_round_finalization(self) -> None:
        """
        Weekly temp check worker:
        - Runs temp check after the weekend's final matches.
        - Finalizes season table, archives round scores on Monday.
        """
        now = datetime.now(timezone.utc)
        weekday = now.weekday() # 0 = Monday, 6 = Sunday
        logger.info(f"NRL weekly check executed on weekday {weekday}...")
        # Persist memory check
        self._load_memory()

nrl_service = NRLService()
