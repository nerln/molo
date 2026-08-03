/* Translations.
 *
 * English is the source. When a key is missing from another language the
 * English string shows through rather than a blank or a raw key, a half
 * translated interface should degrade into a readable one.
 *
 * Adding a language: copy the `en` block, translate the values, register it in
 * LANGUAGES below. Nothing else needs touching.
 */

const STRINGS = {
  en: {
    "app.tagline": "Where your videos come in to dock",

    "nav.queue": "Queue",
    "nav.watchers": "Watching",
    "nav.settings": "Settings",

    "status.engine": "engine",
    "status.ffmpeg": "ffmpeg",
    "status.network": "network",
    "status.present": "found",
    "status.missing": "missing",
    "status.reachable": "shared",

    "composer.placeholder": "Paste a link",
    "composer.button": "Download",
    "composer.drop": "Drop a link here",
    "composer.clipboard": "Copied to your clipboard",
    "composer.dismiss": "Dismiss",

    /* Preset names come from the server, which speaks English. Translating
       them here keeps the interface from coming out half in one language. */
    "preset.best_compat": "Best quality",
    "preset.best_compat.hint": "The best that plays anywhere without re-encoding: H.264 + AAC in MP4.",
    "preset.best_absolute": "Absolute best",
    "preset.best_absolute.hint": "The highest bitrate there is, AV1 or VP9 included. Lands in MKV, which not every player takes.",
    "preset.1080p": "1080p",
    "preset.1080p.hint": "Capped at Full HD, for when 4K is not worth ten times the size.",
    "preset.720p": "720p",
    "preset.720p.hint": "Light. For watching and nothing else.",
    "preset.audio_best": "Audio only (as served)",
    "preset.audio_best.hint": "The best audio track exactly as served, no re-encoding, no added loss.",
    "preset.audio_mp3": "Audio only (MP3 320)",
    "preset.audio_mp3.hint": "Re-encoded to MP3 for older players. That is a re-encode, so it loses a little.",

    "queue.empty.title": "Nothing in the queue",
    "queue.empty.body": "Paste a link above, or copy one anywhere and Molo will offer it.",
    "queue.clear": "Clear finished",
    "queue.active": "Downloading now",

    "job.cancel": "Stop",
    "job.retry": "Retry",
    "job.reveal": "Show file",
    "job.attempt": "attempt",
    "job.attempts": "attempts",
    "job.left": "{time} left",
    "job.noFile": "Molo could not tell where this file ended up.",

    /* Notes arrive from the server as `key:arg:arg`, never as prose, prose
       would pin the queue to whatever language the server was written in. */
    "note.attempts": "took {n} attempts",
    "note.skipped": "already had this one",
    "note.nocover": "downloaded, but the cover art would not attach",
    "note.retry": "retrying ({n}) in {s}s",
    "note.recover": "recovering: {msg}",
    "note.process": "processing: {name}",
    "note.from": "from “{title}”",

    "state.queued": "waiting",
    "state.running": "downloading",
    "state.done": "done",
    "state.error": "failed",
    "state.cancelled": "stopped",
    "state.skipped": "skipped",

    "watch.explain": "A channel or playlist Molo checks on its own, downloading whatever is new. The first pass only takes note of what is already there, so you don't wake up to an entire back catalogue on your disk.",
    "watch.placeholder": "Channel or playlist address",
    "watch.add": "Watch it",
    "watch.every30": "every 30 minutes",
    "watch.every60": "hourly",
    "watch.every360": "every 6 hours",
    "watch.every1440": "once a day",
    "watch.check": "Check now",
    "watch.remove": "Remove",
    "watch.empty": "Nothing being watched.",
    "watch.known": "{count} known",
    "watch.lastCheck": "last checked {when}",
    "watch.never": "never",
    "watch.new": "{count} new",
    "watch.added": "Watching. The first pass takes note of what's already there without downloading it.",
    "watch.foundNew": "{count} new, queued",
    "watch.nothingNew": "Nothing new",

    "settings.destination": "Destination",
    "settings.open": "Open",
    "settings.downloads": "Downloads",
    "settings.parallel": "At the same time",
    "settings.parallelHint": "Past two or three the bandwidth just splits and you gain nothing.",
    "settings.metadata": "Metadata and chapters in the file",
    "settings.thumbnail": "Cover art in the file",
    "settings.subs": "Embedded subtitles",
    "settings.archive": "Remember what you've downloaded",
    "settings.archiveHint": "Stops you pulling the same video twice.",
    "settings.automatic": "Automatic",
    "settings.autoUpdate": "Keep yt-dlp up to date",
    "settings.autoUpdateHint": "A stale engine is the single most common cause of failed downloads. A new one is used from the next launch.",
    "settings.clipboard": "Offer links I copy",
    "settings.network": "Network",
    "settings.lan": "Reachable from your phone",
    "settings.lanHint": "Inside your own network only, with an access key. Nothing is exposed to the internet.",
    "settings.copy": "Copy",
    "settings.copied": "Link copied",
    "settings.language": "Language",
    "settings.languageAuto": "Follow the system",
    "settings.engine": "Engine",
    "settings.updateNow": "Update yt-dlp now",
    "settings.saved": "Saved",

    "ffmpeg.missing.title": "ffmpeg isn't installed",
    "ffmpeg.missing.body": "Without it Molo can't merge separate video and audio streams, which caps you around 720p. Everything else works.",
    "ffmpeg.missing.how": "Install it with",

    "shortcuts.title": "Keyboard",
    "shortcuts.settings": "Settings",
    "shortcuts.paste": "Paste and download",
    "shortcuts.focus": "Focus the address field",
    "shortcuts.queue": "Go to queue",
    "shortcuts.watchers": "Go to watching",
    "shortcuts.help": "This list",
    "shortcuts.close": "Close",

    "gate.title": "Molo",
    "gate.lead": "Three things, then I'll stop talking.",
    "gate.p1.b": "There is no circumvention code in here.",
    "gate.p1": "No CDM, no keys, no decryption. On an encrypted stream Molo fails, and it fails because that is a thing it cannot do.",
    "gate.p2.b": "What you download stays your responsibility.",
    "gate.p2": "Archiving your own lectures and pirating a film are different acts, and the difference is made by you.",
    "gate.p3.b": "Downloading may breach a site's terms of service.",
    "gate.p3": "That is a contract matter between you and that site, not a crime.",
    "gate.accept": "Understood",
    "gate.more": "The full reasoning",

    "token.title": "Access key needed",
    "token.body": "Open Molo from the link in Settings on the computer running it.",
  },

  it: {
    "app.tagline": "Il molo dove attraccano i tuoi video",

    "nav.queue": "Coda",
    "nav.watchers": "Monitor",
    "nav.settings": "Impostazioni",

    "status.engine": "motore",
    "status.ffmpeg": "ffmpeg",
    "status.network": "rete",
    "status.present": "presente",
    "status.missing": "assente",
    "status.reachable": "condiviso",

    "composer.placeholder": "Incolla un link",
    "composer.button": "Scarica",
    "composer.drop": "Lascia qui il link",
    "composer.clipboard": "Copiato nei tuoi appunti",
    "composer.dismiss": "Ignora",

    "preset.best_compat": "Massima qualità",
    "preset.best_compat.hint": "Il meglio che si apre ovunque senza riconvertire: H.264 + AAC in MP4.",
    "preset.best_absolute": "Massima assoluta",
    "preset.best_absolute.hint": "Il bitrate più alto che esiste, AV1 e VP9 compresi. Esce in MKV, che non tutti i player digeriscono.",
    "preset.1080p": "1080p",
    "preset.1080p.hint": "Tetto a Full HD, per quando il 4K non vale dieci volte lo spazio.",
    "preset.720p": "720p",
    "preset.720p.hint": "Leggero. Per guardare e basta.",
    "preset.audio_best": "Solo audio (com'è)",
    "preset.audio_best.hint": "La traccia audio migliore esattamente come viene servita: nessuna riconversione, nessuna perdita aggiunta.",
    "preset.audio_mp3": "Solo audio (MP3 320)",
    "preset.audio_mp3.hint": "Riconvertito in MP3 per i lettori vecchi. È una ricodifica, quindi qualcosa perde.",

    "queue.empty.title": "Non c'è niente in coda",
    "queue.empty.body": "Incolla un link qui sopra, o copiane uno da qualsiasi parte e Molo te lo propone.",
    "queue.clear": "Pulisci i finiti",
    "queue.active": "In corso adesso",

    "job.cancel": "Ferma",
    "job.retry": "Riprova",
    "job.reveal": "Mostra il file",
    "job.attempt": "tentativo",
    "job.attempts": "tentativi",
    "job.left": "mancano {time}",
    "job.noFile": "Molo non è riuscito a capire dove sia finito il file.",

    "note.attempts": "ci sono voluti {n} tentativi",
    "note.skipped": "questo l'avevi già",
    "note.nocover": "scaricato, ma la copertina non si è attaccata",
    "note.retry": "riprovo ({n}) fra {s}s",
    "note.recover": "recupero: {msg}",
    "note.process": "elaborazione: {name}",
    "note.from": "da “{title}”",

    "state.queued": "in attesa",
    "state.running": "in corso",
    "state.done": "fatto",
    "state.error": "fallito",
    "state.cancelled": "fermato",
    "state.skipped": "saltato",

    "watch.explain": "Un canale o una playlist che Molo controlla da solo, scaricando quello che esce di nuovo. Il primo giro prende soltanto nota di quello che c'è già, così non ti svegli con un archivio intero sul disco.",
    "watch.placeholder": "Indirizzo di un canale o di una playlist",
    "watch.add": "Tieni d'occhio",
    "watch.every30": "ogni 30 minuti",
    "watch.every60": "ogni ora",
    "watch.every360": "ogni 6 ore",
    "watch.every1440": "una volta al giorno",
    "watch.check": "Controlla adesso",
    "watch.remove": "Togli",
    "watch.empty": "Non stai seguendo niente.",
    "watch.known": "{count} noti",
    "watch.lastCheck": "ultimo controllo {when}",
    "watch.never": "mai",
    "watch.new": "{count} nuovi",
    "watch.added": "Aggiunto. Il primo giro prende nota di quello che c'è già senza scaricarlo.",
    "watch.foundNew": "{count} nuovi, messi in coda",
    "watch.nothingNew": "Niente di nuovo",

    "settings.destination": "Destinazione",
    "settings.open": "Apri",
    "settings.downloads": "Download",
    "settings.parallel": "In contemporanea",
    "settings.parallelHint": "Oltre due o tre la banda si divide soltanto e non guadagni niente.",
    "settings.metadata": "Metadati e capitoli nel file",
    "settings.thumbnail": "Copertina nel file",
    "settings.subs": "Sottotitoli incorporati",
    "settings.archive": "Ricorda cosa hai già scaricato",
    "settings.archiveHint": "Evita di riprendere due volte lo stesso video.",
    "settings.automatic": "Automatismi",
    "settings.autoUpdate": "Tieni yt-dlp aggiornato",
    "settings.autoUpdateHint": "Un motore vecchio è di gran lunga la causa più frequente dei download falliti. Quello nuovo si usa dal prossimo avvio.",
    "settings.clipboard": "Proponi i link che copio",
    "settings.network": "Rete",
    "settings.lan": "Raggiungibile dal telefono",
    "settings.lanHint": "Solo dentro la tua rete, con una chiave di accesso. Niente viene esposto su internet.",
    "settings.copy": "Copia",
    "settings.copied": "Link copiato",
    "settings.language": "Lingua",
    "settings.languageAuto": "Segui il sistema",
    "settings.engine": "Motore",
    "settings.updateNow": "Aggiorna yt-dlp adesso",
    "settings.saved": "Salvato",

    "ffmpeg.missing.title": "ffmpeg non è installato",
    "ffmpeg.missing.body": "Senza, Molo non può unire video e audio separati, e resti intorno ai 720p. Tutto il resto funziona.",
    "ffmpeg.missing.how": "Installalo con",

    "shortcuts.title": "Tastiera",
    "shortcuts.settings": "Impostazioni",
    "shortcuts.paste": "Incolla e scarica",
    "shortcuts.focus": "Vai al campo indirizzo",
    "shortcuts.queue": "Vai alla coda",
    "shortcuts.watchers": "Vai ai monitor",
    "shortcuts.help": "Questo elenco",
    "shortcuts.close": "Chiudi",

    "gate.title": "Molo",
    "gate.lead": "Tre cose, poi non te le ripeto più.",
    "gate.p1.b": "Qui dentro non c'è codice per aggirare protezioni.",
    "gate.p1": "Niente CDM, niente chiavi, niente decifratura. Su un flusso cifrato Molo fallisce, e fallisce perché è una cosa che non sa fare.",
    "gate.p2.b": "Quello che scarichi resta responsabilità tua.",
    "gate.p2": "Archiviare le proprie lezioni e piratare un film sono atti diversi, e la differenza la fai tu.",
    "gate.p3.b": "Scaricare può violare i termini di servizio di un sito.",
    "gate.p3": "È una questione contrattuale fra te e quel sito, non un reato.",
    "gate.accept": "Ho capito",
    "gate.more": "Il ragionamento per esteso",

    "token.title": "Serve la chiave",
    "token.body": "Apri Molo dal link che trovi nelle impostazioni sul computer che lo sta eseguendo.",
  },
};

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "it", label: "Italiano" },
];

