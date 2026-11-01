

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

const questGivers = ["polar bear", "brown bear", "black bear", "honey bee", "bucko bee", "riley bee"];

// Show only the chosen giver's rows in the Quest Giver Overrides card.
function showQuestGiverSettings(giver) {
    const key = giver.replaceAll(" ", "_");
    const card = document.getElementById("quest-giver-overrides").parentElement;
    card.querySelectorAll("form").forEach(form => {
        const id = form.querySelector("[id]").id;
        if (id !== "quest_override_giver") form.style.display = id.startsWith(`${key}_`) ? "flex" : "none";
    });
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
    const [patterns, settings] = await Promise.all([eel.getPatterns()(), loadAllSettings()]);
    questGivers.forEach(giver => {
        setDropdownData(`${giver.replaceAll(" ", "_")}_quest_gather_pattern`, [{ label: "Auto", value: "auto" }, ...patterns]);
    });
    loadInputs(settings);
    setDropdownValue(document.getElementById("quest_override_giver"), "polar bear");
}

$("#quests-placeholder")
.load("../htmlImports/tabs/quests.html", loadQuests) //load kill tab
.on("click", ".quests-tab-item", (event) => switchQuestsTab(event.currentTarget)) //navigate between tabs
