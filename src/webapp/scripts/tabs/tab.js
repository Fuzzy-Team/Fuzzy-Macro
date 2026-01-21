/*
=============================================
Tab bar
=============================================
*/

//switch tab
//start by hiding all tabs, then show the one that is relevant
//also remove all tabs' active class and add it back to the target one
function switchTab(event) {
    const tabName = event.currentTarget.id.split("-")[0]
    //remove and hide
    Array.from(document.getElementsByClassName("content")).forEach(x => {
        x.style.display = "none"
    })
    Array.from(document.getElementsByClassName("sidebar-item")).forEach(x => {
        x.classList.remove("active")
    })
    //add and show
    event.currentTarget.classList.add("active")
    document.getElementById(`${tabName}-placeholder`).style.display = "flex"

    // Save active tab
    localStorage.setItem("activeTab", event.currentTarget.id)
}
//load and add event handlers
$("#tabs-placeholder")
    .load("../htmlImports/persistent/tabs.html", function () {
        // Restore active tab
        const activeTabId = localStorage.getItem("activeTab")
        if (activeTabId) {
            const tab = document.getElementById(activeTabId)
            if (tab) {
                tab.click()
            }
        }
    })
    .on("click", ".sidebar-item", switchTab)
