"""
Jeeves Services Package
Core AI inference, network diagnostic tools, technical RAG, persona, and flight services.
"""

from .llm_engine import LLMEngine
from .technical_service import TechnicalService, technical_service
from .hardware_service import HardwareService, hardware_service
from .software_service import SoftwareService, software_service
from .wiki_service import search_wikipedia
from .search_service import search_web, search_hardware_lifecycle
from .persona_service import PersonaService, persona_service
from .flight_service import FlightService, flight_service
from .profile_service import ProfileService, profile_service
from .movie_service import MovieService, movie_service
from .kpi_service import KPIService, kpi_service

__all__ = [
    "LLMEngine",
    "TechnicalService",
    "technical_service",
    "HardwareService",
    "hardware_service",
    "SoftwareService",
    "software_service",
    "search_wikipedia",
    "search_web",
    "search_hardware_lifecycle",
    "PersonaService",
    "persona_service",
    "FlightService",
    "flight_service",
    "ProfileService",
    "profile_service",
    "MovieService",
    "movie_service",
    "KPIService",
    "kpi_service",
]


