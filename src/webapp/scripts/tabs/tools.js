let autoClickerTimer = null;
const AUTOCLICKER_MIN_INTERVAL = 10;
const AUTOCLICKER_DEFAULT_INTERVAL = 100;
const AUTOCLICKER_DEFAULT_KEYBIND = "F4";
let autoClickerHotkeyListenerAdded = false;

const TREAT_COST_HONEY = 10000;
const BOND_REQUIREMENTS = [
  0,
  10,
  40,
  200,
  750,
  4000,
  15000,
  60000,
  270000,
  450000,
  1200000,
  2000000,
  4000000,
  7000000,
  15000000,
  120000000,
  450000000,
  1900000000,
  7500000000,
  15000000000,
  475000000000,
  4500000000000,
  95000000000000,
  5000000000000000,
  95000000000000000,
];

function formatCompactHoney(value) {
  const units = [
    { threshold: 1e12, suffix: "T" },
    { threshold: 1e9, suffix: "B" },
    { threshold: 1e6, suffix: "M" },
    { threshold: 1e3, suffix: "K" },
  ];
  const compactFormatter = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

  const absValue = Math.abs(value);
  for (const unit of units) {
    if (absValue >= unit.threshold) {
      const scaled = value / unit.threshold;
      return `${compactFormatter.format(scaled)} ${unit.suffix}`;
    }
  }

  return compactFormatter.format(value);
}

function formatWholeNumber(value) {
  return Math.round(value).toLocaleString();
}

function getBondCalcElements() {
  return {
    start: document.getElementById("bond-calc-start-level"),
    end: document.getElementById("bond-calc-end-level"),
    bonus: document.getElementById("bond-calc-bonus"),
    warning: document.getElementById("bond-calc-warning"),
    totalBond: document.getElementById("bond-calc-total-bond"),
    totalTreats: document.getElementById("bond-calc-total-treats"),
    totalCostOne: document.getElementById("bond-calc-total-cost-one"),
    totalCostFifty: document.getElementById("bond-calc-total-cost-fifty"),
    breakdown: document.getElementById("bond-calc-breakdown"),
  };
}

function calculateTreatsForBond(bond, bonusPercent) {
  const bondPerTreat = 10 * (1 + bonusPercent / 100);
  return Math.ceil(bond / bondPerTreat);
}

function buildBondBreakdownRows(startLevel, endLevel, bonusPercent) {
  const rows = [];

  for (let level = startLevel; level < endLevel; level++) {
    const bond = BOND_REQUIREMENTS[level] || 0;
    const treats = calculateTreatsForBond(bond, bonusPercent);
    const costPerBee = treats * TREAT_COST_HONEY;
    const costForFifty = costPerBee * 50;

    rows.push({
      label: `${level} -> ${level + 1}`,
      bond,
      treats,
      costPerBee,
      costForFifty,
    });
  }

  return rows;
}

function updateBondTreatCalculator() {
  const el = getBondCalcElements();
  if (!el.start || !el.end || !el.bonus || !el.breakdown) return;

  const startLevel = parseInt(el.start.value, 10);
  const endLevel = parseInt(el.end.value, 10);
  let bonusPercent = parseFloat(el.bonus.value);

  if (Number.isNaN(bonusPercent) || bonusPercent < 0) bonusPercent = 0;
  if (bonusPercent > 300) bonusPercent = 300;
  el.bonus.value = bonusPercent;

  if (startLevel >= endLevel) {
    el.warning.style.display = "block";
    el.warning.textContent = "Final level must be higher than initial level.";

    el.totalBond.textContent = "0";
    el.totalTreats.textContent = "0";
    el.totalCostOne.textContent = "0";
    el.totalCostFifty.textContent = "0";
    el.breakdown.innerHTML = "";
    return;
  }

  el.warning.style.display = "none";

  const rows = buildBondBreakdownRows(startLevel, endLevel, bonusPercent);
  const totals = rows.reduce(
    (acc, row) => {
      acc.bond += row.bond;
      acc.treats += row.treats;
      acc.costOne += row.costPerBee;
      acc.costFifty += row.costForFifty;
      return acc;
    },
    { bond: 0, treats: 0, costOne: 0, costFifty: 0 }
  );

  el.totalBond.textContent = formatWholeNumber(totals.bond);
  el.totalTreats.textContent = formatWholeNumber(totals.treats);
  el.totalCostOne.textContent = formatCompactHoney(totals.costOne);
  el.totalCostFifty.textContent = formatCompactHoney(totals.costFifty);

  el.breakdown.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.label}</td>
        <td>${formatWholeNumber(row.bond)}</td>
        <td>${formatWholeNumber(row.treats)}</td>
        <td>${formatCompactHoney(row.costPerBee)}</td>
        <td>${formatCompactHoney(row.costForFifty)}</td>
      </tr>
    `
    )
    .join("");
}

function initializeBondTreatCalculator() {
  const el = getBondCalcElements();
  if (!el.start || !el.end || !el.bonus) return;

  if (!el.start.value) el.start.value = "1";
  if (!el.end.value) el.end.value = "20";
  if (!el.bonus.value) el.bonus.value = "20";

  [el.start, el.end, el.bonus].forEach((input) => {
    input.addEventListener("change", updateBondTreatCalculator);
    input.addEventListener("input", updateBondTreatCalculator);
  });

  updateBondTreatCalculator();
}

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
  initializeBondTreatCalculator();

  switchToolsTab(document.getElementById("tools-autoclicker"));
}

$("#tools-placeholder")
  .load("../htmlImports/tabs/tools.html", loadTools)
  .on("click", ".tools-tab-item", (event) => switchToolsTab(event.currentTarget));
