"use strict";
// The words Saavdhan shows in the call's own language. English UI copy stays English;
// these are the large verdict words, the alarm, the three verbs and the scam names.
// Serif per script: Tiro where Google Fonts has one, Noto Serif for Gujarati and Malayalam.
const LANGS = {
  hi: { font: "Tiro Devanagari Hindi", ready: "तैयार", check: "जाँच", safe: "सुरक्षित", careful: "सावधान", scam: "धोखा", alarm: "धोखा है।",
    verbs: ["सुनता है", "समझता है", "बोलता है"],
    scams: ["डिजिटल अरेस्ट", "केवाईसी अपडेट", "स्क्रीन शेयर", "इनाम या रिफ़ंड", "बिजली कनेक्शन", "किसी को मत बताना"] },
  mr: { font: "Tiro Devanagari Marathi", ready: "तयार", check: "तपासणी", safe: "सुरक्षित", careful: "सावधान", scam: "फसवणूक", alarm: "फसवणूक आहे.",
    verbs: ["ऐकतो", "समजतो", "बोलतो"],
    scams: ["डिजिटल अरेस्ट", "केवायसी अपडेट", "स्क्रीन शेअर", "बक्षीस किंवा रिफंड", "वीज कनेक्शन", "कोणाला सांगू नका"] },
  gu: { font: "Noto Serif Gujarati", ready: "તૈયાર", check: "તપાસ", safe: "સુરક્ષિત", careful: "સાવધાન", scam: "છેતરપિંડી", alarm: "છેતરપિંડી છે.",
    verbs: ["સાંભળે છે", "સમજે છે", "બોલે છે"],
    scams: ["ડિજિટલ અરેસ્ટ", "કેવાયસી અપડેટ", "સ્ક્રીન શેર", "ઇનામ કે રિફંડ", "વીજળી કનેક્શન", "કોઈને કહેશો નહીં"] },
  pa: { font: "Tiro Gurmukhi", ready: "ਤਿਆਰ", check: "ਜਾਂਚ", safe: "ਸੁਰੱਖਿਅਤ", careful: "ਸਾਵਧਾਨ", scam: "ਧੋਖਾ", alarm: "ਧੋਖਾ ਹੈ।",
    verbs: ["ਸੁਣਦਾ ਹੈ", "ਸਮਝਦਾ ਹੈ", "ਬੋਲਦਾ ਹੈ"],
    scams: ["ਡਿਜੀਟਲ ਅਰੈਸਟ", "ਕੇਵਾਈਸੀ ਅੱਪਡੇਟ", "ਸਕ੍ਰੀਨ ਸ਼ੇਅਰ", "ਇਨਾਮ ਜਾਂ ਰਿਫੰਡ", "ਬਿਜਲੀ ਕੁਨੈਕਸ਼ਨ", "ਕਿਸੇ ਨੂੰ ਨਾ ਦੱਸੋ"] },
  bn: { font: "Tiro Bangla", ready: "প্রস্তুত", check: "যাচাই", safe: "নিরাপদ", careful: "সাবধান", scam: "প্রতারণা", alarm: "এটা প্রতারণা।",
    verbs: ["শোনে", "বোঝে", "বলে"],
    scams: ["ডিজিটাল অ্যারেস্ট", "কেওয়াইসি আপডেট", "স্ক্রিন শেয়ার", "পুরস্কার বা রিফান্ড", "বিদ্যুৎ সংযোগ", "কাউকে বলবেন না"] },
  ta: { font: "Tiro Tamil", ready: "தயார்", check: "சரிபார்ப்பு", safe: "பாதுகாப்பு", careful: "கவனம்", scam: "மோசடி", alarm: "இது மோசடி.",
    verbs: ["கேட்கிறது", "புரிந்துகொள்கிறது", "பேசுகிறது"],
    scams: ["டிஜிட்டல் அரெஸ்ட்", "கேஒய்சி அப்டேட்", "ஸ்கிரீன் ஷேர்", "பரிசு அல்லது ரீஃபண்ட்", "மின் இணைப்பு", "யாரிடமும் சொல்லாதீர்கள்"] },
  te: { font: "Tiro Telugu", ready: "సిద్ధం", check: "తనిఖీ", safe: "సురక్షితం", careful: "జాగ్రత్త", scam: "మోసం", alarm: "ఇది మోసం.",
    verbs: ["వింటుంది", "అర్థం చేసుకుంటుంది", "మాట్లాడుతుంది"],
    scams: ["డిజిటల్ అరెస్ట్", "కేవైసీ అప్‌డేట్", "స్క్రీన్ షేర్", "బహుమతి లేదా రీఫండ్", "కరెంట్ కనెక్షన్", "ఎవరికీ చెప్పకండి"] },
  kn: { font: "Tiro Kannada", ready: "ಸಿದ್ಧ", check: "ಪರಿಶೀಲನೆ", safe: "ಸುರಕ್ಷಿತ", careful: "ಎಚ್ಚರಿಕೆ", scam: "ವಂಚನೆ", alarm: "ಇದು ವಂಚನೆ.",
    verbs: ["ಕೇಳುತ್ತದೆ", "ಅರ್ಥಮಾಡಿಕೊಳ್ಳುತ್ತದೆ", "ಮಾತನಾಡುತ್ತದೆ"],
    scams: ["ಡಿಜಿಟಲ್ ಅರೆಸ್ಟ್", "ಕೆವೈಸಿ ಅಪ್‌ಡೇಟ್", "ಸ್ಕ್ರೀನ್ ಶೇರ್", "ಬಹುಮಾನ ಅಥವಾ ರೀಫಂಡ್", "ವಿದ್ಯುತ್ ಸಂಪರ್ಕ", "ಯಾರಿಗೂ ಹೇಳಬೇಡಿ"] },
  ml: { font: "Noto Serif Malayalam", ready: "തയ്യാർ", check: "പരിശോധന", safe: "സുരക്ഷിതം", careful: "ശ്രദ്ധിക്കുക", scam: "തട്ടിപ്പ്", alarm: "ഇത് തട്ടിപ്പാണ്.",
    verbs: ["കേൾക്കുന്നു", "മനസ്സിലാക്കുന്നു", "സംസാരിക്കുന്നു"],
    scams: ["ഡിജിറ്റൽ അറസ്റ്റ്", "കെവൈസി അപ്ഡേറ്റ്", "സ്ക്രീൻ ഷെയർ", "സമ്മാനം അല്ലെങ്കിൽ റീഫണ്ട്", "വൈദ്യുതി കണക്ഷൻ", "ആരോടും പറയരുത്"] },
  en: { font: "Tiro Devanagari Hindi", ready: "Ready", check: "Check", safe: "Safe", careful: "Careful", scam: "Scam", alarm: "It's a scam.",
    verbs: ["Listens", "Understands", "Speaks"], scams: ["", "", "", "", "", ""] },
};

