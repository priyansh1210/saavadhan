"""Local stand-ins for Gnani Prisma/Timbre and the Evon server, so tests spend no credits.

They behave like the real services did in the 2026-11-08 probes: streaming wants one locale,
partials come as `partial` and finals as `final_transcript`, REST allows one request at a time
(429 otherwise), TTS returns a WAV.
"""
import asyncio
import io
import json
import socket
import threading
import time
import wave

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse

SCAM_LINES = [
    "Hello, मैं मुंबई crime branch से inspector राजेश शर्मा बोल रहा हूँ।",
    "आपके आधार कार्ड से एक पार्सल बुक हुआ है जिसमें ड्रग्स मिले हैं। आपके नाम पर केस दर्ज हो गया है।",
    "अभी आप digital arrest में हैं, वीडियो call पर रहिए और यह बात किसी को भी मत बताइए।",
    "अपने account के सारे पैसे RBI के safe account में तुरंत transfer कीजिए। OTP बताइए।",
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def tiny_wav(seconds: float = 0.2, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * seconds))
    return buf.getvalue()


class State:
    """What the fakes saw, and switches to make them misbehave."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.lines = list(SCAM_LINES)
        self.frames_per_line = 20          # ~0.6 s of 32 ms frames per scripted line
        self.stream_headers = []
        self.bad_frames = 0
        self.frames = 0
        self.commits = 0
        self.open_streams = 0
        self.close_silently = False        # close 1008 with no error frame
        self.rest_calls = 0
        self.rest_active = 0
        self.rest_429 = 0
        self.rest_fail = False
        self.tts_calls = []
        self.probe_hits = 0
        self.llm_calls = 0
        self.llm_fail_first = 0            # fail this many LLM calls, then work
        self.llm_force_risk = None         # e.g. 0 to simulate a fooled or wrong Evon
        self.llm_bad_auth = 0


S = State()
gnani = FastAPI()
llm = FastAPI()


@gnani.websocket("/stt/v3/stream")
async def stt_stream(ws: WebSocket):
    h = dict(ws.headers)
    S.stream_headers.append(h)
    await ws.accept()
    if not h.get("x-api-key-id"):
        await ws.close(code=1008)
        return
    lang = h.get("language_code", "")
    if "," in lang or not lang:
        await ws.send_json({"type": "error", "message": f"Invalid language_code: {lang}"})
        await ws.close(code=1008)
        return
    if S.close_silently:
        await ws.close(code=1008, reason="Invalid x-substitution-map")
        return
    S.open_streams += 1
    try:
        await ws.send_json({"type": "connected", "config": {"language_code": lang, "partials_enabled": h.get("x-partials") == "true"}})
        n, line = 0, 0
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                S.frames += 1
                if len(msg["bytes"]) != 1024:
                    S.bad_frames += 1
                n += 1
                if n == 3 and line < len(S.lines):
                    await ws.send_json({"type": "speech_start"})
                if n == S.frames_per_line // 2 and line < len(S.lines):
                    await ws.send_json({"type": "partial", "text": S.lines[line][:20]})
                if n >= S.frames_per_line and line < len(S.lines):
                    await ws.send_json({"type": "final_transcript", "text": S.lines[line],
                                        "detected_language_code": "hi-IN", "latency": 120})
                    line, n = line + 1, 0
            elif msg.get("text"):
                if json.loads(msg["text"]).get("type") == "commit":
                    S.commits += 1
    finally:
        S.open_streams -= 1


@gnani.post("/stt/v3")
async def stt_rest(request: Request):
    form = await request.form()
    if S.rest_active:
        S.rest_429 += 1
        return JSONResponse({"detail": {"error_code": "RATE_LIMITED"}}, status_code=429)
    S.rest_active += 1
    try:
        await asyncio.sleep(0.05)
        i = S.rest_calls
        S.rest_calls += 1
        if S.rest_fail:
            return JSONResponse({"detail": "boom"}, status_code=500)
        assert form.get("audio_file") is not None
        text = S.lines[i] if i < len(S.lines) else ""
        return {"success": True, "transcript": text, "detected_language_code": "hi-IN", "model": "prisma-v3.0"}
    finally:
        S.rest_active -= 1


@gnani.post("/api/v1/tts/inference")
async def tts(request: Request):
    body = await request.json()
    S.tts_calls.append(body)
    if not body.get("text") or not body.get("voice"):
        return JSONResponse({"detail": "bad"}, status_code=400)
    return Response(tiny_wav(rate=body["audio_config"]["sample_rate"]), media_type="audio/wav")


@gnani.get("/ssrf-probe{rest:path}")
async def probe(rest: str = ""):
    S.probe_hits += 1
    return PlainTextResponse("#EXTM3U\n")


def _verdict_for(text: str) -> dict:
    t = text.lower()
    if S.llm_force_risk is not None:
        risk = S.llm_force_risk
    elif "otp" in t or "digital arrest" in t:
        risk = 95
    elif "केस दर्ज" in text:
        risk = 75
    elif "crime branch" in t:
        risk = 35
    else:
        risk = 5
    verdict = "scam" if risk >= 70 else "suspicious" if risk >= 35 else "safe"
    return {"risk": risk, "verdict": verdict, "scam_type": "Digital arrest" if risk >= 70 else "None",
            "red_flags": [{"quote": "digital arrest", "reason": "fake legal threat"}] if risk >= 70 else [],
            "explanation": "test verdict", "warning": "यह फ्रॉड कॉल है। कॉल काटें।" if risk >= 70 else ""}


@llm.get("/health")
async def llm_health():
    return {"status": "ok"}


@llm.post("/v1/chat/completions")
async def chat(request: Request):
    if request.headers.get("authorization") != "Bearer test-llm":
        S.llm_bad_auth += 1
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    S.llm_calls += 1
    if S.llm_fail_first > 0:
        S.llm_fail_first -= 1
        return JSONResponse({"error": "down"}, status_code=500)
    content = json.dumps(_verdict_for(body["messages"][-1]["content"]), ensure_ascii=False)
    if not body.get("stream"):
        return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 20}}

    async def gen():
        for i in range(0, len(content), 7):
            chunk = {"choices": [{"delta": {"content": content[i:i + 7]}}]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.005)
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


def serve(app, port: int) -> uvicorn.Server:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            return server
        time.sleep(0.05)
    raise RuntimeError(f"server on {port} did not start")
