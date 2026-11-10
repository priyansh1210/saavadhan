"""Thin clients for Gnani Prisma (speech-to-text) and Timbre (text-to-speech)."""
import asyncio
import json

import httpx
import websockets

from . import config

# Words the scam detector cares about. Prisma v3.0 favours them while transcribing.
KEYTERMS = [
    "OTP", "UPI", "UPI PIN", "CVV", "KYC", "Aadhaar", "PAN card", "CBI", "ED", "RBI", "TRAI",
    "digital arrest", "arrest warrant", "money laundering", "FIR", "customs", "FedEx", "parcel",
    "AnyDesk", "TeamViewer", "screen share", "Paytm", "PhonePe", "Google Pay", "SBI", "HDFC", "ICICI",
    "cyber crime", "narcotics", "police", "1930",
]
TOPIC = (
    "A phone call heard on speakerphone in India. It may be a fraud call: fake police, CBI or bank "
    "officers, digital arrest, KYC update, OTP or UPI PIN requests, parcel or customs threats."
)


def _require_key() -> str:
    if not config.GNANI_API_KEY:
        raise RuntimeError("GNANI_API_KEY is not set. Add it to the .env file.")
    return config.GNANI_API_KEY


def stt_stream_headers(langs: str | None = None, sample_rate: int = 16000) -> dict:
    # Streaming accepts one locale or indic-auto (a comma list is rejected with 1008), so a
    # "hi-IN,en-IN" choice streams as hi-IN; codemix still keeps the English words in Latin script.
    language = (langs or config.STT_LANGS).split(",")[0].strip()
    return {
        "x-api-key-id": _require_key(),
        "model": config.STT_MODEL,
        "language_code": language,
        "format": config.STT_FORMAT,
        "x-sample-rate": str(sample_rate),
        "x-partials": "true",  # words while the caller is still talking (found by probing; not in the docs)
        "keyterms": json.dumps(KEYTERMS),
        "topic": TOPIC,
        # A phone on speaker: a bit stricter than a clean mic, and force a transcript on long monologues.
        "x-vad-threshold": "0.6",
        "x-min-speech-ms": "150",
        "x-min-silence-ms": "550",
        "x-max-speech-s": "12",
        "x-idle-timeout-sec": "300",
    }


async def open_stt_stream(langs: str | None = None):
    return await websockets.connect(
        config.GNANI_STT_WS,
        additional_headers=stt_stream_headers(langs),
        max_size=None,
        open_timeout=15,
        ping_interval=20,
    )


async def stt_rest(client: httpx.AsyncClient, wav: bytes, langs: str | None = None,
                   previous_text: str = "") -> dict:
    data = {
        "model": config.STT_MODEL,
        "language_code": langs or config.STT_LANGS,
        "format": config.STT_FORMAT,
        "keyterms": json.dumps(KEYTERMS),
        "topic": TOPIC,
    }
    if previous_text:
        data["previous_text"] = previous_text[-600:]
    for attempt in range(6):
        r = await client.post(
            config.GNANI_STT_REST,
            headers={"X-API-Key-ID": _require_key()},
            files={"audio_file": ("chunk.wav", wav, "audio/wav")},
            data=data,
            timeout=60,
        )
        if r.status_code != 429:
            break
        await asyncio.sleep(0.8 * (attempt + 1))  # the account allows one request at a time
    if r.status_code >= 400:
        raise RuntimeError(f"Prisma STT error {r.status_code}: {r.text[:300]}")
    return r.json()


async def tts(client: httpx.AsyncClient, text: str, language: str = "hi-IN",
              voice: str | None = None, sample_rate: int = 24000, speed: float = 0.95) -> bytes:
    body = {
        "text": text,
        "voice": voice or config.TTS_VOICE,
        "model": config.TTS_MODEL,
        "language": language,
        "speed": speed,
        "audio_config": {
            "sample_rate": sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    r = await client.post(
        config.GNANI_TTS_REST,
        headers={"X-API-Key-ID": _require_key(), "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Timbre TTS error {r.status_code}: {r.text[:300]}")
    return r.content
