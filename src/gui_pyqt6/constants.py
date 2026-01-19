"""
Constants and styling for Fuzzy Macro PyQt6 GUI
Includes colors, emojis, and style sheets
"""

# ==================== COLORS ====================
class Colors:
    # Primary backgrounds
    PRIMARY_BG = "#36393F"
    SECONDARY_BG = "#2F3136"
    DARK_BG = "#202225"
    
    # Accents
    PURPLE = "#7A77BB"
    LIGHT_PURPLE = "#C5C3F7"
    
    # Text
    TEXT_PRIMARY = "#E8E8E8"
    TEXT_SECONDARY = "#ADB4BC"
    
    # Borders
    BORDER = "#40444B"
    
    # Category colors
    GATHER_BLUE = "#5865F2"
    COLLECT_GREEN = "#57F287"
    KILL_RED = "#ED4245"
    QUEST_YELLOW = "#FEE75C"
    SPECIAL_PINK = "#EB459E"


# ==================== EMOJIS ====================
class Emojis:
    FIELDS = {
        "sunflower": "🌻",
        "dandelion": "🌼",
        "mushroom": "🍄",
        "blue_flower": "🔷",
        "clover": "🍀",
        "strawberry": "🍓",
        "spider": "🕸️",
        "bamboo": "🐼",
        "pineapple": "🍍",
        "stump": "🐌",
        "cactus": "🌵",
        "pumpkin": "🎃",
        "pine_tree": "🌲",
        "rose": "🌹",
        "mountain_top": "⛰️",
        "pepper": "🌶️",
        "coconut": "🥥"
    }
    
    COLLECT = {
        "wealth_clock": "🕒",
        "blueberry_dispenser": "🔵",
        "strawberry_dispenser": "🍓",
        "coconut_dispenser": "🥥",
        "royal_jelly_dispenser": "💎",
        "treat_dispenser": "🦴",
        "ant_pass_dispenser": "🎫",
        "glue_dispenser": "🧴",
        "stockings": "🧦",
        "feast": "🍽️",
        "samovar": "🏺",
        "snow_machine": "❄️",
        "lid_art": "🖼️",
        "candles": "🕯️",
        "wreath": "🎄",
        "sticker_printer": "🖨️",
        "mondo_buff": "🐣",
        "memory_match": "🍍",
        "mega_memory_match": "🌟",
        "extreme_memory_match": "🌶️",
        "winter_memory_match": "❄️",
        "honeystorm": "🟧",
        "auto_field_boost": "🎲"
    }
    
    KILL = {
        "stinger_hunt": "😈",
        "scorpion": "🦂",
        "werewolf": "🐺",
        "ladybug": "🐞",
        "rhinobeetle": "🪲",
        "spider": "🕷️",
        "mantis": "🦗",
        "ant_challenge": "🎯",
        "coconut_crab": "🦀",
        "stump_snail": "🐌",
    }
    
    PLANTERS = {
        "none": "",
        "paper": "📄",
        "ticket": "🎫",
        "festive": "🎄",
        "sticker": "🏷️",
        "plastic": "♻️",
        "candy": "🍬",
        "red_clay": "🔴",
        "blue_clay": "🔵",
        "tacky": "🟠",
        "pesticide": "☠️",
        "heat-treated": "🔥",
        "hydroponic": "💧",
        "petal": "🌸",
        "planter_of_plenty": "🏆"
    }
    
    BLENDER = {
        "red_extract": "🔴",
        "blue_extract": "🔵",
        "enzymes": "🧪",
        "oil": "🛢️",
        "glue": "🧴",
        "tropical_drink": "🍹",
        "gumdrops": "🍬",
        "moon_charm": "🌙",
        "glitter": "✨",
        "star_jelly": "⭐",
        "purple_potion": "🟣",
        "soft_wax": "🟡",
        "hard_wax": "🟤",
        "swirled_wax": "🌊",
        "caustic_wax": "💚",
        "field_dice": "🎲",
        "smooth_dice": "🎰",
        "loaded_dice": "🎯",
        "super_smoothie": "🥤",
        "turpentine": "🧴"
    }
    
    FIELD_BOOSTERS = {
        "blue_booster": "🔵",
        "red_booster": "🔴",
        "mountain_booster": "⚪"
    }
    
    NECTARS = {
        "comforting": "🧡",
        "motivating": "💛",
        "satisfying": "💚",
        "refreshing": "💙",
        "invigorating": "💜"
    }
    
    QUESTS = {
        "polar_bear_quest": "🐻‍❄️",
        "honey_bee_quest": "🐝",
        "bucko_bee_quest": "💙",
        "riley_bee_quest": "❤️"
    }


