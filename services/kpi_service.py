import os
import json
import time
import logging
import socket
import re
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Heuristics for classifying search/query nature
TOPIC_PATTERNS = {
    "Hardware & Specs (EOL/EOS)": re.compile(r"\b(fortigate|fortinet|cisco|juniper|palo alto|switch|router|firewall|eol|eos|datasheet|throughput|port|hardware|model)\b", re.IGNORECASE),
    "Software & Upgrades": re.compile(r"\b(upgrade|firmware|fortios|esxi|vmware|ubuntu|debian|rhel|windows server|version|patch|release|eoes)\b", re.IGNORECASE),
    "Security & CVE Advisories": re.compile(r"\b(cve|vulnerability|exploit|security|advisory|mitigation|cvss|threat|patch)\b", re.IGNORECASE),
    "Network Diagnostics": re.compile(r"\b(ping|traceroute|dns|dig|nmap|portscan|whois|http|curl|ssl|cert|ipinfo|latency|packet)\b", re.IGNORECASE),
    "Media & Streaming": re.compile(r"\b(movie|tv|series|episode|season|imdb|tmdb|actor|starring|film|show)\b", re.IGNORECASE),
    "Aviation & Flights": re.compile(r"\b(flight|airline|fly|airport|pom|bne|syd|cns|schedule|transit|route)\b", re.IGNORECASE),
    "General IT & Dev": re.compile(r"\b(python|docker|kubernetes|linux|bash|script|git|api|database|sql|cloud)\b", re.IGNORECASE),
    "Bot Identity / VIP": re.compile(r"\b(flavius|creator|who are you|who made you|jeeves|boss)\b", re.IGNORECASE),
}

