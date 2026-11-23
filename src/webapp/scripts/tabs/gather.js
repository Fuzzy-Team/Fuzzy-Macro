/*
=============================================
Gather Tab
=============================================
*/
var fieldNo = 1;
const gatherFieldProperties = [
  "shift_lock",
  "field_drift_compensation",
  "shape",
  "size",
  "width",
  "invert_lr",
  "invert_fb",
  "turn",
  "turn_times",
  "mins",
  "backpack",
  "infinite_gather",
  "return",
  "use_whirlwig_fallback",
  "start_location",
  "distance",
  "sprinkler_offset_x",
  "sprinkler_offset_y",
  "goo",
  "goo_interval",
  "pine_dupe_detection",
];
let gatherPatternMetadata = {};
let activeGatherFieldData = {};
let activeGatherPattern = "";

function normalizeGatherFieldData(fieldData) {
  return {
    ...(fieldData && typeof fieldData === "object" ? fieldData : {}),
    infinite_gather: Boolean(fieldData?.infinite_gather),
  };
}

function getGatherPatternPresets(fieldData) {
  if (
    !fieldData ||
    typeof fieldData.pattern_presets !== "object" ||
    Array.isArray(fieldData.pattern_presets)
  ) {
    return {};
  }
  return fieldData.pattern_presets;
}

function getGatherFieldDataFromInputs() {
  const fieldData = generateSettingObject(gatherFieldProperties);
  fieldData.pattern_presets = getGatherPatternPresets(activeGatherFieldData);
  return fieldData;
}

function rememberGatherPatternPreset(fieldData, pattern) {
  if (!pattern) return fieldData;
  const presets = getGatherPatternPresets(fieldData);
  presets[pattern] = { ...fieldData, shape: pattern };
  delete presets[pattern].pattern_presets;
  fieldData.pattern_presets = presets;
  return fieldData;
}

const DEFAULT_AI_PATTERN_GATHER_SETTINGS = {
  start_location: "center",
  distance: 1,
  size: "m",
  width: 5,
  shift_lock: false,
  field_drift_compensation: true,
  invert_lr: false,
  invert_fb: false,
  turn: "none",
};

const DEFAULT_FUZZY_AI_GATHER_PATTERN_PRESET = {
  ...DEFAULT_AI_PATTERN_GATHER_SETTINGS,
  shape: "fuzzy_ai_gather",
};

const DEFAULT_BLOOMS_AI_PATTERN_PRESET = {
  ...DEFAULT_AI_PATTERN_GATHER_SETTINGS,
  shape: "blooms_ai",
};

const DEFAULT_AI_PATTERN_PRESETS = {
  fuzzy_ai_gather: DEFAULT_FUZZY_AI_GATHER_PATTERN_PRESET,
  blooms_ai: DEFAULT_BLOOMS_AI_PATTERN_PRESET,
};

function applyDefaultAIPatternPreset(fieldData, pattern) {
  const defaults = DEFAULT_AI_PATTERN_PRESETS[pattern];
  if (!defaults) return fieldData;
  return {
    ...fieldData,
    ...defaults,
    shape: pattern,
  };
}

