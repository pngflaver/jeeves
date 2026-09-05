import os
import json
import time
import logging
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from services.search_service import search_web
from services.llm_engine import LLMEngine
import config

logger = logging.getLogger(__name__)

# Trusted & Accredited Rugby League Media Outlets
ACCREDITED_DOMAINS = [
    "nrl.com",
    "foxsports.com.au",
    "abc.net.au",
    "smh.com.au",
    "qrl.com.au",
    "broncos.com.au",
    "postcourier.com.pg",
    "thenational.com.pg"
]

SITE_FILTER = "site:nrl.com OR site:foxsports.com.au OR site:abc.net.au OR site:qrl.com.au OR site:postcourier.com.pg OR site:thenational.com.pg"

NRL_QUERY_PATTERN = re.compile(
    r"\b(nrl|rugby league|broncos|brisbane broncos|maroons|state of origin|origin|png chiefs|png nrl|kumuls|png hunters|reece walsh|billy slater|kevin walters)\b",
    re.IGNORECASE
)

NRL_VALIDATION_SYSTEM_PROMPT = (
    "You are the official NRL (National Rugby League) specialist for Jeeves.\n\n"
    "CRITICAL FACT-CHECKING & SOURCE VALIDATION RULES:\n"
    "1. You must ONLY report facts verified in the provided accredited reference sources (NRL.com, Fox Sports, ABC, QRL, Post-Courier, The National).\n"
    "2. If an inquiry mentions player transfers, expansion news, or team selections that are NOT officially confirmed by the club or NRL, you MUST explicitly label them as '⚠️ [Speculation / Unconfirmed Rumor]'.\n"
    "3. Completely reject and debunk unverified social media rumors (e.g. unconfirmed Facebook posts).\n"
    "4. Cite the verified source outlet or official announcement for major claims.\n"
    "5. Format output with clean markdown headings and bullet points."
)

class NRLService:
    """
    NRL Intelligence Service providing verified, rumor-filtered updates
    with priority focus on Brisbane Broncos, Queensland Maroons, and the PNG Chiefs.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_dir = data_dir or (Path(__file__).resolve().parent.parent / "data")
        self.cache_file = self.base_dir / "nrl_cache.json"
        self.llm = LLMEngine()
        self.cached_briefing: Optional[Dict[str, Any]] = None
        self._load_cache()

    def _load_cache(self) -> None:
        """Load pre-compiled briefing from disk cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cached_briefing = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL cache: {e}")

    def _save_cache(self) -> None:
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

    async def fetch_accredited_search(self, topic: str, max_results: int = 4) -> List[Dict[str, str]]:
        """Fetch search results strictly targeted at accredited rugby league outlets."""
        query = f"{topic} ({SITE_FILTER})"
        return await search_web(query, max_results=max_results)

    async def refresh_priority_briefing(self) -> Dict[str, Any]:
        """
        Background worker task: Fetch fresh accredited news for top 3 priority topics:
        1. Brisbane Broncos
        2. Queensland Maroons (State of Origin)
        3. PNG Chiefs / NRL expansion bid
        """
        logger.info("Refreshing NRL priority briefing from accredited sources...")
        
        # Parallel searches for the 3 priority topics
        task_broncos = self.fetch_accredited_search("Brisbane Broncos NRL news squad match 2026", max_results=3)
        task_maroons = self.fetch_accredited_search("Queensland Maroons State of Origin news 2026", max_results=3)
        task_chiefs = self.fetch_accredited_search("PNG Chiefs NRL team official signing news 2026", max_results=3)

        res_broncos, res_maroons, res_chiefs = await asyncio.gather(
            task_broncos, task_maroons, task_chiefs, return_exceptions=True
        )

        all_sources = []
        if isinstance(res_chiefs, list): all_sources.extend(res_chiefs)
        if isinstance(res_broncos, list): all_sources.extend(res_broncos)
        if isinstance(res_maroons, list): all_sources.extend(res_maroons)

        # Synthesize verified priority briefing via LLM
        prompt = (
            "Summarize the latest verified news for the three priority NRL rugby league topics based ONLY on the sources below:\n\n"
            "1. 🇵🇬 **PNG Chiefs (2028 NRL Expansion Team)**: Marquee player signings (e.g. Joey Manu, Alex Johnston, Jarome Luai), license progress, and official updates.\n"
            "2. 🐴 **Brisbane Broncos**: Recent match results, key player updates (e.g. Reece Walsh, injuries), and squad news.\n"
            "3. 👑 **Queensland Maroons (State of Origin)**: Latest series outcomes, Billy Slater selections, and squad news.\n\n"
            "IMPORTANT: If any transfer or claim is speculative and unconfirmed officially, clearly flag it with ⚠️ [Speculation / Unconfirmed]."
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
        self._save_cache()
        logger.info("NRL priority briefing refreshed and cached successfully.")
        return self.cached_briefing

    async def get_priority_briefing(self) -> str:
        """Get instant pre-compiled priority briefing, triggering background refresh if empty."""
        if not self.cached_briefing:
            data = await self.refresh_priority_briefing()
            return data.get("briefing_text", "")
        return self.cached_briefing.get("briefing_text", "")

    async def query_specific_nrl(self, query: str) -> str:
        """Perform live, rumor-filtered targeted search for specific NRL questions."""
        sources = await self.fetch_accredited_search(query, max_results=4)
        if not sources:
            # Fallback to broader search with rugby league context
            sources = await search_web(f"{query} NRL rugby league official", max_results=4)

        prompt = (
            f"Provide an accurate, verified summary for the NRL inquiry: '{query}'.\n"
            f"Strictly adhere to verified facts. If any claims from social media are unconfirmed, flag them clearly."
        )

        return await self.llm.generate_response(
            prompt,
            search_results=sources,
            is_technical=False,
            custom_system_prompt=NRL_VALIDATION_SYSTEM_PROMPT
        )

nrl_service = NRLService()
