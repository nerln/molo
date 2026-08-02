<div align="center">

<img src="molo/web/icons/icon-192.png" width="86" alt="">

# Molo

**Il molo dove attraccano i tuoi video.**
Interfaccia locale per [yt-dlp](https://github.com/yt-dlp/yt-dlp): una coda sola, raggiungibile dal Mac, da Windows e dal telefono.

[Note legali](LEGAL.md) · [Componenti di terze parti](NOTICE.md) · MIT

</div>

---

## Perché un altro downloader

Non lo è, se guardi una piattaforma alla volta: sul desktop ci sono già
[yt-dlp-gui](https://github.com/imsyy/yt-dlp-gui) e
[Open Video Downloader](https://github.com/jely2002/youtube-dl-gui), su Android
[Seal](https://github.com/JunkFood02/Seal) e
[YTDLnis](https://github.com/deniscerri/ytdlnis), sul server
[MeTube](https://github.com/alexta69/metube). Sono progetti seri e non ha senso
rifarli.

Quello che manca è una coda **sola** attraversata da tutti i dispositivi: copi
un link dal telefono, il download parte sul computer che ha disco e banda, e da
qualunque schermo vedi lo stesso stato.

**Se ti serve solo Android e basta, installa Seal.** Fa il lavoro nativamente e
meglio di qualunque cosa possa fare un client remoto. Molo ha senso quando i
dispositivi sono più di uno.

## Cosa fa

- **Massima qualità senza pensarci.** Sceglie da sé la traccia video e audio
  migliori e le unisce. Il preset predefinito produce H.264 + AAC in MP4, che
  si apre ovunque; ce n'è uno per il bitrate più alto in assoluto quando non ti
  importa della compatibilità.
- **Si riprende dagli errori.** Il classico `HTTP 403` a metà scaricamento non
  è un rifiuto: è un URL firmato scaduto. Molo ruota il client YouTube, aspetta
  con backoff crescente e riprende dal punto in cui era, invece di ricominciare.
- **Tiene yt-dlp aggiornato.** È la causa numero uno dei fallimenti: un yt-dlp
  di qualche mese smette e basta di funzionare. Molo controlla all'avvio.
- **Propone i link che copi.** Copi un indirizzo da qualsiasi programma e te lo
  offre. Propone, non scarica: un download automatico a ogni copia riempirebbe
  il disco per sbaglio.
- **Monitor.** Canali e playlist che si controllano da soli e mettono in coda le
  novità. Il primo giro censisce quello che c'è già senza scaricarlo.
- **Riparte dove aveva lasciato.** La coda sta in SQLite: se chiudi a metà, al
  riavvio i download sospesi riprendono dai file parziali.

## Cosa non fa, per scelta

Nel codice non esiste niente per aggirare misure di protezione: nessun modulo
CDM, nessuna chiave, nessuna decifratura. Questo non è configurabile, è un
fatto sul contenuto del repository.

Sopra a quello c'è la **modalità rigorosa**, accesa di default, che respinge in
anticipo i servizi interamente sotto DRM ([`molo/policy.py`](molo/policy.py),
gira prima di ogni download). Si può spegnere dalle impostazioni, e spegnerla
non aggiunge nessuna capacità: senza decifratura un flusso cifrato resta
illeggibile e fallisce comunque, solo più tardi e con un errore peggiore.
Serve a chi ha accesso legittimo a contenuti non cifrati ospitati su domini in
elenco.

Il ragionamento per esteso, con i riferimenti normativi, sta in
[LEGAL.md](LEGAL.md). In breve: scaricare un flusso servito in chiaro non
aggira nessuna protezione, rompere una cifratura sì, ed è illecito di per sé
nell'UE (art. 6 dir. 2001/29/CE) e negli USA (DMCA §1201).

## Installazione

### Build pronte

Le trovi fra i [Release](https://github.com/eugenionerelli/molo/releases). Non sono
firmate con certificati a pagamento, quindi al primo avvio:

- **macOS**: tasto destro sull'app → «Apri» → «Apri».
- **Windows**: SmartScreen → «Ulteriori informazioni» → «Esegui comunque».
- **Android**: va abilitata l'installazione da origini sconosciute.

### Da sorgente

```bash
git clone https://github.com/eugenionerelli/molo && cd molo
python3 -m venv .venv && .venv/bin/pip install -e ".[desktop]"
.venv/bin/python -m molo
```

ffmpeg serve per unire video e audio separati e non è incluso (è GPL, Molo è
MIT — vedi [NOTICE.md](NOTICE.md)):

```bash
brew install ffmpeg
```

Senza, Molo funziona lo stesso ma resta ai formati già completi, di norma
fino a 720p.

## Sul telefono

Tre strade, in ordine di fatica:

1. **Browser.** Impostazioni → «Raggiungibile dal telefono», copi il link con
   il token e lo apri sul telefono. «Aggiungi a schermata Home» e si comporta
   come un'app: è una PWA.
2. **APK.** Un guscio WebView attorno alla stessa interfaccia, per avere
   l'icona nel cassetto delle app. Lo costruisce la CI.
3. **Termux**, se vuoi Molo autonomo senza computer acceso — yt-dlp gira nativo
   su Android: `scripts/termux-install.sh`.

Il server ascolta su `127.0.0.1` finché non attivi tu l'accesso di rete, e in
quel caso ogni richiesta che non arrivi da locale deve portare il token
generato a installazione. Niente esce dalla tua rete.

## Build

```bash
./packaging/build_macos.sh        # .app + .dmg
pyinstaller packaging/molo.spec   # Windows
cd packaging/android && gradle assembleDebug
```

La [CI](.github/workflows/build.yml) fa le tre build a ogni push su `main` e
allega gli artefatti; su un tag `v*` pubblica il Release.

## Architettura

```
molo/policy.py    la guardia legale: gira prima di tutto il resto
molo/engine.py    yt-dlp come libreria, preset, recupero dagli errori
molo/jobs.py      coda persistente, concorrenza, eventi
molo/watch.py     monitor di canali e playlist
molo/server.py    API HTTP + WebSocket, token per l'accesso di rete
molo/web/         interfaccia: HTML, CSS e JS a mano, nessuna build
```

Un solo processo Python. L'interfaccia è la stessa ovunque: la finestra sul
desktop è il WebView di sistema puntato su localhost, non un Chromium
impacchettato, ed è il motivo per cui il bundle sta in 44 MB invece di 200.

L'interfaccia non ha passo di compilazione di proposito: apri `app.js`, cambi
una riga, ricarichi. Chi forka non deve installare niente.

## Limiti noti

- **L'app impacchettata non aggiorna yt-dlp da sola.** Dentro un bundle
  PyInstaller non c'è pip, e Molo te lo dice invece di fallire in silenzio.
  L'installazione da sorgente si aggiorna normalmente. Il rimedio previsto è
  usare yt-dlp come binario esterno sostituibile a caldo.
- **Le build non sono firmate.** La notarizzazione macOS richiede un Developer
  ID a pagamento, la firma Windows un certificato EV.
- **Android sospende i processi in background**: con Termux, per un download
  lungo tieni l'app in primo piano o attiva il wakelock.
- **L'APK Android e l'eseguibile Windows compilano in CI ma nessuno li ha
  ancora *eseguiti*.** Le build sono verdi e gli artefatti esistono; che poi
  l'APK si installi e il WebView si colleghi davvero è un passaggio che
  richiede un telefono e un PC veri. Solo la build macOS è stata avviata e
  usata per un download completo.

## Contribuire

Le richieste di modifica sono benvenute, con un limite netto: niente codice per
aggirare misure di protezione, niente chiavi CDM, niente documentazione che
presenti l'aggiramento di un paywall come caso d'uso. Non è prudenza eccessiva,
è la condizione perché questo progetto possa esistere alla luce del sole —
[LEGAL.md](LEGAL.md) spiega perché.

```bash
pytest tests -q
```

I test di `policy.py` sono i più importanti del progetto: se passano rotti,
Molo smette di essere ciò che dichiara.
