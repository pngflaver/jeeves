import os
import json
import logging
import asyncio
from typing import List, Dict, Optional
import config
from .search_service import search_web

logger = logging.getLogger(__name__)

class SoftwareService:
    def __init__(
        self,
        config_file: str = config.SOFTWARE_CONFIG_FILE,
        cache_file: str = config.SOFTWARE_CACHE_FILE
    ):
        self.config_file = config_file
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached software data from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read cache file {self.cache_file}: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def _save_cache(self) -> None:
        """Persist cache to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache file {self.cache_file}: {e}")

    def get_tracked_software(self) -> List[str]:
        """Read all active software entries from software.txt."""
        if not os.path.exists(self.config_file):
            return []

        items = []
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        items.append(line)
        except Exception as e:
            logger.error(f"Error reading software list {self.config_file}: {e}")
        return items

    def match_software_in_query(self, query: str) -> Optional[str]:
        """
        Check if the query matches any tracked software in software.txt.
        Case-insensitive matching.
        """
        query_lower = query.lower()
        items = self.get_tracked_software()
        for item in items:
            if item.lower() in query_lower:
                return item
            # Sub-match (e.g., 'fortios 7.2' in 'fortios 7.2.4')
            parts = item.lower().split()
            if len(parts) >= 2 and all(p in query_lower for p in parts):
                return item
        return None

    def get_cached_info(self, software_name: str) -> Optional[Dict]:
        """Get cached search/lifecycle data for software if present."""
        return self.cache.get(software_name.lower().strip())

    def store_software_info(self, software_name: str, sources: List[Dict[str, str]]) -> None:
        """Cache search sources for software."""
        self.cache[software_name.lower().strip()] = {
            "software": software_name,
            "sources": sources,
            "updated_at": asyncio.get_event_loop().time()
        }
        self._save_cache()

    async def fetch_and_cache(self, software_name: str) -> List[Dict[str, str]]:
        """Perform live search for software lifecycle/documentation and store in cache."""
        query = f"{software_name} release lifecycle end of support EOL upgrade path documentation"
        sources = await search_web(query, max_results=4)
        if sources:
            self.store_software_info(software_name, sources)
        return sources

    async def sync_all(self) -> Dict[str, int]:
        """
        Scan all software in software.txt and populate cache.
        """
        items = self.get_tracked_software()
        success = 0
        failed = 0
        for item in items:
            try:
                sources = await self.fetch_and_cache(item)
                if sources:
                    success += 1
                else:
                    failed += 1
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"Failed syncing software '{item}': {e}")
                failed += 1
        return {"total": len(items), "synced": success, "failed": failed}

software_service = SoftwareService()
