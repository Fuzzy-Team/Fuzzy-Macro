

function switchKillTab(target){
    switchSubtab("kill", target)
}

async function loadKill(){
    switchKillTab(document.getElementById(getActiveSubtab("activeKillSubtab", "kill-regular")))
    loadInputs(await loadAllSettings())
}

$("#kill-placeholder")
.load("../htmlImports/tabs/kill.html", loadKill) //load kill tab
.on("click", ".kill-tab-item", (event) => switchKillTab(event.currentTarget)) //navigate between tabs
