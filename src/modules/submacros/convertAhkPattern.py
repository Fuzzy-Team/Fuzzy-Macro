import re

generalReplace = {
    ":=": "𑑛",
    "reps": "width",
    "'": '"',
    "sqrt": "math.sqrt",
    "\ufeff":"",
    "a_index":"i",
    "&&": "and",
    ";": "#",
    "||": "or",
    "static": "",
}

rotationKeys = {"left": "rotleft", "right": "rotright", "up": "rotup", "down": "rotdown"}

def splitTopLevel(text):
    """Split on commas that are outside parentheses and quotes."""
    parts, depth, quoted, start = [], 0, False, 0
    for i, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif quoted:
            continue
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return parts

def splitComment(text):
    """Split a line at the first # that is outside quotes into (code, comment)."""
    quoted = False
    for pos, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            code = text[:pos].rstrip()
            return code, ("  " + text[pos:]) if code else text[pos:]
    return text, ""

def stripOuterParentheses(text):
    """Remove parentheses that wrap the whole expression, including nested pairs."""
    text = text.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        quoted = False
        encloses = True
        for index, char in enumerate(text):
            if char == '"':
                quoted = not quoted
            elif quoted:
                continue
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    if index != len(text) - 1:
                        encloses = False
                    break
        if not encloses or quoted or depth != 0:
            break
        text = text[1:-1].strip()
    return text

def splitTernary(text):
    """Split a quote-aware one-line ternary into condition and both arms.

    Each top-level `?` raises ternaryDepth, so it waits for its own `:`:
    `a ? b ? 1 : 2 : 3` pairs the inner `?` with the inner `:`.
    """
    text = stripOuterParentheses(text)
    question = None
    depth = 0
    ternaryDepth = 0
    quoted = False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif quoted:
            continue
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "?" and depth == 0:
            if question is None:
                question = index
            ternaryDepth += 1
        elif char == ":" and depth == 0 and question is not None:
            ternaryDepth -= 1
            if ternaryDepth == 0:
                return (
                    text[:question].strip(),
                    text[question + 1:index].strip(),
                    text[index + 1:].strip(),
                )
    return None

def hasUnmatchedTernary(text):
    """True when an unquoted `?` has no `:` at the same bracket depth.

    A `?` inside brackets belongs to a sub-expression this converter does not
    rewrite, so it is only reported when it cannot be paired at all.
    """
    questions = []
    depth = 0
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
        elif quoted:
            continue
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(depth - 1, 0)
        elif char == "?":
            if len(questions) <= depth:
                questions.extend([0] * (depth + 1 - len(questions)))
            questions[depth] += 1
        elif char == ":" and depth < len(questions) and questions[depth]:
            questions[depth] -= 1
    return any(questions)

def convertTernary(text):
    """Convert an AHK one-line ternary to Python, recursing into both arms.

    Returns None when the text has no ternary, and raises ValueError when an
    unquoted `?` cannot be paired, so malformed input is not written as a
    successful conversion.
    """
    ternary = splitTernary(text)
    if ternary is None:
        if hasUnmatchedTernary(text):
            raise ValueError(f"Invalid ternary expression: {text}")
        return None
    conditionSection, trueSection, falseSection = ternary
    truePython = convertTernary(trueSection)
    falsePython = convertTernary(falseSection)
    # The true arm of a Python conditional must be parenthesised when it is
    # itself conditional, otherwise Python's right-associative parsing would
    # attach the outer `if` to the inner expression.
    trueResult = f"({truePython})" if truePython is not None else trueSection
    falseResult = f"({falsePython})" if falsePython is not None else falseSection
    return f"{trueResult} if {conditionSection} else {falseResult}"

def convertCall(statement):
    """Python lines for one nm_walk, nm_camerarotation or sleep call. None for any other statement."""
    match = re.fullmatch(r"(nm_walk|nm_camerarotation|sleep)\((.*)\)", statement)
    if not match:
        return None
    name, args = match.group(1), splitTopLevel(match.group(2))
    if name == "sleep":
        return [f"sleep(({args[0]}) / 1000)"]
    if name == "nm_camerarotation":
        return [f"for _ in range({args[1]}):", f"\tself.keyboard.press({rotationKeys[args[0].strip(chr(34))]})"]
    #keys are split on spaces too, so a missing comma between two keys still holds both
    keys = " ".join(args[1:]).split()
    return ([f"self.keyboard.keyDown({key}, False)" for key in keys]
        + [f"self.keyboard.tileWait({args[0]})"]
        + [f"self.keyboard.keyUp({key}, False)" for key in keys])

