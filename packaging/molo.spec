# PyInstaller — spec unico per macOS e Windows.
#   pyinstaller packaging/molo.spec --noconfirm
#
# yt-dlp carica gli estrattori in modo pigro e uvicorn i suoi protocolli per
# nome: PyInstaller non li vede seguendo gli import, quindi vanno raccolti a
# mano o l'app parte e poi esplode al primo download.

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# I percorsi dentro lo spec vengono risolti rispetto alla cartella dello spec,
# non a quella da cui lanci il comando: senza questo ancoraggio la build cerca
# `packaging/molo/web` e si ferma.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

hidden = (
    collect_submodules("yt_dlp")
    + collect_submodules("uvicorn")
    + ["fastapi", "starlette", "anyio", "websockets", "watchfiles", "h11", "httptools"]
)

datas = [(os.path.join(ROOT, "molo", "web"), "molo/web")] + collect_data_files("yt_dlp")

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest", "setuptools"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Molo",
    console=False,
    icon=os.path.join(SPECPATH, "icon.icns" if sys.platform == "darwin" else "icon.ico"),
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,  # UPX rompe le firme su macOS e insospettisce gli antivirus su Windows
    name="Molo",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Molo.app",
        icon=os.path.join(SPECPATH, "icon.icns"),
        bundle_identifier="dev.molo.app",
        info_plist={
            "CFBundleShortVersionString": "0.2.0",
            "CFBundleVersion": "0.2.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            # Molo parla solo con 127.0.0.1: senza questa eccezione ATS
            # bloccherebbe il WebView su HTTP in chiaro.
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        },
    )
