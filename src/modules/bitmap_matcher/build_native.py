#!/usr/bin/env python3
"""Build the bundled bitmap_matcher Cython extension for the current interpreter."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def get_python_version():
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def get_architecture():
    arch = platform.machine().lower()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "i386": "x86",
        "i686": "x86",
    }
    return arch_map.get(arch, arch)


def ensure_build_dependencies():
    required = ("setuptools", "Cython", "numpy")
    missing = []
    for package in required:
        module_name = "Cython" if package == "Cython" else package
        try:
            __import__(module_name)
        except ImportError:
            missing.append(package if package != "Cython" else "cython")

    if not missing:
        return True

    print(f"Installing bitmap_matcher build dependencies: {', '.join(missing)}")
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "setuptools",
                "wheel",
                "cython",
                "numpy<2",
            ],
            cwd=str(PACKAGE_DIR),
        )
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install build dependencies: {exc}")
        return False


def _collect_built_extensions():
    version_tag = f"cpython-{get_python_version().replace('.', '')}"
    candidates = []

    for pattern in ("bitmap_matcher*.so", "bitmap_matcher*.pyd"):
        for path in PACKAGE_DIR.glob(pattern):
            if version_tag in path.name or path.suffix.lower() == ".pyd":
                candidates.append(path)
            elif path.name in ("bitmap_matcher.so", "bitmap_matcher.pyd"):
                candidates.append(path)

    build_root = PACKAGE_DIR / "build"
    if build_root.exists():
        for pattern in ("bitmap_matcher*.so", "bitmap_matcher*.pyd"):
            candidates.extend(build_root.rglob(pattern))

    seen = set()
    unique = []
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def preferred_output_name(source_path):
    py_ver = get_python_version().replace(".", "")
    arch = get_architecture()
    suffix = source_path.suffix  # .so or .pyd
    return f"bitmap_matcher_py{py_ver}_{arch}{suffix}"


def build_native_extension(quiet=False):
    """
    Build bitmap_matcher for the current Python and place it in this package directory.
    Returns the Path to the built extension, or None on failure.
    """
    pyx_path = PACKAGE_DIR / "bitmap_matcher.pyx"
    if not pyx_path.exists():
        if not quiet:
            print(f"bitmap_matcher.pyx not found at {pyx_path}")
        return None

    if not ensure_build_dependencies():
        return None

    version = get_python_version()
    arch = get_architecture()
    build_temp = PACKAGE_DIR / f"build_py{version.replace('.', '')}_{arch}"

    if not quiet:
        print(f"Building bitmap_matcher for Python {version} ({arch})...")

    env = os.environ.copy()
    cmd = [
        sys.executable,
        str(PACKAGE_DIR / "setup_native.py"),
        "build_ext",
        "--inplace",
        "--build-temp",
        str(build_temp),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PACKAGE_DIR),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet and result.stdout.strip():
            print(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        if not quiet:
            print(f"Failed to build bitmap_matcher: {exc}")
            if exc.stdout:
                print(exc.stdout)
            if exc.stderr:
                print(exc.stderr)
        return None

    built = _collect_built_extensions()
    if not built:
        if not quiet:
            print("Build finished but no extension file was found.")
        return None

    # Prefer the most recently modified build artifact.
    built.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    source = built[0]
    dest = PACKAGE_DIR / preferred_output_name(source)
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
        # Clean leftover generic inplace names so the loader prefers the tagged binary.
        for leftover in PACKAGE_DIR.glob("bitmap_matcher.cpython-*"):
            if leftover.resolve() != dest.resolve():
                try:
                    leftover.unlink()
                except Exception:
                    pass
        for leftover_name in ("bitmap_matcher.so", "bitmap_matcher.pyd"):
            leftover = PACKAGE_DIR / leftover_name
            if leftover.exists() and leftover.resolve() != dest.resolve():
                try:
                    leftover.unlink()
                except Exception:
                    pass

    if not quiet:
        print(f"Built bitmap_matcher extension: {dest.name}")

    # Best-effort cleanup of temporary build trees / generated C.
    for temp_name in (build_temp.name, "build", "bitmap_matcher.c"):
        temp_path = PACKAGE_DIR / temp_name
        try:
            if temp_path.is_dir():
                shutil.rmtree(temp_path, ignore_errors=True)
            elif temp_path.is_file():
                temp_path.unlink()
        except Exception:
            pass

    return dest if dest.exists() else source


if __name__ == "__main__":
    built_path = build_native_extension(quiet=False)
    sys.exit(0 if built_path else 1)
