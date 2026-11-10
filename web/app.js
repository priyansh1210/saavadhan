"use strict";
const $ = (s) => document.querySelector(s);

// ---------------------------------------------------------------- helpers
function toast(text, error = false, ms = 4500) {
  const t = $("#toast");
  t.textContent = text;
  t.className = "toast" + (error ? " error" : "");
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), ms);
}
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const stripTags = (s) => s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function highlight(text, phrases) {
  const list = [...new Set(phrases.filter((p) => p && p.length > 1))].sort((a, b) => b.length - a.length);
  if (!list.length) return esc(text);
  const re = new RegExp(list.map(reEsc).join("|"), "gi");
  let out = "", last = 0, m;
  while ((m = re.exec(text))) {
    out += esc(text.slice(last, m.index)) + "<mark>" + esc(m[0]) + "</mark>";
    last = m.index + m[0].length;
    if (!m[0].length) re.lastIndex++;
  }
  return out + esc(text.slice(last));
}

// ---------------------------------------------------------------- verdict panel: one per page
// Live call and Recording do different jobs, so each keeps its own panel and idle words.
// The big word is in the call's language (i18n.js); the line under it stays English.
const SAY = {
  safe: "Sounds safe so far.",
  suspicious: "Be careful. Don't share anything yet.",
  scam: "This is a scam call. Hang up.",
};
const IDLE = { live: "Put the call on speaker, then tap Listen.", file: "Drop a call recording to check it." };
const wordFor = (mode, state) =>
  state === "idle" ? (mode === "live" ? L().ready : L().check) : { safe: L().safe, suspicious: L().careful, scam: L().scam }[state];
const SHORT = { // one or two words per sign, so the panel stays quiet
  secret_code: "Asks for OTP", digital_arrest: "Arrest threat", authority: "Claims authority", legal_threat: "Case or FIR",
  pay_now: "Money pressure", secrecy: "Secrecy", remote_access: "App or link", account_block: "Block threat",
  parcel: "Parcel story", prize: "Prize bait", utility: "Bill cut-off", family: "Family in trouble", id_doc: "KYC / Aadhaar",
  details: "Asks for details", asks_number: "Asks card number", extortion: "Pay-or-else threat", blackmail: "Blackmail",
  wrong_transfer: "\"Sent by mistake\"", insurance_bait: "Insurance bonus", qr_scam: "QR to receive",
  pin_receive: "PIN to receive", job_bait: "Job bait", invest_bait: "Money-double bait",
};

const fresh = (mode) => ({ risk: 0, state: "idle", say: IDLE[mode], signs: "", evon: "", evonCls: "evon" });
const panels = { live: fresh("live"), file: fresh("file") };
let tab = "live";

function render(mode) {
  if (mode !== tab) return; // the other page's panel updates quietly and shows when you switch back
  const p = panels[mode];
  const word = $("#verdict");
  const text = wordFor(mode, p.state);
  if (word.textContent !== text) {
    word.textContent = text;
    fitText(word);
    word.classList.remove("swap");
    void word.offsetWidth; // restart the settle animation
    word.classList.add("swap");
  }
  document.body.dataset.state = p.state;
  $("#verdict-en").textContent = p.say;
  $("#risk-bar").style.width = p.risk + "%";
  $("#risk-num").textContent = p.risk;
  $("#signs").innerHTML = p.signs;
  const box = $("#evon-text");
  box.className = p.evonCls;
  box.innerHTML = p.evon;
}

function setRisk(mode, risk, state, say) {
  const p = panels[mode];
  Object.assign(p, { risk, state, say: say || (state === "idle" ? IDLE[mode] : SAY[state]) });
  render(mode);
}

function setSigns(mode, signs) {
  // the space between items lets the row wrap
  panels[mode].signs = signs.map((s) => `<i>${esc(SHORT[s.key] || s.label)}</i>`).join(" ");
  render(mode);
}

function setEvon(mode, e, { state, waiting } = {}) {
  const p = panels[mode];
  if (state) pill("evon", { thinking: null, ok: "ok", error: "bad", off: null }[state]);
  if (state === "thinking" && !e && !p.evon) Object.assign(p, { evonCls: "evon thinking", evon: "Evon is reading the call…" });
  if (waiting !== undefined) Object.assign(p, { evonCls: "evon", evon: esc(waiting) });
  else if (e) {
    const label = e.scam_type && e.scam_type !== "None" ? e.scam_type : "";
    const why = e.explanation || (e.partial ? "" : "No scam pattern so far.");
    Object.assign(p, { evonCls: "evon", evon: `<b>Evon:</b> ${label ? esc(label) + (why ? ". " : "") : ""}${esc(why)}` });
  }
  render(mode);
}

