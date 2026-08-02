"""Avvio di Molo.

Due modalità, stesso server:

    molo              finestra nativa sul desktop
    molo --headless   solo server, da aprire nel browser (o dal telefono)

La finestra nativa usa il WebView del sistema: WKWebView su macOS, WebView2 su
Windows. Nessun Chromium impacchettato, quindi il bundle resta sotto i 40 MB
invece dei 200 di una app Electron.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time

import uvicorn

from . import config


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(preferred: int) -> int:
    for candidate in range(preferred, preferred + 12):
        if _port_free(candidate):
            return candidate
    return 0  # lascia scegliere al sistema


def _wait_until_up(port: int, timeout: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.15)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="molo", description="Interfaccia locale per yt-dlp")
    parser.add_argument("--headless", action="store_true", help="solo server, senza finestra")
    parser.add_argument("--port", type=int, default=None, help="porta da usare")
    parser.add_argument("--host", default=None, help="indirizzo di ascolto")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(f"Molo {config.VERSION}")
        return 0

    from . import server  # importato qui: crea la cartella dati al primo tocco

    settings = server.settings
    port = args.port or _pick_port(settings.port)
    if port != settings.port and not args.port:
        settings.update({"port": port})  # la porta preferita era occupata

    host = args.host or ("0.0.0.0" if settings.allow_lan else "127.0.0.1")

    uv = uvicorn.Server(
        uvicorn.Config(server.app, host=host, port=port, log_level="warning", access_log=False)
    )

    if args.headless:
        print(f"Molo su http://127.0.0.1:{port}")
        if settings.allow_lan:
            print(f"Dal telefono: {server.lan_url()}/?token={settings.token}")
        uv.run()
        return 0

    # La finestra deve stare sul thread principale (obbligatorio su macOS),
    # quindi è il server ad andare in un thread di servizio.
    thread = threading.Thread(target=uv.run, daemon=True, name="molo-server")
    thread.start()

    if not _wait_until_up(port):
        print("Il server non è partito.", file=sys.stderr)
        return 1

    try:
        import webview
    except ImportError:
        print(f"pywebview non è installato. Molo gira comunque su http://127.0.0.1:{port}")
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        return 0

    window = webview.create_window(
        "Molo",
        f"http://127.0.0.1:{port}",
        width=1000,
        height=760,
        min_size=(620, 540),
        background_color="#202124",
        # Translucenza di sistema dietro la finestra: su macOS è quel filo di
        # profondità che distingue un'app nativa da un sito dentro una cornice.
        # Su altre piattaforme pywebview lo ignora.
        vibrancy=sys.platform == "darwin",
    )
    webview.start()

    uv.should_exit = True
    thread.join(timeout=6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
