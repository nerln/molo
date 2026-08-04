#!/usr/bin/env bash
# Sign, notarise and staple Molo.app for Developer ID distribution.
#
# This is the realistic way to ship a Mac app like this one. It removes the
# right-click-then-Open dance and the "unidentified developer" warning, and it
# is not the App Store; APPSTORE.md explains why that is a different question.
#
# You need a paid Apple Developer account, a "Developer ID Application"
# certificate in your keychain, and an app-specific password stored once:
#
#   xcrun notarytool store-credentials molo-notary \
#       --apple-id you@example.com --team-id ABCDE12345 --password xxxx-xxxx-xxxx-xxxx
#
# Then:
#
#   IDENTITY="Developer ID Application: Your Name (ABCDE12345)" \
#   PROFILE=molo-notary ./packaging/sign_and_notarize.sh
set -euo pipefail

cd "$(dirname "$0")/.."

APP="dist/Molo.app"
IDENTITY="${IDENTITY:-}"
PROFILE="${PROFILE:-molo-notary}"
ENTITLEMENTS="packaging/entitlements-devid.plist"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
DMG="dist/Molo-${VERSION}-macos-$(uname -m).dmg"

if [ -z "$IDENTITY" ]; then
  echo "Set IDENTITY to your Developer ID Application certificate. Available:" >&2
  security find-identity -v -p codesigning | sed 's/^/  /' >&2
  exit 1
fi
[ -d "$APP" ] || { echo "No $APP. Run ./packaging/build_macos.sh first." >&2; exit 1; }

echo "==> signing every nested binary, innermost first"
# Order matters: a bundle is sealed after its contents, so signing the outer
# app before the dylibs inside it invalidates the signature immediately.
find "$APP/Contents" \( -name "*.dylib" -o -name "*.so" -o -perm +111 -type f \) -print0 |
  while IFS= read -r -d '' f; do
    case "$f" in *.py|*.txt|*.json|*.css|*.js|*.html) continue ;; esac
    codesign --force --timestamp --options runtime \
             --entitlements "$ENTITLEMENTS" --sign "$IDENTITY" "$f" 2>/dev/null || true
  done

echo "==> signing the bundle"
codesign --force --timestamp --options runtime \
         --entitlements "$ENTITLEMENTS" --sign "$IDENTITY" "$APP"

echo "==> verifying before we waste a notarisation round trip"
codesign --verify --deep --strict --verbose=2 "$APP"
spctl --assess --type execute --verbose "$APP" || echo "   (spctl will pass only after stapling)"

echo "==> packaging"
rm -f "$DMG"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Molo" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"
codesign --force --timestamp --sign "$IDENTITY" "$DMG"

echo "==> notarising, which takes a few minutes"
xcrun notarytool submit "$DMG" --keychain-profile "$PROFILE" --wait

echo "==> stapling"
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"

echo
echo "Done: $DMG"
echo "It now opens with a double click on a machine that has never seen it."