function setActiveGatherFieldData(fieldData) {
  activeGatherFieldData = normalizeGatherFieldData(fieldData);
  activeGatherPattern = activeGatherFieldData.shape || "";
}
const fuzzyAITokenNames = [
  "Activated Target",
  "Baby Love",
  "Beamstorm",
  "Beesmas Cheer Token",
  "Black Bear Morph",
  "Bloom",
  "Blue Bomb Sync",
  "Blue Boost",
  "Blueberry",
  "Bomb",
  "Brown Bear Morph",
  "Coconut",
  "ComboCoconut",
  "Duped Baby Love",
  "Duped Beamstorm",
  "Duped Beesmas Cheer Token",
  "Duped Black Bear Morph",
  "Duped Blue Bomb Sync",
  "Duped Blue Boost",
  "Duped Blueberry",
  "Duped Bomb",
  "Duped Brown Bear Morph",
  "Duped Festive Blessing Token",
  "Duped Festive Gift Token",
  "Duped Festive Mark Token",
  "Duped Fetch",
  "Duped Flame Fuel",
  "Duped Focus",
  "Duped Fuzz Bombs Token",
  "Duped Glitch Token",
  "Duped Glob",
  "Duped Gumdrop Barrage",
  "Duped Haste",
  "Duped Honey Mark Token",
  "Duped Honey Token",
  "Duped Impale",
  "Duped Inferno Token",
  "Duped Inflate Balloons",
  "Duped Inspire Token",
  "Duped Jelly Bean",
  "Duped Map Corruption",
  "Duped Mark Surge Token",
  "Duped Melody",
  "Duped Mind Hack",
  "Duped Mother Bear Morph",
  "Duped Panda Bear Morph",
  "Duped Pineapple",
  "Duped Polar Bear Morph",
  "Duped Pollen Haze",
  "Duped Pollen Mark Token",
  "Duped Pulse",
  "Duped Puppy Love",
  "Duped Rage Token",
  "Duped Rain Cloud",
  "Duped Red Bomb Sync",
  "Duped Red Boost",
  "Duped Science Bear Morph",
  "Duped Scratch",
  "Duped Snowflake",
  "Duped Snowglobe Shake",
  "Duped Strawberry",
  "Duped Summon Frog Token",
  "Duped Sunflower Seed",
  "Duped Surprise Party",
  "Duped Tabby Love",
  "Duped Target Practice Token",
  "Duped Token Link",
  "Duped Tornado",
  "Duped Treat",
  "Duped Triangulate Token",
  "Duped White Boost",
  "Falling Star",
  "Festive Blessing Token",
  "Festive Gift Token",
  "Festive Mark Station",
  "Festive Mark Token",
  "Fetch",
  "Flame Fuel",
  "Focus",
  "Fully Collected Target",
  "Fuzz Bombs Token",
  "Glitch Token",
  "Glob",
  "Gumdrop Barrage",
  "Haste",
  "Honey Mark Station",
  "Honey Mark Token",
  "Honey Token",
  "Impale",
  "Inferno Token",
  "Inflate Balloons",
  "Inspire Token",
  "Jelly Bean",
  "Map Corruption",
  "Mark Surge Token",
  "Melody",
  "Mind Hack",
  "Mother Bear Morph",
  "Panda Bear Morph",
  "Pineapple",
  "Polar Bear Morph",
  "Pollen Haze",
  "Pollen Mark Station",
  "Pollen Mark Token",
  "Precise Mark Station",
  "Precise Mark Target",
  "Pulse",
  "Puppy Love",
  "Rage Token",
  "Rain Cloud",
  "Red Bomb Sync",
  "Red Boost",
  "Science Bear Morph",
  "Scratch",
  "Smiley",
  "Snowflake",
  "Snowglobe Shake",
  "Strawberry",
  "Summon Frog Token",
  "Sunflower Seed",
  "Surprise Party",
  "Tabby Love",
  "Target Practice Token",
  "TennisBall",
  "Token Link",
  "Tornado",
  "Treat",
  "Triangulate Token",
  "Unactivated Target",
  "White Boost",
];

const fuzzyAITokenNamesByModel = {
  Standard: fuzzyAITokenNames,
  Light: [
    "Baby Love", "Bear Morph", "Bomb", "Boost", "Festive Gift Token",
    "Focus", "Summon Frog Token", "Fuzz Bombs Token", "Haste", "Honey Token",
    "Inflate Balloons", "Inspire Token", "Loot", "Mark", "Melody",
    "Party Balloons", "Tabby Love", "Token Link",
  ],
  Mini: [
    "Balloon", "Bear Morph", "Bomb", "Boost", "Summon Frog Token", "Haste",
    "Inspire Token", "Long Buff", "Loot", "Mark", "Token Link",
  ],
};
let fuzzyAISelectedModel = "Standard";

function getFuzzyAITokenNames() {
  return fuzzyAITokenNamesByModel[fuzzyAISelectedModel] || fuzzyAITokenNamesByModel.Standard;
}

async function refreshFuzzyAISelectedModel() {
  try {
    const settings = await loadAllSettings();
    const configuredModel = String(settings.ai_gather_model || "Standard").trim().toLowerCase();
    fuzzyAISelectedModel = Object.keys(fuzzyAITokenNamesByModel).find(
      (model) => model.toLowerCase() === configuredModel
    ) || "Standard";
  } catch (_error) {
    fuzzyAISelectedModel = "Standard";
  }
  const note = document.getElementById("fuzzy-ai-token-model-note");
  if (note) {
    note.textContent = `Selected model: ${fuzzyAISelectedModel}. Only tokens detected by this model are shown.`;
  }
}

