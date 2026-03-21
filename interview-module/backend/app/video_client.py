"""Talking-head video generation — provider abstraction.

Supported providers: "did" | "heygen" | "mock"
Controlled via VIDEO_PROVIDER env var OR the video_provider settings key in the DB.
"""

import os, uuid, time, base64, logging
from enum import Enum
from typing import Optional
import httpx

from .database import VIDEO_DIR

log = logging.getLogger(__name__)

# ── Provider enum ──────────────────────────────────────────────────────────────

class VideoProviderType(str, Enum):
    DID    = "did"
    HEYGEN = "heygen"
    MOCK   = "mock"

# ── D-ID ───────────────────────────────────────────────────────────────────────

DID_API_BASE = "https://api.d-id.com"
DID_DEFAULT_PRESENTER = (
    "https://clips-presenters.d-id.com/v2/Amber/0zSz8kflCN/OUM7xZOuD5/image.png"
)

# ── HeyGen ────────────────────────────────────────────────────────────────────

HEYGEN_API_BASE = "https://api.heygen.com"
# Default avatar — Kayla (professional, half-body, natural gestures)
# Get avatar_id list via GET /v2/avatars
HEYGEN_DEFAULT_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "Kayla-incasualsuit-20220818")
HEYGEN_DEFAULT_VOICE_ID  = os.getenv("HEYGEN_VOICE_ID",  "1bd001e7e50f421d891986aad5158bc8")  # Kayla default

POLL_INTERVAL = 3    # seconds
POLL_TIMEOUT  = 120  # seconds


# ── Base class ─────────────────────────────────────────────────────────────────

class VideoProvider:
    """Base class — subclass and override generate_talking_head."""

    def generate_talking_head(self, audio_path: str, text: str) -> Optional[str]:
        """Generate a talking-head video. Returns local .mp4 path or None."""
        raise NotImplementedError


# ── D-ID provider ──────────────────────────────────────────────────────────────