const I18N = {
  lang: "en",
  LANGUAGES,

  resolve(preference) {
    if (preference && preference !== "auto" && STRINGS[preference]) return preference;
    const system = (navigator.language || "en").slice(0, 2).toLowerCase();
    return STRINGS[system] ? system : "en";
  },

  use(preference) {
    this.lang = this.resolve(preference);
    document.documentElement.lang = this.lang;
    this.apply();
  },

  /** Translation if we have one, otherwise whatever the server sent. */
  tOr(key, fallback) {
    return (STRINGS[this.lang] && STRINGS[this.lang][key]) || STRINGS.en[key] || fallback;
  },

  t(key, vars) {
    let text = (STRINGS[this.lang] && STRINGS[this.lang][key]) || STRINGS.en[key] || key;
    if (vars) {
      for (const [name, value] of Object.entries(vars)) {
        text = text.replaceAll(`{${name}}`, value);
      }
    }
    return text;
  },

  /** Walks the document and fills anything carrying a data-i18n attribute. */
  apply(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = this.t(el.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = this.t(el.dataset.i18nPlaceholder);
    });
    root.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      el.setAttribute("aria-label", this.t(el.dataset.i18nAria));
    });
    root.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = this.t(el.dataset.i18nTitle);
    });
  },
};

window.I18N = I18N;