const fuzzyAICommonIgnoredTokens = fuzzyAITokenNames.filter((token) =>
  token.startsWith("Duped ")
).concat(["Bloom", "Honey Token", "Blueberry"]);

function parseFuzzyAITokenList(value) {
  if (!value) return [];
  return value
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean);
}

function getFuzzyAITokenState() {
  const preferred = parseFuzzyAITokenList(
    document.getElementById("fuzzy_ai_preferred_tokens")?.value || ""
  );
  const ignored = new Set(
    parseFuzzyAITokenList(document.getElementById("fuzzy_ai_ignored_tokens")?.value || "")
  );
  const tokenNames = getFuzzyAITokenNames();
  const ordered = [];
  preferred.forEach((token) => {
    if (tokenNames.includes(token) && !ordered.includes(token)) {
      ordered.push(token);
    }
  });
  tokenNames.forEach((token) => {
    if (!ordered.includes(token)) ordered.push(token);
  });
  return ordered.map((token) => ({
    name: token,
    enabled: !ignored.has(token),
  }));
}

function renderFuzzyAITokenList() {
  const container = document.getElementById("fuzzy-ai-token-list");
  if (!container) return;

  const tokenState = getFuzzyAITokenState();
  container.innerHTML = tokenState
    .map(
      (token, index) => `
        <div class="fuzzy-ai-token-row" data-token="${token.name}" draggable="true" style="display:flex; align-items:center; justify-content:space-between; gap:0.75rem; padding:0.45rem 0; border-bottom:1px solid rgba(255,255,255,0.08);">
          <label style="display:flex; align-items:center; gap:0.5rem; flex:1;">
            <span class="fuzzy-ai-token-drag-handle" title="Drag to reorder" style="cursor:grab; user-select:none; opacity:0.75;">::</span>
            <input type="checkbox" class="fuzzy-ai-token-enabled" ${token.enabled ? "checked" : ""}>
            <span>${index + 1}. ${token.name}</span>
          </label>
          <div style="display:flex; gap:0.35rem;">
            <button class="import-export-button fuzzy-ai-token-up" ${index === 0 ? "disabled" : ""}>Up</button>
            <button class="import-export-button fuzzy-ai-token-down" ${index === tokenState.length - 1 ? "disabled" : ""}>Down</button>
          </div>
        </div>
      `
    )
    .join("");
}

function getFuzzyAITokenDragAfterElement(container, y) {
  const rows = Array.from(
    container.querySelectorAll(".fuzzy-ai-token-row:not(.dragging)")
  );

  return rows.reduce(
    (closest, row) => {
      const box = row.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset, element: row };
      }
      return closest;
    },
    { offset: Number.NEGATIVE_INFINITY, element: null }
  ).element;
}

function renderFuzzyAITokenListFromRows() {
  const rows = Array.from(document.querySelectorAll(".fuzzy-ai-token-row"));
  rows.forEach((row, index) => {
    const tokenLabel = row.querySelector("label span:last-child");
    if (tokenLabel) tokenLabel.textContent = `${index + 1}. ${row.dataset.token}`;
    const upButton = row.querySelector(".fuzzy-ai-token-up");
    const downButton = row.querySelector(".fuzzy-ai-token-down");
    if (upButton) upButton.disabled = index === 0;
    if (downButton) downButton.disabled = index === rows.length - 1;
  });
}

async function saveFuzzyAITokenPopup() {
  const rows = Array.from(document.querySelectorAll(".fuzzy-ai-token-row"));
  const preferred = [];
  const ignored = [];

  rows.forEach((row) => {
    const token = row.dataset.token;
    const enabled = row.querySelector(".fuzzy-ai-token-enabled")?.checked;
    if (enabled) preferred.push(token);
    else ignored.push(token);
  });

  const fieldDropdown = document.getElementById("field");
  const fieldName = fieldDropdown ? getDropdownValue(fieldDropdown) : "";
  if (!fieldName) return;

  await eel.saveFuzzyAITokenRanking(fieldName, {
    preferred_tokens: preferred.join(","),
    ignored_tokens: ignored.join(","),
  }, fuzzyAISelectedModel)();
}

