import os
import sys

from modules.misc import messageBox


_shown_permissions = set()


def app_name():
    return "Fuzzy Macro" if getattr(sys, "frozen", False) else "Terminal"


def app_bundle_path():
    if not getattr(sys, "frozen", False):
        return None
    return os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))


def permission_text(permission_name, settings_name, details=None):
    name = app_name()
    path = app_bundle_path()
    text = f"{name} does not have {permission_name} permission. The macro will not work properly.\n\n"
    if path:
        text += (
            f"If System Settings already shows {name} as enabled, remove that row with the minus button, "
            f"then add this exact app again:\n{path}\n\n"
        )
    else:
        text += f"Go to System Settings -> Privacy & Security -> {settings_name} -> add and enable {name}.\n\n"

    if details:
        text += f"{details}\n\n"

    text += f"After enabling it, fully quit and restart {name}."
    return text


def show_permission_message(permission_name, settings_name, title=None, details=None, once=True):
    key = (permission_name, settings_name)
    if once and key in _shown_permissions:
        return
    _shown_permissions.add(key)
    messageBox.msgBox(
        title=title or f"{permission_name} Permission",
        text=permission_text(permission_name, settings_name, details),
    )
