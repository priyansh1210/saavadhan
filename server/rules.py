"""Instant, offline scam-sign detector for every language Saavdhan listens to.

It runs on every transcript line in about a millisecond, so the risk meter moves at once; Evon then
gives the deeper verdict. Each sign is either "any of these words" or "these two ideas close together
in one sentence" (money near "send it", "your son" near "arrested"), which works whatever the word
order: Hindi and Tamil put the verb last, English puts it first. The vocabulary is in lexicon.py.
Measured on tests/corpus.py and tests/corpus_multi.py.
"""
import re
from dataclasses import dataclass

from .lexicon import alt


@dataclass(frozen=True)
class Sign:
    key: str
    label: str      # shown in the UI
    label_hi: str
    weight: float   # 0..1, how strongly this alone suggests a scam
    pattern: re.Pattern


_END = r"[^.!?।\n]"  # stay inside one sentence


def near(a: str, b: str, gap: int = 45) -> str:
    """a and b within `gap` characters of each other, in either order, in the same sentence."""
    return f"(?:{a}){_END}{{0,{gap}}}?(?:{b})|(?:{b}){_END}{{0,{gap}}}?(?:{a})"


def _p(*parts: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in parts), re.IGNORECASE)


SIGNS: list[Sign] = [
    Sign("secret_code", "Asks for OTP / PIN / CVV", "OTP / PIN माँगना", 0.6, _p(
        alt("otp", "cvv"), near(alt("pin"), alt("tell"), 30),
        near(alt("back_of"), alt("digits"), 30),  # "the digits on the back of your card" is the CVV, in any language
    )),
    Sign("asks_number", "Asks for your card / account number", "कार्ड / खाते का नंबर माँगना", 0.5, _p(
        near(near(alt("account", "policy"), alt("digits"), 40), alt("tell", "confirm"), 40),
    )),
    Sign("extortion", "Threatens you unless you pay", "पैसे न देने पर धमकी", 0.55, _p(
        near(alt("money", "pay_verb"), alt("unless_paid"), 40),
    )),
    Sign("blackmail", "Claims to have your private photos / videos", "निजी वीडियो से ब्लैकमेल", 0.5, _p(alt("private_media"))),
    Sign("pin_receive", "PIN to \"receive\" money", "पैसे पाने के लिए PIN", 0.5, _p(
        r"\bpin\b.{0,40}(?:paise|paisa|money|rupa?y\w*|amount).{0,25}(?:aa\s?jayenge|aayenge|milenge|credit|receive)",
        r"पिन.{0,40}(?:पैसे|रुपये).{0,25}(?:आ\s?जाएंगे|मिलेंगे)",
    )),
    Sign("digital_arrest", "Arrest threat / \"digital arrest\"", "डिजिटल अरेस्ट / गिरफ़्तारी", 0.55, _p(
        alt("digital_arrest", "arrest"),
    )),
    Sign("family", "Says your family member is in trouble", "परिवार का कोई मुसीबत में", 0.5, _p(
        near(near(alt("your"), alt("relative"), 20), alt("trouble", "arrest", "authority"), 70), alt("release"),
    )),
    Sign("authority", "Claims to be police / CBI / bank / govt", "पुलिस / CBI / बैंक बनकर", 0.3, _p(alt("authority"))),
    Sign("legal_threat", "Threatens a case / FIR / court", "केस / FIR / कोर्ट की धमकी", 0.35, _p(alt("legal"))),
    Sign("pay_now", "Asks you to send money", "पैसे भेजने को कहना", 0.5, _p(
        near(alt("money"), alt("send"), 40), alt("fee"), near(alt("urgent"), alt("pay_verb"), 25),
        r"(?:turant|तुरंत|abhi)\s?(?:paise\s)?(?:transfer|ट्रांसफर|pay|पे|bhej|भेज)",
        r"(?:is|iss|this)\s?number\s?(?:pe|par|pr|on)\s?(?:\S+\s){0,3}?(?:pay|bhej|transfer|bhar)",
    )),
    Sign("secrecy", "Tells you to keep it secret / stay on the call", "किसी को न बताने / कॉल पर रहने को कहना", 0.4, _p(
        alt("secret", "stay_on"),
    )),
    Sign("remote_access", "Asks to install an app / share screen / click a link", "ऐप / स्क्रीन शेयर / लिंक", 0.55, _p(
        alt("remote"), near(alt("link"), alt("click", "send", "pay_verb"), 30), near(alt("app"), alt("install"), 20),
        r"link\s?bhej", r"लिंक\s?भेज",
    )),
    Sign("account_block", "Says your account / card / SIM / KYC will be blocked", "अकाउंट / कार्ड / सिम बंद होने की बात", 0.45, _p(
        near(alt("account", "id_doc"), alt("block"), 40),
    )),
    Sign("wrong_transfer", "\"Sent to you by mistake, send it back\"", "\"गलती से भेजे, वापस भेजो\"", 0.45, _p(
        near(alt("mistake"), alt("back"), 90),
    )),
    Sign("insurance_bait", "Insurance bonus / maturity bait", "बीमा बोनस का लालच", 0.35, _p(
        near(alt("policy"), alt("bonus"), 40),
    )),
    Sign("qr_scam", "QR code to \"receive\" money", "पैसे पाने के लिए QR", 0.75, _p(
        near(alt("qr"), alt("scan"), 40),
    )),
    Sign("id_doc", "Brings up KYC / Aadhaar / PAN", "KYC / आधार की बात", 0.25, _p(alt("id_doc"))),
    Sign("details", "Asks for your personal details", "आपकी जानकारी माँगना", 0.3, _p(
        near(alt("details"), alt("send", "tell", "confirm"), 30),
    )),
    Sign("parcel", "Parcel / courier / customs story", "पार्सल / कूरियर की कहानी", 0.3, _p(alt("parcel"))),
    Sign("prize", "Lottery / prize / refund / cashback bait", "लॉटरी / इनाम / रिफ़ंड का लालच", 0.35, _p(alt("prize"))),
    Sign("job_bait", "Job or work-from-home bait", "नौकरी का लालच", 0.35, _p(
        r"work\s?from\s?home", r"ghar\s?baithe", r"घर\s?बैठे", near(alt("job"), alt("money", "fee"), 40),
    )),
    Sign("invest_bait", "\"Double your money\" investment bait", "पैसा डबल का लालच", 0.4, _p(
        r"(?:paisa|paise|money)\s?double", r"guaranteed\s?(?:return|profit)", r"\blagao\b.{0,25}\bpao\b",
        r"trading\s?(?:tips|group)", r"\bcrypto\b", near(alt("double"), alt("money"), 30),
    )),
    Sign("utility", "Electricity / gas cut-off threat", "बिजली / गैस काटने की धमकी", 0.35, _p(
        alt("power"), alt("cut_off"),
    )),
]