def convertSleep(statement):
    """Python sleep call for a command-style Sleep, or None for anything else."""
    # Only sleep(...), sleep, ... or sleep ... are commands. The lookahead keeps
    # sleep := 500, sleep += 1 and similar assignments untouched.
    match = re.match(r"^sleep(?=\s*,|\s+|\s*\()", statement)
    if not match:
        return None
    argument = statement[match.end():]
    argument = re.sub(r"^\s*,?\s*", "", argument, count=1).strip()
    # An assignment or comparison is not a Sleep argument. This also covers
    # every compound assignment (//=, %=, <<=, ...) and ==/!=/<=/>=.
    if re.match(r"^(?:𑑛|:=|=|(?:\+|-|\*|/|//|%|&|\||\^|<<|>>)=|<|>|!)", argument):
        return None
    # AHK v1 dereference: Sleep, %delay% -> delay. Concatenations such as
    # %n%000 deliberately do not match and keep their percent signs.
    argument = re.sub(r"^%\s*([a-zA-Z_]\w*)\s*%$", r"\1", argument)
    # AHK v1 expression prefix: Sleep, % delay + 500 -> delay + 500.
    argument = re.sub(r"^%\s+(.+)$", r"\1", argument).strip()
    if not argument:
        return None
    return f"sleep(({argument}) / 1000)"

def convertCondition(text):
    """Rewrite the AHK-only operators left in a condition into Python.

    `=`, `&&` and `||` are already handled by the global replacements; `!`,
    `!=` and `<>` need lookahead, and quoted text must keep its contents.
    """
    out = []
    quoted = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            quoted = not quoted
        elif quoted:
            pass
        elif text.startswith("<>", index):
            out.append("!=")
            index += 2
            continue
        elif char == "!" and not text.startswith("=", index + 1):
            out.append("not ")
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)

