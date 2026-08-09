
function switchBoostTab(target){
    setActiveSubtab("activeBoostSubtab", target.id)
    //hide all tabs

    //remove the arrow indicator
    const selector = document.getElementById("boost-select")
    if (selector) selector.remove()
    //remove active class and hide all tabs
    Array.from(document.getElementsByClassName("boost-tab-item")).forEach(x => {
        x.classList.remove("active")
        document.getElementById(`${x.id}-tab`).style.display = "none"
    })
    //add indicator + active class
    target.classList.add("active")
    target.innerHTML = `<div class = "select-indicator" id = "boost-select"></div>` + target.innerHTML
    //show tab
    tab = document.getElementById(`${target.id}-tab`)
    tab.style.display = "block"
    //scroll back to top
    tab.scrollTo(0,0); 
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
        const patterns = await eel.getPatterns()();
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
        const fieldName = String(settings.tad_alt_default_field || "pine tree").trim().toLowerCase();
        const allFields = await eel.loadFields()();
        const source = allFields[fieldName];
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
    if (ele.classList.contains("active")) return
    eel.clearAFB()
    ele.classList.add("active")
    setTimeout(() => {
        ele.classList.remove("active")
      }, 700)
}

$("#boost-placeholder")
.load("../htmlImports/tabs/boost.html", loadBoost) //load kill tab
.on("click", ".boost-tab-item", (event) => switchBoostTab(event.currentTarget)) //navigate between tabs
