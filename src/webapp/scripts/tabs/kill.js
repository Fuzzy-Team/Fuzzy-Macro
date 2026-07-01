

function switchKillTab(target){
    setActiveSubtab("activeKillSubtab", target.id)
    //hide all tabs

    //remove the arrow indicator
    const selector = document.getElementById("kill-select")
    if (selector) selector.remove()
    //remove active class and hide all tabs
    Array.from(document.getElementsByClassName("kill-tab-item")).forEach(x => {
        x.classList.remove("active")
        document.getElementById(`${x.id}-tab`).style.display = "none"
    })
    //add indicator + active class
    target.classList.add("active")
    target.innerHTML = `<div class = "select-indicator" id = "kill-select"></div>` + target.innerHTML
    //show tab
    tab = document.getElementById(`${target.id}-tab`)
    tab.style.display = "block"
    //scroll back to top
    tab.scrollTo(0,0); 
}

function setVicHopStatText(id, value) {
    const element = document.getElementById(id)
    if (element) element.textContent = Number(value || 0).toLocaleString()
}

function renderVicHopStats(settings) {
    const sessionServers = settings?.vic_hop_session_servers_hopped || 0
    const sessionNights = settings?.vic_hop_session_nights_detected || 0
    const sessionVics = settings?.vic_hop_session_vics_detected || 0
    const servers = settings?.vic_hop_servers_hopped || 0
    const nights = settings?.vic_hop_nights_detected || 0
    const vics = settings?.vic_hop_vics_detected || 0

    setVicHopStatText("vic-hop-session-servers", sessionServers)
    setVicHopStatText("vic-hop-session-nights", sessionNights)
    setVicHopStatText("vic-hop-session-vics", sessionVics)
    setVicHopStatText("vic-hop-all-servers", servers)
    setVicHopStatText("vic-hop-all-nights", nights)
    setVicHopStatText("vic-hop-all-vics", vics)
    setVicHopStatText("vic-hop-lifetime-servers", servers)
    setVicHopStatText("vic-hop-lifetime-nights", nights)
    setVicHopStatText("vic-hop-lifetime-vics", vics)
}

async function loadKill(){
    try {
        const settings = await loadAllSettings()
        loadInputs(settings)
        renderVicHopStats(settings)
    } catch (error) {
        console.error("Failed to load kill settings:", error)
    }
    switchKillTab(document.getElementById(getActiveSubtab("activeKillSubtab", "kill-settings")))
}

$("#kill-placeholder")
.load("../htmlImports/tabs/kill.html", loadKill) //load kill tab
.on("click", ".kill-tab-item", (event) => switchKillTab(event.currentTarget)) //navigate between tabs
