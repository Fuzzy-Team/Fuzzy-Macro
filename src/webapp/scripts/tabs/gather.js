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
  "return",
  "use_whirlwig_fallback",
  "start_location",
  "distance",
  "goo",
  "goo_interval",
];
let gatherPatternMetadata = {};
let activeGatherFieldData = {};
let activeGatherPattern = "";

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

function setActiveGatherFieldData(fieldData) {
  activeGatherFieldData =
    fieldData && typeof fieldData === "object" ? fieldData : {};
  activeGatherPattern = activeGatherFieldData.shape || "";
}
const fuzzyAITokenNames = [
  "Baby Love",
  "Beamstorm",
  "Beesmas Cheer",
  "Black Bear Morph",
  "Blue Bomb",
  "Blue Bomb Sync",
  "Blue Boost",
  "Blue Pulse",
  "Blueberry",
  "Brown Bear Morph",
  "Buzz Bomb",
  "Festive Blessing",
  "Festive Gift",
  "Festive Mark",
  "Festive Mark Token",
  "Fetch",
  "Focus",
  "Fuzz Bomb Field",
  "Fuzz Bombs Token",
  "Glitch Token",
  "Glob",
  "Gumdrop Barrage",
  "Haste",
  "Honey",
  "Honey Mark",
  "Honey Mark Token",
  "Impale",
  "Inflate Balloons",
  "Inspire",
  "Map Corruption",
  "Melody",
  "Mind Hack",
  "Mother Bear Morph",
  "Panda Bear Morph",
  "Pineapple",
  "Polar Bear Morph",
  "Pollen Haze",
  "Pollen Mark",
  "Pollen Mark Token",
  "Puppy Ball",
  "Puppy Love",
  "Rain Cloud",
  "Red Bomb",
  "Red Boost",
  "Science Bear Morph",
  "Scratch",
  "Snowflake",
  "Snowglobe Shake",
  "Strawberry",
  "Summon Frog",
  "Sunflower Seed",
  "Surprise Party",
  "Tabby Love",
  "Token Link",
  "Tornado",
  "White Boost",
];

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
  const ordered = [];
  preferred.forEach((token) => {
    if (fuzzyAITokenNames.includes(token) && !ordered.includes(token)) {
      ordered.push(token);
    }
  });
  fuzzyAITokenNames.forEach((token) => {
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
  })();
}

async function openFuzzyAITokenPopup() {
  const fieldDropdown = document.getElementById("field");
  const fieldName = fieldDropdown ? getDropdownValue(fieldDropdown) : "";
  if (fieldName) {
    const ranking = await eel.loadFuzzyAITokenRanking(fieldName)();
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

function updateGatherPatternUI() {
  const pattern = getSelectedGatherPattern();
  const fuzzySection = document.getElementById("fuzzy-ai-gather-section");
  const description = document.getElementById("gather-pattern-metadata");
  const isFuzzyAI = pattern === "fuzzy_ai_gather";

  if (fuzzySection) {
    fuzzySection.style.display = isFuzzyAI ? "block" : "none";
  }
  if (description) {
    description.innerText = "";
    description.style.display = "none";
  }
}
//save the enabled status for the fields
async function saveEnabled() {
  const fields = (await loadSettings()).fields;
  fields[fieldNo - 1] = ele.value;
  eel.saveProfileSetting("fields", fields);
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
  eel.saveField(getInputValue("field"), fieldData);
  updateGatherPatternUI();
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
  } else {
    fieldData.shape = selectedPattern;
  }

  fieldData = rememberGatherPatternPreset(fieldData, selectedPattern);
  setActiveGatherFieldData(fieldData);
  loadInputs(fieldData);
  eel.saveField(getInputValue("field"), fieldData);
  updateGatherPatternUI();
}
//save the fields_enabled
async function updateFieldEnable(ele) {
  //save
  const fields_enabled = (await loadSettings()).fields_enabled;
  fields_enabled[fieldNo - 1] = ele.checked;
  eel.saveProfileSetting("fields_enabled", fields_enabled);
}

//load the field selected in the dropdown
async function loadAndSaveField(ele) {
  const data = (await eel.loadFields()())[getDropdownValue(ele)];
  setActiveGatherFieldData(data);
  loadInputs(data);
  updateGatherPatternUI();
  //save
  const fields = (await loadSettings()).fields;
  fields[fieldNo - 1] = getDropdownValue(ele);
  eel.saveProfileSetting("fields", fields);
}

async function switchGatherTab(target) {
  setActiveSubtab("activeGatherSubtab", target.id);
  fieldNo = target.id.split("-")[1];
  //remove the arrow indicator
  const selector = document.getElementById("gather-select");
  if (selector) selector.remove();
  Array.from(document.getElementsByClassName("gather-tab-item")).forEach((x) =>
    x.classList.remove("active")
  ); //remove the active class
  //add indicator + active class
  target.classList.add("active");
  target.innerHTML =
    `<div class = "select-indicator" id = "gather-select"></div>` +
    target.innerHTML;
  document.getElementById("gather-field").innerText = `Gather Field ${fieldNo}`;
  //scroll back to top
  document.getElementById("gather").scrollTo(0, 0);
  //load the fields
  const settings = await loadSettings();
  const fieldDropdown = document.getElementById("field");
  setDropdownValue(fieldDropdown, settings.fields[fieldNo - 1]);
  document.getElementById("field_enable").checked =
    settings.fields_enabled[fieldNo - 1];
  //get the pattern list
  const patterns = await eel.getPatterns()();
  gatherPatternMetadata = {};
  patterns.forEach((pattern) => {
    gatherPatternMetadata[pattern.value || pattern.name || pattern] = pattern;
  });
  setDropdownData("shape", patterns);
  //load the inputs
  loadAndSaveField(fieldDropdown);
}

$("#gather-placeholder")
  .load("../htmlImports/tabs/gather.html", () =>
    switchGatherTab(
      document.getElementById(getActiveSubtab("activeGatherSubtab", "field-1"))
    )
  ) //load home tab, restore active field once its done loading
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
        const patternsList = await eel.getPatterns()();
        gatherPatternMetadata = {};
        patternsList.forEach((pattern) => {
          gatherPatternMetadata[pattern.value || pattern.name || pattern] = pattern;
        });
        setDropdownData('shape', patternsList);
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
        const data = (await eel.loadFields()())[currentFieldName];
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
