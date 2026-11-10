"""Backend tests against local fakes of Gnani and Evon. No credits are spent.

    py -m unittest tests.test_backend -v
"""
import asyncio
import base64
import io
import json
import os
import sys
import time
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests import fakes  # noqa: E402

GP, LP, AP = fakes.free_port(), fakes.free_port(), fakes.free_port()
# Must be set before server.config is imported; real env/.env values are only defaults.
os.environ.update({
    "GNANI_API_KEY": "test-key",
    "GNANI_STT_WS": f"ws://127.0.0.1:{GP}/stt/v3/stream",
    "GNANI_STT_REST": f"http://127.0.0.1:{GP}/stt/v3",
    "GNANI_TTS_REST": f"http://127.0.0.1:{GP}/api/v1/tts/inference",
    "LLM_BASE_URL": f"http://127.0.0.1:{LP}",
    "LLM_API_KEY": "test-llm",
})

import httpx  # noqa: E402
import websockets  # noqa: E402

from server import app as appmod, config, rules  # noqa: E402

for url in (config.GNANI_STT_WS, config.GNANI_STT_REST, config.GNANI_TTS_REST, config.LLM_BASE_URL):
    assert "127.0.0.1" in url, f"refusing to run: {url} is not a local fake"

fakes.serve(fakes.gnani, GP)
fakes.serve(fakes.llm, LP)
fakes.serve(appmod.app, AP)
BASE = f"http://127.0.0.1:{AP}"
S = fakes.S


def wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * seconds))
    return buf.getvalue()


async def live_call(langs="hi-IN,en-IN", frames=200, stop=True, linger=2.5, pace=0.0):
    """Stream silent 1024-byte frames like the browser does and collect what the server sends."""
    got = []
    async with websockets.connect(f"ws://127.0.0.1:{AP}/ws/live?langs={langs}", max_size=None) as ws:
        async def recv():
            try:
                async for raw in ws:
                    got.append(json.loads(raw))
            except websockets.ConnectionClosed:
                pass
        r = asyncio.create_task(recv())
        for _ in range(frames):
            try:
                await ws.send(b"\0" * 1024)
            except websockets.ConnectionClosed:
                break
            await asyncio.sleep(pace)
        if stop:
            try:
                await ws.send(json.dumps({"type": "stop"}))
            except websockets.ConnectionClosed:
                pass
        await asyncio.sleep(linger)
        r.cancel()
    return got


def kinds(msgs):
    return [m["type"] for m in msgs]