// "gu-IN,hi-IN" -> "gu"; anything unknown -> Hindi.
const langOf = (code) => { const l = String(code || "").slice(0, 2); return LANGS[l] ? l : "hi"; };

let uiLang = "hi";
const loadedFonts = new Set(["Tiro Devanagari Hindi"]);

function setUiLang(code) {
  uiLang = langOf(code);
  const font = LANGS[uiLang].font;
  if (!loadedFonts.has(font)) { // fetch a script's serif only when that language is picked
    loadedFonts.add(font);
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${font.replace(/ /g, "+")}&display=swap`;
    document.head.appendChild(link);
  }
  // --script styles only the translated words; English headlines keep --serif.
  document.documentElement.style.setProperty("--script", `"${font}", "Tiro Devanagari Hindi", Georgia, serif`);
  // Only the translated words carry the language; the rest of the page stays English for screen readers.
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.lang = uiLang));
  return LANGS[uiLang];
}
const L = () => LANGS[uiLang];

// Scripts differ a lot in width (Tamil "கவனம்" is wider than Hindi "सावधान"), so measure instead of guessing:
// shrink the word until it fits on one line, and only let it wrap if it still doesn't fit at the minimum size.
function fitText(el, min = 40) {
  el.style.fontSize = "";
  el.style.whiteSpace = "nowrap";
  let size = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollWidth > el.clientWidth + 1 && size > min) {
    size -= 4;
    el.style.fontSize = size + "px";
  }
  if (el.scrollWidth > el.clientWidth + 1) el.style.whiteSpace = "normal";
}
const fitAll = () => document.querySelectorAll("[data-fit]").forEach((el) => fitText(el));
document.fonts && document.fonts.addEventListener("loadingdone", fitAll); // re-measure once a script's font arrives
addEventListener("resize", fitAll);

// Remember the choice so the home page and the next visit use it. Storage can be blocked; that's fine.
function savedLang() { try { return localStorage.getItem("saavdhan-lang"); } catch { return null; } }
function saveLang(v) { try { localStorage.setItem("saavdhan-lang", v); } catch { /* private mode */ } }
