/*
=============================================
Planters Tab
=============================================
*/

//when the planter slider changes
function changePlanterMode(){
    const ele = document.getElementById("planters_mode")
    saveSetting(ele, 'profile')
    //show the corresponding tab
    const planterMode = {
        0: "off",
        1: "manual",
        2: "auto"
    }
    Array.from(document.getElementsByClassName("planter-tab")).forEach(x => x.style.display="none")
    
    document.getElementById(`planters-${planterMode[ele.value]}`).style.display = "block"
}

const planters = Object.keys(planterIcons)
const planterArray = toImgArray(planterIcons)
const fields = Object.keys(fieldNectarIcons)
const fieldNectarArray = toImgArray(fieldNectarIcons, true)
const nectars = Object.keys(nectarIcons)
const nectarArray = toImgArray(nectarIcons)

function fieldDropDownHTML(id){
    return buildInput(id,{
        name: "dropdown",
        data: fieldNectarArray,
        triggerFunction: "saveSetting(this, 'profile')",
        length: 11.5    
    })
}
function planterDropDownHTML(id){
    return buildInput(id,{
        name: "dropdown",
        data: planterArray,
        triggerFunction: "saveSetting(this, 'profile')",
        length: 11.5
    })
}
function nectarDropDownHTML(id){
    return buildInput(id,{
        name: "dropdown",
        data: nectarArray,
        triggerFunction: "saveSetting(this, 'profile')",
        length: 11.5
    })
}


