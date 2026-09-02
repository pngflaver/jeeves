import re
import logging
from typing import Optional, Dict, Tuple, List
from .search_service import search_web

logger = logging.getLogger(__name__)

# Airline Registry
AIRLINES = {
    "PX": {"name": "Air Niugini", "icao": "ANG", "hub": "POM", "country": "Papua New Guinea", "url": "https://www.airniugini.com.pg"},
    "QF": {"name": "Qantas", "icao": "QFA", "hub": "SYD/BNE/MEL", "country": "Australia", "url": "https://www.qantas.com"},
    "VA": {"name": "Virgin Australia", "icao": "VOZ", "hub": "BNE/SYD/MEL", "country": "Australia", "url": "https://www.virginaustralia.com"},
    "CG": {"name": "PNG Air", "icao": "TOK", "hub": "POM", "country": "Papua New Guinea", "url": "https://www.pngair.com.pg"},
    "SQ": {"name": "Singapore Airlines", "icao": "SIA", "hub": "SIN", "country": "Singapore", "url": "https://www.singaporeair.com"},
    "PR": {"name": "Philippine Airlines", "icao": "PAL", "hub": "MNL", "country": "Philippines", "url": "https://www.philippineairlines.com"},
    "FJ": {"name": "Fiji Airways", "icao": "FJI", "hub": "NAN", "country": "Fiji", "url": "https://www.fijiairways.com"},
    "IE": {"name": "Solomon Airlines", "icao": "SOL", "hub": "HIR", "country": "Solomon Islands", "url": "https://www.flysolomons.com"},
    "NF": {"name": "Air Vanuatu", "icao": "AVN", "hub": "VLI", "country": "Vanuatu", "url": "https://www.airvanuatu.com"},
    "JQ": {"name": "Jetstar", "icao": "JST", "hub": "MEL/BNE/SYD", "country": "Australia", "url": "https://www.jetstar.com"},
}

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
    "CBR": {"name": "Canberra International", "country": "Australia", "cities": ["canberra", "cbr"]},
    "HBA": {"name": "Hobart International", "country": "Australia", "cities": ["hobart", "hba"]},
    "TSV": {"name": "Townsville Airport", "country": "Australia", "cities": ["townsville", "tsv"]},
    "MKY": {"name": "Mackay Airport", "country": "Australia", "cities": ["mackay", "mky"]},
    "ROK": {"name": "Rockhampton Airport", "country": "Australia", "cities": ["rockhampton", "rok"]},
    "GLT": {"name": "Gladstone Airport", "country": "Australia", "cities": ["gladstone", "glt"]},
    "ISA": {"name": "Mount Isa Airport", "country": "Australia", "cities": ["mount isa", "mt isa", "isa"]},
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

# Airline Flight Route Network Catalogues
AIRLINE_NETWORKS = {
    "PX": {
        "airline": "Air Niugini (PX)",
        "scope": "International Route Network",
        "hub": "Port Moresby (POM) Jacksons International",
        "flights": [
            {"flight_no": "PX003 / PX004", "route": "Port Moresby (POM) ⇄ Brisbane (BNE)", "frequency": "Daily morning departure", "type": "International"},
            {"flight_no": "PX005 / PX006", "route": "Port Moresby (POM) ⇄ Brisbane (BNE)", "frequency": "Daily afternoon departure", "type": "International"},
            {"flight_no": "PX001 / PX002", "route": "Port Moresby (POM) ⇄ Sydney (SYD)", "frequency": "Direct weekly flights (Mon/Fri/Sun)", "type": "International"},
            {"flight_no": "PX098 / PX099", "route": "Port Moresby (POM) ⇄ Cairns (CNS)", "frequency": "Daily direct service", "type": "International"},
            {"flight_no": "PX392 / PX393", "route": "Port Moresby (POM) ⇄ Singapore (SIN)", "frequency": "4-5x weekly direct", "type": "International"},
            {"flight_no": "PX010 / PX011", "route": "Port Moresby (POM) ⇄ Manila (MNL)", "frequency": "3-4x weekly direct", "type": "International"},
            {"flight_no": "PX396 / PX397", "route": "Port Moresby (POM) ⇄ Hong Kong (HKG)", "frequency": "Weekly direct service", "type": "International"},
            {"flight_no": "PX084 / PX085", "route": "Port Moresby (POM) ⇄ Nadi (NAN, Fiji)", "frequency": "Weekly service via Honiara", "type": "International"},
            {"flight_no": "PX082 / PX083", "route": "Port Moresby (POM) ⇄ Honiara (HIR, Solomons)", "frequency": "2x weekly direct", "type": "International"},
            {"flight_no": "PX086 / PX087", "route": "Port Moresby (POM) ⇄ Port Vila (VLI, Vanuatu)", "frequency": "Weekly regional flight", "type": "International"},
        ]
    },
    "QF_BNE_DOMESTIC": {
        "airline": "Qantas (QF) / QantasLink",
        "scope": "Domestic Routes Leaving Brisbane (BNE)",
        "hub": "Brisbane Airport (BNE)",
        "flights": [
            {"flight_no": "QF500-QF560 Series", "route": "Brisbane (BNE) ➔ Sydney (SYD)", "frequency": "~20-25 flights daily (hourly departures)", "type": "Trunk Domestic"},
            {"flight_no": "QF600-QF640 Series", "route": "Brisbane (BNE) ➔ Melbourne (MEL)", "frequency": "~12-16 flights daily", "type": "Trunk Domestic"},
            {"flight_no": "QF700 Series", "route": "Brisbane (BNE) ➔ Cairns (CNS)", "frequency": "~5-7 flights daily", "type": "Trunk Domestic"},
            {"flight_no": "QF770 / QF774", "route": "Brisbane (BNE) ➔ Perth (PER)", "frequency": "Multiple daily direct cross-country flights", "type": "Trans-Continental"},
            {"flight_no": "QF650-QF665 Series", "route": "Brisbane (BNE) ➔ Adelaide (ADL)", "frequency": "~4-5 flights daily", "type": "Domestic"},
            {"flight_no": "QF860 Series", "route": "Brisbane (BNE) ➔ Canberra (CBR)", "frequency": "~5-6 flights daily", "type": "Capital Domestic"},
            {"flight_no": "QF824 / QF828", "route": "Brisbane (BNE) ➔ Darwin (DRW)", "frequency": "Daily direct flights", "type": "Domestic"},
            {"flight_no": "QF1550 Series", "route": "Brisbane (BNE) ➔ Hobart (HBA)", "frequency": "Daily direct flights", "type": "Domestic"},
            {"flight_no": "QF2300-QF2550 (QantasLink)", "route": "Brisbane (BNE) ➔ Regional QLD (Townsville, Mackay, Rockhampton, Gladstone, Emerald, Bundaberg, Mount Isa)", "frequency": "Frequent daily regional turboprop & jet services", "type": "Regional QLD"}
        ]
    }
}

