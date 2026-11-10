"""Scam analysis with Gnani Evon, served by llama.cpp's OpenAI-compatible server on the GPU box."""
import asyncio
import json
import re
import time

import httpx

from . import config

SYSTEM_PROMPT = """You are Saavdhan, a fraud-detection assistant that protects people in India during phone calls.
You receive a live speech-to-text transcript of a call that is on speakerphone. It can be Hindi, English, Hinglish
or another Indian language, and it can contain speech-recognition mistakes. Both sides of the call are mixed together.

Judge how likely it is that the CALLER is a scammer. Common Indian scam patterns:
- "Digital arrest": fake police / CBI / ED / customs / narcotics officers say a case, FIR, parcel with drugs or money
  laundering is in your name, keep you on a video call, tell you not to tell family, and demand money to a "safe account".
- Fake bank / KYC / SIM / Aadhaar / PAN calls: account or SIM will be blocked, asks for OTP, UPI PIN, CVV, card number.
- Remote-access tricks: install AnyDesk / TeamViewer / an APK, share your screen, click a link.
- Bait: lottery, KBC prize, refund, cashback, job offer, electricity connection will be cut tonight.
Real banks, police and government NEVER ask for OTP/PIN, never arrest over video call, never ask you to move money.
Normal conversations (family, friends, deliveries, genuine customer care that asks for nothing sensitive) are SAFE.
Do not raise the risk just because a word like "bank" or "OTP" appears in a harmless context.

Decide in this order, and score ONLY what has actually been said so far:
1. Does the caller DEMAND something? Paying, sending or "sending back" money; any fee, charge, deposit or fine; an OTP,
   PIN, CVV, the digits on a card, an account or policy number; installing an app, clicking a link, scanning a QR code;
   keeping the call secret or staying on a video call; or a threat of what happens if you don't. A stranger making any
   of these demands is a SCAM, whatever story comes with it (loan approved, prize won, money sent by mistake, pension,
   electricity, card limit, a relative in trouble). Verdict "scam", risk 80-100; several demands together: 90+.
2. No demand yet, but a pressure story (claims to be police / CBI / bank / courier / telecom; mentions a case, a
   parcel, a blocked account, KYC, a prize): verdict "suspicious", risk 35-65. Real officials do call sometimes.
3. Ordinary conversation, or a genuine service that asks for nothing sensitive: verdict "safe", risk 0-30.

The verdict and the risk must agree: safe 0-30, suspicious 35-69, scam 70-100. Never invent red flags: quote only
words that show a demand, a threat or a pressure story. Ordinary family talk has no red flags.

Examples (verdict, risk, scam_type):
- "Beta, khana kha liya? Papa kaise hain?" -> safe, 0, None
- "Swiggy order aa raha hai, OTP ready rakhiye delivery ke time" -> safe, 10, None (a delivery OTP is shown at your door, not told to a caller)
- "Main CBI se bol raha hoon, aapke naam pe case darj hua hai" -> suspicious, 55, Digital arrest (no demand yet)
- "Aapka loan approve hua hai, file charge 5000 bhej dijiye" -> scam, 90, Fake loan (a stranger demands a fee)

Reply with ONLY a JSON object, no other text, fields in this order. Be brief: the call is happening now.
{
  "verdict": "safe" | "suspicious" | "scam",
  "risk": <integer 0-100>,
  "scam_type": "<one of: Digital arrest, Family emergency, Bank or KYC, OTP or PIN theft, Fake loan, Prize or lottery, Refund, Wrong transfer, Remote access app, QR code, Job, Investment, Electricity or bill, Blackmail, Parcel or customs, Other scam, None>",
  "red_flags": [<0 to 3 items> {"quote": "<2 to 6 words copied exactly from the transcript>", "reason": "<max 6 English words>"}],
  "explanation": "<max 15 English words>",
  "warning": "<max 2 short calm sentences for the person on the call, in the SAME language and script as the call (Hindi in Devanagari for Hindi or Hinglish): don't share OTP, PIN or money, hang up, report on 1930. Empty string if safe.>"
}"""

# Field order matters, measured with tools/evon_cache.py + tools/combine_eval.py on the same sentences: with "risk"
# first the model named the scam and still wrote 30; with "red_flags" first it invented flags. Also tried and
# dropped (Nov 8): multiple-choice "what is asked for / what story" fields first (missed 12 of 30 scams) and a
# free-text gist first (more false "careful"s). This verdict-first version catches the most; its false alarms on
# lines like "let me share my screen" are handled by the combination rule in app.combined_risk.
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["safe", "suspicious", "scam"]},
        "risk": {"type": "integer", "minimum": 0, "maximum": 100},
        "scam_type": {"type": "string"},
        "red_flags": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {"quote": {"type": "string", "maxLength": 60},
                               "reason": {"type": "string", "maxLength": 50}},
                "required": ["quote", "reason"],
            },
        },
        "explanation": {"type": "string", "maxLength": 120},
        "warning": {"type": "string", "maxLength": 200},
    },
    "required": ["verdict", "risk", "scam_type", "red_flags", "explanation", "warning"],
}
_BANDS = {"safe": (0, 30), "suspicious": (35, 69), "scam": (70, 100)}

