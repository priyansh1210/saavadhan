"""Run the real Saavdhan app against fake Gnani + fake Evon, for clicking through the UI without spending credits.

    py tests/fake_stack.py        -> http://127.0.0.1:8800
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests import fakes  # noqa: E402

GP, LP = fakes.free_port(), fakes.free_port()
os.environ.update({
    "GNANI_API_KEY": "test-key",
    "GNANI_STT_WS": f"ws://127.0.0.1:{GP}/stt/v3/stream",
    "GNANI_STT_REST": f"http://127.0.0.1:{GP}/stt/v3",
    "GNANI_TTS_REST": f"http://127.0.0.1:{GP}/api/v1/tts/inference",
    "LLM_BASE_URL": f"http://127.0.0.1:{LP}",
    "LLM_API_KEY": "test-llm",
})
from server import app as appmod, config  # noqa: E402

assert all("127.0.0.1" in u for u in (config.GNANI_STT_WS, config.GNANI_STT_REST, config.GNANI_TTS_REST, config.LLM_BASE_URL))
fakes.S.frames_per_line = 70  # ~2.2 s per scripted line, like real speech
fakes.serve(fakes.gnani, GP)
fakes.serve(fakes.llm, LP)
fakes.serve(appmod.app, 8800)
print("fake stack on http://127.0.0.1:8800", flush=True)
while True:
    time.sleep(3600)
