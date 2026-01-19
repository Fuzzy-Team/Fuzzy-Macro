"""
Unified PyQt6 GUI for Fuzzy Macro
Main application window with all tabs integrated
"""

import sys
import multiprocessing
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
import os

from .constants import GLOBAL_STYLESHEET, Colors
from .tabs import (
    HomeTab, GatherTab, CollectTab, ConfigTab, KillTab,
    PlantersTab, BoostTab, QuestsTab, ProfilesTab
)
from modules.misc.messageBox import msgBox
import modules.misc.settingsManager as settingsManager


# Global GUI instance and compatibility layer
_gui_instance = None
_run_state = None
_run_value_ref = None


def setRunState(state):
    """Set the run state (module-level function for compatibility)"""
    global _run_state, _run_value_ref
    _run_state = state
    if _run_value_ref is not None:
        try:
            _run_value_ref.value = state
        except Exception:
            pass


def getRunState():
    """Get the run state"""
    global _run_state
    return _run_state


def log(time_str="", msg="", color=""):
    """Log a message to the GUI"""
    global _gui_instance
    if _gui_instance:
        _gui_instance.log(time_str, msg, color)


def toggleStartStop():
    """Toggle start/stop buttons"""
    global _gui_instance
    if _gui_instance:
        _gui_instance.toggle_start_stop()


def updateGUI():
    """Update GUI with current settings"""
    global _gui_instance
    if _gui_instance:
        try:
            settings = settingsManager.loadAllSettings()
            _gui_instance.update_from_settings(settings)
        except Exception as e:
            print(f"Error updating GUI: {e}")
        
        app = QApplication.instance()
        if app:
            app.processEvents()


def openLink(link: str):
    """Open link in browser"""
    try:
        import webbrowser
        webbrowser.open(link, autoraise=True)
    except Exception as e:
        print(f"Error opening link: {e}")


def start():
    """Request macro start"""
    global _run_value_ref, _run_state
    if _run_value_ref is not None:
        try:
            _run_value_ref.value = 1
            _run_state = 1
        except Exception:
            pass
    else:
        setRunState(1)


def stop():
    """Request macro stop"""
    global _run_value_ref, _run_state
    if _run_value_ref is not None:
        try:
            _run_value_ref.value = 0
            _run_state = 0
        except Exception:
            pass
    else:
        setRunState(0)


def pause():
    """Request macro pause"""
    global _run_value_ref, _run_state
    if _run_value_ref is not None:
        try:
            _run_value_ref.value = 5
            _run_state = 5
        except Exception:
            pass
    else:
        setRunState(5)


def resume():
    """Resume from pause"""
    global _run_value_ref, _run_state
    if _run_value_ref is not None:
        try:
            _run_value_ref.value = 2
            _run_state = 2
        except Exception:
            pass
    else:
        setRunState(2)


def getPatterns():
    """Get available patterns"""
    try:
        patterns_dir = settingsManager.getPatternsDir()
        return [x.replace('.py', '') for x in os.listdir(patterns_dir) if x.endswith('.py')]
    except Exception:
        return []


def clearManualPlanters():
    """Clear manual planter data"""
    try:
        settingsManager.clearFile("./data/user/manualplanters.txt")
    except Exception as e:
        print(f"Error clearing manual planters: {e}")


def getManualPlanterData():
    """Get manual planter data"""
    try:
        with open("./data/user/manualplanters.txt", "r") as f:
            data = f.read()
        if data.strip():
            import ast
            return ast.literal_eval(data)
        return ""
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error getting manual planter data: {e}")
        return ""


def getAutoPlanterData():
    """Get auto planter data"""
    try:
        import json
        with open("./data/user/auto_planters.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error getting auto planter data: {e}")
        return {}


