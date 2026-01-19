"""
Boost Tab for Fuzzy Macro PyQt6 GUI
Hotbar and field booster management
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QLabel
from ..components.custom_widgets import TabSection, EnhancedCheckBox, FormSection, EmojiComboBox, ValidatedLineEdit


class BoostTab(QWidget):
    """Boost tab with hotbar and buffs sub-tabs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize boost tab UI"""
        layout = QVBoxLayout()
        
        tabs = QTabWidget()
        
        # Hotbar tab
        hotbar_widget = self._create_hotbar_tab()
        tabs.addTab(hotbar_widget, "🎯 Hotbar")
        
        # Buffs tab
        buffs_widget = self._create_buffs_tab()
        tabs.addTab(buffs_widget, "💪 Buffs")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
    
    def _create_hotbar_tab(self):
        """Create hotbar configuration tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        hotbar_section = TabSection("🎯 Hotbar Slots")
        
        for i in range(1, 8):
            slot_layout = QHBoxLayout()
            slot_label = QLabel(f"Slot {i}:")
            use_when = EmojiComboBox(["Never", "Always", "Gathering", "Converting"])
            every_val = ValidatedLineEdit("float", char_limit=6)
            every_unit = EmojiComboBox(["Secs", "Mins"])
            
            slot_layout.addWidget(slot_label)
            slot_layout.addWidget(use_when)
            slot_layout.addWidget(QLabel("Every"))
            slot_layout.addWidget(every_val)
            slot_layout.addWidget(every_unit)
            slot_layout.addStretch()
            
            hotbar_section.add_layout(slot_layout)
        
        layout.addWidget(hotbar_section)
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_buffs_tab(self):
        """Create field buffs configuration tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        boosters_section = TabSection("🎲 Field Boosters")
        gather_boost = EnhancedCheckBox("Gather in boosted fields")
        boosters_section.add_widget(gather_boost)
        separation = ValidatedLineEdit("int", char_limit=4)
        boosters_section.add_widget(FormSection("Separate Boosts", "Minutes between boosts", separation))
        
        for name in ["Blue Booster", "Red Booster", "Mountain Booster"]:
            check = EnhancedCheckBox(name)
            boosters_section.add_widget(check)
        
        layout.addWidget(boosters_section)
        
        afb_section = TabSection("🎲 Auto Field Boost (AFB)")
        
        from PyQt6.QtWidgets import QPushButton
        reset_afb_btn = QPushButton("🔄 Reset AFB Timings")
        afb_section.add_widget(reset_afb_btn)
        
        afb_enable = EnhancedCheckBox("Enable AFB")
        afb_section.add_widget(afb_enable)
        
        afb_wait = ValidatedLineEdit("int", char_limit=3)
        afb_section.add_widget(FormSection("Wait X Secs", "Initial wait time", afb_wait))
        
        afb_rebuff = ValidatedLineEdit("float", char_limit=4)
        afb_section.add_widget(FormSection("Re-Buff Every X Mins", "Rebuff interval", afb_rebuff))
        
        afb_field = EmojiComboBox(["Sunflower", "Dandelion", "Mushroom"])
        afb_section.add_widget(FormSection("Field", "Target field", afb_field))
        
        afb_dice = EmojiComboBox(["Field Dice", "Smooth Dice", "Loaded Dice"])
        afb_section.add_widget(FormSection("Dice", "Dice type", afb_dice))
        
        afb_dice_slot = EmojiComboBox([str(i) for i in range(8)])
        afb_section.add_widget(FormSection("Dice Slot", "Inventory slot", afb_dice_slot))
        
        afb_attempts = ValidatedLineEdit("int", char_limit=3)
        afb_section.add_widget(FormSection("Dice Attempts", "Number of attempts", afb_attempts))
        
        afb_glitter = EnhancedCheckBox("Use Glitter")
        afb_section.add_widget(afb_glitter)
        
        afb_glitter_slot = EmojiComboBox([str(i) for i in range(8)])
        afb_section.add_widget(FormSection("Glitter Slot", "Inventory slot", afb_glitter_slot))
        
        afb_time_limit = EnhancedCheckBox("Enable Time Limit")
        afb_section.add_widget(afb_time_limit)
        
        afb_time_val = ValidatedLineEdit("float", char_limit=4)
        afb_section.add_widget(FormSection("Time Limit", "Duration in minutes", afb_time_val))
        
        layout.addWidget(afb_section)
        
        sticker_section = TabSection("🏷️ Sticker Stack")
        sticker_enable = EnhancedCheckBox("Enable Task")
        sticker_section.add_widget(sticker_enable)
        sticker_item = EmojiComboBox(["Sticker", "Ticket", "Sticker/Ticket"])
        sticker_section.add_widget(FormSection("Item", "Item type", sticker_item))
        hive_skins = EnhancedCheckBox("Use Hive Skins")
        sticker_section.add_widget(hive_skins)
        layout.addWidget(sticker_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
