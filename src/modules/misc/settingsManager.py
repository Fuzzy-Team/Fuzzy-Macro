import ast
#returns a dictionary containing the settings
profileName = "a"
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