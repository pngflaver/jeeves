"""
Jeeves Services Package
Core AI inference, network diagnostic tools, and technical RAG services.
"""

from .llm_engine import LLMEngine
from .technical_service import TechnicalService, technical_service
from .hardware_service import HardwareService, hardware_service
from .software_service import SoftwareService, software_service
from .wiki_service import search_wikipedia
from .search_service import search_web, search_hardware_lifecycle

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
]
