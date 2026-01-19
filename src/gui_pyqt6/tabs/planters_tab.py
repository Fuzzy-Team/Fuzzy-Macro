"""
Planters Tab for Fuzzy Macro PyQt6 GUI
Manual and automatic planter management
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QSlider, QLabel
from PyQt6.QtCore import Qt
from ..components.custom_widgets import TabSection, EnhancedCheckBox, FormSection, EmojiComboBox, ValidatedLineEdit
from ..constants import Colors


class PlantersTab(QWidget):
    """Planters tab with manual and auto modes"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize planters tab UI"""
        layout = QVBoxLayout()
        
        # Mode slider
        mode_layout = QHBoxLayout()
        mode_layout.addStretch()
        
        mode_label = QLabel("Off")
        self.mode_slider = QSlider(Qt.Orientation.Horizontal)
        self.mode_slider.setMinimum(0)
        self.mode_slider.setMaximum(2)
        self.mode_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.mode_slider.setTickInterval(1)
        self.mode_slider.setMaximumWidth(200)
        
        mode_end_label = QLabel("Auto")
        
        self.mode_slider.valueChanged.connect(lambda v: self._update_mode_display(v, mode_label))
        
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_slider)
        mode_layout.addWidget(mode_end_label)
        mode_layout.addStretch()
        
        layout.addLayout(mode_layout)
        
        # Tabs for manual/auto
        self.mode_tabs = QTabWidget()
        
        manual_widget = self._create_manual_tab()
        self.mode_tabs.addTab(manual_widget, "📍 Manual")
        
        auto_widget = self._create_auto_tab()
        self.mode_tabs.addTab(auto_widget, "🤖 Auto")
        
        layout.addWidget(self.mode_tabs)
        self.setLayout(layout)
    
    def _update_mode_display(self, value, label):
        """Update mode display label"""
        modes = ["Off", "Manual", "Auto"]
        label.setText(modes[value])
        self.mode_tabs.setCurrentIndex(min(value, 1))
    
    def _create_manual_tab(self):
        """Create manual planters tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        manual_section = TabSection("📍 Manual Planters")
        
        harvest_time = ValidatedLineEdit("float", char_limit=4)
        manual_section.add_widget(FormSection("Harvest Every X Hours", "Collection interval", harvest_time))
        
        harvest_full = EnhancedCheckBox("Harvest When Full", "Collect when planters are fully grown")
        manual_section.add_widget(harvest_full)
        
        from PyQt6.QtWidgets import QPushButton
        reset_btn = QPushButton("🔄 Clear Planter Timers")
        manual_section.add_widget(reset_btn)
        
        layout.addWidget(manual_section)
        
        cycles_section = TabSection("🔄 Planter Cycles")
        cycles_text = QLabel("5 cycles × 3 planters each. Set to 'none' to ignore slot.")
        cycles_section.add_widget(cycles_text)
        
        # 5 cycles
        from ..components.custom_widgets import MultiItemInput
        for i in range(5):
            cycle_layout = QVBoxLayout()
            cycle_label = QLabel(f"Cycle {i+1}")
            cycle_label.setStyleSheet("font-weight: bold;")
            cycle_layout.addWidget(cycle_label)
            
            # 3 slots per cycle
            for j in range(3):
                slot_layout = QHBoxLayout()
                planter_combo = EmojiComboBox(["Paper", "Ticket", "Festive", "Sticker", "Plastic"])
                field_combo = EmojiComboBox(["Sunflower", "Dandelion", "Mushroom"])
                gather_check = EnhancedCheckBox("Gather")
                glitter_check = EnhancedCheckBox("Glitter")
                
                slot_layout.addWidget(QLabel(f"Slot {j+1}:"))
                slot_layout.addWidget(planter_combo)
                slot_layout.addWidget(field_combo)
                slot_layout.addWidget(gather_check)
                slot_layout.addWidget(glitter_check)
                cycle_layout.addLayout(slot_layout)
            
            cycles_section.add_layout(cycle_layout)
        
        layout.addWidget(cycles_section)
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_auto_tab(self):
        """Create auto planters tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        auto_section = TabSection("🤖 Auto Planters")
        
        harvest_time = ValidatedLineEdit("float", char_limit=4)
        auto_section.add_widget(FormSection("Harvest Every X Hours", "Collection interval", harvest_time))
        
        harvest_full = EnhancedCheckBox("Harvest When Full")
        auto_section.add_widget(harvest_full)
        
        auto_harvest = EnhancedCheckBox("Auto Harvest", "Macro decides optimal harvest time")
        auto_section.add_widget(auto_harvest)
        
        max_planters = ValidatedLineEdit("int", char_limit=1, min_val=1, max_val=9)
        auto_section.add_widget(FormSection("Max Planters", "Maximum concurrent planters", max_planters))
        
        from PyQt6.QtWidgets import QPushButton
        reset_btn = QPushButton("🔄 Clear Planter Timers")
        auto_section.add_widget(reset_btn)
        
        presets = EmojiComboBox(["Blue", "Red", "White", "Custom"])
        auto_section.add_widget(FormSection("Presets", "Load preset configuration", presets))
        
        layout.addWidget(auto_section)
        
        nectar_section = TabSection("💧 Nectar Priority")
        nectars = ["Comforting", "Motivating", "Satisfying", "Refreshing", "Invigorating"]
        for i, nectar in enumerate(nectars):
            combo = EmojiComboBox(nectars)
            min_pct = ValidatedLineEdit("int", char_limit=3, min_val=0, max_val=100)
            priority_layout = QHBoxLayout()
            priority_layout.addWidget(QLabel(f"Priority {i+1}:"))
            priority_layout.addWidget(combo)
            priority_layout.addWidget(QLabel("Min%:"))
            priority_layout.addWidget(min_pct)
            nectar_section.add_layout(priority_layout)
        layout.addWidget(nectar_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
