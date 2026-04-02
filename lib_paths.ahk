gt_stingershop()
{
    global function, FwdKey, LeftKey, BackKey, RightKey, RotLeft
    function := A_ThisFunc
    movement :=
        (
            '
    BSSWalk(3, FwdKey)
    BSSWalk(52, LeftKey)
    BSSWalk(3, FwdKey)
    Send "{w down}{space down}"
    HyperSleep(300)
    Send "{space up}"
    BSSWalk(5, RightKey)
    Send "{space down}"
    HyperSleep(300)
    Send "{space up}{w up}"
    HyperSleep(500)
    BSSWalk(2, FwdKey)
    BSSWalk(15, RightKey)
    BSSWalk(6, FwdKey, RightKey)
    BSSWalk(7, FwdKey)
    BSSWalk(5, BackKey, LeftKey)
    BSSWalk(23, FwdKey)
    BSSWalk(12, LeftKey)
    BSSWalk(11, LeftKey, FwdKey)
    Send "{' . RotLeft . ' 4}"
    BSSWalk(15, FwdKey, RightKey)
    '
        )