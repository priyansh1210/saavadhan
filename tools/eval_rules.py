"""Score the instant scam check on the test sets, per language, and list every miss.

    py tools/eval_rules.py            # tuning sets: summary + misses
    py tools/eval_rules.py --quiet    # summary only
    py tools/eval_rules.py --holdout  # a held-out set only (--holdout2, --holdout3 for the others)
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import app, rules  # noqa: E402
from tests import corpus, corpus_holdout, corpus_multi  # noqa: E402

if "--holdout3" in sys.argv:
    rows = corpus_holdout.cases(corpus_holdout.HOLDOUT3)
elif "--holdout2" in sys.argv:
    rows = corpus_holdout.cases(corpus_holdout.HOLDOUT2)
elif "--holdout" in sys.argv:
    rows = corpus_holdout.cases()
else:
    rows = [("hinglish*", t, label) for t, label in corpus.CASES] + corpus_multi.cases()
stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))
misses = []
for lang, text, label in rows:
    r = rules.scan(text)
    live = app.combined_risk(r["score"], None)
    ok = corpus.passes(label, live)
    stats[lang][label][0 if ok else 1] += 1
    if not ok:
        misses.append((lang, label, live, [s["key"] for s in r["signs"]], text))

if "--quiet" not in sys.argv:
    for lang, label, live, keys, text in misses:
        print(f"MISS {lang:9} [{label:6}] live={live:3} {keys}\n     {text}")
    print()
labels = ("scam", "warn", "nowarn", "safe")
print(f"{'language':10}" + "".join(f"{x:>11}" for x in labels))
for lang, s in stats.items():
    print(f"{lang:10}" + "".join(f"{s[x][0]:>6}/{sum(s[x]):<4}" for x in labels))
tot = {x: [sum(stats[l][x][0] for l in stats), sum(sum(stats[l][x]) for l in stats)] for x in labels}
print(f"{'ALL':10}" + "".join(f"{tot[x][0]:>6}/{tot[x][1]:<4}" for x in labels))
hand = len(rows) if any(a.startswith("--holdout") for a in sys.argv) else corpus_multi.TEMPLATES + len(corpus.CASES)
print(f"\n{len(rows)} sentences ({hand} written by hand), {len(misses)} misses")