# Specific Route Schedules
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
    r"port moresby to brisbane|brisbane to port moresby|next flight|active flight|live flight|"
    r"px\s*\d+|qf\s*\d+|va\s*\d+|sq\s*\d+|pr\s*\d+|flightradar|flightaware)\b",
    re.IGNORECASE
)

FLIGHT_NUMBER_PATTERN = re.compile(r"\b(PX|QF|VA|CG|SQ|PR|FJ|IE|NF|JQ)\s*(\d{1,4})\b", re.IGNORECASE)

class FlightService:
    def is_flight_query(self, query: str) -> bool:
        """Check if query is asking for flight routes, airlines, or tracking."""
        return bool(FLIGHT_INTENT_PATTERN.search(query))

    def detect_flight_number(self, query: str) -> Optional[Tuple[str, str, str]]:
        """
        Detect flight number like PX3, QF57, VA901.
        Returns: (full_flight_code, airline_code, flight_number)
        """
        match = FLIGHT_NUMBER_PATTERN.search(query)
        if match:
            airline_code = match.group(1).upper()
            flight_no = match.group(2)
            full_code = f"{airline_code}{flight_no}"
            return full_code, airline_code, flight_no
        return None

    def resolve_airport(self, name_or_code: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve airport code and full name."""
        cleaned = name_or_code.strip().upper()
        if cleaned in AIRPORT_CODES:
            return cleaned, AIRPORT_CODES[cleaned]["name"]

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
        # 1. Pattern: from <Origin> to <Destination>
        from_to_match = re.search(r"\b(?:from\s+)?([a-zA-Z\s]{2,20}?)\s+(?:to|->|—|-)\s+([a-zA-Z\s]{2,20}?)(?:\s+flight|\s+airline|\s+schedule|\?|$|\.)", query, re.IGNORECASE)
        if from_to_match:
            orig_raw, dest_raw = from_to_match.group(1).strip(), from_to_match.group(2).strip()
            orig_raw = re.sub(r"^(?:flights?\s+|find\s+(?:the\s+)?(?:next\s+)?flights?\s+)", "", orig_raw, flags=re.IGNORECASE).strip()
            orig_code, orig_name = self.resolve_airport(orig_raw)
            dest_code, dest_name = self.resolve_airport(dest_raw)
            if orig_code and dest_code:
                return orig_code, orig_name, dest_code, dest_name

        # 2. Scanning query for recognized city / airport tokens by appearance order
        lowered = query.lower()
        found_airports = []
        for code, data in AIRPORT_CODES.items():
            for alias in [code.lower()] + data.get("cities", []):
                pattern = rf"\b{re.escape(alias)}\b"
                match = re.search(pattern, lowered)
                if match:
                    found_airports.append((match.start(), code, data["name"]))
                    break

        found_airports.sort(key=lambda x: x[0])
        unique_airports = []
        for item in found_airports:
            if not unique_airports or unique_airports[-1][1] != item[1]:
                unique_airports.append(item)

        if len(unique_airports) >= 2:
            return unique_airports[0][1], unique_airports[0][2], unique_airports[1][1], unique_airports[1][2]

        return None, None, None, None

    async def get_flight_context(self, query: str) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Retrieve structured flight route information, airline fleet networks,
        live flight radar status, and real-time live search context.
        """
        sources = []
        lowered = query.lower()

        # 1. Check for specific Flight Number (e.g. PX3, QF57, PX5)
        flight_num_info = self.detect_flight_number(query)
        if flight_num_info:
            full_code, airline_code, flight_no = flight_num_info
            airline_name = AIRLINES.get(airline_code, {}).get("name", airline_code)
            flightaware_url = f"https://www.flightaware.com/live/flight/{full_code}"
            flightradar_url = f"https://www.flightradar24.com/data/flights/{full_code.lower()}"
            sources.append({
                "title": f"Live Flight Tracking: {airline_name} {full_code}",
                "url": flightradar_url,
                "snippet": (
                    f"Flight Code: {full_code} ({airline_name}). "
                    f"Live Status & Radar: Track real-time position, altitude, speed, departure and arrival times. "
                    f"Live FlightRadar24 Tracker: {flightradar_url}. "
                    f"Live FlightAware Tracker: {flightaware_url}."
                )
            })

        # 2. Check for "all international PX flights" / Air Niugini network
        if ("international" in lowered and ("px" in lowered or "air niugini" in lowered)) or ("all px flights" in lowered or "px international" in lowered):
            net = AIRLINE_NETWORKS["PX"]
            flights_str = "\n".join([f"• {f['flight_no']}: {f['route']} ({f['frequency']})" for f in net["flights"]])
            sources.append({
                "title": "Air Niugini (PX) International Flight Network & Timetables",
                "url": "https://www.flightconnections.com/route-map-air-niugini-px",
                "snippet": (
                    f"Airline: {net['airline']}. Hub: {net['hub']}.\n"
                    f"Complete International Schedule:\n{flights_str}\n"
                    f"Live Status Tracking: https://www.flightradar24.com/data/airlines/px-ang/routes"
                )
            })

        # 3. Check for "all QF domestic flights leaving Brisbane" / Qantas BNE network
        if (("qf" in lowered or "qantas" in lowered) and ("brisbane" in lowered or "bne" in lowered) and ("domestic" in lowered or "leaving" in lowered or "departing" in lowered or "flights" in lowered)):
            net = AIRLINE_NETWORKS["QF_BNE_DOMESTIC"]
            flights_str = "\n".join([f"• {f['flight_no']}: {f['route']} ({f['frequency']})" for f in net["flights"]])
            sources.append({
                "title": "Qantas (QF) Domestic Flights Departing Brisbane (BNE)",
                "url": "https://www.flightsfrom.com/BNE/QF",
                "snippet": (
                    f"Airline: {net['airline']}. Departure Hub: {net['hub']}.\n"
                    f"Domestic Routes & Services:\n{flights_str}\n"
                    f"Brisbane Airport Live Departures: https://www.flightradar24.com/data/airports/bne/departures"
                )
            })

        # 4. Check for Specific Route (e.g. POM to BNE)
        orig_code, orig_name, dest_code, dest_name = self.extract_route(query)
        if orig_code and dest_code and (orig_code, dest_code) in POPULAR_ROUTES:
            route_data = POPULAR_ROUTES[(orig_code, dest_code)]
            sources.append({
                "title": f"Direct Route: {route_data['origin_name']} to {route_data['dest_name']}",
                "url": f"https://www.google.com/travel/flights?q=flights+from+{orig_code}+to+{dest_code}",
                "snippet": (
                    f"Route: {route_data['origin_name']} -> {route_data['dest_name']}. "
                    f"Operating Airlines: {', '.join(route_data['airlines'])}. "
                    f"Flight duration: {route_data['duration']}. "
                    f"Distance: {route_data['distance']}. "
                    f"Typical daily schedule: {route_data['frequency']}. "
                    f"Live Radar Tracking: https://www.flightradar24.com/data/flights/px3"
                )
            })

        # 5. Live Web Search for up-to-the-minute flight schedules & active radar
        search_query = query
        if not flight_num_info and not orig_code:
            search_query = f"{query} airline flight schedule status"
        elif flight_num_info:
            search_query = f"{flight_num_info[0]} flight status live tracking schedule today"

        try:
            web_results = await search_web(search_query, max_results=3)
            sources.extend(web_results)
        except Exception as e:
            logger.error(f"Flight search error for '{query}': {e}")

        return bool(sources), sources

flight_service = FlightService()
