import sys, re
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
bad=0
for p in sys.argv[1:]:
    r=check(p)
    print(f"  {'FAIL' if r else 'ok  '}  {p.split('/')[-1]}" + (f"\n        {r}" if r else ""))
    bad += 1 if r else 0
sys.exit(1 if bad else 0)
