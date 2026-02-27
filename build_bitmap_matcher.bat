@echo off
REM Helper to build bitmap_matcher for Windows
REM Attempts to run build_universal.py or setup.py in src/modules/bitmap_matcher

pushd "%~dp0src\modules\bitmap_matcher" || (
    echo Could not find src\modules\bitmap_matcher
    pause
    exit /b 1
)

if exist build_universal.py (
    echo Running build_universal.py
    python build_universal.py
) else if exist setup.py (
    echo Running setup.py build_ext --inplace
    python setup.py build_ext --inplace
) else (
    echo No build script found. Please provide a build_universal.py or setup.py to compile extension.
)

popd
pause
