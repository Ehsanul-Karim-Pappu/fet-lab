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
 "silicon": dict(label="Silicon",            color="#F2C2CF", note="Substrate, channels, n-type S/D epi"),
 "sige":    dict(label="SiGe",               color="#B37FA0", note="p-type source/drain epi"),
 "sio2":    dict(label="SiO₂",               color="#8C1C13", note="STI, interfacial layer, backside ILD"),
 "highk":   dict(label="High-κ (HfO₂)",      color="#BE8250", note="Gate dielectric, κ ≈ 22"),
 "si3n4":   dict(label="Si₃N₄",              color="#E4AE1B", note="Gate spacers"),
 "wall":    dict(label="Dielectric wall",    color="#7A8AA0", note="SiN n–p separation wall (forksheet)"),
 "mdi":     dict(label="Middle isolation",   color="#4E7F8C", note="Dielectric between CFET tiers"),
 "bond":    dict(label="Bonding oxide",      color="#8FB6C0", note="Wafer-bond interface (sequential CFET)"),
 "mo":      dict(label="M₀ · Mo",            color="#E3D3B0", note="Gate fill metal"),
 "nickel":  dict(label="M₁ · Ni",            color="#EE7A1A", note="S/D contact plug"),
 "tungsten":dict(label="M₂ · W",             color="#BFBBD2", note="Top metal, vias, buried power rail"),
 "nisi":    dict(label="M₃ · NiSi",          color="#E6E2F0", note="S/D silicide"),
 "tin":     dict(label="M₄ · TiN",           color="#BE5518", note="Work-function metal and gate cap"),
 # --- schematic-layout palette, used by the showcase inverters ---
 "pwell":   dict(label="P Well",             color="#7FC9EA", note="p-type well / substrate"),
 "nwell":   dict(label="N Well",             color="#EFE53A", note="n-type well under the pMOS"),
 "fox":     dict(label="SiO₂ (field)",       color="#C7CBD0", note="Field oxide the devices sit on"),
 "nanowire":dict(label="Nanowire",           color="#C08A2E", note="Channel running source to drain"),
 "md":      dict(label="MD",                 color="#4FAE4F", note="Source/drain contact"),
 "po":      dict(label="Po",                 color="#3B41CF", note="Gate electrode"),
 "vd":      dict(label="VD",                 color="#8E1C1C", note="Via, MD to Metal 0"),
 "vg":      dict(label="VG",                 color="#F5E93B", note="Via, gate to Metal 0"),
 "m0":      dict(label="Metal 0",            color="#F2C1A2", note="First routing level"),
}
ORDER = ["silicon","sige","sio2","highk","si3n4","wall","mdi","bond",
         "tin","mo","nisi","nickel","tungsten",
         "pwell","nwell","fox","nanowire","md","po","vd","vg","m0"]

