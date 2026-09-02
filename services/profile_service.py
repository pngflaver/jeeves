import os
import json
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import config

logger = logging.getLogger(__name__)

# Heuristics for tone & intent classification
RUDE_PATTERNS = re.compile(
    r"\b(hate you|racist|fake ai|fake taxi|make you pregnant|pregnant|are you gay|you sure a vain|"
    r"vain|stroking your own ego|ego|stupid|dumb|idiot|trash|useless|stfu|shut up|clown|bitch|fucking|fuck)\b",
    re.IGNORECASE
)

TECHNICAL_PATTERNS = re.compile(
    r"\b(fortigate|fortinet|cisco|juniper|palo alto|cli|config|vlan|bgp|ospf|ipsec|vpn|cve|docker|kubernetes|linux|ubuntu|debian|python|port|dns|ping)\b",
    re.IGNORECASE
)

FLIGHT_PATTERNS = re.compile(
    r"\b(flight|fly|airline|air niugini|qantas|schedule|airport|pom|bne|syd|lae|rabaul)\b",
    re.IGNORECASE
)

POLITE_PATTERNS = re.compile(
    r"\b(please|thank you|thanks|kindly|hello|hi|good morning|appreciate|good evening)\b",
    re.IGNORECASE
)

class ProfileService:
    def __init__(self, profiles_file: str = config.USER_PROFILES_FILE):
        self.profiles_file = profiles_file
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load user profiles from disk."""
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    self.profiles = json.load(f)
            except Exception as e:
                logger.error(f"Error reading user profiles from {self.profiles_file}: {e}")
                self.profiles = {}
        else:
            self.profiles = {}

    def _save_profiles(self) -> None:
        """Persist user profiles to disk."""
        try:
            os.makedirs(os.path.dirname(self.profiles_file), exist_ok=True)
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user profiles to {self.profiles_file}: {e}")

    def record_interaction(self, user: Any, chat_id: int, message_text: str) -> Dict[str, Any]:
        """
        Record an incoming message from a Telegram user and update their ongoing profile.
        """
        if not user:
            return {}

        user_id = str(user.id)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Initialize profile if new user
        if user_id not in self.profiles:
            self.profiles[user_id] = {
                "user_id": user.id,
                "username": user.username or "No Username",
                "full_name": user.full_name or "Unknown",
                "first_seen": now_iso,
                "last_seen": now_iso,
                "total_messages": 0,
                "rude_message_count": 0,
                "technical_message_count": 0,
                "message_history": [],
                "assessment": {
                    "archetype": "New User",
                    "tone": "Neutral",
                    "rudeness_score": 1,
                    "summary": "First time interacting with Jeeves.",
                    "traits": ["Newcomer"],
                    "topics": [],
                    "last_assessed": now_iso
                }
            }

        profile = self.profiles[user_id]
        profile["username"] = user.username or profile.get("username", "No Username")
        profile["full_name"] = user.full_name or profile.get("full_name", "Unknown")
        profile["last_seen"] = now_iso
        profile["total_messages"] += 1

        # Classify message flags
        is_rude = bool(RUDE_PATTERNS.search(message_text))
        is_tech = bool(TECHNICAL_PATTERNS.search(message_text))
        is_flight = bool(FLIGHT_PATTERNS.search(message_text))
        is_polite = bool(POLITE_PATTERNS.search(message_text))

        if is_rude:
            profile["rude_message_count"] = profile.get("rude_message_count", 0) + 1
        if is_tech:
            profile["technical_message_count"] = profile.get("technical_message_count", 0) + 1

        # Append to message history (keep last 50 messages per user)
        profile["message_history"].append({
            "timestamp": now_iso,
            "chat_id": chat_id,
            "text": message_text,
            "is_rude": is_rude,
            "is_tech": is_tech,
            "is_flight": is_flight,
            "is_polite": is_polite
        })
        if len(profile["message_history"]) > 50:
            profile["message_history"] = profile["message_history"][-50:]

        # Run automated assessment update
        self._evaluate_user(user_id)
        self._save_profiles()
        return profile

    def _evaluate_user(self, user_id: str) -> None:
        """
        Assess user tone, archetype, rudeness score, and behavioral traits.
        """
        profile = self.profiles.get(user_id)
        if not profile:
            return

        total = profile.get("total_messages", 0)
        if total == 0:
            return

        rude_count = profile.get("rude_message_count", 0)
        tech_count = profile.get("technical_message_count", 0)
        history = profile.get("message_history", [])

        # Calculate Rudeness Score (Scale 1-10)
        rude_ratio = (rude_count / total) if total > 0 else 0
        if rude_ratio >= 0.6:
            score = 9
            tone = "Highly Antagonistic / Troll"
            archetype = "Abusive / Troll"
        elif rude_ratio >= 0.3 or rude_count >= 2:
            score = 7
            tone = "Rude / Provocative"
            archetype = "Challenger / Provocateur"
        elif rude_ratio > 0 or rude_count == 1:
            score = 4
            tone = "Occasionally Blunt / Sarcastic"
            archetype = "Casual Inquisitor"
        elif tech_count >= 2:
            score = 1
            tone = "Technical & Professional"
            archetype = "Engineer / IT Professional"
        else:
            score = 2
            tone = "Neutral / Polite"
            archetype = "Standard Group Member"

        # Extract topics
        topics = set()
        for m in history:
            txt = m.get("text", "").lower()
            if "forti" in txt: topics.add("Fortinet")
            if "cisco" in txt: topics.add("Cisco")
            if "flight" in txt or "airline" in txt: topics.add("Aviation")
            if "gay" in txt or "pregnant" in txt or "racist" in txt or "ego" in txt or "vain" in txt: topics.add("Bot Persona Testing / Trolling")

        # Generate summary description
        traits = []
        if score >= 7:
            traits.append("Hostile Tone")
            traits.append("Provocative Questions")
            traits.append("Boundary Testing")
            summary = f"User frequently sends provocative, rude, or sexually/socially sensitive prompts to test bot limits ({rude_count}/{total} messages flagged)."
        elif archetype == "Engineer / IT Professional":
            traits.append("Technical Focus")
            traits.append("Constructive")
            summary = f"User primarily asks focused engineering, network diagnostic, or technical configuration questions ({tech_count}/{total} queries)."
        else:
            traits.append("General Participant")
            summary = f"User has sent {total} standard message(s) with neutral interaction history."

        profile["assessment"] = {
            "archetype": archetype,
            "tone": tone,
            "rudeness_score": score,
            "summary": summary,
            "traits": traits,
            "topics": list(topics),
            "last_assessed": datetime.now(timezone.utc).isoformat()
        }

    def assess_all_users(self) -> Dict[str, Any]:
        """Run a full daily/on-demand reassessment across all profiled users."""
        count = 0
        for uid in list(self.profiles.keys()):
            self._evaluate_user(uid)
            count += 1
        self._save_profiles()
        return {"total_assessed": count, "timestamp": datetime.now(timezone.utc).isoformat()}

    def find_user_profile(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find profile by user_id or @username (case-insensitive).
        """
        clean_id = identifier.strip().lstrip("@").lower()
        # 1. Match by numeric ID
        if clean_id in self.profiles:
            return self.profiles[clean_id]

        # 2. Match by username or full name
        for uid, p in self.profiles.items():
            u_name = str(p.get("username", "")).lower()
            f_name = str(p.get("full_name", "")).lower()
            if clean_id == u_name or clean_id in f_name or str(uid) == clean_id:
                return p
        return None

    def get_all_profiles_summary(self) -> List[Dict[str, Any]]:
        """List summary of all users sorted by highest rudeness score & message count."""
        summary_list = []
        for uid, p in self.profiles.items():
            ass = p.get("assessment", {})
            summary_list.append({
                "user_id": uid,
                "username": p.get("username", "No Username"),
                "full_name": p.get("full_name", "Unknown"),
                "total_messages": p.get("total_messages", 0),
                "rudeness_score": ass.get("rudeness_score", 1),
                "tone": ass.get("tone", "Neutral"),
                "archetype": ass.get("archetype", "Standard User"),
                "last_seen": p.get("last_seen", "")
            })
        summary_list.sort(key=lambda x: (x["rudeness_score"], x["total_messages"]), reverse=True)
        return summary_list

profile_service = ProfileService()
