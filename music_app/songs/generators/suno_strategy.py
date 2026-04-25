import requests
from django.conf import settings

from .base import SongGeneratorStrategy, GenerationRequest, GenerationResult

SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_STATUS_URL   = "https://api.sunoapi.org/api/v1/generate/record-info"
SUNO_MODEL        = "V4"

_STATUS_MAP = {
    "PENDING":       "PENDING",
    "TEXT_SUCCESS":  "TEXT_SUCCESS",
    "FIRST_SUCCESS": "FIRST_SUCCESS",
    "SUCCESS":       "SUCCESS",
    "FAILED":        "FAILED",
    "RUNNING":       "PENDING",
    "QUEUED":        "PENDING",
    "PROCESSING":    "PENDING",
    "SUBMITTED":     "PENDING",
    "COMPLETE":      "SUCCESS",
    "COMPLETED":     "SUCCESS",
    "DONE":          "SUCCESS",
    "ERROR":         "FAILED",
    "CANCELLED":     "FAILED",
}


def _normalize_status(raw) -> str:
    return _STATUS_MAP.get(str(raw).upper(), "PENDING")


class SunoSongGeneratorStrategy(SongGeneratorStrategy):

    def __init__(self):
        self.api_key = getattr(settings, "SUNO_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(self, request: GenerationRequest) -> GenerationResult:
        tags = " ".join(filter(None, [request.genre, request.mood, request.vocal_style]))
        custom_mode = bool(request.lyrics)
        prompt_text = request.lyrics if custom_mode else request.prompt

        # callBackUrl is required by sunoapi.org; we use a placeholder and poll manually.
        callback_url = getattr(settings, "SUNO_CALLBACK_URL", "http://localhost/callback")

        payload = {
            "title":       request.title or "",
            "tags":        tags,
            "prompt":      prompt_text,
            "model":       SUNO_MODEL,
            "customMode":  custom_mode,
            "instrumental": request.instrumental,
            "callBackUrl": callback_url,
        }
        if request.duration:
            payload["duration"] = request.duration

        try:
            resp = requests.post(SUNO_GENERATE_URL, json=payload,
                                 headers=self.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Guard: data must be a dict
            if not isinstance(data, dict):
                return GenerationResult(task_id="", status="FAILED",
                                        error=f"Unexpected response: {data!r}")

            # Check application-level code (API returns HTTP 200 even for errors)
            if data.get("code", 200) != 200:
                return GenerationResult(task_id="", status="FAILED",
                                        error=data.get("msg", f"API error: {data}"))

            inner = data.get("data")
            if not isinstance(inner, dict):
                return GenerationResult(task_id="", status="FAILED",
                                        error=f"No task data in response: {data}")

            task_id = inner.get("taskId") or inner.get("task_id") or ""
            if not task_id:
                return GenerationResult(task_id="", status="FAILED",
                                        error=f"No taskId in response: {data}")

            return GenerationResult(task_id=task_id, status="PENDING")

        except requests.exceptions.RequestException as exc:
            return GenerationResult(task_id="", status="FAILED", error=str(exc))

    def get_status(self, task_id: str) -> GenerationResult:
        try:
            resp = requests.get(SUNO_STATUS_URL, params={"taskId": task_id},
                                headers=self.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                return GenerationResult(task_id=task_id, status="FAILED",
                                        error=f"Unexpected response: {data!r}")

            inner = data.get("data")
            if not isinstance(inner, dict):
                return GenerationResult(task_id=task_id, status="PENDING")

            raw_status = inner.get("status") or "PENDING"
            status = _normalize_status(raw_status)

            audio_url = None
            duration  = None
            title     = None

            if status in ("SUCCESS", "FIRST_SUCCESS"):
                response_block = inner.get("response") or {}
                clips = response_block.get("sunoData") or []
                if clips and isinstance(clips[0], dict):
                    clip = clips[0]
                    audio_url = (clip.get("audio_url")
                                 or clip.get("audioUrl")
                                 or clip.get("audio"))
                    raw_dur = clip.get("duration")
                    duration = int(float(raw_dur)) if raw_dur else None
                    title    = clip.get("title") or clip.get("name")

            return GenerationResult(
                task_id=task_id,
                status=status,
                audio_url=audio_url,
                title=title,
                duration=duration,
            )

        except requests.exceptions.RequestException as exc:
            return GenerationResult(task_id=task_id, status="FAILED", error=str(exc))
