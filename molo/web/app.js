/* Molo — interfaccia. Vanilla di proposito: nessuna build, nessun bundler,
   apri il file e lo modifichi. Il costo è qualche riga in più, il guadagno è
   che chi forka il progetto non deve installare niente per cambiare un bottone. */

const $ = (id) => document.getElementById(id);
const state = { jobs: new Map(), presets: [], settings: {}, watchers: [], token: null };

/* Il token arriva nel link di accoppiamento. Lo togliamo subito dalla barra
   degli indirizzi: resta in sessionStorage, non nella cronologia del telefono. */
(function grabToken() {
  const params = new URLSearchParams(location.search);
  const fromUrl = params.get("token");
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

/* ---------------- formattatori ---------------- */
const fmtBytes = (n) => {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${u[i]}`;
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

const LABELS = { queued: "in attesa", running: "in corso", done: "fatto",
                 error: "errore", cancelled: "annullato", skipped: "già preso" };

function toast(message, level = "") {
  const el = document.createElement("div");
  el.className = `toast ${level}`;
  el.textContent = message;
  $("toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 5200);
}

/* ---------------- coda ---------------- */
function renderJobs() {
  const list = [...state.jobs.values()].sort((a, b) => b.created_at - a.created_at);
  const box = $("jobs");
  $("empty-jobs").hidden = list.length > 0;
  const pending = list.filter((j) => j.status === "queued" || j.status === "running").length;
  $("count-queue").textContent = pending || "";   // vuoto sparisce, vedi .count:empty

  box.innerHTML = "";
  for (const job of list) box.appendChild(jobCard(job));
}

function jobCard(job) {
  const el = document.createElement("div");
  el.className = "job";
  el.dataset.status = job.status;
  el.dataset.id = job.id;

  const running = job.status === "running";
  const bits = [];
  if (running) {
    bits.push(`${(job.progress || 0).toFixed(1)}%`);
    if (job.speed) bits.push(fmtSpeed(job.speed));
    if (job.eta !== null && job.eta !== undefined) bits.push(`mancano ${fmtEta(job.eta)}`);
    if (job.total_bytes) bits.push(fmtBytes(job.total_bytes));
  } else {
    if (job.uploader) bits.push(job.uploader);
    if (job.note) bits.push(job.note);
  }

  el.innerHTML = `
    ${job.thumbnail ? `<img class="thumb" src="${esc(job.thumbnail)}" alt="" loading="lazy">`
                    : `<div class="thumb"></div>`}
    <div class="body">
      <div class="title" title="${esc(job.title)}">${esc(job.title)}</div>
      <div class="sub">${bits.map(esc).join('<span class="dot">·</span>')}</div>
      ${job.error ? `<div class="err">${esc(job.error)}</div>` : ""}
      ${running || job.progress > 0
        ? `<div class="bar"><i style="width:${Math.min(100, job.progress || 0)}%"></i></div>` : ""}
    </div>
    <div class="actions">
      <span class="badge">${LABELS[job.status] || job.status}</span>
      ${running || job.status === "queued" ? `<button class="btn ghost small" data-act="cancel">Ferma</button>` : ""}
      ${job.status === "error" || job.status === "cancelled" ? `<button class="btn ghost small" data-act="retry">Riprova</button>` : ""}
      ${job.status === "done" && job.filepath ? `<button class="btn ghost small" data-act="reveal">Mostra</button>` : ""}
    </div>`;

  el.querySelectorAll("[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => act(btn.dataset.act, job));
  });
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

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------------- aggiunta ---------------- */
async function addUrl(url, preset) {
  url = (url || $("url").value).trim();
  if (!url) return;
  const btn = $("add");
  btn.disabled = true;
  try {
    await api("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ url, preset: preset || $("preset").value }),
    });
    $("url").value = "";
    $("preview").hidden = true;
  } catch (err) {
    // 451 è il rifiuto della guardia legale: merita un messaggio lungo, non un errore secco.
    toast(err.message, err.status === 451 ? "err" : "err");
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
    if ($("url").value.trim() !== url) return; // l'utente ha già scritto altro
    const box = $("preview");
    const meta = info.kind === "playlist"
      ? `${info.count} elementi${info.uploader ? " · " + info.uploader : ""}`
      : [info.uploader, fmtDur(info.duration), info.max_height ? `fino a ${info.max_height}p` : ""]
          .filter(Boolean).join(" · ");
    box.innerHTML = `
      ${info.thumbnail ? `<img src="${esc(info.thumbnail)}" alt="">` : ""}
      <div class="meta">
        <div class="t">${esc(info.title)}</div>
        <div class="s">${esc(meta)}</div>
      </div>`;
    box.hidden = false;
  } catch (err) {
    if (err.status === 451) { toast(err.message, "err"); $("preview").hidden = true; }
  }
}

/* ---------------- monitor ---------------- */
function renderWatchers() {
  const box = $("watchers");
  $("count-watch").textContent = state.watchers.length || "";
  box.innerHTML = "";
  if (!state.watchers.length) {
    box.innerHTML = `<p class="empty">Nessun monitor attivo.</p>`;
    return;
  }
  for (const w of state.watchers) {
    const el = document.createElement("div");
    el.className = "watcher";
    const when = w.last_check ? new Date(w.last_check * 1000).toLocaleString("it-IT") : "mai";
    el.innerHTML = `
      <div>
        <div class="w-title">${esc(w.title || w.url)}</div>
        <div class="w-sub">ogni ${w.interval_minutes} min · ${w.seen_count} noti · ultimo controllo ${esc(when)}
          ${w.last_new ? ` · ${w.last_new} nuovi` : ""}${w.error ? ` · <span style="color:var(--danger)">${esc(w.error)}</span>` : ""}</div>
      </div>
      <div class="actions">
        <button class="btn ghost small" data-check>Controlla</button>
        <button class="btn ghost small" data-del>Togli</button>
      </div>`;
    el.querySelector("[data-check]").addEventListener("click", async () => {
      try {
        const res = await api(`/api/watchers/${w.id}/check`, { method: "POST" });
        state.watchers = res.watchers; renderWatchers();
        toast(res.new ? `${res.new} nuovi messi in coda` : "Niente di nuovo");
      } catch (err) { toast(err.message, "err"); }
    });
    el.querySelector("[data-del]").addEventListener("click", async () => {
      const res = await api(`/api/watchers/${w.id}`, { method: "DELETE" });
      state.watchers = res.watchers; renderWatchers();
    });
    box.appendChild(el);
  }
}

/* ---------------- impostazioni ---------------- */
const TOGGLES = ["embed_metadata", "embed_thumbnail", "embed_subs", "write_archive",
                 "auto_update_ytdlp", "watch_clipboard", "allow_lan", "strict_policy"];

function fillSettings() {
  const s = state.settings;
  $("download-dir").value = s.download_dir || "";
  $("concurrent").value = s.max_concurrent || 2;
  TOGGLES.forEach((k) => { if ($(k)) $(k).checked = !!s[k]; });
  $("preset").value = s.preset || "best_compat";
  // La spia in basso resta accesa finché la modalità rigorosa è spenta: è uno
  // stato che non deve poter passare inosservato per mesi.
  $("pill-strict").hidden = s.strict_policy !== false;
  updateHint();
}

async function saveSettings(changes) {
  try {
    const res = await api("/api/settings", { method: "POST", body: JSON.stringify(changes) });
    state.settings = res.settings;
    if ("allow_lan" in changes) refreshPairing();
    toast("Salvato", "ok");
  } catch (err) { toast(err.message, "err"); }
}

async function refreshPairing() {
  const box = $("pairing");
  if (!state.settings.allow_lan) { box.hidden = true; $("pill-lan").hidden = true; return; }
  try {
    const info = await api("/api/pairing");
    $("pair-url").textContent = info.url;
    box.hidden = false;
    $("pill-lan").hidden = false;
  } catch (_) {}
}

function updateHint() {
  const preset = state.presets.find((p) => p.key === $("preset").value);
  $("preset-hint").textContent = preset ? preset.hint : "";
}

/* ---------------- WebSocket ---------------- */
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
    } else if (msg.type === "job") {
      if (msg.job) { state.jobs.set(msg.job.id, msg.job); renderJobs(); }
    } else if (msg.type === "progress" || msg.type === "note") {
      const job = state.jobs.get(msg.id);
      if (job) { Object.assign(job, msg); patchCard(job); }
    } else if (msg.type === "cleared") {
      load();
    } else if (msg.type === "watchers") {
      state.watchers = msg.watchers; renderWatchers();
    } else if (msg.type === "clipboard") {
      showSuggestion(msg.url);
    } else if (msg.type === "toast") {
      toast(msg.message, msg.level || "");
    }
  };
  socket.onclose = () => {
    // Backoff: la finestra può restare aperta mentre il portatile dorme.
    retry = Math.min(retry + 1, 6);
    setTimeout(connect, retry * 1000);
  };
}

/* Aggiorna solo la riga che cambia: ridisegnare tutta la lista 3 volte al
   secondo faceva sfarfallare i thumbnail. */
function patchCard(job) {
  const card = document.querySelector(`.job[data-id="${job.id}"]`);
  if (!card) { renderJobs(); return; }
  const bar = card.querySelector(".bar > i");
  if (bar) bar.style.width = `${Math.min(100, job.progress || 0)}%`;
  const sub = card.querySelector(".sub");
  if (sub && job.status === "running") {
    const bits = [`${(job.progress || 0).toFixed(1)}%`];
    if (job.speed) bits.push(fmtSpeed(job.speed));
    if (job.eta !== null && job.eta !== undefined) bits.push(`mancano ${fmtEta(job.eta)}`);
    if (job.note) bits.push(job.note);
    sub.innerHTML = bits.map(esc).join('<span class="dot">·</span>');
  }
}

function showSuggestion(url) {
  if ($("url").value.trim() === url) return;
  $("sugg-url").textContent = url.length > 70 ? url.slice(0, 68) + "…" : url;
  $("suggestion").hidden = false;
  $("suggestion").dataset.url = url;
}

/* ---------------- avvio ---------------- */
async function load() {
  try {
    const data = await api("/api/state");
    state.presets = data.presets;
    state.settings = data.settings;
    state.watchers = data.watchers;
    state.jobs = new Map(data.jobs.map((j) => [j.id, j]));

    $("version").textContent = data.version;
    $("pill-ytdlp").textContent = data.ytdlp;
    $("pill-ffmpeg").textContent = data.ffmpeg ? "presente" : "assente";
    $("pill-ffmpeg").parentElement.className = data.ffmpeg ? "stat" : "stat warn";
    if (!data.ffmpeg) {
      toast("Senza ffmpeg non posso unire video e audio: resti sotto i 720p. Installalo con «brew install ffmpeg».", "err");
    }

    $("preset").innerHTML = state.presets
      .map((p) => `<option value="${p.key}">${esc(p.label)}</option>`).join("");

    fillSettings();
    renderJobs();
    renderWatchers();
    refreshPairing();

    if (!state.settings.accepted_terms) $("gate").hidden = false;
  } catch (err) {
    if (err.status === 401) {
      document.body.innerHTML =
        `<div class="gate"><div class="gate-card"><h1>Serve la chiave</h1>
         <p class="lead">Apri Molo dal link con il token che trovi nelle impostazioni sul computer.</p></div></div>`;
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

  const TITLES = { queue: "Coda", watchers: "Monitor", settings: "Impostazioni" };
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("is-active"));
      item.classList.add("is-active");
      const active = item.dataset.tab;
      Object.keys(TITLES).forEach((name) => { $(`tab-${name}`).hidden = name !== active; });
      $("view-title").textContent = TITLES[active];
      // «Pulisci i finiti» ha senso solo sulla coda.
      $("clear").hidden = active !== "queue";
    });
  });

  $("sugg-add").addEventListener("click", () => {
    addUrl($("suggestion").dataset.url);
    $("suggestion").hidden = true;
  });
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
      toast("Monitor aggiunto. Il primo giro censisce quello che c'è già, senza scaricarlo.");
    } catch (err) { toast(err.message, "err"); }
  });

  $("download-dir").addEventListener("change", (e) => saveSettings({ download_dir: e.target.value }));
  $("concurrent").addEventListener("change", (e) => saveSettings({ max_concurrent: +e.target.value }));
  TOGGLES.forEach((key) => {
    const el = $(key);
    if (el) el.addEventListener("change", () => saveSettings({ [key]: el.checked }));
  });

  $("reveal").addEventListener("click", () =>
    api("/api/reveal", { method: "POST", body: JSON.stringify({ path: $("download-dir").value }) })
      .catch((err) => toast(err.message, "err")));

  $("copy-pair").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("pair-url").textContent);
      toast("Link copiato", "ok");
    } catch (_) { toast("Copialo a mano dal riquadro qui sopra"); }
  });

  $("update-ytdlp").addEventListener("click", async () => {
    $("update-msg").textContent = "Controllo…";
    try {
      const res = await api("/api/update-ytdlp", { method: "POST" });
      $("update-msg").textContent = res.message;
      $("pill-ytdlp").textContent = `yt-dlp ${res.version}`;
    } catch (err) { $("update-msg").textContent = err.message; }
  });

  $("gate-accept").addEventListener("click", async () => {
    $("gate").hidden = true;
    await api("/api/settings", { method: "POST", body: JSON.stringify({ accepted_terms: true }) });
  });
}

wire();
load();
connect();

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
