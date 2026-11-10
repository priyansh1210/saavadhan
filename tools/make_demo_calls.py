"""Generate two test calls with Gnani Timbre: a 'digital arrest' scam call and a normal delivery call.

    py tools/make_demo_calls.py

Writes samples/scam_call.wav, samples/safe_call.wav and phone-quality *_phone.wav versions.
Play one near the laptop mic in Live mode, or upload it in "Check a recording".
These are scripted, synthetic calls for testing only.
"""
import asyncio
import io
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import gnani  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "samples"
RATE = 16000

SCAM = [
    ("Harshad", "हेलो, मैं मुंबई क्राइम ब्रांच से इंस्पेक्टर राजेश शर्मा बोल रहा हूँ। क्या मैं सुनीता वर्मा जी से बात कर रहा हूँ?"),
    ("Chetana", "जी हाँ, बोलिए। क्या हुआ?"),
    ("Harshad", "आपके आधार कार्ड से एक पार्सल बुक हुआ है, जिसमें ड्रग्स और पाँच पासपोर्ट मिले हैं। आपके नाम पर मनी लॉन्ड्रिंग का केस दर्ज हो गया है।"),
    ("Chetana", "क्या? मैंने तो कोई पार्सल नहीं भेजा!"),
    ("Harshad", "देखिए मैडम, आपके नाम पर अरेस्ट वारंट निकल चुका है। अभी आप डिजिटल अरेस्ट में हैं। वीडियो कॉल पर रहिए, और यह बात किसी को भी मत बताइए, घर वालों को भी नहीं।"),
    ("Chetana", "पर अब मैं क्या करूँ?"),
    ("Harshad", "वेरिफिकेशन के लिए अपने अकाउंट के सारे पैसे RBI के सेफ अकाउंट में तुरंत ट्रांसफर कीजिए। और आपके फोन पर एक OTP आया होगा, वो बताइए।"),
]

SAFE = [
    ("Devansh", "हेलो, मैं Amazon डिलीवरी से बोल रहा हूँ। आपका ऑर्डर आ गया है, आप घर पर हैं क्या?"),
    ("Chetana", "हाँ भैया, घर पर ही हूँ। गेट पर आ जाइए।"),
    ("Devansh", "ठीक है मैडम, पाँच मिनट में पहुँच रहा हूँ। कैश ऑन डिलीवरी है, दो सौ निन्यानवे रुपये।"),
    ("Chetana", "ठीक है, मैं आकर दे दूँगी।"),
    ("Devansh", "जी ठीक है, धन्यवाद।"),
]


def pcm_of(wav: bytes) -> bytes:
    with wave.open(io.BytesIO(wav)) as w:
        if w.getframerate() != RATE or w.getnchannels() != 1:
            raise RuntimeError(f"unexpected audio format {w.getframerate()} Hz x{w.getnchannels()}")
        return w.readframes(w.getnframes())


async def build(name: str, script: list[tuple[str, str]], client: httpx.AsyncClient):
    gap = b"\x00\x00" * int(RATE * 0.45)
    parts = []
    for voice, text in script:
        wav = await gnani.tts(client, text, language="hi-IN", voice=voice, sample_rate=RATE, speed=1.0)
        parts += [pcm_of(wav), gap]
        print(f"  {voice}: {text[:50]}…")
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(parts))
    print(f"wrote {path}")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:  # a narrowband, slightly noisy "phone line" version
        phone = OUT / f"{name}_phone.wav"
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(path), "-af",
                        "highpass=f=300,lowpass=f=3400,aresample=8000,aresample=16000,volume=0.9",
                        str(phone)], check=True)
        print(f"wrote {phone}")


async def main():
    OUT.mkdir(exist_ok=True)
    async with httpx.AsyncClient() as client:
        print("scam call:")
        await build("scam_call", SCAM, client)
        print("safe call:")
        await build("safe_call", SAFE, client)


if __name__ == "__main__":
    asyncio.run(main())
