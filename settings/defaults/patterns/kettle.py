#original code by dully176

# drift comp settings.
crfdc = 0.3    # corner fdc.
dwalign = 0.3  # diamond wall align.
dwdrift = 0.5  # diamond wall drift align.
hwalign = 0.2  # honey wall align.
hwdrift = 0.4  # honey wall drift aling.
# advanced settings.
digi = False   # digi stops.
#for i in range(2): idk why this here

step = 0.5

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

l = step*size     # long walk.
s = l/4        # short walk.
h = l/2        # half of long walk. (do not change)
# digi stop setting overwrite.
# do not change unless you know what you"re doing.
# electro doenst know what hes doing

self.keyboard.press(rotup)
self.keyboard.press(rotup)
self.keyboard.press(rotup)
self.keyboard.press(rotup)
sleep(0.05)


def dy_walk(leng, dir1, dir2 = None): #Electro too lazy to change from ahk to py
    if dir2 is None:
        self.keyboard.walk(dir1, leng)
    else:
        self.keyboard.multiWalk([dir1, dir2], leng)

stop = [False, digi]
for stops in stop:
    dy_walk(h, leftkey)
    dy_walk(s, fwdkey)
    dy_walk(l, rightkey)
    dy_walk(s, fwdkey)
    dy_walk(l, leftkey)
    self.keyboard.press(rotleft)
    sleep(0.05)
    dy_walk(l, backkey, leftkey)
    if dwalign > 0 :
        dy_walk(dwalign+dwdrift, backkey, leftkey)
        dy_walk(dwalign, fwdkey, rightkey)
        if stops:
            sleep(0.8)
    dy_walk(s, backkey, rightkey)
    dy_walk(l, fwdkey, rightkey)
    dy_walk(s, backkey, rightkey)
    dy_walk(h, backkey, leftkey)
    self.keyboard.press(rotright)
    sleep(0.05)
    dy_walk(h, backkey)
    dy_walk(s, rightkey)
    dy_walk(l, fwdkey)
    dy_walk(s, rightkey)
    if hwalign > 0 :
        dy_walk(hwalign+hwdrift, rightkey)
        dy_walk(hwalign, leftkey)
        if stops:
            sleep(0.8)
    dy_walk(l, backkey)
    self.keyboard.press(rotleft)
    self.keyboard.press(rotleft)
    sleep(0.05)
    dy_walk(l, fwdkey)
    dy_walk(s, rightkey)
    dy_walk(l, backkey)
    dy_walk(s, rightkey)
    dy_walk(h, fwdkey)
    self.keyboard.press(rotright)
    self.keyboard.press(rotright)
    sleep(0.05)
    # shape two (diagonal)
    dy_walk(h, fwdkey, leftkey)
    if stops:
        sleep(0.8)
    dy_walk(s, fwdkey, rightkey)
    dy_walk(l, backkey, rightkey)
    dy_walk(s, fwdkey, rightkey)
    dy_walk(l, fwdkey, leftkey)
    self.keyboard.press(rotleft)
    sleep(0.05)
    dy_walk(l, leftkey)
    dy_walk(s+crfdc, backkey)
    dy_walk(l, rightkey)
    dy_walk(s+crfdc, backkey)
    dy_walk(h, leftkey)
    self.keyboard.press(rotright)
    sleep(0.05)
    dy_walk(h, backkey, leftkey)
    dy_walk(s, backkey, rightkey)
    dy_walk(l, fwdkey, rightkey)
    dy_walk(s, backkey, rightkey)
    dy_walk(l, backkey, leftkey)
    self.keyboard.press(rotleft)
    self.keyboard.press(rotleft)
    sleep(0.05)
    dy_walk(l, fwdkey, rightkey)
    dy_walk(s, backkey, rightkey)
    dy_walk(l, backkey, leftkey)
    dy_walk(s, backkey, rightkey)
    if stops:
        sleep(0.8)
    dy_walk(h, fwdkey, rightkey)
    self.keyboard.press(rotright)
    self.keyboard.press(rotright)
    sleep(0.05)
    
self.keyboard.press(rotdown)
self.keyboard.press(rotdown)
self.keyboard.press(rotdown)
self.keyboard.press(rotdown)
sleep(0.05)

#dy_walk(t, d, s=nm_walk(t,d,s) if 0) => (s else nm_walk(t,d),sleep(20),0)
#(send("{o 5}"),sleep(ms)) if ds(ms) => (digi else 0,0)

#converted by Electro3.14 (never doing this again :sob:)