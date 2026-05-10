# Cup
# Original Lua pattern by Souka/Seto, based on Kettle by Dully.
# Converted for Fuzzy Macro's Python pattern runner.

digi_stops = False

if sizeword.lower() == "xs":
    size = 0.25
elif sizeword.lower() == "s":
    size = 0.5
elif sizeword.lower() == "l":
    size = 1.5
elif sizeword.lower() == "xl":
    size = 2
else:
    size = 1

step = 0.5
l = step * size
s = l / 4
h = l / 2

# Alignment values are scaled to Fuzzy Macro movement units.
crfdc = 0.3 * step * size
dwalign = 1.5 * step * size
hwalign = 2 * step * size
align_drift = 0.25 * step * size


def ds(seconds):
    if digi_stops:
        sleep(seconds)


def dy_walk(length, dir1, dir2=None):
    if dir2 is None:
        self.keyboard.walk(dir1, length)
    else:
        self.keyboard.multiWalk([dir1, dir2], length)


current_yaw = 0


def set_yaw(yaw):
    global current_yaw
    left_turns = (current_yaw - yaw) % 8
    right_turns = (yaw - current_yaw) % 8
    if left_turns <= right_turns:
        for _ in range(left_turns):
            self.keyboard.press(rotleft)
    else:
        for _ in range(right_turns):
            self.keyboard.press(rotright)
    current_yaw = yaw
    sleep(0.05)


self.keyboard.press(rotup)
self.keyboard.press(rotup)
self.keyboard.press(rotup)
self.keyboard.press(rotup)
sleep(0.05)

# Shape one, straight.
dy_walk(h, leftkey)
dy_walk(s, fwdkey)
dy_walk(l, rightkey)
dy_walk(s, fwdkey)
dy_walk(l, leftkey)
set_yaw(7)
dy_walk(l, backkey, leftkey)
if dwalign > 0:
    dy_walk(dwalign + align_drift, backkey, leftkey)
    dy_walk(dwalign, fwdkey, rightkey)
    ds(0.7)
dy_walk(s, backkey, rightkey)
dy_walk(l, fwdkey, rightkey)
dy_walk(s, backkey, rightkey)
dy_walk(h, backkey, leftkey)
set_yaw(0)
dy_walk(h, backkey)
dy_walk(s, rightkey)
dy_walk(l, fwdkey)
dy_walk(s, rightkey)
if hwalign > 0:
    dy_walk(hwalign + align_drift, rightkey)
    dy_walk(hwalign, leftkey)
    ds(0.6)
dy_walk(l, backkey)
set_yaw(6)
dy_walk(l, fwdkey)
dy_walk(s, rightkey)
dy_walk(l, backkey)
dy_walk(s, rightkey)
dy_walk(h, fwdkey)
set_yaw(0)

# Shape two, diagonal.
dy_walk(h, fwdkey, leftkey)
ds(0.85)
dy_walk(s, fwdkey, rightkey)
dy_walk(l, backkey, rightkey)
dy_walk(s, fwdkey, rightkey)
dy_walk(l, fwdkey, leftkey)
set_yaw(7)
dy_walk(l, leftkey)
dy_walk(s + crfdc, backkey)
dy_walk(l, rightkey)
dy_walk(s + crfdc, backkey)
dy_walk(h, leftkey)
set_yaw(0)
dy_walk(h, backkey, leftkey)
dy_walk(s, backkey, rightkey)
dy_walk(l, fwdkey, rightkey)
dy_walk(s, backkey, rightkey)
dy_walk(l, backkey, leftkey)
set_yaw(6)
dy_walk(l, fwdkey, rightkey)
dy_walk(l, backkey, leftkey)
dy_walk(s, backkey, rightkey)
ds(0.7)
dy_walk(h, fwdkey, rightkey)
set_yaw(0)

self.keyboard.press(rotdown)
self.keyboard.press(rotdown)
self.keyboard.press(rotdown)
self.keyboard.press(rotdown)
sleep(0.05)
