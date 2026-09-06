#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT/companion/macos"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
APP_NAME="OpenAI Work + Codex Regulator"
APP_DIR="$ROOT/dist/${APP_NAME}.app"
ZIP_PATH="$ROOT/dist/openai-work-codex-regulator-companion-v${VERSION}-macos.zip"
RELAY_BASE_URL="${REGULATOR_RELAY_BASE_URL:-}"
BUILD_NUMBER="${REGULATOR_BUILD_NUMBER:-${GITHUB_RUN_NUMBER:-1}}"
HELPER_PATH="${REGULATOR_CODEXBAR_HELPER_PATH:-}"

if [[ "$VERSION" != 3.* ]]; then
  echo "macOS Companion packager requires VERSION 3.x" >&2
  exit 1
fi

if [[ -n "$RELAY_BASE_URL" && "$RELAY_BASE_URL" != https://* ]]; then
  echo "REGULATOR_RELAY_BASE_URL must be HTTPS when supplied" >&2
  exit 1
fi

mkdir -p "$ROOT/dist"
rm -rf "$APP_DIR" "$ZIP_PATH"

swift build -c release --package-path "$PACKAGE_DIR"
BIN_DIR="$(swift build -c release --package-path "$PACKAGE_DIR" --show-bin-path)"
BIN_PATH="$BIN_DIR/RegulatorCompanion"

if [[ ! -x "$BIN_PATH" ]]; then
  echo "compiled RegulatorCompanion executable not found: $BIN_PATH" >&2
  exit 1
fi

mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources" "$APP_DIR/Contents/Helpers"
cp "$BIN_PATH" "$APP_DIR/Contents/MacOS/RegulatorCompanion"
chmod 755 "$APP_DIR/Contents/MacOS/RegulatorCompanion"

if [[ -n "$HELPER_PATH" ]]; then
  if [[ ! -x "$HELPER_PATH" ]]; then
    echo "REGULATOR_CODEXBAR_HELPER_PATH is not executable: $HELPER_PATH" >&2
    exit 1
  fi
  cp "$HELPER_PATH" "$APP_DIR/Contents/Helpers/CodexBarCLI"
  chmod 755 "$APP_DIR/Contents/Helpers/CodexBarCLI"
fi

/usr/libexec/PlistBuddy -c 'Clear dict' "$APP_DIR/Contents/Info.plist" 2>/dev/null || true
cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>ru</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleExecutable</key>
  <string>RegulatorCompanion</string>
  <key>CFBundleIdentifier</key>
  <string>io.github.misyukdima.openai-work-codex-regulator.companion</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>RegulatorCompanion</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${BUILD_NUMBER}</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>RegulatorRelayBaseURL</key>
  <string>${RELAY_BASE_URL}</string>
</dict>
</plist>
PLIST

plutil -lint "$APP_DIR/Contents/Info.plist"

# Development artifact only. Production releases require Developer ID signing
# and notarization; ad-hoc signing here exists solely to validate the bundle.
codesign --force --deep --sign - "$APP_DIR"
codesign --verify --deep --strict "$APP_DIR"

if [[ -n "$HELPER_PATH" ]]; then
  test -x "$APP_DIR/Contents/Helpers/CodexBarCLI"
fi

ditto -c -k --sequesterRsrc --keepParent "$APP_DIR" "$ZIP_PATH"

echo "macOS Companion development artifact: $ZIP_PATH"
echo "relay configured: $([[ -n "$RELAY_BASE_URL" ]] && echo yes || echo no)"
echo "sensor helper bundled: $([[ -n "$HELPER_PATH" ]] && echo yes || echo no)"
