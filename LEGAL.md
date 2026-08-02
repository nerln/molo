# Note legali

**Non è una consulenza legale.** Chi scrive non è un avvocato. Questo documento
spiega su quali basi Molo è progettato e distribuito, perché chi lo usa o lo
forka possa giudicare da sé invece di fidarsi.

---

## La linea, e perché è tracciata lì

Un programma non può sapere se hai il diritto di scaricare un certo file.
Dipende da chi sei, da che accordi hai con la fonte, dal paese in cui ti trovi
e da cosa ne farai. Nessun controllo automatico può decidere al posto tuo.

C'è però una distinzione che un programma **può** applicare, ed è quella su cui
si regge tutto il resto: la differenza fra leggere un flusso servito in chiaro e
rompere una cifratura.

**Flusso in chiaro.** Il tuo browser lo scarica già: è così che riproduce un
video. Salvarlo su disco invece che nella cache non aggira nessuna protezione
tecnica. Può violare i termini di servizio del sito, e quella è una questione
contrattuale fra te e quel sito, non un reato.

**Flusso cifrato con DRM** (Widevine, PlayReady, FairPlay). Per arrivare al
video bisogna rompere la cifratura. Quell'atto è colpito di per sé:

- **Unione europea**: art. 6 della direttiva 2001/29/CE, recepito in Italia
  dall'art. 102-quater della legge 633/1941.
- **Stati Uniti**: DMCA §1201.

La violazione è nell'aggiramento, non nell'uso che poi fai del file. Anche
scaricare per sé un contenuto per cui paghi l'abbonamento resterebbe un
aggiramento.

**Molo non contiene codice per aggirare protezioni.** Non c'è nessun modulo
CDM, nessuna chiave, nessuna routine di decifratura, e non ne verranno
accettati. Questo è il punto fermo, e non è configurabile: è un fatto sul
contenuto del repository, verificabile leggendolo.

Sopra a quel punto fermo c'è un pre-controllo, in
[`molo/policy.py`](molo/policy.py), che gira prima di ogni download:

1. Sull'indirizzo, prima ancora di toccare la rete: i servizi il cui catalogo è
   interamente sotto DRM vengono respinti con un messaggio esplicito.
2. Sui metadati restituiti da yt-dlp: se il contenuto risulta protetto
   (`has_drm`), il job si ferma subito. Vale anche per i siti mai visti prima.

Questo pre-controllo è la **modalità rigorosa**, attiva per impostazione
predefinita, ed è disattivabile dalle impostazioni. Vale la pena essere precisi
su cosa cambia, perché è meno di quanto il nome suggerisca.

Spegnendola non compare nessuna capacità nuova. yt-dlp non sa decifrare
Widevine, PlayReady o FairPlay: su un flusso cifrato fallisce, e fallisce
perché quella cosa non la sa fare nessun pezzo di questo programma. L'unica
differenza pratica è **chi ti dice di no e con che parole**: prima Molo, in
anticipo e con una spiegazione; dopo yt-dlp, più tardi e con un errore secco.

Serve a un caso reale e legittimo: avere accesso a contenuti ospitati su domini
presenti in elenco ma non cifrati — una lezione comprata, un proprio
caricamento, un video pubblico su una piattaforma che altrove usa DRM. Un
elenco di domini è un'approssimazione, e le approssimazioni vanno poter essere
disattivate da chi sa cosa sta facendo.

Va detto anche l'ovvio: un elenco di host in un file di testo non è una
barriera di sicurezza. Chiunque forki il progetto lo cancella in dieci secondi.
Non è lì per impedire, è lì perché il comportamento predefinito dello strumento
sia coerente con quello che il progetto dichiara. La difesa vera è l'altra: non
esiste codice di aggiramento da nessuna parte.

---

## Il precedente che conta

