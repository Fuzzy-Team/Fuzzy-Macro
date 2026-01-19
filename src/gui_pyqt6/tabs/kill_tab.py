"""
Kill Tab for Fuzzy Macro PyQt6 GUI
Mob killing configuration
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QScrollArea
from ..components.custom_widgets import TabSection, EnhancedCheckBox, FormSection, EmojiComboBox, ValidatedLineEdit
from ..constants import FieldData


class KillTab(QWidget):
    """Kill tab with mob configurations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize kill tab UI"""
        layout = QVBoxLayout()
        
        tabs = QTabWidget()
        
        # Settings tab
        settings_widget = self._create_settings_tab()
        tabs.addTab(settings_widget, "⚙️ Settings")
        
        # Regular mobs tab
        regular_widget = self._create_regular_tab()
        tabs.addTab(regular_widget, "🐛 Regular")
        
        # Bosses tab
        bosses_widget = self._create_bosses_tab()
        tabs.addTab(bosses_widget, "👹 Bosses")
        
        # Misc tab
        misc_widget = self._create_misc_tab()
        tabs.addTab(misc_widget, "❓ Misc")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
    
    def _create_settings_tab(self):
        """Create settings sub-tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        respawn_section = TabSection("⏱️ Respawn Modifiers")
        gifted_vb = EnhancedCheckBox("Gifted Vicious Bee")
        respawn_section.add_widget(gifted_vb)
        stick_bug = ValidatedLineEdit("int", char_limit=2)
        respawn_section.add_widget(FormSection("Stick Bug Amulet", "Amulet level", stick_bug))
        icicles = ValidatedLineEdit("int", char_limit=2)
        respawn_section.add_widget(FormSection("Icicles Beequip", "Equipment level", icicles))
        layout.addWidget(respawn_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_regular_tab(self):
        """Create regular mobs tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        regular_section = TabSection("🐛 Regular Mobs")
        for emoji, name in [("🐞", "Ladybugs"), ("🪲", "Rhino Beetles"), ("🦂", "Scorpions"),
                            ("🦗", "Mantises"), ("🕷️", "Spiders"), ("🐺", "Werewolves")]:
            check = EnhancedCheckBox(f"{emoji} {name}")
            regular_section.add_widget(check)
        layout.addWidget(regular_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_bosses_tab(self):
        """Create bosses tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        stinger_section = TabSection("😈 Stinger Hunt")
        stinger_enable = EnhancedCheckBox("Enable Task")
        stinger_section.add_widget(stinger_enable)
        for emoji, field in zip("🌾🌾🌾🌾🌾🌾", 
                               ["Clover", "Spider", "Cactus", "Rose", "Mountain Top", "Pepper"]):
            check = EnhancedCheckBox(f"{emoji} {field}")
            stinger_section.add_widget(check)
        layout.addWidget(stinger_section)
        
        snail_section = TabSection("🐌 Stump Snail")
        snail_enable = EnhancedCheckBox("Enable Task")
        snail_section.add_widget(snail_enable)
        amulet_combo = EmojiComboBox(["Keep", "Replace", "Stop", "Wait for command"])
        snail_section.add_widget(FormSection("Amulet", "Amulet action", amulet_combo))
        layout.addWidget(snail_section)
        
        crab_section = TabSection("🦀 Coconut Crab")
        crab_enable = EnhancedCheckBox("Enable Task")
        crab_section.add_widget(crab_enable)
        layout.addWidget(crab_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_misc_tab(self):
        """Create misc tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        ant_section = TabSection("🎯 Ant Challenge")
        ant_enable = EnhancedCheckBox("Enable Task")
        ant_section.add_widget(ant_enable)
        layout.addWidget(ant_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
