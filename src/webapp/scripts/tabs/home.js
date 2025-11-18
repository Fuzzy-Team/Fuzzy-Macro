/*
=============================================
Home Tab
=============================================
*/

//use a python function to open the link in the user's actual browser
function ahref(link) {
  eel.openLink(link);
}

//update the start button text with current keybinds
async function updateStartButtonText() {
  const settings = await loadAllSettings();
  const startKey = settings.start_keybind || "F1";
  const stopKey = settings.stop_keybind || "F3";

  // Check if macro is currently running
  try {
    const runState = await eel.getRunState()();
    const isRunning = runState === 2; // 2 means running
    const isPaused = runState === 5; // 5 means paused

    const button = document.getElementById("start-btn");
    if (button) {
      if (isPaused) {
        button.classList.add("paused");
        button.classList.remove("active");
        button.disabled = true;
        button.textContent = `⏸️ Paused`;
      } else if (isRunning) {
        button.classList.add("active");
        button.classList.remove("paused");
        button.disabled = false;
        button.textContent = `Stop [${stopKey}]`;
      } else {
        button.classList.remove("active");
        button.classList.remove("paused");
        button.disabled = false;
        button.textContent = `Start [${startKey}]`;
      }
    }
  } catch (error) {
    // Fallback to just setting start text
    const button = document.getElementById("start-btn");
    if (button) {
      button.disabled = false;
      button.textContent = `Start [${startKey}]`;
    }
  }
}

//toggle the start/stop button visuals
eel.expose(toggleStartStop);
async function toggleStartStop() {
  const settings = await loadAllSettings();
  const startKey = settings.start_keybind || "F1";
  const stopKey = settings.stop_keybind || "F3";

  // Check if macro is currently running by checking the run state
  try {
    const runState = await eel.getRunState()();
    const isRunning = runState === 2; // 2 means running
    const isPaused = runState === 5; // 5 means paused

    const button = document.getElementById("start-btn");
    if (button) {
      if (isPaused) {
        // Macro is paused, show paused indicator
        button.classList.add("paused");
        button.classList.remove("active");
        button.disabled = true;
        button.textContent = `⏸️ Paused`;
      } else if (isRunning) {
        // Macro is running, show stop button
        button.classList.add("active");
        button.classList.remove("paused");
        button.disabled = false;
        button.textContent = `Stop [${stopKey}]`;
      } else {
        // Macro is not running, show start button
        button.classList.remove("active");
        button.classList.remove("paused");
        button.disabled = false;
        button.textContent = `Start [${startKey}]`;
      }
    }

    return true; // Success
  } catch (error) {
    return false;
  }
}

eel.expose(log);
function log(time = "", msg = "", color = "") {
  document.getElementById("log");
  let timeText = "";
  if (time) timeText = `[${time}]`;
  const html = `
    <div class = "log-msg"><span style="background-color: #${color}; align-self: start"></span>${timeText} ${msg}</div>
    `;
  const logs = document.getElementById("logs");
  logs.innerHTML += html;
  logs.scrollTop = logs.scrollHeight;
}

//returns a html string for the task
function taskHTML(title, desc = "") {
  const html = `
    <div style="margin-top: 1rem;">
        <div style="font-size: 1.1rem;">${title}</div>
        <div style="font-size: 0.9rem; color: #ADB5BD; display:flex; align-items:center;">${
          desc.includes("<img") ? desc : toTitleCase(desc)
        }</div>
        <div style="background-color: #949393; height: 1px; width: 95%; margin-top: 0.4rem;"></div>
    </div>
    `;
  return html;
}

function secondsToMinsAndHours(time) {
  if (time < 0) return "Ready!";
  const hours = Math.floor(time / 3600);
  const minutes = Math.floor((time - hours * 3600) / 60);
  return `${hours}h ${minutes}m`;
}

//load the tasks
//also set max-height for logs
eel.expose(loadTasks);
eel.expose(updateFieldOnlyMode);
async function updateFieldOnlyMode() {
  // Update field-only mode dropdown to match current settings
  const settings = await loadAllSettings();
  const fieldOnlyDropdown = document.getElementById("field_only_mode");
  if (fieldOnlyDropdown) {
    const currentValue = settings.field_only_mode ? "true" : "false";
    if (fieldOnlyDropdown.value !== currentValue) {
      fieldOnlyDropdown.value = currentValue;
    }
  }
}

