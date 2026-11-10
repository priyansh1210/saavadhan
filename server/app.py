"""Saavdhan backend: live scam-call guard on Gnani Prisma + Evon + Timbre.

Run:  py -m uvicorn server.app:app --port 8000
(Binds to 127.0.0.1 only. There is no login, so anyone who can reach it can spend your Gnani credits.)
"""
import asyncio
import base64
import io
import json
import logging
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import httpx
import websockets
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, evon, gnani, rules

log = logging.getLogger("saavdhan")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

WEB = config.ROOT / "web"
app = FastAPI(title="Saavdhan")
http = httpx.AsyncClient()

# Spoken when Evon has no warning of its own: the same message in every language Timbre speaks.
CANNED_WARNING = {
    "hi-IN": "सावधान! <pauses> यह कॉल फ्रॉड हो सकता है। <pauses> कोई भी OTP, PIN या पैसे मत दीजिए। "
             "<pauses> अभी कॉल काट दीजिए, और 1930 पर शिकायत कीजिए।",
    "en-IN": "Careful! <pauses> This call looks like a scam. <pauses> Do not share any OTP, PIN or money. "
             "<pauses> Hang up now, and report it on 1930.",
    "mr-IN": "सावधान! <pauses> हा कॉल फसवणुकीचा असू शकतो. <pauses> कोणताही OTP, PIN किंवा पैसे देऊ नका. "
             "<pauses> आत्ताच कॉल कट करा, आणि 1930 वर तक्रार करा.",
    "gu-IN": "સાવધાન! <pauses> આ કૉલ છેતરપિંડીનો હોઈ શકે છે. <pauses> કોઈ પણ OTP, PIN કે પૈસા આપશો નહીં. "
             "<pauses> હમણાં જ કૉલ કાપી નાખો, અને 1930 પર ફરિયાદ કરો.",
    "pa-IN": "ਸਾਵਧਾਨ! <pauses> ਇਹ ਕਾਲ ਧੋਖਾਧੜੀ ਹੋ ਸਕਦੀ ਹੈ। <pauses> ਕੋਈ ਵੀ OTP, PIN ਜਾਂ ਪੈਸੇ ਨਾ ਦਿਓ। "
             "<pauses> ਹੁਣੇ ਕਾਲ ਕੱਟ ਦਿਓ, ਅਤੇ 1930 'ਤੇ ਸ਼ਿਕਾਇਤ ਕਰੋ।",
    "bn-IN": "সাবধান! <pauses> এই কলটি প্রতারণা হতে পারে। <pauses> কোনো OTP, PIN বা টাকা দেবেন না। "
             "<pauses> এখনই কল কেটে দিন, আর 1930-এ অভিযোগ করুন।",
    "ta-IN": "கவனம்! <pauses> இந்த அழைப்பு மோசடியாக இருக்கலாம். <pauses> எந்த OTP, PIN அல்லது பணத்தையும் கொடுக்காதீர்கள். "
             "<pauses> உடனே அழைப்பைத் துண்டித்து, 1930-இல் புகார் செய்யுங்கள்.",
    "te-IN": "జాగ్రత్త! <pauses> ఈ కాల్ మోసం కావచ్చు. <pauses> ఏ OTP, PIN లేదా డబ్బు ఇవ్వకండి. "
             "<pauses> వెంటనే కాల్ కట్ చేసి, 1930కి ఫిర్యాదు చేయండి.",
    "kn-IN": "ಎಚ್ಚರಿಕೆ! <pauses> ಈ ಕರೆ ವಂಚನೆಯಾಗಿರಬಹುದು. <pauses> ಯಾವುದೇ OTP, PIN ಅಥವಾ ಹಣ ಕೊಡಬೇಡಿ. "
             "<pauses> ಈಗಲೇ ಕರೆ ಕಟ್ ಮಾಡಿ, 1930ಗೆ ದೂರು ನೀಡಿ.",
    "ml-IN": "ശ്രദ്ധിക്കുക! <pauses> ഈ കോൾ തട്ടിപ്പാകാം. <pauses> ഒരു OTP-യും PIN-ഉം പണവും നൽകരുത്. "
             "<pauses> ഉടൻ കോൾ കട്ട് ചെയ്ത്, 1930-ൽ പരാതി നൽകുക.",
}
# Unicode block of each script -> its language. Devanagari is Hindi unless the call is Marathi.
SCRIPTS = [("ऀ", "ॿ", "hi-IN"), ("ঀ", "৿", "bn-IN"), ("਀", "੿", "pa-IN"),
           ("઀", "૿", "gu-IN"), ("஀", "௿", "ta-IN"), ("ఀ", "౿", "te-IN"),
           ("ಀ", "೿", "kn-IN"), ("ഀ", "ൿ", "ml-IN")]