async function loadPlanters(){
    const cycleElement = document.getElementById("manual-planters-cycles")
    // reset the container to its original header content to avoid duplicates
    cycleElement.innerHTML = `
            <h2>Planter Cycles</h2>
            <p style = "font-weight:500; font-size:1rem;">The macro can place and collect up to 3 planters at once each cycle. Setting a field or planter as 'none' will make the macro ignore that slot</p>
        `
    for (let i=1; i < 6;i++){
        const html = 
        `
        <div class="seperator" style="margin-bottom: 1rem;"></div>
        <h3 class="poppins-semibold">Cycle ${i}</h3>
        <table style="margin-top: 1rem; row-gap: 1rem;">
            <tr>
                <td><h4 class="poppins-regular">Planters:</h4></td>
                <td>${planterDropDownHTML(`cycle${i}_1_planter`)}</td>
                <td>${planterDropDownHTML(`cycle${i}_2_planter`)}</td>
                <td>${planterDropDownHTML(`cycle${i}_3_planter`)}</td>
            </tr>
            <tr>
                <td><h4 class="poppins-regular">Fields:</h4></td>
                <td>${fieldDropDownHTML(`cycle${i}_1_field`)}</td>
                <td>${fieldDropDownHTML(`cycle${i}_2_field`)}</td>
                <td>${fieldDropDownHTML(`cycle${i}_3_field`)}</td>
            </tr>
            <tr>
                <td>
                    <h4 class="poppins-regular">Gather in Planter Field:</h4>
                    <div class="poppins-regular" style="font-size:0.9rem; color: #adb4bc">The field's gather settings match<br>those in the gather tab</div>
                </td>
                
                <td><label class="checkbox-container" style="margin-top:-0.6rem">
                    <input type="checkbox" id = "cycle${i}_1_gather" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label></td>
                <td><label class="checkbox-container" style="margin-top:-0.6rem">
                    <input type="checkbox" id = "cycle${i}_2_gather" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label></td>
                <td><label class="checkbox-container" style="margin-top:-0.6rem">
                    <input type="checkbox" id = "cycle${i}_3_gather" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label></td>
            </tr>
            <tr>
                <td>
                    <h4 class="poppins-regular">Glitter:</h4>
                    <div class="poppins-regular" style="font-size:0.9rem; color: #adb4bc">Use Glitter when the placing a planter.<br>Speeds up planter growth by 25%</div>
                </td>
                <td><label class="checkbox-container" style="margin-top:-1.2rem">
                    <input type="checkbox" id = "cycle${i}_1_glitter" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label></td>
                <td><label class="checkbox-container" style="margin-top:-1.2rem">
                    <input type="checkbox" id = "cycle${i}_2_glitter" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label></td>
                <td><label class="checkbox-container" style="margin-top:-1.2rem">
                    <input type="checkbox" id = "cycle${i}_3_glitter" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label></td>
            </tr>
        </table>
        `
        cycleElement.innerHTML += html
    }

    const nectarPriorityElement = document.getElementById("auto-nectar-priority")
    // clear previous content to prevent duplication when reloading
    nectarPriorityElement.innerHTML = ""
    //auto planter's nectar priority
    for(let i = 0; i < nectars.length; i++){
        const html = `
        <form style="display: flex; align-items:flex-start; justify-content: space-between; padding-right: 5%; margin-top:1rem" ;="">
            ${nectarDropDownHTML(`auto_priority_${i}_nectar`)}
            <input type="text" id="auto_priority_${i}_min" style="width: 10rem; margin-top: 0.6rem;" class="poppins-regular textbox" data-input-type="int" data-input-limit="3" onkeypress="return textboxRestriction(this, event)" onchange="saveSetting(this, 'profile')">
        </form>
        `
        nectarPriorityElement.innerHTML += html
    }

    // Note: Allowed-planters is merged into per-planter panels (enable toggle embedded in each panel)
    
    const planterFieldRestrictionsElement = document.getElementById("auto-planter-field-restrictions")
    // clear previous content to prevent duplication when reloading
    planterFieldRestrictionsElement.innerHTML = ""
    // For each planter, create a collapsible section that shows allowed fields when expanded
    for(let i = 0; i < planters.length; i++){
        if (planters[i] == "none") continue
        let fieldsHTML = ""
        for(let j = 0; j < fields.length; j++){
            if (fields[j] == "none") continue
            const fieldId = `auto_planter_${planters[i]}_field_${fields[j]}`
            fieldsHTML += `
                <div style="display:flex; align-items:center; gap:0.4rem; width: 220px;">
                    <label style="white-space:nowrap; flex:1">${fieldNectarArray[j]}</label>
                    <label class="checkbox-container" style="margin-top: 0;">
                        <input type="checkbox" id="${fieldId}" onchange="saveSetting(this, 'profile'); updatePlanterRestrictionSummaries()">
                        <span class="checkmark"></span>
                    </label>
                </div>
            `
        }
        const summaryId = `planter_restriction_summary_${planters[i]}`
        const enableId = `auto_planter_${planters[i]}`
        const html = `
        <details style="margin-top:0.6rem; transition: box-shadow 0.15s;">
            <summary title="Click to expand and view allowed fields" style="display:flex; align-items:center; justify-content:space-between; cursor:pointer;">
                <div style="display:flex; align-items:center; gap:0.6rem;">
                    <label class="checkbox-container" style="margin:0;">
                        <input type="checkbox" id="${enableId}" onchange="saveSetting(this, 'profile'); updatePlanterRestrictionSummaries(); togglePlanterEnabledStyle('${planters[i]}')">
                        <span class="checkmark"></span>
                    </label>
                    <div>${planterArray[i]}</div>
                </div>
                <div style="font-size:0.9rem; color:#6b7280" id="${summaryId}">Allowed fields: 0</div>
            </summary>
            <div style="display:flex; flex-wrap:wrap; gap:0.6rem; padding-top:0.8rem;">
                ${fieldsHTML}
            </div>
        </details>
        `
        planterFieldRestrictionsElement.innerHTML += html
    }

    const allowedFieldsElement = document.getElementById("auto-allowed-fields")
    // clear previous content to prevent duplication when reloading
    allowedFieldsElement.innerHTML = ""
    //auto planter's nectar priority
    for(let i = 0; i < fields.length; i++){
        if (fields[i] == "none") continue
        const html = `
        <form style="display: flex; align-items:flex-start; justify-content: space-between; padding-right: 10%; margin-top:1rem" ;="">
            <div style="width: 70%;">
                <label>${fieldNectarArray[i]}</label>
            </div>
            <label class="checkbox-container" style="margin-top: 0.6rem;">
                    <input type="checkbox" id="auto_field_${fields[i]}" onchange="saveSetting(this, 'profile')">
                    <span class="checkmark"></span>
                </label>
        </form>
        `
        allowedFieldsElement.innerHTML += html
    }

    //load inputs
    const settings = await loadAllSettings()
    loadInputs(settings)
    // Ensure per-planter field keys default to allowed
    try{
        // For each per-planter-field checkbox, if the setting is not present in the profile,
        // default it to checked (allowed) and persist to profile so it behaves as a default.
        const pfInputs = document.querySelectorAll('input[id^="auto_planter_"][id*="_field_"]')
        pfInputs.forEach(inp => {
            if (!settings.hasOwnProperty(inp.id)){
                inp.checked = true
                try{ eel.saveProfileSetting(inp.id, true) }catch(e){}
            }
        })
    }catch(e){
        // ignore if DOM not ready or eel not available
    }

    // Update the planter restriction summaries after inputs have loaded
    try{
        updatePlanterRestrictionSummaries()
    }catch(e){
        // ignore if function not available yet
    }
    // load auto-planter JSON to set the global gather checkbox
    try{
        const autoData = await eel.getAutoPlanterData()()
        const gatherCheckbox = document.getElementById("auto_planters_gather")
        if (gatherCheckbox && autoData && typeof autoData.gather !== 'undefined'){
            gatherCheckbox.checked = !!autoData.gather
        }
    }catch(e){
        console.warn('Failed to load auto-planter data for gather flag', e)
    }
    //show the planter tab
    changePlanterMode()
}