class Rules(unittest.TestCase):
    def test_scam_call_climbs(self):
        scores = [rules.scan("\n".join(fakes.SCAM_LINES[:i]))["score"] for i in range(1, 5)]
        self.assertEqual(scores, sorted(scores))
        self.assertGreaterEqual(scores[-1], 95)

    def test_everyday_speech_stays_safe(self):
        for text in ["Haan main bilkul fine hoon, tum batao",
                     "Main turant aata hoon, gate pe ruko",
                     "मैं तुरंत आ रहा हूँ, दस मिनट",
                     "Mera pin code 110001 hai, parcel bhej dena",
                     "Beta khana kha liya? Papa kaise hain?"]:
            live = appmod.combined_risk(rules.scan(text)["score"], None)
            with self.subTest(text=text):
                self.assertLess(live, 35, f"harmless line scored {live}")

    def test_every_language_test_set(self):
        """1,253 sentences in 11 language forms: scams must alarm, everyday speech must not."""
        from tests import corpus, corpus_holdout, corpus_multi
        rows = [("hinglish*", t, l) for t, l in corpus.CASES] + corpus_multi.cases() + \
            corpus_holdout.cases() + corpus_holdout.cases(corpus_holdout.HOLDOUT2)
        self.assertGreaterEqual(len(rows), 1200)
        misses = []
        for lang, text, label in rows:
            live = appmod.combined_risk(rules.scan(text)["score"], None)
            if not corpus.passes(label, live):
                misses.append(f"{lang} [{label}] {live}: {text}")
        self.assertEqual(misses, [], f"{len(misses)} sentences scored wrong")

    def test_evon_alone_cannot_sound_the_alarm(self):
        self.assertEqual(appmod.combined_risk(0, {"risk": 95}), config.WARN_THRESHOLD - 1, "Evon alone: amber only")
        self.assertEqual(appmod.combined_risk(30, {"risk": 95}), 95, "Evon plus a rule sign: alarm")
        self.assertEqual(appmod.combined_risk(90, {"risk": 0}), 81, "Evon never lowers what the rules found")

    def test_evon_combination_on_saved_answers(self):
        """Evon's real answers (tools/evon_cache.py) on 673 sentences, re-combined with today's rules."""
        from tests import corpus_holdout
        cache_file = ROOT / "tests" / "evon_cache.json"
        if not cache_file.exists():
            self.skipTest("no saved Evon answers; run py tools/evon_cache.py")
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
        new = {t for _, t, _ in corpus_holdout.cases(corpus_holdout.HOLDOUT3)}
        known_missed, new_unflagged, false_alarms = [], [], []
        for text, c in cache.items():
            live = appmod.combined_risk(rules.scan(text)["score"], {"risk": c["evon_risk"]})
            if c["label"] == "scam" and text in new and live < 35:
                new_unflagged.append(text)
            elif c["label"] == "scam" and text not in new and live < config.WARN_THRESHOLD:
                known_missed.append(text)
            elif c["label"] in ("safe", "nowarn") and live >= config.WARN_THRESHOLD:
                false_alarms.append(text)
        self.assertGreaterEqual(len(cache), 600)
        self.assertEqual(known_missed, [], "a known scam lost its alarm")
        self.assertEqual(new_unflagged, [], "a new scam type was not even marked careful")
        # Measured Nov 8: 26 of 453, almost all "let me share my screen in the meeting". Don't let it grow.
        self.assertLessEqual(len(false_alarms), 26, "\n".join(false_alarms))

    def test_instant_check_is_instant(self):
        from tests import corpus_multi
        texts = [t for _, t, _ in corpus_multi.cases()]
        start = time.perf_counter()
        for t in texts:
            rules.scan(t)
        per_line_ms = (time.perf_counter() - start) * 1000 / len(texts)
        self.assertLess(per_line_ms, 5, f"{per_line_ms:.2f} ms per line")

    def test_warning_speaks_the_call_language(self):
        text, lang = appmod.warning_text(None, "gu-IN")
        self.assertEqual(lang, "gu-IN")
        self.assertIn("1930", text)
        self.assertTrue(any("઀" <= ch <= "૿" for ch in text), "Gujarati call must get a Gujarati warning")
        evon_tamil = {"verdict": "scam", "warning": "இது மோசடி அழைப்பு. உடனே துண்டிக்கவும்."}
        text, lang = appmod.warning_text(evon_tamil, "ta-IN")
        self.assertEqual(lang, "ta-IN")
        self.assertTrue(text.startswith("கவனம்!"))
        evon_marathi = {"verdict": "scam", "warning": "हा फसवणुकीचा कॉल आहे."}
        self.assertEqual(appmod.warning_text(evon_marathi, "mr-IN")[1], "mr-IN", "Devanagari on a Marathi call is Marathi")
        self.assertEqual(appmod.warning_text(evon_marathi, "hi-IN")[1], "hi-IN")
        self.assertEqual(appmod.warning_text(None, "xx-YY")[1], "hi-IN", "unknown language falls back to Hindi")
        evon_english = {"verdict": "scam", "warning": "Don't share OTP or money, hang up, report on 1930."}
        text, lang = appmod.warning_text(evon_english, "hi-IN")
        self.assertEqual(lang, "hi-IN", "an English warning from Evon on a Hindi call is replaced by the Hindi one")
        self.assertTrue(any("ऀ" <= ch <= "ॿ" for ch in text))
        self.assertEqual(appmod.warning_text(evon_english, "en-IN")[1], "en-IN", "English calls keep Evon's English warning")

    def test_wrong_evon_cannot_cancel_a_blatant_scam(self):
        score = rules.scan("\n".join(fakes.SCAM_LINES))["score"]
        self.assertGreaterEqual(appmod.combined_risk(score, {"risk": 0}), config.WARN_THRESHOLD)


