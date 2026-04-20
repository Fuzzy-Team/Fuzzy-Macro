let autoClickerTimer = null;
let autoClickerStatusTimer = null;
let autoGiftedBasicBeeStatusTimer = null;
let hotbarBuffStatusTimer = null;
let toolSessionSynced = false;
const TOOL_SESSION_ID = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const AUTOCLICKER_MIN_INTERVAL = 10;
const AUTOCLICKER_DEFAULT_INTERVAL = 100;
const AUTOCLICKER_DEFAULT_START_DELAY = 3;
const AUTO_GIFTED_BASIC_BEE_DEFAULT_DELAY = 3;
const PRIVATE_SERVER_API_ENDPOINT = "https://servers.fuzzymacro.com/api/servers";
const PRIVATE_SERVER_API_HEADERS = {
  "x-fuzzy-macro-client": "fuzzy-macro",
};
const PRIVATE_SERVER_PAGE_SIZE = 8;
let privateServerEntries = [];
let privateServerPage = 1;

const PRIVATE_SERVER_OPTION_DEFAULTS = {
  field: [
    "Any Field",
    "Sunflower",
    "Dandelion",
    "Mushroom",
    "Blue Flower",
    "Clover",
    "Spider",
    "Bamboo",
    "Strawberry",
    "Pineapple",
    "Stump",
    "Cactus",
    "Pumpkin",
    "Pine Tree",
    "Rose",
    "Mountain Top",
    "Coconut",
    "Pepper",
  ],
  hiveColor: ["Any", "Blue", "Red", "White", "Mixed"],
  region: ["NA", "EU", "OCE", "ASIA", "SA", "AF"],
  minimumSprinkler: ["N/A", "Basic Sprinkler", "Silver Soakers", "Golden Gushers", "Diamond Drenchers", "The Supreme Saturator", "Supreme Saturator"],
  allowedTasks: ["Bug Run", "Boosting", "Quests", "Vic Finder/Night Detection", "Mondo", "Honeystorm", "Snowstorm", "Planters", "Memory Match"],
  neededTasks: ["Mondo", "Honeystorm", "Snowstorm", "Bug Run", "Boosting", "Quests", "Vic Finder/Night Detection", "Puffshrooms"],
};

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
  // Treat 100% as the base (no bonus). Any input is interpreted as total
  // Bond from Treats %. We compute the effective bonus relative to 100%
  // (e.g., input 120 -> effective 20). Ensure the effective bonus
  // never goes below 0.
  const effectiveBonus = Math.max(0, (Number(bonusPercent) || 0) - 100);
  const bondPerTreat = 10 * (1 + effectiveBonus / 100);
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

function getAutoClickerStartDelay() {
  const input = document.getElementById("autoclicker_start_delay_seconds");
  if (!input) return AUTOCLICKER_DEFAULT_START_DELAY;

  let delay = parseInt(input.value, 10);
  if (Number.isNaN(delay)) delay = AUTOCLICKER_DEFAULT_START_DELAY;
  delay = Math.min(10, Math.max(0, delay));

  input.value = delay;
  return delay;
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

    const hotbarBuffStartHotkey = document.getElementById("hotbar-buff-start-hotkey");
    if (hotbarBuffStartHotkey) {
      hotbarBuffStartHotkey.textContent = settings.hotbar_buff_start_keybind || "F4";
    }

    const hotbarBuffStopHotkey = document.getElementById("hotbar-buff-stop-hotkey");
    if (hotbarBuffStopHotkey) {
      hotbarBuffStopHotkey.textContent = stopKey;
    }
  } catch (error) {
    console.error("Failed to load tool stop hotkey:", error);
  }
}

function onAutoClickerIntervalChange() {
  getAutoClickerInterval();
}

