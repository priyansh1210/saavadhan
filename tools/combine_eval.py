"""Compare ways of combining Evon with the instant rules, offline, from Evon's saved answers.

    py tools/combine_eval.py                # needs tests/evon_cache.json (tools/evon_cache.py)
    py tools/combine_eval.py --why "name"   # list the sentences one policy gets wrong

Only answers from the current prompt are used, and rules are re-run live. Sets:
  unseen-3   HOLDOUT3, never used for tuning anything: how well each policy handles new scam types
  unseen-1,2 HOLDOUT and HOLDOUT2: the rules were tuned on these after their first run, so they show
             whether a policy lets Evon drag down an alarm the rules got right
  harmless   every safe / nowarn sentence: any alarm here is a false alarm
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import app, evon, rules  # noqa: E402
from tests import corpus, corpus_holdout  # noqa: E402

PROMPT_ID = hashlib.sha1((evon.SYSTEM_PROMPT + json.dumps(evon.SCHEMA)).encode()).hexdigest()[:10]
cache = json.loads((ROOT / "tests" / "evon_cache.json").read_text(encoding="utf-8"))
unseen3 = {t for _, t, _ in corpus_holdout.cases(corpus_holdout.HOLDOUT3)}
unseen12 = {t for _, t, _ in corpus_holdout.cases() + corpus_holdout.cases(corpus_holdout.HOLDOUT2)}


def group(text, label):
    if label in ("safe", "nowarn"):
        return "harmless"
    return "unseen-3" if text in unseen3 else "unseen-1,2" if text in unseen12 else None


def r9(r):
    return round(r * 0.9)


POLICIES = {
    "rules only": lambda r, e: r9(r),
    "Evon only": lambda r, e: e["risk"],
    "max of both": lambda r, e: max(e["risk"], r9(r)),
    "Evon alarms only with a sign": lambda r, e: max(r9(r), e["risk"] if r > 0 else min(e["risk"], 69)),
    "Evon alarms only if rules >= 25": lambda r, e: max(r9(r), e["risk"] if r >= 25 else min(e["risk"], 69)),
    "Evon alone max 60, with a sign free": lambda r, e: max(r9(r), e["risk"] if r > 0 else min(e["risk"], 60)),
    "Evon never alarms, max 69": lambda r, e: max(r9(r), min(e["risk"], 69)),
    "app.combined_risk (in code now)": lambda r, e: app.combined_risk(r, e),
}

rows = []
for text, c in cache.items():
    g = group(text, c["label"])
    if g and c.get("prompt") == PROMPT_ID:
        e = {"risk": c["evon_risk"], "gist": c.get("gist", "")}
        rows.append((g, c["label"], c["lang"], text, rules.scan(text)["score"], e, c))

counts = defaultdict(int)
for g, label, *_ in rows:
    counts[(g, label)] += 1
cols = [("unseen-3", "scam"), ("unseen-3", "warn"), ("unseen-1,2", "scam"), ("unseen-1,2", "warn"),
        ("harmless", "nowarn"), ("harmless", "safe")]
print(f"prompt {PROMPT_ID}: {len(rows)} answers.  Pass counts (harmless columns count no false alarm):\n")
print(f"{'policy':36}" + "".join(f"{g[:10] + ' ' + l:>18}" for g, l in cols))
for name, f in POLICIES.items():
    ok = defaultdict(int)
    for g, label, lang, text, r, e, c in rows:
        ok[(g, label)] += corpus.passes(label, f(r, e))
    print(f"{name:36}" + "".join(f"{ok[k]:>12}/{counts[k]:<5}" for k in cols))

# The same policies in plain terms: an alarm (>= 70) is red and spoken aloud; "careful" (35-69) is amber and silent.
print(f"\n{'policy':36}{'new scams alarmed':>19}{'new scams >= careful':>22}{'known scams alarmed':>21}"
      f"{'harmless alarmed':>18}{'safe lines amber':>18}")
for name, f in POLICIES.items():
    n = defaultdict(int)
    for g, label, lang, text, r, e, c in rows:
        live = f(r, e)
        if g == "unseen-3" and label == "scam":
            n["a3"] += live >= 70
            n["c3"] += live >= 35
        elif g == "unseen-1,2" and label == "scam":
            n["a12"] += live >= 70
        elif g == "harmless":
            n["fa"] += live >= 70
            n["amber"] += label == "safe" and 35 <= live < 70
    print(f"{name:36}{n['a3']:>13}/{counts[('unseen-3', 'scam')]:<5}{n['c3']:>16}/{counts[('unseen-3', 'scam')]:<5}"
          f"{n['a12']:>15}/{counts[('unseen-1,2', 'scam')]:<5}"
          f"{n['fa']:>12}/{counts[('harmless', 'nowarn')] + counts[('harmless', 'safe')]:<5}"
          f"{n['amber']:>12}/{counts[('harmless', 'safe')]:<5}")

if "--why" in sys.argv:
    name = sys.argv[sys.argv.index("--why") + 1]
    f = POLICIES[name]
    print(f"\nMisses for {name!r}:")
    for g, label, lang, text, r, e, c in rows:
        live = f(r, e)
        if not corpus.passes(label, live):
            print(f"  {g:10} [{label:6}] {lang:9} rules={r:3} evon={e['risk']:3} {e['gist'][:40]:40} "
                  f"live={live:3}  {text[:80]}")
