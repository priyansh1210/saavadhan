"""Check that Evon's risk climbs line by line through the scam call and stays low on harmless calls.

    py tools/calibrate_evon.py
"""
import asyncio
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import evon  # noqa: E402

SCAM_LINES = [
    "Hello, मैं मुंबई crime branch से inspector राजेश शर्मा बोल रहा हूँ। क्या मैं सुनीता वर्मा जी से बात कर रहा हूँ? जी हाँ, बोलिए।",
    "क्या हुआ? आपके आधार कार्ड से एक पार्सल बुक हुआ है जिसमें ड्रग्स और पाँच पासपोर्ट मिले हैं।",
    "देखिए मैडम, आपके नाम पर अरेस्ट वारंट निकल चुका है, अभी आप digital arrest में हैं, वीडियो call पर रहिए और यह बात किसी को भी मत बताइए।",
    "verification के लिए अपने account के सारे पैसे RBI के safe account में तुरंत transfer कीजिए। और आपके phone पर एक OTP आया होगा, वो बताइए।",
]
HARMLESS = [
    "Hello beta, khana kha liya? Haan maa, abhi khaya. Papa kaise hain? Theek hain, bas thoda thak gaye hain.",
    "Hello sir, main HDFC bank se bol raha hoon, aapke credit card ka bill 5000 rupaye due hai, kal last date hai. Aap app se pay kar dijiye. Theek hai, thank you.",
    "Bhaiya mera Swiggy order kahan pahuncha? Madam main bas paanch minute mein aa raha hoon, OTP ready rakhiye delivery ke time. Achha theek hai.",
]


async def main():
    async with httpx.AsyncClient() as c:
        print("SCAM call, line by line:")
        for i in range(1, len(SCAM_LINES) + 1):
            out = await evon.analyze(c, "\n".join(SCAM_LINES[:i]))
            print(f"  after line {i}: {out['risk']:>3} {out['verdict']:<10} {out['scam_type']}")
        print("Harmless calls:")
        for t in HARMLESS:
            out = await evon.analyze(c, t)
            print(f"  {out['risk']:>3} {out['verdict']:<10} {t[:60]}")


asyncio.run(main())
