"""Build configuration for the bundled bitmap_matcher Cython extension."""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy
import platform
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def get_extensions():
    system = platform.system()
    if system == "Windows":
        compile_args = ["/O2"]
        link_args = []
    else:
        compile_args = ["-O2", "-fPIC"]
        link_args = ["-O2"]

    return [
        Extension(
            "bitmap_matcher",
            [str(PACKAGE_DIR / "bitmap_matcher.pyx")],
            include_dirs=[numpy.get_include()],
            extra_compile_args=compile_args,
            extra_link_args=link_args,
            define_macros=[
                ("NPY_NO_DEPRECATED_API",),
            ],
        )
    ]


setup(
    name="bitmap_matcher",
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives={
            "language_level": 3,
            "embedsignature": True,
        },
    ),
    include_dirs=[numpy.get_include()],
    zip_safe=False,
    python_requires=">=3.7",
)
