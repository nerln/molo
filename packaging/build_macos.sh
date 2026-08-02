#!/usr/bin/env bash
# Costruisce Molo.app e il DMG. Da lanciare dalla radice del progetto:
#   ./packaging/build_macos.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"

echo "==> icona"
python3 scripts/make_icons.py

# .icns si costruisce da un .iconset con tutte le taglie: sips ridimensiona,
# iconutil impacchetta. Sono strumenti di sistema, niente da installare.
ICONSET="packaging/icon.iconset"
rm -rf "$ICONSET" && mkdir -p "$ICONSET"
for size in 16 32 64 128 256 512; do
  sips -z $size $size molo/web/icons/icon-512.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z $double $double molo/web/icons/icon-512.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o packaging/icon.icns
rm -rf "$ICONSET"

echo "==> bundle"
rm -rf build dist
"$PY" -m PyInstaller packaging/molo.spec --noconfirm --distpath dist --workpath build

APP="dist/Molo.app"
[ -d "$APP" ] || { echo "Bundle non prodotto"; exit 1; }

# Firma ad-hoc: non è la notarizzazione (serve un Developer ID a pagamento) ma
# evita che macOS uccida il processo su Apple Silicon per firma assente.
echo "==> firma ad-hoc"
codesign --force --deep --sign - "$APP" 2>/dev/null || echo "   (codesign non riuscito, l'app parte comunque col primo avvio manuale)"

echo "==> dmg"
DMG="dist/Molo-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)-macos-$(uname -m).dmg"
rm -f "$DMG"
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Molo" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo
echo "Fatto:"
du -sh "$APP" "$DMG" | sed 's/^/   /'
echo
echo "Al primo avvio macOS dirà che l'app non è verificata perché non è"
echo "notarizzata. Tasto destro sull'app, «Apri», e poi «Apri» di nuovo."
