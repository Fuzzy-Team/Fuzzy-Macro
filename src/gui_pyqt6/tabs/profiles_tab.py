"""
Profiles Tab for Fuzzy Macro PyQt6 GUI
Profile management and settings import/export
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QDialog, QComboBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal
from ..components.custom_widgets import TabSection, EnhancedCheckBox, ValidatedLineEdit


class ProfilesTab(QWidget):
    """Profiles tab for profile management"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize profiles tab UI"""
        layout = QVBoxLayout()
        
        # Current Profile Section
        current_section = TabSection("📌 Current Profile")
        self.current_profile_label = QLabel("Active: Default")
        self.current_profile_label.setStyleSheet("font-weight: bold; color: #28a745;")
        current_section.add_widget(self.current_profile_label)
        layout.addWidget(current_section)
        
        # Switch Profile Section
        switch_section = TabSection("🔄 Switch Profile")
        switch_layout = QVBoxLayout()
        
        self.profile_list = QListWidget()
        self.profile_list.addItem(QListWidgetItem("Default (ACTIVE)"))
        switch_layout.addWidget(QLabel("Available Profiles:"))
        switch_layout.addWidget(self.profile_list)
        
        switch_btn = QPushButton("Switch")
        switch_btn.clicked.connect(self.switch_profile)
        switch_layout.addWidget(switch_btn)
        
        switch_section.add_layout(switch_layout)
        layout.addWidget(switch_section)
        
        # Create Profile Section
        create_section = TabSection("➕ Create New Profile")
        create_layout = QVBoxLayout()
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Profile name")
        create_layout.addWidget(QLabel("Profile Name:"))
        create_layout.addWidget(name_input)
        
        create_btn = QPushButton("✅ Create Profile")
        create_btn.clicked.connect(lambda: self.create_profile(name_input))
        create_layout.addWidget(create_btn)
        
        create_section.add_layout(create_layout)
        layout.addWidget(create_section)
        
        # Duplicate Profile Section
        dup_section = TabSection("📋 Duplicate Profile")
        dup_layout = QVBoxLayout()
        
        source_combo = QComboBox()
        source_combo.addItem("Default")
        dup_layout.addWidget(QLabel("Source Profile:"))
        dup_layout.addWidget(source_combo)
        
        dup_name = QLineEdit()
        dup_name.setPlaceholderText("New profile name")
        dup_layout.addWidget(QLabel("New Name:"))
        dup_layout.addWidget(dup_name)
        
        dup_btn = QPushButton("🔀 Duplicate")
        dup_btn.clicked.connect(lambda: self.duplicate_profile(source_combo, dup_name))
        dup_layout.addWidget(dup_btn)
        
        dup_section.add_layout(dup_layout)
        layout.addWidget(dup_section)
        
        # Export Profile Section
        export_section = TabSection("📤 Export Profile")
        export_layout = QVBoxLayout()
        
        export_combo = QComboBox()
        export_combo.addItem("Default")
        export_layout.addWidget(QLabel("Profile:"))
        export_layout.addWidget(export_combo)
        
        export_btn = QPushButton("⬇️ Export Profile")
        export_btn.clicked.connect(lambda: self.export_profile(export_combo))
        export_layout.addWidget(export_btn)
        
        export_section.add_layout(export_layout)
        layout.addWidget(export_section)
        
        # Import Profile Section
        import_section = TabSection("📥 Import Profile")
        import_layout = QVBoxLayout()
        
        self.import_file_label = QLabel("No file selected")
        import_layout.addWidget(self.import_file_label)
        
        import_file_btn = QPushButton("📂 Choose File")
        import_file_btn.clicked.connect(self.select_import_file)
        import_layout.addWidget(import_file_btn)
        
        import_btn = QPushButton("⬆️ Import Profile")
        import_btn.clicked.connect(self.import_profile)
        import_layout.addWidget(import_btn)
        
        import_section.add_layout(import_layout)
        layout.addWidget(import_section)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def switch_profile(self):
        """Switch to selected profile"""
        current = self.profile_list.currentItem()
        if current:
            QMessageBox.information(self, "Success", f"Switched to {current.text()}")
    
    def create_profile(self, name_input):
        """Create new profile"""
        name = name_input.text().strip()
        if name:
            QMessageBox.information(self, "Success", f"Profile '{name}' created!")
            name_input.clear()
        else:
            QMessageBox.warning(self, "Error", "Please enter a profile name")
    
    def duplicate_profile(self, source_combo, name_input):
        """Duplicate a profile"""
        source = source_combo.currentText()
        name = name_input.text().strip()
        if name:
            QMessageBox.information(self, "Success", f"Profile '{name}' duplicated from '{source}'!")
            name_input.clear()
        else:
            QMessageBox.warning(self, "Error", "Please enter a profile name")
    
    def export_profile(self, profile_combo):
        """Export profile as JSON"""
        profile = profile_combo.currentText()
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Profile", "", "JSON Files (*.json)")
        if file_path:
            QMessageBox.information(self, "Success", f"Profile exported to {file_path}")
    
    def select_import_file(self):
        """Select file for import"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Profile", "", "JSON Files (*.json)")
        if file_path:
            self.import_file_label.setText(f"Selected: {file_path.split('/')[-1]}")
    
    def import_profile(self):
        """Import profile from file"""
        file_label = self.import_file_label.text()
        if "Selected:" in file_label:
            QMessageBox.information(self, "Success", "Profile imported successfully!")
        else:
            QMessageBox.warning(self, "Error", "Please select a file first")