def clearAutoPlanters():
    """Clear auto planter data"""
    data = {
        "planters": [
            {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
            {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
            {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0}
        ],
        "nectar_last_field": {"comforting": "", "refreshing": "", "satisfying": "", "motivating": "", "invigorating": ""}
    }
    try:
        import json
        with open("./data/user/auto_planters.json", "w") as f:
            json.dump(data, f, indent=3)
    except Exception as e:
        print(f"Error clearing auto planters: {e}")


def clearBlender():
    """Clear blender data"""
    try:
        data = {"item": 1, "collectTime": 0}
        with open("data/user/blender.txt", "w") as f:
            f.write(str(data))
    except Exception as e:
        print(f"Error clearing blender: {e}")


def clearAFB():
    """Clear AFB data"""
    try:
        afb_data = {"AFB_dice_cd": 0, "AFB_glitter_cd": 0, "AFB_limit": 0}
        data_str = "\n".join([f"{key}={value}" for key, value in afb_data.items()])
        with open("data/user/AFB.txt", "w") as f:
            f.write(data_str)
    except Exception as e:
        print(f"Error clearing AFB: {e}")


def resetFieldToDefault(field_name: str):
    """Reset field to defaults"""
    try:
        return settingsManager.resetFieldToDefault(field_name)
    except Exception as e:
        print(f"Error resetting field: {e}")
        return False


def exportFieldSettings(field_name: str):
    """Export field settings"""
    try:
        return settingsManager.exportFieldSettings(field_name)
    except Exception as e:
        print(f"Error exporting field settings: {e}")
        return None


def importFieldSettings(field_name: str, json_settings: str):
    """Import field settings"""
    try:
        return settingsManager.importFieldSettings(field_name, json_settings)
    except Exception as e:
        print(f"Error importing field settings: {e}")
        return False


def getMacroVersion():
    """Get macro version"""
    try:
        return settingsManager.getMacroVersion()
    except Exception:
        return None


def update():
    """Update macro"""
    try:
        from modules.misc.update import update as updateFunc
        updateFunc()
        global _gui_instance
        if _gui_instance:
            _gui_instance.close()
        sys.exit()
    except Exception as e:
        print(f"Error updating: {e}")


# Export settings manager methods
loadFields = settingsManager.loadFields
saveField = settingsManager.saveField
loadSettings = settingsManager.loadSettings
loadAllSettings = settingsManager.loadAllSettings
saveProfileSetting = settingsManager.saveProfileSetting
saveGeneralSetting = settingsManager.saveGeneralSetting
saveDictProfileSettings = settingsManager.saveDictProfileSettings
initializeFieldSync = settingsManager.initializeFieldSync
listProfiles = settingsManager.listProfiles
getCurrentProfile = settingsManager.getCurrentProfile
switchProfile = settingsManager.switchProfile
createProfile = settingsManager.createProfile
deleteProfile = settingsManager.deleteProfile
renameProfile = settingsManager.renameProfile
duplicateProfile = settingsManager.duplicateProfile
exportProfile = settingsManager.exportProfile
importProfile = settingsManager.importProfile
importProfileContent = settingsManager.importProfileContent


class FuzzyMacroGUI(QMainWindow):
    """Main GUI window for Fuzzy Macro"""
    
    def __init__(self, run_state):
        super().__init__()
        self.run_state = run_state
        self.setup_styles()
        self.init_ui()
        self.load_version()
    
    def setup_styles(self):
        """Setup application styles"""
        self.setStyleSheet(GLOBAL_STYLESHEET)
        self.setWindowTitle("Fuzzy Macro v2.0")
        self.setGeometry(100, 100, 1400, 900)
    
    def init_ui(self):
        """Initialize main UI"""
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Fuzzy Macro")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        self.version_label = QLabel()
        header_layout.addStretch()
        header_layout.addWidget(self.version_label)
        
        main_layout.addLayout(header_layout)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background-color: #2F3136;
                color: #E8E8E8;
                padding: 10px 20px;
                border: none;
                border-bottom: 3px solid #2F3136;
            }
            QTabBar::tab:selected {
                background-color: #36393F;
                border-bottom: 3px solid #7A77BB;
            }
            QTabBar::tab:hover {
                background-color: #36393F;
            }
        """)
        
        # Create tabs
        self.home_tab = HomeTab()
        self.gather_tab = GatherTab()
        self.collect_tab = CollectTab()
        self.config_tab = ConfigTab()
        self.kill_tab = KillTab()
        self.planters_tab = PlantersTab()
        self.boost_tab = BoostTab()
        self.quests_tab = QuestsTab()
        self.profiles_tab = ProfilesTab()
        
        # Add tabs
        self.tabs.addTab(self.home_tab, "🏠 Home")
        self.tabs.addTab(self.gather_tab, "🌾 Gather")
        self.tabs.addTab(self.collect_tab, "🎁 Collect")
        self.tabs.addTab(self.config_tab, "⚙️ Config")
        self.tabs.addTab(self.kill_tab, "💀 Kill")
        self.tabs.addTab(self.planters_tab, "🌱 Planters")
        self.tabs.addTab(self.boost_tab, "💪 Boost")
        self.tabs.addTab(self.quests_tab, "📝 Quests")
        self.tabs.addTab(self.profiles_tab, "👤 Profiles")
        
        main_layout.addWidget(self.tabs)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Connect signals
        self.home_tab.start_clicked.connect(start)
        self.home_tab.stop_clicked.connect(stop)
        self.home_tab.pause_clicked.connect(pause)
        self.home_tab.update_clicked.connect(update)
        
        # Status update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)
        
        # Load initial data
        self.load_patterns()
    
    def load_version(self):
        """Load and display version"""
        try:
            with open("version.txt", "r") as f:
                version = f.read().strip()
            self.version_label.setText(f"v{version}")
            self.home_tab.set_version(version)
        except Exception:
            pass
    
    def load_patterns(self):
        """Load available patterns"""
        try:
            patterns = getPatterns()
            self.gather_tab.set_patterns(patterns)
        except Exception as e:
            print(f"Error loading patterns: {e}")
    
    def update_status(self):
        """Update status display"""
        global _run_state
        
        if _run_state == 2:
            self.home_tab.update_status("Running")
        elif _run_state == 5:
            self.home_tab.update_status("Paused")
        else:
            self.home_tab.update_status("Stopped")
        
        # Toggle button visibility
        self.home_tab.start_btn.setVisible(_run_state != 2)
        self.home_tab.stop_btn.setVisible(_run_state == 2)
        self.home_tab.pause_btn.setVisible(_run_state == 2)
    
    def update_from_settings(self, settings):
        """Update GUI from settings"""
        pass
    
    def log(self, time_str="", msg="", color=""):
        """Log message"""
        self.home_tab.log(time_str, msg, color)
    
    def toggle_start_stop(self):
        """Toggle start/stop visibility"""
        self.update_status()


def launch(run):
    """Launch the PyQt6 GUI"""
    global _gui_instance, _run_state, _run_value_ref
    
    _run_state = run.value
    _run_value_ref = run
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    gui = FuzzyMacroGUI(run)
    _gui_instance = gui
    gui.show()
    
    app.processEvents()

    return gui, app


if __name__ == "__main__":
    run_state = multiprocessing.Value("i", 3)
    gui, app = launch(run_state)
    sys.exit(QApplication.instance().exec())
