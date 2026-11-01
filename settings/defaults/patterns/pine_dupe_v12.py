# PineDupe v12 by EliTheLegoGuy, ported from Zenith Macro's macro_patterns.py.
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


def safe_pixel_search(start_x1, start_x2, y):
    # Source rounds X half up, then truncates Y separately for each pixel search.
    x1 = math.floor(start_x1 + 0.5)
    x2 = math.floor(start_x2 + 0.5)
    while True:
        if self.checkPauseAndWait():
            return 0
        found_x = findBlackPixel(self.robloxWindow, x1, x2, y)
        if found_x is None:
            return 0
        if findBlackPixel(self.robloxWindow, found_x, found_x, y + 1) is not None:
            return 1
        if findBlackPixel(self.robloxWindow, found_x, found_x, y - 1) is not None:
            return 1
        if found_x == x2:
            return 0
        x1 = found_x + 1


_PINE_SEARCHES = {
    0: ((-0.351, -0.251, 0.119), (-0.031, 0.069, 0.119), (0.287, 0.387, 0.119),
        (-0.389, -0.289, 0.432), (-0.427, -0.327, 0.803)),
    1: ((-0.106, -0.006, 0), (0.198, 0.298, 0.172), (0.438, 0.538, 0.397),
        (-0.282, -0.182, 0.172), (-0.522, -0.422, 0.397)),
    # Source: rotation 2, row 2 searches a single X coordinate (0.325 twice).
    2: ((0.287, 0.387, 0.119), (0.325, 0.325, 0.432), (0.363, 0.463, 0.803),
        (-0.031, 0.069, 0.119), (-0.351, -0.251, 0.119)),
}


_PINE_DUPE_MOVES = {
    0: {2: ((5.66, "w"), (5.66, "d"), (8, "s", "a"), (5.66, "s")),
        4: ((5.66, "a"), (5.66, "s"), (8, "w", "d"), (5.66, "d")),
        1: ((8, "w", "a"), (8, "s", "d")),
        3: ((8, "w", "d"), (8, "a", "s")),
        5: ((8, "a", "s"), (8, "w", "d"))},
    1: {2: ((5.66, "w", "d"), (5.66, "d", "s"), (8, "a"), (5.66, "s", "a")),
        4: ((5.66, "a", "w"), (5.66, "s", "a"), (8, "d"), (5.66, "d", "s")),
        1: ((8, "w"), (8, "s")),
        3: ((8, "d"), (8, "a")),
        5: ((8, "a"), (8, "d"))},
    2: {2: ((5.66, "d"), (5.66, "s"), (8, "a", "w"), (5.66, "a")),
        4: ((5.66, "w"), (5.66, "a"), (8, "d", "s"), (5.66, "s")),
        1: ((8, "w", "d"), (8, "s", "a")),
        3: ((8, "d", "s"), (8, "a", "w")),
        5: ((8, "a", "w"), (8, "d", "s"))},
}


def pine_dupe_search(left_rotations):
    found = {}
    for number, (x1, x2, y) in enumerate(_PINE_SEARCHES[left_rotations], 1):
        found[number] = safe_pixel_search(
            pine_win_x * 0.5 + pine_win_y * x1,
            pine_win_x * 0.5 + pine_win_y * x2, pine_win_y * y)
    moves = _PINE_DUPE_MOVES[left_rotations]
    # Source: FoundDupe1 == 3 is impossible, since each result is 0 or 1.
    for lead, check in ((2, 1), (4, 5)):
        if found[lead] == 1:
            first, second, third, alternative = moves[lead]
            move(*first)
            sleep(0.9)
            if found[check] == (3 if lead == 2 else 1):
                move(*second)
                sleep(0.9)
                move(*third)
            else:
                move(*alternative)
            return
    for number in (1, 3, 5):
        if found[number] == 1:
            first, second = moves[number]
            move(*first)
            sleep(0.9)
            move(*second)
            return


def pine_steps(reps):
    """The body in order: (distance, key[, key2]) is MoveCharacter, ("search", n) is the
    DupeSearch with n left rotations, ("tap", key) is a camera turn."""
    return (
        (2.07, "w", "d"), (4.14, "d"), (4.14, "d", "s"), (4.14, "s"),
        (reps * 1.41, "d", "s"), (4.14, "s", "a"), (1, "s"), (1, "w"), (4.14, "a"),
        (4.14, "w", "a"), (4.14, "w"), (2.07, "w", "d"),
        (0.5, "s", "d"),                                  # go to dupe check spot
        ("search", 0),
        (1, "s", "d"),                                    # go to smaller octogon
        (1.24, "w", "d"), (2.49, "d"), (2.49, "d", "s"), (2.49, "s"), (2.49, "s", "a"),
        (2.49, "a"), (2.49, "w", "a"), (2.49, "w"), (1.24, "w", "d"),
        (1, "w", "a"),                                    # go to bigger octogon
        ("search", 0),
        ("tap", ","),                                     # rotate camera 45 degrees
        (1.66, "d"), (3.31, "d", "s"), (3.31, "s"), (3.31, "a", "s"), (3.31, "a"),
        (3.31, "w", "a"), (3.31, "w"), (3.31, "w", "d"), (1.66, "d"),
        ("search", 1),
        (2, "s"),
        (0.83, "d"), (1.66, "d", "s"), (1.66, "s"), (1.66, "a", "s"), (1.66, "a"),
        (1.66, "w", "a"), (1.66, "w"), (1.66, "w", "d"), (0.83, "d"),
        (2, "w"),
        ("search", 1),
        ("tap", ","),
        (1.66, "s", "d"), (3.31, "s"), (3.31, "s", "a"), (3.31, "a"), (3.31, "w", "a"),
        (3.31, "w"), (3.31, "w", "d"), (3.31, "d"), (1.66, "s", "d"),
        ("search", 2),
        (2, "s", "a"),
        (0.83, "s", "d"), (1.66, "s"), (1.66, "s", "a"), (1.66, "a"), (1.66, "w", "a"),
        (1.66, "w"), (1.66, "w", "d"), (1.66, "d"), (0.83, "s", "d"),
        (3.5, "w", "d"),
        ("search", 2),
        ("tap", "."), ("tap", "."),                       # rotate camera 90 degrees
    )


if not globals().get("pine_started"):
    # RobloxWindowBounds already defaults to the screen bounds without a window.
    pine_win_x, pine_win_y = self.robloxWindow.mw, self.robloxWindow.mh
    for _ in range(4):
        if self.checkPauseAndWait():
            break
        self.keyboard.press(rotup, 0.017)  # Zenith's default setting_key_delay: 17 ms.
    pine_started = True

for step in pine_steps(width):
    if self.checkPauseAndWait():
        break
    if step[0] == "search":
        pine_dupe_search(step[1])
    elif step[0] == "tap":
        self.keyboard.press(step[1], 0.017)
    else:
        move(*step)