def language_of(text: str, call_language: str) -> str:
    for lo, hi, lang in SCRIPTS:
        if any(lo <= ch <= hi for ch in text):
            return "mr-IN" if lang == "hi-IN" and call_language == "mr-IN" else lang
    return "en-IN" if text.strip() else call_language
_tts_cache: dict[tuple[str, str], bytes] = {}
_issued: dict[str, str] = {}  # warning text -> language; /api/tts speaks only these


def combined_risk(rule_score: int, llm: dict | None) -> int:
    """Rules react instantly; Evon can raise the risk but never lower what the rules found.

    The spoken alarm needs two witnesses: Evon alone can only reach "careful" (amber); Evon reaches the alarm when the
    rules also saw at least one sign. Measured with tools/combine_eval.py on 673 sentences (Nov 8): letting Evon alarm
    alone raised 80 false alarms on 453 harmless lines ("let me share my screen", "my pin code is ..."); with this rule
    26, while every known scam still alarms and every new scam type the rules miss still shows amber.
    """
    rules_risk = round(rule_score * 0.9)
    if llm is None:
        return rules_risk
    evon_risk = llm["risk"] if rule_score > 0 else min(llm["risk"], config.WARN_THRESHOLD - 1)
    return max(rules_risk, evon_risk)


def verdict_for(risk: int) -> str:
    return "scam" if risk >= config.WARN_THRESHOLD else "suspicious" if risk >= 35 else "safe"


async def speak(text: str, language: str) -> bytes:
    key = (text, language)
    if key not in _tts_cache:
        if len(_tts_cache) >= 50:  # one warning per scam call; keep memory bounded
            _tts_cache.pop(next(iter(_tts_cache)))
        _tts_cache[key] = await gnani.tts(http, text, language=language)
    return _tts_cache[key]


def warning_text(llm: dict | None, language: str) -> tuple[str, str]:
    """Pick the spoken warning and its language."""
    call_lang = language if language in CANNED_WARNING else "hi-IN"
    if llm and llm.get("warning") and llm["verdict"] != "safe":
        text = llm["warning"]
        lang = language_of(text, call_lang)
        # Evon sometimes answers in English on a Hindi call; the listener must hear their own language.
        if lang == call_lang:
            careful = CANNED_WARNING[lang].split(" <pauses>")[0]  # "सावधान!", "கவனம்!", ...
            return f"{careful} <pauses> {text}", lang
    return CANNED_WARNING[call_lang], call_lang


# --------------------------------------------------------------------------------------------
# Static site and health
# --------------------------------------------------------------------------------------------
@app.get("/")
async def home():
    return FileResponse(WEB / "home.html")


@app.get("/app")
async def guard():
    return FileResponse(WEB / "index.html")


class ScanIn(BaseModel):
    text: str


@app.post("/api/scan")
async def scan(body: ScanIn):
    """The home page's 'Try a line': instant rules only, so it costs no credits."""
    result = rules.scan(body.text[:500])
    risk = combined_risk(result["score"], None)
    return {"risk": risk, "verdict": verdict_for(risk), "signs": result["signs"]}


_judge_lock = asyncio.Lock()


@app.post("/api/judge")
async def judge(body: ScanIn):
    """'Try a line', second opinion: Evon reads the line (runs on our own GPU, so no credits).

    Rules catch known patterns in a millisecond; Evon understands new scam stories the word list has never seen.
    """
    if not evon.enabled():
        raise HTTPException(503, "Evon is not connected")
    text = body.text[:500]
    result = rules.scan(text)
    async with _judge_lock:  # one at a time: the GPU serves the live calls first
        try:
            llm = await evon.analyze(http, text)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"Evon unreachable: {str(e)[:120]}")
    risk = combined_risk(result["score"], llm)
    return {"risk": risk, "verdict": verdict_for(risk), "signs": result["signs"], "evon": llm}


@app.get("/api/health")
async def health():
    return {
        "gnani_key": bool(config.GNANI_API_KEY),
        "evon_configured": evon.enabled(),
        "evon_up": await evon.health(http),
        "stt_model": config.STT_MODEL,
        "tts_model": config.TTS_MODEL,
        "voice": config.TTS_VOICE,
        "threshold": config.WARN_THRESHOLD,
    }


class TTSIn(BaseModel):
    text: str


@app.post("/api/tts")
async def tts_endpoint(body: TTSIn):
    # Only warnings this server produced, so the endpoint can't be used to spend Timbre credits on any text.
    if body.text not in _issued:
        raise HTTPException(403, "Only Saavdhan's own warnings can be spoken")
    try:
        audio = await speak(body.text, _issued[body.text])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    return Response(audio, media_type="audio/wav")