async function openFuzzyAITokenPopup() {
  await refreshFuzzyAISelectedModel();
  const fieldDropdown = document.getElementById("field");
  const fieldName = fieldDropdown ? getDropdownValue(fieldDropdown) : "";
  if (fieldName) {
    const ranking = await eel.loadFuzzyAITokenRanking(fieldName, fuzzyAISelectedModel)();
    const preferredInput = document.getElementById("fuzzy_ai_preferred_tokens");
    const ignoredInput = document.getElementById("fuzzy_ai_ignored_tokens");
    if (preferredInput) preferredInput.value = ranking.preferred_tokens || "";
    if (ignoredInput) ignoredInput.value = ranking.ignored_tokens || "";
  }
  renderFuzzyAITokenList();
  const modal = document.getElementById("fuzzy-ai-token-modal");
  if (modal) modal.style.display = "flex";
}

function closeFuzzyAITokenPopup() {
  const modal = document.getElementById("fuzzy-ai-token-modal");
  if (modal) modal.style.display = "none";
}

function getSelectedGatherPattern() {
  const shapeDropdown = document.getElementById("shape");
  if (!shapeDropdown) return "";
  return getDropdownValue(shapeDropdown);
}

let gatherPatterns = [];
let hiddenGatherPatterns = [];

async function loadGatherPatterns() {
  gatherPatterns = await eel.getPatterns()();
  hiddenGatherPatterns = (await loadAllSettings()).hidden_patterns || [];
  gatherPatternMetadata = {};
  gatherPatterns.forEach((pattern) => {
    gatherPatternMetadata[pattern.value || pattern.name || pattern] = pattern;
  });
}

// Hidden patterns (Config > Other Settings) are left out, except the one the field already uses.
function showGatherPatternOptions(currentShape) {
  const current = String(currentShape || "").toLowerCase();
  const isHidden = (pattern) =>
    hiddenGatherPatterns.includes(pattern.value.toLowerCase()) && pattern.value.toLowerCase() !== current;
  const field = String(getSelectedGatherField()).toLowerCase().replaceAll("_", " ");
  const supportsField = (pattern) =>
    pattern.supported_fields == null || pattern.supported_fields.includes(field);
  setDropdownData("shape", gatherPatterns
    .filter((pattern) => !isHidden(pattern) &&
      (supportsField(pattern) || pattern.value.toLowerCase() === current))
    .map((pattern) => supportsField(pattern) ? pattern : {
      ...pattern,
      label: `${pattern.label || pattern.name} (unavailable here; uses e_lol)`,
    }));
}

function getSelectedGatherField() {
  const fieldDropdown = document.getElementById("field");
  if (!fieldDropdown) return "";
  return getDropdownValue(fieldDropdown);
}

function updateInfiniteGatherUI() {
  const infiniteGather = document.getElementById("infinite_gather")?.checked || false;
  ["mins", "backpack"].forEach((id) => {
    const input = document.getElementById(id);
    if (!input) return;
    input.disabled = infiniteGather;
    input.style.opacity = infiniteGather ? "0.45" : "";
    input.style.cursor = infiniteGather ? "not-allowed" : "";
  });
}

function updateGatherPatternUI() {
  const pattern = getSelectedGatherPattern();
  const field = getSelectedGatherField();
  const fuzzySection = document.getElementById("fuzzy-ai-gather-section");
  const description = document.getElementById("gather-pattern-metadata");
  const isFuzzyAI = pattern === "fuzzy_ai_gather";
  const isHiveHubGather = pattern === "hive_hub" || field === "hive hub";

  if (fuzzySection) {
    fuzzySection.style.display = isFuzzyAI ? "block" : "none";
  }
  const pineDupeSection = document.getElementById("pine-dupe-section");
  if (pineDupeSection) {
    pineDupeSection.style.display = pattern === "pine_dupe" ? "block" : "none";
  }
  if (description) {
    description.innerText = isHiveHubGather
      ? "Notice: Do NOT start the macro in Hive Hub, it will travel there automatically."
      : "";
    description.style.display = isHiveHubGather ? "block" : "none";
  }
  updateInfiniteGatherUI();
}

