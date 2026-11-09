# BambDupe
# Width is the source's reps; size and inverted movement keys are not used.

def move(distance, *keys):
    if self.checkPauseAndWait():
        return
    try:
        for key in keys:
            self.keyboard.keyDown(key, False)
        self.keyboard.tileWait(distance)
    finally:
        for key in keys:
            self.keyboard.keyUp(key, False)


def bamb_dupe_move(distance, *keys):
    global bamb_found_dupe
    loops = math.floor(distance / 2 + 0.5) if distance > 1 else 1
    interval = distance / loops
    for _ in range(loops):
        if self.checkPauseAndWait():
            return
        move(interval, *keys)
        if bamb_found_dupe == 1:
            # Source's one-shot EndDupeLoop timer expires after 1000 ms.
            deadline = time.monotonic() + 1
            while True:
                if self.checkPauseAndWait():
                    return
                stop_dupe_loop = time.monotonic() >= deadline
                bamb_found_dupe = int(findBlackPixel(
                    self.robloxWindow,
                    bamb_win_x * 0.5 - bamb_win_y * 0.12,
                    bamb_win_x * 0.5 + bamb_win_y * 0.1,
                    bamb_win_y * 0.5,
                ) is not None)
                if bamb_found_dupe == 0 or stop_dupe_loop:
                    break


def bamb_moves(reps):
    D, M = "D", "M"   # DupeMove, MoveCharacter
    return (
        (D, 3, "w"),
        (D, 4.57, "a"), (D, 4.14, "a", "s"), (D, 10.5 + reps, "s"), (D, 2.5, "w"),
        (D, 7.83, "d"), (D, 8.14, "w", "d"), (M, 2, "w", "d"), (M, reps, "d"),
        (M, 2, "w", "a"), (D, 2.14, "w", "a"), (D, 4.57, "a"),
        (D, 2, "s"),
        (D, 3.74, "a"), (D, 2.49, "a", "s"), (D, 2.49, "s"), (D, 2.49, "s", "d"),
        (D, 7.49, "d"), (D, 2.49, "w", "d"), (D, 2.49, "w"), (D, 2.49, "w", "a"),
        (D, 3.74, "a"),
        (D, 1, "w"),
        (D, 4.16, "a"), (D, 3.31, "a", "s"), (D, 3.31, "s"), (D, 3.31, "s", "d"),
        (D, 8.31, "d"), (D, 3.31, "w", "d"), (D, 3.31, "w"), (D, 3.31, "w", "a"),
        (D, 4.16, "a"),
        (D, 2, "s"),
        (D, 3.33, "a"), (D, 1.66, "a", "s"), (D, 1.66, "s"), (D, 1.66, "s", "d"),
        (D, 6.66, "d"), (D, 1.66, "w", "d"), (D, 1.66, "w"), (D, 1.66, "w", "a"),
        (D, 3.33, "a"),
        (D, 2, "w"),
        (D, 4.16, "a"), (D, 3.31, "a", "s"), (D, 3.31, "s"), (D, 3.31, "s", "d"),
        (D, 8.31, "d"), (D, 3.31, "w", "d"), (D, 3.31, "w"), (D, 3.31, "w", "a"),
        (D, 4.16, "a"),
        (D, 2, "s"),
        (D, 3.33, "a"), (D, 1.66, "a", "s"), (D, 1.66, "s"), (D, 1.66, "s", "d"),
        (D, 6.66, "d"), (D, 1.66, "w", "d"), (D, 1.66, "w"), (D, 1.66, "w", "a"),
        (D, 3.33, "a"),
    )


if not globals().get("bamb_started"):
    # Fuzzy caches content bounds and cannot distinguish a missing window from
    # its screen-size fallback. The source instead raises for a missing client.
    bamb_win_x, bamb_win_y = self.robloxWindow.mw, self.robloxWindow.mh
    bamb_found_dupe = 0
    # Source: duplicated setup never runs twice; FindDupe's SetTimer is commented
    # out. Keep detection dormant, rather than enabling a timer absent upstream.
    for _ in range(4):
        if self.checkPauseAndWait():
            break
        self.keyboard.press(rotup, 0.017)  # Camera tap hold: 17 ms.
    bamb_started = True

for kind, distance, *keys in bamb_moves(width):
    if self.checkPauseAndWait():
        break
    if kind == "D":
        bamb_dupe_move(distance, *keys)
    else:
        move(distance, *keys)
