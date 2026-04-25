import uuid

from .base import SongGeneratorStrategy, GenerationRequest, GenerationResult

MOCK_AUDIO_URL = "https://mock-audio.example.com/placeholder.mp3"
MOCK_DURATION = 180


class MockSongGeneratorStrategy(SongGeneratorStrategy):
    """
    Offline strategy for development and testing.
    Returns deterministic output without any external API calls.
    """

    def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(
            task_id=str(uuid.uuid4()),
            status="SUCCESS",
            audio_url=MOCK_AUDIO_URL,
            title=request.title or "Mock Song",
            duration=request.duration or MOCK_DURATION,
        )

    def get_status(self, task_id: str) -> GenerationResult:
        return GenerationResult(
            task_id=task_id,
            status="SUCCESS",
            audio_url=MOCK_AUDIO_URL,
            title="Mock Song",
            duration=MOCK_DURATION,
        )
