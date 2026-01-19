"""
Custom PyQt6 widgets for Fuzzy Macro GUI
Includes real-time validation, emoji support, and enhanced controls
"""

from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QDialog,
    QListWidget, QListWidgetItem, QAbstractItemView, QTextEdit, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIntValidator, QDoubleValidator, QFont
from ..constants import Colors


class ValidatedLineEdit(QLineEdit):
    """QLineEdit with real-time validation and character limits"""
    
    value_changed = pyqtSignal(str)
    
    def __init__(self, input_type="text", char_limit=None, min_val=None, max_val=None, parent=None):
        super().__init__(parent)
        self.input_type = input_type
        self.char_limit = char_limit
        self.min_val = min_val
        self.max_val = max_val
        
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.SECONDARY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 2px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Colors.PURPLE};
            }}
        """)
        
        # Setup validators
        if input_type == "int":
            self.setValidator(QIntValidator(min_val or 0, max_val or 999999))
        elif input_type == "float":
            self.setValidator(QDoubleValidator(min_val or 0.0, max_val or 999999.0, 2))
        
        self.textChanged.connect(self._on_text_changed)
        self.editingFinished.connect(self._validate)
    
    def _on_text_changed(self, text):
        """Real-time validation during typing"""
        if self.char_limit and len(text) > self.char_limit:
            self.blockSignals(True)
            self.setText(text[:self.char_limit])
            self.blockSignals(False)
        
        if self.input_type in ("int", "float"):
            self._validate_numeric()
        
        self.value_changed.emit(self.text())
    
    def _validate_numeric(self):
        """Validate numeric constraints"""
        try:
            if self.input_type == "int" and self.text():
                val = int(self.text())
                if self.min_val is not None and val < self.min_val:
                    self.blockSignals(True)
                    self.setText(str(self.min_val))
                    self.blockSignals(False)
                elif self.max_val is not None and val > self.max_val:
                    self.blockSignals(True)
                    self.setText(str(self.max_val))
                    self.blockSignals(False)
            
            elif self.input_type == "float" and self.text():
                val = float(self.text())
                if self.min_val is not None and val < self.min_val:
                    self.blockSignals(True)
                    self.setText(str(self.min_val))
                    self.blockSignals(False)
                elif self.max_val is not None and val > self.max_val:
                    self.blockSignals(True)
                    self.setText(str(self.max_val))
                    self.blockSignals(False)
        except (ValueError, TypeError):
            pass
    
    def _validate(self):
        """Validation on editing finished"""
        if not self.text() and self.min_val is not None:
            self.setText(str(self.min_val))
        self._validate_numeric()


class EmojiComboBox(QComboBox):
    """QComboBox with emoji support"""
    
    value_changed = pyqtSignal(str)
    
    def __init__(self, items=None, emoji_map=None, parent=None):
        super().__init__(parent)
        self.emoji_map = emoji_map or {}
        
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {Colors.SECONDARY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 2px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 6px;
            }}
            QComboBox:focus {{
                border: 2px solid {Colors.PURPLE};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.SECONDARY_BG};
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.PURPLE};
                border: none;
            }}
        """)
        
        if items:
            self.addItems(items)
        
        self.currentTextChanged.connect(lambda: self.value_changed.emit(self.currentText()))
    
    def set_items_with_emoji(self, items):
        """Set items with emoji prefix"""
        self.clear()
        for item in items:
            emoji = self.emoji_map.get(item, "")
            display_text = f"{emoji} {item.replace('_', ' ').title()}".strip()
            self.addItem(display_text, item)
    
    def current_data(self):
        """Get current user data"""
        return self.currentData() or self.currentText().lower().replace(" ", "_")
    
    def set_data(self, value):
        """Set by user data"""
        for i in range(self.count()):
            if self.itemData(i) == value or self.itemText(i).lower() == value.lower():
                self.setCurrentIndex(i)
                return


