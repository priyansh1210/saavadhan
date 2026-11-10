"""Stream a 16 kHz mono WAV into /ws/live at real-time speed, as the browser mic would, and print events.

    py tools/stream_test.py samples/scam_call_phone.wav [ws://localhost:8000]
"""
import asyncio
import json
import sys
import time
import wave

import websockets

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main(path: str, base: str):
    with wave.open(path) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, "need 16 kHz mono"
        pcm = w.readframes(w.getnframes())
    t0 = time.time()
    async with websockets.connect(f"{base}/ws/live?langs=hi-IN,en-IN", max_size=None) as ws:
        async def send():
            for i in range(0, len(pcm), 1024):
                frame = pcm[i:i + 1024].ljust(1024, b"\0")
                await ws.send(frame)
                await asyncio.sleep(0.032)
            await ws.send(b"\0" * 1024 * 40)  # a little trailing silence
            await asyncio.sleep(1.5)
            await ws.send(json.dumps({"type": "stop"}))

        async def recv():
            async for raw in ws:
                m = json.loads(raw)
                t = f"{time.time() - t0:5.1f}s"
                k = m["type"]
                if k == "partial":
                    print(f"{t}   partial: {m['text'][:90]}")
                elif k == "transcript":
                    print(f"{t} TRANSCRIPT ({m.get('latency')} ms): {m['text']}")
                elif k == "risk":
                    ev = m["evon"]
                    print(f"{t} RISK {m['risk']} {m['verdict']} | signs={len(m['rules']['signs'])}"
                          + (f" | evon={ev['risk']} {ev['scam_type']}" if ev else ""))
                elif k == "warning_audio":
                    print(f"{t} WARNING AUDIO {len(m['audio']) * 3 // 4} bytes")
                elif k in ("warning", "notice", "evon", "connected"):
                    print(f"{t} {k.upper()}: {json.dumps({x: y for x, y in m.items() if x != 'type'}, ensure_ascii=False)}")

        sender = asyncio.create_task(send())
        try:
            await asyncio.wait_for(recv(), timeout=len(pcm) / 32000 + 30)
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            pass
        sender.cancel()


asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8000"))
