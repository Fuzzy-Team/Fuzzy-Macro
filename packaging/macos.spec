from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
source = root / 'src'
# The smoke-test Manager spawns from the launcher script; the engine is in the PYZ.
datas = [(str(source / 'desktop.py'), '.')]
for name in ('images', 'webapp', 'hourly_report', 'data/bss'):
    datas.append((str(source / name), name))
for name in ('paths', 'settings/patterns', 'settings/defaults'):
    datas.append((str(root / name), 'seed/' + name))
datas += collect_data_files('coremltools', excludes=['**/test/**', '**/tests/**'])
datas += collect_data_files('certifi')
for name in ('discord.py', 'pypresence', 'coremltools'):
    datas += copy_metadata(name)
for path in (source / 'modules').rglob('*'):
    if path.is_file() and path.suffix not in ('.py', '.pyc', '.so') and '__pycache__' not in path.parts:
        datas.append((str(path), str(path.parent.relative_to(source))))

hidden = ['main', 'modules.misc.ai_gather_common', 'coremltools.libcoremlpython',
          'pynput.keyboard._darwin', 'pynput.mouse._darwin', 'pynput._util.darwin',
          'mss.darwin', 'Vision', 'ColorSync', 'ApplicationServices', 'Quartz.CoreGraphics']
binaries = [(str(source / 'modules/bitmap_matcher/bitmap_matcher_py39_arm64.so'),
             'modules/bitmap_matcher')]
binaries += collect_dynamic_libs('coremltools')
a = Analysis([str(source / 'desktop.py')], pathex=[str(source)], datas=datas,
             binaries=binaries, hiddenimports=hidden,
             excludes=['torch', 'torchvision', 'matplotlib', 'tensorflow', 'sklearn', 'xgboost', 'lightgbm',
                       'paddle', 'paddleocr', 'onnxruntime', 'pytest', 'IPython'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Fuzzy Macro',
          console=False, argv_emulation=False, target_arch='arm64', codesign_identity=None)
collection = COLLECT(exe, a.binaries, a.datas, name='Fuzzy Macro')
app = BUNDLE(collection, name='Fuzzy Macro.app',
             icon=str(source / 'webapp/assets/icons/macro_icon.png'),
             bundle_identifier='com.fuzzyteam.fuzzymacro.native',
             info_plist={'CFBundleShortVersionString': (source / 'webapp/version.txt').read_text().strip(),
                         'LSMinimumSystemVersion': '13.0', 'NSHighResolutionCapable': True,
                         'NSAppleEventsUsageDescription': 'Fuzzy Macro controls Roblox and reads its window state.'})
