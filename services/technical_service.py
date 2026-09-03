import re
import json
import os
import logging
import asyncio
from typing import Dict, Optional, Tuple, List
import config
from .search_service import search_web

logger = logging.getLogger(__name__)

# Known networking & IT hardware vendors and aliases
VENDOR_PATTERNS = {
    "Fortinet": r"\b(fortinet|fortigate|fortiswitch|fortiap|fortios|fortiproxy|fg-\w+|fgt-\w+)\b",
    "Cisco": r"\b(cisco|catalyst|ios-xe|ios-xr|nx-os|nexus|meraki|isr|asr)\b",
    "Palo Alto": r"\b(palo\s*alto|pan-os|pa-\d+)\b",
    "Juniper": r"\b(juniper|junos|srx|ex\d+|qfx)\b",
    "Ubiquiti": r"\b(ubiquiti|unifi|edgerouter|edgeswitch|udm|u6|u7)\b",
    "MikroTik": r"\b(mikrotik|routeros|routerboard|ccr|crs|hex|hap)\b",
    "Aruba": r"\b(aruba|arubaos|cx\s*\d+|procurve)\b",
    "Check Point": r"\b(check\s*point|gaia|quantum)\b",
    "Dell": r"\b(dell|poweredge|powerswitch|idrac|force10)\b",
    "HPE": r"\b(hpe|proliant|ilo)\b",
    "Arista": r"\b(arista|eos)\b"
}

# Known software, operating systems, and platforms
SOFTWARE_PATTERNS = {
    "FortiOS": r"\b(fortios\s*\d*(?:\.\d+)?)\b",
    "Cisco IOS-XE": r"\b(ios-xe\s*\d*(?:\.\d+)?|ios\s*xe)\b",
    "PAN-OS": r"\b(pan-os\s*\d*(?:\.\d+)?)\b",
    "Junos OS": r"\b(junos(?:\s*os)?\s*\d*(?:\.\d+)?)\b",
    "RouterOS": r"\b(routeros\s*(?:v?\d+(?:\.\d+)?)?)\b",
    "Ubuntu": r"\b(ubuntu(?:\s*\d{2}\.\d{2})?(?:\s*lts)?)\b",
    "Debian": r"\b(debian(?:\s*\d+)?)\b",
    "Red Hat Enterprise Linux": r"\b(rhel(?:\s*\d+)?|red\s*hat(?:\s*enterprise\s*linux)?(?:\s*\d+)?)\b",
    "Rocky Linux": r"\b(rocky(?:\s*linux)?(?:\s*\d+)?)\b",
    "AlmaLinux": r"\b(almalinux(?:\s*\d+)?)\b",
    "Windows Server": r"\b(windows\s*server(?:\s*\d{4})?)\b",
    "Docker": r"\b(docker(?:\s*engine|\s*compose)?)\b",
    "Kubernetes": r"\b(kubernetes|k8s(?:\s*\d+\.\d+)?)\b",
    "Nginx": r"\b(nginx)\b",
    "Apache": r"\b(apache(?:\s*httpd)?)\b",
    "PostgreSQL": r"\b(postgres(?:ql)?(?:\s*\d+)?)\b",
    "MySQL": r"\b(mysql(?:\s*\d+(?:\.\d+)?)?)\b",
    "Redis": r"\b(redis(?:\s*\d+)?)\b",
    "Python": r"\b(python(?:\s*\d+\.\d+)?)\b",
    "Node.js": r"\b(node(?:\.js)?(?:\s*\d+)?)\b"
}

# Regex for CVE IDs (e.g. CVE-2024-21762)
CVE_REGEX = re.compile(r"\b(CVE-\d{4}-\d{4,7})\b", re.IGNORECASE)

# Technical domain keywords that indicate a networking, hardware, or cybersecurity question
TECH_DOMAIN_KEYWORDS = re.compile(
    r"\b(vlan|vlans|bgp|ospf|ipsec|vpn|nat|firewall|firewalls|router|routers|switch|switches|gateway|"
    r"subnet|cidr|dhcp|tcp|udp|icmp|packet|latency|acl|acls|snmp|syslog|ntp|ssh|tacacs|radius|"
    r"throughput|datasheet|ports|interfaces|cve|cvss|vulnerability|exploit|firmware|fortios|junos|"
    r"routeros|kernel|docker|kubernetes|k8s|systemd|iptables|wireguard|eol|eos|eosl|eoes|upgrade path|"
    r"compatibility matrix|cli|config|configurations|traceroute|nmap|whois|ssl|tls|cert|certificate)\b",
    re.IGNORECASE
)