async function loadTasks() {
  const setdat = await loadAllSettings();
  let out = "";

  // Update field-only mode dropdown to match current settings
  const fieldOnlyDropdown = document.getElementById("field_only_mode");
  if (fieldOnlyDropdown) {
    const currentValue = setdat.field_only_mode ? "true" : "false";
    if (fieldOnlyDropdown.value !== currentValue) {
      fieldOnlyDropdown.value = currentValue;
    }
  }

  // Check if field-only mode is enabled
  if (setdat.field_only_mode) {
    out += taskHTML("Field Only Mode", "🌾 Gathering in fields only");

    // Still show the fields to be gathered in field-only mode
    for (let i = 0; i <= setdat.fields_enabled.length; i++) {
      if (!setdat.fields_enabled[i]) continue;
      const field = setdat.fields[i];
      out += taskHTML(
        `Gather ${i + 1}`,
        `${fieldEmojis[field.replaceAll(" ", "_")]} ${field}`
      );
    }

    // Display the tasks
    document.getElementById("task-list").innerHTML = out;
    return;
  }

  // Get priority order from settings, or use default order if not set
  const priorityOrder = setdat.task_priority_order || [];

  // Helper function to check if a task is enabled and get its display info
  function getTaskDisplayInfo(taskId) {
    if (taskId.startsWith("gather_")) {
      const fieldName = taskId.replace("gather_", "").replace("_", " ");
      // Check if this field is enabled
      for (let i = 0; i < 3; i++) {
        if (setdat.fields_enabled[i] && setdat.fields[i] === fieldName) {
          const emoji = fieldEmojis[fieldName.replaceAll(" ", "_")] || "";
          return {
            enabled: true,
            title: `Gather ${i + 1}`,
            desc: `${emoji} ${fieldName}`,
          };
        }
      }
      return { enabled: false };
    }

    if (taskId.startsWith("collect_")) {
      const collectName = taskId.replace("collect_", "");

      // Handle special cases
      if (collectName === "sticker_printer") {
        if (!setdat.sticker_printer) return { enabled: false };
        return {
          enabled: true,
          title: "Collect",
          desc: `${collectEmojis.sticker_printer || ""} ${toTitleCase(
            "sticker printer"
          )}`,
        };
      }

      if (collectName === "sticker_stack") {
        if (!setdat.sticker_stack) return { enabled: false };
        return {
          enabled: true,
          title: "Collect Buff",
          desc: toImgArray(stickerStackIcon).join("<br>"),
        };
      }

      // Regular collect items
      if (!setdat[collectName]) return { enabled: false };
      const emoji = collectEmojis[collectName] || "";
      return {
        enabled: true,
        title: "Collect",
        desc: `${emoji} ${toTitleCase(collectName.replaceAll("_", " "))}`,
      };
    }

    if (taskId.startsWith("kill_")) {
      const mob = taskId.replace("kill_", "");
      // Check if this mob is enabled
      if (!setdat[mob]) return { enabled: false };
      const displayName = mob === "rhinobeetle" ? "rhino beetle" : mob;
      const emoji = killEmojis[mob] || "";
      return {
        enabled: true,
        title: "Kill",
        desc: `${emoji} ${toTitleCase(displayName.replaceAll("_", " "))}`,
      };
    }

    if (taskId.startsWith("quest_")) {
      const questName = taskId.replace("quest_", "");
      const questKey = `${questName}_quest`;
      if (!setdat[questKey]) return { enabled: false };
      const emoji = questGiverEmojis[questKey] || "";
      return {
        enabled: true,
        title: "Quest",
        desc: `${emoji} ${toTitleCase(questName.replaceAll("_", " "))}`,
      };
    }

    // Special tasks
    if (taskId === "blender") {
      if (!setdat.blender_enable) return { enabled: false };
      const selectedBlenderItems = {};
      for (let i = 1; i < 4; i++) {
        const item = setdat[`blender_item_${i}`]?.replaceAll(" ", "_");
        if (item == "none" || !item) continue;
        selectedBlenderItems[toTitleCase(item.replaceAll("_", " "))] =
          blenderIcons[item];
      }
      return {
        enabled: true,
        title: "Blender",
        desc: toImgArray(selectedBlenderItems).join("<br>"),
      };
    }

    if (taskId === "planters") {
      if (!setdat.planters_mode) return { enabled: false };
      const type = setdat.planters_mode == 1 ? "Manual" : "Auto";
      return {
        enabled: true,
        title: "Planters",
        desc: type,
      };
    }

    if (taskId === "mondo_buff") {
      if (!setdat.mondo_buff) return { enabled: false };
      return {
        enabled: true,
        title: "Collect",
        desc: `${collectEmojis.mondo_buff || ""} ${toTitleCase("mondo buff")}`,
      };
    }

    if (taskId === "stinger_hunt") {
      if (!setdat.stinger_hunt) return { enabled: false };
      return {
        enabled: true,
        title: "Kill",
        desc: `${killEmojis.stinger_hunt || ""} ${toTitleCase("stinger hunt")}`,
      };
    }

    if (taskId === "auto_field_boost") {
      if (!setdat.Auto_Field_Boost) return { enabled: false };
      return {
        enabled: true,
        title: "Collect Buff",
        desc: `${collectEmojis.Auto_Field_Boost || ""} ${toTitleCase(
          "auto field boost"
        )}`,
      };
    }

    if (taskId === "ant_challenge") {
      if (!setdat.ant_challenge) return { enabled: false };
      return {
        enabled: true,
        title: "Kill",
        desc: `${killEmojis.ant_challenge || ""} ${toTitleCase(
          "ant challenge"
        )}`,
      };
    }

    // Field boosters (blue_booster, red_booster, mountain_booster)
    if (
      taskId === "collect_blue_booster" ||
      taskId === "collect_red_booster" ||
      taskId === "collect_mountain_booster"
    ) {
      const boosterName = taskId.replace("collect_", "");
      if (!setdat[boosterName]) return { enabled: false };
      const emoji = fieldBoosterEmojis[boosterName] || "";
      return {
        enabled: true,
        title: "Collect Buff",
        desc: `${emoji} ${toTitleCase(boosterName.replaceAll("_", " "))}`,
      };
    }

    return { enabled: false };
  }

  // If priority order exists, use it; otherwise fall back to old order
  if (priorityOrder && priorityOrder.length > 0) {
    // Display tasks in priority order
    for (const taskId of priorityOrder) {
      const taskInfo = getTaskDisplayInfo(taskId);
      if (taskInfo.enabled) {
        out += taskHTML(taskInfo.title, taskInfo.desc);
      }
    }
  } else {
    // Fallback to old order if no priority order is set
    //load quest givers
    for (const [k, v] of Object.entries(questGiverEmojis)) {
      if (!setdat[k]) continue;
      out += taskHTML(
        "Quest",
        `${v} ${toTitleCase(k.replaceAll("quest", "").replaceAll("_", " "))}`
      );
    }

    //load collect
    for (const [k, v] of Object.entries(collectEmojis)) {
      if (!setdat[k]) continue;
      out += taskHTML("Collect", `${v} ${toTitleCase(k.replaceAll("_", " "))}`);
    }
    //blender
    if (setdat["blender_enable"]) {
      const selectedBlenderItems = {};
      for (let i = 1; i < 4; i++) {
        const item = setdat[`blender_item_${i}`].replaceAll(" ", "_");
        if (item == "none") continue;
        selectedBlenderItems[toTitleCase(item.replaceAll("_", " "))] =
          blenderIcons[item];
      }
      out += taskHTML("Blender", toImgArray(selectedBlenderItems).join("<br>"));
    }
    //planters
    if (setdat["planters_mode"]) {
      const type = setdat["planters_mode"] == 1 ? "Manual" : "Auto";
      out += taskHTML("Planters", type);
    }
    //load kill
    for (let [k, v] of Object.entries(killEmojis)) {
      if (!setdat[k]) continue;
      if (k == "rhinobeetle") k = "rhino beetle";
      out += taskHTML("Kill", `${v} ${toTitleCase(k.replaceAll("_", " "))}`);
    }
    //load field boosters
    for (const [k, v] of Object.entries(fieldBoosterEmojis)) {
      if (!setdat[k]) continue;
      out += taskHTML(
        "Collect Buff",
        `${v} ${toTitleCase(k.replaceAll("_", " "))}`
      );
    }
    //load sticker stack
    for (const [k, v] of Object.entries(stickerStackIcon)) {
      if (!setdat[k]) continue;
      out += taskHTML(
        "Collect Buff",
        toImgArray(stickerStackIcon).join("<br>")
      );
    }
    //load the gather
    for (let i = 0; i <= setdat.fields_enabled.length; i++) {
      if (!setdat.fields_enabled[i]) continue;
      const field = setdat.fields[i];
      out += taskHTML(
        `Gather ${i + 1}`,
        `${fieldEmojis[field.replaceAll(" ", "_")]} ${field}`
      );
    }
  }

  //display the tasks
  document.getElementById("task-list").innerHTML = out;

  //planter timers

  function getPlanterHTML(planter, field, harvestTime) {
    const currTime = Date.now() / 1000;
    const timeRemaining = secondsToMinsAndHours(harvestTime - currTime);
    return `
            <div class="planter">
                <img class="planter-img" src="./assets/icons/${planter.replaceAll(
                  " ",
                  "_"
                )}_planter.png">
                <div class="field-row">
                    <span>${toTitleCase(field)}</span>
                </div>
                <span class="time ${
                  timeRemaining == "Ready!" ? "ready" : ""
                }">${timeRemaining}</span> 
            </div> 
        `;
  }

  const planterTimerContainer = document.getElementById(
    "planter-timers-container"
  );
  if (setdat["planters_mode"]) {
    planterTimerContainer.classList.add("show");
    let planterData;
    const planterContainer =
      planterTimerContainer.querySelector(".planter-timers");
    let planterTimersOut = "";

    if (setdat["planters_mode"] == 1) {
      planterData = await eel.getManualPlanterData()();
      for (let i = 0; i < planterData.planters.length; i++) {
        if (planterData.planters[i]) {
          planterTimersOut += getPlanterHTML(
            planterData.planters[i],
            planterData.fields[i],
            planterData.harvestTimes[i]
          );
        }
      }
    } else if (setdat["planters_mode"] == 2) {
      planterData = (await eel.getAutoPlanterData()()).planters;
      for (const planter of planterData) {
        if (planter.planter) {
          planterTimersOut += getPlanterHTML(
            planter.planter,
            planter.field,
            planter.harvest_time
          );
        }
      }
    }
    planterContainer.innerHTML = planterTimersOut;
  } else {
    planterTimerContainer.classList.remove("show");
  }
}

