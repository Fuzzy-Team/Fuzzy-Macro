/*
=============================================
Collect Tab
=============================================
*/


function clearBlenderData(ele){
    flashButton(ele, () => eel.clearBlender())
}

// the - / + buttons beside a blender number box
function stepBlenderInput(id, delta, min){
    const box = document.getElementById(id)
    box.value = Math.max(min, (parseInt(box.value, 10) || 0) + delta)
    box.dispatchEvent(new Event("change"))
}

const BLENDER_SLOT_KEYS = ["item", "quantity", "quantity_max", "repeat", "repeat_inf"]
const BLENDER_SLOT_DEFAULT = ["none", 1, false, 1, false]
const BLENDER_MAX_SLOTS = 20 // BLENDER_ITEM_SLOTS in settings_defaults.py

function readBlenderSlot(slot){
    return BLENDER_SLOT_KEYS.map((key) => getInputValue(`blender_${key}_${slot.dataset.slot}`))
}

// rows[i] are the values for slot i + 1. Saved along with how many slots are in use.
// order, when slots moved, is each new position's old slot number (see moveBlenderSlots in gui.py).
function saveBlenderSlots(rows, count, order){
    const next = { blender_slots: count }
    rows.forEach((row, i) => BLENDER_SLOT_KEYS.forEach((key, j) => next[`blender_${key}_${i + 1}`] = row[j]))
    loadInputs(next, "profile")
    if (order) eel.moveBlenderSlots(order)
}

// numbers, screen reader labels, and the limits on removing and adding
function refreshBlenderSlots(){
    const slots = document.querySelectorAll(".blender-slot")
    slots.forEach((slot, i) => {
        const [amount, repeat] = slot.querySelectorAll(".textbox")
        slot.querySelector(".blender-slot-num").textContent = i + 1
        slot.querySelector(".blender-slot-num").setAttribute("aria-label", `Move slot ${i + 1}`)
        amount.setAttribute("aria-label", `Slot ${i + 1} amount`)
        repeat.setAttribute("aria-label", `Slot ${i + 1} repeat count`)
        const remove = slot.querySelector(".blender-slot-remove")
        remove.setAttribute("aria-label", `Remove slot ${i + 1}`)
        remove.disabled = slots.length === 1
    })
    document.querySelector(".blender-add").disabled = slots.length >= BLENDER_MAX_SLOTS
}

function setBlenderSlots(count){
    document.querySelector(".blender-queue").innerHTML = Array.from({ length: count }, (_, i) => blenderSlotHTML(i + 1)).join("")
    refreshBlenderSlots()
}

function addBlenderSlot(){
    const queue = document.querySelector(".blender-queue")
    const rows = Array.from(queue.children).map(readBlenderSlot)
    if (rows.length >= BLENDER_MAX_SLOTS) return
    rows.push(BLENDER_SLOT_DEFAULT)
    queue.insertAdjacentHTML("beforeend", blenderSlotHTML(rows.length))
    refreshBlenderSlots()
    queue.lastElementChild.scrollIntoView({ block: "nearest" })
    saveBlenderSlots(rows, rows.length)
}

function removeBlenderSlot(button){
    const slots = Array.from(document.querySelectorAll(".blender-slot"))
    const rows = slots.map(readBlenderSlot)
    rows.splice(slots.indexOf(button.closest(".blender-slot")), 1)
    rows.push(BLENDER_SLOT_DEFAULT) // the freed last slot goes back to its defaults
    const order = slots.map((slot) => Number(slot.dataset.slot)).filter((n) => n !== Number(button.closest(".blender-slot").dataset.slot))
    slots.pop().remove()
    refreshBlenderSlots()
    saveBlenderSlots(rows, slots.length, order)
}

