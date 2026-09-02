import re
import logging
from typing import Optional, Dict, Tuple, List
from .search_service import search_web

logger = logging.getLogger(__name__)

# Common IATA Airport Codes
AIRPORT_CODES = {
    # Papua New Guinea
    "POM": {"name": "Port Moresby (Jacksons Intl)", "country": "Papua New Guinea", "cities": ["port moresby", "pom", "jacksons"]},
    "LAE": {"name": "Lae (Nadzab Airport)", "country": "Papua New Guinea", "cities": ["lae", "nadzab"]},
    "RAB": {"name": "Rabaul (Tokua Airport)", "country": "Papua New Guinea", "cities": ["rabaul", "tokua", "kokopo"]},
    "MAG": {"name": "Madang Airport", "country": "Papua New Guinea", "cities": ["madang"]},
    "HGU": {"name": "Mount Hagen Airport", "country": "Papua New Guinea", "cities": ["mount hagen", "mt hagen", "hagen"]},
    "GKA": {"name": "Goroka Airport", "country": "Papua New Guinea", "cities": ["goroka"]},
    "WWK": {"name": "Wewak Airport", "country": "Papua New Guinea", "cities": ["wewak", "boram"]},
    "KVG": {"name": "Kavieng Airport", "country": "Papua New Guinea", "cities": ["kavieng"]},
    "MAS": {"name": "Manus Island (Momote)", "country": "Papua New Guinea", "cities": ["manus", "momote", "lorengau"]},
    "BUA": {"name": "Buka Airport", "country": "Papua New Guinea", "cities": ["buka", "bougainville"]},
    "KRI": {"name": "Kikori Airport", "country": "Papua New Guinea", "cities": ["kikori"]},
    "DAU": {"name": "Daru Airport", "country": "Papua New Guinea", "cities": ["daru"]},
    "TBG": {"name": "Tabubil Airport", "country": "Papua New Guinea", "cities": ["tabubil"]},

    # Australia & Pacific
    "BNE": {"name": "Brisbane International", "country": "Australia", "cities": ["brisbane", "bne"]},
    "CNS": {"name": "Cairns International", "country": "Australia", "cities": ["cairns", "cns"]},
    "SYD": {"name": "Sydney Kingsford Smith", "country": "Australia", "cities": ["sydney", "syd"]},
    "MEL": {"name": "Melbourne Tullamarine", "country": "Australia", "cities": ["melbourne", "mel"]},
    "PER": {"name": "Perth International", "country": "Australia", "cities": ["perth", "per"]},
    "ADL": {"name": "Adelaide International", "country": "Australia", "cities": ["adelaide", "adl"]},
    "DRW": {"name": "Darwin International", "country": "Australia", "cities": ["darwin", "drw"]},
    "NAN": {"name": "Nadi International", "country": "Fiji", "cities": ["nadi", "fiji", "nan"]},
    "HIR": {"name": "Honiara Henderson Intl", "country": "Solomon Islands", "cities": ["honiara", "solomon islands", "solomons", "hir"]},
    "VLI": {"name": "Port Vila Bauerfield Intl", "country": "Vanuatu", "cities": ["port vila", "vanuatu", "vli"]},
    "AKL": {"name": "Auckland International", "country": "New Zealand", "cities": ["auckland", "akl"]},

    # Asia & Global Hubs
    "SIN": {"name": "Singapore Changi", "country": "Singapore", "cities": ["singapore", "changi", "sin"]},
    "MNL": {"name": "Manila Ninoy Aquino Intl", "country": "Philippines", "cities": ["manila", "mnl"]},
    "HKG": {"name": "Hong Kong International", "country": "Hong Kong", "cities": ["hong kong", "hkg"]},
    "NRT": {"name": "Tokyo Narita", "country": "Japan", "cities": ["tokyo", "narita", "nrt"]},
    "HND": {"name": "Tokyo Haneda", "country": "Japan", "cities": ["haneda", "hnd"]},
    "KUL": {"name": "Kuala Lumpur International", "country": "Malaysia", "cities": ["kuala lumpur", "kul"]},
    "BKK": {"name": "Bangkok Suvarnabhumi", "country": "Thailand", "cities": ["bangkok", "bkk"]},
    "DPS": {"name": "Bali Denpasar", "country": "Indonesia", "cities": ["bali", "denpasar", "dps"]},
    "DXB": {"name": "Dubai International", "country": "United Arab Emirates", "cities": ["dubai", "dxb"]},
    "DOH": {"name": "Doha Hamad International", "country": "Qatar", "cities": ["doha", "doh"]},
    "LHR": {"name": "London Heathrow", "country": "United Kingdom", "cities": ["london", "heathrow", "lhr"]},
    "LAX": {"name": "Los Angeles International", "country": "United States", "cities": ["los angeles", "lax"]},
    "SFO": {"name": "San Francisco International", "country": "United States", "cities": ["san francisco", "sfo"]},
    "JFK": {"name": "New York John F. Kennedy", "country": "United States", "cities": ["new york", "jfk"]},
}

