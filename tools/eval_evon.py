"""Measure Evon (the real judge) on the held-out sentences, per language. Runs on our own GPU: no Gnani credits.

    py tools/eval_evon.py              # all 242 held-out sentences (about 30 minutes at ~7 s each)
    py tools/eval_evon.py --per-lang 4 # a quick sample: 4 per language

Reports Evon alone and Evon combined with the instant rules (what the app actually shows).
"""
import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import app, config, evon, rules  # noqa: E402
from tests import corpus, corpus_holdout  # noqa: E402

per_lang = int(sys.argv[sys.argv.index("--per-lang") + 1]) if "--per-lang" in sys.argv else None
rows = corpus_holdout.cases() + corpus_holdout.cases(corpus_holdout.HOLDOUT2)
if per_lang:
    seen = defaultdict(int)
    picked = []
    for r in rows:
        if seen[r[0]] < per_lang:
            picked.append(r)
            seen[r[0]] += 1
    rows = picked


async def main():
    if not evon.enabled():
        sys.exit("LLM_BASE_URL is not set: start Evon on the GPU box first.")
    stats = defaultdict(lambda: [0, 0, 0])  # lang -> [evon ok, combined ok, total]
    misses = []
    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        for i, (lang, text, label) in enumerate(rows, 1):
            try:
                v = await evon.analyze(client, text)
            except Exception as e:  # noqa: BLE001
                print(f"[{i}/{len(rows)}] Evon failed: {e}")
                continue
            combined = app.combined_risk(rules.scan(text)["score"], v)
            ok_e, ok_c = corpus.passes(label, v["risk"]), corpus.passes(label, combined)
            s = stats[lang]
            s[0] += ok_e
            s[1] += ok_c
            s[2] += 1
            if not ok_c:
                misses.append(f"{lang} [{label}] evon={v['risk']} combined={combined} {v['scam_type']}: {text}")
            print(f"[{i}/{len(rows)}] {lang:9} {label:6} evon={v['risk']:3} combined={combined:3} {'ok' if ok_c else 'MISS'}", flush=True)
    print("\n" + "\n".join(misses))
    print(f"\n{'language':10}{'Evon alone':>14}{'with rules':>14}")
    tot = [0, 0, 0]
    for lang, (e, c, n) in stats.items():
        print(f"{lang:10}{e:>9}/{n:<4}{c:>9}/{n:<4}")
        tot = [tot[0] + e, tot[1] + c, tot[2] + n]
    print(f"{'ALL':10}{tot[0]:>9}/{tot[2]:<4}{tot[1]:>9}/{tot[2]:<4}")
    print(f"\n{config.LLM_BASE_URL} | {time.perf_counter() - t0:.0f} s")


asyncio.run(main())