class Live(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        S.reset()

    async def test_full_scam_call(self):
        msgs = await live_call(frames=4 * S.frames_per_line + 10)
        k = kinds(msgs)
        for needed in ("connected", "partial", "transcript", "risk", "warning", "warning_audio"):
            self.assertIn(needed, k)
        self.assertEqual(sum(1 for m in msgs if m["type"] == "transcript"), 4)
        self.assertEqual(k.count("warning"), 1, "warn once per call")
        audio = base64.b64decode(next(m for m in msgs if m["type"] == "warning_audio")["audio"])
        self.assertEqual(audio[:4], b"RIFF")
        last = [m for m in msgs if m["type"] == "risk"][-1]
        self.assertEqual(last["verdict"], "scam")
        self.assertEqual(last["evon"]["scam_type"], "Digital arrest")
        h = S.stream_headers[0]
        self.assertEqual(h["language_code"], "hi-IN", "streaming must get one locale")
        self.assertEqual(h["x-partials"], "true")
        self.assertEqual(h["model"], "prisma-v3.0")
        self.assertEqual(S.bad_frames, 0)
        self.assertEqual(S.commits, 1, "stop must commit the last sentence")
        self.assertEqual(S.llm_bad_auth, 0)

    async def test_harmless_call_no_alarm(self):
        S.lines = ["Hello beta, khana kha liya?", "Haan maa, abhi khaya.", "Papa kaise hain?"]
        msgs = await live_call(frames=3 * S.frames_per_line + 10)
        self.assertNotIn("warning", kinds(msgs))
        self.assertEqual([m for m in msgs if m["type"] == "risk"][-1]["verdict"], "safe")
        self.assertEqual(S.tts_calls, [], "no Timbre credits spent on a safe call")

    async def test_closing_early_releases_prisma(self):
        await live_call(frames=0, stop=False, linger=0.3)
        await asyncio.sleep(1.0)
        self.assertEqual(S.open_streams, 0, "a closed browser must close the Prisma stream")

    async def test_prisma_silent_close_is_reported(self):
        S.close_silently = True
        msgs = await live_call(frames=5)
        self.assertIn("notice", kinds(msgs), "user must be told the transcription stopped")

    async def test_evon_down_rules_still_warn(self):
        S.llm_fail_first = 99
        msgs = await live_call(frames=4 * S.frames_per_line + 10)
        self.assertIn("warning", kinds(msgs))
        self.assertIn("error", [m.get("state") for m in msgs if m["type"] == "evon"])

    async def test_evon_sees_the_last_line_after_a_blip(self):
        S.llm_fail_first = 1  # first analysis fails, later lines arrive inside the back-off window
        msgs = await live_call(frames=4 * S.frames_per_line + 10, pace=0.01, stop=False, linger=8)
        oks = [m for m in msgs if m["type"] == "evon" and m.get("state") == "ok"]
        self.assertTrue(oks, "Evon never analysed the call after one failed request")


class Recording(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        S.reset()

    async def test_check_a_recording(self):
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{BASE}/api/analyze", files={"file": ("call.wav", wav(50), "audio/wav")},
                             data={"langs": "hi-IN,en-IN"})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(len(d["segments"]), 4)  # 50 s -> 15+15+15+5
        self.assertEqual(S.rest_429, 0, "chunks must go one at a time")
        self.assertEqual([s["start"] for s in d["segments"]], [0, 15, 30, 45])
        self.assertEqual(d["verdict"], "scam")
        self.assertIsNotNone(d["warning"])
        self.assertEqual(d["evon"]["scam_type"], "Digital arrest")
        async with httpx.AsyncClient(timeout=60) as c:  # the page then asks Timbre to speak that warning
            r = await c.post(f"{BASE}/api/tts", json={"text": d["warning"]["text"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content[:4], b"RIFF")

    async def test_not_audio(self):
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{BASE}/api/analyze", files={"file": ("x.mp3", b"hello, not audio", "audio/mpeg")})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn(":\\", r.json()["detail"], "error must not leak server paths")

    async def test_prisma_down(self):
        S.rest_fail = True
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{BASE}/api/analyze", files={"file": ("call.wav", wav(5), "audio/wav")})
        self.assertEqual(r.status_code, 502)

    async def test_upload_cannot_make_server_fetch_urls(self):
        playlist = (f"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nhttp://127.0.0.1:{GP}/ssrf-probe.ts\n"
                    f"#EXTINF:2,\nhttp://127.0.0.1:{GP}/ssrf-probe-b.wav\n#EXT-X-ENDLIST\n").encode()
        async with httpx.AsyncClient(timeout=60) as c:
            await c.post(f"{BASE}/api/analyze", files={"file": ("x.m3u8", playlist, "audio/x-mpegurl")})
        self.assertEqual(S.probe_hits, 0, "an uploaded playlist made the server fetch a URL")


class Endpoints(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        S.reset()

    async def test_health(self):
        async with httpx.AsyncClient() as c:
            h = (await c.get(f"{BASE}/api/health")).json()
        self.assertTrue(h["gnani_key"] and h["evon_up"])

    async def test_pages_served(self):
        async with httpx.AsyncClient() as c:
            for p in ("/", "/app", "/app.js", "/style.css", "/pcm-worklet.js", "/home.css", "/home.js"):
                self.assertEqual((await c.get(BASE + p)).status_code, 200, p)
            self.assertIn("Hears the scam", (await c.get(BASE + "/")).text)
            self.assertIn('id="mic"', (await c.get(BASE + "/app")).text)

    async def test_try_a_line_spends_nothing(self):
        async with httpx.AsyncClient() as c:
            scam = (await c.post(f"{BASE}/api/scan", json={"text": "Aap digital arrest mein hain, kisi ko mat bataiye, turant paise transfer kijiye"})).json()
            safe = (await c.post(f"{BASE}/api/scan", json={"text": "Beta, khana kha liya? Papa kaise hain?"})).json()
        self.assertEqual(scam["verdict"], "scam")
        self.assertEqual(safe["verdict"], "safe")
        self.assertEqual((S.tts_calls, S.rest_calls, S.llm_calls), ([], 0, 0), "Try a line must not call Gnani or Evon")

    async def test_try_a_line_second_opinion_from_evon(self):
        async with httpx.AsyncClient(timeout=30) as c:
            d = (await c.post(f"{BASE}/api/judge", json={"text": "You are under digital arrest, share the OTP now"})).json()
            S.llm_fail_first = 1
            down = await c.post(f"{BASE}/api/judge", json={"text": "hello"})
        self.assertEqual(d["verdict"], "scam")
        self.assertEqual(d["evon"]["scam_type"], "Digital arrest")
        self.assertEqual(S.tts_calls, [], "a second opinion must not spend Timbre credits")
        self.assertEqual(down.status_code, 502, "if Evon fails, the page keeps the instant result")

    async def test_tts_is_not_an_open_credit_tap(self):
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{BASE}/api/tts", json={"text": f"any text {time.time()}", "language": "hi-IN"})
        self.assertEqual(r.status_code, 403, "anyone reaching the server can spend Timbre credits")
        self.assertEqual(S.tts_calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
