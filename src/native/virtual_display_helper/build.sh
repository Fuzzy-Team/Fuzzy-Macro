#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUT_PATH="$ROOT_DIR/src/data/bin/virtual_display_helper_bin"

swiftc \
  "$SCRIPT_DIR/main.swift" \
  -import-objc-header "$SCRIPT_DIR/CGVirtualDisplayPrivate.h" \
  -framework Cocoa \
  -framework CoreGraphics \
  -o "$OUT_PATH"

chmod +x "$OUT_PATH"
echo "Built helper: $OUT_PATH"