# ---------------------------------------------------------------- shared CDs
TCH, LG, LSP, LSD = 5.0, 15.0, 7.0, 22.0
TIL, THK, TTIN = 1.0, 2.0, 3.0
XG, XSP, XSD = LG/2, LG/2+LSP, LG/2+LSP+LSD          # 7.5 / 14.5 / 36.5
HYS  = TCH/2                                          # 2.5
HY1, HY2, HY3 = HYS+TIL, HYS+TIL+THK, HYS+TIL+THK+TTIN   # 3.5 / 5.5 / 8.5
EOT = round(TIL + THK*3.9/22.0, 2)

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
def build_ns():
    d=Dev("ns","Nanosheet FET","GAA · 3 stacked sheets",
      "The baseline gate-all-around device. Each Si sheet is wrapped on all four faces "
      "by SiO₂ / HfO₂ / TiN, with Mo filling whatever is left between sheets.")
    W, PITCH, NSH = 30.0, 21.0, 3
    hz=W/2; STI=10.0
    ys=[STI+HY3+6.0+i*PITCH for i in range(NSH)]        # 24.5 45.5 66.5
    hz1,hz2,hz3 = hz+TIL, hz+TIL+THK, hz+TIL+THK+TTIN   # 16 18 21
    hzmo=hz3+5.0; ymo=ys[-1]+HY3+9.0; ycap=ymo+6.0
    ysd=ys[-1]+HYS+3.0; ynisi=ysd+5.0; yplug=92.0; ym2=102.0
    zsub=42.0

    d.add("substrate","Si substrate","silicon",[box(-48,48,-26,0,-zsub,zsub)],"Substrate & isolation",[0,-1.2,0])
    d.add("sti","STI / bottom isolation","sio2",[box(-XSP,XSP,0,STI,-zsub,zsub)],"Substrate & isolation",[0,-.8,0])
    for i,yc in enumerate(ys):
        d.add(f"sheet{i+1}",f"Si nanosheet {i+1}","silicon",[box(-XSP,XSP,yc-HYS,yc+HYS,-hz,hz)],"Channel stack",[0,0,0])
    for i,yc in enumerate(ys):
        d.add(f"il{i+1}",f"SiO₂ interfacial layer · sheet {i+1}","sio2",ring4(yc,HYS,hz,TIL,XG),"Gate-all-around films",["radial",yc,1.0])
    for i,yc in enumerate(ys):
        d.add(f"hk{i+1}",f"HfO₂ high-κ · sheet {i+1}","highk",ring4(yc,HY1,hz1,THK,XG),"Gate-all-around films",["radial",yc,2.1])
    for i,yc in enumerate(ys):
        d.add(f"tin{i+1}",f"TiN work-function metal · sheet {i+1}","tin",ring4(yc,HY2,hz2,TTIN,XG),"Gate-all-around films",["radial",yc,3.3])
    mo=[box(-XG,XG,STI,ymo,hz3,hzmo), box(-XG,XG,STI,ymo,-hzmo,-hz3)]
    for a,b in gaps(STI,ymo,[(y-HY3,y+HY3) for y in ys]):
        mo.append(box(-XG,XG,a,b,-hz3,hz3))
    d.add("mo","Mo gate fill","mo",mo,"Gate electrode",[0,1.0,0])
    d.add("gatecap","TiN gate cap","tin",[box(-XG,XG,ymo,ycap,-hzmo,hzmo)],"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact","tungsten",[box(-XG,XG,ycap,ym2,-20,20)],"Gate electrode",[0,1.8,0])
    for s,t in ((-1,"source"),(1,"drain")):
        sp=[box(*sorted((s*XG,s*XSP)),STI,ycap,hz,hzmo), box(*sorted((s*XG,s*XSP)),STI,ycap,-hzmo,-hz)]
        for a,b in gaps(STI,ycap,[(y-HYS,y+HYS) for y in ys]):
            sp.append(box(*sorted((s*XG,s*XSP)),a,b,-hz,hz))
        d.add(f"spacer_{t}",f"Si₃N₄ spacer · {t} side","si3n4",sp,"Spacers",[s*1.3,0,0])
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2
        d.add(f"epi_{T.lower()}",f"{T} epi (Si:P)","silicon",[box(xa,xb,0,ysd,-hz,hz)],"Source / drain",[s*1.6,0,0])
        d.add(f"nisi_{T.lower()}",f"{T} NiSi silicide","nisi",[box(xa,xb,ysd,ynisi,-hz,hz)],"Source / drain",[s*1.9,.3,0])
        d.add(f"ni_{T.lower()}",f"{T} Ni contact plug","nickel",[box(xc-8,xc+8,ynisi,yplug,-12,12)],"Source / drain",[s*2.1,.8,0])
        d.add(f"w_{T.lower()}",f"{T} W metal","tungsten",[box(xa,xb,yplug,ym2,-hz,hz)],"Source / drain",[s*2.3,1.3,0])

    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","Physical gate length",[-XG,ymo+2,hzmo],[XG,ymo+2,hzmo],[0,ymo+22,hzmo+36],["iso","b"])
    d.cal("LSP","L<sub>SP</sub>",f"{LSP:g} nm","Spacer length",[XG,ycap+1,hzmo],[XSP,ycap+1,hzmo],[XSP+30,ycap+16,hzmo+22],["iso","b"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Nanosheet thickness",[-XSP,ys[1]-HYS,hz],[-XSP,ys[1]+HYS,hz],[-XSP-34,ys[1],hz+34],["iso","b","c","gaa"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Nanosheet width",[-XSP,ys[0]-HYS-.6,-hz],[-XSP,ys[0]-HYS-.6,hz],[0,ys[0]-26,zsub+14],["iso","c"])
    d.cal("pitch","Sheet pitch",f"{PITCH:g} nm","Vertical sheet-to-sheet pitch",[XSP,ys[0],-hz],[XSP,ys[1],-hz],[XSP+34,(ys[0]+ys[1])/2,-hz-30],["b","c"])
    d.cal("eot","t_ox",f"{TIL+THK:g} nm",f"{TIL:g} SiO₂ + {THK:g} HfO₂ · EOT {EOT:g} nm",[0,ys[2]+HYS,hz+.1],[0,ys[2]+HY2,hz+.1],[0,ys[2]+32,hz2+40],["c","gaa","iso"])
    d.cal("tin","t<sub>TiN</sub>",f"{TTIN:g} nm","Work-function metal",[0,ys[2]+HY2,-hz-.1],[0,ys[2]+HY3,-hz-.1],[0,ys[2]+26,-hz3-38],["c","gaa"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet-to-sheet pitch",f"{PITCH:g} nm"],
            ["N_sh","Sheets in the stack","3"],["L_SP","Spacer length",f"{LSP:g} nm"],
            ["EOT","Equivalent oxide thickness",f"{EOT:g} nm"],
            ["—","Mo between adjacent TiN shells",f"{PITCH-2*HY3:g} nm"],
            ["—","Active footprint (z)",f"{2*hz3:g} nm"]]
    d.views={"iso":dict(n="(a) Isometric",s="the whole device",az=-.76,el=.36,r=300,tgt=[0,40,0],clip=None),
             "b":dict(n="(b) Along channel",s="source · gate · drain",az=0,el=0,r=265,tgt=[0,42,0],clip=[None,None,0]),
             "c":dict(n="(c) Across channel",s="through the gate",az=1.5708,el=0,r=250,tgt=[0,46,0],clip=[0,None,None]),
             "gaa":dict(n="Gate-all-around",s="source side lifted off",az=-1.12,el=.30,r=205,tgt=[0,45,0],clip=[4,None,None],
                        off=["epi_source","nisi_source","ni_source","w_source","spacer_source"])}
    d.note=("<b>Reading the wrap.</b> Slice across the channel and each sheet resolves into four "
            "concentric films — Si core, 1 nm SiO₂, 2 nm HfO₂, then TiN — with Mo filling the rest. "
            f"At a {PITCH:g} nm pitch only <b>{PITCH-2*HY3:g} nm</b> of Mo survives between adjacent TiN shells. "
            "That gap is the vertical scaling wall: tighten the pitch and the work-function metal of "
            "neighbouring sheets merges before fill metal can get in.")
    return d.finish()

# ================================================================= FINFET ===
def build_fin():
    d=Dev("fin","FinFET","tri-gate · 2 fins",
      "The device the whole roadmap is trying to replace. The channel is a thin vertical fin and "
      "the gate reaches only three of its faces — both sidewalls and the top. Drive current comes "
      "from fin height, so more current means more fins, and more fins means a wider cell.")
    WFIN, HFIN, FPITCH, NFIN = 6.0, 45.0, 27.0, 2
    LGf=18.0; XGf=LGf/2; XSPf=XGf+LSP; XSDf=XSPf+LSD      # 9 / 16 / 38
    STI=12.0; wh=WFIN/2
    ytop=STI+HFIN                                          # 57  exposed fin top
    zf=[(i-(NFIN-1)/2)*FPITCH for i in range(NFIN)]        # -13.5  +13.5
    w1,w2,w3 = wh+TIL, wh+TIL+THK, wh+TIL+THK+TTIN         # 4 6 9
    y1,y2,y3 = ytop+TIL, ytop+TIL+THK, ytop+TIL+THK+TTIN   # 58 60 63
    hzenv = (NFIN-1)/2*FPITCH + w3                         # 22.5
    hzmo = hzenv+5.0                                       # 27.5
    ymo=y3+12.0; ycap=ymo+6.0                              # 75 -> 81
    yepi=ytop+7.0; ynisi=yepi+5.0; yplug=81.0; ym2=95.0    # 64 69 81 95
    zsub=hzmo+8.0

    d.add("substrate","Si substrate","silicon",[box(-48,48,-26,0,-zsub,zsub)],"Substrate & isolation",[0,-1.2,0])
    sti=[]; edges=[-zsub]+[v for z in zf for v in (z-wh,z+wh)]+[zsub]
    for i in range(0,len(edges),2):
        if edges[i+1]>edges[i]: sti.append(box(-XSDf,XSDf,0,STI,edges[i],edges[i+1]))
    d.add("sti","STI (fin reveal)","sio2",sti,"Substrate & isolation",[0,-.8,0])
    for i,z in enumerate(zf):
        d.add(f"fin{i+1}",f"Si fin {i+1}","silicon",[box(-XSDf,XSDf,0,ytop,z-wh,z+wh)],"Fins",[0,0,0])
    for i,z in enumerate(zf):
        d.add(f"il{i+1}",f"SiO₂ interfacial layer · fin {i+1}","sio2",finwrap(z,wh,STI,ytop,TIL,XGf),"Tri-gate films",["radial",(STI+ytop)/2,1.0,z])
    for i,z in enumerate(zf):
        d.add(f"hk{i+1}",f"HfO₂ high-κ · fin {i+1}","highk",finwrap(z,w1,STI,y1,THK,XGf),"Tri-gate films",["radial",(STI+ytop)/2,2.1,z])
    for i,z in enumerate(zf):
        d.add(f"tin{i+1}",f"TiN work-function metal · fin {i+1}","tin",finwrap(z,w2,STI,y2,TTIN,XGf),"Tri-gate films",["radial",(STI+ytop)/2,3.3,z])
    mo=[box(-XGf,XGf,STI,ymo,hzenv,hzmo), box(-XGf,XGf,STI,ymo,-hzmo,-hzenv)]
    for i in range(NFIN-1):
        mo.append(box(-XGf,XGf,STI,ymo,zf[i]+w3,zf[i+1]-w3))
    for z in zf:
        mo.append(box(-XGf,XGf,y3,ymo,z-w3,z+w3))
    d.add("mo","Mo gate fill","mo",mo,"Gate electrode",[0,1.0,0])
    d.add("gatecap","TiN gate cap","tin",[box(-XGf,XGf,ymo,ycap,-hzmo,hzmo)],"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact","tungsten",[box(-XGf,XGf,ycap,ym2,-20,20)],"Gate electrode",[0,1.8,0])
    for sx,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((sx*XGf,sx*XSPf)); sp=[box(xa,xb,ytop,ycap,-hzmo,hzmo)]
        eg=[-hzmo]+[v for z in zf for v in (z-wh,z+wh)]+[hzmo]
        for i in range(0,len(eg),2):
            if eg[i+1]>eg[i]: sp.append(box(xa,xb,STI,ytop,eg[i],eg[i+1]))
        d.add(f"spacer_{t}",f"Si₃N₄ spacer · {t} side","si3n4",sp,"Spacers",[sx*1.3,0,0])
    for sx,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((sx*XSPf,sx*XSDf))
        ep=[];ns=[]
        for z in zf:
            ep += [box(xa,xb,STI,ytop,z-10,z-wh), box(xa,xb,STI,ytop,z+wh,z+10),
                   box(xa,xb,ytop,yepi,z-10,z+10)]
            ns.append(box(xa,xb,yepi,ynisi,z-10,z+10))
        d.add(f"epi_{T.lower()}",f"{T} raised epi (Si:P)","silicon",ep,"Source / drain",[sx*1.6,.2,0])
        d.add(f"nisi_{T.lower()}",f"{T} NiSi silicide","nisi",ns,"Source / drain",[sx*1.9,.5,0])
        d.add(f"ni_{T.lower()}",f"{T} Ni trench contact","nickel",
              [box(xa,xb,ynisi,yplug,-hzenv,hzenv)],"Source / drain",[sx*2.1,.9,0])
        d.add(f"w_{T.lower()}",f"{T} W metal","tungsten",
              [box(xa,xb,yplug,ym2,-hzenv,hzenv)],"Source / drain",[sx*2.3,1.3,0])

    Weff=NFIN*(2*HFIN+WFIN)
    d.cal("Hfin","H<sub>fin</sub>",f"{HFIN:g} nm","Exposed fin height",[-XSPf,STI,zf[0]-wh],[-XSPf,ytop,zf[0]-wh],[-XSPf-30,(STI+ytop)/2,-hzmo-26],["iso","b","c","tri"])
    d.cal("Wfin","W<sub>fin</sub>",f"{WFIN:g} nm","Fin width",[-XSPf,ytop+.6,zf[1]-wh],[-XSPf,ytop+.6,zf[1]+wh],[-XSPf-8,ytop+30,zf[1]+22],["iso","c","tri"])
    d.cal("fp","Fin pitch",f"{FPITCH:g} nm","Fin-to-fin pitch",[XSPf,STI-1,zf[0]],[XSPf,STI-1,zf[1]],[XSPf+28,STI-24,0],["c","b"])
    d.cal("LG","L<sub>G</sub>",f"{LGf:g} nm","Physical gate length",[-XGf,ymo+2,hzmo],[XGf,ymo+2,hzmo],[0,ymo+22,hzmo+34],["iso","b"])
    d.cal("eot","t_ox",f"{TIL+THK:g} nm",f"{TIL:g} SiO₂ + {THK:g} HfO₂ · EOT {EOT:g} nm",[0,ytop,(zf[1][0]+zf[1][1])/2 if isinstance(zf[1],(list,tuple)) else zf[1]],[0,y2,(zf[1][0]+zf[1][1])/2 if isinstance(zf[1],(list,tuple)) else zf[1]],[0,ytop+34,hzmo+28],["c","tri"])
    d.cal("tin","t<sub>TiN</sub>",f"{TTIN:g} nm","Three faces only",[0,(STI+ytop)/2,zf[0]-w2],[0,(STI+ytop)/2,zf[0]-w3],[0,STI+10,-hzmo-30],["c","tri"])
    d.dims=[["L_G","Physical gate length",f"{LGf:g} nm"],["W_fin","Fin width",f"{WFIN:g} nm"],
            ["H_fin","Exposed fin height",f"{HFIN:g} nm"],["Fin pitch","Fin-to-fin pitch",f"{FPITCH:g} nm"],
            ["N_fin","Fins in this device",f"{NFIN}"],["L_SP","Spacer length",f"{LSP:g} nm"],
            ["EOT","Equivalent oxide thickness",f"{EOT:g} nm"],
            ["W_eff","Effective width, (2H+W) x 2 fins",f"{Weff:g} nm"],
            ["—","Gate faces per channel","3 (tri-gate)"],
            ["—","Active footprint (z)",f"{2*hzenv:g} nm"]]
    d.views={"iso":dict(n="Isometric",s="two fins",az=-.78,el=.34,r=290,tgt=[0,38,0],clip=None),
             "b":dict(n="Along channel",s="through one fin",az=0,el=0,r=250,tgt=[0,40,0],clip=[None,None,zf[1]]),
             "c":dict(n="Across channel",s="through the gate",az=1.5708,el=0,r=250,tgt=[0,42,0],clip=[0,None,None]),
             "tri":dict(n="Tri-gate",s="source side lifted off",az=-1.15,el=.28,r=215,tgt=[0,40,0],clip=[3,None,None],
                        off=["epi_source","nisi_source","ni_source","w_source","spacer_source"])}
    d.note=("<b>Why this had to end.</b> The gate reaches three faces of the fin, never the bottom, so "
            "the sub-fin leakage path is only ever suppressed by doping and fin reveal depth. Drive "
            f"current is quantised: one fin gives {2*HFIN+WFIN:g} nm of effective width and you buy more only in "
            f"whole fins, {FPITCH:g} nm of cell width at a time. Taller, thinner fins bought two more nodes, and "
            "then bent, wobbled and broke. Laying the fin on its side and cutting it into stacked "
            "sheets is what the nanosheet does — same idea, gate on all four faces, width now continuous.")
    return d.finish()

# ============================================================== FORKSHEET ===
def build_fs():
    d=Dev("fs","Forksheet FET","n + p astride a dielectric wall",
      "A dielectric wall is patterned between the n and p stacks before the gate. The sheets "
      "are anchored to it, so the gate forks around three faces instead of four — and the n and "
      "p work-function metals sit one wall thickness apart instead of a whole gate-metal gap.")
    W, PITCH, NSH, WALL = 22.0, 21.0, 3, 8.0
    zi=WALL/2                                            # 4  wall face
    zo=zi+W                                              # 26 sheet outer face
    z1,z2,z3 = zo+TIL, zo+TIL+THK, zo+TIL+THK+TTIN       # 27 29 32
    zmo=z3+5.0; STI=10.0
    ys=[STI+HY3+6.0+i*PITCH for i in range(NSH)]
    ymo=ys[-1]+HY3+9.0; ycap=ymo+6.0
    ysd=ys[-1]+HYS+3.0; ynisi=ysd+5.0; yplug=92.0; ym2=102.0; zsub=zmo+5

    d.add("substrate","Si substrate","silicon",[box(-48,48,-26,0,-zsub,zsub)],"Substrate & isolation",[0,-1.2,0])
    d.add("sti","STI / bottom isolation","sio2",[box(-XSP,XSP,0,STI,-zsub,zsub)],"Substrate & isolation",[0,-.8,0])
    d.add("wall","SiN dielectric wall","wall",[box(-XSD,XSD,STI,ymo,-zi,zi)],"Dielectric wall",[0,1.6,0])

    for s,pol in ((1,"n"),(-1,"p")):
        sg = "n" if s>0 else "p"
        for i,yc in enumerate(ys):
            zz=sorted((s*zi,s*zo))
            d.add(f"sheet_{sg}{i+1}",f"{sg}FET sheet {i+1}","silicon",
                  [box(-XSP,XSP,yc-HYS,yc+HYS,zz[0],zz[1])],"Channel stacks",[0,0,0])
        for i,yc in enumerate(ys):
            d.add(f"il_{sg}{i+1}",f"SiO₂ interfacial layer · {sg}{i+1}","sio2",
                  fork3(yc,HYS,zi,zo,TIL,XG,s),"Forked gate films",["radial",yc,1.0])
        for i,yc in enumerate(ys):
            d.add(f"hk_{sg}{i+1}",f"HfO₂ high-κ · {sg}{i+1}","highk",
                  fork3(yc,HY1,zi,z1,THK,XG,s),"Forked gate films",["radial",yc,2.1])
        for i,yc in enumerate(ys):
            d.add(f"tin_{sg}{i+1}",f"{sg}-type TiN work-function metal · {sg}{i+1}","tin",
                  fork3(yc,HY2,zi,z2,TTIN,XG,s),"Forked gate films",["radial",yc,3.3])
        mo=[box(-XG,XG,STI,ymo,*sorted((s*z3,s*zmo)))]
        for a,b in gaps(STI,ymo,[(y-HY3,y+HY3) for y in ys]):
            mo.append(box(-XG,XG,a,b,*sorted((s*zi,s*z3))))
        d.add(f"mo_{sg}",f"Mo gate fill · {sg} side","mo",mo,"Gate electrode",[0,1.0,s*0.9])
        for sx,t in ((-1,"source"),(1,"drain")):
            sp=[box(*sorted((sx*XG,sx*XSP)),STI,ycap,*sorted((s*zo,s*zmo)))]
            for a,b in gaps(STI,ycap,[(y-HYS,y+HYS) for y in ys]):
                sp.append(box(*sorted((sx*XG,sx*XSP)),a,b,*sorted((s*zi,s*zo))))
            d.add(f"spacer_{sg}_{t}",f"Si₃N₄ spacer · {sg} {t}","si3n4",sp,"Spacers",[sx*1.3,0,s*.5])
        for sx,T in ((-1,"Source"),(1,"Drain")):
            xa,xb=sorted((sx*XSP,sx*XSD)); xc=(xa+xb)/2
            zz=sorted((s*zi,s*zo)); zc=(zz[0]+zz[1])/2
            mat = "silicon" if s>0 else "sige"
            lab = "Si:P" if s>0 else "SiGe:B"
            d.add(f"epi_{sg}_{T.lower()}",f"{sg}FET {T.lower()} epi ({lab})",mat,
                  [box(xa,xb,0,ysd,zz[0],zz[1])],"Source / drain",[sx*1.6,0,s*.6])
            d.add(f"nisi_{sg}_{T.lower()}",f"{sg}FET {T.lower()} NiSi","nisi",
                  [box(xa,xb,ysd,ynisi,zz[0],zz[1])],"Source / drain",[sx*1.9,.3,s*.7])
            d.add(f"ni_{sg}_{T.lower()}",f"{sg}FET {T.lower()} Ni plug","nickel",
                  [box(xc-8,xc+8,ynisi,yplug,zc-8,zc+8)],"Source / drain",[sx*2.1,.8,s*.8])
            d.add(f"w_{sg}_{T.lower()}",f"{sg}FET {T.lower()} W metal","tungsten",
                  [box(xa,xb,yplug,ym2,zz[0],zz[1])],"Source / drain",[sx*2.3,1.3,s*.9])
    d.add("gatecap","TiN gate cap","tin",[box(-XG,XG,ymo,ycap,-zmo,zmo)],"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact","tungsten",[box(-XG,XG,ycap,ym2,-20,20)],"Gate electrode",[0,1.8,0])

    d.cal("wall","Wall",f"{WALL:g} nm","SiN n–p separation wall",[0,ymo+1,-zi],[0,ymo+1,zi],[0,ymo+26,zmo+30],["iso","c","fork"])
    d.cal("np","n–p space",f"{WALL:g} nm","TiN-to-TiN across the wall",[XG+1,ys[1],-zi],[XG+1,ys[1],zi],[XSP+30,ys[1]-22,0],["c","fork"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Sheet thickness",[-XSP,ys[1]-HYS,zo],[-XSP,ys[1]+HYS,zo],[-XSP-34,ys[1],zo+32],["iso","b","c","fork"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Sheet width",[-XSP,ys[0]-HYS-.6,zi],[-XSP,ys[0]-HYS-.6,zo],[-XSP-10,ys[0]-26,zo+20],["iso","c"])
    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","Physical gate length",[-XG,ymo+2,zmo],[XG,ymo+2,zmo],[0,ymo+22,zmo+34],["iso","b"])
    d.cal("tin","t<sub>TiN</sub>",f"{TTIN:g} nm","Three-sided, not four",[0,ys[2]+HY2,zo+.1],[0,ys[2]+HY3,zo+.1],[0,ys[2]+30,z3+34],["c","fork"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet-to-sheet pitch",f"{PITCH:g} nm"],
            ["t_wall","Dielectric wall thickness",f"{WALL:g} nm"],
            ["n–p","TiN-to-TiN across the wall",f"{WALL:g} nm"],
            ["N_sh","Sheets per polarity","3"],["EOT","Equivalent oxide thickness",f"{EOT:g} nm"],
            ["—","Gate faces per sheet","3 (forked)"],
            ["—","Active footprint (z)",f"{2*z3:g} nm"]]
    d.views={"iso":dict(n="Isometric",s="both polarities",az=-.80,el=.34,r=330,tgt=[0,42,0],clip=None),
             "b":dict(n="Along channel",s="source · gate · drain",az=0,el=0,r=280,tgt=[0,44,0],clip=[None,None,(zi+zo)/2]),
             "c":dict(n="Across channel",s="n | wall | p",az=1.5708,el=0,r=290,tgt=[0,48,0],clip=[0,None,None]),
             "fork":dict(n="The fork",s="p side lifted off",az=-1.25,el=.30,r=240,tgt=[0,46,0],clip=[4,None,None],
                 off=[f"epi_{g}_source" for g in "np"]+[f"nisi_{g}_source" for g in "np"]+
                     [f"ni_{g}_source" for g in "np"]+[f"w_{g}_source" for g in "np"]+
                     [f"spacer_{g}_source" for g in "np"])}
    d.note=("<b>Why the wall matters.</b> In a nanosheet cell the n and p stacks must be far enough apart "
            "for two separately patterned work-function metals plus the gate-cut margin — tens of "
            f"nanometres. The forksheet replaces that gap with a <b>{WALL:g} nm</b> SiN wall the sheets are "
            "anchored to, so nWFM and pWFM sit against opposite faces of the same wall. The price is the "
            "fourth gate face: the sheet is gated on three sides, not all around, so electrostatic control "
            "is slightly worse than a true GAA sheet of the same thickness.")
    return d.finish()

# =================================================================== CFET ===
def build_cfet(seq=False):
    key = "cfet_seq" if seq else "cfet_mono"
    d=Dev(key, "Sequential CFET" if seq else "Monolithic CFET",
      "top tier bonded on" if seq else "one continuous flow",
      ("The top tier is processed on a separate wafer and bonded on. A bonding oxide runs across "
       "the whole footprint, so the two gates are physically separate and have to be strapped "
       "together by a through-tier via.") if seq else
      ("nFET and pFET share one footprint and one gate. A middle dielectric isolation separates the "
       "two tiers everywhere except under the gate, where the Mo runs straight through from the "
       "bottom sheets to the top ones."))
    W, PITCH, MDI = 20.0, 20.0, 12.0
    hz=W/2; hz1,hz2,hz3 = hz+TIL, hz+TIL+THK, hz+TIL+THK+TTIN     # 11 13 16
    hzmo=hz3+5.0                                                   # 21
    STI=8.0
    yb=[STI+HY3+6.0, STI+HY3+6.0+PITCH]          # 22.5  42.5   bottom (n) tier
    ymdi0=yb[-1]+HY3; ymdi1=ymdi0+MDI            # 51 -> 63
    yt=[ymdi1+HY3, ymdi1+HY3+PITCH]              # 71.5  91.5   top (p) tier
    ymo=yt[-1]+HY3+6.0; ycap=ymo+6.0             # 106 -> 112
    ybsd=ymdi0                                   # bottom S/D top
    ytsd=yt[-1]+HYS+3.0; ynisi=ytsd+5.0          # 97 -> 102
    yplug=112.0; ym2=124.0
    ybm0,ybm1 = -22.0,-12.0                      # backside metal
    zsub=hzmo+6.0
    YB=[ (y-HY3,y+HY3) for y in yb ]; YT=[ (y-HY3,y+HY3) for y in yt ]
    ybond = ymdi0+6.0                            # bond plane inside the tier gap

    # ---- backside power -------------------------------------------------
    d.add("bsm","Backside power metal (W)","tungsten",[box(-48,48,ybm0,ybm1,-zsub,zsub)],"Backside power",[0,-2.0,0])
    ild=[box(-XSP,XSP,ybm1,0,-zsub,zsub)]
    for s in (-1,1):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2
        ild += [box(xa,xc-7,ybm1,0,-zsub,zsub), box(xc+7,xb,ybm1,0,-zsub,zsub),
                box(xc-7,xc+7,ybm1,0,-zsub,-hz), box(xc-7,xc+7,ybm1,0,hz,zsub)]
    d.add("bsild","Backside ILD (SiO₂)","sio2",ild,"Backside power",[0,-1.5,0])
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2
        d.add(f"via_{T.lower()}",f"Buried power via · bottom {T.lower()}","tungsten",
              [box(xc-7,xc+7,ybm1,0,-hz,hz)],"Backside power",[s*1.0,-1.2,0])
    d.add("sti","STI / bottom isolation","sio2",[box(-XSP,XSP,0,STI,-zsub,zsub)],"Substrate & isolation",[0,-.8,0])

    # ---- channels -------------------------------------------------------
    for i,yc in enumerate(yb):
        d.add(f"sheet_n{i+1}",f"nFET sheet {i+1} · bottom tier","silicon",
              [box(-XSP,XSP,yc-HYS,yc+HYS,-hz,hz)],"Bottom tier (n)",[0,0,0])
    for i,yc in enumerate(yt):
        d.add(f"sheet_p{i+1}",f"pFET sheet {i+1} · top tier","silicon",
              [box(-XSP,XSP,yc-HYS,yc+HYS,-hz,hz)],"Top tier (p)",[0,0,0])
    for tag,ylist,grp in (("n",yb,"Bottom tier (n)"),("p",yt,"Top tier (p)")):
        for i,yc in enumerate(ylist):
            d.add(f"il_{tag}{i+1}",f"SiO₂ interfacial layer · {tag}{i+1}","sio2",ring4(yc,HYS,hz,TIL,XG),grp,["radial",yc,1.0])
        for i,yc in enumerate(ylist):
            d.add(f"hk_{tag}{i+1}",f"HfO₂ high-κ · {tag}{i+1}","highk",ring4(yc,HY1,hz1,THK,XG),grp,["radial",yc,2.1])
        for i,yc in enumerate(ylist):
            d.add(f"tin_{tag}{i+1}",f"{tag}-type TiN work-function metal · {tag}{i+1}","tin",ring4(yc,HY2,hz2,TTIN,XG),grp,["radial",yc,3.3])

    # ---- tier isolation --------------------------------------------------
    if seq:
        # full-footprint bond + isolation, punched only where the through-tier via passes
        cols=[(-XSD,-XG,-zsub,zsub),(XG,XSD,-zsub,zsub),
              (-XG,XG,-zsub,hz3),(-XG,XG,hzmo,zsub)]
        mdib,bondb=[],[]
        for x0,x1,z0,z1 in cols:
            mdib.append(box(x0,x1,ymdi0,ybond,z0,z1))
            bondb.append(box(x0,x1,ybond,ybond+3,z0,z1))
            mdib.append(box(x0,x1,ybond+3,ymdi1,z0,z1))
        d.add("mdi","Middle dielectric isolation","mdi",mdib,"Tier isolation",[0,1.1,0])
        d.add("bondox","Wafer-bonding oxide","bond",bondb,"Tier isolation",[0,1.15,0])
        d.add("ttv","Through-tier gate via (W)","tungsten",
              [box(-XG,XG,ymdi0,ymdi1,hz3,hzmo)],"Tier isolation",[0,1.2,1.4])
    else:
        d.add("mdi","Middle dielectric isolation","mdi",
              [box(-XSD,-XG,ymdi0,ymdi1,-zsub,zsub), box(XG,XSD,ymdi0,ymdi1,-zsub,zsub)],
              "Tier isolation",[0,1.1,0])

    # ---- gate fill -------------------------------------------------------
    mo=[]
    blocks = YB+YT+([(ymdi0,ymdi1)] if seq else [])
    for a,b in (gaps(STI,ymo,[(ymdi0,ymdi1)]) if seq else [(STI,ymo)]):
        mo += [box(-XG,XG,a,b,hz3,hzmo), box(-XG,XG,a,b,-hzmo,-hz3)]
    for a,b in gaps(STI,ymo,blocks):
        mo.append(box(-XG,XG,a,b,-hz3,hz3))
    d.add("mo","Mo gate fill","mo",mo,"Gate electrode",[0,1.0,0])
    d.add("gatecap","TiN gate cap","tin",[box(-XG,XG,ymo,ycap,-hzmo,hzmo)],"Gate electrode",[0,1.4,0])
    d.add("gatew","W gate contact","tungsten",[box(-XG,XG,ycap,ym2,-16,16)],"Gate electrode",[0,1.8,0])

    # ---- spacers ---------------------------------------------------------
    for s,t in ((-1,"source"),(1,"drain")):
        xa,xb=sorted((s*XG,s*XSP))
        sp=[]
        for a,b in gaps(STI,ycap,[(ymdi0,ymdi1)]):
            sp += [box(xa,xb,a,b,hz,hzmo), box(xa,xb,a,b,-hzmo,-hz)]
        for a,b in gaps(STI,ycap,[(y-HYS,y+HYS) for y in yb+yt]+[(ymdi0,ymdi1)]):
            sp.append(box(xa,xb,a,b,-hz,hz))
        d.add(f"spacer_{t}",f"Si₃N₄ spacer · {t} side","si3n4",sp,"Spacers",[s*1.3,0,0])

    # ---- source / drain --------------------------------------------------
    for s,T in ((-1,"Source"),(1,"Drain")):
        xa,xb=sorted((s*XSP,s*XSD)); xc=(xa+xb)/2
        d.add(f"epi_n_{T.lower()}",f"Bottom tier {T.lower()} epi (Si:P)","silicon",
              [box(xa,xb,0,ybsd,-hz,hz)],"Bottom tier (n)",[s*1.6,-.4,0])
        d.add(f"epi_p_{T.lower()}",f"Top tier {T.lower()} epi (SiGe:B)","sige",
              [box(xa,xb,ymdi1,ytsd,-hz,hz)],"Top tier (p)",[s*1.6,.4,0])
        d.add(f"nisi_{T.lower()}",f"Top tier {T.lower()} NiSi","nisi",
              [box(xa,xb,ytsd,ynisi,-hz,hz)],"Top tier (p)",[s*1.9,.7,0])
        d.add(f"ni_{T.lower()}",f"Top tier {T.lower()} Ni plug","nickel",
              [box(xc-8,xc+8,ynisi,yplug,-8,8)],"Top tier (p)",[s*2.1,1.0,0])
        d.add(f"w_{T.lower()}",f"Top tier {T.lower()} W metal","tungsten",
              [box(xa,xb,yplug,ym2,-hz,hz)],"Top tier (p)",[s*2.3,1.4,0])

    d.cal("mdi","MDI",f"{MDI:g} nm","Vertical gap between tiers",[XG+1,ymdi0,-hz],[XG+1,ymdi1,-hz],[XSP+30,(ymdi0+ymdi1)/2,-hzmo-28],["iso","b","c","tier"])
    d.cal("tch","t<sub>ch</sub>",f"{TCH:g} nm","Sheet thickness",[-XSP,yb[0]-HYS,hz],[-XSP,yb[0]+HYS,hz],[-XSP-34,yb[0]-6,hz+34],["iso","b","c","tier"])
    d.cal("W","W<sub>sh</sub>",f"{W:g} nm","Sheet width",[-XSP,yt[1]+HYS+.6,-hz],[-XSP,yt[1]+HYS+.6,hz],[-XSP-16,yt[1]+26,0],["iso","c"])
    d.cal("pitch","Tier pitch",f"{yt[0]-yb[1]:g} nm","Bottom sheet to top sheet",[XSP,yb[1],hz],[XSP,yt[0],hz],[XSP+32,(yb[1]+yt[0])/2,hz+30],["b","c"])
    d.cal("LG","L<sub>G</sub>",f"{LG:g} nm","One gate, both tiers",[-XG,ymo+2,hzmo],[XG,ymo+2,hzmo],[0,ymo+24,hzmo+32],["iso","b"])
    d.cal("eot","t_ox",f"{TIL+THK:g} nm",f"{TIL:g} SiO₂ + {THK:g} HfO₂ · EOT {EOT:g} nm",[0,yt[1]+HYS,hz+.1],[0,yt[1]+HY2,hz+.1],[0,yt[1]+28,hz2+36],["c","tier"])
    d.dims=[["L_G","Physical gate length",f"{LG:g} nm"],["t_ch","Sheet thickness",f"{TCH:g} nm"],
            ["W_sh","Sheet width",f"{W:g} nm"],["Pitch","Sheet pitch within a tier",f"{PITCH:g} nm"],
            ["t_MDI","Middle dielectric isolation",f"{MDI:g} nm"],
            ["N_sh","Sheets per tier","2"],["EOT","Equivalent oxide thickness",f"{EOT:g} nm"],
            ["—","Bottom tier contact","backside power via"],
            ["—","Gate","shared, strapped by a via" if seq else "shared, continuous Mo"],
            ["—","Active footprint (z)",f"{2*hz3:g} nm"]]
    d.views={"b":dict(n="Along channel",s="both tiers in section",az=0,el=0,r=310,tgt=[0,52,0],clip=[None,None,0]),
             "iso":dict(n="Isometric",s="the stacked pair",az=-.80,el=.30,r=360,tgt=[0,50,0],clip=None),
             "c":dict(n="Across channel",s="through the gate",az=1.5708,el=0,r=300,tgt=[0,56,0],clip=[0,None,None]),
             "tier":dict(n="Tier interface",s="source side lifted off",az=-1.18,el=.26,r=270,tgt=[0,54,0],clip=[4,None,None],
                 off=["epi_n_source","epi_p_source","nisi_source","ni_source","w_source","spacer_source"])}
    d.note=(("<b>Bonded, not grown.</b> The top tier arrives on its own wafer, so a bonding oxide runs "
             "across the entire footprint — including under the gate. The two gates are therefore separate "
             "conductors and must be tied together by the through-tier via you can see at the edge of the "
             "gate. The payoff is freedom: the top tier can use a different crystal orientation or a "
             "different channel material entirely, as long as everything after bonding stays below ~500 °C.")
            if seq else
            ("<b>One gate, two tiers.</b> The middle dielectric isolation stops at the gate edge — inside "
             "the gate the Mo runs continuously from the bottom sheets to the top ones, which is what makes "
             "this a <i>complementary</i> FET: one gate input drives both the n and the p device, so an "
             "inverter collapses into a single stack. The bottom tier can no longer be reached from above, "
             "so its source/drain is contacted downwards through a buried power via."))
    return d.finish()

# ================================================================ COMPARE ===
def build_cmp():
    d=Dev("cmp","Footprint compare","same scale, gate section only",
      "The same gate cross-section for all four architectures at one scale and one channel width. "
      "Everything outside the gate is stripped, so the only thing left to compare is how much cell "
      "width each one spends on a single n-p pair — and how much effective width it gets back.")
    Wc, P3, P2, MDI, STI = 22.0, 21.0, 20.0, 12.0, 8.0
    WFIN, HFIN, FPITCH = 6.0, 45.0, 27.0
    hz=Wc/2; hzt=hz+TIL+THK+TTIN                        # 11 -> 17
    wh=WFIN/2; w3=wh+TIL+THK+TTIN                       # 3 -> 9
    def stack4(pre,grp,zc,ys):
        for i,yc in enumerate(ys):
            d.add(f"{pre}_s{i+1}",f"Si sheet {i+1}","silicon",[box(-XG,XG,yc-HYS,yc+HYS,zc-hz,zc+hz)],grp,[0,0,0])
            for nm,mat,hy,h,t,mg in (("il","sio2",HYS,hz,TIL,1.0),("hk","highk",HY1,hz+TIL,THK,2.1),
                                     ("tin","tin",HY2,hz+TIL+THK,TTIN,3.3)):
                bs=ring4(yc,hy,h,t,XG)
                for b in bs: b[2]+=zc
                d.add(f"{pre}_{nm}{i+1}",{"il":"SiO₂ interfacial layer","hk":"HfO₂ high-κ",
                      "tin":"TiN work-function metal"}[nm]+f" · sheet {i+1}",mat,bs,grp,["radial",yc,mg,zc])
    def forkstack(pre,grp,s_,ys):
        zi,zo=4.0,4.0+Wc
        for i,yc in enumerate(ys):
            zz=sorted((s_*zi,s_*zo))
            d.add(f"{pre}_s{i+1}",f"Si sheet {i+1}","silicon",[box(-XG,XG,yc-HYS,yc+HYS,zz[0],zz[1])],grp,[0,0,0])
            d.add(f"{pre}_il{i+1}",f"SiO₂ interfacial layer · sheet {i+1}","sio2",fork3(yc,HYS,zi,zo,TIL,XG,s_),grp,["radial",yc,1.0])
            d.add(f"{pre}_hk{i+1}",f"HfO₂ high-κ · sheet {i+1}","highk",fork3(yc,HY1,zi,zo+TIL,THK,XG,s_),grp,["radial",yc,2.1])
            d.add(f"{pre}_tin{i+1}",f"TiN work-function metal · sheet {i+1}","tin",fork3(yc,HY2,zi,zo+TIL+THK,TTIN,XG,s_),grp,["radial",yc,3.3])
    def finstack(pre,grp,zc,ytop):
        for i,z in enumerate((zc-FPITCH/2, zc+FPITCH/2)):
            d.add(f"{pre}_f{i+1}",f"Si fin {i+1}","silicon",[box(-XG,XG,0,ytop,z-wh,z+wh)],grp,[0,0,0])
            for nm,mat,ww,yy,t,mg in (("il","sio2",wh,ytop,TIL,1.0),("hk","highk",wh+TIL,ytop+TIL,THK,2.1),
                                      ("tin","tin",wh+TIL+THK,ytop+TIL+THK,TTIN,3.3)):
                d.add(f"{pre}_{nm}{i+1}",{"il":"SiO₂ interfacial layer","hk":"HfO₂ high-κ",
                      "tin":"TiN work-function metal"}[nm]+f" · fin {i+1}",mat,
                      finwrap(z,ww,STI,yy,t,XG),grp,["radial",(STI+ytop)/2,mg,z])

    CELLS=[]
    # --- FinFET pair ------------------------------------------------------
    zF=-330.0; hzF=(FPITCH/2+w3); sepF=hzF+12.0          # device half 22.5, n-p gap 24
    ytopF=STI+HFIN; ymoF=ytopF+TIL+THK+TTIN+12.0
    for s_,tag in ((1,"n"),(-1,"p")): finstack(f"F_{tag}","FinFET cell",zF+s_*sepF,ytopF)
    moF=[box(-XG,XG,STI,ymoF,zF+sepF+hzF,zF+sepF+hzF+5), box(-XG,XG,STI,ymoF,zF-sepF-hzF-5,zF-sepF-hzF),
         box(-XG,XG,STI,ymoF,zF-sepF+hzF,zF+sepF-hzF)]
    for s_ in (1,-1):
        c=zF+s_*sepF
        moF.append(box(-XG,XG,STI,ymoF,c-FPITCH/2+w3,c+FPITCH/2-w3))
        for z in (c-FPITCH/2,c+FPITCH/2):
            moF.append(box(-XG,XG,ytopF+TIL+THK+TTIN,ymoF,z-w3,z+w3))
    d.add("F_mo","Mo gate fill","mo",moF,"FinFET cell",[0,1.0,0])
    stiF=[]; eg=[zF-sepF-hzF-5]
    for s_ in (-1,1):
        c=zF+s_*sepF
        for z in (c-FPITCH/2,c+FPITCH/2): eg += [z-wh,z+wh]
    eg.append(zF+sepF+hzF+5)
    for i in range(0,len(eg),2):
        if eg[i+1]>eg[i]: stiF.append(box(-XG,XG,0,STI,eg[i],eg[i+1]))
    d.add("F_sti","STI (fin reveal)","sio2",stiF,"FinFET cell",[0,-.8,0])
    d.add("F_sub","Si substrate","silicon",[box(-XG,XG,-14,0,zF-sepF-hzF-5,zF+sepF+hzF+5)],"FinFET cell",[0,-1.2,0])
    CELLS.append((zF,2*(sepF+hzF),"FinFET","2 fins per device",ymoF,2*(2*HFIN+WFIN)))

    # --- Nanosheet pair ---------------------------------------------------
    zA=-170.0; sep=(hzt*2+24)/2
    ysA=[STI+HY3+6.0+i*P3 for i in range(3)]; ymoA=ysA[-1]+HY3+8.0
    stack4("A_n","Nanosheet cell",zA+sep,ysA); stack4("A_p","Nanosheet cell",zA-sep,ysA)
    moA=[box(-XG,XG,STI,ymoA,zA+sep+hzt,zA+sep+hzt+5), box(-XG,XG,STI,ymoA,zA-sep-hzt-5,zA-sep-hzt)]
    for a,b in gaps(STI,ymoA,[(y-HY3,y+HY3) for y in ysA]):
        moA += [box(-XG,XG,a,b,zA+sep-hzt,zA+sep+hzt), box(-XG,XG,a,b,zA-sep-hzt,zA-sep+hzt)]
    moA.append(box(-XG,XG,STI,ymoA,zA-sep+hzt,zA+sep-hzt))
    d.add("A_mo","Mo gate fill","mo",moA,"Nanosheet cell",[0,1.0,0])
    d.add("A_sti","STI","sio2",[box(-XG,XG,0,STI,zA-sep-hzt-5,zA+sep+hzt+5)],"Nanosheet cell",[0,-.8,0])
    d.add("A_sub","Si substrate","silicon",[box(-XG,XG,-14,0,zA-sep-hzt-5,zA+sep+hzt+5)],"Nanosheet cell",[0,-1.2,0])
    CELLS.append((zA,2*(sep+hzt),"Nanosheet","3 sheets per device",ymoA,3*(2*Wc+2*TCH)))

    # --- Forksheet pair ---------------------------------------------------
    zBo=4.0+Wc+TIL+THK+TTIN
    forkstack("B_n","Forksheet cell",1,ysA); forkstack("B_p","Forksheet cell",-1,ysA)
    d.add("B_wall","SiN dielectric wall","wall",[box(-XG,XG,STI,ymoA,-4,4)],"Forksheet cell",[0,1.6,0])
    moB=[box(-XG,XG,STI,ymoA,zBo,zBo+5), box(-XG,XG,STI,ymoA,-zBo-5,-zBo)]
    for a,b in gaps(STI,ymoA,[(y-HY3,y+HY3) for y in ysA]):
        moB += [box(-XG,XG,a,b,4,zBo), box(-XG,XG,a,b,-zBo,-4)]
    d.add("B_mo","Mo gate fill","mo",moB,"Forksheet cell",[0,1.0,0])
    d.add("B_sti","STI","sio2",[box(-XG,XG,0,STI,-zBo-5,zBo+5)],"Forksheet cell",[0,-.8,0])
    d.add("B_sub","Si substrate","silicon",[box(-XG,XG,-14,0,-zBo-5,zBo+5)],"Forksheet cell",[0,-1.2,0])
    CELLS.append((0.0,2*zBo,"Forksheet","3 sheets per device",ymoA,3*(2*Wc+TCH)))

    # --- CFET -------------------------------------------------------------
    zC=90.0
    ybC=[STI+HY3+6.0, STI+HY3+6.0+P2]; m0=ybC[-1]+HY3; m1=m0+MDI
    ytC=[m1+HY3, m1+HY3+P2]; ymoC=ytC[-1]+HY3+8.0
    stack4("C_n","CFET cell",zC,ybC); stack4("C_p","CFET cell",zC,ytC)
    moC=[box(-XG,XG,STI,ymoC,zC+hzt,zC+hzt+5), box(-XG,XG,STI,ymoC,zC-hzt-5,zC-hzt)]
    for a,b in gaps(STI,ymoC,[(y-HY3,y+HY3) for y in ybC+ytC]):
        moC.append(box(-XG,XG,a,b,zC-hzt,zC+hzt))
    d.add("C_mo","Mo gate fill","mo",moC,"CFET cell",[0,1.0,0])
    d.add("C_sti","STI","sio2",[box(-XG,XG,0,STI,zC-hzt-5,zC+hzt+5)],"CFET cell",[0,-.8,0])
    d.add("C_sub","Si substrate","silicon",[box(-XG,XG,-14,0,zC-hzt-5,zC+hzt+5)],"CFET cell",[0,-1.2,0])
    CELLS.append((zC,2*hzt,"CFET","2 sheets per tier",ymoC,2*(2*Wc+2*TCH)))

    w0=CELLS[0][1]
    for zc,w,nm,sub_,yy,we in CELLS:
        d.cal(f"w_{nm}",nm,f"{w:g} nm",f"active footprint · {w/w0*100:.0f}% of FinFET",[0,-16,zc-w/2],[0,-16,zc+w/2],[0,-42,zc],None)
        d.cal(f"h_{nm}",nm,"",sub_,[0,yy,zc],[0,yy+1,zc],[0,yy+28,zc],None)
    d.dims=[[nm,f"{sub_} · W_eff {we:g} nm",f"{w:g} nm  ({w/w0*100:.0f}%)"] for zc,w,nm,sub_,yy,we in CELLS]
    d.dims.append(["—","Channel width used for all four",f"{Wc:g} nm (fin: {WFIN:g}×{HFIN:g} nm)"])
    d.dims.append(["W_eff/nm","Effective width per nm of footprint",
                   " · ".join(f"{nm[:4]} {we/w:.2f}" for zc,w,nm,sub_,yy,we in CELLS)])
    zmid=(CELLS[0][0]-CELLS[0][1]/2 + CELLS[-1][0]+CELLS[-1][1]/2)/2
    d.views={"b":dict(n="Head on",s="footprint widths",az=-1.5708,el=0,r=780,tgt=[0,38,zmid],clip=None),
             "iso":dict(n="All four",s="same scale",az=-1.30,el=.24,r=840,tgt=[0,40,zmid],clip=None),
             "c":dict(n="From above",s="how the area is used",az=-1.5708,el=1.05,r=780,tgt=[0,38,zmid],clip=None)}
    d.note=("<b>What is actually being saved.</b> These are device footprints, not standard-cell heights — "
            "a real cell also carries power rails and routing tracks, so published cell numbers shrink less "
            "than the numbers above. imec quotes roughly 5T → 4.3T for the forksheet, and CFET is generally "
            "credited with a 1.5–2× area gain. The number worth watching is the last row: effective width "
            "per nanometre of footprint. It climbs the whole way — 1.7 → 1.8 → 2.3 → 3.2 — which is the "
            "entire point of the roadmap. Note also what the CFET gives up to get there: four sheets per "
            "n-p pair against six, because stacking two tiers inside a sensible gate height costs you sheets.")
    return d.finish()

# =================================================================== MAIN ===
if __name__ == "__main__":
    devs=[build_fin(), build_ns(), build_fs(), build_cfet(False), build_cfet(True), build_cmp()]
    out=dict(materials=MAT, order=ORDER, devices=[])
    for d in devs:
        m,n = check(d)
        print(f"{d.key:10s} parts={len(d.parts):3d} boxes={n:4d}  max solids/voxel={m}")
        out["devices"].append(dict(key=d.key,name=d.name,tag=d.tag,blurb=d.blurb,parts=d.parts,
            callouts=d.callouts,dims=d.dims,views=d.views,note=d.note,bounds=d.bounds,
            groups=list(dict.fromkeys(p["group"] for p in d.parts))))
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "devices.json")
    json.dump(out, open(out_path, "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize(out_path)//1024, "KB")
