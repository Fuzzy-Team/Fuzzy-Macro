        if (accountType = "main") {
            SetStatus("Vichop", field " - Vicious bee found!")
            ; After detecting the bee, call the appropriate approach-and-kill function.
            switch field {
                case "Pepper": return PepperMainKillVic()
                case "Mountaintop": return MountainTopKillVic()
                case "Spider": return SpiderKillVic()
                case "Cactus", "Cactus (Back)": return CactusKillVic()
                case "Rose": return RoseKillVic()
            }
            return false ; Failsafe
        } else if (accountType = "alt") {
            SetStatus("Vichop", field " - Vicious bee spotted")
            vichop_alt_SendLink(SearcherJoinID, field)
            ; Update both alltime and session stats for vics spotted
            AlltimeVicsSpotted := IniRead("settings\settings.ini", "Vichop", "alltime_vics_spotted", 0) + 1
            SessionVicsSpotted++
            IniWrite(AlltimeVicsSpotted, "settings\settings.ini", "Vichop", "alltime_vics_spotted")
            IniWrite(SessionVicsSpotted, "settings\settings.ini", "Vichop", "session_vics_spotted")
            Sleep(500)
            return true
        }