class KPIService:
    """
    Comprehensive Backend KPI & Analytics Engine for Jeeves.
    Tracks:
    - Host & Bot process resource utilization
    - Multi-window traffic & interaction counters
    - Top active users with behavioral archetypes
    - Nature of searches and thematic query distribution
    - AI latency and command reliability metrics
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_dir = data_dir or (Path(__file__).resolve().parent.parent / "data")
        self.json_file = self.base_dir / "kpis.json"
        self.txt_file = self.base_dir / "kpis.txt"
        self.start_time = time.time()
        self.start_iso = datetime.now(timezone.utc).isoformat()
        
        self.session_events = []
        self.lifetime_data = self._load_json()

    def _load_json(self) -> Dict[str, Any]:
        """Load persistent lifetime counters."""
        if self.json_file.exists():
            try:
                with open(self.json_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading KPI JSON from {self.json_file}: {e}")
        
        return {
            "first_recorded": self.start_iso,
            "total_interactions": 0,
            "total_commands": 0,
            "total_ai_queries": 0,
            "total_errors": 0,
            "ai_latency_total_ms": 0.0,
            "ai_latency_count": 0,
            "command_counts": {},
            "search_categories": {},
            "recent_search_topics": [],
            "recent_events": []  # Rolling 24h events
        }

    def _save_json(self, data: Dict[str, Any]) -> None:
        """Persist structured KPI data."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with open(self.json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving KPI JSON to {self.json_file}: {e}")

    def _classify_nature_of_query(self, text: str) -> str:
        """Classify query text into primary search nature/category."""
        for category, pattern in TOPIC_PATTERNS.items():
            if pattern.search(text):
                return category
        return "General Knowledge & Chat"

    def record_command(self, command_name: str, user_id: Optional[int] = None, success: bool = True, duration_ms: float = 0.0) -> None:
        """Record an executed command."""
        now_ts = time.time()
        
        # Categorize command
        if command_name in ["ping", "traceroute", "dns", "nmap", "whois", "http", "ssl", "ipinfo"]:
            cat = "Network Diagnostics"
        elif command_name in ["movie", "tv"]:
            cat = "Media & Streaming"
        elif command_name in ["flight"]:
            cat = "Aviation & Flights"
        elif command_name in ["hardware", "sync_hardware"]:
            cat = "Hardware & Specs (EOL/EOS)"
        elif command_name in ["software", "sync_software"]:
            cat = "Software & Upgrades"
        else:
            cat = "Bot Commands & Info"

        event = {
            "type": "command",
            "name": command_name,
            "category": cat,
            "user_id": user_id,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "timestamp": now_ts
        }
        
        self.session_events.append(event)
        
        # Update lifetime counters
        self.lifetime_data["total_interactions"] = self.lifetime_data.get("total_interactions", 0) + 1
        self.lifetime_data["total_commands"] = self.lifetime_data.get("total_commands", 0) + 1
        if not success:
            self.lifetime_data["total_errors"] = self.lifetime_data.get("total_errors", 0) + 1
        
        cmds = self.lifetime_data.setdefault("command_counts", {})
        cmds[command_name] = cmds.get(command_name, 0) + 1
        
        cats = self.lifetime_data.setdefault("search_categories", {})
        cats[cat] = cats.get(cat, 0) + 1
        
        recent = self.lifetime_data.setdefault("recent_events", [])
        recent.append(event)
        self._trim_events()
        
        self.export_kpi_files()

    def record_ai_query(self, user_id: Optional[int], prompt: str, duration_ms: float, success: bool = True, source: str = "ollama") -> None:
        """Record an AI LLM query with topic classification and response latency."""
        now_ts = time.time()
        category = self._classify_nature_of_query(prompt)
        
        event = {
            "type": "ai_query",
            "category": category,
            "prompt_snippet": prompt[:60].strip(),
            "user_id": user_id,
            "prompt_length": len(prompt),
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "source": source,
            "timestamp": now_ts
        }
        
        self.session_events.append(event)
        
        self.lifetime_data["total_interactions"] = self.lifetime_data.get("total_interactions", 0) + 1
        self.lifetime_data["total_ai_queries"] = self.lifetime_data.get("total_ai_queries", 0) + 1
        self.lifetime_data["ai_latency_total_ms"] = self.lifetime_data.get("ai_latency_total_ms", 0.0) + duration_ms
        self.lifetime_data["ai_latency_count"] = self.lifetime_data.get("ai_latency_count", 0) + 1
        if not success:
            self.lifetime_data["total_errors"] = self.lifetime_data.get("total_errors", 0) + 1
            
        cats = self.lifetime_data.setdefault("search_categories", {})
        cats[category] = cats.get(category, 0) + 1
        
        # Track recent search query topics
        topics = self.lifetime_data.setdefault("recent_search_topics", [])
        clean_snip = prompt.replace("\n", " ").strip()
        if clean_snip and clean_snip not in topics:
            topics.append(clean_snip[:50])
            if len(topics) > 15:
                self.lifetime_data["recent_search_topics"] = topics[-15:]
        
        recent = self.lifetime_data.setdefault("recent_events", [])
        recent.append(event)
        self._trim_events()
        
        self.export_kpi_files()

    def _trim_events(self) -> None:
        """Keep only last 24 hours of events in recent_events."""
        cutoff = time.time() - 86400
        recent = self.lifetime_data.get("recent_events", [])
        self.lifetime_data["recent_events"] = [e for e in recent if e.get("timestamp", 0) >= cutoff]
        self.session_events = [e for e in self.session_events if e.get("timestamp", 0) >= cutoff]

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Collect host and bot process CPU, RAM, and disk utilization."""
        proc = psutil.Process()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        load1, load5, load15 = psutil.getloadavg()
        
        return {
            "host_cpu_percent": psutil.cpu_percent(interval=None),
            "bot_cpu_percent": proc.cpu_percent(interval=None),
            "bot_memory_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
            "system_memory_used_gb": round(mem.used / (1024 ** 3), 2),
            "system_memory_total_gb": round(mem.total / (1024 ** 3), 2),
            "system_memory_percent": mem.percent,
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "load_avg": f"{load1:.2f}, {load5:.2f}, {load15:.2f}"
        }

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime into human-readable string."""
        td = timedelta(seconds=int(seconds))
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m {secs}s")
        return " ".join(parts)

    def _get_top_users_data(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Extract and rank top users from user profiles."""
        user_profiles_path = self.base_dir / "user_profiles.json"
        if not user_profiles_path.exists():
            return []
        
        try:
            with open(user_profiles_path, "r", encoding="utf-8") as f:
                profiles = json.load(f)
        except Exception:
            return []

        ranked = []
        for u_id, p in profiles.items():
            ass = p.get("assessment", {})
            traits = ass.get("traits", [])
            topics = ass.get("topics", [])
            primary_topic = topics[0] if topics else (traits[0] if traits else "General")
            
            username = p.get("username", "")
            display_name = f"@{username}" if username and username != "No Username" else (p.get("full_name") or f"ID:{u_id}")
            
            ranked.append({
                "user_id": u_id,
                "display_name": display_name,
                "full_name": p.get("full_name", "Unknown"),
                "total_messages": p.get("total_messages", 0),
                "technical_messages": p.get("technical_message_count", 0),
                "rude_messages": p.get("rude_message_count", 0),
                "archetype": ass.get("archetype", "Standard Member"),
                "tone": ass.get("tone", "Neutral"),
                "primary_topic": primary_topic,
                "last_seen": p.get("last_seen", "")
            })
        
        ranked.sort(key=lambda x: x["total_messages"], reverse=True)
        return ranked[:limit]

    def generate_dashboard_text(self) -> str:
        """Generate comprehensive human-readable ASCII table dashboard for 'cat' viewing."""
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        uptime_sec = time.time() - self.start_time
        uptime_str = self._format_uptime(uptime_sec)
        
        sys_m = self._get_system_metrics()
        
        # Lifetime numbers
        lt_interactions = self.lifetime_data.get("total_interactions", 0)
        lt_cmds = self.lifetime_data.get("total_commands", 0)
        lt_ai = self.lifetime_data.get("total_ai_queries", 0)
        lt_errors = self.lifetime_data.get("total_errors", 0)
        lt_success_rate = 100.0 if lt_interactions == 0 else max(0.0, 100.0 - (lt_errors / lt_interactions * 100.0))
        
        avg_latency = 0.0
        if self.lifetime_data.get("ai_latency_count", 0) > 0:
            avg_latency = self.lifetime_data["ai_latency_total_ms"] / self.lifetime_data["ai_latency_count"] / 1000.0
        
        # 24-hour numbers
        recent = self.lifetime_data.get("recent_events", [])
        d_interactions = len(recent)
        d_cmds = sum(1 for e in recent if e.get("type") == "command")
        d_ai = sum(1 for e in recent if e.get("type") == "ai_query")
        d_errors = sum(1 for e in recent if not e.get("success", True))
        
        d_ai_latencies = [e["duration_ms"] for e in recent if e.get("type") == "ai_query" and "duration_ms" in e]
        d_avg_latency = (sum(d_ai_latencies) / len(d_ai_latencies) / 1000.0) if d_ai_latencies else avg_latency
        
        # Read top users
        top_users = self._get_top_users_data(limit=5)
        
        # Nature of searches
        categories = self.lifetime_data.get("search_categories", {})
        total_cats = sum(categories.values()) or 1
        sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        
        # Recent search topics
        recent_topics = self.lifetime_data.get("recent_search_topics", [])[-6:]

        # Command breakdown
        cmd_counts = self.lifetime_data.get("command_counts", {})
        top_cmds = sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True)[:6]

        W = 72
        lines = []
        lines.append("╔" + "═" * (W - 2) + "╗")
        lines.append("║" + " 🤖 JEEVES OPERATIONAL, USER & SEARCH ANALYTICS KPI DASHBOARD ".center(W - 2) + "║")
        lines.append("║" + f" Generated: {now_str} ".center(W - 2) + "║")
        lines.append("╠" + "═" * (W - 2) + "╣")
        
        # Section 1: Service & System Health
        lines.append("║ 🟢 SERVICE & HOST HEALTH" + " " * (W - 27) + "║")
        lines.append(f"║ • Service Uptime:      {uptime_str:<18} Hostname: {socket.gethostname()[:18]:<19} ║")
        lines.append(f"║ • Host CPU Usage:      {sys_m['host_cpu_percent']:>5.1f}%             Bot Process CPU: {sys_m['bot_cpu_percent']:>5.1f}%     ║")
        lines.append(f"║ • System RAM Used:     {sys_m['system_memory_used_gb']} / {sys_m['system_memory_total_gb']} GB ({sys_m['system_memory_percent']}%)   Bot Memory: {sys_m['bot_memory_mb']:>6.1f} MB   ║")
        lines.append(f"║ • Disk Usage (Root):   {sys_m['disk_used_gb']} / {sys_m['disk_total_gb']} GB ({sys_m['disk_percent']}%)   Load Avg:   {sys_m['load_avg']:<17} ║")
        lines.append("╠" + "═" * (W - 2) + "╣")
        
        # Section 2: Traffic & Multi-Window Activity
        lines.append("║ 📊 MULTI-WINDOW TRAFFIC METRICS" + " " * (W - 34) + "║")
        lines.append(f"║ Metric                     Last 24 Hours     Session         Lifetime        ║")
        lines.append("║ ─────────────────────────  ────────────────  ──────────────  ─────────────── ║")
        lines.append(f"║ Total Interactions:        {d_interactions:<16}  {len(self.session_events):<14}  {lt_interactions:<13} ║")
        lines.append(f"║ Diagnostic Commands:       {d_cmds:<16}  {sum(1 for e in self.session_events if e.get('type')=='command'):<14}  {lt_cmds:<13} ║")
        lines.append(f"║ AI / LLM Queries:          {d_ai:<16}  {sum(1 for e in self.session_events if e.get('type')=='ai_query'):<14}  {lt_ai:<13} ║")
        lines.append(f"║ Total Errors / Faults:     {d_errors:<16}  {sum(1 for e in self.session_events if not e.get('success',True)):<14}  {lt_errors:<13} ║")
        lines.append(f"║ Avg LLM Response Time:     {d_avg_latency:>5.2f}s           {avg_latency:>5.2f}s           {avg_latency:>5.2f}s          ║")
        lines.append(f"║ Reliability / Success:     {lt_success_rate:>5.1f}%           {lt_success_rate:>5.1f}%           {lt_success_rate:>5.1f}%          ║")
        lines.append("╠" + "═" * (W - 2) + "╣")

        # Section 3: Nature of Searches & Query Distribution
        lines.append("║ 🔍 NATURE OF SEARCHES & THEMATIC BREAKDOWN" + " " * (W - 45) + "║")
        if sorted_cats:
            for cat_name, cnt in sorted_cats:
                pct = (cnt / total_cats) * 100.0
                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"║ • {cat_name:<28} [{bar}] {cnt:>3} ({pct:>5.1f}%) ║")
        else:
            lines.append("║ • No thematic searches classified yet.                               ║")
        
        if recent_topics:
            lines.append("║                                                                      ║")
            lines.append("║ 📌 Recent / Trending Search Inquiries:                                ║")
            for t in recent_topics:
                lines.append(f"║   ↳ \"{t[:64]}\"{' ' * max(0, 64 - len(t))} ║")
        lines.append("╠" + "═" * (W - 2) + "╣")

        # Section 4: Top Users & Behavioral Analytics
        lines.append("║ 👥 TOP ACTIVE USERS & PARTICIPATION" + " " * (W - 38) + "║")
        lines.append("║ User                     Msgs  Archetype              Focus Area     ║")
        lines.append("║ ───────────────────────  ────  ─────────────────────  ────────────── ║")
        if top_users:
            for u in top_users:
                d_name = u['display_name'][:23]
                arch = u['archetype'][:21]
                foc = u['primary_topic'][:14]
                lines.append(f"║ {d_name:<23}  {u['total_messages']:>4}  {arch:<21}  {foc:<14} ║")
        else:
            lines.append("║ No user interactions recorded yet.                                   ║")
        lines.append("╠" + "═" * (W - 2) + "╣")

        # Section 5: Top Diagnostic Commands
        lines.append("║ 🛠️ COMMAND FREQUENCY BREAKDOWN" + " " * (W - 33) + "║")
        if top_cmds:
            for i in range(0, len(top_cmds), 2):
                c1 = top_cmds[i]
                col1 = f"• {c1[0]}: {c1[1]} runs"
                col2 = ""
                if i + 1 < len(top_cmds):
                    c2 = top_cmds[i+1]
                    col2 = f"• {c2[0]}: {c2[1]} runs"
                lines.append(f"║ {col1:<33} {col2:<34} ║")
        else:
            lines.append("║ • No commands recorded yet.                                          ║")

        lines.append("╚" + "═" * (W - 2) + "╝")
        lines.append("💡 Quick commands: 'cat /root/kpis.txt' | 'cat data/kpis.json' | 'kpi'")
        return "\n".join(lines) + "\n"

    def export_kpi_files(self) -> None:
        """Write out both kpis.json and formatted kpis.txt to disk."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            
            # Enrich json with top users and search breakdown
            export_payload = dict(self.lifetime_data)
            export_payload["top_users"] = self._get_top_users_data(limit=10)
            export_payload["system_metrics"] = self._get_system_metrics()
            
            self._save_json(export_payload)
            dashboard_text = self.generate_dashboard_text()
            with open(self.txt_file, "w", encoding="utf-8") as f:
                f.write(dashboard_text)
        except Exception as e:
            logger.error(f"Error exporting KPI files: {e}")

kpi_service = KPIService()
