import logging
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import httpx
from ddgs import DDGS
import config

logger = logging.getLogger(__name__)

def parse_snippet_timestamp(text: str) -> float:
    """Parse relative or explicit date strings from snippet text into unix timestamp."""
    now = datetime.now(timezone.utc)

    # 1. Relative dates: 'X hours/days/weeks/months ago'
    m_rel = re.search(r"\b(\d+)\s*(hours?|days?|weeks?|months?)\s*ago\b", text, re.I)
    if m_rel:
        val = int(m_rel.group(1))
        unit = m_rel.group(2).lower()
        if "hour" in unit: return (now - timedelta(hours=val)).timestamp()
        if "day" in unit: return (now - timedelta(days=val)).timestamp()
        if "week" in unit: return (now - timedelta(weeks=val)).timestamp()
        if "month" in unit: return (now - timedelta(days=val * 30)).timestamp()

    # 2. Explicit dates: 'Mon DD, YYYY' (e.g. 'Jun 23, 2026')
    m_date = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b", text, re.I)
    if m_date:
        month_str, day_str, year_str = m_date.group(1)[:3].title(), m_date.group(2), m_date.group(3)
        try:
            dt = datetime.strptime(f"{month_str} {day_str} {year_str}", "%b %d %Y").replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass

    # 3. ISO dates: 'YYYY-MM-DD'
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m_iso:
        try:
            dt = datetime.strptime(m_iso.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass

    return 0.0

def enrich_and_sort_by_date(results: List[Dict[str, str]], newest_first: bool = True) -> List[Dict[str, str]]:
    """Enrich sources with publication timestamps and sort newest-first."""
    now_ts = datetime.now(timezone.utc).timestamp()
    enriched = []
    for r in results:
        content = r.get("snippet", "") + " " + r.get("title", "")
        ts = parse_snippet_timestamp(content)
        r_copy = dict(r)
        r_copy["timestamp"] = ts
        if ts > 0:
            age_days = (now_ts - ts) / 86400
            if age_days <= 7:
                r_copy["age_tier"] = "🟢 [Current / Past 7 Days]"
            elif age_days <= 30:
                r_copy["age_tier"] = "🟡 [Past Month]"
            else:
                r_copy["age_tier"] = "🔴 [Historical (> 30 days ago)]"
            r_copy["date_str"] = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d, %Y")
        else:
            r_copy["age_tier"] = "⚪ [Undated / General]"
            r_copy["date_str"] = "Recent"
        enriched.append(r_copy)

    if newest_first:
        # Items with timestamp > 0 sorted descending, undated items at end
        enriched.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return enriched

async def search_duckduckgo(query: str, max_results: int = 4, timelimit: Optional[str] = None) -> List[Dict[str, str]]:
    """Execute asynchronous DuckDuckGo search in a thread executor with optional timelimit ('d', 'w', 'm', 'y')."""
    def _sync_search():
        results = []
        try:
            with DDGS() as ddgs:
                kwargs = {"max_results": max_results}
                if timelimit:
                    kwargs["timelimit"] = timelimit
                raw_results = list(ddgs.text(query, **kwargs))
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
            logger.error(f"DuckDuckGo search error for '{query}' (timelimit={timelimit}): {e}")
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

async def search_web(query: str, max_results: int = 4, timelimit: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Search the live web with provider fallback (Brave API -> DuckDuckGo)
    and optional timelimit ('d'=day, 'w'=week, 'm'=month).
    """
    # 1. Use Brave Search API if key provided (does not support timelimit directly in basic tier)
    if config.BRAVE_SEARCH_API_KEY and not timelimit:
        results = await search_brave(query, config.BRAVE_SEARCH_API_KEY, max_results=max_results)
        if results:
            return results

    # 2. Default to DuckDuckGo (Free, zero API key, supports timelimit 'w' / 'm')
    return await search_duckduckgo(query, max_results=max_results, timelimit=timelimit)

async def search_hardware_lifecycle(device_name: str, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Specialized query formulation for hardware end-of-life, end-of-support, and datasheets.
    """
    query = f"{device_name} end of life EOL EOS EOSL lifecycle datasheet"
    return await search_web(query, max_results=max_results)
