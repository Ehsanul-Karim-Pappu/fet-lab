"""
Parametric 3-stacked nanosheet FET (GAA NS-FET) — single source of truth.
Coordinates in nanometres.
  x : source -> drain (gate-length direction)
  y : vertical (stacking direction)
  z : sheet-width direction
Everything is an axis-aligned box. Shells are built as 4 plates so the
model tiles exactly: no overlapping solids, no gaps.
"""
import json, os, math, os

# ---------------------------------------------------------------- parameters
P = dict(
    t_ch      = 5.0,    # nanosheet (channel) thickness
    W_sh      = 30.0,   # nanosheet width
    L_G       = 15.0,   # physical gate length
    L_SP      = 7.0,    # spacer length
    L_SD      = 22.0,   # source/drain epi length
    pitch     = 21.0,   # vertical sheet pitch
    t_il      = 1.0,    # SiO2 interfacial layer
    t_hk      = 2.0,    # HfO2 high-k
    t_tin     = 3.0,    # TiN work-function metal
    sti_h     = 10.0,   # STI / bottom isolation
    sub_h     = 26.0,   # substrate slab shown
    n_sheets  = 3,
)
k_hfo2, k_sio2 = 22.0, 3.9
P["EOT"] = round(P["t_il"] + P["t_hk"] * k_sio2 / k_hfo2, 2)

tch, Wsh, LG, LSP, LSD = P["t_ch"], P["W_sh"], P["L_G"], P["L_SP"], P["L_SD"]
til, thk, ttin = P["t_il"], P["t_hk"], P["t_tin"]
pitch, sti_h, sub_h = P["pitch"], P["sti_h"], P["sub_h"]

x_g   = LG / 2.0                 #  7.5  gate half-length
x_sp  = x_g + LSP                # 14.5  spacer outer edge
x_sd  = x_sp + LSD               # 36.5  S/D outer edge
hz_sh = Wsh / 2.0                # 15    sheet half-width
hy_sh = tch / 2.0                # 2.5

hz_il, hz_hk, hz_tin = hz_sh + til, hz_sh + til + thk, hz_sh + til + thk + ttin   # 16,18,21
hy_il, hy_hk, hy_tin = hy_sh + til, hy_sh + til + thk, hy_sh + til + thk + ttin   # 3.5,5.5,8.5
hz_mo = hz_tin + 5.0             # 26   gate-fill half-width
y_sti = sti_h                    # 10   top of STI
y1    = y_sti + hy_tin + 6.0     # 24.5 bottom sheet centre (6 nm Mo under stack)
ys    = [y1 + i * pitch for i in range(P["n_sheets"])]     # 24.5, 45.5, 66.5
y_mo_top = ys[-1] + hy_tin + 9.0                           # 84
y_cap_top = y_mo_top + 6.0                                 # 90  TiN gate cap
y_sd_top  = ys[-1] + hy_sh + 3.0                           # 72  top of S/D epi
y_nisi    = y_sd_top + 5.0                                 # 77
y_plug    = 92.0
y_m2      = 102.0
hz_sub    = 35.0
x_sub     = 48.0

P.update(x_g=x_g, x_sp=x_sp, x_sd=x_sd, sheet_y=ys, y_mo_top=y_mo_top, y_m2=y_m2)

# ---------------------------------------------------------------- materials
from build_devices import MAT as DEVICE_MATERIALS
MAT = {k: dict(DEVICE_MATERIALS[k]) for k in ("silicon","sio2","highk","si3n4","mo","cobalt","tungsten","tisi","tin","nwf")}

ORDER = ["silicon","sio2","highk","si3n4","nwf","tin","mo","tisi","cobalt","tungsten"]

parts = []   # {id, name, material, group, boxes:[[cx,cy,cz,dx,dy,dz],...], explode}
def add(pid, name, material, boxes, group, explode=None):
    parts.append(dict(id=pid, name=name, material=material, group=group,
                      boxes=[[round(v,4) for v in b] for b in boxes],
                      explode=explode))

def shell(yc, hy, hz, t, xh):
    """4 plates forming a closed ring in the y-z plane, extruded along x."""
    return [
        [0, yc + hy + t/2, 0,  2*xh, t, 2*(hz+t)],   # top
        [0, yc - hy - t/2, 0,  2*xh, t, 2*(hz+t)],   # bottom
        [0, yc,  hz + t/2,     2*xh, 2*hy, t],       # +z
        [0, yc, -hz - t/2,     2*xh, 2*hy, t],       # -z
    ]

