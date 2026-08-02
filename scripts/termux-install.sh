#!/data/data/com.termux/files/usr/bin/bash
# Molo autonomo sul telefono, senza computer acceso.
#
# Termux dà ad Android un ambiente Linux vero, quindi qui yt-dlp gira nativo:
# è la stessa Molo del desktop, non un client remoto.
#
# Installa Termux da F-Droid, non dal Play Store: la versione del Play Store è
# ferma da anni e i pacchetti non si aggiornano più.
#
#   curl -sL https://raw.githubusercontent.com/nerellone/molo/main/scripts/termux-install.sh | bash
set -euo pipefail

echo "==> pacchetti"
pkg update -y
pkg install -y python ffmpeg git

echo "==> accesso alla memoria del telefono"
# Crea ~/storage, così i download finiscono nella cartella Download visibile
# dalla galleria e dal gestore file, non in una cartella interna a Termux.
termux-setup-storage || echo "   (concedi il permesso e rilancia se necessario)"

echo "==> molo"
DIR="$HOME/molo"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --depth 1 https://github.com/nerellone/molo "$DIR"
fi

cd "$DIR"
pip install --upgrade pip
pip install -e .

mkdir -p "$HOME/storage/downloads/Molo" 2>/dev/null || true
python - <<'PY'
from molo import config
s = config.Settings.load()
import os
target = os.path.expanduser("~/storage/downloads/Molo")
if os.path.isdir(os.path.dirname(target)):
    s.update({"download_dir": target, "watch_clipboard": False})  # pbpaste non esiste qui
    print(f"   destinazione: {target}")
PY

cat <<'MSG'

Fatto. Per avviare:

    cd ~/molo && python -m molo --headless

poi apri http://127.0.0.1:7788 nel browser del telefono. Aggiungilo alla
schermata Home e si comporta come un'app.

Nota: Android sospende i processi in background in modo aggressivo. Per un
download lungo tieni Termux in primo piano, oppure attiva il wakelock dalla
notifica di Termux.
MSG