# --------------------------------------------------------------------------------------------
# Live call: browser mic -> Prisma stream -> rules + Evon -> Timbre warning
# --------------------------------------------------------------------------------------------
class LiveSession:
    def __init__(self, ws: WebSocket, langs: str):
        self.ws = ws
        self.langs = langs
        self.lines: list[str] = []
        first = langs.split(",")[0].strip()
        self.language = first if first in CANNED_WARNING else "hi-IN"  # updated from what Prisma detects
        self.rule_result = {"score": 0, "signs": []}
        self.llm: dict | None = None
        self.warned = False
        self.dirty = asyncio.Event()
        self.closed = False
        self.evon_failed_at = 0.0
        self.send_lock = asyncio.Lock()

    async def send(self, msg: dict):
        if self.closed:
            return
        async with self.send_lock:
            try:
                await self.ws.send_text(json.dumps(msg, ensure_ascii=False))
            except Exception:  # noqa: BLE001
                self.closed = True

    def transcript(self) -> str:
        return "\n".join(self.lines)

    async def publish_risk(self):
        risk = combined_risk(self.rule_result["score"], self.llm)
        await self.send({"type": "risk", "risk": risk, "verdict": verdict_for(risk),
                         "rules": self.rule_result, "evon": self.llm})
        if risk >= config.WARN_THRESHOLD and not self.warned:
            self.warned = True
            asyncio.create_task(self.warn())

    async def warn(self):
        text, lang = warning_text(self.llm, self.language)
        await self.send({"type": "warning", "text": text.replace("<pauses>", "").strip(), "language": lang})
        try:
            audio = await speak(text, lang)
            await self.send({"type": "warning_audio", "audio": base64.b64encode(audio).decode()})
        except Exception as e:  # noqa: BLE001
            log.warning("TTS failed: %s", e)
            await self.send({"type": "notice", "level": "error", "text": f"Timbre TTS failed: {e}"})

    async def on_transcript(self, frame: dict):
        text = (frame.get("text") or "").strip()
        if not text:
            return
        self.language = frame.get("detected_language_code") or self.language
        self.lines.append(text)
        await self.send({"type": "transcript", "text": text, "index": len(self.lines),
                         "language": frame.get("detected_language_code"), "latency": frame.get("latency")})
        self.rule_result = rules.scan(self.transcript())
        await self.publish_risk()
        self.dirty.set()

    async def evon_worker(self):
        if not evon.enabled():
            await self.send({"type": "evon", "state": "off"})
            return
        while not self.closed:
            await self.dirty.wait()
            self.dirty.clear()
            wait = 5 - (time.time() - self.evon_failed_at)
            if wait > 0:  # back off after a failure, then analyse the latest transcript (never drop it)
                await asyncio.sleep(wait)
                if self.closed:
                    break
                self.dirty.clear()
            await self.send({"type": "evon", "state": "thinking"})

            async def early(partial: dict):
                # Evon's score arrives ~1-2 s in; keep the last full explanation on screen meanwhile.
                prev = self.llm or {}
                self.llm = {**partial, "red_flags": prev.get("red_flags", []),
                            "explanation": prev.get("explanation", ""), "warning": prev.get("warning", "")}
                await self.publish_risk()

            try:
                self.llm = await evon.analyze(http, self.transcript(), on_early=early)
                await self.send({"type": "evon", "state": "ok", "latency_ms": self.llm["latency_ms"]})
                await self.publish_risk()
            except Exception as e:  # noqa: BLE001
                self.evon_failed_at = time.time()
                self.dirty.set()  # retry this transcript after the back-off
                log.warning("Evon failed: %s", e)
                await self.send({"type": "evon", "state": "error", "error": str(e)[:200]})

    async def run(self):
        try:
            upstream = await gnani.open_stt_stream(self.langs)
        except Exception as e:  # noqa: BLE001
            await self.send({"type": "notice", "level": "error", "text": f"Could not connect to Prisma: {e}"})
            await self.ws.close()
            return

        async def browser_to_gnani():
            while True:
                msg = await self.ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes"):
                    await upstream.send(msg["bytes"])
                elif msg.get("text"):
                    data = json.loads(msg["text"])
                    if data.get("type") == "stop":
                        await upstream.send(json.dumps({"type": "commit"}))
                        await asyncio.sleep(1.5)
                        break

        async def gnani_to_browser():
            try:
                async for raw in upstream:
                    if isinstance(raw, bytes):
                        continue
                    frame = json.loads(raw)
                    kind = frame.get("type")
                    if kind in ("transcript", "final_transcript"):  # final_transcript when x-partials is on
                        await self.on_transcript(frame)
                    elif kind and "partial" in kind:
                        await self.send({"type": "partial", "text": frame.get("text", "")})
                    elif kind in ("speech_start", "processing", "connected", "speech_end"):
                        await self.send({"type": kind})
                    elif kind == "error":
                        await self.send({"type": "notice", "level": "error", "text": f"Prisma: {frame.get('message')}"})
                    else:
                        log.info("prisma frame %s: %s", kind, str(frame)[:200])
            except websockets.ConnectionClosed as e:
                why = f"{e.rcvd.code} {e.rcvd.reason}".strip() if e.rcvd else "connection lost"
                await self.send({"type": "notice", "level": "error", "text": f"Transcription stopped: Prisma closed the line ({why})"})

        tasks = [asyncio.create_task(browser_to_gnani()), asyncio.create_task(gnani_to_browser()),
                 asyncio.create_task(self.evon_worker())]
        try:
            await asyncio.wait(tasks[:2], return_when=asyncio.FIRST_COMPLETED)
        finally:
            self.closed = True
            self.dirty.set()
            for t in tasks:
                t.cancel()
            await upstream.close()