# Keywords indicating Software Upgrade / Migration requests
SOFTWARE_UPGRADE_KEYWORDS = re.compile(
    r"\b(upgrade path|upgrade guide|upgrade from|upgrade to|how to upgrade|migrate|migration|"
    r"compatibility matrix|supported upgrade path|matrix)\b",
    re.IGNORECASE
)

# Keywords indicating Software Installation / Deployment requests
SOFTWARE_INSTALL_KEYWORDS = re.compile(
    r"\b(how to install|install|installation|setup|deploy|deployment|docker run|docker-compose|"
    r"systemd service|apt install|yum install|dnf install|brew install|pip install)\b",
    re.IGNORECASE
)

# Keywords indicating CLI configuration requests
CLI_CONFIG_KEYWORDS = re.compile(
    r"\b(config|configs|configure|configuration|configurations|cli|syntax|command|commands|setup|set up|"
    r"how to configure|how to set|ipsec|vpn|bgp|ospf|vlan|vlans|nat|interface|interfaces|static route|"
    r"firewall policy|firewall policies|dhcp|acl|acls|snmp|ntp|ssh|tacacs|radius|port config|port configurations)\b",
    re.IGNORECASE
)

# Keywords indicating Hardware / Software Specs or Lifecycle inquiries
SPECS_EOL_KEYWORDS = re.compile(
    r"\b(specs|specification|specifications|datasheet|throughput|ports|interfaces|form factor|"
    r"dimensions|power|concurrent sessions|ram|cpu|eol|eos|eosl|eoes|eoexts|end of life|end of support|"
    r"end of sale|end of engineering support|end of extended support|lifecycle|last order|release date)\b",
    re.IGNORECASE
)

