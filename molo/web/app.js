/* Molo, the interface.
 *
 * Deliberately vanilla: no build step, no bundler. Open the file, change a
 * line, reload. It costs a few extra lines here and saves anyone who forks
 * the project from installing a toolchain to move a button.
 */

const $ = (id) => document.getElementById(id);
const state = { jobs: new Map(), presets: [], settings: {}, watchers: [], token: null, ffmpeg: true };

/* The token arrives in the pairing link. Strip it from the address bar right
   away: it belongs in sessionStorage, not in a phone's browser history. */
(function grabToken() {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) {
    sessionStorage.setItem("molo_token", fromUrl);
    history.replaceState({}, "", location.pathname);
  }
  state.token = sessionStorage.getItem("molo_token");
})();

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers["X-Molo-Token"] = state.token;
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

/* ---------------- formatting ---------------- */
const fmtBytes = (n) => {
  if (!n) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${units[i]}`;
};
const fmtSpeed = (s) => (s ? `${fmtBytes(s)}/s` : "");
const fmtEta = (s) => {
  if (s === null || s === undefined) return "";
  const m = Math.floor(s / 60), sec = Math.round(s % 60);
  return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : m ? `${m}m ${sec}s` : `${sec}s`;
};
const fmtDur = (s) => {
  if (!s) return "";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.round(s % 60);
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
           : `${m}:${String(sec).padStart(2, "0")}`;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const T = (key, vars) => window.I18N.t(key, vars);

/* Server notes look like `retry:2:8` or `from:Some Channel`. Everything after
   the first colon is the payload, so titles containing colons survive. */
function renderNote(note) {
  if (!note) return "";
  const cut = note.indexOf(":");
  const kind = cut === -1 ? note : note.slice(0, cut);
  const rest = cut === -1 ? "" : note.slice(cut + 1);
  switch (kind) {
    case "attempts": return T("note.attempts", { n: rest });
    case "skipped":  return T("note.skipped");
    case "nocover":  return T("note.nocover");
    case "retry":    { const [n, s] = rest.split(":"); return T("note.retry", { n, s }); }
    case "recover":  return T("note.recover", { msg: rest });
    case "process":  return T("note.process", { name: rest });
    case "from":     return T("note.from", { title: rest });
    default:         return note;   // anything unrecognised shows as-is
  }
}

function toast(message, level = "") {
  const el = document.createElement("div");
  el.className = `toast ${level}`;
  el.textContent = message;
  $("toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 5200);
}

/* ---------------- queue ---------------- */
function renderJobs() {
  const all = [...state.jobs.values()].sort((a, b) => b.created_at - a.created_at);
  const running = all.find((j) => j.status === "running");
  const rest = all.filter((j) => j !== running);

  const pending = all.filter((j) => j.status === "queued" || j.status === "running").length;
  $("count-queue").textContent = pending || "";

  renderActive(running);

  $("empty-jobs").hidden = all.length > 0;
  $("list-head").hidden = rest.length === 0;
  $("list-title").textContent = running ? T("nav.queue") : "";

  const box = $("jobs");
  box.innerHTML = "";
  for (const job of rest) box.appendChild(jobRow(job));
}

/* The running item gets a card of its own. A download manager where the thing
   currently happening looks identical to the six finished rows above it is
   giving the user no signal at all. */
function renderActive(job) {
  const box = $("active");
  if (!job) { box.hidden = true; box.innerHTML = ""; return; }

  const rate = [fmtSpeed(job.speed), job.eta != null ? T("job.left", { time: fmtEta(job.eta) }) : "",
                fmtBytes(job.total_bytes)].filter(Boolean).join("  ·  ");

  box.innerHTML = `
    ${job.thumbnail ? `<img class="art" src="${esc(job.thumbnail)}" alt="">` : `<div class="art"></div>`}
    <div class="body">
      <div class="kicker">${esc(T("queue.active"))}</div>
      <div class="title" title="${esc(job.title)}">${esc(job.title)}</div>
      <div class="figures">
        <span class="pct">${(job.progress || 0).toFixed(1)}<span style="font-size:.5em">%</span></span>
        <span class="rate">${esc(rate)}</span>
      </div>
      <div class="bar"><i style="width:${Math.min(100, job.progress || 0)}%"></i></div>
      ${job.note ? `<div class="rate" style="margin-top:6px">${esc(renderNote(job.note))}</div>` : ""}
    </div>`;
  box.hidden = false;
}

function jobRow(job) {
  const el = document.createElement("div");
  el.className = "job";
  el.dataset.status = job.status;
  el.dataset.id = job.id;

  const bits = [];
  if (job.uploader) bits.push(job.uploader);
  if (job.note) bits.push(renderNote(job.note));

  el.innerHTML = `
    ${job.thumbnail ? `<img class="thumb" src="${esc(job.thumbnail)}" alt="" loading="lazy">`
                    : `<div class="thumb"></div>`}
    <div class="body">
      <div class="title" title="${esc(job.title)}">${esc(job.title)}</div>
      <div class="sub">${bits.map(esc).join('<span class="dot">·</span>')}</div>
      ${job.error ? `<div class="err">${esc(job.error)}</div>` : ""}
    </div>
    <div class="actions">
      <span class="badge">${esc(T("state." + job.status))}</span>
      ${job.status === "queued" ? `<button class="btn ghost tiny" data-act="cancel">${esc(T("job.cancel"))}</button>` : ""}
      ${job.status === "error" || job.status === "cancelled" ? `<button class="btn quiet tiny" data-act="retry">${esc(T("job.retry"))}</button>` : ""}
      ${job.status === "done" && job.filepath ? `<button class="btn quiet tiny" data-act="reveal">${esc(T("job.reveal"))}</button>` : ""}
      ${job.status === "done" && !job.filepath ? `<span class="badge" title="${esc(T("job.noFile"))}">?</span>` : ""}
    </div>`;

  el.querySelectorAll("[data-act]").forEach((btn) =>
    btn.addEventListener("click", () => act(btn.dataset.act, job)));
  return el;
}

async function act(action, job) {
  try {
    if (action === "cancel") await api(`/api/jobs/${job.id}/cancel`, { method: "POST" });
    if (action === "retry") await api(`/api/jobs/${job.id}/retry`, { method: "POST" });
    if (action === "reveal") await api("/api/reveal", { method: "POST", body: JSON.stringify({ path: job.filepath }) });
  } catch (err) {
    toast(err.message, "err");
  }
}

/* ---------------- adding ---------------- */
async function addUrl(url, preset) {
  url = (url || $("url").value).trim();
  if (!url) return;
  const btn = $("add");
  btn.disabled = true;
  try {
    await api("/api/jobs", { method: "POST", body: JSON.stringify({ url, preset: preset || $("preset").value }) });
    $("url").value = "";
    $("preview").hidden = true;
    $("suggestion").hidden = true;
  } catch (err) {
    toast(err.message, "err");   // 451 is the policy refusal; it carries its own explanation
  } finally {
    btn.disabled = false;
  }
}

let probeTimer = null;
function scheduleProbe() {
  clearTimeout(probeTimer);
  const url = $("url").value.trim();
  if (!/^https?:\/\/.{6,}/i.test(url)) { $("preview").hidden = true; return; }
  probeTimer = setTimeout(() => probe(url), 550);
}

async function probe(url) {
  try {
    const info = await api("/api/probe", { method: "POST", body: JSON.stringify({ url }) });
    if ($("url").value.trim() !== url) return;   // they typed on
    const meta = info.kind === "playlist"
      ? `${info.count} items${info.uploader ? " · " + info.uploader : ""}`
      : [info.uploader, fmtDur(info.duration), info.max_height ? `up to ${info.max_height}p` : ""]
          .filter(Boolean).join(" · ");
    $("preview").innerHTML = `
      ${info.thumbnail ? `<img src="${esc(info.thumbnail)}" alt="">` : ""}
      <div class="meta"><div class="t">${esc(info.title)}</div><div class="s">${esc(meta)}</div></div>`;
    $("preview").hidden = false;
  } catch (err) {
    if (err.status === 451) { toast(err.message, "err"); $("preview").hidden = true; }
  }
}

/* ---------------- watchers ---------------- */
function renderWatchers() {
  const box = $("watchers");
  $("count-watch").textContent = state.watchers.length || "";
  box.innerHTML = "";
  if (!state.watchers.length) {
    box.innerHTML = `<p class="empty-body" style="padding:28px 0">${esc(T("watch.empty"))}</p>`;
    return;
  }
  for (const w of state.watchers) {
    const el = document.createElement("div");
    el.className = "watcher";
    const when = w.last_check
      ? new Date(w.last_check * 1000).toLocaleString(window.I18N.lang)
      : T("watch.never");
    const bits = [T("watch.known", { count: w.seen_count }), T("watch.lastCheck", { when })];
    if (w.last_new) bits.push(T("watch.new", { count: w.last_new }));
    el.innerHTML = `
      <div>
        <div class="w-title">${esc(w.title || w.url)}</div>
        <div class="w-sub">${bits.map(esc).join(" · ")}${w.error ? ` · <span style="color:var(--danger)">${esc(w.error)}</span>` : ""}</div>
      </div>
      <div class="actions">
        <button class="btn quiet tiny" data-check>${esc(T("watch.check"))}</button>
        <button class="btn ghost tiny" data-del>${esc(T("watch.remove"))}</button>
      </div>`;
    el.querySelector("[data-check]").addEventListener("click", async () => {
      try {
        const res = await api(`/api/watchers/${w.id}/check`, { method: "POST" });
        state.watchers = res.watchers;
        renderWatchers();
        toast(res.new ? T("watch.foundNew", { count: res.new }) : T("watch.nothingNew"));
      } catch (err) { toast(err.message, "err"); }
    });
    el.querySelector("[data-del]").addEventListener("click", async () => {
      state.watchers = (await api(`/api/watchers/${w.id}`, { method: "DELETE" })).watchers;
      renderWatchers();
    });
    box.appendChild(el);
  }
}

/* ---------------- settings ---------------- */
const TOGGLES = ["embed_metadata", "embed_thumbnail", "embed_subs", "write_archive",
                 "auto_update_ytdlp", "watch_clipboard", "allow_lan"];

function fillSettings() {
  const s = state.settings;
  $("download-dir").value = s.download_dir || "";
  $("concurrent").value = s.max_concurrent || 2;
  TOGGLES.forEach((k) => { if ($(k)) $(k).checked = !!s[k]; });
  $("language").value = s.language || "auto";
  updateHint();
}

async function saveSettings(changes) {
  try {
    state.settings = (await api("/api/settings", { method: "POST", body: JSON.stringify(changes) })).settings;
    if ("allow_lan" in changes) refreshPairing();
    toast(T("settings.saved"), "ok");
  } catch (err) { toast(err.message, "err"); }
}

async function refreshPairing() {
  if (!state.settings.allow_lan) { $("pairing").hidden = true; $("pill-lan").hidden = true; return; }
  try {
    const info = await api("/api/pairing");
    $("pair-url").textContent = info.url;
    $("pairing").hidden = false;
    $("pill-lan").hidden = false;
  } catch (_) {}
}

function updateHint() {
  const preset = state.presets.find((p) => p.key === $("preset").value);
  $("preset-hint").textContent = preset ? window.I18N.tOr(`preset.${preset.key}.hint`, preset.hint) : "";
}

function fillPresets() {
  $("preset").innerHTML = state.presets
    .map((p) => `<option value="${p.key}">${esc(window.I18N.tOr("preset." + p.key, p.label))}</option>`)
    .join("");
  $("preset").value = state.settings.preset || "best_compat";
}

/* ---------------- navigation ---------------- */
const TABS = ["queue", "watchers", "settings"];

function showTab(name) {
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("is-active", n.dataset.tab === name));
  TABS.forEach((t) => { $(`tab-${t}`).hidden = t !== name; });
  $("scroll").scrollTop = 0;
}

/* ---------------- keyboard ----------------
 * ⌘, for settings is the one macOS users try without thinking. The rest are
 * the ones that a window like this is expected to answer.
 */
function keyboard() {
  document.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");

    if (e.key === "Escape") {
      const open = document.querySelector(".sheet:not([hidden])");
      if (open && open.id !== "gate") { open.hidden = true; e.preventDefault(); }
      return;
    }
    if (!mod) return;

    if (e.key === ",") { e.preventDefault(); showTab("settings"); }
    else if (e.key === "/") { e.preventDefault(); $("shortcuts").hidden = !$("shortcuts").hidden; }
    else if (e.key === "l") { e.preventDefault(); $("url").focus(); $("url").select(); }
    else if (e.key === "1") { e.preventDefault(); showTab("queue"); }
    else if (e.key === "2") { e.preventDefault(); showTab("watchers"); }
    else if (e.key === "3") { e.preventDefault(); showTab("settings"); }
    else if (e.key === "Enter" && typing && document.activeElement === $("url")) addUrl();
  });

  /* Paste anywhere outside a field and it goes straight into the queue. */
  document.addEventListener("paste", (e) => {
    if (/^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName || "")) return;
    const text = (e.clipboardData?.getData("text") || "").trim();
    if (/^https?:\/\//i.test(text)) { e.preventDefault(); addUrl(text); }
  });
}

/* Drag a link out of a browser and onto the window. */
function dragAndDrop() {
  const zone = $("composer");
  let depth = 0;   // dragenter/leave fire per child; a counter avoids flicker

  window.addEventListener("dragenter", (e) => { e.preventDefault(); if (++depth === 1) zone.classList.add("is-dragging"); });
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; zone.classList.remove("is-dragging"); } });
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    depth = 0;
    zone.classList.remove("is-dragging");
    const text = (e.dataTransfer?.getData("text/uri-list") || e.dataTransfer?.getData("text") || "").trim();
    if (/^https?:\/\//i.test(text)) addUrl(text.split("\n")[0]);
  });
}

/* ---------------- live updates ---------------- */
let socket = null, retry = 0;
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const qs = state.token ? `?token=${encodeURIComponent(state.token)}` : "";
  socket = new WebSocket(`${proto}://${location.host}/ws${qs}`);

  socket.onopen = () => { retry = 0; };
  socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "hello") {
      state.jobs = new Map(msg.jobs.map((j) => [j.id, j]));
      renderJobs();
    } else if (msg.type === "job" && msg.job) {
      state.jobs.set(msg.job.id, msg.job);
      renderJobs();
    } else if (msg.type === "progress" || msg.type === "note") {
      const job = state.jobs.get(msg.id);
      if (job) { Object.assign(job, msg); patchRunning(job); }
    } else if (msg.type === "cleared") {
      load();
    } else if (msg.type === "watchers") {
      state.watchers = msg.watchers;
      renderWatchers();
    } else if (msg.type === "clipboard") {
      offerClipboard(msg.url);
    } else if (msg.type === "toast") {
      toast(msg.message, msg.level || "");
    }
  };
  socket.onclose = () => {
    retry = Math.min(retry + 1, 6);   // the laptop may have slept
    setTimeout(connect, retry * 1000);
  };
}