# ---------------------------------------------------------------- substrate
add("substrate", "Si substrate", "silicon",
    [[0, -sub_h/2, 0, 2*x_sub, sub_h, 2*hz_sub]], "Substrate & isolation", [0,-1.2,0])
add("sti", "STI / bottom isolation", "sio2",
    [[0, sti_h/2, 0, 2*x_sp, sti_h, 2*hz_sub]], "Substrate & isolation", [0,-0.8,0])

# ---------------------------------------------------------------- channels
for i, yc in enumerate(ys):
    add(f"sheet{i+1}", f"Si nanosheet {i+1}", "silicon",
        [[0, yc, 0, 2*x_sp, tch, Wsh]], "Channel stack", [0,0,0])

# ------------------------------------------------- gate-all-around dielectric
for i, yc in enumerate(ys):
    add(f"il{i+1}", f"SiO₂ interfacial layer (sheet {i+1})", "sio2",
        shell(yc, hy_sh, hz_sh, til, x_g), "Gate-all-around stack", ["radial", yc, 1.0])
for i, yc in enumerate(ys):
    add(f"hk{i+1}", f"HfO₂ high-κ (sheet {i+1})", "highk",
        shell(yc, hy_il, hz_il, thk, x_g), "Gate-all-around stack", ["radial", yc, 2.1])
for i, yc in enumerate(ys):
    add(f"tin{i+1}", f"n-type work-function metal (sheet {i+1})", "nwf",
        shell(yc, hy_hk, hz_hk, ttin, x_g), "Gate-all-around stack", ["radial", yc, 3.3])

# ---------------------------------------------------------------- gate fill
mo_boxes = []
for s in (1, -1):
    mo_boxes.append([0, (y_sti+y_mo_top)/2, s*(hz_tin+hz_mo)/2,
                     2*x_g, y_mo_top-y_sti, hz_mo-hz_tin])
seg = [(y_sti, ys[0]-hy_tin)]
for i in range(len(ys)-1):
    seg.append((ys[i]+hy_tin, ys[i+1]-hy_tin))
seg.append((ys[-1]+hy_tin, y_mo_top))
for a, b in seg:
    mo_boxes.append([0, (a+b)/2, 0, 2*x_g, b-a, 2*hz_tin])
add("mo", "Mo gate fill", "mo", mo_boxes, "Gate electrode", [0, 1.0, 0])
add("gatecap", "TiN gate cap", "tin",
    [[0, (y_mo_top+y_cap_top)/2, 0, 2*x_g, y_cap_top-y_mo_top, 2*hz_mo]],
    "Gate electrode", [0, 1.4, 0])
add("gatew", "W gate contact", "tungsten",
    [[0, (y_cap_top+y_m2)/2, 0, 2*x_g, y_m2-y_cap_top, 40.0]],
    "Gate electrode", [0, 1.8, 0])

# ---------------------------------------------------------------- spacers
for s, tag in ((-1, "source"), (1, "drain")):
    xc = s*(x_g + x_sp)/2
    bx = []
    for sz in (1, -1):
        bx.append([xc, (y_sti+y_cap_top)/2, sz*(hz_sh+hz_mo)/2,
                   LSP, y_cap_top-y_sti, hz_mo-hz_sh])
    ss = [(y_sti, ys[0]-hy_sh)]
    for i in range(len(ys)-1):
        ss.append((ys[i]+hy_sh, ys[i+1]-hy_sh))
    ss.append((ys[-1]+hy_sh, y_cap_top))
    for a, b in ss:
        bx.append([xc, (a+b)/2, 0, LSP, b-a, Wsh])
    add(f"spacer_{tag}", f"Si₃N₄ spacer ({tag} side)", "si3n4", bx,
        "Spacers", [s*1.3, 0, 0])

# ---------------------------------------------------------------- S/D + contacts
for s, tag in ((-1, "Source"), (1, "Drain")):
    xc = s*(x_sp + x_sd)/2
    add(f"epi_{tag.lower()}", f"{tag} epi (Si)", "silicon",
        [[xc, y_sd_top/2, 0, LSD, y_sd_top, Wsh]], "Source / drain", [s*1.6, 0, 0])
    add(f"nisi_{tag.lower()}", f"{tag} TiSiₓ silicide", "tisi",
        [[xc, (y_sd_top+y_nisi)/2, 0, LSD, y_nisi-y_sd_top, Wsh]], "Source / drain", [s*1.9, 0.3, 0])
    add(f"ni_{tag.lower()}", f"{tag} Co contact plug", "cobalt",
        [[xc, (y_nisi+y_plug)/2, 0, 16.0, y_plug-y_nisi, 24.0]], "Source / drain", [s*2.1, 0.8, 0])
    add(f"w_{tag.lower()}", f"{tag} W metal", "tungsten",
        [[xc, (y_plug+y_m2)/2, 0, LSD, y_m2-y_plug, Wsh]], "Source / drain", [s*2.3, 1.3, 0])