//save the selected field's settings; if that fails, tell the user and show the saved ones again
async function persistGatherField(fieldData) {
  const field = getInputValue("field");
  try {
    await eel.saveField(field, fieldData)();
  } catch (error) {
    alert(`${field} settings were not saved: ${error?.errorText || error}`);
    const saved = normalizeGatherFieldData((await eel.loadFields()())[field]);
    setActiveGatherFieldData(saved);
    loadInputs(saved);
    updateGatherPatternUI();
  }
}

function saveField() {
  // Validate goo_interval minimum value
  const gooIntervalElement = document.getElementById("goo_interval");
  if (gooIntervalElement && gooIntervalElement.value) {
    const value = parseInt(gooIntervalElement.value);
    if (value < 3) {
      gooIntervalElement.value = 3;
    }
  }

  let fieldData = getGatherFieldDataFromInputs();
  fieldData = rememberGatherPatternPreset(fieldData, fieldData.shape);
  setActiveGatherFieldData(fieldData);
  updateGatherPatternUI();
  persistGatherField(fieldData);
}

function saveFieldPatternChange() {
  let fieldData = getGatherFieldDataFromInputs();
  const previousPattern =
    activeGatherPattern || activeGatherFieldData.shape || fieldData.shape;
  const selectedPattern = fieldData.shape;

  fieldData = rememberGatherPatternPreset(fieldData, previousPattern);

  const presets = getGatherPatternPresets(fieldData);
  const selectedPreset = presets[selectedPattern];
  if (selectedPreset && typeof selectedPreset === "object") {
    fieldData = {
      ...fieldData,
      ...selectedPreset,
      shape: selectedPattern,
      pattern_presets: presets,
    };
  } else if (DEFAULT_AI_PATTERN_PRESETS[selectedPattern]) {
    fieldData = applyDefaultAIPatternPreset(fieldData, selectedPattern);
    fieldData.pattern_presets = presets;
  } else {
    fieldData.shape = selectedPattern;
  }

  fieldData = rememberGatherPatternPreset(fieldData, selectedPattern);
  setActiveGatherFieldData(fieldData);
  showGatherPatternOptions(selectedPattern);
  loadInputs(fieldData);
  updateGatherPatternUI();
  persistGatherField(fieldData);
}
//save the fields_enabled
async function updateFieldEnable(ele) {
  //save
  const fields_enabled = (await loadSettings()).fields_enabled;
  fields_enabled[fieldNo - 1] = ele.checked;
  await saveSettingValue("profile", "fields_enabled", fields_enabled);
}

//load the field selected in the dropdown
async function loadAndSaveField(ele) {
  const data = normalizeGatherFieldData((await eel.loadFields()())[getDropdownValue(ele)]);
  setActiveGatherFieldData(data);
  showGatherPatternOptions(data.shape);
  loadInputs(data);
  updateGatherPatternUI();
  //save
  const fields = (await loadSettings()).fields;
  fields[fieldNo - 1] = getDropdownValue(ele);
  await saveSettingValue("profile", "fields", fields);
}

const MIN_GATHER_FIELD_COUNT = 3;

//one tab per configured field, kept in front of the + button; the x shows once there are more than the minimum
function renderGatherTabs(count) {
  const tabs = document.getElementsByClassName("gather-tab-item");
  while (tabs.length > count) tabs[tabs.length - 1].remove();
  const addButton = document.getElementById("add-field-button");
  for (let i = tabs.length + 1; i <= count; i++) {
    const tab = document.createElement("div");
    tab.id = `field-${i}`;
    tab.className = "gather-tab-item";
    tab.innerHTML = `Field ${i}<span class="gather-remove-field" title="Remove this field" aria-label="Remove field ${i}">&times;</span>`;
    addButton.before(tab);
  }
  addButton.parentElement.classList.toggle("can-remove-field", count > MIN_GATHER_FIELD_COUNT);
}

//both lists are saved in one write so a running macro never reads them with different lengths
async function saveGatherFields(fields, fields_enabled) {
  try {
    await eel.saveDictProfileSettings({ fields, fields_enabled })();
    return true;
  } catch (error) {
    await rejectSettingChange("fields", String(error?.errorText || error));
    return false;
  }
}

