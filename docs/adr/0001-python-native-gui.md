# Replace the web interface with a Python desktop GUI

Fuzzy Macro will use desktop widgets without HTML, JavaScript, a webview, or a browser runtime for its configuration interface. The current web UI remains the visual specification for layout, colors, typography, tabs, and controls; standard OS title bars and file dialogs are acceptable. This requires rebuilding the interface rather than embedding the existing pages.

The port must preserve support for the current macOS configurations and Windows beta, existing profiles and settings, custom patterns, launch commands, and macro behavior. Windows scope covers the GUI and preservation of existing beta behavior; a broader Windows macro-engine port is separate work because this checkout imports macOS-only APIs during startup.

Start with Tkinter/ttk and custom styling. Verify the appearance of representative screens before porting the remaining interface. The finished GUI must cover all nine tabs, all eleven themes, profile management, drag ordering, hotkey recording, logs, reports, and update progress, then replace the web GUI completely.

Closing the native window shuts down the macro, active tools, Discord process, streaming, and standby, then exits. There is no tray or background mode. Visual acceptance requires matching layout, spacing, colors, bundled fonts, and assets, with small differences in OS text rendering allowed. Compare Home and Gather first.

Reference captures showed that the browser ignores the existing font import and renders system fonts. The native GUI deliberately uses the intended Poppins and Libre Franklin faces, bundled for offline use, following the user's choice after reviewing that difference.

## Compatibility constraints

The installer targets Intel Macs running macOS 10.12-10.14 with Python 3.7, Intel Macs running macOS 10.15 or later with Python 3.8, and Apple Silicon Macs running macOS 13 or later with Python 3.9. These are source-defined targets, not verified compatibility results. The Windows beta's OS, Python, and architecture requirements are not established in this checkout.

Preserve the existing settings manager, file formats, defaults, value types, profile import/export formats, custom patterns, and shared runtime data. Preserve save timing and validation from the web interface, including behavior implemented in JavaScript. Keep the existing source distribution and launch commands.

## Runtime integration

The native GUI must service the existing supervisor, worker processes, Discord commands, standby timers, logs, and tool status without blocking input. Replace Eel calls in the runtime with direct Python GUI operations, including explicit hotkey-recording state. Keep widget updates on the GUI thread and retain the existing macro control states and cleanup behavior.

## Verification

Compare representative native screens against the current web interface before completing the port. Check every tab and theme, scrolling, resizing, display scaling, dialogs, drag ordering, keybind recording, and profile switching. Exercise settings and import/export against temporary copies of existing-format data.

Run the existing standby tests and add checks for the changed GUI/runtime integration. Test GUI construction and interactions without starting automation or modifying real user data. Record which platform and interpreter combinations were actually exercised; syntax checks alone do not establish OS compatibility.

The implemented interface uses Tkinter widgets with process-local bundled fonts. Eel is removed from the GUI, supervisor, Discord callbacks, and installer dependencies. Existing report rendering and Flask streaming remain separate from the configuration window.

Validation on October 14, 2026 used macOS 27 on Apple Silicon, Python 3.9.8, and Tk 8.6.11. All 152 tests passed, including an opt-in native rendering test for tab switching, refresh, window resizing, visible headings, and sidebar repainting. Source differential tests cover settings definitions, task ordering, calculators, and import behavior. Runtime tests cover supervisor states and cleanup; automation itself was not started.

Isolated native windows used temporary profiles and runtime data. Visual checks covered all nine tabs, their subtabs, all eleven themes, manual and automatic planters, token dialogs, guides, scrolling, and narrow layouts. Home and Gather were compared with captures of the shipped web UI. The intended bundled fonts change text metrics from the browser's system-font fallback.

The changed production modules parse with Python 3.7, 3.8, and 3.9 grammar, and launch-script syntax checks pass. Windows and the older supported macOS versions were not run on this machine; their compatibility still requires testing on those systems.