class TechnicalService:
    def __init__(self, cache_file: str = config.HARDWARE_CACHE_FILE):
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load technical profiles and hardware/software cache."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading technical cache {self.cache_file}: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def _save_cache(self) -> None:
        """Save technical profiles to cache."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving technical cache {self.cache_file}: {e}")

    def detect_technology(self, query: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Extract vendor, model/software identity, and category (hardware, software, general).
        Returns: (vendor, identity, category)
        """
        # 1. Check Software Patterns
        for sw_name, pattern in SOFTWARE_PATTERNS.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                matched_identity = match.group(0).strip()
                # If query contains explicit version (e.g. FortiOS 7.2.4)
                ver_match = re.search(r"(\d+(?:\.\d+)+)", query)
                if ver_match:
                    full_id = f"{sw_name} {ver_match.group(1)}"
                else:
                    full_id = matched_identity
                vendor = "Fortinet" if "FortiOS" in sw_name else None
                return vendor, full_id, "software"

        # 2. Check Hardware Vendors
        detected_vendor = None
        for vendor_name, pattern in VENDOR_PATTERNS.items():
            if re.search(pattern, query, re.IGNORECASE):
                detected_vendor = vendor_name
                break

        # 3. Check for specific model identifiers
        model_match = re.search(r"\b([A-Za-z]{2,5}[-_]?[A-Za-z0-9]{2,8}[A-Za-z]?)\b", query)
        detected_model = None
        if model_match:
            candidate = model_match.group(1).upper()
            if candidate not in ["WHAT", "WHEN", "WHERE", "HOW", "SHOW", "LIST", "CHECK", "TEST", "PING"]:
                detected_model = candidate

        full_identity = None
        if detected_vendor and detected_model:
            full_identity = f"{detected_vendor} {detected_model}"
        elif detected_model:
            full_identity = detected_model
        elif detected_vendor:
            full_identity = detected_vendor

        category = "hardware" if detected_vendor or detected_model else "general"
        return detected_vendor, full_identity, category

    def classify_intent(self, query: str, is_technical: bool = True) -> str:
        """
        Classify the query into:
        - 'GENERAL_WEB' (Everyday / general non-technical web search)
        - 'CVE' (Vulnerability/CVE security advisory)
        - 'SOFTWARE_UPGRADE' (Software upgrade path, migration, compatibility)
        - 'SOFTWARE_INSTALL' (Software installation, deployment, docker run)
        - 'CLI_CONFIG' (CLI commands, configuration guides, syntax)
        - 'SPECS_EOL' (Datasheet, throughput, ports, lifecycle/EOL)
        - 'TECHNICAL_GENERAL' (General IT/network question)
        """
        if not is_technical:
            return "GENERAL_WEB"

        if CVE_REGEX.search(query) or "vulnerability" in query.lower() or "security advisory" in query.lower():
            return "CVE"
        if SOFTWARE_UPGRADE_KEYWORDS.search(query):
            return "SOFTWARE_UPGRADE"
        if SOFTWARE_INSTALL_KEYWORDS.search(query):
            return "SOFTWARE_INSTALL"
        if CLI_CONFIG_KEYWORDS.search(query):
            return "CLI_CONFIG"
        if SPECS_EOL_KEYWORDS.search(query):
            return "SPECS_EOL"
        return "TECHNICAL_GENERAL"

    def build_search_query(
        self,
        query: str,
        intent: str,
        vendor: Optional[str],
        identity: Optional[str],
        category: str
    ) -> str:
        """Formulate a targeted high-precision technical search query or clean general search."""
        if intent == "GENERAL_WEB":
            # For general everyday queries, send the user's query 100% clean and untouched!
            return query.strip()

        if intent == "CVE":
            cve_match = CVE_REGEX.search(query)
            cve_id = cve_match.group(1) if cve_match else query
            vendor_hint = vendor or ""
            return f"{cve_id} {vendor_hint} vulnerability CVSS affected versions mitigation advisory"

        if intent == "SOFTWARE_UPGRADE":
            target = identity or vendor or ""
            return f"{target} {query} recommended upgrade path compatibility matrix official documentation"

        if intent == "SOFTWARE_INSTALL":
            target = identity or vendor or ""
            return f"{target} {query} installation guide step by step command line official docs"

        if intent == "CLI_CONFIG":
            target = identity or vendor or ""
            return f"{target} {query} CLI configuration command guide syntax official documentation"

        if intent == "SPECS_EOL":
            target = identity or vendor or query
            if category == "software":
                return f"{target} release date lifecycle end of engineering support EOES end of support EOL"
            return f"{target} datasheet specifications throughput ports interfaces lifecycle EOL EOS"

        # General technical query
        target_hint = f"{vendor} " if vendor else ""
        return f"{target_hint}{query} technical documentation"

    def get_cached_profile(self, key: str) -> Optional[Dict]:
        """Look up technical profile in cache."""
        return self.cache.get(key.lower().strip())

    def store_profile(
        self,
        key: str,
        vendor: Optional[str],
        category: str,
        intent: str,
        sources: List[Dict[str, str]]
    ) -> None:
        """Store or update discovered technical profile."""
        clean_key = key.lower().strip()
        existing = self.cache.get(clean_key, {})
        existing["identity"] = key
        existing["vendor"] = vendor
        existing["category"] = category
        existing["last_intent"] = intent
        existing["sources"] = sources
        existing["updated_at"] = asyncio.get_event_loop().time()
        self.cache[clean_key] = existing
        self._save_cache()

    async def get_technical_context(self, user_query: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Analyze user query, classify intent, check/update dynamic cache, and fetch targeted web search.
        Returns: (intent, search_results)
        """
        vendor, identity, category = self.detect_technology(user_query)
        is_tech = bool(
            vendor or category in ["hardware", "software"] or 
            CVE_REGEX.search(user_query) or 
            TECH_DOMAIN_KEYWORDS.search(user_query)
        )
        intent = self.classify_intent(user_query, is_technical=is_tech)
        cache_key = identity or user_query

        # Check if we have cached specs for this exact hardware/software when querying SPECS_EOL
        if intent == "SPECS_EOL" and cache_key:
            cached_data = self.get_cached_profile(cache_key)
            if cached_data and cached_data.get("sources"):
                logger.info(f"Loaded cached technical profile for '{cache_key}'")
                return intent, cached_data["sources"]

        # Formulate specialized search query (clean untouched query if GENERAL_WEB)
        search_q = self.build_search_query(user_query, intent, vendor, identity, category)
        logger.info(f"Executing [{intent}] search: '{search_q}'")
        
        results = await search_web(search_q, max_results=4)
        
        # Auto-cache the technical profile if an identity was discovered and it is technical
        if is_tech and results and identity:
            self.store_profile(identity, vendor, category, intent, results)
            logger.info(f"Auto-discovered and cached {category} profile for '{identity}'")

        return intent, results

technical_service = TechnicalService()
