"""Send a recording to a running Saavdhan server and print what it found.

    py tools/check_file.py samples/scam_call_phone.wav [http://localhost:8000]
"""
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
with open(path, "rb") as f:
    r = httpx.post(f"{base}/api/analyze", files={"file": (path, f, "audio/wav")},
                   data={"langs": "hi-IN,en-IN"}, timeout=180)
d = r.json()
if r.status_code != 200:
    sys.exit(f"ERROR {r.status_code}: {d}")
for s in d["segments"]:
    print(f"[{s['start']:>4.0f}s] rule={s['rule_score']:>3} {s.get('language')}  {s['text'] or s.get('error')}")
print(f"\nRISK {d['risk']} -> {d['verdict'].upper()}")
print("signs:", ", ".join(x["label"] for x in d["rules"]["signs"]) or "none")
if d["evon"]:
    e = d["evon"]
    print(f"Evon ({e['latency_ms']} ms): {e['risk']} {e['verdict']} | {e['scam_type']} | {e['explanation']}")
    for fl in e["red_flags"]:
        print(f"   - \"{fl['quote']}\": {fl['reason']}")
    print("   warning:", e["warning"])
else:
    print("Evon:", d["evon_error"] or "not connected")
print("spoken warning:", d["warning"])
