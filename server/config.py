"""Settings, read from environment variables or a .env file in the project root."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():  # -sig: tolerate a BOM from Notepad
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Gnani speech APIs
GNANI_API_KEY = env("GNANI_API_KEY")
GNANI_STT_WS = env("GNANI_STT_WS", "wss://api.vachana.ai/stt/v3/stream")
GNANI_STT_REST = env("GNANI_STT_REST", "https://api.vachana.ai/stt/v3")
GNANI_TTS_REST = env("GNANI_TTS_REST", "https://api.vachana.ai/api/v1/tts/inference")
STT_MODEL = env("STT_MODEL", "prisma-v3.0")
STT_LANGS = env("STT_LANGS", "hi-IN,en-IN")  # or indic-auto
STT_FORMAT = env("STT_FORMAT", "codemix")    # English words stay in Latin script
TTS_MODEL = env("TTS_MODEL", "timbre-v3.0")
TTS_VOICE = env("TTS_VOICE", "Tarika")

# Evon (OpenAI-compatible llama.cpp server on the GPU box)
LLM_BASE_URL = env("LLM_BASE_URL").rstrip("/")
LLM_API_KEY = env("LLM_API_KEY")
LLM_MODEL = env("LLM_MODEL", "evon")
LLM_TIMEOUT = float(env("LLM_TIMEOUT", "40"))

# Detection
WARN_THRESHOLD = int(env("WARN_THRESHOLD", "70"))
