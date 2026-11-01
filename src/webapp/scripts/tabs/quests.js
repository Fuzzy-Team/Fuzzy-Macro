

function switchQuestsTab(target){
    setActiveSubtab("activeQuestsSubtab", target.id)
    //hide all tabs

    //remove the arrow indicator
    const selector = document.getElementById("quests-select")
    if (selector) selector.remove()
    //remove active class and hide all tabs
    Array.from(document.getElementsByClassName("quests-tab-item")).forEach(x => {
        x.classList.remove("active")
        document.getElementById(`${x.id}-tab`).style.display = "none"
    })
    //add indicator + active class
    target.classList.add("active")
    target.innerHTML = `<div class = "select-indicator" id = "quests-select"></div>` + target.innerHTML
    //show tab
    tab = document.getElementById(`${target.id}-tab`)
    tab.style.display = "block"
    //scroll back to top
    tab.scrollTo(0,0); 
}

let questObjectiveTypes = [];

async function showQuestObjectiveSettings(key, settings) {
    const objective = questObjectiveTypes.find(item => item.value === key);
    if (!objective) return;
    const fieldOptions = objective.fields.map(field => ({
        label: `${fieldEmojis[field.replaceAll(" ", "_")]} ${toTitleCase(field)}`,
        value: field,
    }));
    setDropdownData("quest_mapping_field", [{label: "Auto", value: "auto"}, ...fieldOptions]);
    document.getElementById("quest_mapping_field").closest("form").style.display = objective.field ? "none" : "flex";
    for (const property of ["field", "pattern", "mins", "backpack", "return"]) {
        document.getElementById(`quest_mapping_${property}`).dataset.settingId = `quest_objective_${key}_${property}`;
    }
    loadInputs(settings || await loadAllSettings());
}

// Progress check rows only matter while the quest menu stays open.
function updateQuestProgressFields() {
    const watch = document.getElementById("quest_progress_watch");
    if (!watch) return;
    const mode = document.getElementById("quest_progress_check_mode");
    const interval = getDropdownValue(mode) === "interval";
    mode.closest("form").style.display = watch.checked ? "flex" : "none";
    document.getElementById("quest_progress_check_seconds").closest("form").style.display = watch.checked && interval ? "flex" : "none";
}

async function loadQuests(){
    switchQuestsTab(document.getElementById(getActiveSubtab("activeQuestsSubtab", "quests-quests")));
    const [patterns, objectives, settings] = await Promise.all([
        eel.getPatterns()(), eel.getQuestObjectiveTypes()(), loadAllSettings(),
    ]);
    questObjectiveTypes = objectives;
    const selector = document.getElementById("quest_mapping_objective");
    const current = getDropdownValue(selector);
    setDropdownData("quest_mapping_objective", objectives);
    setDropdownData("quest_mapping_pattern", [{label: "Auto", value: "auto"}, ...patterns]);
    const key = objectives.some(item => item.value === current) ? current : (objectives.find(item => item.value === "pollen_red") || objectives[0])?.value;
    if (key) {
        setDropdownValue(selector, key);
        await showQuestObjectiveSettings(key, settings);
    } else {
        loadInputs(settings);
    }
}

$("#quests-placeholder")
.load("../htmlImports/tabs/quests.html", loadQuests) //load kill tab
.on("click", ".quests-tab-item", (event) => switchQuestsTab(event.currentTarget)) //navigate between tabs