class EnhancedCheckBox(QCheckBox):
    """QCheckBox with enhanced styling and tooltip support"""
    
    state_changed = pyqtSignal(bool)
    
    def __init__(self, text="", description="", parent=None):
        super().__init__(text, parent)
        self.description = description
        
        if description:
            self.setToolTip(description)
        
        self.setStyleSheet(f"""
            QCheckBox {{
                color: {Colors.TEXT_PRIMARY};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                background-color: {Colors.SECONDARY_BG};
                border: 2px solid {Colors.BORDER};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {Colors.PURPLE};
                border: 2px solid {Colors.PURPLE};
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid {Colors.LIGHT_PURPLE};
            }}
        """)
        
        self.stateChanged.connect(lambda: self.state_changed.emit(self.isChecked()))


class DragDropListWidget(QListWidget):
    """QListWidget with drag-and-drop and category coloring"""
    
    order_changed = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.PRIMARY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 4px;
                border-left: 4px solid {Colors.BORDER};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.SECONDARY_BG};
            }}
            QListWidget::item:hover {{
                background-color: {Colors.SECONDARY_BG};
            }}
        """)
        
        self.model().rowsMoved.connect(self._on_order_changed)
    
    def add_item_with_category(self, text, category, data=None):
        """Add item with category color indicator"""
        from ..constants import get_category_color
        item = QListWidgetItem(text)
        if data:
            item.setData(Qt.ItemDataRole.UserRole, data)
        
        color = get_category_color(category)
        item.setData(Qt.ItemDataRole.DecorationRole + 1, color)
        self.addItem(item)
    
    def _on_order_changed(self):
        """Emit signal when order changes"""
        items = []
        for i in range(self.count()):
            item = self.item(i)
            items.append(item.data(Qt.ItemDataRole.UserRole) or item.text())
        self.order_changed.emit(items)
    
    def get_order(self):
        """Get current item order"""
        items = []
        for i in range(self.count()):
            item = self.item(i)
            items.append(item.data(Qt.ItemDataRole.UserRole) or item.text())
        return items


class ImageZoomViewer(QLabel):
    """Label with clickable image zoom capability"""
    
    def __init__(self, image_path=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QLabel {{
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
    
    def mousePressEvent(self, event):
        """Open image in zoom viewer"""
        if self.image_path:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout
            from PyQt6.QtGui import QPixmap
            from PyQt6.QtCore import Qt
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Image Viewer")
            dialog.setGeometry(100, 100, 800, 600)
            
            layout = QVBoxLayout()
            label = QLabel()
            pixmap = QPixmap(self.image_path)
            scaled = pixmap.scaledToHeight(600, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled)
            layout.addWidget(label)
            
            dialog.setLayout(layout)
            dialog.exec()


class FormSection(QWidget):
    """Reusable form section with label and control"""
    
    def __init__(self, title="", description="", control=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        if title:
            title_label = QLabel(title)
            title_font = QFont()
            title_font.setBold(True)
            title_font.setPointSize(11)
            title_label.setFont(title_font)
            layout.addWidget(title_label)
        
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
            layout.addWidget(desc_label)
        
        if control:
            layout.addWidget(control)
        
        layout.setContentsMargins(0, 0, 0, 8)
        self.setLayout(layout)


class TabSection(QWidget):
    """Container for a section with optional grouping"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout()
        
        if title:
            title_label = QLabel(title)
            title_font = QFont()
            title_font.setBold(True)
            title_font.setPointSize(12)
            title_label.setFont(title_font)
            self.layout.addWidget(title_label)
            
            separator = QWidget()
            separator.setFixedHeight(2)
            separator.setStyleSheet(f"background-color: {Colors.BORDER};")
            self.layout.addWidget(separator)
        
        self.setLayout(self.layout)
    
    def add_widget(self, widget):
        """Add widget to section"""
        self.layout.addWidget(widget)
    
    def add_layout(self, layout):
        """Add layout to section"""
        self.layout.addLayout(layout)