class DIDProvider(VideoProvider):
    """D-ID Talks API — text-driven TTS + lip-sync."""

    def __init__(self, api_key: str):
        # D-ID API keys are already base64-encoded; pass directly as Basic auth value
        self._auth = "Basic " + api_key
        self._presenter = os.getenv("DID_PRESENTER_URL", DID_DEFAULT_PRESENTER)

    def generate_talking_head(self, audio_path: str, text: str) -> Optional[str]:
        if not text or not text.strip():
            return None
        try:
            return self._create_and_download(text)
        except Exception as e:
            log.warning("[D-ID] Video generation failed: %s", e)
            return None

    def _create_and_download(self, text: str) -> Optional[str]:
        headers = {"Authorization": self._auth, "Content-Type": "application/json"}

        resp = httpx.post(
            f"{DID_API_BASE}/talks",
            headers=headers,
            json={
                "source_url": self._presenter,
                "script": {
                    "type": "text",
                    "input": text.strip(),
                    "provider": {"type": "microsoft", "voice_id": "en-US-JennyNeural"},
                },
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        talk_id = resp.json()["id"]

        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            poll = httpx.get(f"{DID_API_BASE}/talks/{talk_id}", headers=headers, timeout=10.0)
            poll.raise_for_status()
            data = poll.json()
            status = data.get("status")
            if status == "done":
                result_url = data.get("result_url")
                if not result_url:
                    log.warning("[D-ID] Talk %s done but no result_url", talk_id)
                    return None
                return self._download(result_url)
            if status in ("error", "rejected"):
                log.warning("[D-ID] Talk %s ended with status=%s", talk_id, status)
                return None

        log.warning("[D-ID] Talk %s timed out after %ds", talk_id, POLL_TIMEOUT)
        return None

    def _download(self, url: str) -> Optional[str]:
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        os.makedirs(VIDEO_DIR, exist_ok=True)
        out_path = os.path.join(VIDEO_DIR, f"{uuid.uuid4()}.mp4")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path


# ── HeyGen provider ────────────────────────────────────────────────────────────

class HeyGenProvider(VideoProvider):
    """HeyGen v2 Video API — higher quality avatars with natural gestures."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._avatar_id = HEYGEN_DEFAULT_AVATAR_ID
        self._voice_id  = HEYGEN_DEFAULT_VOICE_ID

    def generate_talking_head(self, audio_path: str, text: str) -> Optional[str]:
        if not text or not text.strip():
            return None
        try:
            return self._create_and_download(text)
        except Exception as e:
            log.warning("[HeyGen] Video generation failed: %s", e)
            return None

    def _headers(self):
        return {"X-Api-Key": self._api_key, "Content-Type": "application/json"}

    def _create_and_download(self, text: str) -> Optional[str]:
        # 1. Submit video generation
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": self._avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": text.strip(),
                    "voice_id": self._voice_id,
                },
            }],
            "dimension": {"width": 1280, "height": 720},
            "aspect_ratio": "16:9",
        }

        resp = httpx.post(
            f"{HEYGEN_API_BASE}/v2/video/generate",
            headers=self._headers(),
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        video_id = data.get("data", {}).get("video_id") or data.get("video_id")
        if not video_id:
            log.warning("[HeyGen] No video_id in response: %s", data)
            return None

        log.info("[HeyGen] Submitted video_id=%s", video_id)

        # 2. Poll for completion
        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            status_resp = httpx.get(
                f"{HEYGEN_API_BASE}/v1/video_status.get",
                headers=self._headers(),
                params={"video_id": video_id},
                timeout=10.0,
            )
            status_resp.raise_for_status()
            status_data = status_resp.json().get("data", {})
            status = status_data.get("status")
            log.info("[HeyGen] video_id=%s status=%s", video_id, status)

            if status == "completed":
                video_url = status_data.get("video_url")
                if not video_url:
                    log.warning("[HeyGen] video_id=%s completed but no video_url", video_id)
                    return None
                return self._download(video_url)
            if status in ("failed", "error"):
                log.warning("[HeyGen] video_id=%s failed: %s", video_id, status_data.get("error"))
                return None

        log.warning("[HeyGen] video_id=%s timed out after %ds", video_id, POLL_TIMEOUT)
        return None

    def _download(self, url: str) -> Optional[str]:
        resp = httpx.get(url, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        os.makedirs(VIDEO_DIR, exist_ok=True)
        out_path = os.path.join(VIDEO_DIR, f"{uuid.uuid4()}.mp4")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path


# ── Mock provider ──────────────────────────────────────────────────────────────

class MockProvider(VideoProvider):
    """No-op provider. Used when VIDEO_PROVIDER=mock or no API key configured."""

    def generate_talking_head(self, audio_path: str, text: str) -> Optional[str]:
        return None


# ── Factory ────────────────────────────────────────────────────────────────────

def get_provider(provider_override: Optional[str] = None) -> VideoProvider:
    """Return the configured VideoProvider.

    Resolution order:
    1. provider_override (passed explicitly, e.g. from DB settings)
    2. VIDEO_PROVIDER env var
    3. Default: "did"
    """
    provider = (provider_override or os.getenv("VIDEO_PROVIDER", "did")).lower().strip()

    if provider == VideoProviderType.HEYGEN:
        key = os.getenv("HEYGEN_API_KEY", "")
        if not key:
            log.warning("[VideoClient] HeyGen selected but HEYGEN_API_KEY not set — falling back to mock")
            return MockProvider()
        return HeyGenProvider(api_key=key)

    if provider == VideoProviderType.DID:
        key = os.getenv("DID_API_KEY", "")
        if not key:
            log.warning("[VideoClient] D-ID selected but DID_API_KEY not set — falling back to mock")
            return MockProvider()
        return DIDProvider(api_key=key)

    return MockProvider()
