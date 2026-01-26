#Ahk code converted by Fuzzy Macro


#lemme cook
nm_walk(8, rightkey)
nm_walk(5, fwdkey)
nm_walk(1, backkey)
nm_walk(3, leftkey)
nm_walk(4, backkey)
for i in range(width):
	#going
	nm_walk(8, fwdkey)
	nm_walk(2, leftkey)
	nm_walk(8, backkey)
	nm_walk(2, leftkey)
	nm_walk(8, fwdkey)
	nm_walk(2, leftkey)
	nm_walk(8, backkey)
	nm_walk(2, leftkey)
	nm_walk(8, fwdkey)
	nm_walk(2, leftkey)
	nm_walk(8, backkey)
	nm_walk(10, rightkey)