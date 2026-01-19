"""
Config Tab for Fuzzy Macro PyQt6 GUI
Global settings with multiple sub-tabs
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea
from ..components.custom_widgets import TabSection, EnhancedCheckBox, FormSection, ValidatedLineEdit, EmojiComboBox, DragDropListWidget, KeybindRecorder
from ..constants import Colors, FieldData


class ConfigTab(QWidget):
    """Config tab with multiple sub-tabs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize config tab UI"""
        layout = QVBoxLayout()
        
        # Sub-tabs
        self.tabs = QTabWidget()
        
        # BSS Tab
        bss_widget = self._create_bss_tab()
        self.tabs.addTab(bss_widget, "🐝 BSS")
        
        # Priorities Tab
        priorities_widget = self._create_priorities_tab()
        self.tabs.addTab(priorities_widget, "📋 Priorities")
        
        # Other Tab
        other_widget = self._create_other_tab()
        self.tabs.addTab(other_widget, "⚙️ Other")
        
        # Discord Tab
        discord_widget = self._create_discord_tab()
        self.tabs.addTab(discord_widget, "💬 Discord")
        
        # Stream Tab
        stream_widget = self._create_stream_tab()
        self.tabs.addTab(stream_widget, "🎥 Stream")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def _create_bss_tab(self):
        """Create BSS configuration tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        basic_section = TabSection("🏠 Basic")
        hive_combo = EmojiComboBox([str(i) for i in range(1, 7)])
        basic_section.add_widget(FormSection("Hive Slot", "Hive location slot", hive_combo))
        movespeed = ValidatedLineEdit("float", char_limit=5)
        basic_section.add_widget(FormSection("Movespeed", "Character movement speed", movespeed))
        bees = ValidatedLineEdit("int", char_limit=2)
        basic_section.add_widget(FormSection("Bees", "Number of bees", bees))
        layout.addWidget(basic_section)
        
        sprinkler_section = TabSection("💧 Sprinkler")
        sprinkler_type = EmojiComboBox(["Basic", "Silver", "Golden", "Diamond", "Saturator"])
        sprinkler_section.add_widget(FormSection("Type", "Sprinkler type", sprinkler_type))
        sprinkler_slot = EmojiComboBox([str(i) for i in range(1, 7)])
        sprinkler_section.add_widget(FormSection("Slot", "Sprinkler slot", sprinkler_slot))
        layout.addWidget(sprinkler_section)
        
        goo_section = TabSection("💧 Goo")
        goo_slot = EmojiComboBox([str(i) for i in range(1, 8)])
        goo_section.add_widget(FormSection("Goo Slot", "Backpack slot", goo_slot))
        layout.addWidget(goo_section)
        
        balloon_section = TabSection("🎈 Balloon")
        balloon_convert = EmojiComboBox(["Always", "Every X", "Never"])
        balloon_section.add_widget(FormSection("Convert", "Balloon conversion", balloon_convert))
        layout.addWidget(balloon_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_priorities_tab(self):
        """Create task priorities tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        priority_section = TabSection("📊 Task Priorities")
        priority_list = DragDropListWidget()
        
        # Sample task categories
        tasks = [
            ("Gather: Sunflower", "gather"),
            ("Gather: Dandelion", "gather"),
            ("Collect: Wealth Clock", "collect"),
            ("Collect: Blender", "collect"),
            ("Kill: Vicious Bee", "kill"),
            ("Planters: Manual", "special"),
            ("Quests: Honey Bee", "quest"),
        ]
        
        for task, category in tasks:
            priority_list.add_item_with_category(task, category, task)
        
        priority_section.add_widget(priority_list)
        layout.addWidget(priority_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_other_tab(self):
        """Create other settings tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        rejoin_section = TabSection("🔄 Rejoining")
        private_server = ValidatedLineEdit("text")
        rejoin_section.add_widget(FormSection("Private Server Link", "Server URL", private_server))
        rejoin_method = EmojiComboBox(["Deeplink", "New Tab", "Reload"])
        rejoin_section.add_widget(FormSection("Rejoin Method", "How to rejoin", rejoin_method))
        rejoin_hours = ValidatedLineEdit("float", char_limit=4)
        rejoin_section.add_widget(FormSection("Rejoin Every X Hours", "Rejoin interval", rejoin_hours))
        layout.addWidget(rejoin_section)
        
        haste_section = TabSection("⚡ Haste")
        haste_check = EnhancedCheckBox("Enable Haste Compensation")
        haste_section.add_widget(haste_check)
        layout.addWidget(haste_section)
        
        keybind_section = TabSection("⌨️ Keybinds")
        start_keybind = KeybindRecorder()
        keybind_section.add_widget(FormSection("Start Macro", "Start keybind", start_keybind))
        stop_keybind = KeybindRecorder()
        keybind_section.add_widget(FormSection("Stop Macro", "Stop keybind", stop_keybind))
        layout.addWidget(keybind_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_discord_tab(self):
        """Create Discord settings tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        webhook_section = TabSection("🔗 Webhook")
        webhook_enable = EnhancedCheckBox("Enable Webhook")
        webhook_section.add_widget(webhook_enable)
        webhook_link = ValidatedLineEdit("text")
        webhook_section.add_widget(FormSection("Webhook Link", "Discord webhook URL", webhook_link))
        layout.addWidget(webhook_section)
        
        bot_section = TabSection("🤖 Discord Bot")
        bot_enable = EnhancedCheckBox("Enable Discord Bot")
        bot_section.add_widget(bot_enable)
        bot_token = ValidatedLineEdit("text")
        bot_section.add_widget(FormSection("Bot Token", "Discord bot token", bot_token))
        layout.addWidget(bot_section)
        
        pings_section = TabSection("🔔 Discord Pings")
        pings_enable = EnhancedCheckBox("Enable Pings")
        pings_section.add_widget(pings_enable)
        user_id = ValidatedLineEdit("text")
        pings_section.add_widget(FormSection("User ID", "Discord user ID", user_id))
        layout.addWidget(pings_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
    
    def _create_stream_tab(self):
        """Create stream settings tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        stream_section = TabSection("🎥 Stream")
        stream_enable = EnhancedCheckBox("Enable Stream Mode")
        stream_section.add_widget(stream_enable)
        pin_stream = EnhancedCheckBox("Pin Stream URL in Discord")
        stream_section.add_widget(pin_stream)
        layout.addWidget(stream_section)
        
        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll
