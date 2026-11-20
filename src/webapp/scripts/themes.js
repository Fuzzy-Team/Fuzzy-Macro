// Every GUI theme. `value` is what the gui_theme setting saves, `label` is shown
// in the theme dropdown, and `id` goes on <html data-theme="..."> so style.css can
// restyle anything for that theme. The first theme is the default.
// The matching report colours live in modules/reports/theme.py.
const GUI_THEMES = [
  { id: "brown", value: "Brown", label: "Fuzzy Theme" },
  { id: "cream", value: "Cream", label: "Gifted Fuzzy Theme" },
  { id: "red", value: "Red", label: "Precise Theme" },
  { id: "blue", value: "blue", label: "Bouyant Theme" },
  { id: "commander", value: "Commander", label: "Commander Theme", aliases: ["comander"] },
  { id: "purple", value: "Purple", label: "Mythic Theme" },
  { id: "basic-black", value: "Basic Black", label: "Basic Bee Theme" },
  { id: "gummy", value: "Gummy", label: "Gummy Theme" },
  { id: "tadpole", value: "Tadpole", label: "Tadpole Theme" },
  { id: "gifted-tad", value: "Gifted Tad", label: "Gifted Tad Theme", aliases: ["gifted tadpole"] },
  { id: "spicy-bee", value: "Spicy Bee", label: "Spicy Bee Theme" },
  { id: "beesmas", value: "Beesmas", label: "Beesmas Theme" },
  { id: "custom", value: "Custom", label: "Custom Theme" },
];

// The Custom theme's six colours, as #RRGGBB settings (the # keeps the settings file from reading 001122 as a number). Defaults match
// DEFAULT_GENERAL_SETTINGS in settings_defaults.py (the Fuzzy theme).
const CUSTOM_THEME_COLORS = {
  gui_color_background: "#121212",
  gui_color_section: "#1E1E1E",
  gui_color_object: "#2B2B2B",
  gui_color_text: "#E0E0E0",
  gui_color_accent: "#AB8062",
  gui_color_accent_text: "#121212",
};
// A typed colour, with or without the #
const HEX_COLOR = /^#?[0-9A-Fa-f]{6}$/;
const normalizeHex = (text) => "#" + text.trim().replace(/^#/, "").toUpperCase();

function readCustomColors() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem("gui_custom_colors")) || {};
  } catch (e) {
    /* storage unavailable or corrupt: use the defaults */
  }
  const colors = {};
  for (const [key, fallback] of Object.entries(CUSTOM_THEME_COLORS)) {
    colors[key] = HEX_COLOR.test(saved[key]) ? normalizeHex(saved[key]) : fallback;
  }
  return colors;
}

const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

function mixHex(a, b, ratio) {
  const [ra, rb] = [hexToRgb(a), hexToRgb(b)];
  return ra.map((channel, i) => Math.round(channel * (1 - ratio) + rb[i] * ratio));
}

const toHex = (rgb) => "#" + rgb.map((c) => c.toString(16).padStart(2, "0")).join("");

// Turn the six colours into the same :root tokens a built-in theme overrides.
function customThemeTokens(colors) {
  const c = colors;
  return {
    "--background": c.gui_color_background,
    "--surface": c.gui_color_section,
    "--surface-hover": c.gui_color_object,
    "--surface-dim": toHex(mixHex(c.gui_color_background, "#000000", 0.15)),
    "--textbox-bg": c.gui_color_object,
    "--drag-item-bg": c.gui_color_object,
    "--primary": c.gui_color_accent,
    "--primary-hover": toHex(mixHex(c.gui_color_accent, "#FFFFFF", 0.18)),
    "--primary-rgb": hexToRgb(c.gui_color_accent).join(", "),
    "--on-primary": c.gui_color_accent_text,
    "--text-main": c.gui_color_text,
    "--text-dim": toHex(mixHex(c.gui_color_text, c.gui_color_background, 0.35)),
    "--border": toHex(mixHex(c.gui_color_section, c.gui_color_text, 0.15)),
    "--active-text": c.gui_color_accent_text,
  };
}

// Custom colours are inline styles on <html>, so they are only present while the Custom theme is on.
function paintCustomTheme(themeId) {
  const style = document.documentElement.style;
  const tokens = customThemeTokens(readCustomColors());
  for (const name of Object.keys(tokens)) {
    if (themeId === "custom") style.setProperty(name, tokens[name]);
    else style.removeProperty(name);
  }
}

// Remember the saved colours so the next page load paints them before first paint.
function setCustomColors(colors) {
  try {
    localStorage.setItem("gui_custom_colors", JSON.stringify(colors));
  } catch (e) {
    /* the setting is still saved by the macro */
  }
  paintCustomTheme(document.documentElement.dataset.theme);
}

function applyTheme(value) {
  if (value) localStorage.setItem("gui_theme", value);
  const key = String(value || "").toLowerCase();
  const theme =
    GUI_THEMES.find((t) => t.value.toLowerCase() === key || (t.aliases || []).includes(key)) || GUI_THEMES[0];
  document.documentElement.dataset.theme = theme.id;
  paintCustomTheme(theme.id);
}

// Apply the last theme before the page paints so it doesn't flash the default.
applyTheme(localStorage.getItem("gui_theme"));
