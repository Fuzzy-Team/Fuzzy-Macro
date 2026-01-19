"""
Home Tab for Fuzzy Macro PyQt6 GUI
Main control center with macro status, task list, and planter timers
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QGroupBox, QComboBox, QScrollArea, QTextEdit, QDialog,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPixmap
import os
from ..constants import Colors, Emojis
from ..components.custom_widgets import EmojiComboBox, EnhancedCheckBox


class MacroLogger(QWidget):
    """Macro log display widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Log type controls
        controls = QHBoxLayout()
        log_label = QLabel("Logs (")
        self.log_type_label = QLabel("Simple")
        log_label_end = QLabel(")")
        self.toggle_log_btn = QPushButton("Detailed")
        self.log_type = "simple"
        self.toggle_log_btn.clicked.connect(self._toggle_log_type)
        
        controls.addWidget(log_label)
        controls.addWidget(self.log_type_label)
        controls.addWidget(log_label_end)
        controls.addStretch()
        controls.addWidget(self.toggle_log_btn)
        
        layout.addLayout(controls)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Courier New';
                font-size: 10px;
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        layout.addWidget(self.log_display)
        
        # Clear button
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        layout.addWidget(clear_btn)
        
        self.setLayout(layout)
    
    def _toggle_log_type(self):
        """Toggle between simple and detailed logs"""
        if self.log_type == "simple":
            self.log_type = "detailed"
            self.log_type_label.setText("Detailed")
            self.toggle_log_btn.setText("Simple")
        else:
            self.log_type = "simple"
            self.log_type_label.setText("Simple")
            self.toggle_log_btn.setText("Detailed")
    
    def log(self, time_str="", msg="", color=""):
        """Add log message"""
        formatted_msg = f"[{time_str}] {msg}" if time_str else msg
        
        if color:
            self.log_display.setTextColor(QColor(color))
        else:
            self.log_display.setTextColor(QColor("#d4d4d4"))
        
        self.log_display.append(formatted_msg)
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """Clear all logs"""
        self.log_display.clear()


class HomeTab(QWidget):
    """Home tab with macro controls and status display"""
    
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    update_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QHBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Left panel - Controls (40% width)
        left_panel = self._create_left_panel()
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(400)
        layout.addWidget(left_widget)
        
        # Right panel - Logs (60% width)
        self.logger = MacroLogger()
        layout.addWidget(self.logger, 1)
        
        self.setLayout(layout)
    
    def _create_left_panel(self):
        """Create left control panel"""
        layout = QVBoxLayout()
        
        # Macro Control Section
        macro_group = self._create_macro_control_section()
        layout.addWidget(macro_group)
        
        # Status Section
        status_group = self._create_status_section()
        layout.addWidget(status_group)
        
        # Macro Mode Section
        mode_group = self._create_macro_mode_section()
        layout.addWidget(mode_group)
        
        # Planter Timers Section
        timers_group = self._create_planter_timers_section()
        layout.addWidget(timers_group)
        
        # Update Section
        update_group = self._create_update_section()
        layout.addWidget(update_group)
        
        # Tasks Section
        tasks_group = self._create_tasks_section()
        layout.addWidget(tasks_group, 1)
        
        # Credits Section
        credits_group = self._create_credits_section()
        layout.addWidget(credits_group)
        
        return layout
    
    def _create_macro_control_section(self):
        """Create macro control buttons"""
        group = QGroupBox("Macro Control")
        layout = QVBoxLayout()
        
        self.start_btn = QPushButton("Start [F1]")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #6f42c1;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #5a32a3;
            }}
        """)
        self.start_btn.clicked.connect(self.start_clicked.emit)
        
        self.stop_btn = QPushButton("Stop [F3]")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.stop_btn.setVisible(False)
        
        self.pause_btn = QPushButton("Pause [F2]")
        self.pause_btn.setMinimumHeight(40)
        self.pause_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffc107;
                color: black;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #ffb300;
            }}
        """)
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        self.pause_btn.setVisible(False)
        
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.pause_btn)
        group.setLayout(layout)
        return group
    
    def _create_status_section(self):
        """Create status display section"""
        group = QGroupBox("Status")
        layout = QVBoxLayout()
        
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.status_label)
        
        self.runtime_label = QLabel("Runtime: 00:00:00")
        layout.addWidget(self.runtime_label)
        
        self.version_label = QLabel("Version: Loading...")
        layout.addWidget(self.version_label)
        
        group.setLayout(layout)
        return group
    
    def _create_macro_mode_section(self):
        """Create macro mode selector"""
        group = QGroupBox("Macro Mode")
        layout = QVBoxLayout()
        
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["🎯 Normal Mode", "🌾 Field Mode", "🎪 Quest Mode"])
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        
        layout.addLayout(mode_layout)
        group.setLayout(layout)
        return group
    
    def _create_planter_timers_section(self):
        """Create planter timers display"""
        group = QGroupBox("Planter Timers")
        layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        clear_timers_btn = QPushButton("Reset Timers")
        clear_timers_btn.clicked.connect(lambda: print("Reset planter timers"))
        btn_layout.addWidget(clear_timers_btn)
        layout.addLayout(btn_layout)
        
        # Timers grid (3 columns)
        self.timers_container = QWidget()
        timers_layout = QVBoxLayout()
        self.timers_container.setLayout(timers_layout)
        
        layout.addWidget(self.timers_container, 1)
        group.setLayout(layout)
        return group
    
    def _create_update_section(self):
        """Create update section"""
        group = QGroupBox("Updates")
        layout = QVBoxLayout()
        
        self.update_btn = QPushButton("Check for Updates")
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
        """)
        self.update_btn.clicked.connect(self.update_clicked.emit)
        layout.addWidget(self.update_btn)
        
        self.version_display = QLabel()
        layout.addWidget(self.version_display)
        
        group.setLayout(layout)
        return group
    
    def _create_tasks_section(self):
        """Create active tasks display"""
        group = QGroupBox("Active Tasks")
        layout = QVBoxLayout()
        
        self.task_list = QListWidget()
        self.task_list.setMaximumHeight(300)
        layout.addWidget(self.task_list)
        
        group.setLayout(layout)
        return group
    
    def _create_credits_section(self):
        """Create credits section"""
        group = QGroupBox("Credits")
        layout = QVBoxLayout()
        
        credits_text = QLabel(
            "GUI Inspiration: ALAS\n"
            "Macro Inspiration: Natro Macro, Stumpy Macro\n"
            "Developers: Existance, Sev, Logan\n"
            "Pattern Makers: Existance, NatroTeam, and others"
        )
        credits_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px;")
        credits_text.setWordWrap(True)
        layout.addWidget(credits_text)
        
        group.setLayout(layout)
        return group
    
    def update_status(self, status_text):
        """Update status display"""
        self.status_label.setText(f"Status: {status_text}")
    
    def add_task(self, task_name, task_desc=""):
        """Add task to list"""
        text = f"{'✓' if task_desc else '•'} {task_name}"
        if task_desc:
            text += f"\n  {task_desc}"
        item = QListWidgetItem(text)
        self.task_list.addItem(item)
    
    def clear_tasks(self):
        """Clear task list"""
        self.task_list.clear()
    
    def set_version(self, version):
        """Set version display"""
        self.version_display.setText(f"Version: {version}")
    
    def log(self, time_str="", msg="", color=""):
        """Log message"""
        self.logger.log(time_str, msg, color)
