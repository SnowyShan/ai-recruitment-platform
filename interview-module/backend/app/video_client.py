"""Talking-head video generation — provider abstraction.

Supports D-ID (default) and a silent MockProvider for local dev.
Swap provider via VIDEO_PROVIDER env var ("did" | "mock").
"""

import os, uuid, time, base64, logging
import httpx

from .database import VIDEO_DIR

log = logging.getLogger(__name__)

DID_API_BASE = "https://api.d-id.com"
DID_DEFAULT_PRESENTER = (
    "https://clips-presenters.d-id.com/v2/Amber/0zSz8kflCN/OUM7xZOuD5/image.png"
)
POLL_INTERVAL = 3       # seconds
POLL_TIMEOUT = 90       # seconds


class VideoProvider:
    """Base class — subclass and override generate_talking_head."""

    def generate_talking_head(self, audio_path: str, text: str) -> str | None:
        """Generate a talking-head video.

        Returns the local .mp4 file path on success, None on failure.
        """
        raise NotImplementedError


class DIDProvider(VideoProvider):
    """D-ID Talks API provider.

    Uses script.type="text" so D-ID handles TTS internally — avoids
    needing a publicly accessible audio URL.
    """

    def __init__(self, api_key: str):
        # D-ID uses Basic auth: base64("key:")
        # D-ID API keys are already base64-encoded; use directly as Basic auth value
        self._auth = "Basic " + api_key
        self._presenter = os.getenv("DID_PRESENTER_URL", DID_DEFAULT_PRESENTER)

    def generate_talking_head(self, audio_path: str, text: str) -> str | None:
        if not text or not text.strip():
            return None
        try:
            return self._create_and_download(text)
        except Exception as e:
            log.warning("[D-ID] Video generation failed: %s", e)
            return None

    def _create_and_download(self, text: str) -> str | None:
        headers = {
            "Authorization": self._auth,
            "Content-Type": "application/json",
        }

        # 1. Create talk
        resp = httpx.post(
            f"{DID_API_BASE}/talks",
            headers=headers,
            json={
                "source_url": self._presenter,
                "script": {
                    "type": "text",
                    "input": text.strip(),
                    "provider": {
                        "type": "microsoft",
                        "voice_id": "en-US-JennyNeural",
                    },
                },
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        talk_id = resp.json()["id"]

        # 2. Poll until done
        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            poll = httpx.get(
                f"{DID_API_BASE}/talks/{talk_id}",
                headers=headers,
                timeout=10.0,
            )
            poll.raise_for_status()
            data = poll.json()
            status = data.get("status")
            if status == "done":
                result_url = data.get("result_url")
                if not result_url:
                    log.warning("[D-ID] Talk %s done but no result_url", talk_id)
                    return None
                return self._download(result_url, talk_id)
            if status in ("error", "rejected"):
                log.warning("[D-ID] Talk %s ended with status=%s", talk_id, status)
                return None

        log.warning("[D-ID] Talk %s timed out after %ds", talk_id, POLL_TIMEOUT)
        return None

    def _download(self, url: str, talk_id: str) -> str | None:
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        os.makedirs(VIDEO_DIR, exist_ok=True)
        out_path = os.path.join(VIDEO_DIR, f"{uuid.uuid4()}.mp4")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path


class MockProvider(VideoProvider):
    """Returns None immediately. Used when VIDEO_PROVIDER=mock or DID_API_KEY not set."""

    def generate_talking_head(self, audio_path: str, text: str) -> str | None:
        return None


def get_provider() -> VideoProvider:
    """Factory — returns the configured VideoProvider."""
    provider = os.getenv("VIDEO_PROVIDER", "did").lower()
    if provider == "did":
        key = os.getenv("DID_API_KEY", "")
        if not key:
            return MockProvider()
        return DIDProvider(api_key=key)
    return MockProvider()