Nell'ottobre 2020 la RIAA chiese a GitHub di rimuovere youtube-dl invocando il
DMCA §1201. GitHub lo rimosse. La Electronic Frontier Foundation rispose per
conto dei manutentori sostenendo che lo strumento non aggira alcuna misura
tecnologica di protezione e ha usi legittimi sostanziali. **Il 16 novembre 2020
GitHub ripristinò il repository** e istituì un fondo da un milione di dollari
per la difesa degli sviluppatori in casi analoghi.

Due principi da quella vicenda, che qui sono scelte progettuali e non slogan:

**Usi legittimi sostanziali.** Dalla dottrina di *Sony Corp. of America v.
Universal City Studios* (1984): uno strumento capace di usi legittimi
sostanziali non è responsabile per contributo alla violazione solo perché
qualcuno lo usa male. Molo di usi legittimi ne ha molti, e non sono pretesti:
archiviare le proprie lezioni, conservare i propri caricamenti, salvare
materiale in licenza aperta, ricerca su corpora video, accessibilità, backup di
contenuti pubblici che spariscono.

**L'induzione conta.** Da *MGM Studios v. Grokster* (2005): chi promuove uno
strumento **per** violare il diritto d'autore risponde di quella promozione,
per quanto neutro sia il codice. È il motivo per cui questo progetto non
menziona da nessuna parte servizi in abbonamento come casi d'uso, non pubblica
guide per aggirare paywall, e non accetta contributi che vadano in quella
direzione. Non è timidezza: è la differenza fra un caso difendibile e uno perso
in partenza.

---

## Italia, copia privata: attenzione a non fraintendere

L'art. 71-sexies della legge 633/1941 consente la riproduzione privata di
fonogrammi e videogrammi per uso esclusivamente personale, senza scopo di lucro
e senza fini direttamente o indirettamente commerciali (a fronte dell'equo
compenso dell'art. 71-septies, quello già incluso nel prezzo di dischi e
memorie).

**Ma il quarto comma dello stesso articolo esclude dalla copia privata le opere
protette da misure tecnologiche di protezione e quelle messe a disposizione su
richiesta ("on demand") a condizioni contrattuali concordate.** Quindi la copia
privata non è un lasciapassare per i servizi in streaming in abbonamento: è
proprio il caso che l'eccezione lascia fuori.

Detto in breve: non esiste una scorciatoia per cui "in Italia si può". Esiste un
perimetro, e Molo è costruito per stare dentro quel perimetro nella parte che
un programma può controllare.

---

## Scelte di distribuzione

**ffmpeg non è impacchettato.** Le build più diffuse sono compilate sotto GPL:
distribuirle dentro Molo estenderebbe gli obblighi GPL all'intero pacchetto,
che è MIT. Molo rileva ffmpeg se c'è e ti dice come installarlo se manca. È
anche il motivo per cui le build pesano poche decine di MB.

**yt-dlp è una dipendenza, non un fork.** yt-dlp è di pubblico dominio
(Unlicense) e si aggiorna ogni pochi giorni: un fork significherebbe
rincorrerlo per sempre e perdere i suoi fix. Molo lo installa e lo aggiorna
come qualunque altra libreria.

**Nessuna chiave, nessun modulo di decifratura.** Il repository non contiene
chiavi CDM, moduli Widevine o codice di decifratura, e non ne accetterà.

**Nessun marchio altrui.** Molo non usa nomi, loghi o icone di piattaforme
video, e non si presenta come autorizzato o affiliato a nessuna di esse.

**Nessun contenuto protetto nei test.** I test usano contenuti in licenza
aperta o materiale generato al momento.

---

## Se ricevi una segnalazione

Se sei un titolare di diritti e ritieni che questo repository violi qualcosa,
apri una issue o scrivi al recapito indicato nel README. Le segnalazioni
motivate ricevono risposta. Le richieste generiche di rimozione fondate sul
fatto che il software *possa* essere usato male incontreranno le ragioni
esposte qui sopra.

---

## In una riga

Molo non aggira protezioni, non è promosso per violare il diritto d'autore, e
non decide al posto tuo se hai il diritto di scaricare quel file. Quella parte
resta tua.
