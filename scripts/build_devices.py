"""
Parametric device library: nanosheet, forksheet, CFET (monolithic + sequential),
plus a to-scale footprint comparison cell.  All dimensions in nanometres.
  x : source -> drain (gate-length direction)
  y : vertical  (stacking direction)
  z : cell-width direction  (n-to-p direction)
Everything is an axis-aligned box.  Conformal films are built as separate
plates so each device tiles exactly: no overlapping solids, no gaps.
"""
import json, os
import numpy as np

# ---------------------------------------------------------------- materials
MAT = {
 "silicon": dict(label="Silicon (Si)",       color="#F2C2CF", note="Channels, substrate, sub-fins and Si source/drain epitaxy; each part names its doping. Doping and strain are not modeled"),
 "sige":    dict(label="Silicon-germanium (SiGe)", color="#B37FA0", note="SiGe layers and SiGe:B source/drain; each part names its Ge content where the patent gives one"),
 "sio2":    dict(label="Silicon oxide (SiO₂)", color="#8C1C13", note="STI, interfacial layers, BOX and isolation oxides; each part names its role"),
 "highk":   dict(label="Hafnium dioxide (HfO₂)", color="#BE8250", note="High-κ gate dielectric, drawn as HfO₂: every patent followed lists Hf-based oxides among its options; relative permittivity 22 is a model assumption"),
 "si3n4":   dict(label="Silicon nitride (SiN)", color="#E4AE1B", note="Spacers, liners, caps, etch stops and gate-cut fills; each part names its role and the patent it follows"),
 "sibcn":   dict(label="SiBCN (low-κ spacer film)", color="#D8C06A", note="Boron- and carbon-doped silicon nitride: the nanosheet patent's spacer and bottom-isolation film [R13], the forksheet patent's gate spacer [R31] and the monolithic CFET patent's spacer material [R33]"),
 "lowk":    dict(label="Low-κ dielectric", color="#9FB6C8", note="A low-κ film the patent names without one composition (inner spacers, isolation, ILD): SiOCN-class, drawn as one material"),
 "alox":    dict(label="Aluminium oxide (AlOₓ)", color="#C9D4DE", note="The FinFET's gate hard mask [R29], the nanosheet's protective liner [R13] and the sequential CFET's etch stop [R34]"),
 "soc":     dict(label="Spin-on carbon (SOC)", color="#4A4A57", note="The FinFET's dummy contact material, about 50–95 % carbon, baked and planarised, then replaced by ILD and contacts [R29]"),
 "wall":    dict(label="SiN dielectric wall", color="#7A8AA0", note="The forksheet's insulating wall between the n and p stacks, and the contact partition wall on it: SiN in the imec forksheet patent the Device follows [R31]; other forksheet patents use other walls, such as a high-κ/low-κ bilayer [R32]"),
 "siu":     dict(label="Undoped Si (growth region)", color="#D8C3CB", note="Undoped Si grown in the source/drain openings from the seed layer, under the doped source/drain (Si/Si CMOS route, R28)"),
 "sic":     dict(label="SiC:P (n-type source/drain)", color="#EFB7A6", note="Phosphorus-doped SiC epitaxy, one n-type source/drain example R28 gives; composition and doping illustrative"),
 "cellmark":dict(label="Cell boundary",      color="#5C6B80", note="Drawing marker for the standard cell's edge; not a material"),
 "mdi":     dict(label="Middle-tier dielectric", color="#4E7F8C", note="Isolation role, not a specified compound; relative permittivity 4.2 assumed"),
 "bond":    dict(label="Bonding oxide (SiO₂)", color="#8FB6C0", note="The sequential CFET's bond layers, SiO₂ fusion-bonded [R34]"),
 "wfill":   dict(label="Tungsten (W) · gate fill", color="#A7A1CB", note="Gate fill metal: W in the nanosheet [R13], forksheet [R31][R32] and monolithic CFET [R33] patents; the sequential CFET patent names none, so W is the model's choice there"),
 "cofill":  dict(label="Cobalt (Co) · gate fill", color="#E7955A", note="The FinFET's gate electrode fill: Co is on its patent's gate-electrode list (TiN, TaN, TaC, Co, Ru, Al) [R29]"),
 "mo":      dict(label="Molybdenum (Mo) · gate fill", color="#E3D3B0", note="Gate fill of the Si/Si design, whose application names none: the model's choice"),
 "cobalt":  dict(label="Cobalt (Co)",        color="#EE7A1A", note="Contact conductor. Co in a TiN liner is one of the FinFET patent's contact options [R29]; elsewhere Co is the model's choice where a patent names no metal"),
 "tungsten":dict(label="Tungsten (W)",       color="#BFBBD2", note="Contact, via and plug conductor: the forksheet patents' contact fill [R31][R32], the CFET patents' contacts and plugs [R33][R34]"),
 "copper":  dict(label="Copper (Cu)",        color="#D98B4A", note="The sequential CFET's inter-metal line between the tiers and its interconnect lines [R34]"),
 "tiox":    dict(label="Titanium oxide (TiOₓ)", color="#B8C4A0", note="The monolithic CFET's sacrificial spacer 810 beside the lower source/drain; removed where a contact reaches the lower tier, left in place elsewhere [R33]"),
 "tisi":    dict(label="Titanium silicide (TiSiₓ)", color="#E6E2F0", note="Contact silicide formed through the contact opening; each part names its patent's wording. Thickness illustrative"),
 "tin":     dict(label="Titanium nitride (TiN)", color="#BE5518", note="The p-type work-function metal in every patent followed, and a contact liner or barrier where the patent names one. Effective work function is not modeled"),
 "nwf":     dict(label="n-type work-function metal (Al-containing)", color="#3E9C8F", note="TiAlC or TiAl in the forksheet and CFET patents, an Al-containing layer from the FinFET patent's list, the nanosheet patent's n-type metal; effective work function is not modeled"),
 "ild":     dict(label="Interlayer dielectric (ILD)", color="#C9776C", note="Dielectric around the device during processing; each step names the patent's material. Left out of the finished models, as their notes say"),
 "poly":    dict(label="Si dummy gate (poly/amorphous)", color="#8FA67A", note="Placeholder gate in the process steps; removed before the metal gate goes in"),
 "pts":     dict(label="p-type Si (punch-through stopper)", color="#D9A6C8", note="Implanted doping under the nFET channels; extent illustrative, real profiles are graded"),
 "pts_n":   dict(label="n-type Si (punch-through stopper)", color="#A7B8E4", note="Implanted doping under the pFET region; extent illustrative, real profiles are graded"),
 "barc":    dict(label="BARC (bottom anti-reflective coating)", color="#6B5B7A", note="Bottom layer of the tri-layer photoresist over the SOC [R29]"),
 "sihm":    dict(label="Si-containing hard mask", color="#9AA7B8", note="Middle layer of the tri-layer photoresist, the mask the SOC is etched through [R29]"),
 "resist":  dict(label="Photoresist or OPL mask", color="#F08A3C", note="Light-sensitive film for patterning, or an organic planarisation layer used as a block mask; each part names which"),
 "resist_exp": dict(label="Photoresist (exposed)", color="#F9D4B4", note="Resist made soluble by exposure; the developer removes it (positive tone)"),
 "chrome":  dict(label="Reticle chrome (not to scale)", color="#8E959E", note="The reticle's opaque pattern. It sits in the scanner, not on the wafer; drawn above it only to show what blocks the light"),
 "liner":   dict(label="Protective liner", color="#6FC7B5", note="Thin film that protects one region while the other is processed; each part names the patent's material"),
 "mandrel": dict(label="Mandrel (first core)", color="#5E86C1", note="Temporary core line whose sidewalls carry the spacers; removed after they form. The SAQP patent's mandrels are amorphous or polycrystalline Si [R30]"),
 "mandrel2": dict(label="Second core", color="#9A7ED3", note="SAQP's second-generation core, cut from the first spacer image; removed after its own spacers form [R30]"),
 "patspacer": dict(label="Patterning spacer (temporary mask)", color="#EDEFF2", note="Spacer film used only as an etch mask for pitch splitting; not a transistor spacer. SiN in the SAQP patent's example [R30]"),
 # --- schematic-layout palette, used by the showcase inverters ---
 "pwell":   dict(label="P Well",             color="#7FC9EA", note="p-type well / substrate"),
 "nwell":   dict(label="N Well",             color="#EFE53A", note="n-type well under the pMOS"),
 "fox":     dict(label="SiO₂ (field)",       color="#C7CBD0", note="Field oxide the devices sit on"),
 "nanowire":dict(label="Channel (schematic Si)", color="#C08A2E", note="Layout role: fins or representative nanosheets; not a material called nanowire"),
 "md":      dict(label="MD",                 color="#4FAE4F", note="Source/drain contact"),
 "po":      dict(label="Po · gate role",      color="#3B41CF", note="Schematic gate electrode; label does not imply a polysilicon final gate"),
 "vd":      dict(label="VD",                 color="#8E1C1C", note="Via, MD to Metal 0"),
 "vg":      dict(label="VG",                 color="#F5E93B", note="Via, gate to Metal 0"),
 "m0":      dict(label="Metal 0",            color="#F2C1A2", note="First routing level"),
}
ORDER = ["silicon","siu","sic","sige","sio2","highk","si3n4","sibcn","lowk","alox","wall","cellmark","mdi","bond",
         "nwf","tin","wfill","cofill","mo","tisi","cobalt","tungsten","copper","soc","barc","sihm","tiox","poly","ild","pts","pts_n","resist","resist_exp","chrome","liner","mandrel","mandrel2","patspacer",
         "pwell","nwell","fox","nanowire","md","po","vd","vg","m0"]
# Gate-fill metals: the renderer's ghost view treats these as the gate.
GATE_FILLS = ("wfill", "cofill", "mo")

# Work-function metal by polarity: an Al-containing n-type metal for nFETs, TiN for pFETs.
WFM = {"n": "nwf", "p": "tin"}
WFL = {"n": "n-type work-function metal", "p": "TiN work-function metal (p-type)"}

