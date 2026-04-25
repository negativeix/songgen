import json
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .generators.base import GenerationRequest, GenerationResult
from .generators.factory import get_generator
from .generators.mock_strategy import MockSongGeneratorStrategy, MOCK_AUDIO_URL
from .generators.suno_strategy import SunoSongGeneratorStrategy
from .models import Library, Song, User, SiteConfig, AuditLog
from .models.enums import SongStatus, SongVisibility

AuthUser = get_user_model()


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


# ─────────────────────────────────────────────────────────────────────────────
# Admin decorator + RBAC Tests
# ─────────────────────────────────────────────────────────────────────────────

class AdminRequiredTests(TestCase):
    """Verify that @admin_required enforces the RBAC boundary."""

    def _make_auth_user(self, email, is_admin=False):
        auth = AuthUser.objects.create_user(username=email, email=email, password="pw")
        songs_user = User.objects.create(username=email, email=email, status="ACTIVE", is_admin=is_admin)
        Library.objects.create(user=songs_user)
        return auth, songs_user

    def test_admin_required_returns_403_for_non_admin(self):
        auth, _ = self._make_auth_user("nonadmin@example.com", is_admin=False)
        self.client.force_login(auth)
        response = self.client.get("/songs/admin/metrics/")
        self.assertEqual(response.status_code, 403)
        body = json.loads(response.content)
        self.assertIn("error", body)

    def test_admin_required_allows_admin(self):
        auth, _ = self._make_auth_user("admin@example.com", is_admin=True)
        self.client.force_login(auth)
        response = self.client.get("/songs/admin/metrics/")
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertIn("active_strategy", body)

    def test_admin_required_returns_403_for_anonymous(self):
        response = self.client.get("/songs/admin/metrics/")
        self.assertEqual(response.status_code, 403)


# ─────────────────────────────────────────────────────────────────────────────
# song_download access-control Tests
# ─────────────────────────────────────────────────────────────────────────────

class SongDownloadTests(TestCase):
    """Verify download endpoint enforces ownership/visibility rules."""

    def setUp(self):
        self.client = Client()
        # Owner
        self.owner_auth = AuthUser.objects.create_user(
            username="owner@example.com", email="owner@example.com", password="pw"
        )
        self.owner = User.objects.create(username="owner", email="owner@example.com", status="ACTIVE")
        self.library = Library.objects.create(user=self.owner)
        # Other user
        self.other_auth = AuthUser.objects.create_user(
            username="other@example.com", email="other@example.com", password="pw"
        )
        self.other = User.objects.create(username="other", email="other@example.com", status="ACTIVE")
        Library.objects.create(user=self.other)

        self.song = Song.objects.create(
            title="Private Song",
            library=self.library,
            status=SongStatus.SUCCESS,
            audio_url="https://cdn.example.com/song.mp3",
            visibility=SongVisibility.PRIVATE,
        )

    def test_download_private_song_as_non_owner_returns_403(self):
        self.client.force_login(self.other_auth)
        response = self.client.get(f"/songs/{self.song.songId}/download/")
        self.assertEqual(response.status_code, 403)

    def test_download_private_song_as_owner_succeeds(self):
        self.client.force_login(self.owner_auth)
        response = self.client.get(f"/songs/{self.song.songId}/download/")
        # Should redirect (302) to the audio URL
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.song.audio_url)

    def test_download_public_song_without_login_succeeds(self):
        self.song.visibility = SongVisibility.PUBLIC
        self.song.save()
        response = self.client.get(f"/songs/{self.song.songId}/download/")
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────────────────────────────────────
# Token management Tests
# ─────────────────────────────────────────────────────────────────────────────

