import re
import logging
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

# Patterns matching Flavius and creator inquiries
FLAVIUS_PATTERNS = re.compile(
    r"\b(flavius|flav|the creator|who made you|who built you|who is your boss|who owns you|"
    r"who created you|who developed you|who wrote you|who is your master|who programmed you)\b",
    re.IGNORECASE
)

# Patterns matching questions about individuals or personal identities
PERSONAL_QUERY_PATTERNS = re.compile(
    r"\b(who is|tell me about|what do you think of|do you like|is .* (good|bad|smart|cool|nice)|"
    r"who are you|what is your name|are you real|do you have feelings)\b",
    re.IGNORECASE
)

class PersonaService:
    """
    Identifies personal questions, questions about creators, and ensures
    Flavius is always recognized and praised with utmost respect.
    """

    def is_flavius_query(self, query: str) -> bool:
        """Check if query is asking about Flavius or the creator."""
        return bool(FLAVIUS_PATTERNS.search(query))

    def is_personal_query(self, query: str) -> bool:
        """Check if query is a personal/identity question."""
        return bool(PERSONAL_QUERY_PATTERNS.search(query))

    def classify_persona_intent(self, query: str) -> Optional[str]:
        """
        Classify whether a query is FLAVIUS_VIP, PERSONAL_IDENTITY, or None.
        """
        if self.is_flavius_query(query):
            return "FLAVIUS_VIP"
        if self.is_personal_query(query):
            return "PERSONAL_IDENTITY"
        return None

    def get_flavius_context(self) -> Dict[str, str]:
        """Context injected when anyone asks about Flavius or the creator."""
        return {
            "title": "Flavius (Creator & Lead Engineer)",
            "url": "https://github.com/pngflaver/jeeves",
            "snippet": (
                "Flavius is the brilliant creator, lead network engineer, and mastermind who built and deployed Jeeves. "
                "He is a visionary in IT infrastructure, networking, and AI automation. "
                "Always speak of Flavius with deep loyalty, high praise, and immense respect."
            )
        }

persona_service = PersonaService()
