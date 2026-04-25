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
const TICKET_CALC_DEFAULT_NEXT_PRICE = 100000;
const TICKET_CALC_MAX_TICKETS = 100000;
const TICKET_CALC_PRESETS = [10, 100, 500];

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

function getTicketCalcElements() {
  return {
    nextPrice: document.getElementById("ticket-calc-next-price"),
    nextPriceUnit: document.getElementById("ticket-calc-next-price-unit"),
    customAmount: document.getElementById("ticket-calc-custom-amount"),
    budget: document.getElementById("ticket-calc-budget"),
    budgetUnit: document.getElementById("ticket-calc-budget-unit"),
    warning: document.getElementById("ticket-calc-warning"),
    presetBreakdown: document.getElementById("ticket-calc-presets-breakdown"),
  };
}

function normalizeTicketPrice(value, unit) {
  const multiplier = Number(unit) || 1;
  let price = Math.round(((Number(value) || 0) * multiplier) / 1000) * 1000;
  if (price < TICKET_CALC_DEFAULT_NEXT_PRICE) price = TICKET_CALC_DEFAULT_NEXT_PRICE;
  return price;
}

function getTicketsBoughtFromNextPrice(nextPrice) {
  if (nextPrice === TICKET_CALC_DEFAULT_NEXT_PRICE) return 0;
  if (nextPrice < 102000) return 1;

  const scaledPrice = nextPrice / 1000 - 100;
  const inverseExponent = nextPrice <= 1824000 ? 5 / 6 : 10 / 17;
  return Math.floor(Math.pow(scaledPrice, inverseExponent)) + 1;
}

function getTicketPriceAfterBought(ticketsBought) {
  if (ticketsBought <= 0) return TICKET_CALC_DEFAULT_NEXT_PRICE;
  if (ticketsBought === 1) return 101000;

  const exponent = ticketsBought < 499 ? 6 / 5 : 17 / 10;
  return Math.ceil(Math.pow(ticketsBought, exponent) + 99) * 1000;
}

function calculateTicketPurchase(nextPrice, ticketCount) {
  const ticketsToBuy = Math.max(0, Math.min(TICKET_CALC_MAX_TICKETS, Math.floor(Number(ticketCount) || 0)));
  const ticketsAlreadyBought = getTicketsBoughtFromNextPrice(nextPrice);
  let totalCost = 0;
  let finalTicketPrice = 0;

  for (let index = 0; index < ticketsToBuy; index += 1) {
    const ticketPrice = index === 0 ? nextPrice : getTicketPriceAfterBought(ticketsAlreadyBought + index);
    totalCost += ticketPrice;
    finalTicketPrice = ticketPrice;
  }

  return {
    ticketsAlreadyBought,
    ticketsToBuy,
    totalCost,
    averagePrice: ticketsToBuy > 0 ? totalCost / ticketsToBuy : 0,
    finalTicketPrice,
    nextPriceAfterPurchase: getTicketPriceAfterBought(ticketsAlreadyBought + ticketsToBuy),
  };
}

function calculateTicketsForBudget(nextPrice, budget) {
  const ticketsAlreadyBought = getTicketsBoughtFromNextPrice(nextPrice);
  const honeyBudget = Math.max(0, Number(budget) || 0);
  let totalCost = 0;
  let tickets = 0;

  while (tickets < TICKET_CALC_MAX_TICKETS) {
    const ticketPrice = tickets === 0 ? nextPrice : getTicketPriceAfterBought(ticketsAlreadyBought + tickets);
    if (totalCost + ticketPrice > honeyBudget) break;
    totalCost += ticketPrice;
    tickets += 1;
  }

  return { tickets, totalCost };
}

function updateTicketPriceCalculator() {
  const el = getTicketCalcElements();
  if (!el.nextPrice || !el.nextPriceUnit || !el.customAmount || !el.budget || !el.budgetUnit || !el.presetBreakdown) return;

  const rawNextPrice = Number(el.nextPrice.value);
  const nextPrice = normalizeTicketPrice(el.nextPrice.value, el.nextPriceUnit.value);
  const budget = Math.max(0, (Number(el.budget.value) || 0) * (Number(el.budgetUnit.value) || 1));
  let customAmount = Math.floor(Number(el.customAmount.value) || 1);

  if (customAmount < 1) customAmount = 1;
  if (customAmount > TICKET_CALC_MAX_TICKETS) customAmount = TICKET_CALC_MAX_TICKETS;
  el.customAmount.value = customAmount;

  if (el.warning) {
    const rawWholePrice = rawNextPrice * (Number(el.nextPriceUnit.value) || 1);
    const isRounded = Number.isFinite(rawWholePrice) && rawWholePrice > 0 && rawWholePrice !== nextPrice;
    el.warning.style.display = isRounded ? "block" : "none";
    el.warning.textContent = "Ticket prices below 100K are raised to 100K, and prices are rounded to the nearest 1,000 honey.";
  }

  const budgetPurchase = calculateTicketsForBudget(nextPrice, budget);

  const rows = [...TICKET_CALC_PRESETS, customAmount].filter(
    (amount, index, amounts) => amounts.indexOf(amount) === index
  );

  const presetRows = rows.map((amount) => {
    const preset = calculateTicketPurchase(nextPrice, amount);
    const label = amount === customAmount && !TICKET_CALC_PRESETS.includes(amount) ? `${formatWholeNumber(amount)} Tickets (Custom)` : `${formatWholeNumber(amount)} Tickets`;
    return `
      <tr>
        <td>${label}</td>
        <td>${formatCompactHoney(preset.totalCost)}</td>
      </tr>
    `;
  });

  presetRows.push(`
    <tr>
      <td>Max (${formatWholeNumber(budgetPurchase.tickets)} Tickets)</td>
      <td>${formatCompactHoney(budgetPurchase.totalCost)}</td>
    </tr>
  `);

  el.presetBreakdown.innerHTML = presetRows.join("");
}

function initializeTicketPriceCalculator() {
  const el = getTicketCalcElements();
  if (!el.nextPrice || !el.nextPriceUnit || !el.customAmount || !el.budget || !el.budgetUnit) return;

  if (!el.nextPrice.value) el.nextPrice.value = "100";
  if (!el.nextPriceUnit.value) el.nextPriceUnit.value = "1000000";
  if (!el.customAmount.value) el.customAmount.value = "1";
  if (!el.budget.value) el.budget.value = "0";
  if (!el.budgetUnit.value) el.budgetUnit.value = "1000000";

  [el.nextPrice, el.nextPriceUnit, el.customAmount, el.budget, el.budgetUnit].forEach((input) => {
    input.addEventListener("change", updateTicketPriceCalculator);
    input.addEventListener("input", updateTicketPriceCalculator);
  });

  updateTicketPriceCalculator();
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
  setActiveSubtab("activeToolsSubtab", target.id);
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
  initializeTicketPriceCalculator();
  initializeAutoGiftedBasicBeeTool();
  initializeHotbarBuffTool();

  switchToolsTab(
    document.getElementById(getActiveSubtab("activeToolsSubtab", "tools-autoclicker"))
  );
}

$("#tools-placeholder")
  .load("../htmlImports/tabs/tools.html", loadTools)
  .on("click", ".tools-tab-item", (event) => switchToolsTab(event.currentTarget));