class KeybindRecorder(QWidget):
    """Widget for recording keyboard shortcuts"""
    
    keybind_recorded = pyqtSignal(str)
    
    def __init__(self, current_keybind="", parent=None):
        super().__init__(parent)
        self.recording = False
        self.recorded_keybind = current_keybind
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.display_label = QLabel(current_keybind or "Click to record")
        self.display_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.SECONDARY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 2px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 6px;
                min-height: 30px;
                min-width: 150px;
            }}
        """)
        
        self.record_btn = QPushButton("Record")
        self.record_btn.setMaximumWidth(100)
        self.record_btn.clicked.connect(self.start_recording)
        
        layout.addWidget(self.display_label)
        layout.addWidget(self.record_btn)
        
        self.setLayout(layout)
    
    def start_recording(self):
        """Start recording keybind"""
        self.recording = True
        self.display_label.setText("Press any key combination...")
        self.display_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.PURPLE};
                color: white;
                border: 2px solid {Colors.LIGHT_PURPLE};
                border-radius: 4px;
                padding: 6px;
                min-height: 30px;
                min-width: 150px;
            }}
        """)
        self.record_btn.setText("Recording...")
        self.record_btn.setEnabled(False)
        self.setFocus()
    
    def keyPressEvent(self, event):
        """Capture key presses"""
        if self.recording:
            modifiers = []
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                modifiers.append("Ctrl")
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                modifiers.append("Alt")
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                modifiers.append("Shift")
            if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
                modifiers.append("Cmd")
            
            key_name = event.text().upper() or "Key"
            keybind = " + ".join(modifiers + [key_name])
            
            self.recorded_keybind = keybind
            self.display_label.setText(keybind)
            self.display_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {Colors.SECONDARY_BG};
                    color: {Colors.TEXT_PRIMARY};
                    border: 2px solid {Colors.PURPLE};
                    border-radius: 4px;
                    padding: 6px;
                    min-height: 30px;
                    min-width: 150px;
                }}
            """)
            
            self.record_btn.setText("Record")
            self.record_btn.setEnabled(True)
            self.recording = False
            
            self.keybind_recorded.emit(keybind)


class MultiItemInput(QWidget):
    """Input for multiple items (like blender slots)"""
    
    def __init__(self, num_items=3, parent=None):
        super().__init__(parent)
        self.num_items = num_items
        self.items = []
        
        layout = QVBoxLayout()
        
        for i in range(num_items):
            item_layout = QHBoxLayout()
            
            item_combo = EmojiComboBox()
            qty_input = ValidatedLineEdit("int", char_limit=7, min_val=1, max_val=9999999)
            max_check = EnhancedCheckBox("Max")
            repeat_input = ValidatedLineEdit("int", char_limit=6, min_val=1, max_val=999999)
            inf_check = EnhancedCheckBox("Inf")
            
            item_layout.addWidget(QLabel(f"Slot {i+1}:"), 0)
            item_layout.addWidget(item_combo, 1)
            item_layout.addWidget(QLabel("Qty:"), 0)
            item_layout.addWidget(qty_input, 0)
            item_layout.addWidget(max_check, 0)
            item_layout.addWidget(QLabel("Repeat:"), 0)
            item_layout.addWidget(repeat_input, 0)
            item_layout.addWidget(inf_check, 0)
            
            self.items.append({
                'combo': item_combo,
                'qty': qty_input,
                'max': max_check,
                'repeat': repeat_input,
                'inf': inf_check
            })
            
            layout.addLayout(item_layout)
        
        self.setLayout(layout)
    
    def get_data(self):
        """Get data from all items"""
        data = []
        for item in self.items:
            data.append({
                'item': item['combo'].current_data(),
                'qty': int(item['qty'].text()) if item['qty'].text() else 0,
                'max': item['max'].isChecked(),
                'repeat': int(item['repeat'].text()) if item['repeat'].text() else 0,
                'inf': item['inf'].isChecked()
            })
        return data
    
    def set_data(self, data_list):
        """Set data for all items"""
        for i, data in enumerate(data_list):
            if i < len(self.items):
                self.items[i]['combo'].set_data(data.get('item', ''))
                self.items[i]['qty'].setText(str(data.get('qty', 0)))
                self.items[i]['max'].setChecked(data.get('max', False))
                self.items[i]['repeat'].setText(str(data.get('repeat', 0)))
                self.items[i]['inf'].setChecked(data.get('inf', False))
