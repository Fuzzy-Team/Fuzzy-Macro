"""Colors for report images, derived from the macro's GUI theme."""



# ---------------------------------------------------------------------------
# Theme / color configuration
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg":           (14, 15, 19),
        "sidebar_bg":   (23, 25, 29),
        "card_bg":      (28, 30, 36),
        "text_primary": (255, 255, 255),
        "text_secondary": (175, 175, 175),
        "grid":         (65, 65, 65),
        "gather":       (166, 255, 124),
        "convert":      (254, 202, 64),
        "bug_run":      (200, 100, 80),
        "other":        (133, 154, 173),
        "honey":        (248, 191, 23),
    },
    "midnight": {
        "bg":           (6, 7, 9),
        "sidebar_bg":   (12, 14, 18),
        "card_bg":      (20, 22, 28),
        "text_primary": (230, 230, 240),
        "text_secondary": (160, 160, 170),
        "grid":         (40, 40, 48),
        "gather":       (130, 220, 90),
        "convert":      (220, 170, 40),
        "bug_run":      (180, 80, 60),
        "other":        (100, 120, 140),
        "honey":        (220, 170, 20),
    },
    "oled": {
        "bg":           (0, 0, 0),
        "sidebar_bg":   (10, 10, 12),
        "card_bg":      (16, 16, 20),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 200, 210),
        "grid":         (35, 35, 40),
        "gather":       (166, 255, 124),
        "convert":      (254, 202, 64),
        "bug_run":      (255, 80, 60),
        "other":        (140, 160, 180),
        "honey":        (255, 200, 30),
    },
}


ACCENT_COLORS = {
    "green":  (34, 255, 6),
    "purple": (153, 102, 255),
    "blue":   (86, 164, 228),
    "gold":   (254, 202, 64),
    "pink":   (255, 102, 178),
}


# ---------------------------------------------------------------------------
# Macro GUI themes
# Every macro GUI theme (the gui_theme setting) gets a matching report theme so
# the hourly/session report looks like the rest of the macro. Mirroring the
# webapp — where each theme only overrides --primary — the macro themes share a
# common dark base and differ only by their accent colour.
# ---------------------------------------------------------------------------

_MACRO_REPORT_BASE = {
    "bg":             (18, 18, 18),    # webapp --background  #121212
    "sidebar_bg":     (24, 24, 24),
    "card_bg":        (30, 30, 30),    # webapp --surface     #1E1E1E
    "text_primary":   (224, 224, 224), # webapp --text-main   #E0E0E0
    "text_secondary": (160, 160, 160), # webapp --text-dim    #A0A0A0
    "grid":           (60, 60, 60),
    "gather":         (166, 255, 124),
    "convert":        (254, 202, 64),
    "bug_run":        (200, 100, 80),
    "other":          (133, 154, 173),
    "honey":          (248, 191, 23),
}


# normalized gui_theme value -> accent colour (the webapp --primary for that theme)
MACRO_THEME_ACCENTS = {
    "brown":       (171, 128, 98),   # Fuzzy        #ab8062
    "cream":       (239, 218, 152),  # Gifted Fuzzy #efda98
    "red":         (203, 65,  68),   # Precise      #cb4144
    "blue":        (63,  193, 195),  # Bouyant      #3fc1c3
    "commander":   (90,  209, 114),  # Commander    #5ad172
    "purple":      (157, 142, 195),  # Mythic       #9d8ec3
    "basic_black": (255, 200, 0),    # Basic Bee    #ffc800
    "gummy":       (255, 0,   255),  # Gummy        #ff00ff
    "tadpole":     (32,  189, 150),  # Tadpole      #20bd96
    "gifted_tad":  (144, 240, 224),  # Gifted Tad   #90f0e0
    "spicy_bee":   (207, 32,  19),    # Spicy Bee    #cf2013
}


def mixColor(base, accent, ratio):
    """Blend a base colour toward the accent (0.0 = base, 1.0 = accent)."""
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(round(b * (1 - ratio) + a * ratio)) for b, a in zip(base, accent))


def saturate(color, factor):
    """Push a colour away from grey to amplify its hue (factor > 1 = more vivid).

    Surfaces are tinted toward a saturated version of the accent so that themes
    with similar hues (e.g. the warm Brown and Cream) stay visually distinct
    even at the low tint ratios used for the dark backgrounds."""
    mean = sum(color) / 3.0
    return tuple(int(round(max(0, min(255, mean + (c - mean) * factor)))) for c in color)


# How vivid the accent is made before it is washed into the dark surfaces. The
# highlight/line accent itself stays the true theme colour; only the background
# tints use this boosted version so close hues read as different colours.
MACRO_TINT_SATURATION = 1.7


# How strongly each palette component is washed toward the theme accent. Dark
# surfaces take a noticeable tint so each theme clearly reads as its colour,
# while text and the semantic activity colours keep most of their own identity
# to stay legible and meaningful.
_MACRO_MIX_RATIOS = {
    "bg":             0.09,
    "sidebar_bg":     0.12,
    "card_bg":        0.14,
    "grid":           0.24,
    "text_primary":   0.04,
    "text_secondary": 0.16,
    "gather":         0.07,
    "convert":        0.07,
    "bug_run":        0.10,
    "other":          0.15,
    "honey":          0.07,
}


# Very subtle tint for the canvas base (the area behind/between panels). Kept
# far lighter than the panels so the report stays dark and the panels still read
# as the theme colour.
MACRO_BASE_BG_MIX = 0.05


def buildMacroReportTheme(accent):
    """Build a full report palette tinted toward a macro theme's accent colour."""
    tint = saturate(accent, MACRO_TINT_SATURATION)
    theme = {
        key: mixColor(base, tint, _MACRO_MIX_RATIOS.get(key, 0.15))
        for key, base in _MACRO_REPORT_BASE.items()
    }
    theme["accent"] = tuple(accent)
    return theme


# Register a tinted report theme for every macro GUI theme.
for _macroTheme, _macroAccent in MACRO_THEME_ACCENTS.items():
    THEMES[_macroTheme] = buildMacroReportTheme(_macroAccent)


# Aliases so alternate spellings of gui_theme still resolve to a report theme.
_MACRO_THEME_ALIASES = {
    "comander":       "commander",
    "basic_bee":      "basic_black",
    "gifted_tadpole": "gifted_tad",
    "gifted_fuzzy":   "cream",
    "fuzzy":          "brown",
    "mythic":         "purple",
    "precise":        "red",
    "bouyant":        "blue",
    "buoyant":        "blue",
}


def resolveReportTheme(guiTheme, fallback="brown"):
    """Map a macro gui_theme value to its matching report theme key."""
    key = str(guiTheme or "").strip().lower().replace(" ", "_")
    key = _MACRO_THEME_ALIASES.get(key, key)
    if key in THEMES:
        return key
    return fallback if fallback in THEMES else "dark"
