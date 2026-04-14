"""
Wispr Flow Speech-to-Text client for TalentBridge Interview Module.

Wispr Flow provides higher-quality transcription than standard STT:
  - Auto-edits (removes filler words, corrects self-corrections)
  - Context-aware transcription
  - 100+ languages

Setup:
  1. Get API access: email enterprise@wisprflow.ai
  2. Create API key at https://platform.wisprflow.ai
  3. Set WISPR_API_KEY in your .env

Falls back to OpenAI Whisper if Wispr Flow is not configured.
"""

import os
import json
import asyncio
import tempfile
import websockets
import base64
import struct

WISPR_API_KEY = os.getenv("WISPR_API_KEY", "")
WISPR_WS_URL = "wss://platform-api.wisprflow.ai/api/v1/dash/ws"
WISPR_REST_URL = "https://platform-api.wisprflow.ai/api/v1/transcribe"


def is_wispr_configured() -> bool:
    """Check if Wispr Flow API key is available."""
    return bool(WISPR_API_KEY and WISPR_API_KEY != "your-wispr-key-here")


async def transcribe_with_wispr_ws(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """
    Transcribe audio using Wispr Flow WebSocket API.
    
    Audio must be 16kHz PCM WAV. This function handles conversion from
    webm/mp4 if needed (via ffmpeg fallback).
    
    Returns transcribed text or empty string on failure.
    """
    if not is_wispr_configured():
        return ""
    
    try:
        # Convert audio to 16kHz PCM WAV if needed
        pcm_data = await _convert_to_pcm_wav(audio_bytes, content_type)
        if not pcm_data:
            return ""
        
        # Base64 encode the PCM data
        b64_audio = base64.b64encode(pcm_data).decode("utf-8")
        
        # Split into 1-second chunks (16000 samples * 2 bytes = 32000 bytes per second)
        chunk_size = 32000
        chunks = []
        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i:i + chunk_size]
            chunks.append(base64.b64encode(chunk).decode("utf-8"))
        
        if not chunks:
            return ""
        
        # Connect to Wispr WebSocket
        ws_url = f"{WISPR_WS_URL}?api_key=Bearer%20{WISPR_API_KEY}"
        
        async with websockets.connect(ws_url, close_timeout=10) as ws:
            # Send auth/start message
            await ws.send(json.dumps({
                "type": "auth",
                "access_token": WISPR_API_KEY,
                "language": ["en"],
                "context": {
                    "app": {
                        "name": "TalentBridge AI Interview",
                        "type": "other"
                    },
                    "dictionary_context": [
                        "technical interview", "coding", "algorithm",
                        "data structure", "API", "microservices"
                    ]
                }
            }))
            
            # Wait for auth confirmation
            auth_response = await asyncio.wait_for(ws.recv(), timeout=10)
            auth_data = json.loads(auth_response)
            if auth_data.get("status") != "auth":
                print(f"[WISPR] Auth failed: {auth_data}")
                return ""
            
            # Stream audio chunks
            packet_duration = 1.0  # 1 second per chunk
            for i, chunk in enumerate(chunks):
                await ws.send(json.dumps({
                    "type": "append",
                    "position": i,
                    "audio_packets": {
                        "packets": [chunk],
                        "volumes": [0.5],
                        "packet_duration": packet_duration,
                        "audio_encoding": "wav",
                        "byte_encoding": "base64"
                    }
                }))
            
            # Send commit
            await ws.send(json.dumps({
                "type": "commit",
                "total_packets": len(chunks)
            }))
            
            # Collect responses until final
            final_text = ""
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(response)
                    
                    if data.get("status") == "text":
                        text = data.get("body", {}).get("text", "")
                        if data.get("final"):
                            final_text = text
                            break
                        else:
                            final_text = text  # Keep latest partial
                    elif data.get("status") == "error":
                        print(f"[WISPR] Error: {data}")
                        break
                except asyncio.TimeoutError:
                    break
            
            return final_text.strip()
    
    except Exception as e:
        print(f"[WISPR] WebSocket transcription failed: {e}")
        return ""


def transcribe_with_wispr_rest(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """
    Transcribe audio using Wispr Flow REST API (synchronous fallback).
    
    Returns transcribed text or empty string on failure.
    """
    if not is_wispr_configured():
        return ""
    
    try:
        import httpx
        
        ext = "m4a" if ("mp4" in content_type or "m4a" in content_type) else "webm"
        
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        try:
            with open(tmp_path, "rb") as f:
                response = httpx.post(
                    WISPR_REST_URL,
                    headers={"Authorization": f"Bearer {WISPR_API_KEY}"},
                    files={"audio": (f"audio.{ext}", f, content_type)},
                    data={
                        "language": "en",
                        "context": json.dumps({
                            "app": {
                                "name": "TalentBridge AI Interview",
                                "type": "other"
                            }
                        })
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json().get("text", "").strip()
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    except Exception as e:
        print(f"[WISPR] REST transcription failed: {e}")
        return ""


async def _convert_to_pcm_wav(audio_bytes: bytes, content_type: str) -> bytes:
    """
    Convert audio to 16kHz mono PCM WAV format required by Wispr Flow.
    Uses ffmpeg if available, otherwise returns raw bytes and hopes for the best.
    """
    import shutil
    
    if not shutil.which("ffmpeg"):
        # If no ffmpeg, try returning raw bytes — Wispr may handle it
        print("[WISPR] ffmpeg not found, sending raw audio")
        return audio_bytes
    
    ext = "m4a" if ("mp4" in content_type or "m4a" in content_type) else "webm"
    
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as inp:
        inp.write(audio_bytes)
        inp_path = inp.name
    
    out_path = inp_path + ".wav"
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", inp_path,
            "-ar", "16000",     # 16kHz sample rate
            "-ac", "1",         # mono
            "-f", "s16le",      # 16-bit PCM
            "-acodec", "pcm_s16le",
            out_path,
            "-y", "-loglevel", "error",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        
        if proc.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                return f.read()
        else:
            return audio_bytes
    except Exception as e:
        print(f"[WISPR] ffmpeg conversion failed: {e}")
        return audio_bytes
    finally:
        for p in (inp_path, out_path):
            try:
                os.unlink(p)
            except:
                pass
