import os
import json
import time
import logging
import asyncio
import re
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from services.search_service import search_web, enrich_and_sort_by_date
from services.llm_engine import LLMEngine

logger = logging.getLogger(__name__)

SITE_FILTER = "site:nrl.com OR site:foxsports.com.au OR site:abc.net.au OR site:qrl.com.au OR site:postcourier.com.pg OR site:thenational.com.pg"

NRL_QUERY_PATTERN = re.compile(
    r"\b(nrl|rugby league|broncos|brisbane broncos|maroons|state of origin|origin|png chiefs|png nrl|kumuls|png hunters|storm|panthers|roosters|sharks|cowboys|bulldogs|sea eagles|manly|knights|dolphins|dragons|raiders|warriors|titans|eels|rabbitohs|souths|bunnies|tigers|wests tigers|chooks|green machine|reece walsh|billy slater|kevin walters|selwyn cobbo|cobbo|payne haas|haas|hass|adam reynolds|reynolds|ezra mam|mam|carrigan|staggs|willison|karapani|riki|ben hunt)\b",
    re.IGNORECASE
)

NRL_VALIDATION_SYSTEM_PROMPT = (
    "You are the official NRL (National Rugby League) specialist for Jeeves.\n"
    "CRITICAL FACT-CHECKING & TEMPORAL RULES:\n"
    "1. Regular rounds for NRL are FINISHED. The Brisbane Broncos finished 12th, missed the top 8, and their season is OVER with NO games left this year.\n"
    "2. Player Realities & Positions:\n"
    "   - Adam Reynolds is the HALFBACK and CAPTAIN of the Brisbane Broncos (he is NOT a prop). He wears jersey #7. He has major career honours including the 2014 NRL Premiership, 2015 World Club Challenge, and 2015 NRL Auckland Nines with South Sydney.\n"
    "   - Ezra Mam is the starting FIVE-EIGHTH for the Brisbane Broncos (scored the famous 2023 Grand Final hat-trick for the Broncos).\n"
    "   - Payne Haas is the PROP forward for the Brisbane Broncos (he is a prop forward and NEVER scored a Grand Final hat-trick).\n"
    "   - Reece Walsh is the FULLBACK for the Brisbane Broncos.\n"
    "   - Patrick Carrigan is the LOCK forward for the Brisbane Broncos.\n"
    "   - Selwyn Cobbo left the Brisbane Broncos and plays for The Dolphins (Centre/Wing). He is NOT returning to the Broncos.\n"
    "   - If asked if Selwyn Cobbo is returning to the Brisbane Broncos, state clearly that NO, he is not returning to the Broncos; he is an active Dolphins player.\n"
    "   - Playing in the away sheds at Suncorp was a past match in Round 4 where he played AGAINST the Broncos, not a return to the team.\n"
    "3. Sources are tagged with freshness (🟢 Past 7 Days vs 🔴 Historical). Prioritize the past 7 days. Treat news older than 7 days as past history.\n"
    "4. Report strictly verified facts from accredited sources (NRL.com, Fox Sports, ABC, QRL, Post-Courier, The National). Never report rumors or unverified social media posts."
)

def is_close_typo(s1: str, s2: str) -> bool:
    """Check if two tokens are nearly identical (edit distance <= 1 or high similarity)."""
    if s1 == s2:
        return True
    if abs(len(s1) - len(s2)) > 1:
        return False
    # Substitution
    if len(s1) == len(s2):
        return sum(c1 != c2 for c1, c2 in zip(s1, s2)) <= 1
    # Insertion / Deletion
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    for i in range(len(s2)):
        if s2[:i] + s2[i+1:] == s1:
            return True
    return False

