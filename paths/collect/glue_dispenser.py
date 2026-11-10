self.keyboard.slowPress("e")
sleep(0.52)
self.keyboard.keyDown("w")
self.keyboard.slowPress("space")
self.keyboard.slowPress("space")
sleep(5.35)
self.keyboard.keyUp("w")
time.sleep(2.2)
self.keyboard.walk("w", 1.7)


self.keyboard.walk("w",1.037)
if True:
    # Allow using the gumdrop quickslot instead of searching the inventory
    use_slot = False
    try:
        use_slot = bool(self.setdat.get("glue_dispenser_use_gumdrop_slot", False))
    except Exception:
        use_slot = False

    if use_slot:
        # perform approach movements then press the configured gumdrop slot
        self.keyboard.walk("a",1.4)
        self.keyboard.walk("w",0.15)
        self.keyboard.walk("a",0.3)
        time.sleep(0.3)
        self.keyboard.walk("w",0.1)
        slot = self.setdat.get("goo_slot", 2)
        self.keyboard.press(str(slot))
        self.canDetectNight = False #dont let night be detected inside gummy bear's lair
        time.sleep(2)
        self.keyboard.walk("w",2.5)
        time.sleep(0.5)
        self.canDetectNight = True
    else:
        itemCoords = self.findItemInInventory("gumdrops")
        if itemCoords is not None:
            self.keyboard.walk("a",1.4)
            self.keyboard.walk("w",0.15)
            self.keyboard.walk("a",0.3)
            time.sleep(0.3)
            self.keyboard.walk("w",0.1)
            self.useItemInInventory(x=itemCoords[0], y=itemCoords[1])
            self.canDetectNight = False #dont let night be detected inside gummy bear's lair
            time.sleep(2)
            self.keyboard.walk("w",2.5)
            time.sleep(0.5)
            self.canDetectNight = True

