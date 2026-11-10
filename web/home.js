"use strict";
const $ = (s) => document.querySelector(s);
const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
const hasGsap = typeof window.gsap !== "undefined";
const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const WORD = { idle: "तैयार", safe: "सुरक्षित", suspicious: "सावधान", scam: "धोखा" }; // the replay is a Hindi call, so it stays Hindi

// Everything else follows the language picked in the app (Hindi until one is picked).
const picked = savedLang();
setUiLang(picked && picked !== "indic-auto" ? picked : "hi");
document.querySelectorAll(".verb").forEach((v, i) => (v.textContent = L().verbs[i]));
const tWord = (verdict) => ({ idle: L().ready, safe: L().safe, suspicious: L().careful, scam: L().scam }[verdict]);
const showTWord = (verdict) => {
  const w = tWord(verdict);
  $("#t-word").textContent = w;
  fitText($("#t-word"));
};
showTWord("idle");

// ------------------------------------------------------------ hero: an example scam call, replayed
// Without JavaScript or GSAP, or with reduced motion, the static frame in the HTML stays as it is.
const SCRIPT = [
  { text: "Hello, मैं मुंबई crime branch से inspector राजेश शर्मा बोल रहा हूँ।", marks: ["crime branch"], state: "suspicious", risk: 35 },
  { text: "आपके आधार से एक पार्सल बुक हुआ है, उसमें ड्रग्स मिले हैं।", marks: ["पार्सल", "ड्रग्स"], state: "suspicious", risk: 62 },
  { text: "आप अभी digital arrest में हैं। यह बात किसी को भी मत बताइए।", marks: ["digital arrest", "किसी को भी मत बताइए"], state: "scam", risk: 91 },
  { text: "Safe account में तुरंत पैसे transfer कीजिए, और OTP बताइए।", marks: ["Safe account", "तुरंत पैसे transfer", "OTP"], state: "scam", risk: 100 },
];
const replay = $("#replay");

function markup(text, marks) {
  let html = esc(text);
  for (const m of marks) html = html.replace(esc(m), `<mark class="hl">${esc(m)}</mark>`);
  return html;
}
function setReplay(state, risk) {
  replay.dataset.state = state;
  $("#r-word").textContent = WORD[state];
  $("#r-bar").style.width = risk + "%";
  $("#r-num").textContent = risk;
}

