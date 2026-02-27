#!/usr/bin/env python3
"""
Build helper to produce platform native bitmap_matcher extensions.

On macOS/Linux this produces .so files; on Windows it produces .pyd files.

Usage:
  python build_universal.py        # build for current Python
  python build_universal.py --all  # attempt builds for multiple installed Python versions (python3.7..3.12)
"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import platform
from pathlib import Path
import glob


ARCH_MAP = {
    'x86_64': 'x86_64',
    'amd64': 'x86_64',
    'arm64': 'arm64',
    'aarch64': 'arm64',
    'i386': 'x86',
    'i686': 'x86',
}


def normalize_arch(raw: str) -> str:
    return ARCH_MAP.get(raw.lower(), raw.lower())


def run_python_info(python_cmd: str) -> tuple[str, str]:
    """Return (pyver_nodot, arch) for given python command."""
    # python_cmd may be a list or a string (for py launcher). Use shell when it contains spaces.
    shell = isinstance(python_cmd, str) and ' ' in python_cmd
    cmd = python_cmd if isinstance(python_cmd, list) else python_cmd
    try:
        if shell:
            out = subprocess.check_output(f"{cmd} -c \"import sys,platform;print(f'{sys.version_info.major}.{sys.version_info.minor}|{platform.machine()}')\"", shell=True, universal_newlines=True)
        else:
            out = subprocess.check_output([cmd, '-c', "import sys,platform;print(f'{sys.version_info.major}.{sys.version_info.minor}|{platform.machine()}')"], universal_newlines=True)
        ver, arch = out.strip().split('|')
        return ver.replace('.', ''), normalize_arch(arch)
    except Exception:
        return None


def find_build_artifacts(base_dir: Path) -> list[Path]:
    patterns = ['*.so', '*.pyd', '*/*.so', '*/*.pyd', 'build/lib*/**/*.so', 'build/lib*/**/*.pyd']
    found = []
    for p in patterns:
        for f in base_dir.glob(p):
            if f.is_file():
                found.append(f)
    # also include any cpython-style names in current dir
    for f in base_dir.glob('*.cpython-*.so'):
        if f.is_file():
            found.append(f)
    return list(dict.fromkeys(found))  # dedupe preserving order


def copy_and_tag(src: Path, dest_dir: Path, pyver_nodot: str, arch: str):
    ext = src.suffix
    dest_dir.mkdir(parents=True, exist_ok=True)
    # name variants
    name1 = f"bitmap_matcher_py{pyver_nodot}_{arch}{ext}"
    name2 = f"bitmap_matcher_py{pyver_nodot}{ext}"
    dst1 = dest_dir / name1
    dst2 = dest_dir / name2
    try:
        shutil.copy2(src, dst1)
        shutil.copy2(src, dst2)
    except Exception:
        # try fallback copy
        shutil.copy(src, dst1)
        shutil.copy(src, dst2)
    return [dst1, dst2]


def run_build(python_cmd, base_dir: Path):
    shell = isinstance(python_cmd, str) and ' ' in python_cmd
    cmd_display = python_cmd if isinstance(python_cmd, str) else python_cmd
    print(f"Building with: {cmd_display}")
    # run setup.py build_ext --inplace if present
    setup_py = base_dir / 'setup.py'
    if not setup_py.exists():
        print("No setup.py found in bitmap_matcher. Skipping build.")
        return []
    try:
        if shell:
            subprocess.check_call(f"{python_cmd} setup.py build_ext --inplace", shell=True)
        else:
            subprocess.check_call([python_cmd, 'setup.py', 'build_ext', '--inplace'])
    except subprocess.CalledProcessError as e:
        print(f"Build failed with {python_cmd}: {e}")
        return []

    artifacts = find_build_artifacts(base_dir)
    if not artifacts:
        print("No artifacts found after build.")
        return []

    info = None
    try:
        info = run_python_info(python_cmd)
    except Exception:
        info = None
    if not info:
        # fallback to current interpreter
        info = (f"{sys.version_info.major}{sys.version_info.minor}", normalize_arch(platform.machine()))
    pyver_nodot, arch = info

    out_files = []
    for art in artifacts:
        copied = copy_and_tag(art, base_dir, pyver_nodot, arch)
        out_files.extend(copied)

    # On macOS, clear quarantine attribute for safety
    try:
        if sys.platform == 'darwin':
            for f in out_files:
                subprocess.run(['xattr', '-cr', str(f)], check=False)
    except Exception:
        pass

    print(f"Built artifacts: {[str(p.name) for p in out_files]}")
    return out_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', help='Try multiple installed Python versions')
    args = parser.parse_args()

    base_dir = Path(__file__).parent.resolve()

    pythons = [sys.executable]
    if args.all:
        # scan for common python executables
        for v in range(7, 13):
            name = f'python3.{v}'
            which = shutil.which(name)
            if which and which not in pythons:
                pythons.append(which)
        # on Windows, also try 'py -3.X' launcher variants
        if os.name == 'nt' and shutil.which('py'):
            for v in range(7, 13):
                pythons.append(f'py -3.{v}')

    all_built = []
    for py in pythons:
        built = run_build(py, base_dir)
        all_built.extend(built)

    if not all_built:
        print("No artifacts were produced. Ensure a valid build script (setup.py) exists and required build toolchains are installed.")
        sys.exit(2)

    print("Done.")


if __name__ == '__main__':
    import platform
    main()
