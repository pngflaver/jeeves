import logging
import asyncio
import re
import urllib.parse
from typing import Dict, Any, List, Optional
import httpx
from services.search_service import search_web

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"(\+?\d{1,4}[-\s]?\(?\d{1,4}\)?[-\s]?\d{3,4}[-\s]?\d{3,4})")
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")

class PlacesService:
    """
    Local Place & Business Directory Service using OpenStreetMap (Nominatim)
    and live web search for verified addresses, operating hours, phone numbers,
    and navigation map links without requiring Google API keys.
    """

    def __init__(self):
        self.osm_headers = {
            "User-Agent": "JeevesTelegramBot/1.0 (Linux; x86_64; +https://github.com/pngflaver/jeeves)"
        }

    async def _query_osm(self, query: str) -> Optional[Dict[str, Any]]:
        """Query OpenStreetMap Nominatim for venue/business metadata and coordinates."""
        clean_q = query.strip()
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": clean_q,
            "format": "json",
            "addressdetails": 1,
            "extratags": 1,
            "limit": 3
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params, headers=self.osm_headers)
                if resp.status_code == 200:
                    items = resp.json()
                    if items:
                        return items[0]
        except Exception as e:
            logger.warning(f"Nominatim lookup error for '{query}': {e}")

        # If full query didn't match, try simplifying (strip common noise words)
        sub_q = re.sub(r"\b(hours|opening times|opening hours|trading hours|clinic|center|centre|store|shop)\b", "", clean_q, flags=re.I).strip()
        if sub_q and sub_q != clean_q:
            try:
                params["q"] = sub_q
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(url, params=params, headers=self.osm_headers)
                    if resp.status_code == 200:
                        items = resp.json()
                        if items:
                            return items[0]
            except Exception:
                pass

        return None

    def _extract_hours_from_snippets(self, snippets: List[Dict[str, str]]) -> str:
        """Extract operating and trading hours statements from web text snippets."""
        all_text = " ".join([r.get("snippet", "") + " " + r.get("title", "") for r in snippets])
        sentences = re.split(r"[\.\n]\s*", all_text)
        
        extracted_hours = []
        for s in sentences:
            clean_s = s.strip()
            # Must mention time indications and days/hours
            if re.search(r"\b(daily|hours?|open|closed|closing|trades?)\b", clean_s, re.I):
                if re.search(r"\b(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|24/7|8am|8pm)\b", clean_s, re.I):
                    if len(clean_s) <= 220 and clean_s not in extracted_hours:
                        extracted_hours.append(clean_s)

        if extracted_hours:
            # Return top 1-2 distinct sentences
            return "\n".join([f"• {h}." if not h.endswith(".") else f"• {h}" for h in extracted_hours[:2]])
        
        # General fallback if explicit hour numbers weren't matched
        return "Operating hours not explicitly published online. Please call ahead or verify via the map/website."

    async def lookup_place(self, raw_query: str) -> Dict[str, Any]:
        """
        Look up a place or business, pulling location from OpenStreetMap
        and operating hours / contact info from live web search.
        """
        clean_q = raw_query.strip()
        
        # 1. Run OSM Nominatim query in parallel with live search
        osm_task = self._query_osm(clean_q)
        search_task = search_web(f"{clean_q} opening hours trading hours phone address", max_results=4)
        
        osm_item, search_results = await asyncio.gather(osm_task, search_task, return_exceptions=True)
        if isinstance(osm_item, Exception):
            osm_item = None
        if isinstance(search_results, Exception):
            search_results = []

        # 2. Extract OpenStreetMap metadata
        address = ""
        phone = ""
        email = ""
        website = ""
        lat = None
        lon = None
        place_title = clean_q.title()

        if osm_item and isinstance(osm_item, dict):
            place_title = osm_item.get("name") or osm_item.get("display_name", "").split(",")[0] or place_title
            address = osm_item.get("display_name", "")
            lat = osm_item.get("lat")
            lon = osm_item.get("lon")
            extratags = osm_item.get("extratags", {})
            phone = extratags.get("phone") or extratags.get("contact:phone", "")
            email = extratags.get("email") or extratags.get("contact:email", "")
            website = extratags.get("website") or extratags.get("contact:website", "")
            osm_hours = extratags.get("opening_hours", "")
        else:
            osm_hours = ""

        # 3. Process web search results for hours and contact info
        web_text = " ".join([r.get("snippet", "") + " " + r.get("title", "") for r in search_results])
        
        if not phone:
            phones_found = PHONE_REGEX.findall(web_text)
            if phones_found:
                # filter out non-phone numbers (e.g. 4-digit years)
                valid_phones = [p.strip() for p in phones_found if len(p.strip()) >= 7 and not p.strip().startswith(("19", "20"))]
                if valid_phones:
                    phone = valid_phones[0]

        if not email:
            emails_found = EMAIL_REGEX.findall(web_text)
            if emails_found:
                valid = [e for e in emails_found if not e.endswith((".png", ".jpg", ".svg", ".js"))]
                if valid:
                    email = valid[0]

        if not website:
            for r in search_results:
                url = r.get("url", "")
                if url and not any(skip in url for skip in ["facebook.com", "tripadvisor.com", "yelp.com", "linkedin.com"]):
                    website = url
                    break

        # 4. Extract Operating Hours
        if osm_hours:
            operating_hours = f"• {osm_hours}"
        else:
            operating_hours = self._extract_hours_from_snippets(search_results)

        # 5. Build Map Links (OpenStreetMap and Google Maps Web Search)
        encoded_q = urllib.parse.quote_plus(clean_q)
        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_q}"
        
        if lat and lon:
            osm_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"
        else:
            osm_url = f"https://www.openstreetmap.org/search?query={encoded_q}"

        return {
            "query": clean_q,
            "title": place_title,
            "address": address or "Address details available via map navigation.",
            "operating_hours": operating_hours,
            "phone": phone,
            "email": email,
            "website": website,
            "google_maps_url": google_maps_url,
            "osm_url": osm_url,
            "lat": lat,
            "lon": lon
        }

    def format_place_card(self, data: Dict[str, Any]) -> str:
        """Format structured Telegram place/venue card with operating hours and map links."""
        title = data.get("title", "Local Place")
        address = data.get("address", "")
        hours = data.get("operating_hours", "")
        phone = data.get("phone", "")
        email = data.get("email", "")
        website = data.get("website", "")
        gmaps_url = data.get("google_maps_url", "")
        osm_url = data.get("osm_url", "")

        lines = [
            f"📍 **{title}**\n",
            f"⏰ **Operating Hours & Schedule:**",
            f"{hours}\n"
        ]

        # Contact information
        contacts = []
        if phone:
            contacts.append(f"• 📞 **Phone:** `{phone}`")
        if email:
            contacts.append(f"• ✉️ **Email:** `{email}`")
        if website:
            contacts.append(f"• 🌐 **Website:** {website}")

        if contacts:
            lines.append("📞 **Contact Details:**")
            lines.extend(contacts)
            lines.append("")

        # Address
        if address and address != "Address details available via map navigation.":
            lines.append("📌 **Location / Address:**")
            lines.append(f"• {address}\n")

        # Map Links
        lines.append("🗺️ **Map & Navigation:**")
        if gmaps_url:
            lines.append(f"• 📍 **Google Maps:** {gmaps_url}")
        if osm_url:
            lines.append(f"• 🌐 **OpenStreetMap:** {osm_url}")

        return "\n".join(lines)

places_service = PlacesService()