async function removeGatherField(number) {
  const settings = await loadSettings();
  const fields = settings.fields.filter((_, i) => i !== number - 1);
  const fields_enabled = settings.fields_enabled.filter((_, i) => i !== number - 1);
  if (fields.length < MIN_GATHER_FIELD_COUNT) return;
  if (!(await saveGatherFields(fields, fields_enabled))) return;
  const current = Number(fieldNo);
  const next = number < current ? current - 1 : Math.min(current, fields.length);
  await switchGatherTab(document.getElementById(`field-${next}`));
}

async function addGatherField() {
  const settings = await loadSettings();
  const fields = [...settings.fields, "pine tree"];
  const fields_enabled = [...settings.fields_enabled, false];
  if (!(await saveGatherFields(fields, fields_enabled))) return;
  renderGatherTabs(fields.length);
  await switchGatherTab(document.getElementById(`field-${fields.length}`));
}

async function switchGatherTab(target) {
  const settings = await loadSettings();
  renderGatherTabs(Math.max(settings.fields.length, MIN_GATHER_FIELD_COUNT));
  if (!target.isConnected) target = document.getElementById("field-1");
  setActiveSubtab("activeGatherSubtab", target.id);
  fieldNo = target.id.split("-")[1];
  Array.from(document.getElementsByClassName("gather-tab-item")).forEach((x) =>
    x.classList.remove("active")
  );
  target.classList.add("active");
  document.getElementById("gather-field").innerText = `Gather Field ${fieldNo}`;
  //scroll back to top
  document.getElementById("gather").scrollTo(0, 0);
  //load the fields
  const fieldDropdown = document.getElementById("field");
  setDropdownValue(fieldDropdown, settings.fields[fieldNo - 1]);
  document.getElementById("field_enable").checked =
    settings.fields_enabled[fieldNo - 1];
  await loadGatherPatterns();
  //load the inputs
  loadAndSaveField(fieldDropdown);
}

//add and remove run one at a time, so a quick second click never works from a stale list
let fieldOperationQueue = Promise.resolve();
function queueFieldOperation(operation) {
  const run = fieldOperationQueue.then(operation);
  fieldOperationQueue = run.catch(() => {});
  return run;
}

