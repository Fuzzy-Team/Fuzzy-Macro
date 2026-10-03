field_name = str(globals().get("field", "")).replace("_", " ").lower()
field_sizes = {
    "sunflower": (33, 20), "dandelion": (36, 18), "mushroom": (32, 23),
    "blue flower": (43, 17), "clover": (29, 26), "strawberry": (22, 26),
    "spider": (28, 26), "bamboo": (39, 18), "pineapple": (33, 23),
    "stump": (11, 9), "cactus": (33, 18), "pumpkin": (33, 17),
    "pine tree": (31, 23), "rose": (31, 20), "mountain top": (24, 28),
    "pepper": (27, 21), "coconut": (30, 21),
}

field_width, field_height = field_sizes.get(field_name, (30, 20))
padding = 4
travel_width = max(4, field_width - (padding * 2))
travel_height = max(4, field_height - (padding * 2))
align_width = max(2, (field_width / 2) - padding)
align_height = max(2, (field_height / 2) - padding)

scale = {"xs": 0.5, "s": 0.75, "m": 1.0, "l": 1.25, "xl": 1.5}.get(
    str(sizeword).lower(), 1.0
)
side = max(0.2, 0.18 * scale)
long = max(0.35, 0.18 * scale)

def walk(key, distance):
    self.keyboard.walk(key, distance * 0.22)

def phase():
    for _ in range(max(1, int(width))):
        walk(tcfbkey, long * 5)
        walk(tclrkey, side)
        walk(afcfbkey, long * 5)
        walk(tclrkey, side)
        walk(tcfbkey, long * 5)
        walk(afclrkey, side * 2)
        walk(afcfbkey, long * 5)
        walk(afclrkey, side)

phase()
