/*
=============================================
Collect Tab
=============================================
*/


function clearBlenderData(ele){
    if (ele.classList.contains("active")) return
    eel.clearBlender()
    ele.classList.add("active")
    setTimeout(() => {
        ele.classList.remove("active")
      }, 700)
}

function switchCollectTab(target){
    setActiveSubtab("activeCollectSubtab", target.id)
    Array.from(document.getElementsByClassName("collect-tab-item")).forEach(x => {
        x.classList.remove("active")
        document.getElementById(`${x.id}-tab`).style.display = "none"
    })

    target.classList.add("active")
    const tab = document.getElementById(`${target.id}-tab`)
    tab.style.display = "block"
    tab.scrollTo(0, 0)
}

const sproutAITokenPriority = [
    "Token Link",
    "Coconut",
    "Pineapple",
    "Blueberry",
    "Strawberry",
    "Sunflower Seed",
    "Jelly Bean",
    "Snowflake",
    "Beesmas Cheer Token",
    "Festive Blessing Token",
    "Treat",
    "Honey Token",
]

const sproutAIFieldTokens = {
    sunflower: ["Sunflower Seed"],
    pineapple: ["Pineapple"],
    strawberry: ["Strawberry"],
    coconut: ["Coconut"],
    "blue flower": ["Blueberry"],
    bamboo: ["Blueberry"],
    "pine tree": ["Blueberry"],
    stump: ["Blueberry"],
    mushroom: ["Strawberry"],
    rose: ["Strawberry"],
    pepper: ["Strawberry"],
}

function parseSproutAITokenList(value) {
    if (!value) return []
    return value.split(",").map((token) => token.trim()).filter(Boolean)
}

function isHiddenSproutAIToken(token) {
    return token === "Bloom" || token.startsWith("Duped ")
}

function getAllSproutAITokenNames() {
    if (typeof fuzzyAITokenNames !== "undefined" && Array.isArray(fuzzyAITokenNames)) {
        return fuzzyAITokenNames
    }
    return sproutAITokenPriority
}

function getSproutAITokenNames() {
    return getAllSproutAITokenNames().filter((token) => !isHiddenSproutAIToken(token))
}

function getSproutAITokenState() {
    const tokenNames = getSproutAITokenNames()
    const preferred = parseSproutAITokenList(document.getElementById("sprouts_preferred_tokens")?.value || "")
    const ignored = new Set(parseSproutAITokenList(document.getElementById("sprouts_ignored_tokens")?.value || ""))
    const ordered = []
    preferred.forEach((token) => {
        if (tokenNames.includes(token) && !ordered.includes(token)) ordered.push(token)
    })
    tokenNames.forEach((token) => {
        if (!ordered.includes(token)) ordered.push(token)
    })
    return ordered.map((token) => ({
        name: token,
        enabled: !ignored.has(token),
    }))
}

function renderSproutAITokenList() {
    const container = document.getElementById("sprout-ai-token-list")
    if (!container) return
    const tokenState = getSproutAITokenState()
    container.innerHTML = tokenState.map((token, index) => `
        <div class="sprout-ai-token-row" data-token="${token.name}" draggable="true">
            <label>
                <span class="sprout-ai-token-drag-handle" title="Drag to reorder">::</span>
                <input type="checkbox" class="sprout-ai-token-enabled" ${token.enabled ? "checked" : ""}>
                <span>${index + 1}. ${token.name}</span>
            </label>
            <div>
                <button class="import-export-button sprout-ai-token-up" ${index === 0 ? "disabled" : ""}>Up</button>
                <button class="import-export-button sprout-ai-token-down" ${index === tokenState.length - 1 ? "disabled" : ""}>Down</button>
            </div>
        </div>
    `).join("")
}

function refreshSproutAITokenRows() {
    const rows = Array.from(document.querySelectorAll(".sprout-ai-token-row"))
    rows.forEach((row, index) => {
        const tokenLabel = row.querySelector("label span:last-child")
        if (tokenLabel) tokenLabel.textContent = `${index + 1}. ${row.dataset.token}`
        const upButton = row.querySelector(".sprout-ai-token-up")
        const downButton = row.querySelector(".sprout-ai-token-down")
        if (upButton) upButton.disabled = index === 0
        if (downButton) downButton.disabled = index === rows.length - 1
    })
}

function getSproutAITokenDragAfterElement(container, y) {
    const rows = Array.from(container.querySelectorAll(".sprout-ai-token-row:not(.dragging)"))
    return rows.reduce((closest, row) => {
        const box = row.getBoundingClientRect()
        const offset = y - box.top - box.height / 2
        if (offset < 0 && offset > closest.offset) return { offset, element: row }
        return closest
    }, { offset: Number.NEGATIVE_INFINITY, element: null }).element
}

function getSelectedSproutField() {
    const fieldDropdown = document.getElementById("sprouts_field")
    return fieldDropdown ? getDropdownValue(fieldDropdown) : "sunflower"
}