function resetPanel(mode, say, state = "idle") {
  panels[mode] = fresh(mode);
  setRisk(mode, 0, state, say);
}

// ---------------------------------------------------------------- model status (footer)
async function health() {
  try {
    const h = await (await fetch("/api/health")).json();
    pill("prisma", h.gnani_key ? "ok" : "bad");
    pill("timbre", h.gnani_key ? "ok" : "bad");
    pill("evon", h.evon_up ? "ok" : h.evon_configured ? "bad" : null);
    if (!h.gnani_key) toast("Add GNANI_API_KEY to the .env file and restart the server.", true, 8000);
  } catch {
    toast("The Saavdhan server is not reachable.", true);
  }
}
function pill(k, state) {
  const p = document.querySelector(`.model[data-k="${k}"]`);
  if (!p || state === undefined) return;
  p.classList.toggle("bad", state === "bad");
  p.title = state === "bad" ? "Not reachable right now" : "";
}

// ---------------------------------------------------------------- alarm + audio
let warnAudio = null;
let speaking = false;
function showAlarm(text, type) {
  $("#alarm-title").textContent = L().alarm;
  $("#alarm").hidden = false;
  fitText($("#alarm-title"), 48); // measured after it's visible
  $("#alarm-text").textContent = stripTags(text || "").replace(/^[^\s!]+!\s*/, ""); // the heading already says "careful"
  $("#alarm-type").textContent = type && type !== "None" ? `: ${type.toLowerCase()}` : "";
  $("#alarm").hidden = false;
  $("#alarm-close").focus();
  if (navigator.vibrate) navigator.vibrate([400, 150, 400, 150, 400]);
}
function playWav(blob) {
  if (warnAudio) warnAudio.pause();
  warnAudio = new Audio(URL.createObjectURL(blob));
  speaking = true;
  warnAudio.onended = warnAudio.onerror = () => (speaking = false);
  warnAudio.play().catch(() => { speaking = false; toast("Tap 'Hear the warning again' to play it."); });
}
function b64ToBlob(b64) {
  const bin = atob(b64);
  const u8 = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  return new Blob([u8], { type: "audio/wav" });
}
$("#alarm-close").onclick = () => { $("#alarm").hidden = true; };
$("#alarm-replay").onclick = () => { if (warnAudio) { warnAudio.currentTime = 0; speaking = true; warnAudio.play(); } };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#alarm").hidden = true; });

// ---------------------------------------------------------------- navigation
function openTab(name) {
  tab = name;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
  document.body.classList.toggle("learn", name === "learn");
  if (panels[name]) render(name);
  history.replaceState(null, "", name === "live" ? location.pathname : "#" + name);
}
document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => openTab(b.dataset.tab)));
const chosenLangs = () => $("#langs").value;

// Language: the big words, alarm and scam names follow the call's language.
function applyLang(code) {
  setUiLang(code);
  document.querySelectorAll(".scams dt span").forEach((s, i) => (s.textContent = L().scams[i]));
  if (panels[tab]) render(tab);
}
const remembered = savedLang();
if (remembered && [...$("#langs").options].some((o) => o.value === remembered)) $("#langs").value = remembered;
applyLang(chosenLangs() === "indic-auto" ? "hi" : chosenLangs());
$("#langs").onchange = () => {
  saveLang(chosenLangs());
  applyLang(chosenLangs() === "indic-auto" ? "hi" : chosenLangs());
};

// ---------------------------------------------------------------- LIVE
const live = { ws: null, ctx: null, stream: null, node: null, lines: [], phrases: [], partial: "", start: 0, timer: null,
  scamType: "", last: null, active: false };

function renderTranscript() {
  const box = $("#transcript");
  if (!live.lines.length && !live.partial) return;
  box.innerHTML = live.lines.map((l) => `<p>${highlight(l, live.phrases)}</p>`).join("") +
    (live.partial ? `<p class="partial">${esc(live.partial)}</p>` : "");
  box.scrollTop = box.scrollHeight;
}

