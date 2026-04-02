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
  "fuzzy_ai_calibration_path",
  "fuzzy_ai_capture_backend",
  "fuzzy_ai_confidence_threshold",
  "fuzzy_ai_sprinkler_confidence_threshold",
  "fuzzy_ai_min_token_distance",
  "fuzzy_ai_idle_return_interval",
  "fuzzy_ai_no_token_recalibration_timeout",
  "fuzzy_ai_movements_before_recalibration",
  "fuzzy_ai_sprinkler_arrival_threshold",
  "fuzzy_ai_max_sprinkler_distance",
  "fuzzy_ai_sprinkler_rescan_attempts",
  "fuzzy_ai_sprinkler_rescan_delay",
  "fuzzy_ai_target_sprinkler_label",
  "fuzzy_ai_preferred_tokens",
  "fuzzy_ai_ignored_tokens",
];
let gatherPatternMetadata = {};

function getSelectedGatherPattern() {
  const shapeDropdown = document.getElementById("shape");
  if (!shapeDropdown) return "";
  return getDropdownValue(shapeDropdown);
}

function renderFuzzyAIValidationResult(result) {
  const container = document.getElementById("fuzzy-ai-validation-results");
  if (!container) return;

  if (!result) {
    container.innerHTML = "";
    return;
  }

  const errors = Array.isArray(result.errors) ? result.errors : [];
  const warnings = Array.isArray(result.warnings) ? result.warnings : [];
  const details = result.details || {};
  const statusColor = result.ok ? "#8ad48a" : "#ff8b8b";
  const sections = [
    `<div style="font-weight:600; color:${statusColor};">${result.ok ? "Environment ready" : "Environment issues found"}</div>`,
  ];

  if (errors.length > 0) {
    sections.push(`<div><strong>Errors:</strong><br>${errors.join("<br>")}</div>`);
  }
  if (warnings.length > 0) {
    sections.push(`<div><strong>Warnings:</strong><br>${warnings.join("<br>")}</div>`);
  }

  const detailLines = [];
  if (details.resolved_capture_backend) {
    detailLines.push(`Capture backend: ${details.resolved_capture_backend}`);
  }
  if (details.blue_model) {
    detailLines.push(`Blue model: ${details.blue_model}`);
  }
  if (details.sprinkler_model) {
    detailLines.push(`Sprinkler model: ${details.sprinkler_model}`);
  }
  if (details.calibration_path) {
    detailLines.push(`Calibration: ${details.calibration_path}`);
  }
  if (detailLines.length > 0) {
    sections.push(`<div><strong>Details:</strong><br>${detailLines.join("<br>")}</div>`);
  }

  container.innerHTML = sections.join("<div style=\"margin-top:0.5rem;\"></div>");
}

function updateGatherPatternUI() {
  const pattern = getSelectedGatherPattern();
  const fuzzySection = document.getElementById("fuzzy-ai-gather-section");
  const validateButton = document.getElementById("validate-fuzzy-ai-button");
  const description = document.getElementById("gather-pattern-metadata");
  const metadata = gatherPatternMetadata[pattern] || {};
  const isFuzzyAI = pattern === "fuzzy_ai_gather";

  if (fuzzySection) {
    fuzzySection.style.display = isFuzzyAI ? "block" : "none";
  }
  if (validateButton) {
    validateButton.style.display = isFuzzyAI ? "inline-flex" : "none";
  }
  if (description) {
    description.innerText = metadata.description || "";
    description.style.display = metadata.description ? "block" : "none";
  }
  if (!isFuzzyAI) {
    renderFuzzyAIValidationResult(null);
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

  const fieldData = generateSettingObject(gatherFieldProperties);
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
  loadInputs(data);
  updateGatherPatternUI();
  //save
  const fields = (await loadSettings()).fields;
  fields[fieldNo - 1] = getDropdownValue(ele);
  eel.saveProfileSetting("fields", fields);
}

async function switchGatherTab(target) {
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
    switchGatherTab(document.getElementById("field-1"))
  ) //load home tab, switch to field 1 once its done loading
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
  .on("click", "#validate-fuzzy-ai-button", async (event) => {
    event.preventDefault();
    const result = await eel.validateGatherPatternEnvironment(
      generateSettingObject(gatherFieldProperties)
    )();
    renderFuzzyAIValidationResult(result);
  })
  .on("click", "#import-modal", function(event) {
    // Close modal when clicking outside the modal content
    if (event.target === this) {
      $(this).hide();
    }
  });
