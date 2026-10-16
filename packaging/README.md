# macOS app build

The PyInstaller spec builds an Apple Silicon app for macOS 13 or later with Python 3.9 and the dependencies from `install_dependencies.command`. Install PyInstaller and html2image in the build environment, then run from the repository root:

```sh
python -m PyInstaller --noconfirm --distpath dist --workpath build/macos packaging/macos.spec
```

The result is `dist/Fuzzy Macro.app`. It includes Python, Tk, the native interface, artwork, bundled fonts, the bitmap matcher, and Core ML support. AI models download through the existing model manager on first normal startup. Hourly reports still use an installed Chrome or Chromium, and public streaming still uses an installed cloudflared.

The app keeps its profiles, patterns, downloaded models, and runtime data in `~/Library/Application Support/Fuzzy Macro`. Logs go to `~/Library/Logs/Fuzzy Macro/app.log`. Existing exported profiles can be imported through Config. Source installations keep their existing data locations.

Before loading input-control libraries, the app requests Accessibility access. If access is missing, a window offers to open Accessibility settings and waits until permission is enabled. Quitting that window cancels startup safely.

The source updater cannot replace compiled code. App builds require replacing the `.app` with a newer build. The local build is ad-hoc signed; it is not an Apple-notarized distribution.

Run the isolated bundle check without starting automation or changing real user data:

```sh
"dist/Fuzzy Macro.app/Contents/MacOS/Fuzzy Macro" --smoke-test
```

This checks engine imports, Core ML, the bitmap matcher, multiprocessing, and construction and refresh of all nine native tabs against temporary settings. It does not test automation against Roblox or run model inference.
