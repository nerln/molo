# Componenti di terze parti

Molo è distribuito sotto licenza MIT. Le build contengono anche il software
elencato qui sotto, ciascuno con la propria licenza.

| Componente | Licenza | Impacchettato |
|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense (pubblico dominio) | sì |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | sì |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | sì |
| [uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | sì |
| [pydantic](https://github.com/pydantic/pydantic) | MIT | sì |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | solo desktop |
| CPython | PSF License 2.0 | sì |
| [ffmpeg](https://ffmpeg.org) | LGPL-2.1+ / GPL-2+ secondo la build | **no, vedi sotto** |

## Perché ffmpeg non è dentro il pacchetto

Le build di ffmpeg che circolano di più sono compilate con componenti GPL.
Includerne una in Molo estenderebbe gli obblighi della GPL a tutto il pacchetto,
che invece è MIT: chi forka il progetto si ritroverebbe vincoli che non ha
scelto.

Molo quindi cerca ffmpeg nel sistema e, se non lo trova, lo dice e continua a
funzionare con i formati che non richiedono di unire flussi separati (di norma
fino a 720p).

Per installarlo:

```bash
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
pkg install ffmpeg           # Android via Termux
```

## Nessun componente DRM

Molo non contiene, non scarica e non richiama moduli CDM, chiavi Widevine o
codice di decifratura. Vedi [LEGAL.md](LEGAL.md).
