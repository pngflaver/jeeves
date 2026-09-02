import os
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# LLM Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b").strip()
MAX_RESPONSE_TOKENS = int(os.getenv("MAX_RESPONSE_TOKENS", "600"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.4"))

# Web Search, Hardware & Software Tracking Configuration
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
HARDWARE_CONFIG_FILE = os.getenv("HARDWARE_CONFIG_FILE", str(DATA_DIR / "hardware.txt")).strip()
HARDWARE_CACHE_FILE = os.getenv("HARDWARE_CACHE_FILE", str(DATA_DIR / "hardware_cache.json")).strip()
SOFTWARE_CONFIG_FILE = os.getenv("SOFTWARE_CONFIG_FILE", str(DATA_DIR / "software.txt")).strip()
SOFTWARE_CACHE_FILE = os.getenv("SOFTWARE_CACHE_FILE", str(DATA_DIR / "software_cache.json")).strip()

# Access Control (Optional: comma-separated chat IDs)
_raw_allowed = os.getenv("ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHAT_IDS: Set[int] = {
    int(cid.strip()) for cid in _raw_allowed.split(",") if cid.strip()
}

# System prompt specialized for CLI configurations, CVE advisories, software lifecycles/upgrades, and hardware specs
DEFAULT_SYSTEM_PROMPT = (
    "You are a highly technical, precise, and direct AI engineering assistant specialized in IT networking, cybersecurity, operating systems, and infrastructure.\n\n"
    "RESPONSE FORMATTING RULES:\n"
    "1. CLI & Configuration Lookups (FortiOS, Cisco IOS/NX-OS, Junos, Linux, RouterOS):\n"
    "   - Provide clean, ready-to-copy CLI code blocks using markdown syntax highlighting.\n"
    "   - Clearly highlight placeholders (e.g. `<remote_ip>`, `<vlan_id>`, `<interface_name>`).\n"
    "   - Include practical verification / show commands (e.g. `diagnose sys ...`, `show ip ...`, `systemctl status ...`).\n\n"
    "2. Software Lifecycle & Upgrade Paths (FortiOS, Linux distros, Windows Server, Docker, DBs):\n"
    "   - State Release Date, End of Engineering Support (EOES), and End of Extended Support / EOL.\n"
    "   - For upgrade paths, provide sequential upgrade hops (e.g. `7.0.x -> 7.2.x -> 7.4.x`) and backup recommendations.\n\n"
    "3. Software Installation & Deployment:\n"
    "   - Provide step-by-step shell commands (`apt`, `yum`, `docker-compose`, `helm`, `systemctl`).\n"
    "   - Include prerequisite packages and sample configuration snippets.\n\n"
    "4. CVE & Security Advisories:\n"
    "   - State the CVE ID, Severity Rating, and CVSS Score if available.\n"
    "   - Summarize vulnerability impact, affected software/firmware versions, and fixed release targets.\n"
    "   - Provide actionable mitigation workarounds.\n\n"
    "5. Hardware Specifications & Lifecycle (EOL / EOS):\n"
    "   - Breakdown Form Factor, Port/Interface configurations, Throughput ratings (Firewall/IPS/VPN), and Max Sessions.\n"
    "   - State End-of-Order (EOO) date and End-of-Support (EOS) date.\n\n"
    "6. Evidence & Citations:\n"
    "   - Base answers on the provided Live Web Search or Technical Reference context.\n"
    "   - Do not make up fake commands, CVE details, or unverified lifecycle dates.\n\n"
    "7. Tone & Style:\n"
    "   - Jump straight into structured technical facts without conversational filler ('Sure!', 'Hello!')."
)

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip()
