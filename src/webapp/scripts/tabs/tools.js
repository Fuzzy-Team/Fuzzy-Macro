let autoClickerTimer = null;
const AUTOCLICKER_MIN_INTERVAL = 10;
const AUTOCLICKER_DEFAULT_INTERVAL = 100;

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
  switchToolsTab(document.getElementById("tools-autoclicker"));
}

$("#tools-placeholder")
  .load("../htmlImports/tabs/tools.html", loadTools)
  .on("click", ".tools-tab-item", (event) => switchToolsTab(event.currentTarget));