# ---------------------------------------------------------------- callouts
CALLOUTS = [
 dict(id="LG", v=["iso","b"],   tex="L_G", label="L<sub>G</sub>", value=f"{LG:g} nm", desc="Physical gate length",
      a=[-x_g, y_mo_top+2, hz_mo], b=[x_g, y_mo_top+2, hz_mo], lab=[0, y_mo_top+22, hz_mo+36]),
 dict(id="LSP", v=["iso","b"],  tex="L_SP", label="L<sub>SP</sub>", value=f"{LSP:g} nm", desc="Spacer length",
      a=[x_g, y_cap_top+1, hz_mo], b=[x_sp, y_cap_top+1, hz_mo], lab=[x_sp+30, y_cap_top+16, hz_mo+22]),
 dict(id="tch", v=["iso","b","c","gaa"],  tex="t_ch", label="t<sub>ch</sub>", value=f"{tch:g} nm", desc="Nanosheet thickness",
      a=[-x_sp, ys[1]-hy_sh, hz_sh], b=[-x_sp, ys[1]+hy_sh, hz_sh], lab=[-x_sp-34, ys[1], hz_sh+34]),
 dict(id="W", v=["iso","c"],    tex="W_sh", label="W<sub>sh</sub>", value=f"{Wsh:g} nm", desc="Nanosheet width",
      a=[-x_sp, ys[0]-hy_sh-0.6, -hz_sh], b=[-x_sp, ys[0]-hy_sh-0.6, hz_sh], lab=[0, ys[0]-26, hz_sub+14]),
 dict(id="pitch", v=["b","c"],tex="pitch", label="Sheet pitch", value=f"{pitch:g} nm", desc="Vertical sheet-to-sheet pitch",
      a=[x_sp, ys[0], -hz_sh], b=[x_sp, ys[1], -hz_sh], lab=[x_sp+34, (ys[0]+ys[1])/2, -hz_sh-30]),
 dict(id="eot", v=["c","gaa","iso"],  tex="t_ox", label="t_ox", value=f"{til+thk:g} nm", desc=f"Physical stack; EOT {P['EOT']:g} nm under assumed permittivities",
      a=[0, ys[2]+hy_sh, hz_sh+0.1], b=[0, ys[2]+hy_hk, hz_sh+0.1], lab=[0, ys[2]+32, hz_hk+40]),
 dict(id="tin", v=["c","gaa"],  tex="t_TiN", label="t<sub>WFM</sub>", value=f"{ttin:g} nm", desc="n-type work-function metal",
      a=[0, ys[2]+hy_hk, -hz_sh-0.1], b=[0, ys[2]+hy_tin, -hz_sh-0.1], lab=[0, ys[2]+26, -hz_tin-38]),
]

out = dict(params=P, materials=MAT, order=ORDER, parts=parts, callouts=CALLOUTS,
           bounds=dict(x=[-x_sub, x_sub], y=[-sub_h, y_m2], z=[-hz_sub, hz_sub]))
HERE = os.path.dirname(os.path.abspath(__file__))
json.dump(out, open(os.path.join(os.path.dirname(HERE), "data", "geometry.json"), "w"), indent=1)

# ------------------------------------------------------------------ sanity
n_boxes = sum(len(p["boxes"]) for p in parts)
vol = sum(b[3]*b[4]*b[5] for p in parts for b in p["boxes"])
print(f"parts={len(parts)}  boxes={n_boxes}  total volume={vol:,.0f} nm^3")
print("EOT =", P["EOT"], "nm   sheet centres:", ys)
# overlap check on a coarse voxel grid
import numpy as np
STEP=0.5
gx=np.arange(-x_sd-1, x_sd+1, STEP); gy=np.arange(-sub_h, y_m2, STEP); gz=np.arange(-hz_sub, hz_sub, STEP)
cnt=np.zeros((len(gx),len(gy),len(gz)), np.uint8)
for p in parts:
    for cx,cy,cz,dx,dy,dz in p["boxes"]:
        ix=(gx>cx-dx/2)&(gx<cx+dx/2); iy=(gy>cy-dy/2)&(gy<cy+dy/2); iz=(gz>cz-dz/2)&(gz<cz+dz/2)
        cnt[np.ix_(ix,iy,iz)] += 1
print("max solids per voxel =", int(cnt.max()), "(1 = no overlapping solids)")
