"""Entry point for the self-contained macOS application bundle."""

import multiprocessing
import os
from pathlib import Path
import sys

# Frozen worker processes must branch before constructing a window or loading models.
if __name__ == '__main__':
    if '--smoke-test' not in sys.argv:
        log_path = Path(os.environ.get('FUZZY_APP_LOG', str(Path.home() / 'Library/Logs/Fuzzy Macro/app.log')))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(str(log_path), 'a', buffering=1)
    multiprocessing.freeze_support()

import runpy
import shutil
import tempfile
import traceback


def request_accessibility():
    """Wait for Accessibility access before importing input-control libraries."""
    from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
    if AXIsProcessTrusted():
        return True
    if AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
        return True

    import subprocess
    import tkinter as tk
    from modules.gui.widgets import Button, palette, register_fonts
    register_fonts()
    colors = palette('brown')
    window = tk.Tk()
    window.title('Fuzzy Macro - Accessibility Permission')
    window.configure(bg=colors['bg'])
    window.resizable(False, False)
    body = tk.Frame(window, bg=colors['bg'], padx=28, pady=24)
    body.pack(fill='both', expand=True)
    tk.Label(body, text='Accessibility permission required', font=('Helvetica', -18, 'bold'),
             bg=colors['bg'], fg=colors['text'], anchor='w').pack(fill='x')
    tk.Label(body, text='Enable Fuzzy Macro in System Settings → Privacy & Security → Accessibility.\n\n'
             'Leave this window open. Fuzzy Macro will continue automatically once access is enabled.',
             font=('Helvetica', -14), bg=colors['bg'], fg=colors['dim'], justify='left',
             wraplength=470).pack(fill='x', pady=(14, 22))
    buttons = tk.Frame(body, bg=colors['bg'])
    buttons.pack(fill='x')
    def open_settings():
        subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'], check=True)
    Button(buttons, 'Open Accessibility Settings', open_settings, colors).pack(side='left')
    Button(buttons, 'Quit', window.destroy, colors).pack(side='right', padx=(12, 0))
    window.protocol('WM_DELETE_WINDOW', window.destroy)
    window.bind('<Escape>', lambda event: window.destroy())
    granted = [False]
    def check_permission():
        if AXIsProcessTrusted():
            granted[0] = True
            window.destroy()
        else:
            window.after(500, check_permission)
    window.after(500, check_permission)
    window.mainloop()
    return granted[0]


def prepare_data(root, resources):
    """Install runtime assets while preserving profiles and custom patterns."""
    from modules.misc.update import PATTERN_OVERWRITE_EXCEPTIONS
    root.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'webapp', 'hourly_report', 'data/bss'):
        shutil.copytree(str(resources / name), str(root / 'src' / name), dirs_exist_ok=True)
    for name in ('paths', 'settings/patterns', 'settings/defaults'):
        source = resources / 'seed' / name
        for path in source.rglob('*'):
            if path.is_file():
                target = root / name / path.relative_to(source)
                overwrite = name == 'settings/defaults' or (name == 'settings/patterns' and path.name in PATTERN_OVERWRITE_EXCEPTIONS)
                if overwrite or not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(path), str(target))
    (root / 'src/data/user').mkdir(parents=True, exist_ok=True)
    (root / 'src/data/models').mkdir(parents=True, exist_ok=True)
    os.environ['FUZZY_APP_DATA_DIR'] = str(root)
    os.chdir(str(root / 'src'))


def smoke_test():
    """Exercise packaged dependencies and widgets without starting automation."""
    import json
    import gui
    from modules import bitmap_matcher
    from modules.misc import ai_gather_common, modelManager, settingsManager
    from modules.gui.app import TABS

    assert hasattr(bitmap_matcher, '_bitmap_matcher'), 'Bitmap matcher failed to load'
    assert ai_gather_common.coreml_available(), 'Core ML runtime failed to load'
    assert modelManager.MODEL_DIR == str(Path(settingsManager.getProjectRoot()) / 'src/data/models')
    # Import the engine, but prohibit startup downloads and model cleanup in this test.
    original_download = modelManager.ensure_missing_supported_models
    def prohibit_download():
        raise RuntimeError('Model downloads are disabled during the bundle smoke test.')
    modelManager.ensure_missing_supported_models = prohibit_download
    try:
        __import__('main')
    finally:
        modelManager.ensure_missing_supported_models = original_download
    with multiprocessing.Manager() as manager:
        state = manager.Value('i', 3)
        assert state.value == 3, 'Frozen multiprocessing manager failed'
    worker = multiprocessing.Process(target=print, args=('Frozen worker log ready',))
    worker.start()
    worker.join(20)
    if worker.is_alive():
        worker.terminate()
        worker.join()
        raise RuntimeError('Frozen worker did not exit')
    assert worker.exitcode == 0, 'Frozen worker failed'
    assert 'Frozen worker log ready' in Path(os.environ['FUZZY_APP_LOG']).read_text(), 'Worker output was lost'
    gui.launch()
    app = gui._app
    from tkinter import font
    assert {'Poppins', 'Libre Franklin'}.issubset(set(font.families(app.root))), 'Bundled fonts did not register'
    errors = []
    app.root.report_callback_exception = lambda kind, error, tb: errors.append(str(error))
    for tab in TABS:
        app.show_tab(tab)
        app.refresh()
        app.root.update()
    app.show_tab('home')
    app.root.update()
    app.root.after(1000, app.close)
    app.root.mainloop()
    if errors:
        raise RuntimeError('; '.join(errors))
    print(json.dumps(dict(result='passed', tabs=list(TABS), data_root=settingsManager.getProjectRoot())))


def main():
    resources = Path(sys._MEIPASS)
    testing = '--smoke-test' in sys.argv
    if not testing and not request_accessibility():
        return
    temporary = tempfile.TemporaryDirectory(prefix='fuzzy-app-smoke-') if testing else None
    root = Path(temporary.name) if temporary else Path.home() / 'Library/Application Support/Fuzzy Macro'
    prepare_data(root, resources)
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    log_dir = root if testing else Path.home() / 'Library/Logs/Fuzzy Macro'
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ['FUZZY_APP_LOG'] = str(log_dir / 'app.log')
    log = open(str(log_dir / 'app.log'), 'a', buffering=1)
    sys.stdout = sys.stderr = log
    try:
        if testing:
            smoke_test()
        else:
            runpy.run_module('main', run_name='__main__', alter_sys=True)
    except BaseException:
        traceback.print_exc()
        raise
    finally:
        log.flush()
        if temporary:
            # Keep the smoke result visible to a CLI caller before removing its data.
            with open(str(log_dir / 'app.log')) as source:
                sys.__stdout__.write(source.read())
            temporary.cleanup()


if __name__ == '__main__':
    main()