_use_schema = True  # switched off automatically if the server rejects json_schema
last_usage: dict = {}


def enabled() -> bool:
    return bool(config.LLM_BASE_URL)


def _headers() -> dict:
    h = {"Content-Type": "application/json", "ngrok-skip-browser-warning": "1"}
    if config.LLM_API_KEY:
        h["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    return h


def _extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _consistent(verdict, risk: int) -> tuple[str, int]:
    """The model's verdict is more reliable than its number, so keep the number inside the verdict's band."""
    risk = max(0, min(100, int(risk)))
    if verdict not in _BANDS:
        verdict = "scam" if risk >= 70 else "suspicious" if risk >= 35 else "safe"
    lo, hi = _BANDS[verdict]
    return verdict, max(lo, min(hi, risk))


def _clean(d: dict) -> dict:
    verdict, risk = _consistent(d.get("verdict"), d.get("risk", 0))
    flags = [f for f in d.get("red_flags", []) if isinstance(f, dict) and f.get("quote")][:6]
    return {
        "risk": risk,
        "verdict": verdict,
        "scam_type": str(d.get("scam_type", "")).strip()[:60],
        "red_flags": [{"quote": str(f["quote"])[:120], "reason": str(f.get("reason", ""))[:120]} for f in flags],
        "explanation": str(d.get("explanation", "")).strip()[:300],
        "warning": str(d.get("warning", "")).strip()[:400],
    }


# verdict, risk and scam_type come first; the comma after scam_type means all three are complete.
_EARLY = re.compile(r'"verdict"\s*:\s*"(\w+)"\s*,\s*"risk"\s*:\s*(\d+)\s*,\s*"scam_type"\s*:\s*"([^"]*)"\s*,')


async def analyze(client: httpx.AsyncClient, transcript: str, on_early=None) -> dict:
    """Return the cleaned verdict plus timing, or raise on failure.

    With on_early, the answer is streamed and on_early({risk, verdict, scam_type}) is awaited as soon
    as those first fields are written, about a second in, long before the quotes and warning finish.
    """
    # The free tunnel sometimes drops a kept-alive connection; one quick retry covers it.
    for attempt in range(3):
        try:
            return await _analyze_stream(client, transcript, on_early)
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
            if attempt == 2:
                raise RuntimeError(f"Evon connection failed: {e}") from e
            await asyncio.sleep(0.3)


async def _analyze_stream(client: httpx.AsyncClient, transcript: str, on_early) -> dict:
    global _use_schema, last_usage
    body = _body(transcript)
    body["stream"] = True
    body["stream_options"] = {"include_usage": True}
    t0 = time.perf_counter()
    text, sent_early, timings, usage = "", False, {}, {}
    async with client.stream("POST", f"{config.LLM_BASE_URL}/v1/chat/completions", headers=_headers(),
                             json=body, timeout=config.LLM_TIMEOUT) as r:
        if r.status_code == 400 and _use_schema:
            await r.aread()
            _use_schema = False
            return await _analyze_stream(client, transcript, on_early)
        if r.status_code >= 400:
            await r.aread()
            raise RuntimeError(f"Evon HTTP {r.status_code}: {r.text[:200]}")
        async for line in r.aiter_lines():
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            timings = chunk.get("timings") or timings
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices", []):
                text += (choice.get("delta") or {}).get("content") or ""
            if on_early and not sent_early:
                m = _EARLY.search(text)
                if m:
                    sent_early = True
                    verdict, risk = _consistent(m.group(1), m.group(2))
                    await on_early({"risk": risk, "verdict": verdict,
                                    "scam_type": m.group(3), "red_flags": [], "explanation": "", "warning": "",
                                    "partial": True, "latency_ms": round((time.perf_counter() - t0) * 1000)})
    out = _clean(_extract_json(text))
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000)
    last_usage = {"prompt": usage.get("prompt_tokens"), "output": usage.get("completion_tokens"),
                  "prompt_tok_s": round(timings.get("prompt_per_second", 0)),
                  "gen_tok_s": round(timings.get("predicted_per_second", 0)), "cached": timings.get("cache_n")}
    return out


def _body(transcript: str) -> dict:
    body = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Call transcript so far:\n\"\"\"\n{transcript[-3000:]}\n\"\"\""},
        ],
        "temperature": 0.1,
        "max_tokens": 320,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if _use_schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "verdict", "schema": SCHEMA}}
    return body


async def health(client: httpx.AsyncClient) -> bool:
    if not enabled():
        return False
    try:
        r = await client.get(f"{config.LLM_BASE_URL}/health", headers=_headers(), timeout=5)
        return r.status_code == 200
    except httpx.HTTPError:
        return False
