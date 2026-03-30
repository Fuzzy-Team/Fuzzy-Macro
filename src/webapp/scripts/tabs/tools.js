let autoClickerTimer = null;
let autoClickerStatusTimer = null;
let autoGiftedBasicBeeStatusTimer = null;
let toolSessionSynced = false;
const TOOL_SESSION_ID = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const AUTOCLICKER_MIN_INTERVAL = 10;
const AUTOCLICKER_DEFAULT_INTERVAL = 100;
const AUTO_GIFTED_BASIC_BEE_DEFAULT_DELAY = 3;

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
  900000000000000,
  9000000000000000,
];

function formatCompactHoney(value) {
  const units = [
    { threshold: 1e18, suffix: "Qn" },
    { threshold: 1e15, suffix: "Qd" },
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
    beeCount: document.getElementById("bond-calc-bee-count"),
    warning: document.getElementById("bond-calc-warning"),
    totalBond: document.getElementById("bond-calc-total-bond"),
    totalTreatsLabel: document.getElementById("bond-calc-total-treats-label"),
    totalTreats: document.getElementById("bond-calc-total-treats"),
    totalCostOne: document.getElementById("bond-calc-total-cost-one"),
    totalCostBeesLabel: document.getElementById("bond-calc-total-cost-bees-label"),
    totalCostBees: document.getElementById("bond-calc-total-cost-bees"),
    breakdownCostBeesLabel: document.getElementById("bond-calc-breakdown-cost-bees-label"),
    breakdown: document.getElementById("bond-calc-breakdown"),
  };
}

function calculateTreatsForBond(bond, bonusPercent) {
  const bondPerTreat = 10 * (1 + bonusPercent / 100);
  return Math.ceil(bond / bondPerTreat);
}

function buildBondBreakdownRows(startLevel, endLevel, bonusPercent, beeCount) {
  const rows = [];

  for (let level = startLevel; level < endLevel; level++) {
    const bond = BOND_REQUIREMENTS[level] || 0;
    const treats = calculateTreatsForBond(bond, bonusPercent);
    const costPerBee = treats * TREAT_COST_HONEY;
    const costForBees = costPerBee * beeCount;

    rows.push({
      label: `${level} -> ${level + 1}`,
      bond,
      treats,
      costPerBee,
      costForBees,
    });
  }

  return rows;
}