class AdminTokenTests(TestCase):
    """Verify token rotate/revoke admin endpoints."""

    def setUp(self):
        self.client = Client()
        self.admin_auth = AuthUser.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="pw"
        )
        admin_songs = User.objects.create(
            username="admin", email="admin@example.com", status="ACTIVE", is_admin=True
        )
        lib = Library.objects.create(user=admin_songs)
        self.song = Song.objects.create(
            title="Shared Song",
            library=lib,
            status=SongStatus.SUCCESS,
            audio_url="https://cdn.example.com/song.mp3",
            visibility=SongVisibility.PUBLIC,
            public_token=uuid.uuid4(),
        )
        self.original_token = self.song.public_token

    def test_token_regenerate_changes_uuid(self):
        self.client.force_login(self.admin_auth)
        response = self.client.post(f"/songs/admin/tokens/{self.song.songId}/regenerate/")
        self.assertEqual(response.status_code, 200)
        self.song.refresh_from_db()
        self.assertNotEqual(self.song.public_token, self.original_token)

    def test_token_revoke_makes_song_private(self):
        self.client.force_login(self.admin_auth)
        response = self.client.post(f"/songs/admin/tokens/{self.song.songId}/revoke/")
        self.assertEqual(response.status_code, 200)
        self.song.refresh_from_db()
        self.assertEqual(self.song.visibility, SongVisibility.PRIVATE)
        self.assertIsNone(self.song.public_token)


# ─────────────────────────────────────────────────────────────────────────────
# NFR-17: Per-user daily quota enforcement
# ─────────────────────────────────────────────────────────────────────────────

class QuotaEnforcementTests(TestCase):
    """Verify that song_generate enforces the per-user daily limit (NFR-17)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username="quotauser", email="quota@example.com", status="ACTIVE")
        self.library = Library.objects.create(user=self.user)
        self.user_id = str(self.user.userId)
        # Set a tight quota for testing
        SiteConfig.objects.update_or_create(key='max_songs_per_day', defaults={'value': '2'})

    def _generate(self, mock_gen):
        """Helper: POST to /songs/generate/ with a mocked generator."""
        return self.client.post(
            "/songs/generate/",
            data=json.dumps({"user_id": self.user_id, "prompt": "test prompt"}),
            content_type="application/json",
        )

    @patch("songs.views.get_generator")
    def test_generation_allowed_within_quota(self, mock_get_gen):
        mock_get_gen.return_value.generate.return_value = GenerationResult(
            task_id="t1", status="SUCCESS", audio_url=MOCK_AUDIO_URL, title="Song", duration=180
        )
        response = self._generate(mock_get_gen)
        self.assertEqual(response.status_code, 200)

    @patch("songs.views.get_generator")
    def test_generation_blocked_when_quota_exceeded(self, mock_get_gen):
        mock_get_gen.return_value.generate.return_value = GenerationResult(
            task_id="t1", status="SUCCESS", audio_url=MOCK_AUDIO_URL, title="Song", duration=180
        )
        # Fill quota (limit = 2)
        self._generate(mock_get_gen)
        self._generate(mock_get_gen)
        # Third attempt must be rejected
        response = self._generate(mock_get_gen)
        self.assertEqual(response.status_code, 429)
        body = json.loads(response.content)
        self.assertIn("Daily generation limit", body["error"])
        self.assertEqual(body["quota_limit"], 2)

    @patch("songs.views.get_generator")
    def test_quota_zero_means_unlimited(self, mock_get_gen):
        SiteConfig.objects.update_or_create(key='max_songs_per_day', defaults={'value': '0'})
        mock_get_gen.return_value.generate.return_value = GenerationResult(
            task_id="t1", status="SUCCESS", audio_url=MOCK_AUDIO_URL, title="Song", duration=180
        )
        # Should not be blocked even after many requests
        for _ in range(5):
            r = self._generate(mock_get_gen)
            self.assertNotEqual(r.status_code, 429)

    @patch("songs.views.get_generator")
    def test_quota_exceeded_writes_audit_log(self, mock_get_gen):
        mock_get_gen.return_value.generate.return_value = GenerationResult(
            task_id="t1", status="SUCCESS", audio_url=MOCK_AUDIO_URL, title="Song", duration=180
        )
        self._generate(mock_get_gen)
        self._generate(mock_get_gen)
        self._generate(mock_get_gen)  # triggers quota_exceeded
        exceeded = AuditLog.objects.filter(action='quota_exceeded', user_email='quota@example.com')
        self.assertTrue(exceeded.exists())


# ─────────────────────────────────────────────────────────────────────────────
# NFR-19: AuditLog writes on generation
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogTests(TestCase):
    """Verify AuditLog is written on song generation (NFR-19)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username="audituser", email="audit@example.com", status="ACTIVE")
        self.library = Library.objects.create(user=self.user)
        self.user_id = str(self.user.userId)

    @patch("songs.views.get_generator")
    def test_successful_generation_writes_audit_log(self, mock_get_gen):
        mock_get_gen.return_value.generate.return_value = GenerationResult(
            task_id="task-audit-1", status="SUCCESS", audio_url=MOCK_AUDIO_URL, title="Audit Song", duration=180
        )
        self.client.post(
            "/songs/generate/",
            data=json.dumps({"user_id": self.user_id, "prompt": "audit test"}),
            content_type="application/json",
        )
        logs = AuditLog.objects.filter(user_email="audit@example.com")
        actions = list(logs.values_list('action', flat=True))
        self.assertIn('generate_started', actions)
        self.assertIn('generate_success', actions)

    @patch("songs.views.get_generator")
    def test_failed_generation_writes_audit_log(self, mock_get_gen):
        mock_get_gen.return_value.generate.side_effect = RuntimeError("API down")
        self.client.post(
            "/songs/generate/",
            data=json.dumps({"user_id": self.user_id, "prompt": "fail test"}),
            content_type="application/json",
        )
        failed = AuditLog.objects.filter(user_email="audit@example.com", action='generate_failed')
        self.assertTrue(failed.exists())
        self.assertIn("API down", failed.first().detail)