# ==================== FIELD DATA ====================
class FieldData:
    FIELD_NAMES = [
        "sunflower", "dandelion", "mushroom", "blue_flower", "clover",
        "strawberry", "spider", "bamboo", "pineapple", "stump",
        "cactus", "pumpkin", "pine_tree", "rose", "mountain_top",
        "pepper", "coconut"
    ]
    
    FIELD_NAMES_DISPLAY = [
        "🌻 Sunflower", "🌼 Dandelion", "🍄 Mushroom", "🔷 Blue Flower", "🍀 Clover",
        "🍓 Strawberry", "🕸️ Spider", "🐼 Bamboo", "🍍 Pineapple", "🐌 Stump",
        "🌵 Cactus", "🎃 Pumpkin", "🌲 Pine Tree", "🌹 Rose", "⛰️ Mountain Top",
        "🌶️ Pepper", "🥥 Coconut"
    ]
    
    PATTERN_SIZES = ["XS", "S", "M", "L", "XL"]
    PATTERN_WIDTHS = list(range(1, 9))
    
    RETURN_METHODS = ["reset", "walk", "rejoin", "whirligig"]
    RETURN_METHODS_DISPLAY = ["💀 Reset", "👟 Walk", "🔄 Rejoin", "🌱 Whirligig"]
    
    START_LOCATIONS = [
        "center", "upper_right", "right", "lower_right", "bottom",
        "lower_left", "left", "upper_left", "top"
    ]
    START_LOCATIONS_DISPLAY = [
        "🎯 Center", "📍 Upper Right", "➡️ Right", "📍 Lower Right", "⬇️ Bottom",
        "📍 Lower Left", "⬅️ Left", "📍 Upper Left", "⬆️ Top"
    ]
    
    START_LOCATION_DISTANCES = list(range(1, 11))
    CAMERA_TURN_DIRECTIONS = ["None", "Left", "Right"]
    CAMERA_TURN_TIMES = [1, 2, 3, 4]


