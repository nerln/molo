"""Starting Molo.

Two modes, same server:

    molo              a native window on the desktop
    molo --headless   server only, to open in a browser (or from a phone)

The native window uses the system WebView: WKWebView on macOS, WebView2 on
Windows. No bundled Chromium, which is why the build stays around 40 MB
instead of the 200 an Electron app would cost.
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
    return 0  # let the OS pick one


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
    parser = argparse.ArgumentParser(prog="molo", description="A local interface for yt-dlp")
    parser.add_argument("--headless", action="store_true", help="server only, no window")
    parser.add_argument("--port", type=int, default=None, help="port to listen on")
    parser.add_argument("--host", default=None, help="address to bind")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(f"Molo {config.VERSION}")
        return 0

    from . import server  # imported here: it creates the data folder on first touch

    settings = server.settings
    port = args.port or _pick_port(settings.port)
    if port != settings.port and not args.port:
        settings.update({"port": port})  # the preferred port was taken

    host = args.host or ("0.0.0.0" if settings.allow_lan else "127.0.0.1")

    uv = uvicorn.Server(
        uvicorn.Config(server.app, host=host, port=port, log_level="warning", access_log=False)
    )

    if args.headless:
        print(f"Molo at http://127.0.0.1:{port}")
        if settings.allow_lan:
            print(f"From your phone: {server.lan_url()}/?token={settings.token}")
        uv.run()
        return 0

    # The window has to live on the main thread (mandatory on macOS), so it is
    # the server that goes onto a worker thread.
    thread = threading.Thread(target=uv.run, daemon=True, name="molo-server")
    thread.start()

    if not _wait_until_up(port):
        print("The server did not start.", file=sys.stderr)
        return 1

    try:
        import webview
    except ImportError:
        print(f"pywebview is not installed. Molo is still running at http://127.0.0.1:{port}")
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
        # System translucency behind the window. On macOS it is the sliver of
        # depth that separates a native app from a site in a frame. Other
        # platforms ignore it.
        vibrancy=sys.platform == "darwin",
    )
    webview.start()

    uv.should_exit = True
    thread.join(timeout=6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