function updateBondTreatCalculator() {
  const el = getBondCalcElements();
  if (!el.start || !el.end || !el.bonus || !el.beeCount || !el.breakdown) return;

  const startLevel = parseInt(el.start.value, 10);
  const endLevel = parseInt(el.end.value, 10);
  let bonusPercent = parseFloat(el.bonus.value);
  let beeCount = parseInt(el.beeCount.value, 10);

  if (Number.isNaN(bonusPercent) || bonusPercent < 0) bonusPercent = 0;
  if (bonusPercent > 300) bonusPercent = 300;
  el.bonus.value = bonusPercent;

  if (Number.isNaN(beeCount) || beeCount < 1) beeCount = 1;
  if (beeCount > 50) beeCount = 50;
  el.beeCount.value = beeCount;

  if (el.totalTreatsLabel) {
    el.totalTreatsLabel.textContent = `Treats Needed (${beeCount} Bee${beeCount === 1 ? "" : "s"})`;
  }
  if (el.totalCostBeesLabel) {
    el.totalCostBeesLabel.textContent = `Cost (${beeCount} Bee${beeCount === 1 ? "" : "s"})`;
  }
  if (el.breakdownCostBeesLabel) {
    el.breakdownCostBeesLabel.textContent = `Cost for ${beeCount} Bee${beeCount === 1 ? "" : "s"}`;
  }

  if (startLevel >= endLevel) {
    el.warning.style.display = "block";
    el.warning.textContent = "Final level must be higher than initial level.";

    el.totalBond.textContent = "0";
    el.totalTreats.textContent = "0";
    el.totalCostOne.textContent = "0";
    el.totalCostBees.textContent = "0";
    el.breakdown.innerHTML = "";
    return;
  }

  el.warning.style.display = "none";

  const rows = buildBondBreakdownRows(startLevel, endLevel, bonusPercent, beeCount);
  const totals = rows.reduce(
    (acc, row) => {
      acc.bond += row.bond;
      acc.treats += row.treats;
      acc.costOne += row.costPerBee;
      return acc;
    },
    { bond: 0, treats: 0, costOne: 0 }
  );
  const totalTreatsForBees = totals.treats * beeCount;
  const totalCostForBees = totals.costOne * beeCount;

  el.totalBond.textContent = formatCompactHoney(totals.bond);
  el.totalTreats.textContent = formatCompactHoney(totalTreatsForBees);
  el.totalCostOne.textContent = formatCompactHoney(totals.costOne);
  el.totalCostBees.textContent = formatCompactHoney(totalCostForBees);

  el.breakdown.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.label}</td>
        <td>${formatWholeNumber(row.bond)}</td>
        <td>${formatWholeNumber(row.treats)}</td>
        <td>${formatCompactHoney(row.costPerBee)}</td>
        <td>${formatCompactHoney(row.costForBees)}</td>
      </tr>
    `
    )
    .join("");
}

function initializeBondTreatCalculator() {
  const el = getBondCalcElements();
  if (!el.start || !el.end || !el.bonus || !el.beeCount) return;

  if (!el.start.value) el.start.value = "1";
  if (!el.end.value) el.end.value = "20";
  if (!el.bonus.value) el.bonus.value = "20";
  if (!el.beeCount.value) el.beeCount.value = "50";

  [el.start, el.end, el.bonus, el.beeCount].forEach((input) => {
    input.addEventListener("change", updateBondTreatCalculator);
    input.addEventListener("input", updateBondTreatCalculator);
  });

  updateBondTreatCalculator();
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

async function refreshToolStopHotkey() {
  if (typeof loadAllSettings !== "function") return;

  try {
    const settings = await loadAllSettings();
    const stopKey = settings.stop_keybind || "F3";

    const autoClickerStopHotkey = document.getElementById("autoclicker_stop_hotkey");
    if (autoClickerStopHotkey) {
      autoClickerStopHotkey.textContent = stopKey;
    }

    const autoGiftedBasicBeeStopHotkey = document.getElementById("auto-gifted-basic-bee-stop-hotkey");
    if (autoGiftedBasicBeeStopHotkey) {
      autoGiftedBasicBeeStopHotkey.textContent = stopKey;
    }
  } catch (error) {
    console.error("Failed to load tool stop hotkey:", error);
  }
}

function onAutoClickerIntervalChange() {
  getAutoClickerInterval();
}

function renderAutoClickerStatus(status) {
  if (!status) return;

  autoClickerTimer = status.running ? true : null;

  const startButton = document.getElementById("autoclicker_start");
  if (startButton) {
    startButton.classList.toggle("active", !!status.running);
    startButton.innerText = status.running ? "Running" : "Start";
    startButton.style.display = status.running ? "none" : "";
  }

  const stopButton = document.getElementById("autoclicker_stop");
  if (stopButton) {
    stopButton.classList.toggle("active", !!status.running);
    stopButton.style.display = status.running ? "" : "none";
  }

  const statusElement = document.getElementById("autoclicker_status");
  if (statusElement) {
    statusElement.textContent = status.message || "Ready";
  }
}

async function refreshAutoClickerStatus() {
  if (!window.eel || typeof eel.getAutoClickerStatus !== "function") return;

  try {
    const status = await eel.getAutoClickerStatus()();
    renderAutoClickerStatus(status);
  } catch (error) {
    console.error("Failed to refresh auto clicker status:", error);
  }
}

async function syncToolSessionState() {
  if (toolSessionSynced) return;
  if (!window.eel || typeof eel.syncToolSession !== "function") return;

  try {
    const result = await eel.syncToolSession(TOOL_SESSION_ID)();
    toolSessionSynced = true;

    if (result?.status?.auto_clicker) {
      renderAutoClickerStatus(result.status.auto_clicker);
    }

    if (result?.status?.auto_gifted_basic_bee) {
      renderAutoGiftedBasicBeeStatus(result.status.auto_gifted_basic_bee);
    }
  } catch (error) {
    console.error("Failed to sync tool session:", error);
  }
}

async function startAutoClicker() {
  if (!window.eel || typeof eel.startAutoClickerTool !== "function") return;
  if (autoClickerTimer) return;

  const startButton = document.getElementById("autoclicker_start");
  if (startButton) {
    startButton.classList.add("active");
    startButton.innerText = "Starting...";
  }

  try {
    const result = await eel.startAutoClickerTool(getAutoClickerInterval())();
    const statusElement = document.getElementById("autoclicker_status");
    if (statusElement && result && result.message) {
      statusElement.textContent = result.message;
    }
  } catch (error) {
    console.error("Failed to start auto clicker:", error);
  }

  await refreshAutoClickerStatus();
}

async function stopAutoClicker() {
  if (!window.eel || typeof eel.stopAutoClickerTool !== "function") return;

  try {
    const result = await eel.stopAutoClickerTool()();
    const statusElement = document.getElementById("autoclicker_status");
    if (statusElement && result && result.message) {
      statusElement.textContent = result.message;
    }
  } catch (error) {
    console.error("Failed to stop auto clicker:", error);
  }

  await refreshAutoClickerStatus();
}

function initializeAutoClickerTool() {
  const intervalInput = document.getElementById("autoclicker_interval_ms");
  if (intervalInput && !intervalInput.value) {
    intervalInput.value = AUTOCLICKER_DEFAULT_INTERVAL;
  }

  if (!autoClickerStatusTimer) {
    autoClickerStatusTimer = setInterval(refreshAutoClickerStatus, 1000);
  }

  refreshAutoClickerStatus();
}

function getAutoGiftedBasicBeeDelay() {
  const input = document.getElementById("auto-gifted-basic-bee-delay");
  if (!input) return AUTO_GIFTED_BASIC_BEE_DEFAULT_DELAY;

  let delay = parseInt(input.value, 10);
  if (Number.isNaN(delay)) delay = AUTO_GIFTED_BASIC_BEE_DEFAULT_DELAY;
  delay = Math.min(10, Math.max(1, delay));
  input.value = delay;
  return delay;
}

function getAutoGiftedBasicBeePauseSettings() {
  return {
    pause_on_gifted_basic: true,
    pause_on_gifted_other: !!document.getElementById("auto-gifted-basic-bee-pause-gifted-other")?.checked,
    pause_on_legendary: !!document.getElementById("auto-gifted-basic-bee-pause-legendary")?.checked,
    pause_on_mythic: !!document.getElementById("auto-gifted-basic-bee-pause-mythic")?.checked,
    pause_on_basic: false,
    pause_on_other: false,
  };
}

function renderAutoGiftedBasicBeeStatus(status) {
  if (!status) return;

  const state = document.getElementById("auto-gifted-basic-bee-state");
  const slot = document.getElementById("auto-gifted-basic-bee-slot");
  const eggs = document.getElementById("auto-gifted-basic-bee-eggs");
  const rj = document.getElementById("auto-gifted-basic-bee-rj");
  const rolls = document.getElementById("auto-gifted-basic-bee-rolls");
  const message = document.getElementById("auto-gifted-basic-bee-message");
  const lastText = document.getElementById("auto-gifted-basic-bee-last-text");
  const startButton = document.getElementById("auto-gifted-basic-bee-start");
  const stopButton = document.getElementById("auto-gifted-basic-bee-stop");

  if (state) state.textContent = status.state || "idle";
  if (slot) {
    slot.textContent =
      status.bee_slot_x != null && status.bee_slot_y != null
        ? `${status.bee_slot_x}, ${status.bee_slot_y}`
        : "Not captured";
  }
  if (eggs) eggs.textContent = status.basic_eggs_used ?? 0;
  if (rj) rj.textContent = status.royal_jellies_used ?? 0;
  if (rolls) rolls.textContent = status.rolls ?? 0;
  if (message) message.textContent = status.message || "Ready";
  if (lastText) lastText.textContent = status.last_detected_text || "None";

  if (startButton) {
    startButton.classList.toggle("active", !!status.running);
    startButton.textContent = "Start";
    startButton.style.display = status.running ? "none" : "";
  }

  if (stopButton) {
    stopButton.classList.toggle("active", !!status.running);
    stopButton.style.display = status.running ? "" : "none";
  }
}

async function refreshAutoGiftedBasicBeeStatus() {
  if (!window.eel || typeof eel.getAutoGiftedBasicBeeStatus !== "function") return;
  try {
    const status = await eel.getAutoGiftedBasicBeeStatus()();
    renderAutoGiftedBasicBeeStatus(status);
  } catch (error) {
    console.error("Failed to refresh Auto Gifted Basic Bee status:", error);
  }
}

async function startAutoGiftedBasicBeeTool() {
  if (!window.eel || typeof eel.startAutoGiftedBasicBeeTool !== "function") return;
  const delay = getAutoGiftedBasicBeeDelay();
  const pauseSettings = getAutoGiftedBasicBeePauseSettings();

  try {
    const result = await eel.startAutoGiftedBasicBeeTool(delay, pauseSettings)();
    const message = document.getElementById("auto-gifted-basic-bee-message");
    if (message && result && result.message) {
      message.textContent = result.message;
    }
    await refreshAutoGiftedBasicBeeStatus();
  } catch (error) {
    console.error("Failed to start Auto Gifted Basic Bee tool:", error);
  }
}

async function stopAutoGiftedBasicBeeTool() {
  if (!window.eel || typeof eel.stopAutoGiftedBasicBeeTool !== "function") return;

  try {
    const result = await eel.stopAutoGiftedBasicBeeTool()();
    const message = document.getElementById("auto-gifted-basic-bee-message");
    if (message && result && result.message) {
      message.textContent = result.message;
    }
    await refreshAutoGiftedBasicBeeStatus();
  } catch (error) {
    console.error("Failed to stop Auto Gifted Basic Bee tool:", error);
  }
}

function initializeAutoGiftedBasicBeeTool() {
  const delayInput = document.getElementById("auto-gifted-basic-bee-delay");
  if (delayInput && !delayInput.value) {
    delayInput.value = AUTO_GIFTED_BASIC_BEE_DEFAULT_DELAY;
  }

  if (!autoGiftedBasicBeeStatusTimer) {
    autoGiftedBasicBeeStatusTimer = setInterval(refreshAutoGiftedBasicBeeStatus, 1000);
  }

  refreshAutoGiftedBasicBeeStatus();
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
  syncToolSessionState();
  refreshToolStopHotkey();
  initializeAutoClickerTool();
  initializeBondTreatCalculator();
  initializeAutoGiftedBasicBeeTool();

  switchToolsTab(document.getElementById("tools-autoclicker"));
}

$("#tools-placeholder")
  .load("../htmlImports/tabs/tools.html", loadTools)
  .on("click", ".tools-tab-item", (event) => switchToolsTab(event.currentTarget));
