
function switchBoostTab(target){
    switchSubtab("boost", target)
}

//items that can be picked for a hotbar slot. mins is how long the item's buff lasts and becomes the
//slot's Use Every timer when picked. Glitter and Gumdrops have no buff time to suggest, so they only label the slot.
const boostHotbarItems = [
    { name: "Oil", icon: "oil", mins: 10 },
    { name: "Super Smoothie", icon: "super_smoothie", mins: 20 },
    { name: "Red Extract", icon: "red_extract", mins: 10 },
    { name: "Blue Extract", icon: "blue_extract", mins: 10 },
    { name: "Glue", icon: "glue", mins: 10 },
    { name: "Enzymes", icon: "enzymes", mins: 10 },
    { name: "Tropical Drink", icon: "tropical_drink", mins: 10 },
    { name: "Purple Potion", icon: "purple_potion", mins: 15 },
    { name: "Glitter", icon: "glitter" },
    { name: "Gumdrops", icon: "gumdrops" },
].map((item) => ({ ...item, value: item.name.toLowerCase() }))

const boostHotbarItemOptions = [
    { label: "None", value: "none" },
    ...boostHotbarItems.map((item) => ({
        label: `<img src="./assets/icons/${item.icon}.png" class="icon-img">${item.name}`,
        value: item.value,
    })),
]

//show the picked item's icon on the slot button and the slot panel
function updateBoostHotbarIcons() {
    for (let slot = 1; slot <= 7; slot++) {
        const dropdown = document.getElementById(`hotbar${slot}_item`)
        const frame = document.querySelector(`#boost-slot-${slot} .boost-hotbar-slot-frame`)
        const icon = document.querySelector(`#boost-hotbar-slot-${slot}-panel .boost-hotbar-panel-icon`)
        if (!dropdown || !frame || !icon) continue
        const item = boostHotbarItems.find((x) => x.value === getDropdownValue(dropdown))
        const html = item
            ? `<img src="./assets/icons/${item.icon}.png" alt="${item.name}">`
            : `<span class="boost-hotbar-slot-empty"></span>`
        frame.innerHTML = html
        icon.innerHTML = html
        icon.classList.toggle("boost-hotbar-panel-icon-empty", !item)
        document.getElementById(`boost-slot-${slot}`).title = item ? `Slot ${slot}: ${item.name}` : `Slot ${slot}`
    }
}

//save the picked item and set the slot's timer to the item's buff time. The timer can still be edited afterwards.
async function pickBoostHotbarItem(dropdown) {
    await saveSetting(dropdown, "profile")
    const slot = dropdown.id.match(/\d+/)[0]
    const item = boostHotbarItems.find((x) => x.value === getDropdownValue(dropdown))
    if (!item || !item.mins) return
    const valueEle = document.getElementById(`hotbar${slot}_use_every_value`)
    const formatEle = document.getElementById(`hotbar${slot}_use_every_format`)
    valueEle.value = item.mins
    setDropdownValue(formatEle, "mins")
    await saveSetting(valueEle, "profile")
    await saveSetting(formatEle, "profile")
}

function switchBoostHotbarSlot(slot) {
    Array.from(document.getElementsByClassName("boost-hotbar-slot")).forEach((button) => {
        button.classList.remove("active")
    })
    Array.from(document.getElementsByClassName("boost-hotbar-panel")).forEach((panel) => {
        panel.classList.remove("active")
    })

    const button = document.getElementById(`boost-slot-${slot}`)
    const panel = document.getElementById(`boost-hotbar-slot-${slot}-panel`)
    if (!button || !panel) return

    button.classList.add("active")
    panel.classList.add("active")
}

async function loadBoost(){
    switchBoostTab(document.getElementById(getActiveSubtab("activeBoostSubtab", "boost-hotbar")))
    switchBoostHotbarSlot(1)
    try {
        const patterns = await eel.getDefaultPatterns()();
        setDropdownData("tad_alt_gather_shape", patterns);
        const settings = await loadAllSettings();
        const patternDropdown = document.getElementById("tad_alt_gather_shape");
        if (patternDropdown) setDropdownValue(patternDropdown, settings.tad_alt_gather_shape || "e_lol");
    } catch (error) {
        console.error("Could not load TAD Alt patterns", error);
    }
}

async function copyHostFieldSettingsToTadAlt(button) {
    if (button.classList.contains("active")) return;
    button.classList.add("active");
    try {
        const settings = await loadAllSettings();
        const fieldName = String(settings.tad_alt_default_field || "pine tree").trim();
        const normalizedFieldName = fieldName.toLowerCase().replaceAll("_", " ").replace(/\s+/g, " ");
        const allFields = await eel.loadFields()();
        const sourceEntry = Object.entries(allFields).find(([key]) =>
            String(key).trim().toLowerCase().replaceAll("_", " ").replace(/\s+/g, " ") === normalizedFieldName
        );
        const source = sourceEntry?.[1];
        if (!source) throw new Error(`No host settings found for ${fieldName}`);

        const copied = {
            tad_alt_gather_shape: source.shape || "e_lol",
            tad_alt_gather_size: source.size || "m",
            tad_alt_gather_width: source.width ?? 5,
            tad_alt_gather_shift_lock: Boolean(source.shift_lock),
            tad_alt_gather_drift_compensation: Boolean(source.field_drift_compensation),
            tad_alt_gather_invert_lr: Boolean(source.invert_lr),
            tad_alt_gather_invert_fb: Boolean(source.invert_fb),
            tad_alt_gather_turn: source.turn || "none",
            tad_alt_gather_turn_times: source.turn_times ?? 1,
            tad_alt_gather_start_location: source.start_location || "center",
            tad_alt_gather_distance: source.distance ?? 1,
            tad_alt_gather_goo: Boolean(source.goo),
            tad_alt_gather_goo_interval: source.goo_interval ?? 3,
        };

        await eel.saveDictProfileSettings(copied)();
        loadInputs(copied);
        button.textContent = "Copied";
    } catch (error) {
        console.error("Could not copy host field settings to TAD Alt", error);
        button.textContent = "Copy Failed";
    } finally {
        setTimeout(() => {
            button.classList.remove("active");
            button.textContent = "Copy Settings";
        }, 900);
    }
}


function clearAFBData(ele){
    flashButton(ele, () => eel.clearAFB())
}

$("#boost-placeholder")
.load("../htmlImports/tabs/boost.html", loadBoost) //load kill tab
.on("click", ".boost-tab-item", (event) => switchBoostTab(event.currentTarget)) //navigate between tabs
