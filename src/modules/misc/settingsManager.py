import ast
import os
import shutil

#returns a dictionary containing the settings
profileName = "a"

# Profile management functions
def getProfilesDir():
    """Get the profiles directory path"""
    return "../settings/profiles"

def listProfiles():
    """List all available profiles"""
    profiles_dir = getProfilesDir()
    if os.path.exists(profiles_dir):
        profiles = [d for d in os.listdir(profiles_dir) 
                   if os.path.isdir(os.path.join(profiles_dir, d)) and not d.startswith('.')]
        return sorted(profiles)
    return []

def getCurrentProfile():
    """Get the current profile name"""
    global profileName
    return profileName

def switchProfile(name):
    """Switch to a different profile"""
    global profileName
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, name)
    
    if not os.path.exists(profile_path) or not os.path.isdir(profile_path):
        return False, f"Profile '{name}' not found"
    
    profileName = name
    
    # Sync the new profile's field settings to general settings
    initializeFieldSync()
    
    return True, f"Switched to profile: {name}"

def createProfile(name):
    """Create a new profile by copying the current profile"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Sanitize the profile name
    name = name.strip().replace(' ', '_').lower()
    if not name:
        return False, "Profile name cannot be empty"
    
    # Check if profile already exists
    new_profile_path = os.path.join(profiles_dir, name)
    if os.path.exists(new_profile_path):
        return False, f"Profile '{name}' already exists"
    
    # Copy current profile to new profile
    current_profile_path = os.path.join(profiles_dir, profileName)
    try:
        shutil.copytree(current_profile_path, new_profile_path)
        return True, f"Created profile: {name}"
    except Exception as e:
        return False, f"Failed to create profile: {str(e)}"

def deleteProfile(name):
    """Delete a profile (cannot delete current or last profile)"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Cannot delete current profile
    if name == profileName:
        return False, "Cannot delete the currently active profile"
    
    # Cannot delete if it's the only profile
    profiles = listProfiles()
    if len(profiles) <= 1:
        return False, "Cannot delete the only remaining profile"
    
    profile_path = os.path.join(profiles_dir, name)
    if not os.path.exists(profile_path):
        return False, f"Profile '{name}' not found"
    
    try:
        shutil.rmtree(profile_path)
        return True, f"Deleted profile: {name}"
    except Exception as e:
        return False, f"Failed to delete profile: {str(e)}"

