import re, sys
def check(path):
    s=open(path).read(); i=0; n=len(s); stack=[]; line=1
    while i<n:
        c=s[i]
        if c=='\n': line+=1; i+=1; continue
        if s.startswith('"""',i):
            j=s.find('"""',i+3)
            if j<0: return f"{path}: unterminated raw string at line {line}"
            line+=s.count('\n',i,j); i=j+3; continue
        if c=='"':
            i+=1
            while i<n and s[i]!='"':
                if s[i]=='\\': i+=1
                if s[i]=='\n': line+=1
                i+=1
            i+=1; continue
        if c=="'":
            i+=1
            while i<n and s[i]!="'":
                if s[i]=='\\': i+=1
                i+=1
            i+=1; continue
        if s.startswith('//',i):
            j=s.find('\n',i); i=n if j<0 else j; continue
        if s.startswith('/*',i):
            j=s.find('*/',i+2)
            if j<0: return f"{path}: unterminated block comment at line {line}"
            line+=s.count('\n',i,j); i=j+2; continue
        if c in '([{': stack.append((c,line)); i+=1; continue
        if c in ')]}':
            if not stack: return f"{path}:{line}: unexpected '{c}'"
            o,ol=stack.pop()
            if '([{'.index(o)!=')]}'.index(c):
                return f"{path}:{line}: '{c}' closes '{o}' opened at line {ol}"
            i+=1; continue
        i+=1
    if stack:
        o,ol=stack[-1]; return f"{path}: '{o}' at line {ol} never closed"
    return None

# Compose state is declared with `var x by remember...` inside the composable body, and
# Kotlin will not let anything above that line refer to it. It is an easy mistake to make
# when dropping a LaunchedEffect into a function, and the compiler is the only other thing
# that catches it, so look for a use that sits above its own declaration.
DECL = re.compile(r'^\s+var\s+(\w+)\s+by\s+remember', re.M)
FUN  = re.compile(r'^(?:@\w+\s*\n)*(?:private\s+|internal\s+)?fun\b', re.M)

def strip_noise(t):
    t = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), t, flags=re.S)
    return re.sub(r'//[^\n]*', '', t)

def early_use(path):
    src = open(path, encoding='utf-8').read()
    starts = [m.start() for m in FUN.finditer(src)] + [len(src)]
    out = []
    for a, b in zip(starts, starts[1:]):
        body = src[a:b]
        clean = strip_noise(body)
        base = src[:a].count('\n') + 1
        for m in DECL.finditer(clean):
            name, at = m.group(1), m.start()
            for u in re.finditer(rf'\b{re.escape(name)}\b', clean[:at]):
                out.append(f"line {base + clean.count(chr(10), 0, u.start())}: "
                           f"'{name}' used before its declaration on line "
                           f"{base + clean.count(chr(10), 0, at)}")
                break
    return out

# An annotation belongs to the declaration directly under it. Inserting a new function
# between the two silently reassigns it — @Composable ends up on the wrong function and
# the one that needed it loses it, which the compiler only notices much later. So check
# that every annotation is followed by something that can actually carry one.
ANNOT = re.compile(r'^\s*@(\w+)\s*(?:\(.*\))?\s*$')
CARRIER = re.compile(r'^\s*(?:@|public\s|private\s|internal\s|protected\s|inline\s|'
                  r'suspend\s|open\s|override\s|abstract\s|external\s)*'
                  r'(?:fun|val|var|class|object|interface|constructor)\b')

def orphan_annotation(path):
    out = []
    lines = open(path, encoding='utf-8').read().split('\n')
    for i, ln in enumerate(lines):
        m = ANNOT.match(ln)
        if not m:
            continue
        j = i + 1
        while j < len(lines) and (not lines[j].strip()
                                  or lines[j].lstrip().startswith(('//', '/*', '*'))):
            j += 1
        if j >= len(lines) or not CARRIER.match(lines[j]):
            out.append(f"line {i+1}: @{m.group(1)} is not attached to a declaration "
                       f"(line {j+1} is {lines[j].strip()[:40]!r})")
    return out

# The compiler's own rule: a function that calls a composable must itself be @Composable.
# Inserting a function between an annotation and the function it belonged to silently moves
# it, so the one that needed it loses it. Only calls at the top level of a function body
# count — inside an `item { }` lambda the context is composable again, which is exactly how
# a LazyListScope extension is allowed to call Text without being annotated itself.
COMPOSE = ("Text", "Row", "Column", "Box", "Surface", "Spacer", "LazyColumn", "LazyRow",
           "Icon", "Button", "OutlinedButton", "TextButton", "Switch", "Slider", "Scaffold",
           "AnimatedVisibility", "Canvas", "Image", "Divider", "HorizontalDivider")
CALL = re.compile(r'^\s*(?:[\w.]+\s*=\s*)?(' + "|".join(COMPOSE) + r')\s*\(')
FUNC = re.compile(r'^(\s*)(?:public |private |internal |protected |inline |suspend |'
                  r'open |override |abstract )*fun\b')

def missing_composable(path):
    lines = strip_noise(open(path, encoding="utf-8").read()).split("\n")
    out, i = [], 0
    while i < len(lines):
        m = FUNC.match(lines[i])
        if not m or "{" not in lines[i] and not lines[i].rstrip().endswith("("):
            i += 1; continue
        # is it annotated? look back over the annotation block
        j, ann = i - 1, False
        while j >= 0 and (not lines[j].strip() or lines[j].lstrip().startswith("@")):
            if lines[j].strip() == "@Composable": ann = True
            j -= 1
        name = re.search(r'fun\s+([\w.]+)', lines[i])
        name = name.group(1) if name else "?"
        # walk the body, counting braces, and look at depth 1 only
        depth, k, started = 0, i, False
        while k < len(lines):
            ln = lines[k]
            if started and depth == 1 and CALL.match(ln) and not ann:
                out.append(f"line {k+1}: {name} calls {CALL.match(ln).group(1)} "
                           f"but is not marked @Composable")
                break
            depth += ln.count("{") - ln.count("}")
            if "{" in ln: started = True
            if started and depth <= 0: break
            k += 1
        i = max(k, i + 1)
    return out

bad=0
for p in sys.argv[1:]:
    r=(check(p) or (early_use(p) or [None])[0] or (orphan_annotation(p) or [None])[0]
       or (missing_composable(p) or [None])[0])
    print(f"  {'FAIL' if r else 'ok  '}  {p.split('/')[-1]}" + (f"\n        {r}" if r else ""))
    bad += 1 if r else 0
sys.exit(1 if bad else 0)
