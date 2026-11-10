"""Run Evon once on the held-out scams and on every harmless sentence, and save the answers, so different
ways of combining Evon with the instant rules can be compared offline (tools/combine_eval.py).

    py tools/evon_cache.py          # all ~670 sentences, ~10 minutes with 4 parallel requests
    py tools/evon_cache.py --dev    # only the tuning slice (Hinglish, Hindi, English; never HOLDOUT3)

Each answer remembers a fingerprint of the prompt that produced it; changing the prompt re-asks.
"""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import evon, rules  # noqa: E402
from tests import corpus, corpus_holdout, corpus_multi  # noqa: E402

OUT = ROOT / "tests" / "evon_cache.json"
DEV_LANGS = {"hinglish*", "hinglish", "hi", "en"}
PROMPT_ID = hashlib.sha1((evon.SYSTEM_PROMPT + json.dumps(evon.SCHEMA)).encode()).hexdigest()[:10]

rows = corpus_holdout.cases() + corpus_holdout.cases(corpus_holdout.HOLDOUT2)
held3 = corpus_holdout.cases(corpus_holdout.HOLDOUT3)
rows += [("hinglish*", t, l) for t, l in corpus.CASES if l in ("safe", "nowarn")]
rows += [r for r in corpus_multi.cases() if r[2] in ("safe", "nowarn")]
if "--dev" in sys.argv:
    rows = [r for r in rows if r[0] in DEV_LANGS]
else:
    rows += held3


async def main():
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [r for r in rows if cache.get(r[1], {}).get("prompt") != PROMPT_ID]
    print(f"prompt {PROMPT_ID}: {len(rows)} sentences, {len(todo)} to ask Evon", flush=True)
    t0, done, sem = time.perf_counter(), 0, asyncio.Semaphore(4)  # the Kaggle server has 4 slots

    async def ask(client, lang, text, label):
        nonlocal done
        async with sem:
            try:
                v = await evon.analyze(client, text)
            except Exception as e:  # noqa: BLE001
                print(f"failed: {e}", flush=True)
                return
        r = rules.scan(text)
        cache[text] = {"lang": lang, "label": label, "prompt": PROMPT_ID, "rules_score": r["score"],
                       "rules_signs": [s["key"] for s in r["signs"]], "evon_risk": v["risk"],
                       "evon_verdict": v["verdict"], "gist": v.get("gist", ""), "scam_type": v["scam_type"]}
        done += 1
        if done % 50 == 0:
            OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
            print(f"[{done}/{len(todo)}] {time.perf_counter() - t0:.0f} s", flush=True)

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=8)) as client:
        await asyncio.gather(*(ask(client, *r) for r in todo))
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"saved {len(cache)} answers to {OUT} in {time.perf_counter() - t0:.0f} s")


asyncio.run(main())
