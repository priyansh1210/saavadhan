"""Time Evon on the scam transcript: prompt/generation speed and total latency.

    py tools/bench_evon.py
"""
import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import config, evon  # noqa: E402

TRANSCRIPT = """Hello, मैं मुंबई crime branch से inspector राजेश शर्मा बोल रहा हूँ। क्या मैं सुनीता वर्मा जी से बात कर रहा हूँ? जी हाँ। बोलिए, क्या हुआ?
आपके आधार कार्ड से एक पार्सल बुक हुआ है जिसमें ड्रग्स और पाँच पासपोर्ट मिले हैं। आपके नाम पर मनी लॉन्ड्रिंग का केस दर्ज हो गया है।
देखिए मैडम। आपके नाम पर arrest warrant निकल चुका है, अभी आप digital arrest में हैं, video call पर रहिये और यह बात किसी को भी मत बताइये।
verification के लिए अपने account के सारे पैसे RBI के safe account में तुरंत transfer कीजिए। और आपके फोन पर एक OTP आया होगा, वह बताइये।"""


async def main():
    async with httpx.AsyncClient() as c:
        for run in range(2):
            t0 = time.perf_counter()

            async def early(p):
                print(f"   early after {time.perf_counter() - t0:.1f}s: risk={p['risk']} {p['verdict']} {p['scam_type']}")

            out = await evon.analyze(c, TRANSCRIPT, on_early=early)
            print(f"run {run + 1}: {time.perf_counter() - t0:.1f}s  risk={out['risk']} {out['scam_type']}")
            print("   flags:", [f["quote"] for f in out["red_flags"]])
            print("   warning:", out["warning"])
            print("   usage:", evon.last_usage)


asyncio.run(main())