# ==================== STYLE SHEETS ====================
GLOBAL_STYLESHEET = f"""
    QMainWindow {{
        background-color: {Colors.PRIMARY_BG};
        color: {Colors.TEXT_PRIMARY};
    }}
    
    QTabWidget::pane {{
        border: none;
        background-color: {Colors.PRIMARY_BG};
    }}
    
    QTabBar::tab {{
        background-color: {Colors.SECONDARY_BG};
        color: {Colors.TEXT_PRIMARY};
        padding: 8px 16px;
        border: none;
        border-bottom: 3px solid {Colors.SECONDARY_BG};
    }}
    
    QTabBar::tab:selected {{
        background-color: {Colors.PRIMARY_BG};
        border-bottom: 3px solid {Colors.PURPLE};
    }}
    
    QTabBar::tab:hover {{
        background-color: {Colors.PRIMARY_BG};
    }}
    
    QWidget {{
        background-color: {Colors.PRIMARY_BG};
        color: {Colors.TEXT_PRIMARY};
    }}
    
    QLabel {{
        color: {Colors.TEXT_PRIMARY};
    }}
    
    QPushButton {{
        background-color: {Colors.PURPLE};
        color: white;
        border: none;
        border-radius: 5px;
        padding: 8px 16px;
        font-weight: bold;
    }}
    
    QPushButton:hover {{
        background-color: {Colors.LIGHT_PURPLE};
    }}
    
    QPushButton:pressed {{
        background-color: #6a6795;
    }}
    
    QPushButton:disabled {{
        background-color: #555555;
        color: #888888;
    }}
    
    QLineEdit {{
        background-color: {Colors.SECONDARY_BG};
        color: {Colors.TEXT_PRIMARY};
        border: 2px solid {Colors.BORDER};
        border-radius: 4px;
        padding: 6px;
        selection-background-color: {Colors.PURPLE};
    }}
    
    QLineEdit:focus {{
        border: 2px solid {Colors.PURPLE};
    }}
    
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
    
    QTextEdit {{
        background-color: {Colors.SECONDARY_BG};
        color: {Colors.TEXT_PRIMARY};
        border: 2px solid {Colors.BORDER};
        border-radius: 4px;
        padding: 6px;
    }}
    
    QTextEdit:focus {{
        border: 2px solid {Colors.PURPLE};
    }}
    
    QSpinBox, QDoubleSpinBox {{
        background-color: {Colors.SECONDARY_BG};
        color: {Colors.TEXT_PRIMARY};
        border: 2px solid {Colors.BORDER};
        border-radius: 4px;
        padding: 6px;
    }}
    
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {Colors.PURPLE};
    }}
    
    QSlider::groove:horizontal {{
        background-color: {Colors.SECONDARY_BG};
        border: 1px solid {Colors.BORDER};
        height: 8px;
        margin: 0px;
        border-radius: 4px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {Colors.PURPLE};
        border: 1px solid {Colors.PURPLE};
        width: 18px;
        margin: -5px 0;
        border-radius: 9px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: {Colors.LIGHT_PURPLE};
    }}
    
    QScrollBar:vertical {{
        background-color: {Colors.SECONDARY_BG};
        width: 10px;
        border-radius: 5px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {Colors.BORDER};
        border-radius: 5px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {Colors.PURPLE};
    }}
    
    QScrollBar:horizontal {{
        background-color: {Colors.SECONDARY_BG};
        height: 10px;
        border-radius: 5px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {Colors.BORDER};
        border-radius: 5px;
        min-width: 20px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {Colors.PURPLE};
    }}
    
    QScrollBar::add-line, QScrollBar::sub-line {{
        border: none;
        background: none;
    }}
    
    QGroupBox {{
        color: {Colors.TEXT_PRIMARY};
        border: 2px solid {Colors.BORDER};
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }}
    
    QHeaderView::section {{
        background-color: {Colors.SECONDARY_BG};
        color: {Colors.TEXT_PRIMARY};
        padding: 5px;
        border: 1px solid {Colors.BORDER};
    }}
    
    QTableWidget {{
        background-color: {Colors.PRIMARY_BG};
        alternate-background-color: {Colors.SECONDARY_BG};
        gridline-color: {Colors.BORDER};
    }}
    
    QTableWidget::item {{
        padding: 5px;
    }}
    
    QTableWidget::item:selected {{
        background-color: {Colors.PURPLE};
    }}
    
    QMessageBox {{
        background-color: {Colors.PRIMARY_BG};
    }}
    
    QMessageBox QLabel {{
        color: {Colors.TEXT_PRIMARY};
    }}
    
    QDialog {{
        background-color: {Colors.PRIMARY_BG};
    }}
"""

def get_category_color(category: str) -> str:
    """Get color for a given task category"""
    category = category.lower()
    if "gather" in category:
        return Colors.GATHER_BLUE
    elif "collect" in category:
        return Colors.COLLECT_GREEN
    elif "kill" in category:
        return Colors.KILL_RED
    elif "quest" in category:
        return Colors.QUEST_YELLOW
    else:
        return Colors.SPECIAL_PINK
