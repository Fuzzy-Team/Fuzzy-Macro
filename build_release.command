#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

/bin/bash "./build_app.command"

PKG_ROOT="${TMPDIR:-/tmp}/fuzzy-macro-pkgroot"
RELEASE_SUFFIX="${FUZZY_RELEASE_SUFFIX:-Installer}"
PKG_PATH="dist/Fuzzy Macro ${RELEASE_SUFFIX}.pkg"

rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/Applications"

ditto --norsrc --noextattr "dist/Fuzzy Macro.app" "$PKG_ROOT/Applications/Fuzzy Macro.app"

pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "com.fuzzyteam.fuzzymacro.pkg" \
    --version "0.0.0" \
    --install-location "/" \
    "$PKG_PATH"

printf "\nRelease package complete: %s/%s\n" "$(pwd)" "$PKG_PATH"
