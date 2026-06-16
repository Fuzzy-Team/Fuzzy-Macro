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

function setActiveSubtab(storageKey, tabId) {
    if (!storageKey || !tabId) return
    localStorage.setItem(storageKey, tabId)
}

function getActiveSubtab(storageKey, fallbackTabId) {
    return localStorage.getItem(storageKey) || fallbackTabId
}
//load and add event handlers
$("#tabs-placeholder")
    .load("../htmlImports/persistent/tabs.html", function (response, status, xhr) {
        if (status === "error") {
            console.error("Failed to load sidebar tabs:", xhr.status, xhr.statusText)
            this.innerHTML = `<div class="sidebar-load-error">Failed to load tabs (${xhr.status})</div>`
            return
        }
        // Restore active tab
        const activeTabId = localStorage.getItem("activeTab")
        if (activeTabId) {
            const tab = document.getElementById(activeTabId)
            if (tab) {
                tab.click()
                return
            }
        }
        const homeTab = document.getElementById("home-tab")
        if (homeTab) homeTab.click()
    })
    .on("click", ".sidebar-item", switchTab)
