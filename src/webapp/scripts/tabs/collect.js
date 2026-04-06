/*
=============================================
Collect Tab
=============================================
*/


function clearBlenderData(ele){
    if (ele.classList.contains("active")) return
    eel.clearBlender()
    ele.classList.add("active")
    setTimeout(() => {
        ele.classList.remove("active")
      }, 700)
}

function switchCollectTab(target){
    Array.from(document.getElementsByClassName("collect-tab-item")).forEach(x => {
        x.classList.remove("active")
        document.getElementById(`${x.id}-tab`).style.display = "none"
    })

    target.classList.add("active")
    const tab = document.getElementById(`${target.id}-tab`)
    tab.style.display = "block"
    tab.scrollTo(0, 0)
}

async function loadCollect(){
    const settings = await loadAllSettings()
    loadInputs(settings)
    switchCollectTab(document.getElementById("collect-dispensers"))
}

$("#collect-placeholder")
.load("../htmlImports/tabs/collect.html", loadCollect)
 .on("click", ".collect-tab-item", (event) => switchCollectTab(event.currentTarget))