# Pairs that are much stronger together than alone.
COMBOS = [
    ({"authority", "secrecy"}, 0.25),
    ({"digital_arrest", "secrecy"}, 0.2),
    ({"secret_code", "account_block"}, 0.3),
    ({"secret_code", "prize"}, 0.3),
    ({"secret_code", "authority"}, 0.2),
    ({"parcel", "authority"}, 0.15),
    ({"family", "pay_now"}, 0.35),
    ({"id_doc", "account_block"}, 0.2),
    ({"secret_code", "id_doc"}, 0.35),  # an Aadhaar OTP is never asked for on a genuine call
    ({"prize", "details"}, 0.25),
    ({"invest_bait", "secrecy"}, 0.25),
    ({"id_doc", "secrecy"}, 0.2),
    ({"insurance_bait", "details"}, 0.25),
    ({"wrong_transfer", "pay_now"}, 0.2),
    ({"blackmail", "extortion"}, 0.2),
]
# Almost every scam is "a demand plus a story": these add weight next to any other sign.
WITH_ANY = {"pay_now": 0.4, "remote_access": 0.3, "secrecy": 0.2, "extortion": 0.3}


def scan(text: str) -> dict:
    """Return {score: 0-100, signs: [{key,label,label_hi,weight,matches}]}."""
    found = []
    for s in SIGNS:
        matches = sorted({m.group(0).strip() for m in s.pattern.finditer(text)}, key=len, reverse=True)
        if matches:
            found.append({"key": s.key, "label": s.label, "label_hi": s.label_hi,
                          "weight": s.weight, "matches": matches[:6]})
    keys = {f["key"] for f in found}
    keep = 1.0
    for f in found:
        keep *= 1.0 - f["weight"]
    for combo, bonus in COMBOS:
        if combo <= keys:
            keep *= 1.0 - bonus
    for key, bonus in WITH_ANY.items():
        if key in keys and len(keys) > 1:
            keep *= 1.0 - bonus
    return {"score": round((1.0 - keep) * 100), "signs": found}
