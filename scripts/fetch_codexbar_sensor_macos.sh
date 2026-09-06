#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK="$ROOT/companion/sensors/codexbar-v0.56.7.json"
OUTPUT="${1:-$ROOT/dist/CodexBarCLI}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/regulator-codexbar.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

if [[ ! -f "$LOCK" ]]; then
  echo "sensor lock file missing: $LOCK" >&2
  exit 1
fi

read_lock() {
  python3 - "$LOCK" "$1" "$2" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
print(data["artifacts"][sys.argv[2]][sys.argv[3]])
PY
}

fetch_arch() {
  local arch="$1"
  local dir="$WORK/$arch"
  local archive="$WORK/$arch.tar.gz"
  local url sha actual binary
  mkdir -p "$dir"
  url="$(read_lock artifacts "$arch" url)"
  sha="$(read_lock artifacts "$arch" sha256)"

  curl --fail --location --silent --show-error --retry 3 --retry-delay 2 "$url" --output "$archive"
  actual="$(shasum -a 256 "$archive" | awk '{print $1}')"
  if [[ "$actual" != "$sha" ]]; then
    echo "CodexBar sensor checksum mismatch for $arch" >&2
    echo "expected: $sha" >&2
    echo "actual:   $actual" >&2
    exit 1
  fi

  tar -xzf "$archive" -C "$dir"
  binary="$(find "$dir" -type f \( -name 'CodexBarCLI' -o -name 'codexbar' \) -perm -111 | head -n 1 || true)"
  if [[ -z "$binary" ]]; then
    echo "CodexBar executable not found in $arch artifact" >&2
    exit 1
  fi
  printf '%s\n' "$binary"
}

ARM_BIN="$(fetch_arch macos-arm64)"
INTEL_BIN="$(fetch_arch macos-x86_64)"
mkdir -p "$(dirname "$OUTPUT")"
lipo -create "$ARM_BIN" "$INTEL_BIN" -output "$OUTPUT"
chmod 755 "$OUTPUT"

ARCHS="$(lipo -archs "$OUTPUT")"
if [[ "$ARCHS" != *arm64* || "$ARCHS" != *x86_64* ]]; then
  echo "universal CodexBar helper missing required architectures: $ARCHS" >&2
  exit 1
fi

codesign --force --sign - "$OUTPUT"
codesign --verify --strict "$OUTPUT"

echo "pinned universal CodexBar sensor ready: $OUTPUT"
echo "architectures: $ARCHS"
