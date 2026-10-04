# New Python compatibility live tests

Tested on October 3, 2026, on Apple Silicon with macOS 27.0. Each interpreter used a separate virtual environment under `/private/tmp`. The normal macro environment and profile were not changed.

| Check | Python 3.10.19 | Python 3.11.8 | Python 3.12.6 |
| --- | --- | --- | --- |
| Dependency installation and `pip check` | Pass | Pass | Pass |
| Actual GUI startup and keyboard listener | Pass | Pass | Pass |
| GUI callbacks and settings save/restore | Pass | Pass | Pass |
| Screen capture and matcher on captured pixels | Pass | Pass | Pass |
| macOS Vision OCR | Pass | Pass | Pass |
| OpenCV conversion and Torch execution | Pass | Pass | Pass |
| Compiled Core ML model inference | Pass after dependency fix | Pass | Pass |

The runtime checks used the real macOS APIs. Screen capture returned a nonblank image, and the native matcher found a crop of that capture. Vision recognized a known phrase rendered with the system Helvetica font. Core ML loaded `sprinkler_detection_standard.mlmodelc` and predicted using its required 736 by 736 image input, returning finite output with shape `(1, 300, 6)`.

Dependencies included NumPy 1.26.4, Torch 2.7.0, torchvision 0.22.0, and coremltools 9.0. No installer certificate modifications or Python system installations were performed. Tests installed the package list into temporary environments rather than running the entire installer command.

## Problems found

Python 3.10 selected SciPy 1.15.3, whose native `_spropack` module failed to load with a malformed Mach-O `__thread_bss` section. This prevented importing coremltools. Installing SciPy 1.14.1 fixed import and actual model inference. The installer now constrains SciPy to that tested version for Python 3.10. A matching failure is documented in [SciPy issue 25635](https://github.com/scipy/scipy/issues/25635).

The modern Python installation path also omitted coremltools. The live environments installed it explicitly, and the installer now includes it for Python 3.10 through 3.12.

## Scope

These tests cover native runtime operations, GUI startup, and frontend/backend communication. They do not cover Intel binaries, older macOS releases, Roblox navigation, or a full gathering session. All test apps were stopped after validation. Launcher regression tests and installer/launcher shell syntax checks also pass.