# ─────────────────────────────────────────────────────────────────────────────
# NFR-20: Runtime config update
# ─────────────────────────────────────────────────────────────────────────────

class RuntimeConfigTests(TestCase):
    """Verify admin can update SiteConfig values at runtime (NFR-20)."""

    def setUp(self):
        self.client = Client()
        self.admin_auth = AuthUser.objects.create_user(
            username="cfgadmin@example.com", email="cfgadmin@example.com", password="pw"
        )
        User.objects.create(username="cfgadmin", email="cfgadmin@example.com", status="ACTIVE", is_admin=True)
        SiteConfig.objects.update_or_create(key='max_songs_per_day', defaults={'value': '10'})

    def test_admin_can_update_quota_config(self):
        self.client.force_login(self.admin_auth)
        response = self.client.post(
            "/songs/admin/config/",
            data=json.dumps({"key": "max_songs_per_day", "value": "25"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["value"], "25")
        self.assertEqual(SiteConfig.get_int('max_songs_per_day'), 25)

    def test_non_admin_cannot_update_config(self):
        non_admin_auth = AuthUser.objects.create_user(
            username="plain@example.com", email="plain@example.com", password="pw"
        )
        User.objects.create(username="plain", email="plain@example.com", status="ACTIVE", is_admin=False)
        self.client.force_login(non_admin_auth)
        response = self.client.post(
            "/songs/admin/config/",
            data=json.dumps({"key": "max_songs_per_day", "value": "0"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        # Config must be unchanged
        self.assertEqual(SiteConfig.get_int('max_songs_per_day'), 10)

    def test_unknown_config_key_rejected(self):
        self.client.force_login(self.admin_auth)
        response = self.client.post(
            "/songs/admin/config/",
            data=json.dumps({"key": "secret_backdoor", "value": "evil"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = json.loads(response.content)
        self.assertIn("Unknown config key", body["error"])
