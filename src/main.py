import os
import subprocess
import sys
from modules.misc import messageBox


def exitForMissingDependencies(message):
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "install_dependencies.command"))
    try:
        if os.path.exists(script):
            subprocess.Popen(["/bin/bash", script])
        else:
            messageBox.msgBox(title="Dependencies not installed", text=message)
    except Exception:
        pass
    sys.exit(0)


# Child processes are started with "spawn", which re-runs this file's top level
# in every child (the multiprocessing Manager, the macro, and the Discord bot).
# Keep everything below the __main__ guard so those children only load what
# their own target needs.
if __name__ == "__main__":
    try:
        # only checks that dependencies are installed
        import requests
        from modules.misc.ColorProfile import DisplayColorProfile
    except ModuleNotFoundError:
        exitForMissingDependencies("Dependencies are not installed. Refer to Discord for help.")

    # delete backup from previous update if pending
    try:
        from modules.misc.update import delete_backup_if_pending
        delete_backup_if_pending()
    except Exception:
        pass

    try:
        from modules.misc.modelManager import ensure_missing_supported_models
        ensure_missing_supported_models()
    except Exception:
        pass

    from modules.app import runApp
    from modules.macro_loop import macro

    runApp(macro)