# ---------------------------------------------------------------- shared CDs
TCH, LG, LSP, LSD = 5.0, 15.0, 7.0, 22.0
TIL, THK, TTIN = 1.0, 2.0, 3.0
XG, XSP, XSD = LG/2, LG/2+LSP, LG/2+LSP+LSD          # 7.5 / 14.5 / 36.5
HYS  = TCH/2                                          # 2.5
HY1, HY2, HY3 = HYS+TIL, HYS+TIL+THK, HYS+TIL+THK+TTIN   # 3.5 / 5.5 / 8.5
EOT = round(TIL + THK*3.9/22.0, 2)

# The Process nanosheet flows' stack. Their route [R13] makes the nFET and the pFET from one
# Si/SiGe stack: the nFET keeps the Si layers as its channels and the pFET the SiGe ones, so
# both layers must be channel-thin, and each device's gate has only the other layer's
# thickness between its sheets. Device mode spaces its sheets 21 nm apart so every film shows;
# the Process flows cannot, or the pFET's sheets would be 16 nm thick. Here both layers are
# 7 nm, and the gate films (0.5 nm SiO2, 1.5 nm HfO2, 1.5 nm work-function metal on each
# sheet) fill each 7 nm gap between sheets with no fill metal, as in real stacks.
NS_PROCESS_STACK = dict(tch=7.0, tsg=7.0, til=0.5, thk=1.5, twf=1.5)
# The exploded gate view of the same devices: sheets as thick, gaps and films enlarged so each
# film can be seen and tapped. A display choice, not a device: never quoted as dimensions.
NS_EXPLODED_STACK = dict(tch=7.0, tsg=16.0, til=1.0, thk=2.0, twf=3.0)

class Dev:
    def __init__(self, key, name, tag, blurb):
        self.key, self.name, self.tag, self.blurb = key, name, tag, blurb
        self.parts, self.callouts, self.dims, self.views = [], [], [], {}
    def add(self, pid, name, material, boxes, group, explode):
        self.parts.append(dict(id=pid, name=name, material=material, group=group,
                               boxes=[[round(float(v),4) for v in b] for b in boxes],
                               explode=explode))
    def cal(self, cid, label, value, desc, a, b, lab, v=None):
        self.callouts.append(dict(id=cid, label=label, value=value, desc=desc,
                                  a=a, b=b, lab=lab, v=v))
    def finish(self):
        bx = [b for p in self.parts for b in p["boxes"]]
        self.bounds = dict(
            x=[min(b[0]-b[3]/2 for b in bx), max(b[0]+b[3]/2 for b in bx)],
            y=[min(b[1]-b[4]/2 for b in bx), max(b[1]+b[4]/2 for b in bx)],
            z=[min(b[2]-b[5]/2 for b in bx), max(b[2]+b[5]/2 for b in bx)])
        return self

def box(x0,x1,y0,y1,z0,z1):
    return [(x0+x1)/2,(y0+y1)/2,(z0+z1)/2, x1-x0, y1-y0, z1-z0]

def ring4(yc, hy, hz, t, xh):
    """closed ring around a sheet, extruded along x (gate-all-around)"""
    return [box(-xh,xh, yc+hy,yc+hy+t, -(hz+t),hz+t),
            box(-xh,xh, yc-hy-t,yc-hy, -(hz+t),hz+t),
            box(-xh,xh, yc-hy,yc+hy,  hz,hz+t),
            box(-xh,xh, yc-hy,yc+hy, -(hz+t),-hz)]

def fork3(yc, hy, zi, zo, t, xh, s):
    """three-sided film: top, bottom, outer face.  s=+1 sheet sits on +z of wall"""
    if s > 0:
        return [box(-xh,xh, yc+hy,yc+hy+t, zi,zo+t),
                box(-xh,xh, yc-hy-t,yc-hy, zi,zo+t),
                box(-xh,xh, yc-hy,yc+hy,  zo,zo+t)]
    return [box(-xh,xh, yc+hy,yc+hy+t, -(zo+t),-zi),
            box(-xh,xh, yc-hy-t,yc-hy, -(zo+t),-zi),
            box(-xh,xh, yc-hy,yc+hy, -(zo+t),-zo)]

def finwrap(zc, wh, y0, y1, t, xh):
    """three-sided film over a standing fin: both sidewalls + the top"""
    return [box(-xh,xh, y0,y1, zc-wh-t,zc-wh),
            box(-xh,xh, y0,y1, zc+wh,zc+wh+t),
            box(-xh,xh, y1,y1+t, zc-wh-t,zc+wh+t)]

def lim6(b):
    return (b[0]-b[3]/2, b[0]+b[3]/2, b[1]-b[4]/2, b[1]+b[4]/2, b[2]-b[5]/2, b[2]+b[5]/2)

def carve(region, obstacles):
    """Disjoint boxes filling [region] (x0,x1,y0,y1,z0,z1) outside every obstacle box."""
    obs = [lim6(b) for b in obstacles]
    def cuts(a):
        lo, hi = region[a], region[a+1]
        return sorted({lo, hi} | {o[i] for o in obs for i in (a, a+1) if lo < o[i] < hi})
    xs, ys, zs = cuts(0), cuts(2), cuts(4)
    nx, ny, nz = len(xs)-1, len(ys)-1, len(zs)-1
    free = np.ones((nx, ny, nz), bool)
    for o in obs:
        ix = [i for i in range(nx) if o[0] < (xs[i]+xs[i+1])/2 < o[1]]
        iy = [j for j in range(ny) if o[2] < (ys[j]+ys[j+1])/2 < o[3]]
        iz = [k for k in range(nz) if o[4] < (zs[k]+zs[k+1])/2 < o[5]]
        if ix and iy and iz: free[np.ix_(ix, iy, iz)] = False
    out = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                if not free[i, j, k]: continue
                i1 = i
                while i1+1 < nx and free[i1+1, j, k]: i1 += 1
                j1 = j
                while j1+1 < ny and free[i:i1+1, j1+1, k].all(): j1 += 1
                k1 = k
                while k1+1 < nz and free[i:i1+1, j:j1+1, k1+1].all(): k1 += 1
                free[i:i1+1, j:j1+1, k:k1+1] = False
                out.append(box(xs[i], xs[i1+1], ys[j], ys[j1+1], zs[k], zs[k1+1]))
    return out

def lined(xa, xb, y0, y1, z0, z1, t):
    """A contact opening lined with a film of thickness [t] on its floor and four walls:
    (liner boxes, core box)."""
    return ([box(xa, xb, y0, y0+t, z0, z1),
             box(xa, xa+t, y0+t, y1, z0, z1), box(xb-t, xb, y0+t, y1, z0, z1),
             box(xa+t, xb-t, y0+t, y1, z0, z0+t), box(xa+t, xb-t, y0+t, y1, z1-t, z1)],
            box(xa+t, xb-t, y0+t, y1, z0+t, z1-t))

def gaps(lo, hi, blocks):
    """the y-intervals of [lo,hi] not covered by blocks [(a,b),...]"""
    out, cur = [], lo
    for a,b in sorted(blocks):
        if a > cur: out.append((cur,a))
        cur = max(cur,b)
    if cur < hi: out.append((cur,hi))
    return out

def check(dev, step=0.5):
    bx=[b for p in dev.parts for b in p["boxes"]]
    B=dev.bounds
    gx=np.arange(B["x"][0],B["x"][1],step); gy=np.arange(B["y"][0],B["y"][1],step)
    gz=np.arange(B["z"][0],B["z"][1],step)
    cnt=np.zeros((len(gx),len(gy),len(gz)),np.uint8)
    for cx,cy,cz,dx,dy,dz in bx:
        ix=(gx>cx-dx/2)&(gx<cx+dx/2); iy=(gy>cy-dy/2)&(gy<cy+dy/2); iz=(gz>cz-dz/2)&(gz<cz+dz/2)
        cnt[np.ix_(ix,iy,iz)] += 1
    return int(cnt.max()), len(bx)

