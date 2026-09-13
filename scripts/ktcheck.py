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

bad=0
for p in sys.argv[1:]:
    r=check(p) or (early_use(p) or [None])[0]
    print(f"  {'FAIL' if r else 'ok  '}  {p.split('/')[-1]}" + (f"\n        {r}" if r else ""))
    bad += 1 if r else 0
sys.exit(1 if bad else 0)
