#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK="$ROOT/companion/auth/codex-rust-v0.153.4.json"
OUTPUT="${1:-$ROOT/dist/codex}"
LICENSE_DIR="${2:-$ROOT/dist/codex-license}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/regulator-codex-auth.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

if [[ ! -f "$LOCK" ]]; then
  echo "Codex auth-helper lock file missing: $LOCK" >&2
  exit 1
fi

read_lock() {
  local section="$1"
  local key="$2"
  local field="${3:-}"
  python3 - "$LOCK" "$section" "$key" "$field" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
value = data[sys.argv[2]][sys.argv[3]]
if sys.argv[4]:
    value = value[sys.argv[4]]
print(value)
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
    echo "OpenAI Codex auth-helper checksum mismatch for $arch" >&2
    echo "expected: $sha" >&2
    echo "actual:   $actual" >&2
    exit 1
  fi

  tar -xzf "$archive" -C "$dir"
  binary="$(find "$dir" -type f \( -name 'codex' -o -name 'codex-*-apple-darwin' \) | head -n 1 || true)"
  if [[ -z "$binary" ]]; then
    echo "OpenAI Codex executable not found in $arch artifact" >&2
    exit 1
  fi
  chmod 755 "$binary"
  printf '%s\n' "$binary"
}

ARM_BIN="$(fetch_arch macos-arm64)"
INTEL_BIN="$(fetch_arch macos-x86_64)"
mkdir -p "$(dirname "$OUTPUT")" "$LICENSE_DIR"
lipo -create "$ARM_BIN" "$INTEL_BIN" -output "$OUTPUT"
chmod 755 "$OUTPUT"

ARCHS="$(lipo -archs "$OUTPUT")"
if [[ "$ARCHS" != *arm64* || "$ARCHS" != *x86_64* ]]; then
  echo "universal OpenAI Codex helper missing required architectures: $ARCHS" >&2
  exit 1
fi

codesign --force --sign - "$OUTPUT"
codesign --verify --strict "$OUTPUT"

LICENSE_URL="$(read_lock license_files license)"
NOTICE_URL="$(read_lock license_files notice)"
curl --fail --location --silent --show-error --retry 3 "$LICENSE_URL" --output "$LICENSE_DIR/OpenAI-Codex-LICENSE.txt"
curl --fail --location --silent --show-error --retry 3 "$NOTICE_URL" --output "$LICENSE_DIR/OpenAI-Codex-NOTICE.txt"

grep -q 'Apache License' "$LICENSE_DIR/OpenAI-Codex-LICENSE.txt"
grep -q 'OpenAI Codex' "$LICENSE_DIR/OpenAI-Codex-NOTICE.txt"

echo "pinned universal OpenAI Codex auth helper ready: $OUTPUT"
echo "architectures: $ARCHS"
echo "license bundle: $LICENSE_DIR"