function onLiveMessage(m) {
  switch (m.type) {
    case "connected":
      $("#mic-label").textContent = "Listening";
      pill("prisma", "ok");
      break;
    case "partial":
      live.partial = m.text;
      renderTranscript();
      break;
    case "transcript":
      live.partial = "";
      live.lines.push(m.text);
      // "Detect language": switch the big words to whatever Prisma hears.
      if (chosenLangs() === "indic-auto" && m.language && langOf(m.language) !== uiLang) applyLang(m.language);
      renderTranscript();
      break;
    case "risk":
      live.last = { risk: m.risk, verdict: m.verdict };
      setRisk("live", m.risk, m.verdict);
      setSigns("live", m.rules.signs);
      live.phrases = m.rules.signs.flatMap((s) => s.matches).concat((m.evon?.red_flags || []).map((f) => f.quote));
      if (m.evon) {
        setEvon("live", m.evon);
        live.scamType = m.evon.scam_type && m.evon.scam_type !== "None" ? m.evon.scam_type : live.scamType;
      }
      renderTranscript();
      break;
    case "evon":
      setEvon("live", null, { state: m.state });
      if (m.state === "off") setEvon("live", null, { waiting: "" });
      break;
    case "warning":
      showAlarm(m.text, live.scamType);
      break;
    case "warning_audio":
      playWav(b64ToBlob(m.audio));
      break;
    case "notice":
      toast(m.text, m.level === "error", 7000);
      break;
  }
}