eel.expose(closeWindow);
function closeWindow() {
  let new_window = open(location, "_self");
  new_window.top.close();
}

// Function to periodically check and update button state
async function checkAndUpdateButtonState() {
  try {
    const runState = await eel.getRunState()();
    const isRunning = runState === 2;
    const isPaused = runState === 5;

    const settings = await loadAllSettings();
    const startKey = settings.start_keybind || "F1";
    const stopKey = settings.stop_keybind || "F3";

    const button = document.getElementById("start-btn");
    if (button) {
      if (isPaused) {
        button.classList.add("paused");
        button.classList.remove("active");
        button.disabled = true;
        button.textContent = `⏸️ Paused`;
      } else if (isRunning) {
        button.classList.add("active");
        button.classList.remove("paused");
        button.disabled = false;
        button.textContent = `Stop [${stopKey}]`;
      } else {
        button.classList.remove("active");
        button.classList.remove("paused");
        button.disabled = false;
        button.textContent = `Start [${startKey}]`;
      }
    }

    // Update field-only mode dropdown to match current settings
    const fieldOnlyDropdown = document.getElementById("field_only_mode");
    if (fieldOnlyDropdown) {
      const currentValue = settings.field_only_mode ? "true" : "false";
      if (fieldOnlyDropdown.value !== currentValue) {
        fieldOnlyDropdown.value = currentValue;
      }
    }
  } catch (error) {
    console.error("Error checking button state:", error);
  }
}

