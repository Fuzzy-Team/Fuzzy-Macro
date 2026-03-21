let autoClickerTimer = null;
const AUTOCLICKER_MIN_INTERVAL = 10;
const AUTOCLICKER_DEFAULT_INTERVAL = 100;
const AUTOCLICKER_DEFAULT_KEYBIND = "F4";
let autoClickerHotkeyListenerAdded = false;

function normalizeKeybindFromEvent(event) {
  let combo = [];
  if (event.ctrlKey) combo.push("Ctrl");
  if (event.altKey) combo.push("Alt");
  if (event.shiftKey) combo.push("Shift");
  if (event.metaKey) combo.push("Cmd");

  let mainKey = event.key;
  if (mainKey === " ") mainKey = "Space";
  else if (mainKey === "Control") mainKey = "Ctrl";
  else if (mainKey === "Alt") mainKey = "Alt";
  else if (mainKey === "Shift") mainKey = "Shift";
  else if (mainKey === "Meta") mainKey = "Cmd";
  else if (mainKey.startsWith("F") && mainKey.length <= 3) mainKey = mainKey;
  else if (mainKey.length === 1) mainKey = mainKey.toUpperCase();

  combo.push(mainKey);
  return combo.join("+");
}

function getAutoClickerKeybind() {
  const keybindElement = document.getElementById("autoclicker_keybind");
  if (!keybindElement) return AUTOCLICKER_DEFAULT_KEYBIND;
  return keybindElement.dataset.keybind || AUTOCLICKER_DEFAULT_KEYBIND;
}

function ensureAutoClickerKeybindLoaded() {
  const keybindElement = document.getElementById("autoclicker_keybind");
  if (!keybindElement) return;

  let keybind = keybindElement.dataset.keybind || "";
  if (!keybind) {
    keybind = AUTOCLICKER_DEFAULT_KEYBIND;
    keybindElement.dataset.keybind = keybind;
    if (window.eel && typeof eel.saveGeneralSetting === "function") {
      eel.saveGeneralSetting("autoclicker_keybind", keybind);
    }
  }

  const display = keybindElement.querySelector(".keybind-display");
  if (display) {
    display.textContent = keybind.replace(/\+/g, " + ");
  }
}

function shouldIgnoreAutoClickerHotkey(event) {
  if (typeof keybindRecording !== "undefined" && keybindRecording) return true;

  const target = event.target;
  if (!target) return false;

  const tagName = (target.tagName || "").toLowerCase();
  const editable = target.isContentEditable;
  const isTextInput = tagName === "input" || tagName === "textarea" || tagName === "select";
  return editable || isTextInput;
}

function addAutoClickerHotkeyListener() {
  if (autoClickerHotkeyListenerAdded) return;
  autoClickerHotkeyListenerAdded = true;

  window.addEventListener("keydown", (event) => {
    if (shouldIgnoreAutoClickerHotkey(event)) return;

    const configuredKeybind = getAutoClickerKeybind();
    if (!configuredKeybind) return;

    const pressed = normalizeKeybindFromEvent(event);
    if (pressed !== configuredKeybind) return;

    event.preventDefault();
    event.stopPropagation();

    if (autoClickerTimer) {
      stopAutoClicker();
    } else {
      startAutoClicker();
    }
  });
}

function getAutoClickerInterval() {
  const input = document.getElementById("autoclicker_interval_ms");
  if (!input) return AUTOCLICKER_DEFAULT_INTERVAL;

  let interval = parseInt(input.value, 10);
  if (Number.isNaN(interval)) interval = AUTOCLICKER_DEFAULT_INTERVAL;
  if (interval < AUTOCLICKER_MIN_INTERVAL) interval = AUTOCLICKER_MIN_INTERVAL;

  input.value = interval;
  return interval;
}

function onAutoClickerIntervalChange() {
  const interval = getAutoClickerInterval();
  if (autoClickerTimer) {
    clearInterval(autoClickerTimer);
    autoClickerTimer = setInterval(() => {
      if (window.eel && typeof eel.autoClickerClick === "function") {
        eel.autoClickerClick();
      }
    }, interval);
  }
}

function startAutoClicker() {
  if (autoClickerTimer) return;

  const interval = getAutoClickerInterval();
  const startButton = document.getElementById("autoclicker_start");

  if (startButton) {
    startButton.classList.add("active");
    startButton.innerText = "Running";
  }

  autoClickerTimer = setInterval(() => {
    if (window.eel && typeof eel.autoClickerClick === "function") {
      eel.autoClickerClick();
    }
  }, interval);
}

function stopAutoClicker() {
  if (!autoClickerTimer) return;

  clearInterval(autoClickerTimer);
  autoClickerTimer = null;

  const startButton = document.getElementById("autoclicker_start");
  if (startButton) {
    startButton.classList.remove("active");
    startButton.innerText = "Start";
  }
}

function switchToolsTab(target) {
  const selector = document.getElementById("tools-select");
  if (selector) selector.remove();

  Array.from(document.getElementsByClassName("tools-tab-item")).forEach((x) => {
    x.classList.remove("active");
    const panel = document.getElementById(`${x.id}-tab`);
    if (panel) panel.style.display = "none";
  });

  target.classList.add("active");
  target.innerHTML = `<div class = "select-indicator" id = "tools-select"></div>` + target.innerHTML;

  const tab = document.getElementById(`${target.id}-tab`);
  if (tab) {
    tab.style.display = "block";
    tab.scrollTo(0, 0);
  }
}

function loadTools() {
  const intervalInput = document.getElementById("autoclicker_interval_ms");
  if (intervalInput && !intervalInput.value) {
    intervalInput.value = AUTOCLICKER_DEFAULT_INTERVAL;
  }

  ensureAutoClickerKeybindLoaded();
  addAutoClickerHotkeyListener();

  switchToolsTab(document.getElementById("tools-autoclicker"));
}

$("#tools-placeholder")
  .load("../htmlImports/tabs/tools.html", loadTools)
  .on("click", ".tools-tab-item", (event) => switchToolsTab(event.currentTarget));