def ahkPatternToPython(ahk):

    def checkOrder(string, pattern):
        i, j = 0, 0
        for char in string:
            if char == pattern[j]:
                j += 1
            if j == len(pattern):
                return True
            i += 1
     
        return False
    
    #set to lowercase
    ahk = ahk.lower()
    
    #do replacements
    for k, v in generalReplace.items():
        ahk = ahk.replace(k,v)

    # Convert standalone equality to ==, leaving comparisons, compound
    # assignments, ==, and => untouched.
    ahk = re.sub(r'(?<![=!<>+\-*/%&|^])=(?![=>])', '==', ahk)
    # Convert dir/Dir/Dir<digits> identifiers without touching words like direction.
    ahk = re.sub(r'\bdir(\d*)\b', r'direc\1', ahk)

    #convert into lines
    #comments and identations
    ahkCleaned = [x.split(";")[0].strip() for x in ahk.split("\n")]
    #remove empty lines
    ahkCleaned = [x for x in ahkCleaned if x]
    #auto indent
    #remove single close brackets
    out = []
    level = 0
    for line in ahkCleaned:
        code, _ = splitComment(line)
        if code == "}":
            level -= 1
            continue
        if code.startswith("}"):
            level -= 1
        out.append("{}{}".format("\t"*level, line))
        if code.endswith("{"):
            level += 1
    #extract out only the pattern code
    start = None
    end = None
    for i,e in enumerate(out):
        if "patterns[" in e:
            start = i+2
        elif e == ')"':
            end = i
    if not start is None and not end is None:
        out = out[start:end]
    
    #convert ahk to python
    #a stack of control frames tracks braced and unbraced conditionals/loops, so an
    #else or else if can continue a chain that is still open at the same level
    #tabs: indentation this frame adds, mode: need_stmt -> child -> done, or block while a brace is open
    stack = []
    for i,e in enumerate(out[:]):
        baseLevel = len(e) - len(e.lstrip("\t"))
        line = e.strip()
        code, comment = splitComment(line)

        if code:
            isElseHeader = bool(re.match(r"^\}?\s*(?:else\s+if|elseif|else)\b", code))
            isIfHeader = bool(re.match(r"^\}?\s*(?:if|else\s+if|elseif)\b", code))
            isLoopHeader = bool(re.match(r"^(?:loop|\}?\s*while)\b", code))
            isHeader = isIfHeader or isElseHeader or isLoopHeader
            hasOpenBrace = code.endswith("{")

            #close the frames this line has dedented out of
            while stack and baseLevel < stack[-1]["base"]:
                stack.pop()
                while stack and stack[-1]["mode"] == "child":
                    if baseLevel < stack[-1]["base"]:
                        stack.pop()
                    else:
                        stack[-1]["mode"] = "done"
            for frame in stack:
                if frame["mode"] == "block" and baseLevel <= frame["base"]:
                    frame["mode"] = "done"

            #a done frame can still be continued by an else at its own level, otherwise it ends
            if isElseHeader:
                while stack and stack[-1]["mode"] == "done" and not (stack[-1]["can_else"] and stack[-1]["base"] == baseLevel):
                    stack.pop()
                    if stack and stack[-1]["mode"] == "child":
                        stack[-1]["mode"] = "done"
                if stack and stack[-1]["mode"] == "done" and stack[-1]["can_else"] and stack[-1]["base"] == baseLevel:
                    #consumed by this else/else if continuation, its parent stays in mode == "child"
                    stack.pop()
            else:
                while stack and stack[-1]["mode"] == "done":
                    stack.pop()
                    if stack and stack[-1]["mode"] == "child":
                        stack[-1]["mode"] = "done"

        extraTabs = sum(f["tabs"] for f in stack if f["mode"] != "done")
        if extraTabs:
            e = "\t"*extraTabs + e
            out[i] = e
        indent = e[:len(e) - len(e.lstrip("\t"))]

        if code:
            #the statement controlled by an unbraced header is this line, or the header itself
            if stack and stack[-1]["mode"] == "need_stmt":
                if isHeader or hasOpenBrace:
                    stack[-1]["mode"] = "child"
                else:
                    stack[-1]["mode"] = "done"
            #an unbraced header indents its whole statement, even a braced block
            if isHeader or hasOpenBrace:
                stack.append({
                    "base": baseLevel,
                    "tabs": 0 if hasOpenBrace else 1,
                    "mode": "block" if hasOpenBrace else "need_stmt",
                    "can_else": isIfHeader,
                })

        noSpaces = code.replace(" ","")
        
        #replace loop
        if noSpaces == 'loop"width"{' or noSpaces == 'loopwidth{':
            out[i] = indent + 'for i in range(width):' + comment
        elif code.startswith("loop"):
            #loop number of times
            digits = ''.join([x for x in code if x.isdigit()])
            if digits:
                out[i] = indent + f'for i in range({int(digits)}):' + comment
        #convert nm_walk, nm_cameraRotation and sleep, including several on one line separated by commas
        elif re.match(r"(nm_walk|nm_camerarotation|sleep)\(", code):
            converted = []
            for statement in splitTopLevel(code):
                call = convertCall(statement)
                if call is None:
                    #not a whole call, e.g. sleep(a + b) * 2 or x := 1 after a comma
                    sleepCall = convertSleep(statement)
                    call = [sleepCall] if sleepCall else [statement]
                converted += call
            out[i] = indent + ("\n" + indent).join(converted) + comment
        elif re.match(r"sleep\b", code):
            sleepCall = convertSleep(code)
            if sleepCall:
                out[i] = indent + sleepCall + comment
        #convert send
        elif line.startswith("send"):
            cmds = []
            lineCopy = line
            while True:
                openB = lineCopy.find("{")
                closeB = lineCopy.find("}", openB + 1) if openB != -1 else -1
                if openB == -1 or closeB == -1:
                    identation = leading_spaces = len(e) - len(e.lstrip())
                    out[i] = e.replace(line, "\n{}".format(identation*"\t").join(cmds))
                    break
                add = lineCopy[openB:closeB+1]
                lineCopy = lineCopy.replace(add,"",1)
                add = add[1:-1].strip()
                if not add:
                    continue
                #remove whitespace between quotations
                add = re.sub(r'"\s*([^"]*?)\s*"', r'"\1"', add)
                #split into parameters
                args = add.split(" ")
                #get key
                key = args[0]
                #check if variable 
                if (key[0] == '"' and key[-1] == '"') or (key[0] == '%' and key[-1] == '%'):
                    key = key[1:-1]
                    #check for weird variable string thing that ahk can do
                    if key.count("%") == 2:
                        # Use regex to find text between %%
                        varNames = re.findall(r'%([^%]+)%', key)
                        # Remove the varNames from the input string
                        nonVarString = re.sub(r'%[^%]+%', '', key)
                        #use locals to access variables as a string
                        key = "locals[f'" + nonVarString + ''.join(["{" + x + "}" for x in varNames]) + "']"
                else:
                    key = f'"{key}"'
                #get command, a key with no count is pressed once
                command = args[1] if len(args) > 1 else "1"
                if command == "up":
                    cmds.append(f"self.keyboard.keyUp({key}, False)")
                elif command == "down":
                    cmds.append(f"self.keyboard.keyDown({key}, False)")
                elif command.isdigit():
                    for _ in range(int(command)):
                        cmds.append(f"self.keyboard.press({key})")
                else: #its probably a variable
                    var = command.replace('"', "").replace("%", "")
                    cmds.append(f"for _ in range({var}):")
                    cmds.append(f"\tself.keyboard.press({key})")
                
        #deal with waits
        elif line.startswith("walk"):
            out[i] = e.replace("walk", "self.keyboard.tileWait").replace('"',"")
        #if/else statements
        elif code.startswith("if"):
            #a braced if drops its brace, an unbraced one controls the next statement
            head = code[:-1].rstrip() if code.endswith("{") else code
            out[i] = indent + head + ":" + comment

        elif re.match(r"^\}?\s*(?:else\s+if|elseif)\b", code):
            elifLine = re.sub(r"^\}?\s*(?:else\s+if|elseif)\b", "elif", code, count=1)
            if elifLine.endswith("{"):
                elifLine = elifLine[:-1].rstrip()
            out[i] = indent + elifLine + ":" + comment

        elif "else" in code and not "if" in code:
            out[i] = indent + "else:" + comment
        #while loops use the same expression syntax as if, so normalise the
        #condition instead of emitting AHK operators into Python
        elif re.match(r"^\}?\s*while\b", code):
            condition = re.sub(r"^\}?\s*while\b", "", code, count=1).strip()
            if condition.endswith("{"):
                condition = condition[:-1].rstrip()
            #`while := ...` is an assignment to a variable named while, not a loop
            if condition and not condition.startswith("𑑛"):
                out[i] = indent + f"while {convertCondition(condition)}:" + comment
        #one line if/else statements
        elif convertTernary(code.partition("𑑛")[2] if "𑑛" in code else code) is not None:
            lhs, separator, _ = code.partition("𑑛")
            replacement = convertTernary(code.partition("𑑛")[2] if "𑑛" in code else code)
            if separator:
                replacement = f"{lhs}{separator} {replacement}"
            out[i] = indent + replacement + comment
        #function definition
        elif checkOrder(line, "(){") and not checkOrder(line, "𑑛(){"):
            out[i] = "def " + out[i].replace("{", ":")
            
        
    out.insert(0, "#Ahk code converted by Fuzzy Macro\n\n")
    return "\n".join(out).replace("𑑛", "=")