// Start polling for button state updates
let buttonStateInterval;

$("#home-placeholder")
  .load("../htmlImports/tabs/home.html", async () => {
    await loadTasks();
    await updateStartButtonText();

    // Initialize field-only mode dropdown
    const settings = await loadAllSettings();
    const fieldOnlyDropdown = document.getElementById("field_only_mode");
    if (fieldOnlyDropdown) {
      fieldOnlyDropdown.value = settings.field_only_mode ? "true" : "false";
    }

    // Start checking button state every 500ms
    buttonStateInterval = setInterval(checkAndUpdateButtonState, 500);
  }) //load home tab
  .on("unload", () => {
    // Stop polling when tab is unloaded
    if (buttonStateInterval) {
      clearInterval(buttonStateInterval);
      buttonStateInterval = null;
    }
  })
  .on("click", "#log-btn", (event) => {
    //log button
    const result = purpleButtonToggle(event.currentTarget, [
      "Simple",
      "Detailed",
    ]);
    document.getElementById("log-type").innerText = result;
  })
  .on("click", "#start-btn", (event) => {
    //start button
    //no need to change display, python will trigger toggleStartStop
    if (event.currentTarget.classList.contains("active")) {
      eel.stop();
    } else {
      eel.start();
    }
  })
  .on("click", "#update-btn", async (event) => {
    //start button
    if (!event.currentTarget.classList.contains("active")) {
      purpleButtonToggle(event.currentTarget, ["Update", "Updating"]);
      await eel.update();
    }
  })
  .on("click", "#clear-timers-btn", async (event) => {
    const btn = event.currentTarget;
    if (btn.classList.contains("active")) return;
    btn.classList.add("active");
    const setdat = await loadAllSettings();
    if (setdat["planters_mode"] == 1) {
      eel.clearManualPlanters();
    } else if (setdat["planters_mode"] == 2) {
      eel.clearAutoPlanters();
    }
    document
      .getElementById("planter-timers-container")
      .querySelector(".planter-timers").innerHTML = "";
    setTimeout(() => {
      btn.classList.remove("active");
    }, 700);
  })
  .on("change", "#field_only_mode", async (event) => {
    // Handle field-only mode dropdown
    const selectedValue = event.currentTarget.value;
    const isFieldOnlyMode = selectedValue === "true";
    await eel.saveGeneralSetting("field_only_mode", isFieldOnlyMode);
    // Reload tasks to reflect the change
    await loadTasks();
  });
