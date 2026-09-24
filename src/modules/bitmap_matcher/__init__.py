"""
Bitmap Matcher - loads the compiled extension built for this Python version and CPU
"""
import sys
import platform
from pathlib import Path
import importlib.util
import subprocess

ARCHITECTURES = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}


def find_compatible_so():
    """Return the path of the extension for this Python version and CPU, or None."""
    arch = platform.machine().lower()
    arch = ARCHITECTURES.get(arch, arch)
    so_path = Path(__file__).parent / f"bitmap_matcher_py{sys.version_info.major}{sys.version_info.minor}_{arch}.so"
    return so_path if so_path.exists() else None


def load_bitmap_matcher():
    """Load the bitmap_matcher extension module."""
    so_path = find_compatible_so()
    if so_path is None:
        available = ", ".join(f.name for f in Path(__file__).parent.glob("*.so"))
        raise ImportError(
            f"No bitmap_matcher extension for Python {sys.version_info.major}.{sys.version_info.minor} "
            f"on {platform.machine()}. Available: {available}"
        )

    # clear the download quarantine flag, otherwise macOS refuses to load the unsigned extension
    subprocess.run(["xattr", "-cr", str(so_path)])

    spec = importlib.util.spec_from_file_location("bitmap_matcher", so_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _bitmap_matcher = load_bitmap_matcher()
    __all__ = [name for name in dir(_bitmap_matcher) if not name.startswith('_')]
    for name in __all__:
        globals()[name] = getattr(_bitmap_matcher, name)

except ImportError as e:
    print(f"Warning: {e}")
    print("bitmap_matcher extension not available.")

    # keep imports working and fail with a clear error when a function is used
    def _unavailable(*args, **kwargs):
        raise RuntimeError("bitmap_matcher extension is not loaded")

    __all__ = ["find_bitmap_cython", "find_all_bitmap_cython", "create_bitmap_from_base64"]
    for name in __all__:
        globals()[name] = _unavailable