function onAutoClickerStartDelayChange() {
  getAutoClickerStartDelay();
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

    if (result?.status?.hotbar_buff) {
      renderHotbarBuffStatus(result.status.hotbar_buff);
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
    const result = await eel.startAutoClickerTool(
      getAutoClickerInterval(),
      getAutoClickerStartDelay()
    )();
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
  const startDelayInput = document.getElementById("autoclicker_start_delay_seconds");
  if (startDelayInput && !startDelayInput.value) {
    startDelayInput.value = AUTOCLICKER_DEFAULT_START_DELAY;
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

function renderHotbarBuffStatus(status) {
  if (!status) return;

  const state = document.getElementById("hotbar-buff-state");
  const lastSlot = document.getElementById("hotbar-buff-last-slot");
  const message = document.getElementById("hotbar-buff-message");
  const startButton = document.getElementById("hotbar-buff-start");
  const stopButton = document.getElementById("hotbar-buff-stop");

  if (state) state.textContent = status.state || "idle";
  if (lastSlot) lastSlot.textContent = status.last_slot ? `Slot ${status.last_slot}` : "None";
  if (message) message.textContent = status.message || "Ready";

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

async function refreshHotbarBuffStatus() {
  if (!window.eel || typeof eel.getHotbarBuffStatus !== "function") return;

  try {
    const status = await eel.getHotbarBuffStatus()();
    renderHotbarBuffStatus(status);
  } catch (error) {
    console.error("Failed to refresh hotbar buff status:", error);
  }
}

async function startHotbarBuffTool() {
  if (!window.eel || typeof eel.startHotbarBuffTool !== "function") return;

  try {
    const result = await eel.startHotbarBuffTool()();
    const message = document.getElementById("hotbar-buff-message");
    if (message && result && result.message) {
      message.textContent = result.message;
    }
    await refreshHotbarBuffStatus();
  } catch (error) {
    console.error("Failed to start hotbar buff tool:", error);
  }
}

async function stopHotbarBuffTool() {
  if (!window.eel || typeof eel.stopHotbarBuffTool !== "function") return;

  try {
    const result = await eel.stopHotbarBuffTool()();
    const message = document.getElementById("hotbar-buff-message");
    if (message && result && result.message) {
      message.textContent = result.message;
    }
    await refreshHotbarBuffStatus();
  } catch (error) {
    console.error("Failed to stop hotbar buff tool:", error);
  }
}

function initializeHotbarBuffTool() {
  if (!hotbarBuffStatusTimer) {
    hotbarBuffStatusTimer = setInterval(refreshHotbarBuffStatus, 1000);
  }

  refreshHotbarBuffStatus();
  switchHotbarBuffToolSlot(1);
}

function privateServerNumber(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  if (String(value).trim().toLowerCase() === "n/a") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function privateServerBoolean(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value > 0;
  const normalized = String(value ?? "").trim().toLowerCase();
  return ["yes", "true", "needed", "required", "1"].includes(normalized);
}

function privateServerRequiredBeeCount(requiredBees, beeName) {
  if (!Array.isArray(requiredBees)) return undefined;
  const target = requiredBees.find((bee) => String(bee?.name || "").toLowerCase() === beeName);
  return target ? target.count : undefined;
}

function privateServerArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean).map((item) => String(item).trim()).filter(Boolean);
  return String(value)
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function privateServerEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function privateServerFormatList(items, fallback = "None") {
  const list = privateServerArray(items);
  if (!list.length) return fallback;
  return list.map(privateServerEscape).join(", ");
}

function privateServerFormatDate(value) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function privateServerOptionValue(value) {
  const normalized = String(value || "").trim();
  return normalized.toLowerCase() === "any field" || normalized.toLowerCase() === "any" ? "" : normalized;
}

function normalizePrivateServer(raw, index) {
  const requirements = raw.requirements || {};
  const giftedBees = requirements.gifted_bees || raw.gifted_bees || {};
  const tasks = raw.tasks || {};
  const slots = raw.slots || {};
  const requiredBees = requirements.required_bees || raw.required_bees || [];

  return {
    id: String(raw.id || raw.message_id || `server-${index}`),
    link: raw.link || raw.url || raw.private_server_link || "",
    author: raw.author || raw.discord?.author || "",
    messageText: raw.message_text || raw.discord?.message_text || raw.notes || "",
    createdAt: raw.created_at || raw.timestamp || raw.discord?.created_at || "",
    updatedAt: raw.updated_at || "",
    region: raw.region || "",
    hiveColor: raw.hive_color || raw.color || "",
    field: raw.field || "",
    minimumBees: privateServerNumber(requirements.minimum_bees ?? raw.minimum_bees),
    minimumLevel: privateServerNumber(requirements.minimum_level ?? raw.minimum_level),
    minimumSprinkler: requirements.minimum_sprinkler || raw.minimum_sprinkler || "",
    popStarNeeded: privateServerBoolean(requirements.pop_star_needed ?? raw.pop_star_needed ?? raw.pop_star),
    fuzzyBees: privateServerNumber(giftedBees.fuzzy ?? giftedBees.fuzzy_bees ?? raw.fuzzy_bees ?? privateServerRequiredBeeCount(requiredBees, "fuzzy bee")),
    tadpoles: privateServerNumber(giftedBees.tadpole ?? giftedBees.tadpoles ?? raw.tadpoles ?? privateServerRequiredBeeCount(requiredBees, "tadpole bee")),
    buoyants: privateServerNumber(giftedBees.buoyant ?? giftedBees.buoyants ?? raw.buoyants ?? privateServerRequiredBeeCount(requiredBees, "buoyant bee")),
    giftedOther: privateServerArray(giftedBees.other || raw.gifted_other),
    ownerTakesSlots: slots.owner_takes || raw.owner_takes_slots || "",
    availableSlots: privateServerNumber(slots.available ?? raw.available_slots, null),
    allowedTasks: privateServerArray(tasks.allowed || raw.allowed_tasks),
    neededTasks: privateServerArray(tasks.needed || tasks.required || raw.needed_tasks || raw.required_tasks),
    restartsEveryHours: raw.restarts_every_hours ?? raw.restart_hours ?? "",
    serverHas: privateServerArray(raw.server_has),
    notes: raw.notes || "",
  };
}

function getPrivateServerDataset(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.servers)) return payload.servers;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

function getPrivateServerFilters() {
  return {
    field: document.getElementById("private-server-field")?.value || "",
    color: document.getElementById("private-server-color")?.value || "",
    region: document.getElementById("private-server-region")?.value || "",
    sprinkler: document.getElementById("private-server-sprinkler")?.value || "",
    popStar: document.getElementById("private-server-pop-star")?.value || "",
    allowedTask: document.getElementById("private-server-allowed-task")?.value || "",
    neededTask: document.getElementById("private-server-needed-task")?.value || "",
    maxMinimumBees: privateServerNumber(document.getElementById("private-server-min-bees")?.value, null),
    maxMinimumLevel: privateServerNumber(document.getElementById("private-server-min-level")?.value, null),
    minTadpoles: privateServerNumber(document.getElementById("private-server-min-tadpoles")?.value),
    minBuoyants: privateServerNumber(document.getElementById("private-server-min-buoyants")?.value),
    sort: document.getElementById("private-server-sort")?.value || "newest",
  };
}

function filterPrivateServers(server) {
  const filters = getPrivateServerFilters();
  if (filters.field && server.field !== filters.field) return false;
  if (filters.color && server.hiveColor !== filters.color) return false;
  if (filters.region && server.region !== filters.region) return false;
  if (filters.sprinkler && server.minimumSprinkler !== filters.sprinkler) return false;
  if (filters.popStar === "yes" && !server.popStarNeeded) return false;
  if (filters.popStar === "no" && server.popStarNeeded) return false;
  if (filters.allowedTask && !server.allowedTasks.includes(filters.allowedTask)) return false;
  if (filters.neededTask && !server.neededTasks.includes(filters.neededTask)) return false;
  if (filters.maxMinimumBees !== null && server.minimumBees > filters.maxMinimumBees) return false;
  if (filters.maxMinimumLevel !== null && server.minimumLevel > filters.maxMinimumLevel) return false;
  if (server.tadpoles < filters.minTadpoles) return false;
  if (server.buoyants < filters.minBuoyants) return false;
  return true;
}

function sortPrivateServers(servers) {
  const sort = getPrivateServerFilters().sort;
  const byText = (key) => (a, b) => String(a[key]).localeCompare(String(b[key]));
  const byNumber = (key) => (a, b) => a[key] - b[key];
  const byNewest = (a, b) => new Date(b.createdAt || 0) - new Date(a.createdAt || 0);

  const sorters = {
    newest: byNewest,
    field: byText("field"),
    color: byText("hiveColor"),
    minimum_bees: byNumber("minimumBees"),
    minimum_level: byNumber("minimumLevel"),
    tadpoles: (a, b) => b.tadpoles - a.tadpoles,
    buoyants: (a, b) => b.buoyants - a.buoyants,
  };

  return [...servers].sort(sorters[sort] || byNewest);
}

function renderPrivateServerOptions() {
  const optionTargets = [
    ["private-server-field", "field", PRIVATE_SERVER_OPTION_DEFAULTS.field],
    ["private-server-color", "hiveColor", PRIVATE_SERVER_OPTION_DEFAULTS.hiveColor],
    ["private-server-region", "region", PRIVATE_SERVER_OPTION_DEFAULTS.region],
    ["private-server-sprinkler", "minimumSprinkler", PRIVATE_SERVER_OPTION_DEFAULTS.minimumSprinkler],
  ];

  optionTargets.forEach(([id, key, defaults]) => {
    const select = document.getElementById(id);
    if (!select) return;
    const currentValue = select.value;
    const values = [
      ...new Set([
        ...(defaults || []),
        ...privateServerEntries.map((server) => server[key]).filter(Boolean),
      ]),
    ].sort((a, b) => a.localeCompare(b));
    select.innerHTML = `<option value="">Any</option>` + values
      .filter((value) => privateServerOptionValue(value))
      .map((value) => `<option value="${privateServerEscape(privateServerOptionValue(value))}">${privateServerEscape(value)}</option>`)
      .join("");
    if (values.map(privateServerOptionValue).includes(currentValue)) select.value = currentValue;
  });

  [
    ["private-server-allowed-task", "allowedTasks", PRIVATE_SERVER_OPTION_DEFAULTS.allowedTasks],
    ["private-server-needed-task", "neededTasks", PRIVATE_SERVER_OPTION_DEFAULTS.neededTasks],
  ].forEach(([id, key, defaults]) => {
    const select = document.getElementById(id);
    if (!select) return;
    const currentValue = select.value;
    const values = [
      ...new Set([
        ...(defaults || []),
        ...privateServerEntries.flatMap((server) => server[key] || []),
      ]),
    ].sort((a, b) => a.localeCompare(b));
    select.innerHTML = `<option value="">Any</option>` + values
      .map((value) => `<option value="${privateServerEscape(value)}">${privateServerEscape(value)}</option>`)
      .join("");
    if (values.includes(currentValue)) select.value = currentValue;
  });
}

function renderPrivateServerResults() {
  const results = document.getElementById("private-server-results");
  const count = document.getElementById("private-server-count");
  const pagination = document.getElementById("private-server-pagination");
  if (!results) return;

  const filteredServers = sortPrivateServers(privateServerEntries.filter(filterPrivateServers));
  const pageSize = PRIVATE_SERVER_PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(filteredServers.length / pageSize));
  privateServerPage = Math.min(Math.max(1, privateServerPage), totalPages);
  const pageStart = (privateServerPage - 1) * pageSize;
  const pageServers = filteredServers.slice(pageStart, pageStart + pageSize);

  if (count) {
    count.textContent = `${filteredServers.length} server${filteredServers.length === 1 ? "" : "s"} - Page ${privateServerPage} of ${totalPages}`;
  }

  if (!filteredServers.length) {
    results.innerHTML = `<div class="private-server-empty">No private servers match these filters.</div>`;
    if (pagination) pagination.innerHTML = "";
    return;
  }

  results.innerHTML = pageServers
    .map((server) => {
      const joinButton = server.link
        ? `<a class="private-server-card-button private-server-join" href="${privateServerEscape(server.link)}" target="_blank" rel="noopener noreferrer">Join</a>`
        : `<span class="private-server-missing-link">No link</span>`;
      const setButton = server.link
        ? `<button class="private-server-card-button private-server-set" onclick="setPrivateServerLink('${encodeURIComponent(server.id)}')">Set as Private Server</button>`
        : "";
      return `
        <article class="private-server-card">
          <div class="private-server-card-header">
            <div>
              <h3>${privateServerEscape(server.field || "Any Field")} ${server.hiveColor ? `- ${privateServerEscape(server.hiveColor)}` : ""}</h3>
              <p>${server.region ? privateServerEscape(server.region) : "Any Region"}</p>
            </div>
            <div class="private-server-card-actions">
              ${joinButton}
              ${setButton}
            </div>
          </div>
          <div class="private-server-requirements">
            <span>Bees: ${server.minimumBees || "N/A"}+</span>
            <span>Level: ${server.minimumLevel || "N/A"}+</span>
            <span>Fuzzy: ${server.fuzzyBees}</span>
            <span>Tadpoles: ${server.tadpoles}</span>
            <span>Buoyants: ${server.buoyants}</span>
            <span>Sprinkler: ${privateServerEscape(server.minimumSprinkler || "N/A")}</span>
            <span>Pop Star: ${server.popStarNeeded ? "Yes" : "No"}</span>
          </div>
          <div class="private-server-details">
            <p><strong>Allowed:</strong> ${privateServerFormatList(server.allowedTasks, "Any")}</p>
            <p><strong>Needed:</strong> ${privateServerFormatList(server.neededTasks)}</p>
            <p><strong>Has:</strong> ${privateServerFormatList(server.serverHas)}</p>
            <p><strong>Owner slots:</strong> ${privateServerEscape(server.ownerTakesSlots || "N/A")}</p>
            <p><strong>Restarts:</strong> ${privateServerEscape(server.restartsEveryHours || "N/A")}${server.restartsEveryHours && !["never", "n/a"].includes(String(server.restartsEveryHours).toLowerCase()) ? " hours" : ""}</p>
          </div>
          ${server.messageText || server.notes ? `<div class="private-server-discord-text">${privateServerEscape(server.messageText || server.notes)}</div>` : ""}
          <div class="private-server-meta">
            <span>${privateServerEscape(server.author || "Unknown poster")}</span>
            <span>${privateServerFormatDate(server.createdAt)}</span>
          </div>
        </article>
      `;
    })
    .join("");

  if (pagination) {
    pagination.innerHTML = `
      <button class="private-server-page-button" onclick="changePrivateServerPage(-1)" ${privateServerPage <= 1 ? "disabled" : ""}>Previous</button>
      <span>${pageStart + 1}-${Math.min(pageStart + pageSize, filteredServers.length)} of ${filteredServers.length}</span>
      <button class="private-server-page-button" onclick="changePrivateServerPage(1)" ${privateServerPage >= totalPages ? "disabled" : ""}>Next</button>
    `;
  }
}

function changePrivateServerPage(delta) {
  privateServerPage += delta;
  renderPrivateServerResults();
}

async function setPrivateServerLink(serverId) {
  const decodedServerId = decodeURIComponent(serverId);
  const server = privateServerEntries.find((entry) => entry.id === decodedServerId);
  const status = document.getElementById("private-server-status");

  if (!server?.link) {
    if (status) status.textContent = "This server does not have a link.";
    return;
  }

  if (!window.eel || typeof eel.saveGeneralSetting !== "function") {
    if (status) status.textContent = "Settings are not available.";
    return;
  }

  try {
    await eel.saveGeneralSetting("private_server_link", server.link)();
    const input = document.getElementById("private_server_link");
    if (input) input.value = server.link;
    if (status) status.textContent = "Private server link updated.";
  } catch (error) {
    console.error("Failed to set private server link:", error);
    if (status) status.textContent = "Failed to update private server link.";
  }
}

async function refreshPrivateServers() {
  const status = document.getElementById("private-server-status");
  const refreshButton = document.getElementById("private-server-refresh");

  if (status) status.textContent = "Loading...";
  if (refreshButton) {
    refreshButton.classList.add("active");
    refreshButton.textContent = "Loading";
  }

  try {
    const response = await fetch(PRIVATE_SERVER_API_ENDPOINT, {
      cache: "no-store",
      headers: PRIVATE_SERVER_API_HEADERS,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    privateServerEntries = getPrivateServerDataset(payload).map(normalizePrivateServer);
    privateServerPage = 1;
    renderPrivateServerOptions();
    renderPrivateServerResults();
    if (status) status.textContent = `Loaded ${privateServerEntries.length} server${privateServerEntries.length === 1 ? "" : "s"}`;
  } catch (error) {
    privateServerEntries = [];
    renderPrivateServerOptions();
    renderPrivateServerResults();
    if (status) status.textContent = `Failed to load server list: ${error.message}`;
    console.error("Failed to load private servers:", error);
  } finally {
    if (refreshButton) {
      refreshButton.classList.remove("active");
      refreshButton.textContent = "Refresh";
    }
  }
}

function initializePrivateServerFinder() {
  [
    "private-server-field",
    "private-server-color",
    "private-server-region",
    "private-server-sprinkler",
    "private-server-pop-star",
    "private-server-allowed-task",
    "private-server-needed-task",
    "private-server-min-bees",
    "private-server-min-level",
    "private-server-min-tadpoles",
    "private-server-min-buoyants",
    "private-server-sort",
  ].forEach((id) => {
    const input = document.getElementById(id);
    if (!input) return;
    const updateResults = () => {
      privateServerPage = 1;
      renderPrivateServerResults();
    };
    input.addEventListener("input", updateResults);
    input.addEventListener("change", updateResults);
  });

  refreshPrivateServers();
}

function switchHotbarBuffToolSlot(slot) {
  Array.from(document.getElementsByClassName("hotbar-buff-tool-slot")).forEach((button) => {
    button.classList.remove("active");
  });
  Array.from(document.getElementsByClassName("hotbar-buff-tool-panel")).forEach((panel) => {
    panel.classList.remove("active");
  });

  const button = document.getElementById(`hotbar-buff-tool-slot-${slot}`);
  const panel = document.getElementById(`hotbar-buff-tool-slot-${slot}-panel`);
  if (!button || !panel) return;

  button.classList.add("active");
  panel.classList.add("active");
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
  initializePrivateServerFinder();
  initializeAutoGiftedBasicBeeTool();
  initializeHotbarBuffTool();

  switchToolsTab(document.getElementById("tools-autoclicker"));
}

$("#tools-placeholder")
  .load("../htmlImports/tabs/tools.html", loadTools)
  .on("click", ".tools-tab-item", (event) => switchToolsTab(event.currentTarget));
