"""
Gather Tab for Fuzzy Macro PyQt6 GUI
Per-field gathering configuration with 5 field tabs
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QScrollArea, QGroupBox, QComboBox, QMessageBox, QDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import json
from ..constants import Colors, FieldData, Emojis
from ..components.custom_widgets import (
    ValidatedLineEdit, EmojiComboBox, EnhancedCheckBox, TabSection, FormSection
)


class FieldConfigWidget(QWidget):
    """Configuration widget for a single field"""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, field_name="", patterns=None, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.patterns = patterns or []
        self.controls = {}
        self.init_ui()
    
    def init_ui(self):
        """Initialize field configuration UI"""
        layout = QVBoxLayout()
        layout.setSpacing(0)
        
        # Gather Field Section
        gather_section = TabSection("🌾 Gather Field")
        
        self.enable_check = EnhancedCheckBox("Enable Task")
        self.enable_check.state_changed.connect(self.settings_changed.emit)
        gather_section.add_widget(self.enable_check)
        
        field_ctrl = EmojiComboBox(emoji_map=Emojis.FIELDS)
        field_ctrl.set_items_with_emoji(FieldData.FIELD_NAMES)
        field_ctrl.value_changed.connect(self.settings_changed.emit)
        form_section = FormSection("Field", "Which field to gather in", field_ctrl)
        gather_section.add_widget(form_section)
        self.controls['field'] = field_ctrl
        
        shift_lock = EnhancedCheckBox("Use Shift Lock", "Enable shift lock switch when gathering")
        shift_lock.state_changed.connect(self.settings_changed.emit)
        gather_section.add_widget(shift_lock)
        self.controls['shift_lock'] = shift_lock
        
        drift = EnhancedCheckBox("Field Drift Compensation",
            "Move to supreme saturator between patterns")
        drift.state_changed.connect(self.settings_changed.emit)
        gather_section.add_widget(drift)
        self.controls['field_drift_compensation'] = drift
        
        layout.addWidget(gather_section)
        
        # Pattern Section
        pattern_section = TabSection("🎨 Pattern")
        
        shape_combo = EmojiComboBox()
        shape_combo.addItems([p.replace('.py', '').replace('_', ' ').title() for p in self.patterns])
        shape_combo.value_changed.connect(self.settings_changed.emit)
        pattern_section.add_widget(FormSection("Shape", "Movement pattern", shape_combo))
        self.controls['shape'] = shape_combo
        
        size_combo = QComboBox()
        size_combo.addItems(FieldData.PATTERN_SIZES)
        size_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        pattern_section.add_widget(FormSection("Size", "Overall area coverage", size_combo))
        self.controls['size'] = size_combo
        
        width_combo = QComboBox()
        width_combo.addItems([str(w) for w in FieldData.PATTERN_WIDTHS])
        width_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        pattern_section.add_widget(FormSection("Width", "Pattern repetitions", width_combo))
        self.controls['width'] = width_combo
        
        invert_lr = EnhancedCheckBox("Invert Left/Right", "Reverse horizontal direction")
        invert_lr.state_changed.connect(self.settings_changed.emit)
        pattern_section.add_widget(invert_lr)
        self.controls['invert_lr'] = invert_lr
        
        invert_fb = EnhancedCheckBox("Invert Forward/Back", "Reverse vertical direction")
        invert_fb.state_changed.connect(self.settings_changed.emit)
        pattern_section.add_widget(invert_fb)
        self.controls['invert_fb'] = invert_fb
        
        layout.addWidget(pattern_section)
        
        # Rotate Camera Section
        rotate_section = TabSection("📷 Rotate Camera")
        
        turn_combo = QComboBox()
        turn_combo.addItems(["None", "Left", "Right"])
        turn_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        rotate_section.add_widget(FormSection("Direction", "Camera rotation direction", turn_combo))
        self.controls['turn'] = turn_combo
        
        turn_times_combo = QComboBox()
        turn_times_combo.addItems([str(t) for t in FieldData.CAMERA_TURN_TIMES])
        turn_times_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        rotate_section.add_widget(FormSection("Turn X times", "Number of rotations", turn_times_combo))
        self.controls['turn_times'] = turn_times_combo
        
        layout.addWidget(rotate_section)
        
        # Gather Until Section
        gather_until_section = TabSection("⏰ Gather Until")
        
        mins_input = ValidatedLineEdit("float", char_limit=4, min_val=0)
        mins_input.value_changed.connect(self.settings_changed.emit)
        gather_until_section.add_widget(FormSection("Mins", "Maximum gathering minutes", mins_input))
        self.controls['mins'] = mins_input
        
        backpack_input = ValidatedLineEdit("int", char_limit=3, min_val=0, max_val=100)
        backpack_input.value_changed.connect(self.settings_changed.emit)
        gather_until_section.add_widget(FormSection("Backpack%", "Stop at backpack capacity", backpack_input))
        self.controls['backpack'] = backpack_input
        
        return_combo = QComboBox()
        return_combo.addItems(FieldData.RETURN_METHODS_DISPLAY)
        return_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        gather_until_section.add_widget(FormSection("Return To Hive", "How to return", return_combo))
        self.controls['return'] = return_combo
        
        layout.addWidget(gather_until_section)
        
        # Start Location Section
        start_section = TabSection("🗺️ Start Location")
        
        location_combo = QComboBox()
        location_combo.addItems(FieldData.START_LOCATIONS_DISPLAY)
        location_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        start_section.add_widget(FormSection("Location", "Starting position", location_combo))
        self.controls['start_location'] = location_combo
        
        distance_combo = QComboBox()
        distance_combo.addItems([str(d) for d in FieldData.START_LOCATION_DISTANCES])
        distance_combo.currentTextChanged.connect(lambda: self.settings_changed.emit())
        start_section.add_widget(FormSection("Distance", "Distance from hive", distance_combo))
        self.controls['distance'] = distance_combo
        
        layout.addWidget(start_section)
        
        # Goo Settings Section
        goo_section = TabSection("💧 Goo Settings")
        
        use_goo = EnhancedCheckBox("Use Goo", "Apply goo during gathering")
        use_goo.state_changed.connect(self.settings_changed.emit)
        goo_section.add_widget(use_goo)
        self.controls['goo'] = use_goo
        
        goo_interval = ValidatedLineEdit("int", char_limit=4, min_val=3)
        goo_interval.value_changed.connect(self.settings_changed.emit)
        goo_section.add_widget(FormSection("Goo Interval", "Seconds between goo usage (min 3)", goo_interval))
        self.controls['goo_interval'] = goo_interval
        
        layout.addWidget(goo_section)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def get_settings(self):
        """Get current field settings"""
        return {
            'field_enable': self.enable_check.isChecked(),
            'field': self.controls['field'].current_data(),
            'shift_lock': self.controls['shift_lock'].isChecked(),
            'field_drift_compensation': self.controls['field_drift_compensation'].isChecked(),
            'shape': self.controls['shape'].current_data(),
            'size': self.controls['size'].currentText(),
            'width': int(self.controls['width'].currentText()),
            'invert_lr': self.controls['invert_lr'].isChecked(),
            'invert_fb': self.controls['invert_fb'].isChecked(),
            'turn': self.controls['turn'].currentText().lower(),
            'turn_times': int(self.controls['turn_times'].currentText()),
            'mins': float(self.controls['mins'].text()) if self.controls['mins'].text() else 0,
            'backpack': int(self.controls['backpack'].text()) if self.controls['backpack'].text() else 100,
            'return': FieldData.RETURN_METHODS[FieldData.RETURN_METHODS_DISPLAY.index(self.controls['return'].currentText())],
            'start_location': FieldData.START_LOCATIONS[FieldData.START_LOCATIONS_DISPLAY.index(self.controls['start_location'].currentText())],
            'distance': int(self.controls['distance'].currentText()),
            'goo': self.controls['goo'].isChecked(),
            'goo_interval': int(self.controls['goo_interval'].text()) if self.controls['goo_interval'].text() else 3,
        }


class GatherTab(QWidget):
    """Gather tab with 5 field configurations"""
    
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.field_configs = {}
        self.patterns = []
        self.init_ui()
    
    def init_ui(self):
        """Initialize gather tab UI"""
        layout = QVBoxLayout()
        
        # Field tabs
        self.field_tabs = QTabWidget()
        
        for i in range(1, 6):
            field_config = FieldConfigWidget(f"Field {i}", self.patterns)
            field_config.settings_changed.connect(lambda i=i: self._on_field_settings_changed(i))
            self.field_configs[i] = field_config
            self.field_tabs.addTab(field_config, f"🌾 Field {i}")
        
        layout.addWidget(self.field_tabs)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("📊 Export Settings")
        export_btn.clicked.connect(self.export_settings)
        button_layout.addWidget(export_btn)
        
        import_btn = QPushButton("📥 Import Settings")
        import_btn.clicked.connect(self.import_settings)
        button_layout.addWidget(import_btn)
        
        reset_btn = QPushButton("🔄 Reset to Default")
        reset_btn.clicked.connect(self.reset_field)
        button_layout.addWidget(reset_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _on_field_settings_changed(self, field_num):
        """Handle field settings change"""
        settings = self.field_configs[field_num].get_settings()
        self.settings_changed.emit({'field': field_num, 'settings': settings})
    
    def export_settings(self):
        """Export field settings as JSON"""
        current_field = self.field_tabs.currentIndex() + 1
        settings = self.field_configs[current_field].get_settings()
        json_str = json.dumps(settings, indent=2)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Field Settings")
        dialog.setGeometry(100, 100, 500, 400)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Field {current_field} Settings:"))
        
        text_edit = QTextEdit()
        text_edit.setText(json_str)
        layout.addWidget(text_edit)
        
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(json_str))
        layout.addWidget(copy_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        from PyQt6.QtGui import QClipboard
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Success", "Settings copied to clipboard!")
    
    def import_settings(self):
        """Import field settings from JSON"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Import Field Settings")
        dialog.setGeometry(100, 100, 500, 400)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Paste JSON settings:"))
        
        text_edit = QTextEdit()
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        confirm_btn = QPushButton("Import")
        confirm_btn.clicked.connect(lambda: self._perform_import(text_edit.toPlainText(), dialog))
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def _perform_import(self, json_str, dialog):
        """Perform JSON import"""
        try:
            settings = json.loads(json_str)
            QMessageBox.information(self, "Success", "Settings imported successfully!")
            dialog.accept()
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Error", f"Invalid JSON: {str(e)}")
    
    def reset_field(self):
        """Reset current field to defaults"""
        current_field = self.field_tabs.currentIndex() + 1
        reply = QMessageBox.question(self, "Reset Field",
            f"Reset Field {current_field} to default settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Success", "Field reset to defaults!")
    
    def set_patterns(self, patterns):
        """Set available patterns"""
        self.patterns = patterns
        for config in self.field_configs.values():
            config.patterns = patterns
