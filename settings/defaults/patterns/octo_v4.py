# Octo v4

def key_down(*keys):
    for key in keys:
        self.keyboard.keyDown(key, False)

def key_up(*keys):
    for key in keys:
        self.keyboard.keyUp(key, False)

def walk(distance):
    """Walk `distance` tiles with the keys already held."""
    self.keyboard.tileWait(distance)

def move(distance, *keys):
    key_down(*keys)
    walk(distance)
    key_up(*keys)

def find_octo_color():
    """First window pixel within 8 per channel of 0x01D8FF, scanning rows top to bottom.
    Returns (x, y) in window pixels, or None."""
    window = self.robloxWindow
    bgra = mssScreenshotNP(window.mx, window.my, window.mw, window.mh)
    bgr = bgra[:, :, :3].astype(np.int16)
    close = np.all(np.abs(bgr - np.array([255, 216, 1], dtype=np.int16)) <= 8, axis=2)
    hits = np.argwhere(close)
    if len(hits) == 0:
        return None
    y, x = hits[0]
    return int(x), int(y)

def go_to_xy(x, y, win_x, win_y):
    """Walk toward a window pixel: diagonal first, then the rest of the way on one axis."""
    mx = (x - win_x * 0.5) / win_y * 17
    my = (y - win_y * 0.5) / win_y * 16
    key_up("w", "a", "s", "d")
    if mx > 0:
        if my > 0:
            if mx > my:
                key_down("d", "s")
                walk(my * 1.414)
                key_up("s")
                walk(mx - my)
                key_up("d")
            else:
                key_down("d", "s")
                walk(mx * 1.414)
                key_up("d")
                walk(my - mx)
                key_up("s")
        else:
            if mx > -my:
                key_down("d", "w")
                walk(-my * 1.414)
                key_up("w")
                walk(mx + my)
                key_up("d")
            else:
                key_down("d", "w")
                walk(mx * 1.414)
                key_up("d")
                walk(-my - mx)
                key_up("w")
    else:
        if my > 0:
            if -mx > my:
                key_down("a", "s")
                walk(my * 1.414)
                key_up("s")
                walk(-mx - my)
                key_up("a")
            else:
                key_down("a", "s")
                walk(-mx * 1.414)
                key_up("a")
                walk(my + mx)
                key_up("s")
        else:
            if mx < my:
                key_down("a", "w")
                walk(-my * 1.414)
                key_up("w")
                walk(-mx + my)
                key_up("a")
            else:
                key_down("a", "w")
                walk(-mx * 1.414)
                key_up("a")
                walk(-my + mx)
                key_up("w")

def octo_moves():
    # `width` is the field's width setting (the source's reps).
    second_leg = 4.14 + (width - 1) * 1.41
    return (
        (2.5, "s"),
        (2.07, "d"), (2.07, "d", "w"), (2.07, "d", "w"), (4.14, "w"), (4.14, "w", "a"),
        (4.14, "a"), (4.14, "a", "s"), (second_leg, "s"),
        (2.07, "s", "d"), (2.07, "s", "d"), (2.07, "d"),
        (3.75, "w"),
        (0.83, "d"), (1.66, "d", "w"), (1.66, "w"), (1.66, "w", "a"), (1.66, "a"),
        (1.66, "a", "s"), (1.66, "s"), (1.66, "s", "d"), (0.83, "d"),
        (2.5, "s"),
        (1.66, "d"), (3.31, "d", "w"), (3.31, "w"), (3.31, "w", "a"), (3.31, "a"),
        (3.31, "a", "s"), (3.31, "s"), (3.31, "s", "d"), (1.66, "d"),
        (1.25, "w"),
        (1.24, "d"), (2.49, "d", "w"), (2.49, "w"), (2.49, "w", "a"), (2.49, "a"),
        (2.49, "a", "s"), (2.49, "s"), (2.49, "s", "d"), (1.24, "d"),
    )

# Setup runs once per gather: four PgUp rotations, then for width != 1 walk back 12 tiles and forward 4.
if not globals().get("octo_started"):
    globals()["octo_started"] = True
    for _ in range(4):
        self.keyboard.press(rotup)
    if width != 1:
        move(12, "s")
        move(4, "w")

window = self.robloxWindow
if width != 1:
    hit = find_octo_color()
    if hit is not None:
        go_to_xy(hit[0], hit[1] + window.mh * 0.4, window.mw, window.mh)

for distance, *keys in octo_moves():
    move(distance, *keys)
