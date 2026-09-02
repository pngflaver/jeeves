import os
import json
import time
import logging
import socket
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class KPIService:
    """
    Backend KPI and Metrics Engine for Jeeves.
    Tracks command execution, AI latencies, error rates, user growth, and system load.
    Generates data/kpis.json and human-readable ASCII data/kpis.txt for instant 'cat' inspection.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_dir = data_dir or (Path(__file__).resolve().parent.parent / "data")
        self.json_file = self.base_dir / "kpis.json"
        self.txt_file = self.base_dir / "kpis.txt"
        self.start_time = time.time()
        self.start_iso = datetime.now(timezone.utc).isoformat()
        
        # In-memory session tracking
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

    def record_command(self, command_name: str, user_id: Optional[int] = None, success: bool = True, duration_ms: float = 0.0) -> None:
        """Record an executed command."""
        now_ts = time.time()
        event = {
            "type": "command",
            "name": command_name,
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
        
        # Append to recent rolling events
        recent = self.lifetime_data.setdefault("recent_events", [])
        recent.append(event)
        self._trim_events()
        
        self.export_kpi_files()

    def record_ai_query(self, user_id: Optional[int], prompt_length: int, duration_ms: float, success: bool = True, source: str = "ollama") -> None:
        """Record an AI LLM query with response latency."""
        now_ts = time.time()
        event = {
            "type": "ai_query",
            "user_id": user_id,
            "prompt_length": prompt_length,
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

    def generate_dashboard_text(self) -> str:
        """Generate human-readable ASCII table dashboard for 'cat' viewing."""
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
        
        # Read user profile stats
        user_profiles_path = self.base_dir / "user_profiles.json"
        total_tracked_users = 0
        rude_count = 0
        tech_count = 0
        if user_profiles_path.exists():
            try:
                with open(user_profiles_path, "r", encoding="utf-8") as f:
                    u_data = json.load(f)
                    total_tracked_users = len(u_data)
                    for u in u_data.values():
                        if u.get("rude_message_count", 0) > 0:
                            rude_count += 1
                        if u.get("technical_message_count", 0) > 0:
                            tech_count += 1
            except Exception:
                pass

        # Command breakdown
        cmd_counts = self.lifetime_data.get("command_counts", {})
        top_cmds = sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True)[:8]

        W = 68
        lines = []
        lines.append("╔" + "═" * (W - 2) + "╗")
        lines.append("║" + " 🤖 JEEVES OPERATIONAL & PERFORMANCE KPI DASHBOARD ".center(W - 2) + "║")
        lines.append("║" + f" Generated: {now_str} ".center(W - 2) + "║")
        lines.append("╠" + "═" * (W - 2) + "╣")
        
        # Section 1: Service & System Health
        lines.append("║ 🟢 SERVICE & HOST HEALTH" + " " * (W - 27) + "║")
        lines.append(f"║ • Service Uptime:      {uptime_str:<18} Hostname: {socket.gethostname()[:15]:<16} ║")
        lines.append(f"║ • Host CPU Usage:      {sys_m['host_cpu_percent']:>5.1f}%             Bot Process CPU: {sys_m['bot_cpu_percent']:>5.1f}%   ║")
        lines.append(f"║ • System RAM Used:     {sys_m['system_memory_used_gb']} / {sys_m['system_memory_total_gb']} GB ({sys_m['system_memory_percent']}%)   Bot Memory: {sys_m['bot_memory_mb']:>6.1f} MB ║")
        lines.append(f"║ • Disk Usage (Root):   {sys_m['disk_used_gb']} / {sys_m['disk_total_gb']} GB ({sys_m['disk_percent']}%)   Load Avg:   {sys_m['load_avg']:<14} ║")
        lines.append("╠" + "═" * (W - 2) + "╣")
        
        # Section 2: Traffic & Multi-Window Activity
        lines.append("║ 📊 MULTI-WINDOW TRAFFIC METRICS" + " " * (W - 34) + "║")
        lines.append(f"║ Metric                     Last 24 Hours     Session         Lifetime      ║")
        lines.append("║ ─────────────────────────  ────────────────  ──────────────  ───────────── ║")
        lines.append(f"║ Total Interactions:        {d_interactions:<16}  {len(self.session_events):<14}  {lt_interactions:<11} ║")
        lines.append(f"║ Diagnostic Commands:       {d_cmds:<16}  {sum(1 for e in self.session_events if e.get('type')=='command'):<14}  {lt_cmds:<11} ║")
        lines.append(f"║ AI / LLM Queries:          {d_ai:<16}  {sum(1 for e in self.session_events if e.get('type')=='ai_query'):<14}  {lt_ai:<11} ║")
        lines.append(f"║ Total Errors / Faults:     {d_errors:<16}  {sum(1 for e in self.session_events if not e.get('success',True)):<14}  {lt_errors:<11} ║")
        lines.append("╠" + "═" * (W - 2) + "╣")

        # Section 3: AI Inference & Reliability
        lines.append("║ 🧠 AI PERFORMANCE & RELIABILITY" + " " * (W - 34) + "║")
        lines.append(f"║ • Avg LLM Response Time:   {d_avg_latency:>5.2f}s (24h)   /   {avg_latency:>5.2f}s (Lifetime)          ║")
        lines.append(f"║ • Execution Reliability:   {lt_success_rate:>5.1f}% Success Rate ({lt_errors} lifetime errors)       ║")
        lines.append(f"║ • Active Tracked Users:    {total_tracked_users:<5} (Tech: {tech_count}, Flagged/Rude: {rude_count})         ║")
        lines.append("╠" + "═" * (W - 2) + "╣")

        # Section 4: Top Commands Breakdown
        lines.append("║ 🛠️ COMMAND FREQUENCY BREAKDOWN (TOP 8)" + " " * (W - 41) + "║")
        if top_cmds:
            for i in range(0, len(top_cmds), 2):
                c1 = top_cmds[i]
                col1 = f"• {c1[0]}: {c1[1]} runs"
                col2 = ""
                if i + 1 < len(top_cmds):
                    c2 = top_cmds[i+1]
                    col2 = f"• {c2[0]}: {c2[1]} runs"
                lines.append(f"║ {col1:<31} {col2:<32} ║")
        else:
            lines.append("║ • No commands recorded yet.                                        ║")

        lines.append("╚" + "═" * (W - 2) + "╝")
        lines.append("💡 Quick commands: 'cat data/kpis.txt' | 'cat data/kpis.json' | './kpi'")
        return "\n".join(lines) + "\n"

    def export_kpi_files(self) -> None:
        """Write out both kpis.json and formatted kpis.txt to disk."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self._save_json(self.lifetime_data)
            dashboard_text = self.generate_dashboard_text()
            with open(self.txt_file, "w", encoding="utf-8") as f:
                f.write(dashboard_text)
        except Exception as e:
            logger.error(f"Error exporting KPI files: {e}")

kpi_service = KPIService()