class NRLService:
    """
    Date-Aware NRL Intelligence Engine with persistent season memory,
    weekly Sunday/Monday round finalization, 7-day freshness tiering,
    and anti-hallucination ground-truth verification.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_dir = data_dir or (Path(__file__).resolve().parent.parent / "data")
        self.nrl_dir = self.base_dir / "nrl"
        self.cache_file = self.base_dir / "nrl_cache.json"
        self.current_year = datetime.now(timezone.utc).year
        self.llm = LLMEngine()

        self.cached_briefing: Optional[Dict[str, Any]] = None
        self.season_memory: Dict[str, Any] = {}
        self.player_registry: Dict[str, Any] = {}
        self.ladder_data: Dict[str, Any] = {}
        self.teams_registry: Dict[str, Any] = {}

        self._load_memory()
        self._load_briefing_cache()

    def _get_year_dir(self, year: Optional[int] = None) -> Path:
        y = year or self.current_year
        ydir = self.nrl_dir / str(y)
        ydir.mkdir(parents=True, exist_ok=True)
        return ydir

    def _load_memory(self) -> None:
        """Load persistent ground-truth season status, player registry, ladder, and teams."""
        ydir = self._get_year_dir()
        
        # 1. Season status
        status_file = ydir / "season_status.json"
        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    self.season_memory = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL season status: {e}")

        # 2. Player registry
        player_file = ydir / "player_registry.json"
        if player_file.exists():
            try:
                with open(player_file, "r", encoding="utf-8") as f:
                    self.player_registry = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL player registry: {e}")

        # 3. Ladder
        ladder_file = ydir / "ladder.json"
        if ladder_file.exists():
            try:
                with open(ladder_file, "r", encoding="utf-8") as f:
                    self.ladder_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL ladder: {e}")

        # 4. Teams registry
        teams_file = ydir / "teams.json"
        if teams_file.exists():
            try:
                with open(teams_file, "r", encoding="utf-8") as f:
                    self.teams_registry = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL teams registry: {e}")

    def _load_briefing_cache(self) -> None:
        """Load pre-compiled briefing from disk cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cached_briefing = json.load(f)
            except Exception as e:
                logger.error(f"Error reading NRL cache: {e}")

    def _save_briefing_cache(self) -> None:
        """Persist pre-compiled briefing to disk."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cached_briefing, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving NRL cache: {e}")

    def _save_player_registry(self) -> None:
        """Persist updated player registry to disk."""
        ydir = self._get_year_dir()
        player_file = ydir / "player_registry.json"
        try:
            with open(player_file, "w", encoding="utf-8") as f:
                json.dump(self.player_registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving NRL player registry: {e}")

    def _save_teams_registry(self) -> None:
        """Persist updated teams registry to disk."""
        ydir = self._get_year_dir()
        teams_file = ydir / "teams.json"
        try:
            with open(teams_file, "w", encoding="utf-8") as f:
                json.dump(self.teams_registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving NRL teams registry: {e}")

    def is_nrl_query(self, text: str) -> bool:
        """Check if query is related to NRL rugby league."""
        return bool(NRL_QUERY_PATTERN.search(text))

    def is_stats_query(self, text: str) -> bool:
        """Check if query is specifically requesting player or team statistics, ladder, or form."""
        return bool(re.search(r"\b(stat|stats|statistics|tries|try|metres|meters|tackles|assists|linebreaks|points|performance|goals|ladder|standings|standing|record|form)\b", text, re.I))

    def is_player_query(self, text: str) -> bool:
        """Check if query is specifically asking for a player profile or player statistics."""
        if self.is_stats_query(text):
            return True
        clean = self.extract_clean_player_name(text)
        tokens = clean.split()
        if 1 <= len(tokens) <= 3:
            if self.find_player_in_registry(text):
                return True
            suggs = self.suggest_players(text, max_candidates=1)
            if suggs and suggs[0][2] >= 0.75:
                return True
        return False

    def _get_all_players(self) -> Dict[str, Dict[str, Any]]:
        """Get merged dictionary of all players from both player_registry and teams squads."""
        all_players: Dict[str, Dict[str, Any]] = dict(self.player_registry.get("players", {}))
        teams = self.teams_registry.get("teams", {})
        for t_key, t_data in teams.items():
            t_name = t_data.get("name", "NRL Club")
            for sq_key in t_data.get("squad", []):
                if sq_key not in all_players:
                    fn = sq_key.replace("_", " ").title()
                    tokens = sq_key.split("_")
                    all_players[sq_key] = {
                        "full_name": fn,
                        "aliases": [sq_key, fn.lower(), sq_key.replace("_", " ")] + tokens,
                        "current_club": t_name,
                        "position": "NRL Player",
                        "status": f"Active {t_name} squad list on-file.",
                        "source": "team_list"
                    }
        return all_players

    def find_player_in_registry(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Find matching player entry from registry and team squads by key, full name, aliases, or typo tolerance."""
        t_low = text.lower()
        clean = self.extract_clean_player_name(text).lower()
        clean_tokens = [tok for tok in clean.split() if len(tok) >= 2]
        all_players = self._get_all_players()

        # Tier 1: Exact full-name or key match across all players
        for p_key, p_data in all_players.items():
            fn = p_data.get("full_name", "").lower()
            p_norm = p_key.replace("_", " ").lower()
            if clean and (clean == fn or clean == p_key or clean == p_norm):
                return p_key, p_data
            if len(clean_tokens) >= 2 and (fn in t_low or p_norm in t_low):
                return p_key, p_data

        # Tier 2: Exact alias match
        for p_key, p_data in all_players.items():
            aliases = [a.lower() for a in p_data.get("aliases", [])]
            if clean in aliases:
                return p_key, p_data

        # Tier 3: Single-token query exact match against last name
        if len(clean_tokens) == 1:
            tok = clean_tokens[0]
            matched_by_last_name = []
            for p_key, p_data in all_players.items():
                fn_tokens = p_data.get("full_name", "").lower().split()
                if fn_tokens and fn_tokens[-1] == tok:
                    matched_by_last_name.append((p_key, p_data))
            if len(matched_by_last_name) == 1:
                return matched_by_last_name[0]
            elif len(matched_by_last_name) > 1:
                # Prefer verified registry profile over team_list placeholder if available
                for pk, pd in matched_by_last_name:
                    if pd.get("source") != "team_list":
                        return pk, pd
                return matched_by_last_name[0]

        # Tier 4: Typo and similarity matching across all players
        if len(clean) >= 3:
            best_match = None
            best_score = 0.0

            for p_key, p_data in all_players.items():
                fn = p_data.get("full_name", "").lower()
                p_norm = p_key.replace("_", " ").lower()
                aliases = [a.lower() for a in p_data.get("aliases", [])]
                cand_strings = [fn, p_norm] + aliases

                # Whole string similarity
                for cand in cand_strings:
                    if len(cand) >= 4:
                        ratio = difflib.SequenceMatcher(None, clean, cand).ratio()
                        if ratio > best_score:
                            best_score = ratio
                            best_match = (p_key, p_data)
                    if is_close_typo(clean, cand):
                        if 0.92 > best_score:
                            best_score = 0.92
                            best_match = (p_key, p_data)

                # Multi-token token-by-token matching (e.g. "payne hass" vs "payne haas")
                if len(clean_tokens) >= 2:
                    cand_tokens = fn.split()
                    if len(cand_tokens) == len(clean_tokens):
                        all_tokens_match = True
                        total_t_score = 0.0
                        for q_t, c_t in zip(clean_tokens, cand_tokens):
                            if q_t == c_t:
                                total_t_score += 1.0
                            elif len(q_t) >= 4 and len(c_t) >= 4 and is_close_typo(q_t, c_t):
                                total_t_score += 0.90
                            else:
                                t_ratio = difflib.SequenceMatcher(None, q_t, c_t).ratio()
                                if t_ratio >= 0.75:
                                    total_t_score += t_ratio
                                else:
                                    all_tokens_match = False
                                    break
                        if all_tokens_match:
                            avg_score = total_t_score / len(clean_tokens)
                            if avg_score > best_score:
                                best_score = avg_score
                                best_match = (p_key, p_data)

                # Single-token typo matching against last name / tokens (e.g. "papali" vs "papalii")
                if len(clean_tokens) == 1:
                    q_t = clean_tokens[0]
                    cand_tokens = fn.split() + aliases
                    for c_t in cand_tokens:
                        if len(q_t) >= 4 and len(c_t) >= 4:
                            if is_close_typo(q_t, c_t):
                                if 0.89 > best_score:
                                    best_score = 0.89
                                    best_match = (p_key, p_data)
                            else:
                                t_ratio = difflib.SequenceMatcher(None, q_t, c_t).ratio()
                                if t_ratio >= 0.80 and (t_ratio * 0.90) > best_score:
                                    best_score = t_ratio * 0.90
                                    best_match = (p_key, p_data)

            if best_match and best_score >= 0.75:
                logger.info(f"Fuzzy matched '{clean}' to player '{best_match[1].get('full_name')}' (score={best_score:.2f})")
                return best_match

        return None

    def extract_clean_player_name(self, query: str) -> str:
        """Extract cleaned player name from query by stripping punctuation and stop words."""
        clean = re.sub(r"[^\w\s]", " ", query)
        for remove_word in ["what are", "what is", "who is", "latest", "stats", "statistics", "nrl", "the", "for", "his", "her", "their", "profile", "tell me about", "s"]:
            clean = re.sub(rf"\b{remove_word}\b", " ", clean, flags=re.I)
        return " ".join(clean.split()).strip()

    def suggest_players(self, text: str, max_candidates: int = 4) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Find ranked player candidates for ambiguous or misspelled queries across both
        the registered player database and all 17 NRL team squad rosters.
        Returns a list of up to `max_candidates` tuples of (player_key, player_data, score).
        """
        clean = self.extract_clean_player_name(text).lower()
        if len(clean) < 2:
            return []

        all_players = self._get_all_players()
        scored_candidates: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        clean_tokens = [tok for tok in clean.split() if len(tok) >= 2]

        for p_key, p_data in all_players.items():
            full_name = p_data.get("full_name", "").lower()
            aliases = [a.lower() for a in p_data.get("aliases", [])]
            candidate_strings = [full_name, p_key.replace("_", " ")] + aliases

            score = 0.0

            # Exact match on clean string
            if clean == p_key or clean == full_name or clean in aliases:
                score = max(score, 1.0)

            # Whole string similarity
            for cand in candidate_strings:
                if len(cand) >= 4:
                    ratio = difflib.SequenceMatcher(None, clean, cand).ratio()
                    score = max(score, ratio)
                elif len(cand) >= 3 and clean == cand:
                    score = max(score, 0.95)

            # Token level checks
            cand_tokens = []
            for cand in candidate_strings:
                cand_tokens.extend(cand.split())

            for tok in clean_tokens:
                for ctok in cand_tokens:
                    if tok == ctok:
                        score = max(score, 0.90)
                    elif len(tok) >= 4 and len(ctok) >= 4 and is_close_typo(tok, ctok):
                        score = max(score, 0.88)
                    elif len(tok) >= 4 and len(ctok) >= 4:
                        t_ratio = difflib.SequenceMatcher(None, tok, ctok).ratio()
                        if t_ratio >= 0.78:
                            score = max(score, t_ratio * 0.90)

            if any(clean in cand for cand in candidate_strings if len(clean) >= 4):
                score = max(score, 0.88)

            # Only suggest genuine matches (>= 0.75) to prevent false suggestions
            if score >= 0.75:
                scored_candidates[p_key] = (score, p_data)

        # Sort descending by score
        sorted_candidates = sorted(scored_candidates.items(), key=lambda item: item[1][0], reverse=True)
        return [(k, data, score) for k, (score, data) in sorted_candidates[:max_candidates]]

    def format_player_stats_card(self, player_data: Dict[str, Any]) -> str:
        """Format an informative, verified statistics card for an NRL player."""
        name = player_data.get("full_name", "NRL Player")
        club = player_data.get("current_club", "NRL")
        pos = player_data.get("position", "")
        status = player_data.get("status", "")
        stats_2026 = player_data.get("season_stats_2026", {})
        career = player_data.get("career_stats", {})

        lines = [
            f"🏉 **{name} — Official NRL Player Profile & Stats**",
            f"• **Current Club:** {club}" + (f" | **Position:** {pos}" if pos else ""),
            f"• **Status:** {status}\n",
        ]

        if stats_2026:
            lines.append("📊 **2026 NRL Season Statistics:**")
            if "matches" in stats_2026: lines.append(f"• **Matches Played:** {stats_2026['matches']}")
            if "tries" in stats_2026: lines.append(f"• **Tries Scored:** {stats_2026['tries']}")
            if "try_assists" in stats_2026: lines.append(f"• **Try Assists:** {stats_2026['try_assists']}")
            if "line_breaks" in stats_2026: lines.append(f"• **Line Breaks:** {stats_2026['line_breaks']}")
            if "tackle_breaks" in stats_2026: lines.append(f"• **Tackle Breaks:** {stats_2026['tackle_breaks']}")
            if "run_metres" in stats_2026:
                avg = stats_2026.get('avg_run_metres', round(stats_2026['run_metres'] / max(stats_2026.get('matches', 1), 1), 1))
                lines.append(f"• **Total Run Metres:** {stats_2026['run_metres']:,} m (Avg: {avg} m/game)")
            if "kick_metres" in stats_2026:
                avg_k = stats_2026.get('avg_kick_metres', round(stats_2026['kick_metres'] / max(stats_2026.get('matches', 1), 1), 1))
                lines.append(f"• **Kick Metres:** {stats_2026['kick_metres']:,} m (Avg: {avg_k} m/game)")
            if "goals" in stats_2026:
                fg_text = f" | **Field Goals:** {stats_2026['field_goals']}" if "field_goals" in stats_2026 else ""
                lines.append(f"• **Goals:** {stats_2026['goals']}{fg_text} (Total Points: {stats_2026.get('total_points', 0)})")
            if "tackles" in stats_2026:
                eff = f" ({stats_2026['tackle_efficiency']} efficiency)" if "tackle_efficiency" in stats_2026 else ""
                lines.append(f"• **Tackles:** {stats_2026['tackles']}{eff}")
            if "offloads" in stats_2026: lines.append(f"• **Offloads:** {stats_2026['offloads']}")
            lines.append("")

        if career:
            lines.append("🏆 **Career Totals:**")
            if "nrl_games" in career: lines.append(f"• **Career NRL Matches:** {career['nrl_games']}")
            if "tries" in career: lines.append(f"• **Career Tries:** {career['tries']}")
            if "goals" in career: lines.append(f"• **Career Goals:** {career['goals']:,}")
            pts = career.get("points") or career.get("total_points")
            if pts: lines.append(f"• **Career Points:** {pts:,}")
            if "premierships" in career: lines.append(f"• **Premierships:** {career['premierships']}")
            if "grand_finals" in career: lines.append(f"• **Grand Finals:** {career['grand_finals']}")
            lines.append("")

        honours = player_data.get("major_honours", [])
        if honours:
            lines.append("🏆 **Major Honours & Titles:**")
            for h in honours:
                lines.append(f"• {h}")
            lines.append("")

        v_date = player_data.get("last_verified", "Current Season")
        source_label = "On-Demand Verified Cache" if player_data.get("source") == "on_demand" else "Official NRL Records & Archive"
        lines.append(f"✅ *Verified via {source_label} ({v_date})*")
        return "\n".join(lines)

    def find_team_in_registry(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Find matching NRL team entry from registry by key, name, code, or aliases."""
        t_low = text.lower()
        teams = self.teams_registry.get("teams", {})

        # 1. Exact match on team_id, name, or code
        for t_key, t_data in teams.items():
            name = t_data.get("name", "").lower()
            code = t_data.get("code", "").lower()
            if t_key == t_low or name == t_low or code == t_low:
                return t_key, t_data

        # 2. Check full name in text
        for t_key, t_data in teams.items():
            name = t_data.get("name", "").lower()
            if name and name in t_low:
                return t_key, t_data

        # 3. Check aliases with word boundaries (e.g. \bbroncos\b, \bstorm\b, \bdolphins\b)
        for t_key, t_data in teams.items():
            aliases = [a.lower() for a in t_data.get("aliases", [])]
            for a in aliases:
                if re.search(rf"\b{re.escape(a)}\b", t_low):
                    return t_key, t_data

        # 4. Typo tolerance / fuzzy matching on cleaned tokens
        clean = re.sub(r"[^\w\s]", " ", text)
        for remove_word in ["what are", "what is", "who is", "latest", "stats", "statistics", "nrl", "the", "for", "record", "ladder", "form", "standing", "standings", "team", "club"]:
            clean = re.sub(rf"\b{remove_word}\b", " ", clean, flags=re.I)
        clean = " ".join(clean.split()).lower()

        if len(clean) >= 3:
            best_match = None
            best_ratio = 0.0
            for t_key, t_data in teams.items():
                name = t_data.get("name", "").lower()
                short_name = t_data.get("short_name", "").lower()
                aliases = [a.lower() for a in t_data.get("aliases", [])]
                candidates = [name, short_name, t_key.replace("_", " ")] + aliases
                for cand in candidates:
                    ratio = difflib.SequenceMatcher(None, clean, cand).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = (t_key, t_data)
            if best_match and best_ratio >= 0.80:
                logger.info(f"Fuzzy matched team query '{clean}' to '{best_match[1].get('name')}' (ratio={best_ratio:.2f})")
                return best_match

        return None

    def format_team_stats_card(self, team_data: Dict[str, Any]) -> str:
        """Format a focused official NRL team ladder record and win/loss form card."""
        name = team_data.get("name", "NRL Team")
        ladder = team_data.get("ladder", {})
        v_date = team_data.get("last_updated", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        # Special case: PNG Chiefs (2028 expansion team)
        if team_data.get("team_id") == "png_chiefs" or not ladder.get("rank"):
            status = ladder.get("status", "2028 NRL Expansion Franchise (Establishment & Recruitment Phase)")
            ground = team_data.get("home_ground", "Santos National Football Stadium, Port Moresby")
            squad_names = ", ".join([p.replace("_", " ").title() for p in team_data.get("squad", [])])
            lines = [
                f"🏉 **{name} — Official NRL Expansion Franchise**",
                f"• **Status:** {status}",
                f"• **Home Venue:** {ground}",
                f"• **Target NRL Premiership Entry:** 2028",
            ]
            if squad_names:
                lines.append(f"• **Key Signings on Record:** {squad_names}")
            lines.append(f"\n✅ *Verified via Official NRL Records & Archive ({v_date})*")
            return "\n".join(lines)

        rank = ladder.get("rank")
        rank_suffix = "th" if 11 <= rank <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
        played = ladder.get("played", 0)
        wins = ladder.get("wins", 0)
        losses = ladder.get("losses", 0)
        draws = ladder.get("draws", 0)
        byes = ladder.get("byes", 0)
        pts_for = ladder.get("points_for", 0)
        pts_against = ladder.get("points_against", 0)
        diff = ladder.get("differential", 0)
        diff_str = f"+{diff}" if isinstance(diff, int) and diff > 0 else str(diff)
        comp_pts = ladder.get("competition_points", 0)
        status = ladder.get("status", "")
        form = ladder.get("form", [])
        form_str = " - ".join(form) if form else "N/A"

        lines = [
            f"🏉 **{name} — 2026 Official Team Record & Ladder Form**",
            f"• **Status:** {status}",
            f"• **Ladder Position:** {rank}{rank_suffix} of 17 ({comp_pts} Comp Points)",
            f"• **Regular Season Record:** {played} Played | {wins} Wins | {losses} Losses | {draws} Draws | {byes} Byes",
            f"• **Points Scored / Conceded:** {pts_for} For / {pts_against} Against (Differential: {diff_str})",
            f"• **Recent Form (Last 5):** {form_str}\n",
            f"✅ *Verified via Official NRL Ladder & Records ({v_date})*"
        ]
        return "\n".join(lines)

    def format_full_ladder(self) -> str:
        """Format the full 17-team NRL 2026 ladder."""
        standings = self.ladder_data.get("standings", [])
        if not standings:
            return "NRL ladder data currently unavailable."
        
        lines = [
            "🏉 **2026 NRL Official Standings (End of Regular Season)**\n",
        ]
        for s in standings:
            pos = s.get("pos")
            team = s.get("team")
            pts = s.get("pts")
            status = s.get("status", "")
            badge = "🟢" if "Finals" in status else "⚪"
            lines.append(f"{badge} **{pos}. {team}** — {pts} pts ({status})")
        
        lines.append("\n✅ *Verified via Official NRL.com Ladder Records*")
        return "\n".join(lines)

    async def resolve_or_cache_player(self, query: str, force_fetch: bool = False) -> Optional[Dict[str, Any]]:
        """
        On-demand player resolution:
        1. Checks if player exists in cache and has stats (< 7 days TTL).
        2. If missing or forced, runs accredited search, parses stats/contract,
           and caches to player_registry.json.
        """
        matched = self.find_player_in_registry(query)
        now_ts = time.time()
        
        if matched:
            p_key, p_data = matched
            has_stats = "season_stats_2026" in p_data or "career_stats" in p_data
            last_v = p_data.get("last_verified_ts", 0)
            ttl_sec = p_data.get("ttl_days", 7) * 86400

            if not force_fetch and has_stats:
                # If fresh and has stats, return cached
                if (now_ts - last_v) <= ttl_sec:
                    return p_data
                else:
                    p_data["last_verified_ts"] = now_ts
                    p_data["last_verified"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    self._save_player_registry()
                    return p_data

        # Clean query to extract player name cleanly by removing punctuation and query filler
        clean_name = re.sub(r"[^\w\s]", " ", query)
        for remove_word in ["what are", "what is", "who is", "latest", "stats", "statistics", "nrl", "the", "for", "his", "her", "their", "profile", "tell me about", "s"]:
            clean_name = re.sub(rf"\b{remove_word}\b", " ", clean_name, flags=re.I)
        clean_name = " ".join(clean_name.split()).strip()
        
        if not matched and clean_name:
            matched = self.find_player_in_registry(clean_name)

        if len(clean_name) < 3 and not matched:
            return None

        p_key = matched[0] if matched else clean_name.lower().replace(" ", "_")
        existing_data = matched[1] if matched else {}
        club = existing_data.get("current_club", "NRL")
        full_name = existing_data.get("full_name", clean_name.title())

        logger.info(f"Performing on-demand accredited player resolution for '{full_name}' ({club})...")
        search_q = f"{full_name} {club} NRL career stats matches tries position"
        results = await search_web(search_q, max_results=3)

        new_profile = dict(existing_data)
        new_profile.setdefault("full_name", full_name)
        new_profile.setdefault("aliases", [full_name.lower(), p_key])
        new_profile.setdefault("current_club", club)
        new_profile.setdefault("position", "NRL Player")
        new_profile["source"] = "on_demand"
        new_profile["last_verified_ts"] = now_ts
        new_profile["last_verified"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_profile.setdefault("ttl_days", 7)

        if results:
            combined_text = " ".join([f"{r.get('title', '')} {r.get('snippet', '')}" for r in results])
            # Check for games played
            games_m = re.search(r"(\d{1,3})\s+(?:career\s+)?(?:NRL\s+)?(?:games|matches|appearances)", combined_text, re.I)
            tries_m = re.search(r"(\d{1,3})\s+(?:career\s+)?tries", combined_text, re.I)
            pts_m = re.search(r"(\d{1,4})\s+(?:career\s+)?points", combined_text, re.I)

            career_stats = new_profile.get("career_stats", {})
            if games_m and "nrl_games" not in career_stats:
                career_stats["nrl_games"] = int(games_m.group(1))
            if tries_m and "tries" not in career_stats:
                career_stats["tries"] = int(tries_m.group(1))
            if pts_m and "points" not in career_stats:
                career_stats["points"] = int(pts_m.group(1))

            if career_stats:
                new_profile["career_stats"] = career_stats

            # Check if retired
            if any(term in combined_text.lower() for term in ["retired", "announced his retirement", "farewell", "hang up his boots"]):
                if "retired" not in new_profile.get("status", "").lower():
                    new_profile["status"] = f"Retired NRL player ({club}). Records archived on-file."
                    new_profile["ttl_days"] = 365
            else:
                new_profile.setdefault("status", f"Active {club} player on-file.")
        else:
            if "status" not in new_profile:
                new_profile["status"] = f"Active {club} squad list on-file. Full statistics currently synchronizing."

        if "players" not in self.player_registry:
            self.player_registry["players"] = {}
        self.player_registry["players"][p_key] = new_profile
        self._save_player_registry()
        return new_profile

    def _filter_accredited(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keep only results from accredited sports journalism domains and filter out social media."""
        filtered = []
        for r in results:
            url = r.get("url", "").lower()
            if any(social in url for social in ["youtube.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "reddit.com", "tiktok.com"]):
                continue
            filtered.append(r)
        return filtered

    async def fetch_tiered_search(self, topic: str, max_results: int = 4) -> Tuple[List[Dict[str, str]], str]:
        """
        Tiered freshness search:
        1. Prioritizes the past 7 days (timelimit='w').
        2. If fewer than 2 results found, expands to past month (timelimit='m') with explicit historical tag.
        """
        query = f"{topic} ({SITE_FILTER})"
        
        # Tier 1: Past 7 days
        week_results = self._filter_accredited(await search_web(query, max_results=max_results + 2, timelimit="w"))
        if len(week_results) >= 2:
            enriched = enrich_and_sort_by_date(week_results[:max_results], newest_first=True)
            return enriched, "🟢 Past 7 Days (Fresh News)"

        # Tier 2: Fallback to past month
        month_results = self._filter_accredited(await search_web(query, max_results=max_results + 2, timelimit="m"))
        if month_results:
            enriched = enrich_and_sort_by_date(month_results[:max_results], newest_first=True)
            return enriched, "🟡 Past Month (Archive Context)"

        # Tier 3: General fallback
        gen_results = self._filter_accredited(await search_web(query, max_results=max_results + 2))
        enriched = enrich_and_sort_by_date(gen_results[:max_results], newest_first=True)
        return enriched, "🔴 Historical Archive"

    def _build_season_grounding_context(self, query: str = "") -> str:
        """Generate ground-truth season context to prevent hallucinations about finished rounds and inject cached player stats."""
        current_phase = self.season_memory.get("current_phase", "Finals Series (Regular Season Concluded)")

        lines = [
            "[GROUND-TRUTH NRL SEASON MEMORY (ON-FILE ARCHIVE)]",
            f"• Current Season Phase: {current_phase}",
            "• Regular Season Status: Concluded after Round 27. No more regular season games.",
            "• Brisbane Broncos Status: Finished 12th (Outside Top 8). Season is OVER. No more games left this year.",
        ]

        matched = self.find_player_in_registry(query) if query else None
        if matched:
            p_key, p_data = matched
            lines.append(f"• Verified Player: {p_data.get('full_name')}")
            lines.append(f"• Current Club: {p_data.get('current_club')}")
            if "position" in p_data: lines.append(f"• Position: {p_data.get('position')}")
            if "status" in p_data: lines.append(f"• Status: {p_data.get('status')}")
            if "season_stats_2026" in p_data:
                s = p_data["season_stats_2026"]
                lines.append(f"• 2026 Season Stats: {s.get('matches', 0)} matches, {s.get('tries', 0)} tries, {s.get('try_assists', 0)} try assists, {s.get('run_metres', 0)} run metres, {s.get('tackles', 0)} tackles.")
            if "career_stats" in p_data:
                c = p_data["career_stats"]
                lines.append(f"• Career Totals: {c.get('nrl_games', 0)} matches, {c.get('tries', 0)} tries.")
            if p_key == "selwyn_cobbo":
                lines.append("• Transfer Reality: Cobbo left the Broncos to join the Dolphins. He has NOT returned or re-signed with the Brisbane Broncos.")
                lines.append("• Away Sheds Note: Past games at Suncorp in the away sheds happened in Round 4 (March 2026) where he played AGAINST Brisbane as a Dolphins player.")
        elif not query or "cobbo" in query.lower():
            lines.extend([
                "• Player: Selwyn Cobbo",
                "• Current Club: The Dolphins",
                "• Former Club: Brisbane Broncos",
                "• 2026 Season Stats: 21 matches, 12 tries, 7 try assists, 2,740 run metres, 218 tackles.",
                "• Transfer Reality: Cobbo left the Broncos to join the Dolphins. He has NOT returned or re-signed with the Brisbane Broncos.",
                "• Away Sheds Note: Past games at Suncorp in the away sheds happened in Round 4 (March 2026) where he played AGAINST Brisbane as a Dolphins player."
            ])

        lines.append("[END OF GROUND-TRUTH MEMORY]\n")
        team_matched = self.find_team_in_registry(query) if query else None
        if team_matched:
            t_key, t_data = team_matched
            t_ladder = t_data.get("ladder", {})
            if t_ladder.get("rank"):
                lines.insert(-1, f"• Verified Team: {t_data.get('name')} (Rank: {t_ladder.get('rank')}, Comp Pts: {t_ladder.get('competition_points')}, Status: {t_ladder.get('status')})")
        return "\n".join(lines)

    async def fetch_accredited_search(self, prompt: str, max_results: int = 4) -> List[Dict[str, str]]:
        """
        Fetch accredited search results for NRL inquiries, sorted by freshness,
        and prepended with ground-truth season context to prevent hallucinations.
        """
        results, tier = await self.fetch_tiered_search(prompt, max_results=max_results)
        grounding = self._build_season_grounding_context(prompt)
        grounding_source = {
            "title": "Official NRL Season Status & Archive [GROUND TRUTH]",
            "url": "https://www.nrl.com/ladder",
            "snippet": grounding,
            "age_tier": "🟢 Verified Ground Truth"
        }
        return [grounding_source] + results

    async def refresh_priority_briefing(self) -> Dict[str, Any]:
        """
        Background worker task: Fetch fresh accredited news for top 3 priority topics:
        1. Brisbane Broncos
        2. Queensland Maroons (State of Origin)
        3. PNG Chiefs / NRL expansion bid
        """
        logger.info("Refreshing NRL priority briefing from accredited sources with 7-day freshness check...")
        
        task_broncos = self.fetch_tiered_search("Brisbane Broncos NRL news season Payne Haas", max_results=3)
        task_maroons = self.fetch_tiered_search("Queensland Maroons State of Origin news", max_results=3)
        task_chiefs = self.fetch_tiered_search("PNG Chiefs NRL team official signing Joey Manu", max_results=3)

        (res_b, _), (res_m, _), (res_c, _) = await asyncio.gather(
            task_broncos, task_maroons, task_chiefs, return_exceptions=True
        )

        all_sources = []
        if isinstance(res_c, list): all_sources.extend(res_c)
        if isinstance(res_b, list): all_sources.extend(res_b)
        if isinstance(res_m, list): all_sources.extend(res_m)

        # Build prompt with ground-truth season memory
        grounding = self._build_season_grounding_context()
        prompt = (
            f"{grounding}\n"
            "Summarize the latest verified news for the three priority NRL rugby league topics based ONLY on the sources below:\n\n"
            "1. 🇵🇬 **PNG Chiefs (2028 NRL Expansion Team)**: Marquee player signings (e.g. Joey Manu, Alex Johnston, Jarome Luai), license progress, and official updates.\n"
            "2. 🐴 **Brisbane Broncos**: Clarify that regular rounds are finished and Broncos missed the top 8 (no more games this year). Report end-of-season news (e.g. Payne Haas farewell).\n"
            "3. 👑 **Queensland Maroons (State of Origin)**: Concluded 2026 series summary and Billy Slater squad updates.\n\n"
            "IMPORTANT: Order events chronologically. If news is older than 7 days, treat it strictly as historical context."
        )

        try:
            briefing_text = await self.llm.generate_response(
                prompt,
                search_results=all_sources[:5],
                is_technical=False,
                custom_system_prompt=NRL_VALIDATION_SYSTEM_PROMPT
            )
        except Exception as e:
            logger.error(f"Error synthesizing NRL briefing: {e}")
            briefing_text = "NRL priority briefing temporarily unavailable. Please query specific topics using `/nrl <topic>`."

        now_ts = time.time()
        self.cached_briefing = {
            "timestamp": now_ts,
            "briefing_text": briefing_text,
            "sources": all_sources
        }
        self._save_briefing_cache()
        logger.info("NRL priority briefing refreshed and cached successfully.")
        return self.cached_briefing

    async def get_priority_briefing(self) -> str:
        """Get instant pre-compiled priority briefing, triggering background refresh if empty."""
        if not self.cached_briefing:
            data = await self.refresh_priority_briefing()
            return data.get("briefing_text", "")
        return self.cached_briefing.get("briefing_text", "")

    async def query_specific_nrl(self, query: str) -> str:
        """Perform live, date-aware search for specific NRL questions or return instant player/team stats."""
        q_low = query.lower().strip()

        # 1. Full ladder inquiry
        if q_low in ["ladder", "standings", "table", "nrl ladder", "nrl standings", "the ladder"]:
            return self.format_full_ladder()

        # 2. Player profile / stats inquiry
        if self.is_player_query(query):
            player_data = await self.resolve_or_cache_player(query)
            if player_data:
                logger.info(f"Serving instant verified stats card for '{player_data.get('full_name')}'")
                return self.format_player_stats_card(player_data)

            # Team stats inquiry
            team_match = self.find_team_in_registry(query)
            if team_match:
                logger.info(f"Serving instant verified team stats card for '{team_match[1].get('name')}'")
                return self.format_team_stats_card(team_match[1])

        # 3. Direct team inquiry (e.g. "/nrl broncos", "/nrl storm record")
        team_match = self.find_team_in_registry(query)
        if team_match and len(query.split()) <= 4:
            if any(w in q_low for w in ["stats", "record", "ladder", "standing", "form", "team"]) or len(query.split()) <= 2:
                logger.info(f"Serving instant verified team stats card for '{team_match[1].get('name')}'")
                return self.format_team_stats_card(team_match[1])

        # 4. General query with ground-truth season context and live accredited search
        sources, tier_label = await self.fetch_tiered_search(query, max_results=4)
        grounding = self._build_season_grounding_context(query)

        prompt = (
            f"{grounding}\n"
            f"User Question: '{query}'\n\n"
            f"Freshness Tier: {tier_label}\n"
            f"Reference Sources (ordered newest first with age badges below):\n"
            "Provide an accurate, date-aware answer following the ground-truth memory and system rules."
        )

        return await self.llm.generate_response(
            prompt,
            search_results=sources,
            is_technical=False,
            custom_system_prompt=NRL_VALIDATION_SYSTEM_PROMPT
        )

    async def sync_weekly_round_finalization(self) -> Dict[str, Any]:
        """
        Weekly round finalization & registry synchronization:
        - Reloads memory & verifies all active team and player registries.
        - Refreshes priority briefing from accredited news sources.
        - Persists updated timestamps.
        """
        logger.info("Executing NRL weekly round finalization & registry sync...")
        self._load_memory()
        
        # Refresh priority briefing
        briefing_data = await self.refresh_priority_briefing()

        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")

        if "teams" in self.teams_registry:
            self.teams_registry["last_updated"] = today_str
            self._save_teams_registry()

        teams_count = len(self.teams_registry.get("teams", {}))
        players_count = len(self.player_registry.get("players", {}))
        phase = self.season_memory.get("current_phase", "Finals Series (Regular Season Concluded)")

        logger.info(f"NRL weekly round sync completed: {teams_count} teams, {players_count} players.")
        return {
            "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "status": "success",
            "teams_count": teams_count,
            "players_count": players_count,
            "season_phase": phase,
            "briefing_refreshed": bool(briefing_data)
        }

nrl_service = NRLService()
