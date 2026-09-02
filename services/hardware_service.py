import os
import json
import logging
import asyncio
from typing import List, Dict, Optional
import config
from .search_service import search_hardware_lifecycle

logger = logging.getLogger(__name__)

class HardwareService:
    def __init__(
        self,
        config_file: str = config.HARDWARE_CONFIG_FILE,
        cache_file: str = config.HARDWARE_CACHE_FILE
    ):
        self.config_file = config_file
        self.cache_file = cache_file
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached hardware data from disk."""
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

    def get_tracked_devices(self) -> List[str]:
        """Read all active device names from hardware.txt."""
        if not os.path.exists(self.config_file):
            return []

        devices = []
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        devices.append(line)
        except Exception as e:
            logger.error(f"Error reading hardware list {self.config_file}: {e}")
        return devices

    def match_device_in_query(self, query: str) -> Optional[str]:
        """
        Check if the query matches any tracked device in hardware.txt.
        Case-insensitive matching.
        """
        query_lower = query.lower()
        devices = self.get_tracked_devices()
        for dev in devices:
            if dev.lower() in query_lower:
                return dev
            # Try sub-model match e.g. '40f' in 'fortigate 40f'
            parts = dev.lower().split()
            if len(parts) >= 2 and all(p in query_lower for p in parts):
                return dev
        return None

    def get_cached_info(self, device_name: str) -> Optional[Dict]:
        """Get cached search/lifecycle data for a device if present."""
        return self.cache.get(device_name.lower())

    def store_device_info(self, device_name: str, sources: List[Dict[str, str]]) -> None:
        """Cache search sources for a device."""
        self.cache[device_name.lower()] = {
            "device": device_name,
            "sources": sources,
            "updated_at": asyncio.get_event_loop().time()
        }
        self._save_cache()

    async def fetch_and_cache(self, device_name: str) -> List[Dict[str, str]]:
        """Perform live search for a device and store in cache."""
        sources = await search_hardware_lifecycle(device_name)
        if sources:
            self.store_device_info(device_name, sources)
        return sources

    async def sync_all(self) -> Dict[str, int]:
        """
        Scan all devices in hardware.txt and populate cache.
        """
        devices = self.get_tracked_devices()
        success = 0
        failed = 0
        for dev in devices:
            try:
                sources = await self.fetch_and_cache(dev)
                if sources:
                    success += 1
                else:
                    failed += 1
                await asyncio.sleep(1.0)  # Gentle delay between searches
            except Exception as e:
                logger.error(f"Failed syncing device '{dev}': {e}")
                failed += 1
        return {"total": len(devices), "synced": success, "failed": failed}

hardware_service = HardwareService()