// Slots are dragged around in the page, but each keeps its own setting ids. Once the order
// is final, put the cards back and write each slot's settings into its new position.
function commitBlenderOrder(save){
    const queue = document.querySelector(".blender-queue")
    const slots = Array.from(queue.children)
    const rows = slots.map(readBlenderSlot)
    const order = slots.map((slot) => Number(slot.dataset.slot))
    slots.sort((a, b) => a.dataset.slot - b.dataset.slot).forEach((slot) => queue.appendChild(slot))
    refreshBlenderSlots()
    if (save) saveBlenderSlots(rows, rows.length, order)
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
    const modelName = getSelectedSproutTokenModelName()
    if (typeof fuzzyAITokenNamesByModel !== "undefined" && fuzzyAITokenNamesByModel[modelName]) {
        return fuzzyAITokenNamesByModel[modelName]
    }
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

// the element a dragged row should go in front of, or null to go last
function getDragAfterElement(container, y, rowSelector) {
    const rows = Array.from(container.querySelectorAll(rowSelector))
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

function normalizeSproutAIModel(value) {
    return String(value || "standard").trim().toLowerCase().replace(/\s+/g, "_").replace(/-/g, "_")
}

function getSelectedSproutTokenModelName() {
    const model = normalizeSproutAIModel(getSelectedSproutAIModel())
    if (model === "token_light" || model === "loot_light" || model === "light") return "Light"
    if (model === "token_mini" || model === "loot_mini" || model === "mini") return "Mini"
    return "Standard"
}

function refreshSproutAIModelOptions() {
    const tokenButton = document.getElementById("configure-sprout-ai-tokens-button")
    const tokenPriorityRow = tokenButton?.closest("form")
    if (!tokenPriorityRow) return
    const model = normalizeSproutAIModel(getSelectedSproutAIModel())
    const isLootModel = model === "loot_light" || model === "loot_mini" || model === "light" || model === "mini"
    tokenPriorityRow.style.display = isLootModel ? "none" : "flex"
}

function applySproutAITokenPreset(presetName) {
    const allTokenNames = getAllSproutAITokenNames()
    const tokenNames = allTokenNames.filter((token) => !isHiddenSproutAIToken(token))
    let preferred = []
    if (presetName === "all") {
        preferred = tokenNames
    } else if (presetName === "field") {
        const fieldTokens = sproutAIFieldTokens[getSelectedSproutField()] || []
        preferred = [...fieldTokens, ...tokenNames].filter((token, index, arr) => tokenNames.includes(token) && arr.indexOf(token) === index)
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

async function openSproutAITokenPopup() {
    // Preset buttons write into the hidden token inputs, so load the saved lists
    // again: after Cancel the next open must not show the discarded preset.
    try {
        const settings = await loadAllSettings()
        const preferredInput = document.getElementById("sprouts_preferred_tokens")
        const ignoredInput = document.getElementById("sprouts_ignored_tokens")
        if (preferredInput && typeof settings.sprouts_preferred_tokens === "string") {
            preferredInput.value = settings.sprouts_preferred_tokens
        }
        if (ignoredInput && typeof settings.sprouts_ignored_tokens === "string") {
            ignoredInput.value = settings.sprouts_ignored_tokens
        }
    } catch (error) {
        console.error("Failed to load sprout token settings:", error)
    }
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
    setBlenderSlots(settings.blender_slots)
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
 .on("dragstart", ".blender-slot-num", (event) => {
    const slot = event.currentTarget.closest(".blender-slot")
    const box = slot.getBoundingClientRect()
    event.originalEvent.dataTransfer.effectAllowed = "move"
    event.originalEvent.dataTransfer.setDragImage(slot, event.originalEvent.clientX - box.left, event.originalEvent.clientY - box.top)
    setTimeout(() => slot.classList.add("dragging"))
 })
 .on("dragend", ".blender-slot-num", (event) => {
    event.currentTarget.closest(".blender-slot").classList.remove("dragging")
    // dropped outside the list, or Esc: put everything back
    commitBlenderOrder(event.originalEvent.dataTransfer.dropEffect !== "none")
 })
 .on("dragover", ".blender-queue", (event) => {
    event.preventDefault()
    const dragging = document.querySelector(".blender-slot.dragging")
    if (!dragging) return
    const afterElement = getDragAfterElement(event.currentTarget, event.originalEvent.clientY, ".blender-slot:not(.dragging)")
    if (afterElement == null) event.currentTarget.appendChild(dragging)
    else event.currentTarget.insertBefore(dragging, afterElement)
    refreshBlenderSlots()
 })
 .on("keydown", ".blender-slot-num", (event) => {
    const step = { ArrowUp: -1, ArrowDown: 1 }[event.key]
    if (!step) return
    event.preventDefault()
    const slot = event.currentTarget.closest(".blender-slot")
    const queue = slot.parentElement
    const index = Array.from(queue.children).indexOf(slot)
    const other = queue.children[index + step]
    if (!other) return
    queue.insertBefore(step < 0 ? slot : other, step < 0 ? other : slot)
    commitBlenderOrder(true)
    document.querySelectorAll(".blender-slot-num")[index + step].focus()
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
    const afterElement = getDragAfterElement(event.currentTarget, event.originalEvent.clientY, ".sprout-ai-token-row:not(.dragging)")
    if (afterElement == null) event.currentTarget.appendChild(dragging)
    else event.currentTarget.insertBefore(dragging, afterElement)
 })
