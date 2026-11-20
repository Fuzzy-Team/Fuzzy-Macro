"""Colours for report images, matched to the macro's GUI theme."""

import re

from modules.misc.settings_defaults import DEFAULT_GENERAL_SETTINGS


# The dark palette every report theme starts from. The first block mirrors the
# webapp's default tokens; the second is the panel and graph chrome.
_REPORT_BASE = {
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

    "canvas":         (18, 18, 18),    # behind and between the panels
    "panel":          (32, 30, 32),
    "panel_outline":  (40, 38, 40),
    "graph_bg":       (20, 20, 20),
    "graph_grid":     (47, 47, 55),
    "graph_tick":     (64, 60, 78),
}


# How strongly each base colour is washed toward the theme accent. Dark
# surfaces take a noticeable tint so each theme reads as its colour, while text
# and the activity colours keep most of their own identity to stay legible.
# The canvas stays nearly neutral so the panels stand out from it.
_MIX_RATIOS = {
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

    "canvas":         0.05,
    "panel":          0.15,
    "panel_outline":  0.20,
    "graph_bg":       0.10,
    "graph_grid":     0.22,
    "graph_tick":     0.22,
}


# How vivid the accent is made before it is washed into the base. The accent
# itself stays the true theme colour; only the tints use this boosted version so
# close hues (e.g. Brown and Cream) still read as different colours.
TINT_SATURATION = 1.7


# One entry per GUI theme in webapp/scripts/themes.js, keyed by its normalized
# gui_theme value. "accent" is the theme's --primary. Any other key from
# _REPORT_BASE sets that colour outright instead of tinting it, for themes that
# change more than the accent (e.g. a coloured background).
REPORT_THEMES = {
    "brown":       {"accent": (171, 128, 98)},   # Fuzzy        #ab8062
    "cream":       {"accent": (239, 218, 152)},  # Gifted Fuzzy #efda98
    "red":         {"accent": (203, 65,  68)},   # Precise      #cb4144
    "blue":        {"accent": (63,  193, 195)},  # Bouyant      #3fc1c3
    "commander":   {"accent": (90,  209, 114)},  # Commander    #5ad172
    "purple":      {"accent": (157, 142, 195)},  # Mythic       #9d8ec3
    "basic_black": {"accent": (255, 200, 0)},    # Basic Bee    #ffc800
    "gummy":       {"accent": (255, 0,   255)},  # Gummy        #ff00ff
    "tadpole":     {"accent": (32,  189, 150)},  # Tadpole      #20bd96
    "gifted_tad":  {"accent": (144, 240, 224)},  # Gifted Tad   #90f0e0
    "spicy_bee":   {"accent": (207, 32,  19)},   # Spicy Bee    #cf2013
    "beesmas": {                                 # Beesmas      #ff6b6b on winter blue
        "accent":         (255, 107, 107),
        "bg":             (13,  31,  60),
        "sidebar_bg":     (17,  38,  72),
        "card_bg":        (21,  48,  90),
        "text_primary":   (238, 244, 255),
        "text_secondary": (168, 188, 220),
        "grid":           (52,  78,  120),
        "canvas":         (11,  26,  51),
        "panel":          (21,  48,  90),
        "panel_outline":  (43,  75,  124),
        "graph_bg":       (15,  35,  66),
        "graph_grid":     (40,  66,  108),
        "graph_tick":     (60,  88,  132),
    },
}

DEFAULT_THEME = "brown"


# Alternate spellings of gui_theme that resolve to a report theme.
_THEME_ALIASES = {
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


def mixColor(base, accent, ratio):
    """Blend a base colour toward the accent (0.0 = base, 1.0 = accent)."""
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(round(b * (1 - ratio) + a * ratio)) for b, a in zip(base, accent))


def saturate(color, factor):
    """Push a colour away from grey to amplify its hue (factor > 1 = more vivid)."""
    mean = sum(color) / 3.0
    return tuple(int(round(max(0, min(255, mean + (c - mean) * factor)))) for c in color)


def buildReportTheme(spec):
    """Full report palette for a theme: the base tinted toward its accent, plus its own overrides."""
    accent = tuple(spec["accent"])
    tint = saturate(accent, TINT_SATURATION)
    palette = {key: mixColor(base, tint, _MIX_RATIOS[key]) for key, base in _REPORT_BASE.items()}
    palette.update({key: tuple(color) for key, color in spec.items()})
    return palette


THEMES = {name: buildReportTheme(spec) for name, spec in REPORT_THEMES.items()}


def customThemeSpec(setdat):
    """Report colours for the Custom theme, from the six gui_color_* hex settings."""
    def color(name):
        raw = str(setdat.get(name, "")).strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
            raw = DEFAULT_GENERAL_SETTINGS[name]
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))

    bg, section, text = color("gui_color_background"), color("gui_color_section"), color("gui_color_text")
    return {
        "accent":         color("gui_color_accent"),
        "bg":             bg,
        "canvas":         bg,
        "sidebar_bg":     section,
        "card_bg":        section,
        "panel":          section,
        "panel_outline":  mixColor(section, text, 0.15),
        "graph_bg":       mixColor(bg, (0, 0, 0), 0.15),
        "text_primary":   text,
        "text_secondary": mixColor(text, bg, 0.35),
    }


def resolveReportTheme(guiTheme, setdat=None):
    """Map a macro gui_theme value to its matching report theme key. The Custom theme is built from setdat."""
    key = str(guiTheme or "").strip().lower().replace(" ", "_")
    key = _THEME_ALIASES.get(key, key)
    if key == "custom":
        THEMES[key] = buildReportTheme(customThemeSpec(setdat if isinstance(setdat, dict) else {}))
    return key if key in THEMES else DEFAULT_THEME
