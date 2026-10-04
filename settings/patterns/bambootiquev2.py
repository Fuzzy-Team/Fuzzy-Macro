# Ahk code converted by Fuzzy Macro

# Scale movement for the configured field size and use the macro's keyboard API.
if sizeword.lower() == "xs":
    size = 0.25
elif sizeword.lower() == "s":
    size = 0.5
elif sizeword.lower() == "l":
    size = 1
elif sizeword.lower() == "xl":
    size = 1.25
else:
    size = 0.75

size = size / 5.5
nm_walk = self.keyboard.walk
fwdkey = tcfbkey
backkey = afcfbkey
leftkey = tclrkey
rightkey = afclrkey

# lemme cook
nm_walk(rightkey, 8 * size)
nm_walk(fwdkey, 5 * size)
nm_walk(backkey, 1 * size)
nm_walk(leftkey, 3 * size)
nm_walk(backkey, 4 * size)
for i in range(width):
	# going
	nm_walk(fwdkey, 8 * size)
	nm_walk(leftkey, 2 * size)
	nm_walk(backkey, 8 * size)
	nm_walk(leftkey, 2 * size)
	nm_walk(fwdkey, 8 * size)
	nm_walk(leftkey, 2 * size)
	nm_walk(backkey, 8 * size)
	nm_walk(leftkey, 2 * size)
	nm_walk(fwdkey, 8 * size)
	nm_walk(leftkey, 2 * size)
	nm_walk(backkey, 8 * size)
	nm_walk(rightkey, 10 * size)
