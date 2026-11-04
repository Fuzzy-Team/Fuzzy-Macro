# Fuzzy Display

Pinned universal helper built from the source commit in manifest.json. The archive preserves executable permissions and contains the upstream MIT notice. Users enable it in Config → Other Settings → Display. It defaults to off and requires macOS 13+.

Build updates in the Fuzzy-Team/Fuzzy-Display repository with bash build.sh, then replace FuzzyDisplay.tar.gz and update both hashes and the source commit in manifest.json. The loader verifies the archive and executable before launch. The extracted app lives under runtime user data so macOS privacy permissions have a stable path across macro starts.

This binary is ad hoc signed, not Developer ID signed or notarized. Live checks on macOS 27.0.1 arm64 passed for display creation, the 1920x1080 game crop at 1x, input, OCR, replacement-client rejoin, preview focus, repeated start/hide/show, negative display origins, both capture paths and placement restoration. Physical Retina hardware, Intel runtime, older macOS releases, sleep/wake and clean-machine Gatekeeper/permission setup remain untested.