@app.websocket("/ws/live")
async def live(ws: WebSocket, langs: str = ""):
    await ws.accept()
    session = LiveSession(ws, langs or config.STT_LANGS)
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        log.exception("live session failed")
        await session.send({"type": "notice", "level": "error", "text": str(e)})
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------------------------
# Recording check: file -> 15 s chunks -> Prisma REST -> rules timeline + Evon verdict
# --------------------------------------------------------------------------------------------
CHUNK_S = 15


def to_pcm16k(raw: bytes, suffix: str) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(500, "ffmpeg is not installed on the server")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"in{suffix or '.bin'}"
        src.write_bytes(raw)
        p = subprocess.run([ffmpeg, "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000",
                            "-f", "s16le", "-"], capture_output=True, timeout=120)
        if p.returncode != 0:
            log.info("ffmpeg could not read upload: %s", p.stderr.decode(errors="replace")[-300:])
            raise HTTPException(400, "This file doesn't look like audio. Try an MP3, M4A, WAV or OGG recording.")
        return p.stdout


def wav_bytes(pcm: bytes, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


@app.post("/api/analyze")
async def analyze_file(file: UploadFile = File(...), langs: str = Form("")):
    if (file.size or 0) > 40 * 1024 * 1024:  # checked before reading it into memory
        raise HTTPException(413, "Please upload a file under 40 MB")
    raw = await file.read()
    pcm = await asyncio.to_thread(to_pcm16k, raw, Path(file.filename or "").suffix)
    step = CHUNK_S * 16000 * 2
    chunks = [pcm[i:i + step] for i in range(0, len(pcm), step)]
    if len(chunks) > 1 and len(chunks[-1]) < 16000:  # drop a tail under 0.5 s
        chunks.pop()
    if len(chunks) > 40:
        raise HTTPException(413, "Please upload a recording under 10 minutes")

    # One chunk at a time: the account allows one active Prisma request, and each chunk
    # gets the previous chunk's words as context, which helps at the cut points.
    segments = []
    previous = ""
    for i, c in enumerate(chunks):
        seg = {"start": i * CHUNK_S, "end": i * CHUNK_S + len(c) / 32000, "text": ""}
        try:
            res = await gnani.stt_rest(http, wav_bytes(c), langs or config.STT_LANGS, previous_text=previous)
            seg["text"] = (res.get("transcript") or "").strip()
            seg["language"] = res.get("detected_language_code")
            previous = (previous + " " + seg["text"]).strip()
        except Exception as e:  # noqa: BLE001
            seg["error"] = str(e)
        segments.append(seg)
    errors = [s["error"] for s in segments if s.get("error")]
    if errors and len(errors) == len(segments):
        raise HTTPException(502, errors[0])

    so_far = []
    for s in segments:
        if s["text"]:
            so_far.append(s["text"])
        s["rule_score"] = rules.scan("\n".join(so_far))["score"] if so_far else 0
    full = "\n".join(so_far)
    rule_result = rules.scan(full)
    llm, llm_error = None, None
    if evon.enabled() and full:
        try:
            llm = await evon.analyze(http, full)
        except Exception as e:  # noqa: BLE001
            llm_error = str(e)[:200]
    risk = combined_risk(rule_result["score"], llm)
    language = next((s["language"] for s in segments if s.get("language")), "hi-IN")
    warn_text, warn_lang = warning_text(llm, language)
    if risk >= config.WARN_THRESHOLD:
        if len(_issued) >= 100:
            _issued.pop(next(iter(_issued)))
        _issued[warn_text] = warn_lang
    return JSONResponse({
        "duration": len(pcm) / 32000,
        "segments": segments,
        "rules": rule_result,
        "evon": llm,
        "evon_error": llm_error,
        "risk": risk,
        "verdict": verdict_for(risk),
        "warning": {"text": warn_text, "language": warn_lang} if risk >= config.WARN_THRESHOLD else None,
    })


app.mount("/", StaticFiles(directory=WEB), name="web")