async function toggleAutoPlantersGather(val){
    try{
        await eel.setAutoPlanterGather(!!val)()
    }catch(e){
        console.warn('Failed to set auto planter gather flag', e)
    }
}

function clearManualPlantersData(){
    const btn = document.getElementById("manual-planters-reset-btn")
    if (btn.classList.contains("active")) return
    eel.clearManualPlanters()
    btn.classList.add("active")
    setTimeout(() => {
        btn.classList.remove("active")
      }, 700)
}

function clearAutoPlantersData(){
    const btn = document.getElementById("auto-planters-reset-btn")
    if (btn.classList.contains("active")) return
    eel.clearAutoPlanters()
    btn.classList.add("active")
    setTimeout(() => {
        btn.classList.remove("active")
      }, 700)
}

// Update the displayed "Allowed fields: X" summary for each planter
function updatePlanterRestrictionSummaries(){
    for(let i = 0; i < planters.length; i++){
        if (planters[i] == "none") continue
        const inputs = document.querySelectorAll(`input[id^="auto_planter_${planters[i]}_field_"]`)
        let count = 0
        inputs.forEach(x => { if (x.checked) count++ })
        const summary = document.getElementById(`planter_restriction_summary_${planters[i]}`)
        if (summary) summary.innerText = `Allowed fields: ${count}`
        // Update visual style for enabled state
        try{
            togglePlanterEnabledStyle(planters[i])
        }catch(e){ }
    }
}

// Toggle visual highlight for a planter panel when globally enabled
function togglePlanterEnabledStyle(planterName){
    const summaryId = `planter_restriction_summary_${planterName}`
    const enableCheckbox = document.getElementById(`auto_planter_${planterName}`)
    const summaryElem = document.getElementById(summaryId)
    if (!summaryElem) return
    const detailsElem = summaryElem.closest('details')
    if (!detailsElem) return
    if (enableCheckbox && enableCheckbox.checked){
        detailsElem.style.boxShadow = '0 0 0 2px rgba(96,165,250,0.12)'
        detailsElem.style.borderRadius = '6px'
        detailsElem.style.border = '1px solid rgba(96,165,250,0.25)'
    } else {
        detailsElem.style.boxShadow = ''
        detailsElem.style.border = 'none'
    }
}

