import logging
import asyncio
from typing import List, Dict, Optional
import httpx
from ddgs import DDGS
import config

logger = logging.getLogger(__name__)

async def search_duckduckgo(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Execute asynchronous DuckDuckGo search in a thread executor."""
    def _sync_search():
        results = []
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))
                for r in raw_results:
                    title = r.get("title", "").strip()
                    href = r.get("href", "").strip()
                    body = r.get("body", "").strip()
                    if title and href:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": body
                        })
        except Exception as e:
            logger.error(f"DuckDuckGo search error for '{query}': {e}")
        return results

    return await asyncio.to_thread(_sync_search)

async def search_brave(query: str, api_key: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Search using Brave Search API if API key is configured."""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }
    params = {"q": query, "count": max_results}
    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("web", {}).get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", "")
                    })
    except Exception as e:
        logger.error(f"Brave search error for '{query}': {e}")
    return results

async def search_web(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Search the live web with provider fallback (Brave API -> DuckDuckGo).
    """
    # 1. Use Brave Search API if key provided
    if config.BRAVE_SEARCH_API_KEY:
        results = await search_brave(query, config.BRAVE_SEARCH_API_KEY, max_results=max_results)
        if results:
            return results

    # 2. Default to DuckDuckGo (Free, zero API key)
    return await search_duckduckgo(query, max_results=max_results)

async def search_hardware_lifecycle(device_name: str, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Specialized query formulation for hardware end-of-life, end-of-support, and datasheets.
    """
    query = f"{device_name} end of life EOL EOS EOSL lifecycle datasheet"
    return await search_web(query, max_results=max_results)
