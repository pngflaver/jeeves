import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import uuid
logger = logging.getLogger(__name__)

class QualityService:
    """
    Backend Quality Logging & Review Engine for Jeeves.
    Logs interactions to pending.jsonl without impacting Telegram UI.
    Provides batch retrieval, evaluation storage, and archival to processed.jsonl.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_dir = data_dir or (Path(__file__).resolve().parent.parent / "data")
        self.records_dir = self.base_dir / "quality_records"
        self.pending_file = self.records_dir / "pending.jsonl"
        self.processed_file = self.records_dir / "processed.jsonl"
        self.reviews_dir = self.records_dir / "reviews"

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure quality records directories exist."""
        try:
            self.records_dir.mkdir(parents=True, exist_ok=True)
            self.reviews_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating quality records directories: {e}")

    def log_interaction(
        self,
        command: str,
        user: Optional[Any],
        query: str,
        response: str,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Log an interaction to pending.jsonl.
        Safe and non-blocking: catches exceptions so user experience is never degraded.
        """
        try:
            now_dt = datetime.now(timezone.utc)
            record_id = f"qa_{now_dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

            clean_sources = []
            if sources:
                for s in sources:
                    if isinstance(s, dict):
                        clean_sources.append({
                            "title": s.get("title", ""),
                            "url": s.get("url", ""),
                            "age_tier": s.get("age_tier", "")
                        })

            user_id = getattr(user, "id", None) if user else None
            username = getattr(user, "username", None) or getattr(user, "first_name", "Anonymous") if user else "Anonymous"

            record = {
                "id": record_id,
                "timestamp": time.time(),
                "date_iso": now_dt.isoformat(),
                "command": command.lstrip("/"),
                "user_id": user_id,
                "username": username,
                "query": str(query).strip(),
                "response": str(response).strip(),
                "sources": clean_sources,
                "status": "pending"
            }

            self._ensure_dirs()
            with open(self.pending_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            logger.info(f"Logged interaction {record_id} ({command}) to {self.pending_file}")
            return record_id
        except Exception as e:
            logger.error(f"Error logging quality interaction: {e}", exc_info=True)
            return None

    def get_pending_records(self) -> List[Dict[str, Any]]:
        """Retrieve all unprocessed records from pending.jsonl."""
        records = []
        if not self.pending_file.exists():
            return records

        try:
            with open(self.pending_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception as parse_err:
                            logger.warning(f"Skipping malformed json line in {self.pending_file}: {parse_err}")
        except Exception as e:
            logger.error(f"Error reading pending quality records: {e}")

        return records

    def get_processed_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent processed records from processed.jsonl."""
        records = []
        if not self.processed_file.exists():
            return records

        try:
            with open(self.processed_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Error reading processed quality records: {e}")

        return records[-limit:]

    def archive_records(
        self,
        record_ids: Optional[List[str]] = None,
        evaluations: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> int:
        """
        Move reviewed records from pending.jsonl to processed.jsonl.
        If record_ids is None, archives all pending records.
        Attaches evaluation data (verdict: yes/no, notes, etc.) if provided.
        """
        all_pending = self.get_pending_records()
        if not all_pending:
            return 0

        target_ids = set(record_ids) if record_ids is not None else {r["id"] for r in all_pending}
        to_archive = []
        to_keep = []

        now_iso = datetime.now(timezone.utc).isoformat()
        for r in all_pending:
            if r.get("id") in target_ids:
                archived_record = dict(r)
                archived_record["status"] = "processed"
                archived_record["archived_at"] = now_iso

                # Merge evaluation if available
                if evaluations and r["id"] in evaluations:
                    ev = evaluations[r["id"]]
                    archived_record["quality_verdict"] = ev.get("verdict", "unspecified")
                    archived_record["quality_notes"] = ev.get("notes", "")
                    archived_record["evaluated_by"] = ev.get("evaluated_by", "Antigravity/Gemini")
                    archived_record["evaluated_at"] = now_iso

                to_archive.append(archived_record)
            else:
                to_keep.append(r)

        if not to_archive:
            return 0

        self._ensure_dirs()
        # 1. Append archived records to processed.jsonl
        try:
            with open(self.processed_file, "a", encoding="utf-8") as f:
                for r in to_archive:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Error writing to processed quality records: {e}")
            return 0

        # 2. Rewrite pending.jsonl with only remaining unreviewed records
        try:
            with open(self.pending_file, "w", encoding="utf-8") as f:
                for r in to_keep:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Error rewriting pending quality records: {e}")

        logger.info(f"Archived {len(to_archive)} quality records to {self.processed_file}. Remaining pending: {len(to_keep)}")
        return len(to_archive)

    def generate_quality_review_report(
        self,
        evaluations: Dict[str, Dict[str, Any]],
        reviewer: str = "Antigravity/Gemini"
    ) -> Path:
        """
        Generate a comprehensive, structured Markdown review report
        and archive all evaluated records so they are never re-reviewed.
        """
        all_pending = {r["id"]: r for r in self.get_pending_records()}
        now_dt = datetime.now(timezone.utc)
        date_str = now_dt.strftime("%Y-%m-%d")
        ts_str = now_dt.strftime("%Y-%m-%d_%H%M%S")

        total_evaluated = len(evaluations)
        yes_count = sum(1 for ev in evaluations.values() if str(ev.get("verdict", "")).lower() == "yes")
        no_count = sum(1 for ev in evaluations.values() if str(ev.get("verdict", "")).lower() == "no")
        other_count = total_evaluated - (yes_count + no_count)
        approval_rate = (yes_count / total_evaluated * 100.0) if total_evaluated > 0 else 0.0

        lines = [
            f"# Jeeves Quality Check & Performance Review ({date_str})",
            f"**Reviewer:** {reviewer} | **Evaluated Date:** {now_dt.isoformat()}",
            f"**Total Answers Evaluated:** {total_evaluated} | **Approval Rate:** {approval_rate:.1f}%\n",
            "## 📊 Executive Summary Scorecard",
            f"| Metric | Value |",
            f"| :--- | :--- |",
            f"| Total Evaluated | **{total_evaluated}** |",
            f"| 👍 Approved (Yes) | **{yes_count}** ({approval_rate:.1f}%) |",
            f"| 👎 Flagged for Improvement (No) | **{no_count}** ({(no_count/total_evaluated*100.0 if total_evaluated else 0):.1f}%) |",
            f"| ⚪ Neutral / Other | **{other_count}** |\n",
            "---",
            "## 🔍 Detailed Q&A Evaluations\n"
        ]

        # Group by Yes vs No
        no_items = []
        yes_items = []

        for rec_id, ev in evaluations.items():
            record = all_pending.get(rec_id, {})
            verdict = str(ev.get("verdict", "")).lower()
            notes = ev.get("notes", "")

            item_md = [
                f"### Record `{rec_id}` — Verdict: **{'👍 YES' if verdict == 'yes' else '👎 NO'}**",
                f"- **Command:** `/{record.get('command', 'unknown')}`",
                f"- **Timestamp:** `{record.get('date_iso', '')}`",
                f"- **User:** `{record.get('username', '')}` (ID: `{record.get('user_id', '')}`)",
                f"- **User Query:**",
                f"  > *\"{record.get('query', '')}\"*",
                f"- **Jeeves Response Snippet:**",
                f"  ```\n  {record.get('response', '')[:500]}...\n  ```",
                f"- **Reviewer Notes & Root Cause Analysis:**",
                f"  {notes if notes else 'N/A'}\n"
            ]
            if verdict == "no":
                no_items.extend(item_md)
            else:
                yes_items.extend(item_md)

        if no_items:
            lines.append("### ⚠️ Answers Flagged for Improvement ([NO])\n")
            lines.extend(no_items)
            lines.append("---\n")

        if yes_items:
            lines.append("### ✅ Approved Answers ([YES])\n")
            lines.extend(yes_items)
            lines.append("---\n")

        lines.extend([
            "## 💡 Recommended System Adjustments",
            "Based on this evaluation cycle:",
            "1. Review any prompt drift or source freshness tiers for queries rated [NO].",
            "2. Update persistent grounding memory in `data/nrl/2026/` or hardware/software caches if facts were missing.",
            "3. Ensure temporal awareness (`< 7 days`) remains enforced across all accredited search pipelines.\n",
            f"*(Archived {total_evaluated} records from `pending.jsonl` to `processed.jsonl`)*"
        ])

        report_file = self.reviews_dir / f"quality_review_{ts_str}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Archive evaluated records
        self.archive_records(list(evaluations.keys()), evaluations)

        logger.info(f"Generated quality review report: {report_file}")
        return report_file

quality_service = QualityService()
