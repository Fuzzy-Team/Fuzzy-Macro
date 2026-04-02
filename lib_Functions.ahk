WaitTillLoadedVichop() {
    ; Intended use is if you want to join next game without leaving.

    ; Timeouts (milliseconds)
    totalTimeoutMs := 40000   ; hard cap for the entire wait
    neverLeaveTimeoutMs := 15000 ; if we started in-game and never leave within this, fail

    startTime := A_TickCount

    ActivateRoblox()

    ; Capture initial state
    initialInGame := IsInGame()
    everInGameAtStart := initialInGame
    leftGame := !initialInGame ; if we didn't start in-game, treat "left old game" as already satisfied
    lastState := initialInGame