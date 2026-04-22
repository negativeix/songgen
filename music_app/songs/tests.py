import json
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase

from .generators.base import GenerationRequest, GenerationResult
from .generators.factory import get_generator
from .generators.mock_strategy import MockSongGeneratorStrategy, MOCK_AUDIO_URL
from .generators.suno_strategy import SunoSongGeneratorStrategy
from .models import Library, User


# ─────────────────────────────────────────────────────────────────────────────
# Mock Strategy Tests
# ─────────────────────────────────────────────────────────────────────────────

class MockStrategyTests(TestCase):
    def setUp(self):
        self.strategy = MockSongGeneratorStrategy()
        self.request = GenerationRequest(
            prompt="A happy pop song about summer",
            title="Summer Vibes",
            genre="POP",
            mood="happy",
        )

    def test_generate_returns_success_status(self):
        result = self.strategy.generate(self.request)
        self.assertEqual(result.status, "SUCCESS")
        self.assertIsNotNone(result.audio_url)
        self.assertIsNotNone(result.task_id)
        self.assertEqual(result.duration, 180)

    def test_generate_is_deterministic(self):
        """Same strategy always returns the same fixed audio URL."""
        result1 = self.strategy.generate(self.request)
        result2 = self.strategy.generate(self.request)
        self.assertEqual(result1.audio_url, result2.audio_url)
        self.assertEqual(result1.audio_url, MOCK_AUDIO_URL)

    def test_get_status_always_returns_success(self):
        result = self.strategy.get_status("any-task-id-123")
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.audio_url, MOCK_AUDIO_URL)


# ─────────────────────────────────────────────────────────────────────────────
# Suno Strategy Tests (external HTTP calls are mocked)
# ─────────────────────────────────────────────────────────────────────────────

class SunoStrategyTests(TestCase):

    def _make_strategy(self):
        from django.conf import settings
        settings.SUNO_API_KEY = "test-api-key"
        return SunoSongGeneratorStrategy()

    @patch("songs.generators.suno_strategy.requests.post")
    def test_generate_returns_pending_on_success(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "code": 200,
            "data": {"taskId": "suno-task-abc123"},
        }

        strategy = self._make_strategy()
        result = strategy.generate(GenerationRequest(
            prompt="A calm jazz track", title="Night Jazz", genre="JAZZ"
        ))

        self.assertEqual(result.status, "PENDING")
        self.assertEqual(result.task_id, "suno-task-abc123")
        self.assertIsNone(result.audio_url)

    @patch("songs.generators.suno_strategy.requests.post")
    def test_generate_returns_failed_on_connection_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("API unreachable")

        strategy = self._make_strategy()
        result = strategy.generate(GenerationRequest(prompt="test"))

        self.assertEqual(result.status, "FAILED")
        self.assertIn("API unreachable", result.error)
        self.assertEqual(result.task_id, "")

    @patch("songs.generators.suno_strategy.requests.get")
    def test_get_status_returns_success_with_audio_url(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "code": 200,
            "data": {
                "taskId": "suno-task-abc123",
                "status": "SUCCESS",
                "response": {
                    "sunoData": [{
                        "audio_url": "https://cdn.suno.ai/song.mp3",
                        "duration": 240,
                        "title": "Night Jazz",
                    }]
                },
            },
        }

        strategy = self._make_strategy()
        result = strategy.get_status("suno-task-abc123")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.audio_url, "https://cdn.suno.ai/song.mp3")
        self.assertEqual(result.duration, 240)
        self.assertEqual(result.title, "Night Jazz")


# ─────────────────────────────────────────────────────────────────────────────
# Factory Tests
# ─────────────────────────────────────────────────────────────────────────────

class FactoryTests(TestCase):

    def test_returns_mock_strategy_by_default(self):
        from django.conf import settings
        original = getattr(settings, "GENERATOR_STRATEGY", "mock")
        settings.GENERATOR_STRATEGY = "mock"
        try:
            strategy = get_generator()
            self.assertIsInstance(strategy, MockSongGeneratorStrategy)
        finally:
            settings.GENERATOR_STRATEGY = original

    def test_returns_suno_strategy_when_configured(self):
        from django.conf import settings
        original = getattr(settings, "GENERATOR_STRATEGY", "mock")
        settings.GENERATOR_STRATEGY = "suno"
        settings.SUNO_API_KEY = "test-key"
        try:
            strategy = get_generator()
            self.assertIsInstance(strategy, SunoSongGeneratorStrategy)
        finally:
            settings.GENERATOR_STRATEGY = original

    def test_unknown_value_falls_back_to_mock(self):
        from django.conf import settings
        original = getattr(settings, "GENERATOR_STRATEGY", "mock")
        settings.GENERATOR_STRATEGY = "unknown_strategy"
        try:
            strategy = get_generator()
            self.assertIsInstance(strategy, MockSongGeneratorStrategy)
        finally:
            settings.GENERATOR_STRATEGY = original


# ─────────────────────────────────────────────────────────────────────────────
# Generation API Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class GenerationAPITests(TestCase):

    def setUp(self):
        self.client = Client()
        user = User.objects.create(
            username="testuser",
            email="test@example.com",
            status="ACTIVE",
        )
        Library.objects.create(user=user)
        self.user_id = str(user.userId)

    @patch("songs.views.get_generator")
    def test_generate_endpoint_mock_strategy(self, mock_get_gen):
        mock_strategy = MagicMock()
        mock_strategy.generate.return_value = GenerationResult(
            task_id="mock-task-001",
            status="SUCCESS",
            audio_url=MOCK_AUDIO_URL,
            title="Summer Vibes",
            duration=180,
        )
        mock_get_gen.return_value = mock_strategy

        response = self.client.post(
            "/songs/generate/",
            data=json.dumps({
                "user_id": self.user_id,
                "prompt": "An upbeat pop song",
                "genre": "POP",
                "mood": "happy",
                "title": "Summer Vibes",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertIn("song_id", body)
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["audio_url"], MOCK_AUDIO_URL)

    def test_generate_endpoint_requires_prompt(self):
        response = self.client.post(
            "/songs/generate/",
            data=json.dumps({"user_id": self.user_id, "title": "No prompt here"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.content)
        self.assertIn("error", body)
