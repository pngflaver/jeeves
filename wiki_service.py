import logging
import re
from typing import Optional, Dict, List
import httpx

logger = logging.getLogger(__name__)

WIKI_SEARCH_API = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
USER_AGENT = "TelegramLLMBot/1.0 (https://t.me/pgjeevesbot; contact: admin@localhost)"

STOPWORDS = {
    "what", "is", "how", "much", "in", "a", "an", "the", "of", "for",
    "to", "and", "or", "who", "where", "when", "why", "can", "you",
    "tell", "me", "about", "explain", "does", "did", "do", "are", "were"
}

def is_article_relevant(query: str, title: str, extract: str) -> bool:
    """
    Check if the retrieved Wikipedia article has sufficient keyword overlap
    with the meaningful words in the user query.
    """
    query_tokens = [
        w.lower() for w in re.findall(r"[a-zA-Z0-9]+", query)
        if len(w) >= 3 and w.lower() not in STOPWORDS
    ]
    if not query_tokens:
        return True

    text_corpus = f"{title} {extract}".lower()
    matches = [w for w in query_tokens if w in text_corpus]

    # Require at least 50% keyword match or minimum 2 matched significant keywords
    match_ratio = len(matches) / len(query_tokens)
    is_match = match_ratio >= 0.5 or (len(query_tokens) >= 3 and len(matches) >= 2)

    if not is_match:
        logger.info(
            f"Wikipedia result '{title}' discarded as irrelevant for query '{query}' "
            f"(matched {matches} out of {query_tokens}, ratio: {match_ratio:.2f})"
        )
    return is_match

async def search_wikipedia(query: str) -> Optional[Dict[str, str]]:
    """
    Search Wikipedia for a query and return title, extract summary, and URL
    ONLY if the result is genuinely relevant to the query.
    """
    clean_query = query.strip()
    if not clean_query or len(clean_query) < 2:
        return None

    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=4.0) as client:
            # 1. Search for closest Wikipedia article title
            params = {
                "action": "query",
                "list": "search",
                "srsearch": clean_query,
                "format": "json",
                "utf8": 1,
                "srlimit": 1,
            }
            res = await client.get(WIKI_SEARCH_API, params=params)
            if res.status_code != 200:
                return None

            data = res.json()
            search_items = data.get("query", {}).get("search", [])
            if not search_items:
                return None

            title = search_items[0].get("title")
            if not title:
                return None

            # 2. Fetch summary extract for the matched article
            summary_url = f"{WIKI_SUMMARY_API}{title.replace(' ', '_')}"
            summary_res = await client.get(summary_url)
            if summary_res.status_code != 200:
                return None

            sdata = summary_res.json()
            extract = sdata.get("extract", "").strip()
            page_url = sdata.get("content_urls", {}).get("desktop", {}).get("page", "")

            if not extract or not page_url:
                return None

            # 3. Check relevance before accepting
            if not is_article_relevant(clean_query, title, extract):
                return None

            return {
                "title": title,
                "extract": extract,
                "url": page_url,
            }
    except Exception as e:
        logger.warning(f"Wikipedia search failed for '{clean_query}': {e}")
        return None
