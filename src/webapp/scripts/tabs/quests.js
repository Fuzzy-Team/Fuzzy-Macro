

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
let questPatterns = [];
let questObjectiveSettingsRequest = 0;
// Objective Type dropdown options. The catalog has 44 objectives, too many for one list.
const questObjectiveGroups = [
    {label: "Pollen by Color", value: "pollen", kinds: ["pollen"]},
    {label: "Pollen in a Field", value: "gather", kinds: ["gather"]},
    {label: "Tokens", value: "token", kinds: ["token", "fieldtoken"]},
    {label: "Goo", value: "goo", kinds: ["pollengoo", "gathergoo"]},
    {label: "Bloom Petals", value: "petal", kinds: ["gatherpetal"]},
];

function questObjectiveGroup(key) {
    return questObjectiveGroups.find(group => group.kinds.includes(key.split("_")[0]));
}

function showQuestObjectiveGroup(value, key, settings) {
    const options = questObjectiveTypes.filter(item => questObjectiveGroup(item.value).value === value);
    setDropdownData("quest_mapping_objective", options);
    key = key || options[0].value;
    setDropdownValue(document.getElementById("quest_mapping_objective"), key);
    return showQuestObjectiveSettings(key, settings);
}

function setQuestMappingLoading(loading) {
    for (const id of ["quest_mapping_field", "quest_mapping_pattern", "open-quest-gather-button"]) {
        document.getElementById(id).style.pointerEvents = loading ? "none" : "";
    }
}

async function showQuestObjectiveSettings(key, settings) {
    const objective = questObjectiveTypes.find(item => item.value === key);
    if (!objective) return;
    const request = ++questObjectiveSettingsRequest;
    setQuestMappingLoading(true);
    const prefix = `quest_objective_${key}_`;
    for (const input of [document.getElementById("quest_mapping_field"), document.getElementById("quest_mapping_pattern"), ...questGatherInputs()]) {
        input.dataset.settingId = prefix + input.id.slice("quest_mapping_".length);
    }
    settings = settings || await loadAllSettings();
    if (request !== questObjectiveSettingsRequest || getDropdownValue(document.getElementById("quest_mapping_objective")) !== key) return;
    const currentPattern = String(settings[prefix + "pattern"] || "").toLowerCase();
    const hiddenPatterns = settings.hidden_patterns || [];
    setDropdownData("quest_mapping_pattern", [{label: "Auto", value: "auto"}, ...questPatterns.filter(pattern =>
        !hiddenPatterns.includes(pattern.value.toLowerCase()) || pattern.value.toLowerCase() === currentPattern)]);
    const fieldOptions = objective.fields.map(field => ({
        label: `${fieldEmojis[field.replaceAll(" ", "_")]} ${toTitleCase(field)}`,
        value: field,
    }));
    setDropdownData("quest_mapping_field", [{label: "Auto", value: "auto"}, ...fieldOptions]);
    document.getElementById("quest_mapping_field").closest("form").style.display = objective.field ? "none" : "flex";
    loadInputs(settings);
    setQuestMappingLoading(false);
    document.getElementById("objective-gather-settings").parentElement.style.display = "block";
}

function questGatherInputs() {
    return document.querySelectorAll('#quest-gather-modal [id^="quest_mapping_"]');
}

async function openQuestGatherSettings() {
    const request = ++questObjectiveSettingsRequest;
    setQuestMappingLoading(true);
    const key = getDropdownValue(document.getElementById("quest_mapping_objective"));
    document.getElementById("quest-gather-objective").textContent = questObjectiveTypes.find(item => item.value === key).label;
    const settings = await loadAllSettings();
    if (request !== questObjectiveSettingsRequest || getDropdownValue(document.getElementById("quest_mapping_objective")) !== key) return;
    loadInputs(settings);
    setQuestMappingLoading(false);
    document.getElementById("quest-gather-modal").style.display = "flex";
}

function closeQuestGatherSettings() {
    document.getElementById("quest-gather-modal").style.display = "none";
}

async function saveQuestGatherSettings() {
    const changes = Object.fromEntries(Array.from(questGatherInputs(), input =>
        [input.dataset.settingId, getInputValueFromElement(input)]));
    try {
        await eel.saveDictProfileSettings(changes)();
    } catch (error) {
        alert(`Gather settings were not saved: ${error?.errorText || error}`);
        return;
    }
    closeQuestGatherSettings();
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
    const request = ++questObjectiveSettingsRequest;
    switchQuestsTab(document.getElementById(getActiveSubtab("activeQuestsSubtab", "quests-quests")));
    document.getElementById("objective-gather-settings").parentElement.style.display = "none";
    const [patterns, objectives, settings] = await Promise.all([
        eel.getPatterns()(), eel.getQuestObjectiveTypes()(), loadAllSettings(),
    ]);
    if (request !== questObjectiveSettingsRequest) return;
    questObjectiveTypes = objectives;
    questPatterns = patterns;
    const selector = document.getElementById("quest_mapping_objective");
    const current = getDropdownValue(selector);
    const key = objectives.some(item => item.value === current) ? current : (objectives.find(item => item.value === "pollen_red") || objectives[0])?.value;
    if (key) {
        const group = questObjectiveGroup(key).value;
        setDropdownValue(document.getElementById("quest_mapping_group"), group);
        await showQuestObjectiveGroup(group, key, settings);
    } else {
        loadInputs(settings);
    }
}

$("#quests-placeholder")
.load("../htmlImports/tabs/quests.html", loadQuests) //load kill tab
.on("click", ".quests-tab-item", (event) => switchQuestsTab(event.currentTarget)) //navigate between tabs