$("#gather-placeholder")
  .load("../htmlImports/tabs/gather.html", async () => {
    renderGatherTabs(Math.max((await loadSettings()).fields.length, MIN_GATHER_FIELD_COUNT));
    await switchGatherTab(
      document.getElementById(getActiveSubtab("activeGatherSubtab", "field-1"))
    );
  }) //load gather tab, restore active field once its done loading
  .on("click", "#add-field-button", () => queueFieldOperation(addGatherField))
  .on("click", ".gather-remove-field", (event) => {
    event.stopPropagation();
    const number = Number(event.currentTarget.parentElement.id.split("-")[1]);
    queueFieldOperation(() => removeGatherField(number));
  })
  .on("click", ".gather-tab-item", (event) =>
    switchGatherTab(event.currentTarget)
  ) //navigate between fields
  .on("click", "#import-patterns-button", async (event) => {
    event.preventDefault();

    // Create a file input to select pattern .py files
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.py,.ahk';
    input.multiple = true;
    input.onchange = async (e) => {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;
      const patterns = [];
      for (const file of files) {
        try {
          const text = await file.text();
          patterns.push({ name: file.name, content: text });
        } catch (err) {
          console.error('Failed to read file', file.name, err);
        }
      }

      try {
        const result = await eel.importPatterns(patterns)();
        let msg = '';
        if (result.saved && result.saved.length) msg += `Saved: ${result.saved.join(', ')}\n`;
        if (result.errors && result.errors.length) msg += `Errors: ${result.errors.join(', ')}`;
        if (!msg) msg = 'No files were processed.';
        alert(msg);
        // refresh pattern dropdown
        await loadGatherPatterns();
        showGatherPatternOptions(getSelectedGatherPattern());
        const hiddenDropdown = document.getElementById("hidden_patterns");
        if (hiddenDropdown) {
          const hidden = getDropdownValue(hiddenDropdown);
          setDropdownData("hidden_patterns", gatherPatterns);
          setDropdownValue(hiddenDropdown, hidden);
        }
        updateGatherPatternUI();
      } catch (err) {
        console.error(err);
        alert('Failed to import patterns.');
      }
    };
    input.click();
  })
  .on("click", "#reset-field-button", async (event) => {
    event.preventDefault();

    // Get the currently selected field name
    const fieldDropdown = document.getElementById("field");
    const currentFieldName = getDropdownValue(fieldDropdown);

    if (!currentFieldName) {
      alert("Please select a field first.");
      return;
    }

    // Show confirmation dialog
    const confirmReset = confirm(
      `Are you sure you want to reset "${currentFieldName}" field settings to default values? This action cannot be undone.`
    );

    if (!confirmReset) {
      return;
    }

    try {
      // Call the reset function
      const success = await eel.resetFieldToDefault(currentFieldName)();

      if (success) {
        // Reload the field data and update the UI
        const data = normalizeGatherFieldData((await eel.loadFields()())[currentFieldName]);
        setActiveGatherFieldData(data);
        loadInputs(data);
        updateGatherPatternUI();
        alert(
          `Successfully reset "${currentFieldName}" field settings to defaults.`
        );
      } else {
        alert(
          `Failed to reset "${currentFieldName}" field settings. Field may not exist in default settings.`
        );
      }
    } catch (error) {
      console.error("Error resetting field:", error);
      alert("An error occurred while resetting field settings.");
    }
  })
  .on("click", "#export-field-button", async (event) => {
    event.preventDefault();

    // Get the currently selected field name
    const fieldDropdown = document.getElementById("field");
    const currentFieldName = getDropdownValue(fieldDropdown);

    if (!currentFieldName) {
      alert("Please select a field first.");
      return;
    }

    try {
      // Call the export function
      const jsonSettings = await eel.exportFieldSettings(currentFieldName)();

      if (jsonSettings) {
        // Parse JSON to extract metadata
        let metadata = {};
        try {
          const parsedData = JSON.parse(jsonSettings);
          metadata = parsedData.metadata || {};
        } catch (e) {
          // If parsing fails, that's okay - just use empty metadata
        }

        // Copy to clipboard
        await navigator.clipboard.writeText(jsonSettings);
        
        // Build success message with metadata
        let successMsg = `Settings for "${currentFieldName}" exported and copied to clipboard!`;
        if (metadata.macro_version) {
          successMsg += `\n\nExport details:\nMacro version: ${metadata.macro_version}`;
        }
        if (metadata.export_date) {
          successMsg += `\nExported: ${new Date(metadata.export_date).toLocaleString()}`;
        }
        
        alert(successMsg);
      } else {
        alert("Failed to export field settings. Field may not exist.");
      }
    } catch (error) {
      console.error("Error exporting field settings:", error);
      alert("An error occurred while exporting field settings.");
    }
  })
  .on("click", "#import-field-button", async (event) => {
    event.preventDefault();

    // Get the currently selected field name
    const fieldDropdown = document.getElementById("field");
    const currentFieldName = getDropdownValue(fieldDropdown);

    if (!currentFieldName) {
      alert("Please select a field first.");
      return;
    }

    // Show the import modal
    const modal = document.getElementById("import-modal");
    const textarea = document.getElementById("import-json-textarea");
    textarea.value = "";
    modal.style.display = "flex";
  })
  .on("click", "#cancel-import-button", (event) => {
    event.preventDefault();
    // Hide the import modal
    document.getElementById("import-modal").style.display = "none";
  })
  .on("click", "#confirm-import-button", async (event) => {
    event.preventDefault();

    const fieldDropdown = document.getElementById("field");
    const currentFieldName = getDropdownValue(fieldDropdown);
    const textarea = document.getElementById("import-json-textarea");
    const jsonSettings = textarea.value.trim();

    if (!jsonSettings) {
      alert("Please paste JSON settings to import.");
      return;
    }

    try {
      // Call the import function
      const result = await eel.importFieldSettings(currentFieldName, jsonSettings)();

      if (result && result.success) {
        // Reload the field data and update the UI
        const data = (await eel.loadFields()())[currentFieldName];
        setActiveGatherFieldData(data);
        loadInputs(data);
        updateGatherPatternUI();
        // Hide the modal
        document.getElementById("import-modal").style.display = "none";

        // Build success message with metadata
        let successMsg = `Successfully imported settings for "${currentFieldName}"!`;
        
        // Add metadata information if available
        if (result.imported_from_field && result.imported_from_field !== "unknown") {
          successMsg += `\n\nImported from field: ${result.imported_from_field}`;
        }
        if (result.macro_version && result.macro_version !== "unknown") {
          successMsg += `\nMacro version: ${result.macro_version}`;
        }
        
        // Add pattern replacement information
        if (result.missing_patterns && result.missing_patterns.length > 0) {
          const patternMsg = result.missing_patterns.join(", ");
          successMsg += `\n\nNote: Some patterns were not found and were replaced:\n${patternMsg}`;
        }
        if (result.warnings && result.warnings.length > 0) {
          successMsg += `\n\nWarnings:\n${result.warnings.join("\n")}`;
        }
        
        alert(successMsg);
      } else {
        alert("Failed to import field settings. Please check your JSON format.");
      }
    } catch (error) {
      console.error("Error importing field settings:", error);
      alert("An error occurred while importing field settings. Please check your JSON format.");
    }
  })
  .on("click", "#configure-fuzzy-ai-tokens-button", (event) => {
    event.preventDefault();
    openFuzzyAITokenPopup();
  })
  .on("click", "#cancel-fuzzy-ai-tokens-button", (event) => {
    event.preventDefault();
    closeFuzzyAITokenPopup();
  })
  .on("click", "#save-fuzzy-ai-tokens-button", async (event) => {
    event.preventDefault();
    await saveFuzzyAITokenPopup();
    closeFuzzyAITokenPopup();
  })
  .on("click", "#select-all-fuzzy-ai-tokens-button, #select-none-fuzzy-ai-tokens-button", function(event) {
    event.preventDefault();
    const checked = event.currentTarget.id === "select-all-fuzzy-ai-tokens-button";
    document.querySelectorAll(".fuzzy-ai-token-enabled").forEach((box) => {
      box.checked = checked;
    });
  })
  .on("click", "#fuzzy-ai-token-modal", function(event) {
    if (event.target === this) {
      closeFuzzyAITokenPopup();
    }
  })
  .on("dragstart", ".fuzzy-ai-token-row", function(event) {
    event.currentTarget.classList.add("dragging");
    event.currentTarget.style.opacity = "0.45";
    if (event.originalEvent?.dataTransfer) {
      event.originalEvent.dataTransfer.effectAllowed = "move";
      event.originalEvent.dataTransfer.setData("text/plain", event.currentTarget.dataset.token || "");
    }
  })
  .on("dragend", ".fuzzy-ai-token-row", function(event) {
    event.currentTarget.classList.remove("dragging");
    event.currentTarget.style.opacity = "";
    renderFuzzyAITokenListFromRows();
  })
  .on("dragover", "#fuzzy-ai-token-list", function(event) {
    event.preventDefault();
    const draggingRow = document.querySelector(".fuzzy-ai-token-row.dragging");
    if (!draggingRow) return;

    const afterElement = getFuzzyAITokenDragAfterElement(
      event.currentTarget,
      event.originalEvent.clientY
    );
    if (afterElement == null) {
      event.currentTarget.appendChild(draggingRow);
    } else {
      event.currentTarget.insertBefore(draggingRow, afterElement);
    }
  })
  .on("drop", "#fuzzy-ai-token-list", function(event) {
    event.preventDefault();
    renderFuzzyAITokenListFromRows();
  })
  .on("click", ".fuzzy-ai-token-up", function(event) {
    event.preventDefault();
    const row = event.currentTarget.closest(".fuzzy-ai-token-row");
    const previous = row?.previousElementSibling;
    if (row && previous) {
      row.parentElement.insertBefore(row, previous);
      renderFuzzyAITokenListFromRows();
    }
  })
  .on("click", ".fuzzy-ai-token-down", function(event) {
    event.preventDefault();
    const row = event.currentTarget.closest(".fuzzy-ai-token-row");
    const next = row?.nextElementSibling;
    if (row && next) {
      row.parentElement.insertBefore(next, row);
      renderFuzzyAITokenListFromRows();
    }
  })
  .on("click", "#import-modal", function(event) {
    // Close modal when clicking outside the modal content
    if (event.target === this) {
      $(this).hide();
    }
  });