# Known key routes with verified direct airline operations
POPULAR_ROUTES = {
    ("POM", "BNE"): {
        "origin_name": "Port Moresby (POM)",
        "dest_name": "Brisbane (BNE)",
        "airlines": ["Air Niugini (PX)", "Qantas (QF)"],
        "duration": "approx. 3 hours 15 minutes",
        "distance": "2,084 km (1,295 miles)",
        "frequency": "Daily direct flights (typically morning PX3 / QF57 and afternoon PX5 flights)",
        "direct": True
    },
    ("BNE", "POM"): {
        "origin_name": "Brisbane (BNE)",
        "dest_name": "Port Moresby (POM)",
        "airlines": ["Air Niugini (PX)", "Qantas (QF)"],
        "duration": "approx. 3 hours 15 minutes",
        "distance": "2,084 km (1,295 miles)",
        "frequency": "Daily direct flights (morning and afternoon)",
        "direct": True
    },
    ("POM", "CNS"): {
        "origin_name": "Port Moresby (POM)",
        "dest_name": "Cairns (CNS)",
        "airlines": ["Air Niugini (PX)"],
        "duration": "approx. 1 hour 30 minutes",
        "distance": "840 km (522 miles)",
        "frequency": "Multiple flights weekly / daily",
        "direct": True
    },
    ("POM", "SYD"): {
        "origin_name": "Port Moresby (POM)",
        "dest_name": "Sydney (SYD)",
        "airlines": ["Air Niugini (PX)", "Qantas (QF)"],
        "duration": "approx. 3 hours 55 minutes",
        "distance": "2,750 km (1,708 miles)",
        "frequency": "Direct and connecting via BNE/CNS",
        "direct": True
    },
    ("POM", "SIN"): {
        "origin_name": "Port Moresby (POM)",
        "dest_name": "Singapore (SIN)",
        "airlines": ["Air Niugini (PX)"],
        "duration": "approx. 6 hours 45 minutes",
        "distance": "4,925 km (3,060 miles)",
        "frequency": "Multiple weekly direct flights",
        "direct": True
    },
    ("POM", "MNL"): {
        "origin_name": "Port Moresby (POM)",
        "dest_name": "Manila (MNL)",
        "airlines": ["Air Niugini (PX)", "Philippine Airlines (PR)"],
        "duration": "approx. 5 hours 30 minutes",
        "distance": "3,850 km (2,392 miles)",
        "frequency": "Regular weekly flights",
        "direct": True
    }
}

FLIGHT_INTENT_PATTERN = re.compile(
    r"\b(flight|flights|airline|airlines|flying|fly|plane|schedule|timetable|pom to bne|bne to pom|"
    r"port moresby to brisbane|brisbane to port moresby|next flight)\b",
    re.IGNORECASE
)

