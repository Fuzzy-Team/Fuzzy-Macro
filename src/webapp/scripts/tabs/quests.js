

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

function showQuestGiverSettings(key) {
    document.querySelectorAll(".quest-giver-settings").forEach(section => {
        section.hidden = section.id !== `${key}-quest-settings`;
    });
}

async function loadQuests(){
    switchQuestsTab(document.getElementById(getActiveSubtab("activeQuestsSubtab", "quests-quests")));
    const [patterns, settings] = await Promise.all([eel.getPatterns()(), loadAllSettings()]);
    document.querySelectorAll('select[id$="_quest_gather_pattern"]').forEach(select => {
        patterns.forEach(pattern => select.add(new Option(pattern.label || pattern.name, pattern.value || pattern.name)));
        const saved = settings[select.id];
        if (saved && !Array.from(select.options).some(option => option.value === saved)) {
            select.add(new Option(`${saved} (not found)`, saved));
        }
    });
    loadInputs(settings);
}

$("#quests-placeholder")
.load("../htmlImports/tabs/quests.html", loadQuests) //load kill tab
.on("click", ".quests-tab-item", (event) => switchQuestsTab(event.currentTarget)) //navigate between tabs
