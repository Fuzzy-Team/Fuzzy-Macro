

function switchKillTab(target){
    switchSubtab("kill", target)
}

function loadKill(){
    switchKillTab(document.getElementById(getActiveSubtab("activeKillSubtab", "kill-settings")))
}

$("#kill-placeholder")
.load("../htmlImports/tabs/kill.html", loadKill) //load kill tab
.on("click", ".kill-tab-item", (event) => switchKillTab(event.currentTarget)) //navigate between tabs
