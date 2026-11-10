# /brag plan: Saavdhan

## Rubric
- **What is it:** a live scam-call guard. Put a phone call on speaker; Saavdhan listens and warns you out loud, in your language, the moment it turns into fraud.
- **Who it's for:** families in India, and the parents and grandparents who get "digital arrest", KYC and OTP calls.
- **What sets it apart:** it works during the call, not after; it speaks the warning so nobody has to read a screen; ten Indian languages and Hinglish; built on three Gnani models (Prisma listens, Evon understands, Timbre speaks).
- **Most impressive claim:** "Hears the scam before you do." (the app's own headline). In the replayed call the alarm fires on "you are under digital arrest", before the caller asks for money.
- **Visual hook:** the verdict word turning green, amber, then red as a real Timbre-voiced scam call plays, and the whole screen flooding red: "धोखा है।"
- **Real UI to show:** the live app (verdict panel, transcript with highlighted phrases, dock), the full-screen alarm, the home page's three-model section and "Try a line".
- **Tone:** polished: calm, confident, long holds, soft fades. No emojis.
- **Share caption:** "A scam call, on speaker. Saavdhan hears it turn into fraud and says so out loud, in your language. Built on Gnani AI's Prisma, Evon and Timbre."

All numbers on screen are real outputs of this code on these lines (rules + Evon via the running server, Nov 9). The call audio is `samples/scam_call.wav`, made earlier with Gnani Timbre from a written script; its names (राजेश शर्मा) are fictional. No keys, URLs or personal data appear.

## Angle
The product proves itself: watch a scam call get caught live, then learn what did it.

## Format
1920x1080, 30 fps, 60 s (the user's request; the challenge's demo length). Music 100 BPM (beat 0.6 s, bar 2.4 s), D minor for the call, F major after; every cut on a beat.

## Storyboard
| # | Time | Scene | On screen | Audio |
|---|---|---|---|---|
| 1 The call | 0.0-14.4 | The live app, listening. Three caller lines play in Timbre's voice; the transcript streams in (grey partials, then final). Verdict: green सुरक्षित -> amber सावधान 55 after Evon ("Digital arrest. Claims to be police.") -> 62 -> red धोखा 77 on "digital arrest". Phrases underline. Slow push-in. | real app UI only | Caller voice; low Dm pad and a heartbeat pulse, ducked under the voice; riser into 14.4 |
| 2 The alarm | 14.4-24.0 | Red floods the screen from the bottom, as in the app: धोखा है। / This is a scam call: digital arrest. / the Hindi warning / Don't share any OTP, PIN or money. / Hang up and call 1930. Red recedes at the end. | the app's alarm screen | Low impact + two-note alert chime in key, heartbeat continues |
| 3a Claim | 24.0-26.4 | Paper. **Hears the scam before you do.** word by word | headline | Groove enters in F major |
| 3b Models | 26.4-36.0 | **Three Gnani models, one job.** Three columns rise one by one: सुनता है / Prisma listens; समझता है / Evon understands; बोलता है / Timbre speaks, each with a small live motif (streaming text, risk bar, voice bars) | home page section | Groove; soft pluck as each column lands |
| 4 Languages | 36.0-45.6 | **Ten Indian languages. Hinglish too.** Ten cards pop in on the beat: सावधान in each script (Saavdhan's own name) | verdict words from i18n.js | One bell per card, ascending pentatonic |
| 5 Try a line | 45.6-54.0 | **Say what a caller might say.** Typing "Aapka KYC aaj expire ho raha hai, OTP bata dijiye" -> धोखा 85, Asks for OTP / Block threat / KYC, Evon: Bank or KYC. Then "Beta, khana kha liya? Papa kaise hain?" -> सुरक्षित 0, Evon: no scam pattern | home page "Try a line" | Soft key ticks on 16ths; minor dyad on scam, major dyad on safe |
| 6 Close | 54.0-60.0 | **Next time the phone rings, keep Saavdhan open.** Then the mark सावधान Saavdhan, "Built on Gnani AI: Prisma, Evon, Timbre", "Already paid someone? Call 1930." Hold. | app's closing line | Drums out, F major swell, ring out |

Durations sum to 60.0 s. Every cut lands on a beat (14.4, 24.0, 26.4, 36.0, 45.6, 54.0). Readable lines hold at least 0.3 s per word once settled.
Poster: the red alarm screen, settled (about 20 s), or the red verdict panel with the transcript; pick from stills.
