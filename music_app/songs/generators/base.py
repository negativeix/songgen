from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GenerationRequest:
    prompt: str
    title: str = ""
    genre: Optional[str] = None
    mood: Optional[str] = None
    vocal_style: Optional[str] = None
    lyrics: Optional[str] = None
    instrumental: bool = False


@dataclass
class GenerationResult:
    task_id: str
    status: str  # PENDING | TEXT_SUCCESS | FIRST_SUCCESS | SUCCESS | FAILED
    audio_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None


class SongGeneratorStrategy(ABC):

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Submit a generation request and return the initial result."""

    @abstractmethod
    def get_status(self, task_id: str) -> GenerationResult:
        """Poll for the current status of a previously submitted generation task."""
