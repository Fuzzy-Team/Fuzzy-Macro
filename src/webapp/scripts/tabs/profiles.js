/*
=============================================
Profiles Tab
=============================================
*/

async function loadProfiles() {
  const settings = await loadAllSettings();
  loadInputs(settings);

  // Load profile list
  await loadProfileList();
}

/*
=============================================
Profile Management
=============================================
*/

async function loadProfileList() {
  try {
    const profiles = await eel.listProfiles()();
    const currentProfile = await eel.getCurrentProfile()();

    // Update current profile display
    const currentProfileDisplay = document.getElementById(
      "current-profile-display"
    );
    if (currentProfileDisplay) {
      currentProfileDisplay.textContent = currentProfile;
    }

    // Update profile list
    const profileList = document.getElementById("profile-list");
    if (profileList) {
      profileList.innerHTML = "";
      profiles.forEach((profile) => {
        const isActive = profile === currentProfile;
        const profileItem = document.createElement("div");
        profileItem.className = `profile-item ${isActive ? "active" : ""}`;
        profileItem.innerHTML = `
          <div style="display: flex; align-items: center;">
            <span class="profile-item-name">${profile}</span>
            ${
              isActive
                ? '<span class="current-profile-badge">ACTIVE</span>'
                : ""
            }
          </div>
          <div class="profile-item-actions">
            ${
              !isActive
                ? `<button class="profile-btn profile-btn-primary" onclick="switchToProfile('${profile}')">Switch</button>`
                : ""
            }
            ${
              !isActive && profiles.length > 1
                ? `<button class="profile-btn profile-btn-danger" onclick="deleteProfileConfirm('${profile}')">Delete</button>`
                : ""
            }
          </div>
        `;
        profileList.appendChild(profileItem);
      });
    }

    // Update duplicate source dropdown
    const duplicateSelect = document.getElementById("duplicate-source-profile");
    if (duplicateSelect) {
      duplicateSelect.innerHTML = "";
      profiles.forEach((profile) => {
        const option = document.createElement("option");
        option.value = profile;
        option.textContent = profile;
        if (profile === currentProfile) {
          option.selected = true;
        }
        duplicateSelect.appendChild(option);
      });
    }
  } catch (error) {
    console.error("Error loading profiles:", error);
  }
}

async function switchToProfile(profileName) {
  try {
    const [success, message] = await eel.switchProfile(profileName)();
    if (success) {
      showProfileStatus("create-profile-status", message, "success");

      // Fully refresh GUI like a page reload
      await refreshAllSettings();

      // Reload profile list
      await loadProfileList();
    } else {
      showProfileStatus("create-profile-status", message, "error");
    }
  } catch (error) {
    showProfileStatus("create-profile-status", `Error: ${error}`, "error");
  }
}

// Refresh all settings and GUI elements (like a page refresh)
async function refreshAllSettings() {
  try {
    // Load all settings from the new profile
    const settings = await loadAllSettings();

    // Update all input elements with new settings
    loadInputs(settings);

    // Reload gather tab (field settings)
    const currentGatherTab = document.querySelector(".gather-tab-item.active");
    if (currentGatherTab && typeof switchGatherTab === "function") {
      await switchGatherTab(currentGatherTab);
    } else if (typeof switchGatherTab === "function") {
      // Default to field 1 if no active tab
      const field1Tab = document.getElementById("field-1");
      if (field1Tab) await switchGatherTab(field1Tab);
    }

    // Reload collect tab
    if (typeof loadCollect === "function") {
      await loadCollect();
    }

    // Reload boost tab
    if (typeof loadBoost === "function") {
      loadBoost();
    }

    // Reload kill tab
    if (typeof loadKill === "function") {
      loadKill();
    }

    // Reload quests tab
    if (typeof loadQuests === "function") {
      loadQuests();
    }

    // Reload planters tab
    if (typeof loadPlanters === "function") {
      await loadPlanters();
    }

    // Reload home tasks
    if (typeof loadTasks === "function") {
      await loadTasks();
    }

    // Reload config tab
    if (typeof loadConfig === "function") {
      await loadConfig();
    }

    console.log("All settings refreshed for new profile");
  } catch (error) {
    console.error("Error refreshing settings:", error);
  }
}

async function createNewProfile() {
  const nameInput = document.getElementById("new-profile-name");
  const name = nameInput.value.trim();

  if (!name) {
    showProfileStatus(
      "create-profile-status",
      "Please enter a profile name",
      "error"
    );
    return;
  }

  try {
    const [success, message] = await eel.createProfile(name)();
    if (success) {
      showProfileStatus("create-profile-status", message, "success");
      nameInput.value = "";
      await loadProfileList();
    } else {
      showProfileStatus("create-profile-status", message, "error");
    }
  } catch (error) {
    showProfileStatus("create-profile-status", `Error: ${error}`, "error");
  }
}

async function deleteProfileConfirm(profileName) {
  if (
    confirm(
      `Are you sure you want to delete the profile "${profileName}"? This action cannot be undone.`
    )
  ) {
    try {
      const [success, message] = await eel.deleteProfile(profileName)();
      if (success) {
        showProfileStatus("create-profile-status", message, "success");
        await loadProfileList();
      } else {
        showProfileStatus("create-profile-status", message, "error");
      }
    } catch (error) {
      showProfileStatus("create-profile-status", `Error: ${error}`, "error");
    }
  }
}

async function duplicateExistingProfile() {
  const sourceSelect = document.getElementById("duplicate-source-profile");
  const newNameInput = document.getElementById("duplicate-new-name");

  const sourceName = sourceSelect.value;
  const newName = newNameInput.value.trim();

  if (!newName) {
    showProfileStatus(
      "duplicate-profile-status",
      "Please enter a new profile name",
      "error"
    );
    return;
  }

  try {
    const [success, message] = await eel.duplicateProfile(
      sourceName,
      newName
    )();
    if (success) {
      showProfileStatus("duplicate-profile-status", message, "success");
      newNameInput.value = "";
      await loadProfileList();
    } else {
      showProfileStatus("duplicate-profile-status", message, "error");
    }
  } catch (error) {
    showProfileStatus("duplicate-profile-status", `Error: ${error}`, "error");
  }
}

function showProfileStatus(elementId, message, type) {
  const statusElement = document.getElementById(elementId);
  if (statusElement) {
    statusElement.innerHTML = `<div class="profile-status ${type}">${message}</div>`;
    // Clear status after 5 seconds
    setTimeout(() => {
      statusElement.innerHTML = "";
    }, 5000);
  }
}

// Load profiles tab
$("#profiles-placeholder").load(
  "../htmlImports/tabs/profiles.html",
  loadProfiles
);