class FlightService:
    def is_flight_query(self, query: str) -> bool:
        """Check if query is asking for flight routes or airlines."""
        return bool(FLIGHT_INTENT_PATTERN.search(query))

    def resolve_airport(self, name_or_code: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve airport code and full name."""
        cleaned = name_or_code.strip().upper()
        if cleaned in AIRPORT_CODES:
            return cleaned, AIRPORT_CODES[cleaned]["name"]

        # Search by city or airport name
        lowered = name_or_code.strip().lower()
        for code, data in AIRPORT_CODES.items():
            if any(city in lowered for city in data.get("cities", [])) or lowered in data["name"].lower():
                return code, data["name"]
        return None, None

    def extract_route(self, query: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Extract origin and destination from query.
        Returns: (origin_code, origin_name, dest_code, dest_name)
        """
        lowered = query.lower()

        # 1. Pattern: from <Origin> to <Destination>
        from_to_match = re.search(r"\b(?:from\s+)?([a-zA-Z\s]{2,20}?)\s+(?:to|->|—|-)\s+([a-zA-Z\s]{2,20}?)(?:\s+flight|\s+airline|\s+schedule|\?|$|\.)", query, re.IGNORECASE)
        if from_to_match:
            orig_raw, dest_raw = from_to_match.group(1).strip(), from_to_match.group(2).strip()
            # Clean leading 'flights ' or 'flight '
            orig_raw = re.sub(r"^(?:flights?\s+|find\s+(?:the\s+)?(?:next\s+)?flights?\s+)", "", orig_raw, flags=re.IGNORECASE).strip()
            orig_code, orig_name = self.resolve_airport(orig_raw)
            dest_code, dest_name = self.resolve_airport(dest_raw)
            if orig_code and dest_code:
                return orig_code, orig_name, dest_code, dest_name

        # 2. Scanning query for recognized city / airport tokens by appearance order
        found_airports = []
        for code, data in AIRPORT_CODES.items():
            for alias in [code.lower()] + data.get("cities", []):
                pattern = rf"\b{re.escape(alias)}\b"
                match = re.search(pattern, lowered)
                if match:
                    found_airports.append((match.start(), code, data["name"]))
                    break

        found_airports.sort(key=lambda x: x[0])
        # Deduplicate sequential identical codes
        unique_airports = []
        for item in found_airports:
            if not unique_airports or unique_airports[-1][1] != item[1]:
                unique_airports.append(item)

        if len(unique_airports) >= 2:
            return unique_airports[0][1], unique_airports[0][2], unique_airports[1][1], unique_airports[1][2]

        return None, None, None, None

    async def get_flight_context(self, query: str) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Retrieve structured flight route information and real-time live search context.
        """
        orig_code, orig_name, dest_code, dest_name = self.extract_route(query)
        sources = []

        # 1. Check known popular routes database
        if orig_code and dest_code and (orig_code, dest_code) in POPULAR_ROUTES:
            route_data = POPULAR_ROUTES[(orig_code, dest_code)]
            sources.append({
                "title": f"Direct Route: {route_data['origin_name']} to {route_data['dest_name']}",
                "url": f"https://www.google.com/travel/flights?q=flights+from+{orig_code}+to+{dest_code}",
                "snippet": (
                    f"Route: {route_data['origin_name']} -> {route_data['dest_name']}. "
                    f"Airlines operating direct flights: {', '.join(route_data['airlines'])}. "
                    f"Flight duration: {route_data['duration']}. "
                    f"Distance: {route_data['distance']}. "
                    f"Typical schedules: {route_data['frequency']}. "
                    f"Official Carriers: Air Niugini (www.airniugini.com.pg), Qantas (www.qantas.com)."
                )
            })

        # 2. Perform live web search for real-time timetables / schedules
        search_term = f"flights from {orig_name or orig_code or 'POM'} to {dest_name or dest_code or 'BNE'} airlines schedule timetable"
        try:
            web_results = await search_web(search_term, max_results=3)
            sources.extend(web_results)
        except Exception as e:
            logger.error(f"Flight search error for '{query}': {e}")

        return bool(sources), sources

flight_service = FlightService()
