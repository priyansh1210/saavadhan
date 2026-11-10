"""Print Evon's full JSON verdict for a few sentences (debugging its scoring).

    py tools/peek_evon.py "sentence one" "sentence two"
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import evon  # noqa: E402


async def main():
    async with httpx.AsyncClient() as c:
        for text in sys.argv[1:]:
            v = await evon.analyze(c, text)
            print(text[:80], "\n ", json.dumps(v, ensure_ascii=False), "\n")


asyncio.run(main())
