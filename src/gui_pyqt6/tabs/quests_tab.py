"""
Quests Tab for Fuzzy Macro PyQt6 GUI
Quest settings and quest selection
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QScrollArea
from ..components.custom_widgets import TabSection, EnhancedCheckBox, FormSection, EmojiComboBox, ValidatedLineEdit


class QuestsTab(QWidget):
    """Quests tab with settings and quest selection"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize quests tab UI"""
        layout = QVBoxLayout()
        
        tabs = QTabWidget()
        
        # Settings tab
        settings_widget = self._create_settings_tab()
        tabs.addTab(settings_widget, "⚙️ Settings")
        
        # Quests tab
        quests_widget = self._create_quests_tab()
        tabs.addTab(quests_widget, "📝 Quests")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
    
    def _create_settings_tab(self):
        """Create quest settings tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        override_section = TabSection("🔄 Override Gather Settings")
        
        gather_mins = ValidatedLineEdit("float", char_limit=4)
        override_section.add_widget(FormSection("Gather Until Mins", "0 = disable", gather_mins))
        
        return_method = EmojiComboBox(["No Override", "💀 Reset", "👟 Walk", "🔄 Rejoin", "🌱 Whirligig"])
        override_section.add_widget(FormSection("Return To Hive", "Return method", return_method))
        
        layout.addWidget(override_section)
        
        goo_section = TabSection("💧 Goo Settings")
        
        use_gumdrops = EnhancedCheckBox("Use Gumdrops")
        goo_section.add_widget(use_gumdrops)
        
        gumdrop_slot = EmojiComboBox([str(i) for i in range(1, 8)])
        goo_section.add_widget(FormSection("Gumdrop Slot", "Inventory slot", gumdrop_slot))
        
        layout.addWidget(goo_section)
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_quests_tab(self):
        """Create quest selection tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        quests_section = TabSection("📝 Quest Selection")
        
        quests = [
            ("🐻‍❄️ Polar Bear", "polar_bear_quest"),
            ("🐝 Honey Bee", "honey_bee_quest"),
            ("💙 Bucko Bee", "bucko_bee_quest"),
            ("❤️ Riley Bee", "riley_bee_quest"),
        ]
        
        for quest_name, quest_key in quests:
            check = EnhancedCheckBox(quest_name)
            quests_section.add_widget(check)
        
        layout.addWidget(quests_section)
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