async function startLive() {
  Object.assign(live, { lines: [], phrases: [], partial: "", scamType: "", last: null, active: true });
  setLiveUI(true);
  $("#transcript").innerHTML = '<p class="hint">Connecting…</p>';
  resetPanel("live", "Listening. Keep the phone on speaker, close to this device.", "safe");

  try {
    live.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: true },
    });
  } catch (e) {
    toast("Saavdhan needs the microphone to listen to the call.", true);
    stopLive();
    return;
  }
  if (!live.active) { stopLive(); return; } // stopped while the permission prompt was open
  live.ctx = new AudioContext();
  await live.ctx.audioWorklet.addModule("pcm-worklet.js");
  if (!live.active) { stopLive(); return; }
  const src = live.ctx.createMediaStreamSource(live.stream);
  live.node = new AudioWorkletNode(live.ctx, "pcm16k");
  const sink = live.ctx.createGain();
  sink.gain.value = 0;
  src.connect(live.node).connect(sink).connect(live.ctx.destination);

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live?langs=${encodeURIComponent(chosenLangs())}`);
  ws.binaryType = "arraybuffer";
  live.ws = ws;
  const silence = new Int16Array(512).buffer;
  const mic = $("#mic");
  live.node.port.onmessage = (e) => {
    if (e.data && e.data.level !== undefined) {
      mic.style.setProperty("--lvl", Math.min(1, e.data.level * 2.2).toFixed(2)); // the ring shows the real input level
      return;
    }
    // While our own warning plays, send silence so Saavdhan doesn't transcribe itself.
    if (ws.readyState === 1) ws.send(speaking ? silence : e.data);
  };
  ws.onmessage = (e) => onLiveMessage(JSON.parse(e.data));
  ws.onclose = () => { if (live.ws === ws) stopLive(false); };
  ws.onerror = () => toast("Lost the connection to the Saavdhan server.", true);

  live.start = Date.now();
  live.timer = setInterval(() => ($("#timer").textContent = fmt((Date.now() - live.start) / 1000)), 500);
}

function setLiveUI(on) {
  const mic = $("#mic");
  mic.classList.toggle("on", on);
  mic.setAttribute("aria-label", on ? "Stop listening" : "Start listening");
  mic.style.setProperty("--lvl", 0);
  $("#mic-label").textContent = on ? "Connecting" : "Listen";
  $("#timer").textContent = "";
  $("#langs").disabled = on;
}

function stopLive(sendStop = true) {
  live.active = false;
  const ws = live.ws;
  live.ws = null;
  if (ws) {
    if (ws.readyState === WebSocket.OPEN && sendStop) {
      ws.send(JSON.stringify({ type: "stop" })); // let Prisma finish the last sentence, then close
      setTimeout(() => ws.close(), 2500);
    } else if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
  }
  if (live.stream) live.stream.getTracks().forEach((t) => t.stop());
  if (live.ctx) live.ctx.close();
  live.stream = live.ctx = live.node = null;
  live.partial = "";
  clearInterval(live.timer);
  setLiveUI(false);
  if (!live.lines.length) {
    $("#transcript").innerHTML = '<p class="hint">Nothing was heard. Put the call on speaker and tap Listen again.</p>';
    resetPanel("live");
  } else {
    renderTranscript();
    const r = live.last || { risk: 0, verdict: "safe" };
    setRisk("live", r.risk, r.verdict, r.verdict === "safe" ? "Call ended. It sounded safe." : undefined);
  }
  health(); // put the model status back to its real state
}

$("#mic").onclick = () => (live.active ? stopLive() : startLive());

// ---------------------------------------------------------------- RECORDING
let chosen = null;
let report = null;
const drop = $("#drop");
$("#pick").onclick = () => $("#file").click();
$("#file").onchange = (e) => choose(e.target.files[0]);
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); choose(e.dataTransfer.files[0]); };
function choose(f) {
  if (!f) return;
  chosen = f;
  $("#file-name").textContent = `${f.name}, ${(f.size / 1e6).toFixed(1)} MB`;
  $("#analyze").disabled = false;
}

$("#analyze").onclick = async () => {
  if (!chosen) return;
  $("#analyze").disabled = true;
  $("#result").hidden = true;
  $("#loading").hidden = false;
  resetPanel("file", "Checking the recording…");
  const steps = ["Prisma is listening to the recording", "Evon is checking it for scam patterns"];
  let step = 0;
  $("#loading-text").textContent = steps[0];
  const stepTimer = setInterval(() => ($("#loading-text").textContent = steps[Math.min(++step, 1)]), 4000);
  const fd = new FormData();
  fd.append("file", chosen);
  fd.append("langs", chosenLangs());
  try {
    const r = await fetch("/api/analyze", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.statusText);
    report = data;
    showReport();
  } catch (e) {
    resetPanel("file");
    health();
    toast(e.message, true, 8000);
  } finally {
    clearInterval(stepTimer);
    $("#loading").hidden = true;
    $("#analyze").disabled = false;
  }
};

let revealedAll = false;
let fileWarned = false;
function showReport() {
  revealedAll = false;
  fileWarned = false;
  $("#result").hidden = false;
  $("#tab-file").classList.add("has-result");
  setRisk("file", 0, "safe", "Play the recording to follow along.");
  const player = $("#player");
  player.src = URL.createObjectURL(chosen);
  renderFile(0);
  player.ontimeupdate = () => renderFile(player.currentTime);
  player.onended = () => revealAll();
  player.play().catch(() => {});
}

function filePhrases() {
  return report.rules.signs.flatMap((s) => s.matches).concat((report.evon?.red_flags || []).map((f) => f.quote));
}

function renderFile(t) {
  if (!report || revealedAll) return;
  const segs = report.segments.filter((s) => s.text && s.start <= t);
  const phrases = filePhrases();
  $("#transcript2").innerHTML = segs.length
    ? segs.map((s) => `<p>${highlight(s.text, phrases)}</p>`).join("")
    : '<p class="hint">Listening…</p>';
  $("#transcript2").scrollTop = $("#transcript2").scrollHeight;
  const last = segs[segs.length - 1];
  const risk = last ? Math.round(last.rule_score * 0.9) : 0;
  setRisk("file", risk, risk >= 70 ? "scam" : risk >= 35 ? "suspicious" : "safe");
  const heard = segs.map((s) => s.text).join("\n").toLowerCase();
  setSigns("file", report.rules.signs.filter((s) => s.matches.some((mm) => heard.includes(mm.toLowerCase()))));
  if (risk >= 70) triggerFileWarning();
}

function revealAll() {
  if (!report) return;
  revealedAll = false;
  renderFile(1e9);
  revealedAll = true;
  setRisk("file", report.risk, report.verdict);
  setSigns("file", report.rules.signs);
  showFileEvon();
  if (report.warning) triggerFileWarning();
}

function showFileEvon() {
  if (report.evon) setEvon("file", report.evon, { state: "ok" });
  else setEvon("file", null, { state: report.evon_error ? "error" : "off", waiting: "" });
}

async function triggerFileWarning() {
  if (fileWarned || !report.warning) return;
  fileWarned = true;
  showAlarm(report.warning.text, report.evon?.scam_type);
  showFileEvon(); // the alarm pauses playback, so explain why right away
  try {
    const r = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: report.warning.text }) });
    if (!r.ok) throw new Error(await r.text());
    $("#player").pause();
    playWav(await r.blob());
  } catch (e) {
    toast("Timbre could not speak the warning.", true);
  }
}

$("#skip").onclick = () => { $("#player").pause(); revealAll(); };

openTab(["file", "learn"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "live"); // links like /app#file
health();
setInterval(health, 30000);