function getSelectedSproutAIModel() {
    const modelDropdown = document.getElementById("sprouts_ai_model")
    return String(modelDropdown ? getDropdownValue(modelDropdown) : "standard").trim().toLowerCase()
}

function refreshSproutAIModelOptions() {
    const tokenButton = document.getElementById("configure-sprout-ai-tokens-button")
    const tokenPriorityRow = tokenButton?.closest("form")
    if (!tokenPriorityRow) return
    tokenPriorityRow.style.display = getSelectedSproutAIModel() === "standard" ? "flex" : "none"
}

function applySproutAITokenPreset(presetName) {
    const allTokenNames = getAllSproutAITokenNames()
    const tokenNames = allTokenNames.filter((token) => !isHiddenSproutAIToken(token))
    let preferred = []
    if (presetName === "all") {
        preferred = sproutAITokenPriority.filter((token) => tokenNames.includes(token))
    } else if (presetName === "field") {
        const fieldTokens = sproutAIFieldTokens[getSelectedSproutField()] || []
        preferred = [...fieldTokens, ...sproutAITokenPriority].filter((token, index, arr) => tokenNames.includes(token) && arr.indexOf(token) === index)
    }
    preferred = preferred.filter((token, index, arr) => arr.indexOf(token) === index)
    const ignored = allTokenNames.filter((token) => isHiddenSproutAIToken(token) || !preferred.includes(token))
    document.getElementById("sprouts_preferred_tokens").value = preferred.join(",")
    document.getElementById("sprouts_ignored_tokens").value = ignored.join(",")
    renderSproutAITokenList()
}

async function saveSproutAITokenPopup() {
    const rows = Array.from(document.querySelectorAll(".sprout-ai-token-row"))
    const preferred = []
    const ignored = getAllSproutAITokenNames().filter(isHiddenSproutAIToken)
    rows.forEach((row) => {
        const token = row.dataset.token
        const enabled = row.querySelector(".sprout-ai-token-enabled")?.checked
        if (enabled) preferred.push(token)
        else if (!ignored.includes(token)) ignored.push(token)
    })
    const preferredInput = document.getElementById("sprouts_preferred_tokens")
    const ignoredInput = document.getElementById("sprouts_ignored_tokens")
    preferredInput.value = preferred.join(",")
    ignoredInput.value = ignored.join(",")
    await eel.saveProfileSetting("sprouts_preferred_tokens", preferredInput.value)()
    await eel.saveProfileSetting("sprouts_ignored_tokens", ignoredInput.value)()
    closeSproutAITokenPopup()
}

function openSproutAITokenPopup() {
    renderSproutAITokenList()
    const modal = document.getElementById("sprout-ai-token-modal")
    if (modal) modal.style.display = "flex"
}

function closeSproutAITokenPopup() {
    const modal = document.getElementById("sprout-ai-token-modal")
    if (modal) modal.style.display = "none"
}

async function loadCollect(){
    const settings = await loadAllSettings()
    loadInputs(settings)
    refreshSproutAIModelOptions()
    switchCollectTab(document.getElementById(getActiveSubtab("activeCollectSubtab", "collect-dispensers")))
}

$("#collect-placeholder")
.load("../htmlImports/tabs/collect.html", loadCollect)
 .on("click", ".collect-tab-item", (event) => switchCollectTab(event.currentTarget))
 .on("click", "#cancel-sprout-ai-tokens-button", closeSproutAITokenPopup)
 .on("click", "#save-sprout-ai-tokens-button", saveSproutAITokenPopup)
 .on("click", ".sprout-ai-token-preset", (event) => {
    event.preventDefault()
    applySproutAITokenPreset(event.currentTarget.dataset.preset)
 })
 .on("click", ".sprout-ai-token-up", (event) => {
    const row = event.currentTarget.closest(".sprout-ai-token-row")
    if (row?.previousElementSibling) {
        row.parentElement.insertBefore(row, row.previousElementSibling)
        refreshSproutAITokenRows()
    }
 })
 .on("click", ".sprout-ai-token-down", (event) => {
    const row = event.currentTarget.closest(".sprout-ai-token-row")
    if (row?.nextElementSibling) {
        row.parentElement.insertBefore(row.nextElementSibling, row)
        refreshSproutAITokenRows()
    }
 })
 .on("dragstart", ".sprout-ai-token-row", (event) => {
    event.currentTarget.classList.add("dragging")
 })
 .on("dragend", ".sprout-ai-token-row", (event) => {
    event.currentTarget.classList.remove("dragging")
    refreshSproutAITokenRows()
 })
 .on("dragover", "#sprout-ai-token-list", (event) => {
    event.preventDefault()
    const dragging = document.querySelector(".sprout-ai-token-row.dragging")
    if (!dragging) return
    const afterElement = getSproutAITokenDragAfterElement(event.currentTarget, event.originalEvent.clientY)
    if (afterElement == null) event.currentTarget.appendChild(dragging)
    else event.currentTarget.insertBefore(dragging, afterElement)
 })