function play() {
  const lines = $("#r-lines");
  lines.innerHTML = "";
  replay.classList.remove("done");
  $("#r-flood").classList.remove("on");
  $("#r-again").hidden = true;
  setReplay("idle", 0);
  const tl = gsap.timeline({ delay: 0.6 });
  SCRIPT.forEach((s) => {
    const p = document.createElement("p");
    p.innerHTML = markup(s.text, s.marks);
    tl.call(() => lines.appendChild(p))
      .fromTo(p, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" })
      .call(() => { p.querySelectorAll(".hl").forEach((m) => m.classList.add("on")); setReplay(s.state, s.risk); }, null, "+=0.5")
      .to({}, { duration: 1.5 }); // time to read the line before the next one
  });
  tl.call(() => { $("#r-flood").classList.add("on"); replay.classList.add("done"); })
    .call(() => ($("#r-again").hidden = false), null, "+=1.2");
}

if (hasGsap && !calm) {
  play();
  $("#r-again").onclick = play;
}

// ------------------------------------------------------------ headings reveal word by word
if (hasGsap && !calm && window.ScrollTrigger) {
  gsap.registerPlugin(ScrollTrigger);
  document.querySelectorAll(".split").forEach((el) => {
    const text = el.textContent.trim();
    el.setAttribute("aria-label", text); // screen readers get the whole sentence, not the pieces
    el.innerHTML = text.split(/\s+/).map((w) => `<span class="w" aria-hidden="true">${esc(w)}</span>`).join(" ");
    const words = el.querySelectorAll(".w");
    const anim = { opacity: 0, y: "0.35em", duration: 0.6, stagger: 0.045, ease: "power3.out" };
    if (el.tagName === "H1") gsap.from(words, { ...anim, delay: 0.1 });
    else gsap.from(words, { ...anim, scrollTrigger: { trigger: el, start: "top 85%", once: true } });
  });
  gsap.from(".lede, .hero-copy .ctas", { opacity: 0, y: 12, duration: 0.6, stagger: 0.1, delay: 0.45, ease: "power2.out" });
  gsap.from(".step", { opacity: 0, y: 18, duration: 0.6, stagger: 0.12, ease: "power2.out",
    scrollTrigger: { trigger: ".steps", start: "top 85%", once: true } });
}

// ------------------------------------------------------------ try a line (instant check, no credits)
const SHORT = {
  secret_code: "Asks for OTP", digital_arrest: "Arrest threat", authority: "Claims authority", legal_threat: "Case or FIR",
  pay_now: "Money pressure", secrecy: "Secrecy", remote_access: "App or link", account_block: "Block threat",
  parcel: "Parcel story", prize: "Prize bait", utility: "Bill cut-off", family: "Family in trouble", id_doc: "KYC / Aadhaar",
  details: "Asks for details", asks_number: "Asks card number", extortion: "Pay-or-else threat", blackmail: "Blackmail",
  wrong_transfer: "\"Sent by mistake\"", insurance_bait: "Insurance bonus", qr_scam: "QR to receive",
  pin_receive: "PIN to receive", job_bait: "Job bait", invest_bait: "Money-double bait",
};
const box = $("#line");
let timer = null;
let seq = 0;

async function check() {
  const text = box.value.trim();
  const out = $("#try-out");
  if (!text) {
    out.dataset.state = "idle";
    showTWord("idle");
    $("#t-bar").style.width = "0%";
    $("#t-num").textContent = "0";
    $("#t-signs").textContent = "";
    return;
  }
  const mine = ++seq;
  try {
    const r = await fetch("/api/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    const d = await r.json();
    if (mine !== seq) return; // a newer keystroke already asked
    show(d);
    clearTimeout(judgeTimer);
    judgeTimer = setTimeout(() => askEvon(text, mine), 700); // then a second opinion once typing pauses
  } catch {
    $("#t-signs").textContent = "The Saavdhan server isn't running, so this box can't check lines right now.";
  }
}

function show(d, evonLine) {
  const out = $("#try-out");
  out.dataset.state = d.verdict;
  showTWord(d.verdict);
  $("#t-bar").style.width = d.risk + "%";
  $("#t-num").textContent = d.risk;
  const signs = d.signs.map((s) => `<i>${esc(SHORT[s.key] || s.label)}</i>`).join(" ");
  $("#t-signs").innerHTML = (evonLine ? `<b class="t-evon">${esc(evonLine)}</b> ` : "") + (signs || (evonLine ? "" : "No scam signs in this line."));
}

// Evon understands scam stories the instant word list has never seen. If it's offline, the instant result stands.
let judgeTimer = null;
async function askEvon(text, mine) {
  try {
    const r = await fetch("/api/judge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    if (!r.ok || mine !== seq) return;
    const d = await r.json();
    if (mine !== seq) return;
    const e = d.evon;
    const label = e.scam_type && e.scam_type !== "None" ? e.scam_type : "";
    show(d, label ? `Evon: ${label}` : "Evon: no scam pattern");
  } catch { /* instant result stands */ }
}

box.addEventListener("input", () => {
  document.querySelectorAll("#examples button").forEach((b) => b.classList.remove("on"));
  clearTimeout(timer);
  timer = setTimeout(check, 250);
});
document.querySelectorAll("#examples button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#examples button").forEach((x) => x.classList.toggle("on", x === b));
    box.value = b.textContent;
    check();
  };
});