def renameProfile(old_name, new_name):
    """Rename a profile"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Sanitize the new name
    new_name = new_name.strip().replace(' ', '_').lower()
    if not new_name:
        return False, "New profile name cannot be empty"
    
    old_path = os.path.join(profiles_dir, old_name)
    new_path = os.path.join(profiles_dir, new_name)
    
    if not os.path.exists(old_path):
        return False, f"Profile '{old_name}' not found"
    
    if os.path.exists(new_path):
        return False, f"Profile '{new_name}' already exists"
    
    try:
        os.rename(old_path, new_path)
        # If we renamed the current profile, update the reference
        if old_name == profileName:
            profileName = new_name
        return True, f"Renamed profile from '{old_name}' to '{new_name}'"
    except Exception as e:
        return False, f"Failed to rename profile: {str(e)}"

def duplicateProfile(source_name, new_name):
    """Duplicate an existing profile with a new name"""
    profiles_dir = getProfilesDir()
    
    # Sanitize the new name
    new_name = new_name.strip().replace(' ', '_').lower()
    if not new_name:
        return False, "New profile name cannot be empty"
    
    source_path = os.path.join(profiles_dir, source_name)
    new_path = os.path.join(profiles_dir, new_name)
    
    if not os.path.exists(source_path):
        return False, f"Source profile '{source_name}' not found"
    
    if os.path.exists(new_path):
        return False, f"Profile '{new_name}' already exists"
    
    try:
        shutil.copytree(source_path, new_path)
        return True, f"Duplicated profile '{source_name}' as '{new_name}'"
    except Exception as e:
        return False, f"Failed to duplicate profile: {str(e)}"

def readSettingsFile(path):
    #get each line
    #read the file, format it to:
    #[[key, value], [key, value]]
    with open(path) as f:
        data = [[x.strip() for x in y.split("=", 1)] for y in f.read().split("\n") if y]
    f.close()
    #convert to a dict
    out = {}
    for k,v in data:
        try:
            out[k] = ast.literal_eval(v)
        except:
            #check if integer
            if v.isdigit():
                out[k] = int(v)
            elif v.replace(".","",1).isdigit():
                out[k] = float(v)
            out[k] = v
    return out

def saveDict(path, data):
    out = "\n".join([f"{k}={v}" for k,v in data.items()])
    with open(path, "w") as f:
        f.write(str(out))
    f.close()

#update one property of a setting
def saveSettingFile(setting,value, path):
    #get the dictionary
    data = readSettingsFile(path)
    #update the dictionary
    data[setting] = value
    #write it
    saveDict(path, data)

def loadFields():
    with open(f"../settings/profiles/{profileName}/fields.txt") as f:
        out = ast.literal_eval(f.read())
    f.close()
    
    # Auto-add missing goo settings for backward compatibility
    # This ensures users upgrading from older versions get the new goo functionality
    fieldsUpdated = False
    for field, settings in out.items():
        # Add missing goo settings if they don't exist
        if "goo" not in settings:
            settings["goo"] = False  # Default to disabled
            fieldsUpdated = True
        if "goo_interval" not in settings:
            settings["goo_interval"] = 3  # Default to 3 seconds (minimum allowed)
            fieldsUpdated = True
    
    # Save the updated fields if any were modified
    if fieldsUpdated:
        with open(f"../settings/profiles/{profileName}/fields.txt", "w") as f:
            f.write(str(out))
        f.close()
    
    for field,settings in out.items():
        for k,v in settings.items():
            #check if integer
            if isinstance(v,str): 
                if v.isdigit(): out[field][k] = int(v)
                elif v.replace(".","",1).isdigit(): out[field][k] = float(v)
    return out

def saveField(field, settings):
    fieldsData = loadFields()
    fieldsData[field] = settings
    with open(f"../settings/profiles/{profileName}/fields.txt", "w") as f:
        f.write(str(fieldsData))
    f.close()

def syncFieldSettings(setting, value):
    """Synchronize field settings from profile to general settings"""
    try:
        # Update the general settings file
        generalSettingsPath = "../settings/generalsettings.txt"
        generalData = readSettingsFile(generalSettingsPath)
        generalData[setting] = value
        saveDict(generalSettingsPath, generalData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to general settings: {e}")

def syncFieldSettingsToProfile(setting, value):
    """Synchronize field settings from general to profile settings"""
    try:
        # Update the profile settings file
        profileSettingsPath = f"../settings/profiles/{profileName}/settings.txt"
        profileData = readSettingsFile(profileSettingsPath)
        profileData[setting] = value
        saveDict(profileSettingsPath, profileData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to profile settings: {e}")

def saveProfileSetting(setting, value):
    saveSettingFile(setting, value, f"../settings/profiles/{profileName}/settings.txt")
    # Synchronize field settings with general settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettings(setting, value)

def saveDictProfileSettings(dict):

    saveDict(f"../settings/profiles/{profileName}/settings.txt", {**readSettingsFile(f"../settings/profiles/{profileName}/settings.txt"), **dict})

#increment a setting, and return the dictionary for the setting
def incrementProfileSetting(setting, incrValue):
    #get the dictionary
    data = readSettingsFile(f"../settings/profiles/{profileName}/settings.txt")
    #update the dictionary
    data[setting] += incrValue
    #write it
    saveDict(f"../settings/profiles/{profileName}/settings.txt", data)
    return data

def saveGeneralSetting(setting, value):
    saveSettingFile(setting, value, "../settings/generalsettings.txt")
    # Synchronize field settings with profile settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettingsToProfile(setting, value)

def loadSettings():
    settings = readSettingsFile(f"../settings/profiles/{profileName}/settings.txt")
    # Ensure fields and fields_enabled arrays have 5 elements
    defaultSettings = readSettingsFile("./data/default_settings/settings.txt")
    defaultFields = defaultSettings.get("fields", ['pine tree', 'sunflower', 'dandelion', 'pine tree', 'sunflower'])
    defaultFieldsEnabled = defaultSettings.get("fields_enabled", [True, False, False, False, False])
    
    fields = settings.get("fields", [])
    fieldsEnabled = settings.get("fields_enabled", [])
    
    # Extend arrays to 5 elements if needed
    updated = False
    while len(fields) < 5:
        fields.append(defaultFields[len(fields)] if len(fields) < len(defaultFields) else defaultFields[-1])
        updated = True
    while len(fieldsEnabled) < 5:
        fieldsEnabled.append(defaultFieldsEnabled[len(fieldsEnabled)] if len(fieldsEnabled) < len(defaultFieldsEnabled) else False)
        updated = True
    
    if updated:
        settings["fields"] = fields
        settings["fields_enabled"] = fieldsEnabled
        saveDict(f"../settings/profiles/{profileName}/settings.txt", settings)
    
    return settings

#return a dict containing all settings except field (general, profile, planters)
def loadAllSettings():
    return {**loadSettings(), **readSettingsFile("../settings/generalsettings.txt")}

def initializeFieldSync():
    """Initialize field synchronization between profile and general settings"""
    try:
        profileData = readSettingsFile(f"../settings/profiles/{profileName}/settings.txt")
        generalData = readSettingsFile("../settings/generalsettings.txt")
        
        # Check if field settings exist in both files
        profileFields = profileData.get("fields", [])
        generalFields = generalData.get("fields", [])
        
        # If general settings has different fields, sync from profile to general
        if profileFields != generalFields and profileFields:
            generalData["fields"] = profileFields
            saveDict("../settings/generalsettings.txt", generalData)
            
        # Sync fields_enabled as well
        profileFieldsEnabled = profileData.get("fields_enabled", [])
        generalFieldsEnabled = generalData.get("fields_enabled", [])
        
        if profileFieldsEnabled != generalFieldsEnabled and profileFieldsEnabled:
            generalData["fields_enabled"] = profileFieldsEnabled
            saveDict("../settings/generalsettings.txt", generalData)
            
    except Exception as e:
        print(f"Warning: Could not initialize field synchronization: {e}")

#clear a file
def clearFile(filePath):
    open(filePath, 'w').close()