function changePreset(ele){
    const presetData = {
        "blue": {
            "auto_priority_0_nectar": "comforting",
            "auto_priority_1_nectar": "motivating",
            "auto_priority_2_nectar": "satisfying",
            "auto_priority_3_nectar": "refreshing",
            "auto_priority_4_nectar": "invigorating",
            "auto_priority_0_min": 70,
            "auto_priority_1_min": 80,
            "auto_priority_2_min": 80,
            "auto_priority_3_min": 80,
            "auto_priority_4_min": 40,
            "auto_field_sunflower": true,
            "auto_field_dandelion": true,
            "auto_field_mushroom": false,
            "auto_field_blue_flower": true,
            "auto_field_clover": true,
            "auto_field_strawberry": true,
            "auto_field_spider": true,
            "auto_field_bamboo": false,
            "auto_field_pineapple": true,
            "auto_field_stump": false,
            "auto_field_cactus": true,
            "auto_field_pumpkin": false,
            "auto_field_pine_tree": true,
            "auto_field_rose": true,
            "auto_field_mountain_top": false,
            "auto_field_pepper": true,
            "auto_field_coconut": false,
        },
        "red": {
            "auto_priority_0_nectar": "invigorating",
            "auto_priority_1_nectar": "refreshing",
            "auto_priority_2_nectar": "motivating",
            "auto_priority_3_nectar": "satisfying",
            "auto_priority_4_nectar": "comforting",
            "auto_priority_0_min": 70,
            "auto_priority_1_min": 80,
            "auto_priority_2_min": 80,
            "auto_priority_3_min": 80,
            "auto_priority_4_min": 40,
            "auto_field_sunflower": true,
            "auto_field_dandelion": true,
            "auto_field_mushroom": false,
            "auto_field_blue_flower": true,
            "auto_field_clover": true,
            "auto_field_strawberry": true,
            "auto_field_spider": true,
            "auto_field_bamboo": true,
            "auto_field_pineapple": true,
            "auto_field_stump": false,
            "auto_field_cactus": true,
            "auto_field_pumpkin": true,
            "auto_field_pine_tree": true,
            "auto_field_rose": true,
            "auto_field_mountain_top": false,
            "auto_field_pepper": true,
            "auto_field_coconut": false,
        },
        "white": {
            "auto_priority_0_nectar": "satisfying",
            "auto_priority_1_nectar": "motivating",
            "auto_priority_2_nectar": "refreshing",
            "auto_priority_3_nectar": "comforting",
            "auto_priority_4_nectar": "invigorating",
            "auto_priority_0_min": 70,
            "auto_priority_1_min": 80,
            "auto_priority_2_min": 80,
            "auto_priority_3_min": 80,
            "auto_priority_4_min": 40,
            "auto_field_sunflower": true,
            "auto_field_dandelion": true,
            "auto_field_mushroom": false,
            "auto_field_blue_flower": true,
            "auto_field_clover": true,
            "auto_field_strawberry": true,
            "auto_field_spider": true,
            "auto_field_bamboo": true,
            "auto_field_pineapple": true,
            "auto_field_stump": false,
            "auto_field_cactus": true,
            "auto_field_pumpkin": false,
            "auto_field_pine_tree": true,
            "auto_field_rose": true,
            "auto_field_mountain_top": false,
            "auto_field_pepper": true,
            "auto_field_coconut": false,
        }
    }
    saveSetting(ele, "profile")
    const preset = getInputValue(ele.id)
    if (preset in presetData){
        const data = presetData[preset]
        loadInputs(data, save="profile")
    }
}

$("#planters-placeholder")
.load("../htmlImports/tabs/planters.html", loadPlanters) 