/* Only touch the numbers that changed. Rebuilding the whole card several
   times a second made the artwork flicker. */
function patchRunning(job) {
  const box = $("active");
  if (box.hidden || job.status !== "running") { renderJobs(); return; }
  const pct = box.querySelector(".pct");
  const bar = box.querySelector(".bar > i");
  const rate = box.querySelector(".rate");
  if (pct) pct.innerHTML = `${(job.progress || 0).toFixed(1)}<span style="font-size:.5em">%</span>`;
  if (bar) bar.style.width = `${Math.min(100, job.progress || 0)}%`;
  if (rate) {
    rate.textContent = [fmtSpeed(job.speed), job.eta != null ? T("job.left", { time: fmtEta(job.eta) }) : "",
                        fmtBytes(job.total_bytes)].filter(Boolean).join("  ·  ");
  }
}

function offerClipboard(url) {
  if ($("url").value.trim() === url) return;
  $("sugg-url").textContent = url.length > 64 ? url.slice(0, 62) + "…" : url;
  $("suggestion").hidden = false;
  $("suggestion").dataset.url = url;
}

/* ---------------- boot ---------------- */
async function load() {
  try {
    const data = await api("/api/state");
    state.presets = data.presets;
    state.settings = data.settings;
    state.watchers = data.watchers;
    state.ffmpeg = data.ffmpeg;
    state.jobs = new Map(data.jobs.map((j) => [j.id, j]));

    window.I18N.use(data.settings.language);

    $("version").textContent = data.version;
    $("pill-ytdlp").textContent = data.ytdlp;
    $("pill-ffmpeg").textContent = T(data.ffmpeg ? "status.present" : "status.missing");
    $("stat-ffmpeg").className = data.ffmpeg ? "stat" : "stat warn";

    /* A missing dependency is a state, not an event. The old code raised a
       toast here, which vanished after five seconds and looked like a bug. */
    $("ffmpeg-notice").hidden = data.ffmpeg;
    $("ffmpeg-cmd").textContent =
      data.platform === "Windows" ? "winget install Gyan.FFmpeg"
      : data.platform === "Darwin" ? "brew install ffmpeg"
      : "sudo apt install ffmpeg";

    fillPresets();
    $("language").innerHTML =
      `<option value="auto">${esc(T("settings.languageAuto"))}</option>` +
      window.I18N.LANGUAGES.map((l) => `<option value="${l.code}">${esc(l.label)}</option>`).join("");

    fillSettings();
    renderJobs();
    renderWatchers();
    refreshPairing();

    if (!state.settings.accepted_terms) $("gate").hidden = false;
  } catch (err) {
    if (err.status === 401) {
      document.body.innerHTML =
        `<div class="sheet"><div class="sheet-card narrow"><h1>${esc(T("token.title"))}</h1>
         <p class="lead">${esc(T("token.body"))}</p></div></div>`;
      return;
    }
    toast(err.message, "err");
  }
}

