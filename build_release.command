#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

/bin/bash "./build_app.command"

PKG_ROOT="${TMPDIR:-/tmp}/fuzzy-macro-pkgroot"
PKG_WORK="${TMPDIR:-/tmp}/fuzzy-macro-pkgwork"
RELEASE_SUFFIX="${FUZZY_RELEASE_SUFFIX:-Installer}"
PKG_PATH="dist/Fuzzy Macro ${RELEASE_SUFFIX}.pkg"
COMPONENT_PKG="$PKG_WORK/Fuzzy Macro Component.pkg"
DISTRIBUTION_XML="$PKG_WORK/Distribution.xml"
TARGET_ARCH="${FUZZY_TARGET_ARCH:-$(uname -m)}"

if [ "$TARGET_ARCH" = "arm64" ]; then
    MIN_MACOS="${FUZZY_MIN_MACOS:-13.0}"
else
    MIN_MACOS="${FUZZY_MIN_MACOS:-10.12}"
fi

rm -rf "$PKG_ROOT"
rm -rf "$PKG_WORK"
mkdir -p "$PKG_ROOT/Applications"
mkdir -p "$PKG_WORK"

ditto --norsrc --noextattr "dist/Fuzzy Macro.app" "$PKG_ROOT/Applications/Fuzzy Macro.app"

pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "com.fuzzyteam.fuzzymacro.${TARGET_ARCH}.pkg" \
    --version "0.0.0" \
    --install-location "/" \
    "$COMPONENT_PKG"

cat > "$DISTRIBUTION_XML" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>Fuzzy Macro</title>
    <options customize="never" require-scripts="false"/>
    <allowed-os-versions>
        <os-version min="${MIN_MACOS}"/>
    </allowed-os-versions>
    <pkg-ref id="com.fuzzyteam.fuzzymacro.${TARGET_ARCH}.pkg"/>
    <choices-outline>
        <line choice="default"/>
    </choices-outline>
    <choice id="default" title="Fuzzy Macro">
        <pkg-ref id="com.fuzzyteam.fuzzymacro.${TARGET_ARCH}.pkg"/>
    </choice>
    <pkg-ref id="com.fuzzyteam.fuzzymacro.${TARGET_ARCH}.pkg" version="0.0.0" onConclusion="none">Fuzzy Macro Component.pkg</pkg-ref>
</installer-gui-script>
EOF

productbuild \
    --distribution "$DISTRIBUTION_XML" \
    --package-path "$PKG_WORK" \
    "$PKG_PATH"

printf "\nRelease package complete: %s/%s\nArchitecture: %s\nMinimum macOS: %s\n" "$(pwd)" "$PKG_PATH" "$TARGET_ARCH" "$MIN_MACOS"
