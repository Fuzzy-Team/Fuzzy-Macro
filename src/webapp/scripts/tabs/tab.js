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

//subtab bar: items are ".{prefix}-tab-item" and each shows the panel "#{item id}-tab"
function switchSubtab(prefix, target) {
    setActiveSubtab(`active${prefix[0].toUpperCase()}${prefix.slice(1)}Subtab`, target.id)
    const selector = document.getElementById(`${prefix}-select`)
    if (selector) selector.remove()
    Array.from(document.getElementsByClassName(`${prefix}-tab-item`)).forEach(x => {
        x.classList.remove("active")
        const panel = document.getElementById(`${x.id}-tab`)
        if (panel) panel.style.display = "none"
    })
    target.classList.add("active")
    target.innerHTML = `<div class = "select-indicator" id = "${prefix}-select"></div>` + target.innerHTML
    const tab = document.getElementById(`${target.id}-tab`)
    if (tab) {
        tab.style.display = "block"
        tab.scrollTo(0, 0)
    }
}

//briefly mark a reset button active (ignoring clicks meanwhile) and run fn
function flashButton(el, fn) {
    if (el.classList.contains("active")) return
    fn()
    el.classList.add("active")
    setTimeout(() => el.classList.remove("active"), 700)
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