function wire() {
  $("add").addEventListener("click", () => addUrl());
  $("url").addEventListener("keydown", (e) => { if (e.key === "Enter") addUrl(); });
  $("url").addEventListener("input", scheduleProbe);
  $("preset").addEventListener("change", () => { updateHint(); saveSettings({ preset: $("preset").value }); });

  $("clear").addEventListener("click", async () => {
    await api("/api/jobs", { method: "DELETE" });
    await load();
  });

  document.querySelectorAll(".nav-item").forEach((item) =>
    item.addEventListener("click", () => showTab(item.dataset.tab)));
  document.querySelectorAll("[data-close-sheet]").forEach((btn) =>
    btn.addEventListener("click", () => { btn.closest(".sheet").hidden = true; }));

  $("sugg-add").addEventListener("click", () => addUrl($("suggestion").dataset.url));
  $("sugg-no").addEventListener("click", () => { $("suggestion").hidden = true; });

  $("watch-add").addEventListener("click", async () => {
    const url = $("watch-url").value.trim();
    if (!url) return;
    try {
      const res = await api("/api/watchers", {
        method: "POST",
        body: JSON.stringify({ url, preset: $("preset").value, interval_minutes: +$("watch-interval").value }),
      });
      state.watchers = res.watchers;
      $("watch-url").value = "";
      renderWatchers();
      toast(T("watch.added"));
    } catch (err) { toast(err.message, "err"); }
  });

  $("download-dir").addEventListener("change", (e) => saveSettings({ download_dir: e.target.value }));
  $("concurrent").addEventListener("change", (e) => saveSettings({ max_concurrent: +e.target.value }));
  TOGGLES.forEach((key) => {
    const el = $(key);
    if (el) el.addEventListener("change", () => saveSettings({ [key]: el.checked }));
  });

  $("language").addEventListener("change", async (e) => {
    window.I18N.use(e.target.value);
    await saveSettings({ language: e.target.value });
    renderJobs();
    renderWatchers();
    load();
  });

  $("reveal").addEventListener("click", () =>
    api("/api/reveal", { method: "POST", body: JSON.stringify({ path: $("download-dir").value }) })
      .catch((err) => toast(err.message, "err")));

  $("copy-pair").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("pair-url").textContent);
      toast(T("settings.copied"), "ok");
    } catch (_) {}
  });

  $("update-ytdlp").addEventListener("click", async () => {
    $("update-msg").textContent = "…";
    try {
      const res = await api("/api/update-ytdlp", { method: "POST" });
      $("update-msg").textContent = res.message;
      /* The engine on disk changed, the one running did not: it was imported at
         launch and stays until the next one. Showing the new number next to a
         process still using the old one would be a small lie, so the pill keeps
         the running version and gains the pending one beside it. */
      $("pill-ytdlp").textContent = res.pending
        ? `${res.version} → ${res.pending}`
        : res.version;
    } catch (err) { $("update-msg").textContent = err.message; }
  });

  $("gate-accept").addEventListener("click", async () => {
    $("gate").hidden = true;
    await api("/api/settings", { method: "POST", body: JSON.stringify({ accepted_terms: true }) });
  });
}

window.I18N.use("auto");   // something readable before /api/state answers
wire();
keyboard();
dragAndDrop();
load();
connect();

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