test = '''

;@NoInterrupt
CameraRot(Dir, Num) {
	Static rot := false
	Static LRNum := 0
	Static LRDir := "Right"
	Init := OnExit((*) => rot && send("{" Rot%LRDir% " " Abs(LRNum) "}"), -1) 
	send "{" Rot%Dir% " " Num "}"
	rot := (dir = "Up" || dir = "Down" || dir = "Left" || dir = "Right")
	if (Dir="Left" || Dir="Right") {
		LRNum := (Dir="Left") ? LRNum+Num : LRNum-Num
		LRDir := (LRNum<0) ? "Right" : "Left"
	}
}
;function created by Kuruni and SP

Move(Dir, Dis, Dir2:="") {
	DirType := (Dir2!="")
	send "{" Dir " down}"
	if (DirType)
		send "{" Dir2 " down}"
	Walk(Dis)
	send "{" Dir " up}"
	if (DirType)
		send "{" Dir2 " up}"
}
;function created by Kuruni

loop reps {
	Move("s", 4)
	Move("d", 12)
	Move("w", 4, "a")
	Move("a", 8)
	Move("s", 4, "d")
	Move("a", 1)

	CameraRot("Right", 1)
	
	Move("w", 7)
	Move("s", 7, "d")
	Move("w", 5, "d")
	Move("a", 7)
	Move("w", 5, "d")
	Move("s", 7)
	Move("a", 10, "s")
	
	CameraRot("Right", 1)
	
	Move("w", 10)
	Move("a", 5, "s")
	Move("d", 5, "s")
	
	CameraRot("Left", 2)
	
}
'''
#print(ahkPatternToPython(test))

