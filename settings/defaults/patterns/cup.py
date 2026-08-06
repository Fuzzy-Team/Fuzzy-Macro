# Cup
# Original Lua pattern by Souka/Seto, based on Kettle by Dully.
# Converted for Fuzzy Macro's Python pattern runner.

alignment = 0

crFDC = 0.3 * 4 + alignment
dwAlign = 1.5 * 4 + alignment
hwAlign = 2 * 4 + alignment

l = 6.25 * 4
s = l / 4
h = l / 2

digiStops = False

def ds(ms):
    if digiStops:
        sleep(ms / 1000)

def dy_walk(length, dir1, dir2=None):
    tiles = length / 4
    if dir2 is None:
        self.keyboard.tileWalk(dir1, tiles)
    else:
        self.keyboard.multiTileWalk([dir1, dir2], tiles)

def set_yaw_7():
    self.keyboard.press(rotleft)

def set_yaw_6():
    self.keyboard.press(rotleft)
    self.keyboard.press(rotleft)

def set_yaw_0_from_7():
    self.keyboard.press(rotright)

def set_yaw_0_from_6():
    self.keyboard.press(rotright)
    self.keyboard.press(rotright)

# shape one (straight)

dy_walk(h, leftkey)
sleep(0.02)
dy_walk(s, fwdkey)
sleep(0.02)
dy_walk(l, rightkey)
sleep(0.02)
dy_walk(s, fwdkey)
sleep(0.02)
dy_walk(l, leftkey)
sleep(0.02)

set_yaw_7()
dy_walk(l, backkey, leftkey)
sleep(0.02)

if dwAlign > 0:
    dy_walk(dwAlign + 2, backkey, leftkey)
    sleep(0.02)
    dy_walk(dwAlign, fwdkey, rightkey)
    sleep(0.02)
    ds(700)

dy_walk(s, backkey, rightkey)
sleep(0.02)
dy_walk(l, fwdkey, rightkey)
sleep(0.02)
dy_walk(s, backkey, rightkey)
sleep(0.02)
dy_walk(h, backkey, leftkey)
sleep(0.02)

set_yaw_0_from_7()
dy_walk(h, backkey)
sleep(0.02)
dy_walk(s, rightkey)
sleep(0.02)
dy_walk(l, fwdkey)
sleep(0.02)
dy_walk(s, rightkey)
sleep(0.02)

if hwAlign > 0:
    dy_walk(hwAlign + 2, rightkey)
    sleep(0.02)
    dy_walk(hwAlign, leftkey)
    sleep(0.02)
    ds(600)

dy_walk(l, backkey)
sleep(0.02)

set_yaw_6()
dy_walk(l, fwdkey)
sleep(0.02)
dy_walk(s, rightkey)
sleep(0.02)
dy_walk(l, backkey)
sleep(0.02)
dy_walk(s, rightkey)
sleep(0.02)
dy_walk(h, fwdkey)
sleep(0.02)

set_yaw_0_from_6()

# shape two (diago)

dy_walk(h, fwdkey, leftkey)
sleep(0.02)
ds(850)

dy_walk(s, fwdkey, rightkey)
sleep(0.02)
dy_walk(l, backkey, rightkey)
sleep(0.02)
dy_walk(s, fwdkey, rightkey)
sleep(0.02)
dy_walk(l, fwdkey, leftkey)
sleep(0.02)

set_yaw_7()
dy_walk(l, leftkey)
sleep(0.02)
dy_walk(s + crFDC, backkey)
sleep(0.02)
dy_walk(l, rightkey)
sleep(0.02)
dy_walk(s + crFDC, backkey)
sleep(0.02)
dy_walk(h, leftkey)
sleep(0.02)

set_yaw_0_from_7()
dy_walk(h, backkey, leftkey)
sleep(0.02)
dy_walk(s, backkey, rightkey)
sleep(0.02)
dy_walk(l, fwdkey, rightkey)
sleep(0.02)
dy_walk(s, backkey, rightkey)
sleep(0.02)
dy_walk(l, backkey, leftkey)
sleep(0.02)

set_yaw_6()
dy_walk(l, fwdkey, rightkey)
sleep(0.02)
dy_walk(l, backkey, leftkey)
sleep(0.02)
dy_walk(s, backkey, rightkey)
sleep(0.02)
ds(700)

dy_walk(h, fwdkey, rightkey)
sleep(0.05)

set_yaw_0_from_6()
