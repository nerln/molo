# Third-party components

Molo is distributed under the MIT licence. The builds also contain the software
listed below, each under its own licence.

| Component | Licence | Bundled |
|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense (public domain) | yes |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | yes |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | yes |
| [uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | yes |
| [pydantic](https://github.com/pydantic/pydantic) | MIT | yes |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | desktop only |
| CPython | PSF Licence 2.0 | yes |
| [ffmpeg](https://ffmpeg.org) | LGPL-2.1+ or GPL-2+ depending on the build | **no, see below** |

## Why ffmpeg is not in the package

The ffmpeg builds in widest circulation are compiled with GPL components.
Including one would extend GPL obligations to the whole package, which is MIT,
and anyone forking Molo would inherit constraints they never chose.

So Molo looks for ffmpeg on the system instead. If it cannot find one, it says
so and keeps working with the formats that do not need separate streams merged,
which usually means up to 720p.

Installing it:

```bash
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
pkg install ffmpeg           # Android, under Termux
sudo apt install ffmpeg      # Debian and Ubuntu
```

Molo looks in `PATH` first and then in the places these package managers
install to, because an app launched from Finder does not inherit the shell's
`PATH` and would otherwise insist that an installed ffmpeg is missing.

## No DRM components

Molo contains no CDM modules, no Widevine components, no keys, and no
decryption code. It does not download any at runtime. See [LEGAL.md](LEGAL.md).
