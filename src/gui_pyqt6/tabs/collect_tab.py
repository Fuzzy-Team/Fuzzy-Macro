"""
Collect Tab for Fuzzy Macro PyQt6 GUI
Collection and passive income management
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QPushButton
from ..components.custom_widgets import TabSection, EnhancedCheckBox, FormSection, MultiItemInput, EmojiComboBox
from ..constants import Emojis, Colors


class CollectTab(QWidget):
    """Collect tab for collection settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize collect tab UI"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        container = QWidget()
        layout = QVBoxLayout()
        
        # Regular Collection
        regular_section = TabSection("🎁 Regular Collection")
        for emoji, key in [("🕒", "wealth_clock"), ("🔵", "blueberry_dispenser"),
                           ("🍓", "strawberry_dispenser"), ("🥥", "coconut_dispenser"),
                           ("💎", "royal_jelly_dispenser"), ("🎫", "ant_pass_dispenser"),
                           ("🦴", "treat_dispenser"), ("🧴", "glue_dispenser"),
                           ("🟧", "honeystorm")]:
            check = EnhancedCheckBox(f"{emoji} {key.replace('_', ' ').title()}")
            regular_section.add_widget(check)
            setattr(self, f"{key}_check", check)
        layout.addWidget(regular_section)
        
        # Sticker Printer
        sticker_section = TabSection("🖨️ Sticker Printer")
        sticker_enable = EnhancedCheckBox("Enable Task")
        sticker_section.add_widget(sticker_enable)
        sticker_egg = EmojiComboBox(["Basic", "Silver", "Gold", "Diamond", "Mythic"])
        sticker_section.add_widget(FormSection("Egg Type", "Sticker egg rarity", sticker_egg))
        layout.addWidget(sticker_section)
        self.sticker_egg = sticker_egg
        
        # Mondo Buff
        mondo_section = TabSection("🐣 Mondo Buff")
        mondo_enable = EnhancedCheckBox("Enable Task")
        mondo_section.add_widget(mondo_enable)
        from ..components.custom_widgets import ValidatedLineEdit
        mondo_time = ValidatedLineEdit("int", char_limit=3, min_val=1)
        mondo_section.add_widget(FormSection("Damage For X Mins", "Duration", mondo_time))
        mondo_loot = EnhancedCheckBox("Collect Loot From Mondo")
        mondo_section.add_widget(mondo_loot)
        mondo_loops = EmojiComboBox([str(i) for i in range(1, 6)])
        mondo_section.add_widget(FormSection("Loops", "Collection loops", mondo_loops))
        layout.addWidget(mondo_section)
        
        # Memory Match
        memory_section = TabSection("🎮 Memory Match")
        for name, emoji in [("Memory Match", "🍍"), ("Mega Memory Match", "🌟"),
                            ("Extreme Memory Match", "🌶️"), ("Winter Memory Match", "❄️")]:
            check = EnhancedCheckBox(f"{emoji} {name}")
            memory_section.add_widget(check)
        layout.addWidget(memory_section)
        
        # Blender
        blender_section = TabSection("🧪 Blender")
        blender_enable = EnhancedCheckBox("Enable Task")
        blender_section.add_widget(blender_enable)
        reset_blender = QPushButton("Reset Blender Timers")
        blender_section.add_widget(reset_blender)
        blender_items = MultiItemInput(num_items=3)
        blender_section.add_widget(blender_items)
        layout.addWidget(blender_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
