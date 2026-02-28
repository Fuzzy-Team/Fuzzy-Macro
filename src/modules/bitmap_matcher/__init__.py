# __init__.py - Auto-import the correct .so file
"""
Bitmap Matcher - Automatic platform and Python version detection
"""
import sys
import platform
import os
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import zipfile
import atexit

_EXTRACTED_EXT_DIRS = []

def get_python_version():
    """Get Python version as string (e.g., '3.9')."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"

def get_architecture():
    """Get system architecture."""
    arch = platform.machine().lower()
    # Normalize architecture names
    arch_map = {
        'x86_64': 'x86_64',
        'amd64': 'x86_64',
        'arm64': 'arm64',
        'aarch64': 'arm64',
        'i386': 'x86',
        'i686': 'x86',
    }
    return arch_map.get(arch, arch)

def _get_cp_tag():
    """Get CPython tag (e.g., cp39)."""
    return f"cp{sys.version_info.major}{sys.version_info.minor}"

def _get_windows_platform_tags():
    """Get compatible Windows wheel platform tags in preference order."""
    arch = get_architecture()
    if arch == 'x86_64':
        return ['win_amd64']
    if arch == 'x86':
        return ['win32']
    if arch == 'arm64':
        return ['win_arm64']
    return []

def _cleanup_extracted_dirs():
    """Cleanup extracted temporary extension directories."""
    for temp_dir in _EXTRACTED_EXT_DIRS:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

atexit.register(_cleanup_extracted_dirs)

def find_compatible_so():
    """Find the most compatible unpacked extension file for current environment."""
    py_version = get_python_version()
    arch = get_architecture()
    current_dir = Path(__file__).parent
    
    # Search patterns in order of preference.
    # On Windows prefer .pyd files (and wheels are handled separately).
    is_windows = platform.system() == "Windows"
    py_ver_nodot = py_version.replace('.', '')
    if is_windows:
        # Do NOT include any .so fallbacks on Windows; prefer .pyd only.
        search_patterns = [
            f"bitmap_matcher_py{py_ver_nodot}_{arch}.pyd",
            f"bitmap_matcher_{arch}_py{py_ver_nodot}.pyd",
            f"bitmap_matcher.{_get_cp_tag()}-win_amd64.pyd",
            f"bitmap_matcher.{_get_cp_tag()}-win32.pyd",
            f"bitmap_matcher.{_get_cp_tag()}-win_arm64.pyd",
            f"bitmap_matcher_py{py_ver_nodot}.pyd",
            f"bitmap_matcher_{arch}.pyd",
            "bitmap_matcher.pyd",
        ]
    else:
        search_patterns = [
            f"bitmap_matcher_py{py_ver_nodot}_{arch}.so",
            f"bitmap_matcher_{arch}_py{py_ver_nodot}.so",
            f"bitmap_matcher_py{py_ver_nodot}.so",
            f"bitmap_matcher.cpython-{py_ver_nodot}.so",
            f"bitmap_matcher_{arch}.so",
            "bitmap_matcher.so",
            # fallback to .pyd
            f"bitmap_matcher_py{py_ver_nodot}_{arch}.pyd",
            f"bitmap_matcher_{arch}_py{py_ver_nodot}.pyd",
            f"bitmap_matcher_py{py_ver_nodot}.pyd",
            f"bitmap_matcher_{arch}.pyd",
            "bitmap_matcher.pyd",
        ]
    
    # Search in current directory and subdirectories
    search_dirs = [
        current_dir,
        current_dir / "dist",
        current_dir / f"py{py_version.replace('.', '')}",
        current_dir / "dist" / f"py{py_version.replace('.', '')}",
    ]
    
    for directory in search_dirs:
        if not directory.exists():
            continue
            
        for pattern in search_patterns:
            so_path = directory / pattern
            if so_path.exists():
                return so_path
    
    return None

def find_compatible_wheel_extension():
    """Find and extract compatible .pyd from a Windows wheel, returning extracted path."""
    if platform.system() != "Windows":
        return None

    current_dir = Path(__file__).parent
    cp_tag = _get_cp_tag()
    plat_tags = _get_windows_platform_tags()

    if not plat_tags:
        return None

    # Wheel naming: dist-version-pythonTag-abiTag-platformTag.whl
    wheel_candidates = []
    for wheel_path in current_dir.glob("*.whl"):
        name = wheel_path.name
        if f"-{cp_tag}-" not in name:
            continue
        for platform_tag in plat_tags:
            if name.endswith(f"-{platform_tag}.whl"):
                wheel_candidates.append(wheel_path)
                break

    for wheel_path in wheel_candidates:
        try:
            with zipfile.ZipFile(wheel_path) as wheel_zip:
                member_names = wheel_zip.namelist()
                pyd_members = [name for name in member_names if name.lower().endswith('.pyd')]
                if not pyd_members:
                    continue

                preferred = None
                for member in pyd_members:
                    member_lower = member.lower()
                    if cp_tag in member_lower and any(tag in member_lower for tag in plat_tags):
                        preferred = member
                        break
                if preferred is None:
                    preferred = pyd_members[0]

                temp_dir = tempfile.mkdtemp(prefix="bitmap_matcher_")
                _EXTRACTED_EXT_DIRS.append(temp_dir)
                extracted_path = Path(wheel_zip.extract(preferred, path=temp_dir))
                return extracted_path
        except zipfile.BadZipFile:
            continue

    return None

def load_bitmap_matcher():
    """Dynamically load the bitmap_matcher module."""
    # On Windows prefer extracting from a wheel first; never load .so on Windows.
    so_path = None
    if platform.system() == "Windows":
        so_path = find_compatible_wheel_extension()
        if so_path is None:
            # fall back to any unpacked .pyd
            so_path = find_compatible_so()
    else:
        # Non-Windows: try .so/.pyd first, then wheel extraction.
        so_path = find_compatible_so()
        if so_path is None:
            so_path = find_compatible_wheel_extension()
    
    if so_path is None:
        raise ImportError(
            f"Could not find compatible bitmap_matcher extension for "
            f"Python {get_python_version()} on {get_architecture()}.\n"
            f"Available files in current directory:\n" +
            "\n".join([f"  - {f.name}" for f in sorted(Path(__file__).parent.glob("*.so"))] +
                       [f"  - {f.name}" for f in sorted(Path(__file__).parent.glob("*.pyd"))] +
                       [f"  - {f.name}" for f in sorted(Path(__file__).parent.glob("*.whl"))]) +
            f"\n\nTry building with: python{get_python_version()} build_universal.py"
        )
    
    # On macOS, remove quarantine attributes; skip on other platforms.
    try:
        if platform.system() == "Darwin":
            subprocess.run(["xattr", "-cr", str(so_path)], check=False)
    except Exception:
        # Non-fatal if xattr not available or fails
        pass

    #load the module from the .so file
    spec = importlib.util.spec_from_file_location("bitmap_matcher", so_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {so_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module

#auto-load the module and expose its contents
try:
    _bitmap_matcher = load_bitmap_matcher()
    
    # Export all public attributes from the loaded module
    __all__ = [name for name in dir(_bitmap_matcher) if not name.startswith('_')]
    
    # Make all functions/classes available at package level
    for name in __all__:
        globals()[name] = getattr(_bitmap_matcher, name)
        
except ImportError as e:
    # Provide helpful error message
    print(f"Warning: {e}")
    print("bitmap_matcher extension not available.")
    
    # You could provide fallback implementations here if needed
    def fallback_function():
        raise RuntimeError("bitmap_matcher extension not loaded. Please build the extension first.")
    
    # Example fallback (adjust based on your actual functions)
    __all__ = ['match_bitmap']  # Add your actual function names
    match_bitmap = fallback_function

# bitmap_matcher_loader.py - Alternative standalone loader
"""
Standalone loader for bitmap_matcher that can be used in any script
"""
import sys
import platform
import os
from pathlib import Path
import importlib.util

class BitmapMatcherLoader:
    """Dynamic loader for bitmap_matcher extensions."""
    
    def __init__(self, search_paths=None):
        self.search_paths = search_paths or [Path.cwd()]
        self._module = None
        self._loaded_from = None
    
    @property
    def python_version(self):
        """Get current Python version string."""
        return f"{sys.version_info.major}.{sys.version_info.minor}"
    
    @property
    def architecture(self):
        """Get normalized architecture string."""
        arch = platform.machine().lower()
        arch_map = {
            'x86_64': 'x86_64',
            'amd64': 'x86_64', 
            'arm64': 'arm64',
            'aarch64': 'arm64',
            'i386': 'x86',
            'i686': 'x86',
        }
        return arch_map.get(arch, arch)
    
    def find_extension(self):
        """Find the best matching extension file."""
        py_ver = self.python_version.replace('.', '')
        arch = self.architecture
        
        # Directory patterns
        dir_patterns = [
            "",
            f"py{py_ver}/",
            f"dist/py{py_ver}/",
            "dist/",
        ]

        # On Windows: prefer extracting from a wheel (.whl) first, then look for .pyd files.
        if platform.system() == "Windows":
            cp_tag = _get_cp_tag()
            plat_tags = _get_windows_platform_tags()

            for search_path in self.search_paths:
                search_path = Path(search_path)

                for dir_pattern in dir_patterns:
                    search_dir = search_path / dir_pattern
                    if not search_dir.exists():
                        continue

                    # Try wheel files first
                    for wheel_path in search_dir.glob("*.whl"):
                        try:
                            with zipfile.ZipFile(wheel_path) as wheel_zip:
                                member_names = wheel_zip.namelist()
                                pyd_members = [name for name in member_names if name.lower().endswith('.pyd')]
                                if not pyd_members:
                                    continue

                                preferred = None
                                for member in pyd_members:
                                    member_lower = member.lower()
                                    if cp_tag in member_lower and any(tag in member_lower for tag in plat_tags):
                                        preferred = member
                                        break
                                if preferred is None:
                                    preferred = pyd_members[0]

                                temp_dir = tempfile.mkdtemp(prefix="bitmap_matcher_")
                                _EXTRACTED_EXT_DIRS.append(temp_dir)
                                extracted_path = Path(wheel_zip.extract(preferred, path=temp_dir))
                                return extracted_path
                        except zipfile.BadZipFile:
                            continue

                    # If no wheel worked, search for .pyd files directly
                    pyd_patterns = [
                        f"bitmap_matcher_py{py_ver}_{arch}.pyd",
                        f"bitmap_matcher_{arch}_py{py_ver}.pyd",
                        f"bitmap_matcher_py{py_ver}.pyd",
                        f"bitmap_matcher_{arch}.pyd",
                        "bitmap_matcher.pyd",
                    ]

                    for pattern in pyd_patterns:
                        matches = list(search_dir.glob(pattern))
                        if matches:
                            return matches[0]

            return None

        # Non-Windows: behave as before, preferring .so then falling back to .pyd
        patterns = [
            f"bitmap_matcher_py{py_ver}_{arch}.so",
            f"bitmap_matcher_{arch}_py{py_ver}.so",
            f"bitmap_matcher_py{py_ver}.so",
            f"bitmap_matcher.cpython-{py_ver}*.so",
            f"bitmap_matcher_{arch}.so",
            "bitmap_matcher.so",
            "bitmap_matcher.pyd",
        ]

        for search_path in self.search_paths:
            search_path = Path(search_path)

            for dir_pattern in dir_patterns:
                search_dir = search_path / dir_pattern
                if not search_dir.exists():
                    continue

                for pattern in patterns:
                    matches = list(search_dir.glob(pattern))
                    if matches:
                        return matches[0]  # Return first match
        
        return None
    
    def load(self, force_reload=False):
        """Load the bitmap_matcher module."""
        if self._module is not None and not force_reload:
            return self._module
        
        so_path = self.find_extension()
        if so_path is None:
            available_files = []
            for search_path in self.search_paths:
                available_files.extend(Path(search_path).glob("*.so"))
                available_files.extend(Path(search_path).glob("*.pyd"))
            
            raise ImportError(
                f"No compatible bitmap_matcher extension found for "
                f"Python {self.python_version} on {self.architecture}.\n"
                f"Searched in: {[str(p) for p in self.search_paths]}\n"
                f"Available extensions: {[f.name for f in available_files]}\n"
                f"Run: python{self.python_version} build_universal.py"
            )
        
        spec = importlib.util.spec_from_file_location("bitmap_matcher", so_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec from {so_path}")
        
        self._module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self._module)
        self._loaded_from = so_path
        
        return self._module
    
    @property
    def loaded_from(self):
        """Get the path of the currently loaded extension."""
        return self._loaded_from
    
    def get_info(self):
        """Get information about the loaded module."""
        return {
            'python_version': self.python_version,
            'architecture': self.architecture,
            'loaded_from': str(self._loaded_from) if self._loaded_from else None,
            'module_loaded': self._module is not None,
        }

# Convenience functions
def load_bitmap_matcher(search_paths=None):
    """Convenience function to load bitmap_matcher."""
    loader = BitmapMatcherLoader(search_paths)
    return loader.load()

def get_bitmap_matcher_info(search_paths=None):
    """Get information about bitmap_matcher availability."""
    loader = BitmapMatcherLoader(search_paths)
    try:
        loader.load()
        return loader.get_info()
    except ImportError as e:
        info = loader.get_info()
        info['error'] = str(e)
        return info

# usage_example.py - Example of how to use the loader
"""
Example usage of the bitmap_matcher loader
"""

def example_usage():
    """Demonstrate different ways to use the loader."""
    
    print("=== Method 1: Using the package __init__.py ===")
    try:
        # If __init__.py is set up correctly, this should work automatically
        import bitmap_matcher
        print("✓ Imported via package")
        # Use bitmap_matcher.your_function_name()
    except ImportError as e:
        print(f"✗ Package import failed: {e}")
    
    print("\n=== Method 2: Using the standalone loader ===")
    try:
        from bitmap_matcher_loader import load_bitmap_matcher, get_bitmap_matcher_info
        
        # Get info about what would be loaded
        info = get_bitmap_matcher_info()
        print(f"System info: {info}")
        
        # Load the module
        bm = load_bitmap_matcher()
        print(f"✓ Loaded from: {info['loaded_from']}")
        
        # Use the module
        # result = bm.your_function_name()
        
    except ImportError as e:
        print(f"✗ Standalone loader failed: {e}")
    
    print("\n=== Method 3: Using loader class directly ===")
    try:
        from bitmap_matcher_loader import BitmapMatcherLoader
        
        # Create loader with custom search paths
        loader = BitmapMatcherLoader([
            Path.cwd(),
            Path.cwd() / "dist",
            Path("/custom/path/to/extensions")
        ])
        
        # Load and get info
        module = loader.load()
        info = loader.get_info()
        
        print(f"✓ Loaded successfully")
        print(f"  Python: {info['python_version']}")
        print(f"  Architecture: {info['architecture']}")
        print(f"  File: {info['loaded_from']}")
        
    except ImportError as e:
        print(f"✗ Direct loader failed: {e}")

if __name__ == "__main__":
    example_usage()