# ============================================================== NANOSHEET ===
def build_ns(stack=None):
    """Device mode's nanosheet, or with [stack] (NS_PROCESS_STACK) the Process flows' one:
    the same parts, with the sheets, their spacing and the gate films at [stack]'s values."""
    d=Dev("ns","Nanosheet FET","GAA · 3 stacked sheets",
      "A gate-all-around nFET: three silicon nanosheets over bottom dielectric isolation (BDI), after IBM's US 2023/0420457 A1. It has SiBCN spacers and BDI, low-κ inner spacers, a Hf-based high-κ, an n-type work-function metal, and a W fill under a SiN self-aligned-contact cap [R13].")
    W, PITCH, NSH = 30.0, 21.0, 3
    TCH, TIL, THK, TTIN = globals()["TCH"], globals()["TIL"], globals()["THK"], globals()["TTIN"]
    if stack:
        TCH, TIL, THK, TTIN = stack["tch"], stack["til"], stack["thk"], stack["twf"]
        PITCH = TCH + stack["tsg"]
    HYS = TCH/2; HY1, HY2, HY3 = HYS+TIL, HYS+TIL+THK, HYS+TIL+THK+TTIN
    EOT = round(TIL + THK*3.9/22.0, 2)
    hz=W/2; STI=10.0
    # Device mode leaves room for fill metal under the lowest sheet; the Process stack's
    # bottom SiGe layer is as thick as the others.
    y0 = STI+stack["tsg"]+HYS if stack else STI+HY3+6.0
    ys=[y0+i*PITCH for i in range(NSH)]                 # 24.5 45.5 66.5 (Device mode)
    top=ys[-1]+HYS
    hz1,hz2,hz3 = hz+TIL, hz+TIL+THK, hz+TIL+THK+TTIN   # 16 18 21
    # The source/drain epitaxy rises above the stack: the pFET's (H lower, see build_ns_p)
    # slightly above its top, the nFET's about one layer higher (Figs. 11A, 13A-19A) [R13]. The
    # gate stands clear of both.
    hzmo=hz3+5.0; ymo=ys[-1]+HY3+19.0; ycap=ymo+6.0
    ysd=ys[-1]+HYS+13.0; ynisi=ysd+5.0
    # The contacts stop level with the top of the SAC cap, as the FinFET's do with its hard mask.
    yplug=ycap; ym2=ycap
    zsub=34.0; SUBFIN=8.0      # 68 nm n-to-p pitch: gates 16 nm apart, room for the 12 nm cut

    # The stack sits on a short Si sub-fin. The STI beside it (low-κ in the patent) stops
    # level with the bottom of the BDI: in the flow it is recessed that far so the base
    # layer's sidewalls are open for the etch that replaces it with the BDI. The sub-fin
    # carries the p-type punch-through stopper implanted before the stack was grown [R13].
    d.add("substrate","Si substrate","silicon",[box(-48,48,-26,-SUBFIN,-zsub,zsub)],
          "Substrate & isolation",[0,-1.2,0])
    d.add("pts","p-type punch-through stopper (sub-fin)","pts",[box(-48,48,-SUBFIN,0,-hz,hz)],
          "Substrate & isolation",[0,-1.0,0])
    d.add("sti","STI (low-κ dielectric)","lowk",[box(-48,48,-SUBFIN,0,hz,zsub), box(-48,48,-SUBFIN,0,-zsub,-hz)],
          "Substrate & isolation",[0,-.8,0])
    # One conformal film makes the gate spacers and fills the cavity as the BDI [R13].
    d.add("bdi","Bottom dielectric isolation (BDI) · SiBCN spacer film","sibcn",[box(-XSD,XSD,0,STI,-hz,hz)],
          "Substrate & isolation",[0,-.8,0])
    for i,yc in enumerate(ys):
        d.add(f"sheet{i+1}",f"Si nanosheet {i+1}","silicon",[box(-XSP,XSP,yc-HYS,yc+HYS,-hz,hz)],"Channel stack",[0,0,0])
    for i,yc in enumerate(ys):
        d.add(f"il{i+1}",f"SiO₂ interfacial layer · sheet {i+1}","sio2",ring4(yc,HYS,hz,TIL,XG),"Gate-all-around films",["radial",yc,1.0])
    for i,yc in enumerate(ys):
        d.add(f"hk{i+1}",f"HfO₂ high-κ · sheet {i+1}","highk",ring4(yc,HY1,hz1,THK,XG),"Gate-all-around films",["radial",yc,2.1])
    for i,yc in enumerate(ys):
        d.add(f"tin{i+1}",f"n-type work-function metal · sheet {i+1}","nwf",ring4(yc,HY2,hz2,TTIN,XG),"Gate-all-around films",["radial",yc,3.3])
    # Beside the BDI the gate reaches down to the STI, where the dummy gate was. The W fill
    # is recessed and capped by the SiN self-aligned-contact (SAC) cap; the gate contact
    # goes down through the cap onto the W [R13].
    mo=[box(-XG,XG,STI,ymo,hz3,hzmo), box(-XG,XG,STI,ymo,-hzmo,-hz3),
        box(-XG,XG,0,STI,hz,hzmo), box(-XG,XG,0,STI,-hzmo,-hz)]
    for a,b in gaps(STI,ymo,[(y-HY3,y+HY3) for y in ys]):
        mo.append(box(-XG,XG,a,b,-hz3,hz3))
    d.add("mo","W gate fill (recessed)","wfill",mo,"Gate electrode",[0,1.0,0])
    gw=box(-XG,XG,ymo,ym2,-20,20)
    d.add("gatecap","SiN self-aligned-contact (SAC) cap","si3n4",carve((-XG,XG,ymo,ycap,-hzmo,hzmo),[gw]),"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact (through the SAC cap)","tungsten",[gw],"Gate electrode",[0,1.8,0])
    for s,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((s*XG,s*XSP))
        # Outer spacer: the SiBCN film on the dummy gate's sidewalls. Inner spacers: the low-κ
        # fill of the pockets the SiGe indent left, between and under the sheets [R13].
        d.add(f"spacer_{t}",f"SiBCN gate spacer · {t} side","sibcn",
              [box(xa,xb,0,ycap,hz,hzmo), box(xa,xb,0,ycap,-hzmo,-hz), box(xa,xb,top,ycap,-hz,hz)],
              "Spacers",[s*1.3,0,0])
        d.add(f"inner_{t}",f"Low-κ inner spacers · {t} side","lowk",
              [box(xa,xb,a,b,-hz,hz) for a,b in gaps(STI,top,[(y-HYS,y+HYS) for y in ys])],
              "Spacers",[s*1.1,0,0])
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2
        d.add(f"epi_{T.lower()}",f"{T} epi (Si:P; the dopant is the model's)","silicon",[box(xa,xb,STI,ysd,-hz,hz)],"Source / drain",[s*1.6,0,0])
        d.add(f"nisi_{T.lower()}",f"{T} TiSiₓ silicide (the patent: the contact may include a silicide)","tisi",[box(xa,xb,ysd,ynisi,-hz,hz)],"Source / drain",[s*1.9,.3,0])
        d.add(f"ni_{T.lower()}",f"{T} Co contact plug (model's choice)","cobalt",[box(xc-8,xc+8,ynisi,yplug,-12,12)],"Source / drain",[s*2.1,.8,0])

    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","Physical gate length",[-XG,ymo+2,hzmo],[XG,ymo+2,hzmo],[0,ymo+22,hzmo+36],["iso","b"])
    d.cal("LSP","L<sub>SP</sub>",f"{LSP:g} nm","Spacer length",[XG,ycap+1,hzmo],[XSP,ycap+1,hzmo],[XSP+30,ycap+16,hzmo+22],["iso","b"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Nanosheet thickness",[-XSP,ys[1]-HYS,hz],[-XSP,ys[1]+HYS,hz],[-XSP-34,ys[1],hz+34],["iso","b","c","gaa"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Nanosheet width",[-XSP,ys[0]-HYS-.6,-hz],[-XSP,ys[0]-HYS-.6,hz],[0,ys[0]-26,zsub+14],["iso","c"])
    d.cal("pitch","Sheet pitch",f"{PITCH:g} nm","Vertical sheet-to-sheet pitch",[XSP,ys[0],-hz],[XSP,ys[1],-hz],[XSP+34,(ys[0]+ys[1])/2,-hz-30],["b","c"])
    d.cal("eot","t_ox",f"{TIL+THK:g} nm",f"{TIL:g} SiO₂ + {THK:g} HfO₂ · EOT {EOT:g} nm",[0,ys[2]+HYS,hz+.1],[0,ys[2]+HY2,hz+.1],[0,ys[2]+32,hz2+40],["c","gaa","iso"])
    d.cal("tin","t<sub>WFM</sub>",f"{TTIN:g} nm","n-type work-function metal",[0,ys[2]+HY2,-hz-.1],[0,ys[2]+HY3,-hz-.1],[0,ys[2]+26,-hz3-38],["c","gaa"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet-to-sheet pitch",f"{PITCH:g} nm"],
            ["N_sh","Sheets in the stack","3"],["L_SP","Spacer length",f"{LSP:g} nm"],
            ["EOT","Equivalent oxide thickness of the drawn films (production stacks: typically below about 1 nm)",f"{EOT:g} nm"],
            ["—","Fill between work-function shells (spacing enlarged)",f"{PITCH-2*HY3:g} nm"],
            ["—","Active footprint (z)",f"{2*hz3:g} nm"]]
    d.views={"iso":dict(n="3D overview",s="the whole device",az=-.76,el=.36,r=300,tgt=[0,40,0],clip=None),
             "b":dict(n="Along channel",s="source · gate · drain",az=0,el=0,r=265,tgt=[0,42,0],clip=[None,None,0]),
             "c":dict(n="Across channel",s="through the gate",az=1.5708,el=0,r=250,tgt=[0,46,0],clip=[0,None,None]),
             "gaa":dict(n="Gate-all-around",s="source side lifted off",az=-1.12,el=.30,r=205,tgt=[0,45,0],clip=[4,None,None],
                        off=["epi_source","nisi_source","ni_source","spacer_source","inner_source"])}
    d.note=("<b>Reading the wrap.</b> Each Si sheet is wrapped in three films: an SiO2 interfacial layer, HfO2 and an n-type work-function metal. W fills the rest of the gate, under a SiN self-aligned-contact (SAC) cap [R13]. Thicknesses and spacings are the model's choices. The EOT (equivalent oxide thickness) of " f"{EOT:g}nm is that of the drawn films.")
    return d.finish()

# ================================================================= FINFET ===
def build_fin():
    """The FinFET nFET after TSMC's US 9,812,358 B1 [R29]: Si fins in a P well, SiN gate
    spacers (the seal spacers are removed with the dummy gate, Fig. 12B), SiP source/drain grown
    in recesses, a replacement gate (high-κ and work-function layer lining the fins, the STI
    floor and the spacer walls, Co fill) recessed under an AlOₓ hard mask, and replacement
    contacts (TiN liner, Co) formed where a spin-on-carbon dummy contact stood."""
    d=Dev("fin","FinFET","tri-gate · 2 fins",
      "A tri-gate FinFET nFET, after TSMC's US 9,812,358 B1. It has Si fins in a P well, SiP source/drain, and a replacement high-κ/metal gate under an AlOₓ hard mask. Its Co contacts, in a TiN liner, take the place of a spin-on-carbon dummy contact [R29].")
    WFIN, HFIN, FPITCH, NFIN = 6.0, 45.0, 27.0, 2
    LGf=18.0; XGf=LGf/2; XSPf=XGf+LSP; XSDf=XSPf+LSD      # 9 / 16 / 38
    TLIN = 1.0                                             # contact liner
    STI=12.0; wh=WFIN/2
    ytop=STI+HFIN                                          # 57  exposed fin top
    zf=[(i-(NFIN-1)/2)*FPITCH for i in range(NFIN)]        # -13.5  +13.5
    w1,w2,w3 = wh+TIL, wh+TIL+THK, wh+TIL+THK+TTIN         # 4 6 9
    y1,y2,y3 = ytop+TIL, ytop+TIL+THK, ytop+TIL+THK+TTIN   # 58 60 63
    hzenv = (NFIN-1)/2*FPITCH + w3                         # 22.5
    hzmo = hzenv+5.0                                       # 27.5
    ymo=y3+12.0; ycap=ymo+6.0                              # 75 -> 81: the recess the hard mask fills
    yepi=ytop+7.0; ynisi=yepi+5.0                          # 64 69
    zsub=hzmo+8.0

    d.add("substrate","Si substrate · P well (nFET region)","silicon",[box(-48,48,-26,0,-zsub,zsub)],"Substrate & isolation",[0,-1.2,0])
    sti=[]; edges=[-zsub]+[v for z in zf for v in (z-wh,z+wh)]+[zsub]
    for i in range(0,len(edges),2):
        if edges[i+1]>edges[i]: sti.append(box(-XSDf,XSDf,0,STI,edges[i],edges[i+1]))
    d.add("sti","STI · silicon oxide (FCVD), recessed","sio2",sti,"Substrate & isolation",[0,-.8,0])
    # Outside the spacers each fin is recessed to the STI top, and the source/drain grows
    # from the recess: full height only under the gate and spacers, a stub below the epi.
    for i,z in enumerate(zf):
        d.add(f"fin{i+1}",f"Si fin {i+1} (P well)","silicon",[box(-XSPf,XSPf,0,ytop,z-wh,z+wh),
              box(-XSDf,-XSPf,0,STI,z-wh,z+wh),box(XSPf,XSDf,0,STI,z-wh,z+wh)],"Fins",[0,0,0])
    for i,z in enumerate(zf):
        d.add(f"il{i+1}",f"SiO₂ interfacial layer · fin {i+1}","sio2",finwrap(z,wh,STI,ytop,TIL,XGf),"Tri-gate films",["radial",(STI+ytop)/2,1.0,z])
    for i,z in enumerate(zf):
        d.add(f"hk{i+1}",f"HfO₂ high-κ · fin {i+1}","highk",finwrap(z,w1,STI,y1,THK,XGf),"Tri-gate films",["radial",(STI+ytop)/2,2.1,z])
    for i,z in enumerate(zf):
        # over the STI it starts on the high-κ floor, and along x it stops at the high-κ on the walls
        d.add(f"tin{i+1}",f"n-type work-function metal (Al-containing) · fin {i+1}","nwf",
              finwrap(z,w2,STI+THK,y2,TTIN,XGf-THK),"Tri-gate films",["radial",(STI+ytop)/2,3.3,z])
    # The gate dielectric is conformal in the trench: on the fins, on the STI floor between
    # them and on the gate spacers' walls (Figs. 13A/B), recessed with the gate (Fig. 14).
    # The work-function layer follows it; the Co fill takes the rest.
    trench=(-XGf,XGf,STI,ymo,-hzmo,hzmo)
    solid=lambda ids: [b for q in d.parts if q["id"] in ids for b in q["boxes"]]
    films=[f"{k}{i+1}" for k in ("fin","il","hk") for i in range(NFIN)]
    d.add("floor_hk","HfO₂ high-κ · on the STI floor and the spacer walls","highk",
          carve(trench,solid(films)+[box(-XGf+THK,XGf-THK,STI+THK,ymo,-hzmo,hzmo)]),"Tri-gate films",[0,.6,0])
    films+=["floor_hk"]+[f"tin{i+1}" for i in range(NFIN)]
    TW=THK+TTIN
    d.add("floor_wf","n-type work-function metal (Al-containing) · on the floor and the spacer walls","nwf",
          carve(trench,solid(films)+[box(-XGf+TW,XGf-TW,STI+TW,ymo,-hzmo,hzmo)]),"Tri-gate films",[0,.8,0])
    d.add("mo","Co gate fill (recessed)","cofill",carve(trench,solid(films+["floor_wf"])),"Gate electrode",[0,1.0,0])
    gw=box(-XGf,XGf,ymo,ycap,-20,20)
    d.add("gatecap","AlOₓ hard mask (protects the gate at the contact etch)","alox",
          carve((-XGf,XGf,ymo,ycap,-hzmo,hzmo),[gw]),"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact (through the hard mask)","tungsten",[gw],"Gate electrode",[0,1.8,0])
    for sx,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((sx*XGf,sx*XSPf)); sp=[box(xa,xb,ytop,ycap,-hzmo,hzmo)]
        eg=[-hzmo]+[v for z in zf for v in (z-wh,z+wh)]+[hzmo]
        for i in range(0,len(eg),2):
            if eg[i+1]>eg[i]: sp.append(box(xa,xb,STI,ytop,eg[i],eg[i+1]))
        d.add(f"spacer_{t}",f"SiN gate spacer · {t} side","si3n4",sp,"Spacers",[sx*1.3,0,0])
    for sx,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((sx*XSPf,sx*XSDf))
        ep=[];ns=[]
        for z in zf:
            # grown from the recessed fin: narrow at the seed, faceted out above the STI
            ep += [box(xa,xb,STI,STI+6,z-wh-2,z+wh+2), box(xa,xb,STI+6,yepi,z-10,z+10)]
            # The silicide forms only where the contact opening meets the epi: its footprint.
            ns.append(box(xa,xb,yepi,ynisi,max(z-10,-hzenv),min(z+10,hzenv)))
        d.add(f"epi_{T.lower()}",f"{T} epi (SiP) · grown in the recess","silicon",ep,"Source / drain",[sx*1.6,.2,0])
        d.add(f"nisi_{T.lower()}",f"{T} silicide (TiSiₓ) · formed by the contact anneal","tisi",ns,"Source / drain",[sx*1.9,.5,0])
        ln,core=lined(xa,xb,ynisi,ycap,-hzenv,hzenv,TLIN)
        d.add(f"liner_{T.lower()}",f"{T} contact liner (TiN)","tin",ln,"Source / drain",[sx*2.0,.8,0])
        d.add(f"ni_{T.lower()}",f"{T} replacement contact (Co)","cobalt",[core],"Source / drain",[sx*2.2,.9,0])

    Weff=NFIN*(2*HFIN+WFIN)
    d.cal("Hfin","H<sub>fin</sub>",f"{HFIN:g} nm","Exposed fin height",[-XSPf,STI,zf[0]-wh],[-XSPf,ytop,zf[0]-wh],[-XSPf-30,(STI+ytop)/2,-hzmo-26],["iso","b","c","tri"])
    d.cal("Wfin","W<sub>fin</sub>",f"{WFIN:g} nm","Fin width",[-XSPf,ytop+.6,zf[1]-wh],[-XSPf,ytop+.6,zf[1]+wh],[-XSPf-8,ytop+30,zf[1]+22],["iso","c","tri"])
    d.cal("fp","Fin pitch",f"{FPITCH:g} nm","Fin-to-fin pitch",[XSPf,STI-1,zf[0]],[XSPf,STI-1,zf[1]],[XSPf+28,STI-24,0],["c","b"])
    d.cal("LG","L<sub>G</sub>",f"{LGf:g} nm","Physical gate length",[-XGf,ymo+2,hzmo],[XGf,ymo+2,hzmo],[0,ymo+22,hzmo+34],["iso","b"])
    d.cal("eot","t_ox",f"{TIL+THK:g} nm",f"{TIL:g} SiO₂ + {THK:g} HfO₂ · EOT {EOT:g} nm",[0,ytop,zf[1]],[0,y2,zf[1]],[0,ytop+34,hzmo+28],["c","tri"])
    d.cal("tin","t<sub>WFM</sub>",f"{TTIN:g} nm","n-type work-function metal (WFM), on three faces only",[0,(STI+ytop)/2,zf[0]-w2],[0,(STI+ytop)/2,zf[0]-w3],[0,STI+10,-hzmo-30],["c","tri"])
    d.dims=[["L_G","Physical gate length (the gate trench, lining films included)",f"{LGf:g} nm"],["W_fin","Fin width",f"{WFIN:g} nm"],
            ["H_fin","Exposed fin height",f"{HFIN:g} nm"],["Fin pitch","Fin-to-fin pitch",f"{FPITCH:g} nm"],
            ["N_fin","Fins in this device",f"{NFIN}"],["L_SP","Gate spacer (the seal spacers are removed with the dummy gate)",f"{LSP:g} nm"],
            ["EOT","Equivalent oxide thickness of the drawn films (production stacks: typically below about 1 nm)",f"{EOT:g} nm"],
            ["W_eff","Effective width, (2H+W) x 2 fins",f"{Weff:g} nm"],
            ["Gate","Work-function layer, fill, cap","Al-containing WFM · Co · AlOₓ hard mask"],
            ["Contacts","Replacement contacts","TiN liner · Co · silicide"],
            ["—","Gate faces per channel","3 (tri-gate)"],
            ["—","Active footprint (z)",f"{2*hzenv:g} nm"]]
    d.views={"iso":dict(n="3D overview",s="two fins",az=-.78,el=.34,r=290,tgt=[0,38,0],clip=None),
             "b":dict(n="Along channel",s="through one fin",az=0,el=0,r=250,tgt=[0,40,0],clip=[None,None,zf[1]]),
             "c":dict(n="Across channel",s="through the gate",az=1.5708,el=0,r=250,tgt=[0,42,0],clip=[0,None,None]),
             "tri":dict(n="Tri-gate",s="source side lifted off",az=-1.15,el=.28,r=215,tgt=[0,40,0],clip=[3,None,None],
                        off=["epi_source","nisi_source","liner_source","ni_source","spacer_source"])}
    d.note=("<b>After US 9,812,358 B1.</b> The gate seal spacers are removed with the dummy gate, so the gate dielectric lies directly on the SiN gate spacers. The dielectric lines the fins, the STI floor between them and the spacer walls, and is recessed with the gate. The gate electrodes come from the patent's list (TiN, TaN, TaC, Co, Ru, Al). Here they are an Al-containing work-function layer and a Co fill. The gate is recessed and capped by a metal-oxide hard mask (AlOₓ), which protects it when the self-aligned contacts are etched [R29]. In self-aligned contact schemes, this kind of dielectric cap, with insulated sidewalls, is what stops a source/drain contact from shorting to the gate [R26]. The contacts are formed where a baked spin-on-carbon dummy contact stood: a TiN liner and Co, with a silicide at the epitaxy formed by an anneal [R29]. The model's own choices are the SiO₂ interfacial layer (the patent names none), HfO₂ (from its Hf-oxide option), TiSiₓ (for its unnamed silicide), the W gate contact (no metal named), and the box-shaped epitaxy and flat contact floor (the patent's epitaxy is faceted and its contacts wrap the facets). Each drawn fin has 96nm of gated perimeter (2 x 45nm height + 6nm top width). Dimensions are the model's choices.")
    return d.finish()

# ============================================================== FORKSHEET ===
def fs_floor(d, sg, s, zi, z3, ytop0, XG_, grp):
    """Gate films on a sub-fin's top under the gate: with no bottom isolation, the lowest
    stretch of gate sits on the sub-fin, so the films line it too."""
    zf=zi+22.0                                           # the sub-fin's outer face
    for k,(nm,mat,t) in enumerate((("SiO₂ interfacial layer","sio2",TIL),("HfO₂ high-κ","highk",THK),
                                   (WFL[sg],WFM[sg],TTIN))):
        y0=ytop0+sum((TIL,THK,TTIN)[:k])
        bx=[box(-XG_,XG_,y0,y0+t,*sorted((s*zi,s*z3)))]
        # The interfacial oxide grows on the silicon only; over the STI the high-κ lies directly
        # on the oxide, taking the interfacial layer's place.
        if k==0: bx=[box(-XG_,XG_,y0,y0+t,*sorted((s*zi,s*zf)))]
        if k==1: bx.append(box(-XG_,XG_,ytop0,ytop0+TIL,*sorted((s*zf,s*z3))))
        d.add(f"floor_{('il','hk','wf')[k]}_{sg}",f"{nm} · on the {sg}FET sub-fin (bottom of the gate)",mat,
              bx,grp,[0,-.4,s*.3])
    return ytop0+TIL+THK+TTIN

def build_fs():
    """The forksheet pair after imec's EP 3 989 273 A1 [R31]: Si channels either side of a
    SiN insulating wall whose base sits in the substrate and whose top rises above the top
    channel; SiBCN gate spacers and SiN inner spacers; P- and N-doped Si source/drain grown
    from the sheet ends, each region masked in turn; HfO2, TiN (p) and TiAlC (n) work-function
    metals, W fill, common above the wall; a SiN contact partition wall on top of the
    insulating wall splitting TiN/W source/drain contacts made in one opening."""
    d=Dev("fs","Forksheet FET","inner-wall forksheet · n/p pair",
      "An inner-wall forksheet pair, after imec's EP 3 989 273 A1. Si nanosheets sit on either side of a SiN wall, and each sheet is gated on three faces. One W gate fill is shared above the wall, and a contact partition wall on the wall separates the n and p source/drain contacts [R31].")
    W, PITCH, NSH, WALL = 22.0, 21.0, 3, 8.0
    zi=WALL/2                                            # 4  wall face
    zo=zi+W                                              # 26 sheet outer face
    z1,z2,z3 = zo+TIL, zo+TIL+THK, zo+TIL+THK+TTIN       # 27 29 32
    zmo=z3+5.0; STI=10.0; ZP=6.0                         # partition wall half-width: 12 nm, wider than the wall
    ys=[STI+HY3+6.0+i*PITCH for i in range(NSH)]
    top=ys[-1]+HYS
    # The top sacrificial layer 116a is thicker than the others (the gaps are 16 nm), so the wall,
    # level with its top, rises well above the top channel [R31, 0060-0064].
    ywall=top+20.0
    ymo=ywall+6.0; ycap=ymo+6.0
    ysd=top+3.0; ym2=ycap+10.0; zsub=zmo+5; YB=6.0       # wall base embedded 6 nm in the substrate
    GS="Substrate & isolation"

    sub=[box(-48,48,-26,-YB,-zsub,zsub), box(-48,48,-YB,0,zi,zsub), box(-48,48,-YB,0,-zsub,-zi)]
    sub += [box(-48,48,0,STI,zi,zo), box(-48,48,0,STI,-zo,-zi)]
    d.add("substrate","Si substrate and sub-fins","silicon",sub,GS,[0,-1.2,0])
    d.add("sti","STI (silicon oxide)","sio2",[box(-48,48,0,STI,zo,zsub), box(-48,48,0,STI,-zsub,-zo)],GS,[0,-.8,0])
    d.add("wall","SiN insulating wall (base in the substrate)","wall",[box(-XSD,XSD,-YB,ywall,-zi,zi)],"Dielectric wall",[0,1.6,0])

    for s,pol in ((1,"n"),(-1,"p")):
        sg = pol
        grp=f"{sg}FET"
        for i,yc in enumerate(ys):
            zz=sorted((s*zi,s*zo))
            d.add(f"sheet_{sg}{i+1}",f"{sg}FET Si sheet {i+1}","silicon",
                  [box(-XSP,XSP,yc-HYS,yc+HYS,zz[0],zz[1])],"Channel stacks",[0,0,0])
        for i,yc in enumerate(ys):
            d.add(f"il_{sg}{i+1}",f"SiO₂ interfacial layer · {sg}{i+1}","sio2",
                  fork3(yc,HYS,zi,zo,TIL,XG,s),"Forked gate films",["radial",yc,1.0])
        for i,yc in enumerate(ys):
            d.add(f"hk_{sg}{i+1}",f"HfO₂ high-κ · {sg}{i+1}","highk",
                  fork3(yc,HY1,zi,z1,THK,XG,s),"Forked gate films",["radial",yc,2.1])
        for i,yc in enumerate(ys):
            d.add(f"tin_{sg}{i+1}",("TiAlC n-type work-function metal" if sg=="n" else "TiN p-type work-function metal")+f" · {sg}{i+1}",WFM[sg],
                  fork3(yc,HY2,zi,z2,TTIN,XG,s),"Forked gate films",["radial",yc,3.3])
        yfl=fs_floor(d,sg,s,zi,z3,STI,XG,"Forked gate films")
        mo=[box(-XG,XG,STI,ymo,*sorted((s*z3,s*zmo)))]
        for a,b in gaps(yfl,ymo,[(y-HY3,y+HY3) for y in ys]):
            mo.append(box(-XG,XG,a,b,*sorted((s*zi,s*z3))))
        d.add(f"mo_{sg}",f"W gate fill · {sg} side","wfill",mo,"Gate electrode",[0,1.0,s*0.9])
        for sx,t in ((-1,"source"),(1,"drain")):
            xa,xb=sorted((sx*XG,sx*XSP))
            d.add(f"spacer_{sg}_{t}",f"SiBCN gate spacer · {sg} {t}","sibcn",
                  [box(xa,xb,STI,ycap,*sorted((s*zo,s*zmo))), box(xa,xb,top,ycap,*sorted((s*zi,s*zo)))],
                  "Spacers",[sx*1.3,0,s*.5])
            d.add(f"inner_{sg}_{t}",f"SiN inner spacers · {sg} {t}","si3n4",
                  [box(xa,xb,a,b,*sorted((s*zi,s*zo))) for a,b in gaps(STI,top,[(y-HYS,y+HYS) for y in ys])],
                  "Spacers",[sx*1.1,0,s*.5])
        for sx,T in ((-1,"Source"),(1,"Drain")):
            xa,xb=sorted((sx*XSP,sx*XSD))
            zz=sorted((s*zi,s*zo)); zc=sorted((s*ZP,s*zo))
            lab = "Si:P" if sg=="n" else "Si:B"
            d.add(f"epi_{sg}_{T.lower()}",f"{sg}FET {T.lower()} epi ({lab})","silicon",
                  [box(xa,xb,STI,ysd,zz[0],zz[1])],"Source / drain",[sx*1.6,0,s*.6])
            # Liner 133 (SiN, an etch stop) stays on the spacer face and the wall tip, opened at
            # the contact bottom [R31, 0073, 0093].
            xs=(xb-1,xb) if sx<0 else (xa,xa+1)            # the spacer-side face
            xa2,xb2=(xa,xb-1) if sx<0 else (xa+1,xb)
            zw=sorted((s*zi,s*(zi+1)))                      # the wall-tip face
            zz2=sorted((s*(zi+1),s*zo)); zc2=sorted((s*ZP,s*zo))
            d.add(f"liner_{sg}_{T.lower()}",f"SiN liner 133 · on the spacer and the wall tip ({sg} {T.lower()})","si3n4",
                  [box(xs[0],xs[1],ysd,ywall,zz[0],zz[1]), box(xs[0],xs[1],ywall,ycap,zc[0],zc[1]),
                   box(xa2,xb2,ysd,ywall,zw[0],zw[1])],"Spacers",[sx*1.9,.6,s*.5])
            d.add(f"nisi_{sg}_{T.lower()}",f"{sg}FET {T.lower()} contact · TiN (ALD; the floor drawn)","tin",
                  [box(xa2,xb2,ysd,ysd+1,zz2[0],zz2[1])],"Source / drain",[sx*1.9,.3,s*.7])
            d.add(f"ni_{sg}_{T.lower()}",f"{sg}FET {T.lower()} contact · W fill (CVD)","tungsten",
                  [box(xa2,xb2,ysd+1,ywall,zz2[0],zz2[1]), box(xa2,xb2,ywall,ycap,zc2[0],zc2[1])],"Source / drain",[sx*2.1,.8,s*.8])
    # The contact partition wall on top of the insulating wall, one each side of the gate:
    # the n and p contacts are etched through one opening and it keeps them apart [R31].
    for sx,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((sx*XSP,sx*XSD))
        d.add(f"cpw_{t}",f"SiN contact partition wall · {t} side","wall",[box(xa,xb,ywall,ycap,-ZP,ZP)],"Dielectric wall",[sx*1.4,1.8,0])
    d.add("mo_c","W gate fill · common, above the wall (the option the patent's background describes)","wfill",[box(-XG,XG,ywall,ymo,-zi,zi)],"Gate electrode",[0,1.2,0])
    d.add("spacer_c","SiBCN gate spacer · over the wall",
          "sibcn",[box(XG,XSP,ywall,ycap,-zi,zi), box(-XSP,-XG,ywall,ycap,-zi,zi)],"Spacers",[0,1.0,0])
    gw=box(-XG,XG,ymo,ycap,-8,8)
    d.add("gatecap","SiN gate cap (the gate recessed; cap material the model's choice)","si3n4",
          carve((-XG,XG,ymo,ycap,-zmo,zmo),[gw]),"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact","tungsten",[gw],"Gate electrode",[0,1.8,0])

    d.cal("wall","Wall",f"{WALL:g} nm","SiN insulating wall between the n and p stacks",[0,ywall+1,-zi],[0,ywall+1,zi],[0,ywall+26,zmo+30],["iso","c","fork"])
    d.cal("np","n–p space",f"{WALL:g} nm","gap between the n and p work-function metals, across the wall",[XG+1,ys[1],-zi],[XG+1,ys[1],zi],[XSP+30,ys[1]-22,0],["c","fork"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Sheet thickness",[-XSP,ys[1]-HYS,zo],[-XSP,ys[1]+HYS,zo],[-XSP-34,ys[1],zo+32],["iso","b","c","fork"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Sheet width",[-XSP,ys[0]-HYS-.6,zi],[-XSP,ys[0]-HYS-.6,zo],[-XSP-10,ys[0]-26,zo+20],["iso","c"])
    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","Physical gate length",[-XG,ymo+2,zmo],[XG,ymo+2,zmo],[0,ymo+22,zmo+34],["iso","b"])
    d.cal("tin","t<sub>WFM</sub>",f"{TTIN:g} nm","work-function metal on three sides, not four",[0,ys[2]+HY2,zo+.1],[0,ys[2]+HY3,zo+.1],[0,ys[2]+30,z3+34],["c","fork"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet-to-sheet pitch",f"{PITCH:g} nm"],
            ["t_wall","Insulating wall width (patent range: 5–20 nm)",f"{WALL:g} nm"],
            ["Wall top","Above the top channel",f"{ywall-top:g} nm"],
            ["Partition","Contact partition wall width (patent range: 10–24 nm)",f"{2*ZP:g} nm"],
            ["n–p","Gap between the n and p work-function metals, across the wall",f"{WALL:g} nm"],
            ["N_sh","Sheets per polarity","3"],["EOT","Equivalent oxide thickness of the drawn films (production stacks: typically below about 1 nm)",f"{EOT:g} nm"],
            ["WFM","Work-function metal, p · n","TiN · TiAlC"],["S/D","Source/drain epitaxy, p · n","Si:B · Si:P"],
            ["—","Gate faces per sheet","3 (forked)"],
            ["—","Active footprint (z)",f"{2*z3:g} nm"]]
    d.views={"iso":dict(n="3D overview",s="both polarities",az=-.80,el=.34,r=330,tgt=[0,42,0],clip=None),
             "b":dict(n="Along channel",s="source · gate · drain",az=0,el=0,r=280,tgt=[0,44,0],clip=[None,None,(zi+zo)/2]),
             "c":dict(n="Across channel",s="n | wall | p",az=1.5708,el=0,r=290,tgt=[0,48,0],clip=[0,None,None]),
             "fork":dict(n="The fork",s="p side lifted off",az=-1.25,el=.30,r=240,tgt=[0,46,0],clip=[4,None,None],
                 off=[f"epi_{g}_source" for g in "np"]+[f"nisi_{g}_source" for g in "np"]+
                     [f"ni_{g}_source" for g in "np"]+[f"spacer_{g}_source" for g in "np"]+
                     [f"inner_{g}_source" for g in "np"]+["cpw_source"])}
    d.note=("<b>After EP 3 989 273 A1.</b> A SiN insulating wall separates the n and p stacks. Its base sits in the substrate. A thicker top sacrificial layer lets it rise above the top channel, so the work-function metals stay apart and the source/drain epitaxy is confined sideways. The TiN (p) and TiAlC (n) work-function metals are joined by a common W fill above the wall. That is the option the patent's background describes; its own figures do not cut through the gate at the wall. A SiN liner stays on the spacers and the wall tip. The source/drain contacts, TiN then W, are etched in one opening on each side of the gate. A SiN contact partition wall, formed on top of the insulating wall, splits them [R31]. This is the classic inner-wall forksheet, not imec's later outer-wall one [R2]. Dimensions are the model's choices, within the patent's ranges where it gives them.")
    return d.finish()

# =================================================================== CFET ===
def cfet_tier(d, tag, ylist, grp, hz):
    """One tier's sheets and gate-all-around films."""
    for i,yc in enumerate(ylist):
        d.add(f"sheet_{tag}{i+1}",f"{tag}FET Si sheet {i+1}","silicon",[box(-XSP,XSP,yc-HYS,yc+HYS,-hz,hz)],grp,[0,0,0])
    hz1,hz2 = hz+TIL, hz+TIL+THK
    for i,yc in enumerate(ylist):
        d.add(f"il_{tag}{i+1}",f"SiO₂ interfacial layer · {tag}{i+1}","sio2",ring4(yc,HYS,hz,TIL,XG),grp,["radial",yc,1.0])
    for i,yc in enumerate(ylist):
        d.add(f"hk_{tag}{i+1}",f"HfO₂ high-κ · {tag}{i+1}","highk",ring4(yc,HY1,hz1,THK,XG),grp,["radial",yc,2.1])
    for i,yc in enumerate(ylist):
        d.add(f"tin_{tag}{i+1}",WFL[tag]+f" · {tag}{i+1}",WFM[tag],ring4(yc,HY2,hz2,TTIN,XG),grp,["radial",yc,3.3])

def build_cfet(seq=False):
    return build_cfet_seq() if seq else build_cfet_mono()

def build_cfet_mono():
    """IBM's US 11,869,812 B2 [R33]: a lower pFET and an upper nFET from one stack on an
    insulating layer (BOX). The high-Ge SiGe layer between the tiers is replaced by the
    spacer material (SiBCN); the lower S/D (SiGe:B) is notched and isolated by SiO2 (1110);
    the upper S/D (Si:P) grows above it. One HKMG (HfO2; TiN lower and TiAlC upper, W and a
    SiN cap are the model's choices); front-side contacts only: a common via through the
    upper drain into the lower one, the upper source from above, the lower source through
    the space a sacrificial TiOx spacer left."""
    d=Dev("cfet_mono","Monolithic CFET","monolithic integration · common gate",
      "A monolithic CFET, after IBM's US 11,869,812 B2. A SiGe:B pFET sits below a Si:P nFET, and one common gate serves both. An oxide layer in a notch separates the two tiers' source/drain, and every contact is made from the front [R33].")
    W, PITCH, MDI = 20.0, 20.0, 12.0
    hz=W/2; hz3 = hz+TIL+THK+TTIN; hzmo=hz3+5.0          # 10 16 21
    STI=8.0
    yb=[STI+HY3+6.0, STI+HY3+6.0+PITCH]          # 22.5 42.5  lower tier (p)
    ymdi0=yb[-1]+HY3; ymdi1=ymdi0+MDI            # 51 -> 63
    yt=[ymdi1+HY3, ymdi1+HY3+PITCH]              # 71.5 91.5  upper tier (n)
    ymo=yt[-1]+HY3+6.0; ycap=ymo+6.0             # 106 -> 112
    ylo=ymdi0-3.0; yup=ymdi1+2.0                 # lower S/D top (notched) · upper S/D bottom
    ytsd=yt[-1]+HYS+3.0; ynisi=ytsd+3.0; ym2=ycap          # contacts stop level with the cap
    zsub=hzmo+6.0
    YB=[(y-HY3,y+HY3) for y in yb]; YT=[(y-HY3,y+HY3) for y in yt]

    d.add("substrate","Si substrate","silicon",[box(-48,48,-18,0,-zsub,zsub)],"Substrate & isolation",[0,-1.4,0])
    d.add("box","BOX (SiO₂) · insulating layer under the stack","sio2",[box(-48,48,0,STI,-zsub,zsub)],"Substrate & isolation",[0,-.8,0])
    cfet_tier(d,"p",yb,"Lower tier (p)",hz)
    cfet_tier(d,"n",yt,"Upper tier (n)",hz)
    # Where the high-Ge SiGe between the tiers was: the spacer material fills the void [R33].
    d.add("mdi","SiBCN between the tiers (the spacer material filled the removed SiGe)","sibcn",
          [box(-XSP,XSP,ymdi0,ymdi1,-hz,hz)],"Tier isolation",[0,1.1,0])
    mo=[box(-XG,XG,STI,ymo,hz3,hzmo), box(-XG,XG,STI,ymo,-hzmo,-hz3),
        box(-XG,XG,ymdi0,ymdi1,hz,hz3), box(-XG,XG,ymdi0,ymdi1,-hz3,-hz)]
    for a,b in gaps(STI,ymo,YB+YT+[(ymdi0,ymdi1)]):
        mo.append(box(-XG,XG,a,b,-hz3,hz3))
    d.add("mo","W gate fill · one gate for both tiers","wfill",mo,"Gate electrode",[0,1.0,0])
    gw=box(-XG,XG,ymo,ym2,-12,12)
    d.add("gatecap","SiN gate cap (the patent: a gate dielectric cap; SiN the model's choice)","si3n4",carve((-XG,XG,ymo,ycap,-hzmo,hzmo),[gw]),"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact (the model's addition: the patent shows S/D contacts only)","tungsten",[gw],"Gate electrode",[0,1.8,0])
    for s,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((s*XG,s*XSP))
        sp=[box(xa,xb,STI,ycap,hz,hzmo), box(xa,xb,STI,ycap,-hzmo,-hz)]
        for a,b in gaps(STI,ycap,[(y-HYS,y+HYS) for y in yb+yt]+[(ymdi0,ymdi1)]):
            sp.append(box(xa,xb,a,b,-hz,hz))
        d.add(f"spacer_{t}",f"SiBCN spacers and inner spacers · {t} side","sibcn",sp,"Spacers",[s*1.3,0,0])
    # Source/drain, after Figs. 9-17: the lower S/D (SiGe:B) has its top centre recessed into a
    # notch, leaving an ear on each side; isolation layer 1110 fills the notch, covers the top,
    # and fills the -z side where the sacrificial TiOx 810 was removed first; the upper S/D (Si:P)
    # grows on 1110. On the +z side 810 stays, except where the lower source's contact replaces it.
    NOTCH, EAR, SIDE = 4.0, 3.0, 6.0
    yn = ylo - NOTCH                                   # notch floor
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2; t=T.lower()
        V=box(xc-6,xc+6,yn-1,ym2,-6,6)                 # the drain side's common via
        SU=box(xc-7,xc+7,yup,ytsd,-7,7); SL=box(xc-7,xc+7,yn-2,yn,-7,7)
        cut=[V,SU,SL] if t=="drain" else []
        d.add(f"epi_p_{t}",f"Lower pFET {t} epi (SiGe:B) · notched on top","sige",
              carve((xa,xb,STI,yn,-hz,hz),cut)+[box(xa,xb,yn,ylo,-hz,-hz+EAR), box(xa,xb,yn,ylo,hz-EAR,hz)],
              "Lower tier (p)",[s*1.6,-.4,0])
        iso=[box(xa,xb,yn,ylo,-hz+EAR,hz-EAR), box(xa,xb,ylo,yup,-hz,hz), box(xa,xb,STI,yup,-hz-SIDE,-hz)]
        if t=="drain": iso.append(box(xa,xb,ylo,yup,hz,hz+SIDE))
        d.add(f"iso_{t}",f"Isolation layer 1110 (SiO₂) · in the notch, beside and above the lower {t}","sio2",
              [c for b in iso for c in carve(lim6(b),cut)],"Tier isolation",[s*1.5,0,0])
        d.add(f"epi_n_{t}",f"Upper nFET {t} epi (Si:P)","silicon",carve((xa,xb,yup,ytsd,-hz,hz),cut),"Upper tier (n)",[s*1.6,.4,0])
        if t=="source":
            d.add("nisi_source","Upper source silicide (TiSiₓ)","tisi",[box(xa,xb,ytsd,ynisi,-hz,hz)],"Upper tier (n)",[s*1.9,.7,0])
        else:
            d.add("tiox_drain","Sacrificial TiOₓ spacer 810 · left beside the lower drain","tiox",
                  [box(xa,xb,STI,ylo,hz,hz+SIDE)],"Tier isolation",[s*1.5,-.4,.4])
            d.add("sil_up_drain","Silicide liner (TiSiₓ) · where the common via passes the upper drain","tisi",
                  carve(lim6(SU),[V]),"Contacts",[s*1.9,.7,0])
            d.add("sil_lo_drain","Silicide liner (TiSiₓ) · where the common via lands in the lower drain","tisi",
                  carve(lim6(SL),[V]),"Contacts",[s*1.9,-.2,0])
            d.add("ni_drain","W common via · through the upper drain and the isolation into the lower drain (the output)",
                  "tungsten",[V],"Contacts",[1.8,1.0,0])
    # Upper source: a via from above. Lower source: its contact fills the space the TiOx 810 left
    # on its +z side, with a silicide on the S/D, and rises beside the upper source, kept off it
    # by the ILD [R33].
    xa,xb=-XSD,-XSP; xc=(xa+xb)/2
    d.add("ni_source","W contact · upper nFET source","tungsten",[box(xc-8,xc+8,ynisi,ym2,-8,8)],"Contacts",[-1.8,1.0,0])
    d.add("sil_lo_source","Silicide liner (TiSiₓ) · on the lower source, under its contact","tisi",
          [box(xa,xb,STI,ylo,hz,hz+1)],"Contacts",[-1.9,-.2,.4])
    d.add("ni_lo_source","W contact · lower pFET source, through the space the TiOₓ left","tungsten",
          [box(xa,xb,STI,ylo,hz+1,hz+6), box(xa,xb,ylo,ym2,hz+3,hz+9)],"Contacts",[-1.8,.4,.6])
    # The riser is set 3 nm off the upper source so the two nets cannot touch; in the patent
    # that space is ILD 1310 (SiO₂, SiN or SiOC). Drawn here, since the scenes hide the ILD.
    d.add("vdd_gap","ILD (SiO₂) · keeps the V_DD contact off the upper nFET source","sio2",
          [box(xa,xb,ylo,ym2,hz,hz+3), box(xa,xb,ynisi,ym2,8,hz)],"Contacts",[-1.6,.4,.3])

    d.cal("mdi","Tier gap",f"{MDI:g} nm","SiBCN between the tiers",[XG+1,ymdi0,-hz],[XG+1,ymdi1,-hz],[XSP+30,(ymdi0+ymdi1)/2,-hzmo-28],["iso","b","c","tier"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Sheet thickness",[-XSP,yb[0]-HYS,hz],[-XSP,yb[0]+HYS,hz],[-XSP-34,yb[0]-6,hz+34],["iso","b","c","tier"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Sheet width",[-XSP,yt[1]+HYS+.6,-hz],[-XSP,yt[1]+HYS+.6,hz],[-XSP-16,yt[1]+26,0],["iso","c"])
    d.cal("pitch","Tier pitch",f"{yt[0]-yb[1]:g} nm","Lower sheet to upper sheet",[XSP,yb[1],hz],[XSP,yt[0],hz],[XSP+32,(yb[1]+yt[0])/2,hz+30],["b","c"])
    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","One gate, both tiers",[-XG,ymo+2,hzmo],[XG,ymo+2,hzmo],[0,ymo+24,hzmo+32],["iso","b"])
    d.cal("eot","t_ox",f"{TIL+THK:g} nm",f"{TIL:g} SiO₂ + {THK:g} HfO₂ · EOT {EOT:g} nm",[0,yt[1]+HYS,hz+.1],[0,yt[1]+HY2,hz+.1],[0,yt[1]+28,hz+TIL+THK+36],["c","tier"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet pitch within a tier",f"{PITCH:g} nm"],
            ["Tiers","Lower · upper","pFET (SiGe:B) · nFET (Si:P)"],
            ["t_MDI","SiBCN between the tiers",f"{MDI:g} nm"],
            ["N_sh","Sheets per tier","2"],["EOT","Equivalent oxide thickness of the drawn films (production stacks: typically below about 1 nm)",f"{EOT:g} nm"],
            ["—","Contacts","front side only: one via on both drains; the lower source reached beside the upper one"],
            ["—","Gate","one high-κ/metal gate (HKMG) for both tiers, as in the patent; TiN lower, TiAlC upper, W fill and SiN cap are the model's choices"],
            ["—","Active footprint (z)",f"{2*hz3:g} nm"]]
    d.views={"iso":dict(n="3D overview",s="the stacked pair",az=-.80,el=.30,r=360,tgt=[0,56,0],clip=None),
             "b":dict(n="Along channel",s="both tiers in section",az=0,el=0,r=310,tgt=[0,58,0],clip=[None,None,0]),
             "c":dict(n="Across channel",s="through the gate",az=1.5708,el=0,r=300,tgt=[0,60,0],clip=[0,None,None]),
             "tier":dict(n="Tier interface",s="source side lifted off",az=-1.18,el=.26,r=270,tgt=[0,56,0],clip=[4,None,None],
                 off=["epi_n_source","epi_p_source","iso_source","nisi_source","ni_source","ni_lo_source","sil_lo_source","vdd_gap","spacer_source"])}
    d.note=("<b>After US 11,869,812 B2.</b> One stack makes both tiers: a pFET below with SiGe:B source/drain, and an nFET above with Si:P. The high-Ge SiGe between the tiers is removed, and the spacer material fills the gap. The top of the lower source/drain is recessed into a notch, and an oxide layer fills it, so the upper source/drain grows clear of the lower one. One gate serves both tiers. Every contact is made from the front. One via runs down through the upper drain and the oxide into the top of the lower drain. The lower source is reached through the space a sacrificial TiOₓ spacer left beside it. Each contact has a silicide where it meets the source/drain [R33]. The patent names one work-function metal for both tiers. The TiN (lower) and TiAlC (upper) split, the W fill, the SiN cap and the gate contact are the model's choices. So are the dimensions.")
    return d.finish()

def build_cfet_seq():
    """TSMC's US 2024/0413156 A1 [R34]: the lower transistor (a pFET here; the patent allows
    either type) is made in one wafer; an etch stop, a dielectric holding an inter-metal line
    (Cu) and bond layers (SiO2) go on top; a second wafer is bonded and the upper nFET made in
    it. Deep plugs (W) run from the front through the upper drain, and from the back through
    the lower drain, to the inter-metal line: the drains' common node. The gates are separate;
    the patent draws no gate-to-gate connection."""
    d=Dev("cfet_seq","Sequential CFET","sequential integration · bonded tiers",
      "A sequential CFET, after TSMC's US 2024/0413156 A1. A pFET is made in the lower wafer and an nFET in a wafer bonded above it. Deep plugs from the front and the back join their drains through an inter-metal line. The gates are separate [R34].")
    W, PITCH = 20.0, 20.0
    hz=W/2; hz3 = hz+TIL+THK+TTIN; hzmo=hz3+5.0          # 10 16 21
    STI=8.0
    yb=[STI+HY3+6.0, STI+HY3+6.0+PITCH]          # 22.5 42.5  lower tier (p)
    ylg=yb[-1]+HY3+4.0; ylc=ylg+3.0              # lower gate top · its cap top (55, 58)
    yes=ylc; yd0=yes+2.0; yl0=yd0+2.0; yl1=yl0+6.0; yd1=yd0+10.0      # etch stop · dielectric · Cu line
    yb1=yd1+3.0; yb2=yb1+3.0; yu0=yb2            # bond 68L · bond 68U; the upper stack sits on 68U
    yt=[yu0+HY3+6.0, yu0+HY3+6.0+PITCH]          # upper tier (n)
    ymo=yt[-1]+HY3+6.0; ycap=ymo+6.0
    ybsd=yb[-1]+HYS+3.0                          # lower S/D top
    ytsd=yt[-1]+HYS+3.0; ynisi=ytsd+3.0; ym2=ycap          # contacts stop level with the cap
    zsub=hzmo+6.0; BL0,BL1=-16.0,-8.0            # backside line level
    YB=[(y-HY3,y+HY3) for y in yb]; YT=[(y-HY3,y+HY3) for y in yt]
    xd0,xd1=XSP,XSD; xdc=(xd0+xd1)/2; xs0,xs1=-XSD,-XSP; xsc=(xs0+xs1)/2
    P70=box(xdc-4,xdc+4,yl1,ym2,-4,4)            # deep plug 70: front, through the upper drain
    P90=box(xdc-4,xdc+4,BL1,yl0,-4,4)            # deep plug 90: back, through the lower drain
    P91=box(xsc-4,xsc+4,BL1,STI,-4,4)            # plug 91: back, landing on the lower source

    # ---- backside: the substrate is gone; dielectric and lines under the lower tier ----
    # The lower gate is reached from the back too: the patent draws no gate contact, so this via
    # and its line are the model's addition, under the fill's side beside the stack.
    PG=box(-2,2,BL1,STI,hz3,hzmo)
    d.add("bsline_s","Backside line (Cu) · lower source (V_DD)","copper",[box(-48,-4,BL0,BL1,-zsub,zsub)],"Backside interconnect",[0,-2.0,0])
    d.add("bsline_g","Backside line (Cu) · lower gate (the model's addition)","copper",[box(-2.5,2.5,BL0,BL1,-zsub,zsub)],"Backside interconnect",[0,-2.0,0])
    d.add("bsline_d","Backside line (Cu) · the drains' node","copper",[box(4,48,BL0,BL1,-zsub,zsub)],"Backside interconnect",[.6,-2.0,0])
    # With the lower wafer's substrate ground away, the backside dielectric (an etch stop and a
    # low-κ layer, 93) meets the stack directly; the STI oxide stays beside it [R34].
    FOOT=box(-XSD,XSD,0,STI,-hz,hz)
    d.add("bsdiel","Backside dielectric 93 (etch stop and low-κ; the low-κ drawn)","lowk",
          carve((-48,48,BL1,0,-zsub,zsub),[P90,P91,PG])+carve(lim6(FOOT),[P90,P91])
          +[box(-4,-2.5,BL0,BL1,-zsub,zsub),box(2.5,4,BL0,BL1,-zsub,zsub)],
          "Backside interconnect",[0,-1.5,0])
    d.add("sti_l","STI (SiO₂) · beside the lower stack","sio2",
          carve((-48,48,0,STI,-zsub,zsub),[P90,P91,PG,FOOT]),"Lower tier (p)",[0,-.9,0])
    d.add("gatew_p","W gate via · lower gate, from the back (the model's addition)","tungsten",[PG],"Lower tier (p)",[0,-1.2,0])
    # ---- lower tier (p), in the lower wafer ----
    cfet_tier(d,"p",yb,"Lower tier (p)",hz)
    mo=[box(-XG,XG,STI,ylg,hz3,hzmo), box(-XG,XG,STI,ylg,-hzmo,-hz3)]
    for a,b in gaps(STI,ylg,YB): mo.append(box(-XG,XG,a,b,-hz3,hz3))
    d.add("mo_p","W gate fill · lower pFET (W: the model's choice)","wfill",mo,"Lower tier (p)",[0,.6,0])
    d.add("cap_p","SiN gate cap · lower pFET (model's choice)","si3n4",[box(-XG,XG,ylg,ylc,-hzmo,hzmo)],"Lower tier (p)",[0,.8,0])
    for s,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((s*XG,s*XSP))
        sp=[box(xa,xb,STI,ylc,hz,hzmo), box(xa,xb,STI,ylc,-hzmo,-hz)]
        sp+=[box(xa,xb,a,b,-hz,hz) for a,b in gaps(STI,ylc,[(y-HYS,y+HYS) for y in yb])]
        d.add(f"spacer_p_{t}",f"Lower gate spacer and SiOCN inner spacers · {t}","lowk",sp,"Lower tier (p)",[s*1.3,-.3,0])
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); t=T.lower()
        reg=(xa,xb,STI,ybsd,-hz,hz)
        d.add(f"epi_p_{t}",f"Lower pFET {t} epi (SiGe:B)","sige",carve(reg,[P90] if s>0 else [P91]),"Lower tier (p)",[s*1.6,-.4,0])
    # ---- between the tiers ----
    d.add("estop","Etch stop (AlOₓ)","alox",carve((-XSD,XSD,yes,yd0,-zsub,zsub),[P90]),"Between the tiers",[0,1.0,0])
    line=box(XSP,XSD,yl0,yl1,-hz,hz)
    d.add("m66","Inter-metal line 66 (Cu) · joins the drains","copper",[line],"Between the tiers",[1.0,1.1,0])
    d.add("diel64","Dielectric (SiO₂) around the line","sio2",carve((-XSD,XSD,yd0,yd1,-zsub,zsub),[line,P90,P70]),"Between the tiers",[0,1.1,0])
    d.add("bond_l","Bond layer 68L (SiO₂)","bond",carve((-XSD,XSD,yd1,yb1,-zsub,zsub),[P70]),"Between the tiers",[0,1.2,0])
    d.add("bond_u","Bond layer 68U (SiO₂) · fusion-bonded","bond",carve((-XSD,XSD,yb1,yb2,-zsub,zsub),[P70]),"Between the tiers",[0,1.25,0])
    # No oxide under the upper stack: the upper wafer is thinned to its stack, which sits on bond
    # layer 68U [R34].
    # ---- upper tier (n), in the bonded wafer ----
    cfet_tier(d,"n",yt,"Upper tier (n)",hz)
    mo=[box(-XG,XG,yu0,ymo,hz3,hzmo), box(-XG,XG,yu0,ymo,-hzmo,-hz3)]
    for a,b in gaps(yu0,ymo,YT): mo.append(box(-XG,XG,a,b,-hz3,hz3))
    d.add("mo","W gate fill · upper nFET (W: the model's choice)","wfill",mo,"Gate electrode",[0,1.0,0])
    gw=box(-XG,XG,ymo,ym2,-12,12)
    d.add("gatecap","SiN gate cap · upper nFET (model's choice)","si3n4",carve((-XG,XG,ymo,ycap,-hzmo,hzmo),[gw]),"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact · upper gate","tungsten",[gw],"Gate electrode",[0,1.8,0])
    for s,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((s*XG,s*XSP))
        sp=[box(xa,xb,yu0,ycap,hz,hzmo), box(xa,xb,yu0,ycap,-hzmo,-hz)]
        sp+=[box(xa,xb,a,b,-hz,hz) for a,b in gaps(yu0,ycap,[(y-HYS,y+HYS) for y in yt])]
        d.add(f"spacer_{t}",f"Upper gate spacer and SiOCN inner spacers · {t}","lowk",sp,"Upper tier (n)",[s*1.3,.3,0])
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2; t=T.lower()
        cut=[P70] if s>0 else []
        d.add(f"epi_n_{t}",f"Upper nFET {t} epi (Si:P)","silicon",carve((xa,xb,yu0,ytsd,-hz,hz),cut),"Upper tier (n)",[s*1.6,.4,0])
        d.add(f"nisi_{t}",f"Upper {t} silicide (TiSiₓ)","tisi",carve((xa,xb,ytsd,ynisi,-hz,hz),cut),"Upper tier (n)",[s*1.9,.7,0])
    d.add("ni_source","W contact plug 71 · upper nFET source","tungsten",[box(xsc-6,xsc+6,ynisi,ym2,-6,6)],"Contacts",[-1.8,1.0,0])
    d.add("ni_drain","W deep plug 70 · front, through the upper drain to line 66","tungsten",[P70],"Contacts",[1.8,1.0,0])
    d.add("via_drain","W deep plug 90 · back, through the lower drain to line 66","tungsten",[P90],"Contacts",[1.8,-1.0,0])
    d.add("via_source","W plug 91 · back, onto the lower pFET source","tungsten",[P91],"Contacts",[-1.8,-1.0,0])

    d.cal("mdi","Tier gap",f"{yu0-ylg:g} nm","Lower gate top to the upper wafer",[XG+1,ylg,-hz],[XG+1,yu0,-hz],[XSP+30,(ylg+yu0)/2,-hzmo-28],["iso","b","c","tier"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Sheet thickness",[-XSP,yb[0]-HYS,hz],[-XSP,yb[0]+HYS,hz],[-XSP-34,yb[0]-6,hz+34],["iso","b","c","tier"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Sheet width",[-XSP,yt[1]+HYS+.6,-hz],[-XSP,yt[1]+HYS+.6,hz],[-XSP-16,yt[1]+26,0],["iso","c"])
    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","Each tier's gate",[-XG,ymo+2,hzmo],[XG,ymo+2,hzmo],[0,ymo+24,hzmo+32],["iso","b"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet pitch within a tier",f"{PITCH:g} nm"],
            ["Tiers","Lower · upper","pFET (SiGe:B) · nFET (Si:P)"],
            ["Between","Etch stop · dielectric and line · bond layers","AlOₓ · SiO₂ with Cu · SiO₂ + SiO₂"],
            ["N_sh","Sheets per tier","2"],["EOT","Equivalent oxide thickness of the drawn films (production stacks: typically below about 1 nm)",f"{EOT:g} nm"],
            ["—","Drains","joined by line 66: plug 70 from the front, plug 90 from the back"],
            ["—","Gates","separate; their contacts (upper from the front, lower from the back) are the model's additions"],
            ["—","Active footprint (z)",f"{2*hz3:g} nm"]]
    d.views={"iso":dict(n="3D overview",s="the bonded pair",az=-.80,el=.30,r=380,tgt=[0,60,0],clip=None),
             "b":dict(n="Along channel",s="both tiers in section",az=0,el=0,r=340,tgt=[0,62,0],clip=[None,None,0]),
             "c":dict(n="Across channel",s="through the gate",az=1.5708,el=0,r=320,tgt=[0,64,0],clip=[0,None,None]),
             "tier":dict(n="Tier interface",s="source side lifted off",az=-1.18,el=.26,r=290,tgt=[0,60,0],clip=[4,None,None],
                 off=["epi_n_source","epi_p_source","nisi_source","ni_source","via_source","spacer_source","spacer_p_source"])}
    d.note=("<b>After US 2024/0413156 A1.</b> The lower transistor is made in the lower wafer. It is a pFET here; the patent allows either type on either tier. An AlOₓ etch stop, an oxide holding an inter-metal line (Cu) and a bond layer go on top. A second wafer is fusion-bonded, oxide to oxide, and the upper nFET is made in it. So its processing must respect the finished lower tier. Deep plugs join both drains to the inter-metal line: from the front through the upper drain, and from the back through the lower drain. Interconnect runs on both faces. The two gates are separate. The patent draws no connection between them, and no gate contacts. The upper gate's front contact and the lower gate's back via and line are the model's additions [R34]. The finished die sits flipped on a carrier; it is drawn upright. Dimensions and the W gate fill are the model's choices.")
    return d.finish()

# ================================================================ COMPARE ===
if __name__ == "__main__":
    # The Device mode's Compare is made from these models later, in build_inverters.py.
    devs=[build_fin(), build_ns(), build_fs(), build_cfet(False), build_cfet(True)]
    out=dict(materials=MAT, order=ORDER, devices=[])
    for d in devs:
        m,n = check(d)
        print(f"{d.key:10s} parts={len(d.parts):3d} boxes={n:4d}  max solids/voxel={m}")
        out["devices"].append(dict(key=d.key,name=d.name,tag=d.tag,blurb=d.blurb,parts=d.parts,
            callouts=d.callouts,dims=d.dims,views=d.views,note=d.note,bounds=d.bounds,
            groups=list(dict.fromkeys(p["group"] for p in d.parts))))
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "devices.json")
    json.dump(out, open(out_path, "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize(out_path)//1024, "KB")
