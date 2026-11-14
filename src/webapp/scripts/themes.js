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
];

function applyTheme(value) {
  if (value) localStorage.setItem("gui_theme", value);
  const key = String(value || "").toLowerCase();
  const theme =
    GUI_THEMES.find((t) => t.value.toLowerCase() === key || (t.aliases || []).includes(key)) || GUI_THEMES[0];
  document.documentElement.dataset.theme = theme.id;
}

// Apply the last theme before the page paints so it doesn't flash the default.
applyTheme(localStorage.getItem("gui_theme"));
