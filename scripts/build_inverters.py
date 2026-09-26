"""
CMOS inverter standard cells in four architectures.
Every part carries a `net` so the viewer can light the conducting path:
  vdd | gnd | out | in | chan_p | chan_n | body
"""
import json, os
from pathlib import Path
DATA = Path(__file__).resolve().parent.parent / "data/devices.json"
from build_devices import (Dev, box, ring4, fork3, finwrap, gaps, check,
                           MAT, ORDER, WFM, WFL, TCH, LSP, LSD, TIL, THK, TTIN, EOT,
                           HYS, HY1, HY2, HY3)

NOTE_NS = ("<b>One input, complementary devices.</b> The two gates share an input conductor. Each device has its own illustrative work-function metal: an Al-containing n-type metal for the nFET and TiN for the pFET. Actual threshold tuning requires process-specific gate stacks. IN/OUT colors show ideal logic states, not simulated currents. Sheets are drawn 21nm apart (centre to centre) so every film shows; real stacks space them roughly 7-12nm apart, where the work-function metal fills the gap with no fill metal.")
NOTE_FIN = ("<b>Fin-count sizing.</b> Both transistors use two fins, giving a geometric width ratio of 1. Adding a third pFET fin would make that ratio 1.5. Neither ratio guarantees electrical balance: mobility, threshold, strain and contacts also matter. This viewer does not calculate switching delay or current.")
NOTE_FS = ("<b>A common input over a wall.</b> The TiN gate cap bridges the inner wall, joining the two gate-fill regions, in this illustrative cell. Reduced n/p spacing can save lateral span, but does not remove all gate-patterning and contact constraints. Sheets are drawn 21nm apart (centre to centre) so every film shows; real stacks space them roughly 7-12nm apart, where the work-function metal fills the gap with no fill metal.")
NOTE_CFET = ("<b>Stacked inverter example.</b> The nFET is below the pFET, with a common input and connected drains. A backside GND path and an output riser are choices in this drawing; they are not the only possible CFET contact scheme. The model is not a characterized standard cell. Sheets are drawn 20nm apart (centre to centre) so every film shows; real stacks space them roughly 7-12nm apart, where the work-function metal fills the gap with no fill metal.")

def A(d, pid, name, mat, boxes, group, explode, net="body"):
    d.add(pid, name, mat, boxes, group, explode)
    d.parts[-1]["net"] = net

# ---------------------------------------------------------------- metal deck
def deck(d, C):
    """Rails, local interconnect, vias and pads shared by every cell."""
    xg, xsp, xsd = C["xg"], C["xsp"], C["xsd"]
    zr, xc = C["zrail"], C["xcell"]
    y0, y1 = C["ym0"], C["ym0t"]          # local interconnect (M0)
    yv, ym, ymt = C["ym0t"], C["ym1"], C["ym1t"]
    xs0, xs1 = -xsd, -xsp                 # source side
    xd0, xd1 = xsp, xsd                   # drain side

    # --- M0 local interconnect -------------------------------------------
    for tag, net, zlo, zhi in C["m0"]:
        xa, xb = (xs0, xs1) if tag.startswith("s") else (xd0, xd1)
        A(d, f"m0_{tag}", C["m0name"][tag], "cobalt",
          [box(xa, xb, y0, y1, zlo, zhi)], "Local interconnect", [0, .9, 0], net)

    # --- M1 rails, output bar, input pad ---------------------------------
    if C.get("vdd_top", True):
        A(d, "rail_vdd", "V_DD rail (M1)", "tungsten",
          [box(-xc, xc, ym, ymt, zr - 6, zr + 6)], "Power & signal", [0, 1.6, .8], "vdd")
    if C.get("gnd_top", True):
        A(d, "rail_gnd", "GND rail (M1)", "tungsten",
          [box(-xc, xc, ym, ymt, -zr - 6, -zr + 6)], "Power & signal", [0, 1.6, -.8], "gnd")
    A(d, "bar_out", "Output node (M1)", "tungsten",
      [box(xd0 + 5, xd1 - 3, ym, ymt, C["zout"][0], C["zout"][1])], "Power & signal", [0, 1.6, 0], "out")
    A(d, "pad_in", "Input pad (M1)", "tungsten",
      [box(-xg, xg, ym, ymt, C["zin"][0], C["zin"][1])], "Power & signal", [0, 1.7, 0], "in")

    # --- vias -------------------------------------------------------------
    vias = []
    for vid, net, xa, xb, za, zb, ya, yb in C["vias"]:
        vias.append((vid, net, box(xa, xb, ya, yb, za, zb)))
    for vid, net, b in vias:
        A(d, f"via_{vid}", C["vianame"][vid], "tungsten", [b], "Power & signal", [0, 1.3, 0], net)

    # --- gate strap -------------------------------------------------------
    A(d, "gatevia", "Gate contact (input)", "tungsten",
      [box(-xg + 1, xg - 1, C["ygate"], ym, C["zin"][0] + 1, C["zin"][1] - 1)],
      "Power & signal", [0, 1.5, 0], "in")

    # --- cell boundary ----------------------------------------------------
    t = 1.2
    A(d, "cellbox", "Cell boundary", "cellmark",
      [box(-xc, xc, 0, t, zr + 6 - t, zr + 6),
       box(-xc, xc, 0, t, -zr - 6, -zr - 6 + t),
       box(-xc, -xc + t, 0, t, -zr - 6 + t, zr + 6 - t),
       box(xc - t, xc, 0, t, -zr - 6 + t, zr + 6 - t)],
      "Cell boundary", [0, -1.4, 0], "body")

# ---------------------------------------------------------------- finishing
def finish(d, C, arch, extra_dims, note="", zcut=0.0):
    d.logic = True
    d.note = note
    d.cal("vdd", "V<sub>DD</sub>", "", "rail feeding the pMOS source",
          [0, C["ym1"], C["zrail"]], [0, C["ym1t"], C["zrail"]], [0, C["ym1t"] + 26, C["zrail"] + 22], None)
    d.cal("gnd", "GND", "", "rail at the nMOS source",
          [0, C["gndy"], C["gndz"]], [0, C["gndy"] + 1, C["gndz"]], [0, C["gndy"] - 26, C["gndz"] - 22], None)
    d.cal("out", "OUT", "", "both drains tied together",
          [C["xsp"] + 6, C["ym1"], 0], [C["xsd"] - 3, C["ym1"], 0], [C["xsd"] + 26, C["ym1t"] + 20, 0], None)
    d.cal("inn", "IN", "", "one gate across both devices",
          [0, C["ym1"], C["zin"][0]], [0, C["ym1"], C["zin"][1]], [-C["xcell"] - 20, C["ym1t"] + 22, 0], None)
    d.dims = extra_dims
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0]+B["x"][1])/2, (B["y"][0]+B["y"][1])/2, (B["z"][0]+B["z"][1])/2]
    R = 2.30 * max(B["x"][1]-B["x"][0], B["y"][1]-B["y"][0], B["z"][1]-B["z"][0])
    hi = [B["x"][1], B["y"][1], B["z"][1]]
    d.views = {
      "cell": dict(n="3D overview", s="everything wired up", az=-.82, el=.32, r=R, tgt=ctr, clip=None),
      "gate": dict(n="Through the gate", s="both devices in section", az=1.5708, el=0, r=R*.92, tgt=ctr, clip=[0, None, None]),
      "chan": dict(n="Along the channel", s="source · gate · drain", az=0, el=.02, r=R*.76, tgt=ctr, clip=[None, None, zcut]),
      "plan": dict(n="Routing", s="rails and interconnect", az=-1.5708, el=1.02, r=R*.88, tgt=ctr, clip=None),
      "top": dict(n="Top view", s="straight down on the cell", az=-1.5708, el=1.45,
                  r=2.1 * max(B["z"][1]-B["z"][0], (B["x"][1]-B["x"][0]) * 1.5), tgt=ctr, clip=None)}
    return d

# ============================================================ NANOSHEET INV =
def inv_ns():
    d = Dev("inv_ns", "Nanosheet inverter", "GAA · 3 sheets per device",
            "An illustrative CMOS inverter with three nanosheets per transistor. The two gates share IN; the pFET source connects to V_DD, the nFET source to GND, and their drains connect to OUT.")
    W, PITCH, STI = 22.0, 21.0, 10.0
    LG, xg = 15.0, 7.5; xsp, xsd = xg + LSP, xg + LSP + LSD
    hz = W / 2; hz1, hz2, hz3 = hz + TIL, hz + TIL + THK, hz + TIL + THK + TTIN
    ys = [STI + HY3 + 6 + i * PITCH for i in range(3)]
    ymo = ys[-1] + HY3 + 9; ycap = ymo + 6
    ysd = ys[-1] + HYS + 3; ynisi = ysd + 5
    zc = 30.0; zg = zc + hz3 + 5; zr = zg + 10; xc = xsd + 4
    ym0, ym0t, ym1, ym1t = ynisi, ynisi + 15, ynisi + 21, ynisi + 31

    A(d, "substrate", "Si substrate", "silicon", [box(-xc + 3, xc - 3, -22, 0, -zr - 2, zr + 2)], "Substrate & isolation", [0, -1.2, 0])
    A(d, "sti", "STI / bottom isolation", "sio2", [box(-xsd, xsd, 0, STI, -zr - 2, zr + 2)], "Substrate & isolation", [0, -.8, 0])
    for s, pol, grp in ((1, "p", "pMOS (pull-up)"), (-1, "n", "nMOS (pull-down)")):
        z0 = s * zc; net = "chan_p" if s > 0 else "chan_n"
        for i, yy in enumerate(ys):
            A(d, f"{pol}_s{i+1}", f"{pol}MOS sheet {i+1}", "silicon",
              [box(-xsp, xsp, yy - HYS, yy + HYS, z0 - hz, z0 + hz)], grp, [0, 0, 0], net)
        for nm, mat, hy, h, t, mg, lab in (("il", "sio2", HYS, hz, TIL, 1.0, "SiO₂ interfacial layer"),
                                           ("hk", "highk", HY1, hz1, THK, 2.1, "HfO₂ high-κ"),
                                           ("tin", WFM[pol], HY2, hz2, TTIN, 3.3, WFL[pol] + f" · {pol}FET (illustrative)")):
            for i, yy in enumerate(ys):
                bs = ring4(yy, hy, h, t, xg)
                for b in bs: b[2] += z0
                A(d, f"{pol}_{nm}{i+1}", f"{lab} · {pol}{i+1}", mat, bs, grp, ["radial", yy, mg, z0], "in" if nm == "tin" else "body")
        for sx, T in ((-1, "source"), (1, "drain")):
            xa, xb = sorted((sx * xsp, sx * xsd))
            nt = ("vdd" if s > 0 else "gnd") if sx < 0 else "out"
            A(d, f"{pol}_epi_{T}", f"{pol}MOS {T} epi", "silicon" if s < 0 else "sige",
              [box(xa, xb, STI, ysd, z0 - hz, z0 + hz)], grp, [sx * 1.6, 0, s * .4], nt)
            A(d, f"{pol}_nisi_{T}", f"{pol}MOS {T} TiSiₓ", "tisi",
              [box(xa, xb, ysd, ynisi, z0 - hz, z0 + hz)], grp, [sx * 1.9, .3, s * .5], nt)
            sp = []
            xa2, xb2 = sorted((sx * xg, sx * xsp))
            for a, b in gaps(STI, ycap, [(y - HYS, y + HYS) for y in ys]):
                sp.append(box(xa2, xb2, a, b, z0 - hz, z0 + hz))
            A(d, f"{pol}_spacer_{T}", f"Si₃N₄ spacer · {pol} {T}", "si3n4", sp, "Spacers", [sx * 1.3, 0, s * .4], "body")
    mo = []
    zb = [(-zg, -zc - hz3), (-zc + hz3, zc - hz3), (zc + hz3, zg)]
    for a, b in zb: mo.append(box(-xg, xg, STI, ymo, a, b))
    for s in (1, -1):
        for a, b in gaps(STI, ymo, [(y - HY3, y + HY3) for y in ys]):
            mo.append(box(-xg, xg, a, b, s * zc - hz3, s * zc + hz3))
    A(d, "mo", "Mo gate fill (shared gate)", "mo", mo, "Gate electrode", [0, 1.0, 0], "in")
    A(d, "gatecap", "TiN gate cap", "tin", [box(-xg, xg, ymo, ycap, -zg, zg)], "Gate electrode", [0, 1.4, 0], "in")
    for sx in (-1, 1):
        xa, xb = sorted((sx * xg, sx * xsp))
        A(d, f"spacer_out_{sx}", "Si₃N₄ spacer · outer", "si3n4",
          [box(xa, xb, STI, ycap, -zg, -zc - hz), box(xa, xb, STI, ycap, -zc + hz, zc - hz), box(xa, xb, STI, ycap, zc + hz, zg)],
          "Spacers", [sx * 1.3, 0, 0], "body")

    C = dict(xg=xg, xsp=xsp, xsd=xsd, zrail=zr, xcell=xc, ym0=ym0, ym0t=ym0t, ym1=ym1, ym1t=ym1t,
             ygate=ycap, zout=(-zc - hz, zc + hz), zin=(-9, 9), gndy=ym1, gndz=-zr,
             m0=[("s_p", "vdd", zc - hz, zr + 6), ("s_n", "gnd", -zr - 6, -zc + hz), ("d", "out", -zc - hz, zc + hz)],
             m0name={"s_p": "pMOS source → V_DD", "s_n": "nMOS source → GND", "d": "Drain bar → output"},
             vias=[("vdd", "vdd", -xsd + 4, -xsp - 6, zr - 5, zr + 5, ym0t, ym1),
                   ("gnd", "gnd", -xsd + 4, -xsp - 6, -zr - 5, -zr + 5, ym0t, ym1),
                   ("outp", "out", xsp + 6, xsd - 6, zc - 6, zc + 6, ym0t, ym1),
                   ("outn", "out", xsp + 6, xsd - 6, -zc - 6, -zc + 6, ym0t, ym1)],
             vianame={"vdd": "V_DD via", "gnd": "GND via", "outp": "Output via · pMOS", "outn": "Output via · nMOS"})
    deck(d, C)
    Weff = 3 * (2 * W + 2 * TCH)
    return finish(d, C, "ns", zcut=zc, note=NOTE_NS, extra_dims=[
        ["Devices", "pMOS and nMOS, one gate", "2 × 3 sheets"],
        ["W_eff", "Per device", f"{Weff:g} nm"],
        ["Cell z", "Rail-to-rail span (z)", f"{2*(zr+6):g} nm"],
        ["Nets", "V_DD · GND · IN · OUT", "4"],
        ["W_p/W_n", "Geometric width ratio", "1.00"]])

# ============================================================== FINFET INV ==
def inv_fin():
    d = Dev("inv_fin", "FinFET inverter", "tri-gate · 2 fins per device",
            "An illustrative CMOS inverter with two fins per transistor. Fin count provides discrete geometric sizing; equal counts do not imply equal pull-up and pull-down strength.")
    WF, HF, FP, STI = 6.0, 45.0, 27.0, 12.0
    LG, xg = 18.0, 9.0; xsp, xsd = xg + LSP, xg + LSP + LSD
    wh = WF / 2; w1, w2, w3 = wh + TIL, wh + TIL + THK, wh + TIL + THK + TTIN
    ytop = STI + HF; y1, y2, y3 = ytop + TIL, ytop + TIL + THK, ytop + TIL + THK + TTIN
    hzE = FP / 2 + w3
    ymo = y3 + 12; ycap = ymo + 6; yepi = ytop + 7; ynisi = yepi + 5
    zc = hzE + 12.0; zg = zc + hzE + 5; zr = zg + 10; xc = xsd + 4
    ym0, ym0t, ym1, ym1t = ynisi, ynisi + 15, ynisi + 21, ynisi + 31
    A(d, "substrate", "Si substrate", "silicon", [box(-xc + 3, xc - 3, -22, 0, -zr - 2, zr + 2)], "Substrate & isolation", [0, -1.2, 0])
    fins = [s * zc + o for s in (1, -1) for o in (-FP / 2, FP / 2)]
    sti = []; eg = [-zr - 2] + [v for z in sorted(fins) for v in (z - wh, z + wh)] + [zr + 2]
    for i in range(0, len(eg), 2):
        if eg[i + 1] > eg[i]: sti.append(box(-xsd, xsd, 0, STI, eg[i], eg[i + 1]))
    A(d, "sti", "STI (fin reveal)", "sio2", sti, "Substrate & isolation", [0, -.8, 0])
    for s, pol, grp in ((1, "p", "pMOS (pull-up)"), (-1, "n", "nMOS (pull-down)")):
        z0 = s * zc; net = "chan_p" if s > 0 else "chan_n"
        for i, z in enumerate((z0 - FP / 2, z0 + FP / 2)):
            A(d, f"{pol}_f{i+1}", f"{pol}MOS fin {i+1}", "silicon",
              [box(-xsd, xsd, 0, ytop, z - wh, z + wh)], grp, [0, 0, 0], net)
            for nm, mat, ww, yy, t, mg, lab in (("il", "sio2", wh, ytop, TIL, 1.0, "SiO₂ interfacial layer"),
                                                ("hk", "highk", w1, y1, THK, 2.1, "HfO₂ high-κ"),
                                                ("tin", WFM[pol], w2, y2, TTIN, 3.3, WFL[pol] + f" · {pol}FET (illustrative)")):
                A(d, f"{pol}_{nm}{i+1}", f"{lab} · {pol} fin {i+1}", mat,
                  finwrap(z, ww, STI, yy, t, xg), grp, ["radial", (STI + ytop) / 2, mg, z], "in" if nm == "tin" else "body")
        for sx, T in ((-1, "source"), (1, "drain")):
            xa, xb = sorted((sx * xsp, sx * xsd)); nt = ("vdd" if s > 0 else "gnd") if sx < 0 else "out"
            ep = []; ns = []
            for z in (z0 - FP / 2, z0 + FP / 2):
                ep += [box(xa, xb, STI, ytop, z - 10, z - wh), box(xa, xb, STI, ytop, z + wh, z + 10),
                       box(xa, xb, ytop, yepi, z - 10, z + 10)]
                ns.append(box(xa, xb, yepi, ynisi, z - 10, z + 10))
            A(d, f"{pol}_epi_{T}", f"{pol}MOS {T} raised epi", "silicon" if s < 0 else "sige", ep, grp, [sx * 1.6, .2, s * .4], nt)
            A(d, f"{pol}_nisi_{T}", f"{pol}MOS {T} TiSiₓ", "tisi", ns, grp, [sx * 1.9, .5, s * .5], nt)
    mo = [box(-xg, xg, STI, ymo, -zg, -zc - hzE), box(-xg, xg, STI, ymo, -zc + hzE, zc - hzE), box(-xg, xg, STI, ymo, zc + hzE, zg)]
    for s in (1, -1):
        c = s * zc
        mo.append(box(-xg, xg, STI, ymo, c - FP / 2 + w3, c + FP / 2 - w3))
        for z in (c - FP / 2, c + FP / 2): mo.append(box(-xg, xg, y3, ymo, z - w3, z + w3))
    A(d, "mo", "Mo gate fill (shared gate)", "mo", mo, "Gate electrode", [0, 1.0, 0], "in")
    A(d, "gatecap", "TiN gate cap", "tin", [box(-xg, xg, ymo, ycap, -zg, zg)], "Gate electrode", [0, 1.4, 0], "in")
    for sx in (-1, 1):
        xa, xb = sorted((sx * xg, sx * xsp)); sp = [box(xa, xb, ytop, ycap, -zg, zg)]
        eg2 = [-zg] + [v for z in sorted(fins) for v in (z - wh, z + wh)] + [zg]
        for i in range(0, len(eg2), 2):
            if eg2[i + 1] > eg2[i]: sp.append(box(xa, xb, STI, ytop, eg2[i], eg2[i + 1]))
        A(d, f"spacer_{sx}", "Si₃N₄ spacer", "si3n4", sp, "Spacers", [sx * 1.3, 0, 0], "body")
    C = dict(xg=xg, xsp=xsp, xsd=xsd, zrail=zr, xcell=xc, ym0=ym0, ym0t=ym0t, ym1=ym1, ym1t=ym1t,
             ygate=ycap, zout=(-zc - hzE, zc + hzE), zin=(-10, 10), gndy=ym1, gndz=-zr,
             m0=[("s_p", "vdd", zc - hzE, zr + 6), ("s_n", "gnd", -zr - 6, -zc + hzE), ("d", "out", -zc - hzE, zc + hzE)],
             m0name={"s_p": "pMOS source → V_DD", "s_n": "nMOS source → GND", "d": "Drain bar → output"},
             vias=[("vdd", "vdd", -xsd + 4, -xsp - 6, zr - 5, zr + 5, ym0t, ym1),
                   ("gnd", "gnd", -xsd + 4, -xsp - 6, -zr - 5, -zr + 5, ym0t, ym1),
                   ("outp", "out", xsp + 6, xsd - 6, zc - 7, zc + 7, ym0t, ym1),
                   ("outn", "out", xsp + 6, xsd - 6, -zc - 7, -zc + 7, ym0t, ym1)],
             vianame={"vdd": "V_DD via", "gnd": "GND via", "outp": "Output via · pMOS", "outn": "Output via · nMOS"})
    deck(d, C)
    # Along the channel through a fin (the inner pMOS fin), not between the two fins.
    return finish(d, C, "fin", zcut=zc - FP / 2, note=NOTE_FIN, extra_dims=[
        ["Devices", "pMOS and nMOS, one gate", "2 × 2 fins"],
        ["W_eff", "Per device, 2H+W per fin", f"{2*(2*HF+WF):g} nm"],
        ["Cell z", "Rail-to-rail span (z)", f"{2*(zr+6):g} nm"],
        ["W_p/W_n", "Geometric width ratio", "1.00 (2 fins each)"],
        ["—", "Drive granularity", f"{FP:g} nm of cell per extra fin"]])

# =========================================================== FORKSHEET INV ==
def inv_fs():
    d = Dev("inv_fs", "Forksheet inverter", "n and p astride the wall",
            "An illustrative inner-wall forksheet inverter. The n/p stacks abut a dielectric wall; the two gate regions join above it to form a common input.")
    W, PITCH, STI, WALL = 22.0, 21.0, 10.0, 8.0
    LG, xg = 15.0, 7.5; xsp, xsd = xg + LSP, xg + LSP + LSD
    zi = WALL / 2; zo = zi + W; z1, z2, z3 = zo + TIL, zo + TIL + THK, zo + TIL + THK + TTIN
    ys = [STI + HY3 + 6 + i * PITCH for i in range(3)]
    ymo = ys[-1] + HY3 + 9; ycap = ymo + 6; ysd = ys[-1] + HYS + 3; ynisi = ysd + 5
    zg = z3 + 5; zr = zg + 10; xc = xsd + 4
    ym0, ym0t, ym1, ym1t = ynisi, ynisi + 15, ynisi + 21, ynisi + 31
    A(d, "substrate", "Si substrate", "silicon", [box(-xc + 3, xc - 3, -22, 0, -zr - 2, zr + 2)], "Substrate & isolation", [0, -1.2, 0])
    A(d, "sti", "STI / bottom isolation", "sio2", [box(-xsd, xsd, 0, STI, -zr - 2, zr + 2)], "Substrate & isolation", [0, -.8, 0])
    A(d, "wall", "SiN dielectric wall", "wall",
      [box(-xsp, xsp, STI, ymo, -zi, zi), box(xsp, xsd, STI, ynisi, -zi, zi), box(-xsd, -xsp, STI, ynisi, -zi, zi)],
      "Dielectric wall", [0, 1.6, 0], "body")
    for s, pol, grp in ((1, "p", "pMOS (pull-up)"), (-1, "n", "nMOS (pull-down)")):
        net = "chan_p" if s > 0 else "chan_n"
        for i, yy in enumerate(ys):
            zz = sorted((s * zi, s * zo))
            A(d, f"{pol}_s{i+1}", f"{pol}MOS sheet {i+1}", "silicon", [box(-xsp, xsp, yy - HYS, yy + HYS, zz[0], zz[1])], grp, [0, 0, 0], net)
        for nm, mat, hy, zz, t, mg, lab in (("il", "sio2", HYS, zo, TIL, 1.0, "SiO₂ interfacial layer"),
                                            ("hk", "highk", HY1, z1, THK, 2.1, "HfO₂ high-κ"),
                                            ("tin", WFM[pol], HY2, z2, TTIN, 3.3, WFL[pol] + f" · {pol}FET (illustrative)")):
            for i, yy in enumerate(ys):
                A(d, f"{pol}_{nm}{i+1}", f"{lab} · {pol}{i+1}", mat, fork3(yy, hy, zi, zz, t, xg, s), grp, ["radial", yy, mg], "in" if nm == "tin" else "body")
        mo = [box(-xg, xg, STI, ymo, *sorted((s * z3, s * zg)))]
        for a, b in gaps(STI, ymo, [(y - HY3, y + HY3) for y in ys]):
            mo.append(box(-xg, xg, a, b, *sorted((s * zi, s * z3))))
        A(d, f"mo_{pol}", f"Mo gate fill · {pol} side", "mo", mo, "Gate electrode", [0, 1.0, s * .9], "in")
        for sx, T in ((-1, "source"), (1, "drain")):
            xa, xb = sorted((sx * xsp, sx * xsd)); zz = sorted((s * zi, s * zo))
            nt = ("vdd" if s > 0 else "gnd") if sx < 0 else "out"
            A(d, f"{pol}_epi_{T}", f"{pol}MOS {T} epi", "sige" if s > 0 else "silicon", [box(xa, xb, STI, ysd, zz[0], zz[1])], grp, [sx * 1.6, 0, s * .5], nt)
            A(d, f"{pol}_nisi_{T}", f"{pol}MOS {T} TiSiₓ", "tisi", [box(xa, xb, ysd, ynisi, zz[0], zz[1])], grp, [sx * 1.9, .3, s * .6], nt)
            xa2, xb2 = sorted((sx * xg, sx * xsp)); sp = [box(xa2, xb2, STI, ycap, *sorted((s * zo, s * zg)))]
            for a, b in gaps(STI, ycap, [(y - HYS, y + HYS) for y in ys]):
                sp.append(box(xa2, xb2, a, b, *sorted((s * zi, s * zo))))
            A(d, f"{pol}_spacer_{T}", f"Si₃N₄ spacer · {pol} {T}", "si3n4", sp, "Spacers", [sx * 1.3, 0, s * .5], "body")
    A(d, "gatecap", "TiN gate cap (bridges the wall)", "tin", [box(-xg, xg, ymo, ycap, -zg, zg)], "Gate electrode", [0, 1.4, 0], "in")
    C = dict(xg=xg, xsp=xsp, xsd=xsd, zrail=zr, xcell=xc, ym0=ym0, ym0t=ym0t, ym1=ym1, ym1t=ym1t,
             ygate=ycap, zout=(-zo, zo), zin=(-6, 6), gndy=ym1, gndz=-zr,
             m0=[("s_p", "vdd", zi, zr + 6), ("s_n", "gnd", -zr - 6, -zi), ("d", "out", -zo, zo)],
             m0name={"s_p": "pMOS source → V_DD", "s_n": "nMOS source → GND", "d": "Drain bar → output"},
             vias=[("vdd", "vdd", -xsd + 4, -xsp - 6, zr - 5, zr + 5, ym0t, ym1),
                   ("gnd", "gnd", -xsd + 4, -xsp - 6, -zr - 5, -zr + 5, ym0t, ym1),
                   ("outp", "out", xsp + 6, xsd - 6, zi + 3, zo - 3, ym0t, ym1),
                   ("outn", "out", xsp + 6, xsd - 6, -zo + 3, -zi - 3, ym0t, ym1)],
             vianame={"vdd": "V_DD via", "gnd": "GND via", "outp": "Output via · pMOS", "outn": "Output via · nMOS"})
    deck(d, C)
    return finish(d, C, "fs", zcut=(zi+zo)/2, note=NOTE_FS, extra_dims=[
        ["Devices", "pMOS and nMOS, one gate", "2 × 3 sheets"],
        ["W_eff", "Per device, 2W+t per sheet", f"{3*(2*W+TCH):g} nm"],
        ["t_wall", "n-to-p separation", f"{WALL:g} nm"],
        ["Cell z", "Rail-to-rail span (z)", f"{2*(zr+6):g} nm"],
        ["W_p/W_n", "Geometric width ratio", "1.00"]])

# ================================================================ CFET INV ==
def inv_cfet():
    d = Dev("inv_cfet", "CFET inverter", "one stack, one gate",
            "An illustrative stacked nFET/pFET inverter. This example uses nFET below pFET, backside GND, a common gate input and a riser connecting the drains.")
    W, PITCH, MDI, STI = 20.0, 20.0, 12.0, 8.0
    xg, xsp, xsd = 7.5, 14.5, 36.5
    hz = W / 2; hz1, hz2, hz3 = hz + TIL, hz + TIL + THK, hz + TIL + THK + TTIN
    hzmo = hz3 + 5
    yb = [STI + HY3 + 6, STI + HY3 + 6 + PITCH]
    m0y, m1y = yb[-1] + HY3, yb[-1] + HY3 + MDI          # 51 -> 63
    yt = [m1y + HY3, m1y + HY3 + PITCH]                  # 71.5  91.5
    ymo = yt[-1] + HY3 + 6; ycap = ymo + 6               # 106 -> 112
    ytsd = yt[-1] + HYS + 3; ynisi = ytsd + 5            # 97 -> 102
    ym0, ym0t, ym1, ym1t = ynisi, ynisi + 15, ynisi + 21, ynisi + 31
    zr = hzmo + 10; xc = xsd + 4; zmdi = hzmo + 6        # 31 / 40.5 / 27
    # Output riser: its -z face on the drains' +z face (z = hz), so it contacts both drains.
    rz0, rz1, rx0, rx1 = hz, 20.0, 18.0, 30.0
    bs0, bs1 = -22.0, -12.0

    A(d, "rail_gnd_bs", "GND rail (backside metal)", "tungsten",
      [box(-xc + 3, xc - 3, bs0, bs1, -zr - 6, zr + 6)], "Backside power", [0, -2.0, 0], "gnd")
    ild = [box(-xsp, xsp, bs1, 0, -zr - 2, zr + 2), box(xsp, xsd, bs1, 0, -zr - 2, zr + 2)]
    xa, xb = -xsd, -xsp; xcv = (xa + xb) / 2
    ild += [box(xa, xcv - 7, bs1, 0, -zr - 2, zr + 2), box(xcv + 7, xb, bs1, 0, -zr - 2, zr + 2),
            box(xcv - 7, xcv + 7, bs1, 0, -zr - 2, -hz), box(xcv - 7, xcv + 7, bs1, 0, hz, zr + 2)]
    A(d, "bsild", "Backside ILD (SiO₂)", "sio2", ild, "Backside power", [0, -1.5, 0])
    A(d, "via_gnd", "Buried power via → nMOS source", "tungsten",
      [box(xcv - 7, xcv + 7, bs1, 0, -hz, hz)], "Backside power", [-1.0, -1.2, 0], "gnd")
    A(d, "sti", "STI / bottom isolation", "sio2", [box(-xsp, xsp, 0, STI, -zr - 2, zr + 2)], "Substrate & isolation", [0, -.8, 0])

    for tier, ylist, pol, grp in (("n", yb, "n", "nMOS (bottom tier)"), ("p", yt, "p", "pMOS (top tier)")):
        net = "chan_n" if pol == "n" else "chan_p"
        for i, yy in enumerate(ylist):
            A(d, f"{pol}_s{i+1}", f"{pol}MOS sheet {i+1}", "silicon",
              [box(-xsp, xsp, yy - HYS, yy + HYS, -hz, hz)], grp, [0, 0, 0], net)
        for nm, mat, hy, h, t, mg, lab in (("il", "sio2", HYS, hz, TIL, 1.0, "SiO₂ interfacial layer"),
                                           ("hk", "highk", HY1, hz1, THK, 2.1, "HfO₂ high-κ"),
                                           ("tin", WFM[pol], HY2, hz2, TTIN, 3.3, WFL[pol] + f" · {pol}FET (illustrative)")):
            for i, yy in enumerate(ylist):
                A(d, f"{pol}_{nm}{i+1}", f"{lab} · {pol}{i+1}", mat, ring4(yy, hy, h, t, xg), grp, ["radial", yy, mg], "in" if nm == "tin" else "body")
    # tier isolation, punched for the output riser
    mdi = [box(-xsd, -xg, m0y, m1y, -zmdi, zmdi), box(xg, rx0, m0y, m1y, -zmdi, zmdi),
           box(rx1, xsd, m0y, m1y, -zmdi, zmdi), box(rx0, rx1, m0y, m1y, -zmdi, rz0),
           box(rx0, rx1, m0y, m1y, rz1, zmdi)]
    A(d, "mdi", "Middle dielectric isolation", "mdi", mdi, "Tier isolation", [0, 1.1, 0])
    mo = [box(-xg, xg, STI, ymo, hz3, hzmo), box(-xg, xg, STI, ymo, -hzmo, -hz3)]
    for a, b in gaps(STI, ymo, [(y - HY3, y + HY3) for y in yb + yt]):
        mo.append(box(-xg, xg, a, b, -hz3, hz3))
    A(d, "mo", "Mo gate fill (through both tiers)", "mo", mo, "Gate electrode", [0, 1.0, 0], "in")
    A(d, "gatecap", "TiN gate cap", "tin", [box(-xg, xg, ymo, ycap, -hzmo, hzmo)], "Gate electrode", [0, 1.4, 0], "in")
    for sx, T in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((sx * xg, sx * xsp)); sp = []
        for a, b in gaps(STI, ycap, [(m0y, m1y)]):
            sp += [box(xa, xb, a, b, hz, hzmo), box(xa, xb, a, b, -hzmo, -hz)]
        for a, b in gaps(STI, ycap, [(y - HYS, y + HYS) for y in yb + yt] + [(m0y, m1y)]):
            sp.append(box(xa, xb, a, b, -hz, hz))
        A(d, f"spacer_{T}", f"Si₃N₄ spacer · {T}", "si3n4", sp, "Spacers", [sx * 1.3, 0, 0], "body")
    for sx, T in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((sx * xsp, sx * xsd))
        ntn = "gnd" if sx < 0 else "out"; ntp = "vdd" if sx < 0 else "out"
        A(d, f"n_epi_{T}", f"nMOS {T} epi (Si:P)", "silicon", [box(xa, xb, 0, m0y, -hz, hz)], "nMOS (bottom tier)", [sx * 1.6, -.4, 0], ntn)
        A(d, f"p_epi_{T}", f"pMOS {T} epi (SiGe:B)", "sige", [box(xa, xb, m1y, ytsd, -hz, hz)], "pMOS (top tier)", [sx * 1.6, .4, 0], ntp)
        A(d, f"nisi_{T}", f"pMOS {T} TiSiₓ", "tisi", [box(xa, xb, ytsd, ynisi, -hz, hz)], "pMOS (top tier)", [sx * 1.9, .7, 0], ntp)
    A(d, "riser", "Output riser · bottom drain to top", "tungsten",
      [box(rx0, rx1, 0, ym0, rz0, rz1)], "Local interconnect", [1.4, .6, .8], "out")

    C = dict(xg=xg, xsp=xsp, xsd=xsd, zrail=zr, xcell=xc, ym0=ym0, ym0t=ym0t, ym1=ym1, ym1t=ym1t,
             ygate=ycap, zout=(-hz, hz), zin=(-18, -6), gndy=(bs0 + bs1) / 2, gndz=0, gnd_top=False,
             m0=[("s_p", "vdd", -hz, zr + 6), ("d", "out", -hz, rz1)],
             m0name={"s_p": "pMOS source → V_DD", "d": "Drain bar → output"},
             vias=[("vdd", "vdd", -xsd + 4, -xsp - 6, zr - 5, zr + 5, ym0t, ym1),
                   ("out", "out", xsp + 6, xsd - 6, -8, 8, ym0t, ym1)],
             vianame={"vdd": "V_DD via", "out": "Output via"})
    deck(d, C)
    return finish(d, C, "cfet", zcut=0.0, note=NOTE_CFET, extra_dims=[
        ["Devices", "pMOS over nMOS, one gate", "2 × 2 sheets"],
        ["W_eff", "Per device", f"{2*(2*W+2*TCH):g} nm"],
        ["t_MDI", "Tier isolation", f"{MDI:g} nm"],
        ["Cell z", "Rail-to-rail span (z)", f"{2*(zr+6):g} nm"],
        ["GND", "Reached from", "backside power rail"]])

# ======================================================== INVERTER COMPARE ==
def inv_cmp():
    d = Dev("inv_cmp", "Inverter compare", "four cells, one scale",
            "Four illustrative CMOS inverter cells at a common geometric scale. The z spans include the drawn rails and routing. They are not iso-performance or foundry-library comparisons.")
    builders = [(inv_fin, "FinFET"), (inv_ns, "Nanosheet"), (inv_fs, "Forksheet"), (inv_cfet, "CFET")]
    cells, cur, GAP = [], -300.0, 45.0
    for build, nm in builders:
        src = build()
        w = src.bounds["z"][1] - src.bounds["z"][0]
        zoff = cur - src.bounds["z"][0]
        for p in src.parts:
            boxes = [[b[0], b[1], b[2] + zoff, b[3], b[4], b[5]] for b in p["boxes"]]
            e = p["explode"]
            if isinstance(e, list) and len(e) and e[0] == "radial":
                e = ["radial", e[1], e[2], (e[3] if len(e) > 3 else 0.0) + zoff]
            d.add(f"{src.key}_{p['id']}", p["name"], p["material"], boxes, f"{nm} cell", e)
            d.parts[-1]["net"] = p["net"]
        cells.append((nm, cur + w / 2.0, w, src.bounds["y"][1]))
        cur += w + GAP

    w0 = cells[0][2]
    for nm, zc, w, ytop in cells:
        d.cal(f"w_{nm}", nm, f"{w:g} nm", f"cell height (rail-to-rail span) · {w / w0 * 100:.0f}% of FinFET",
              [0, -26, zc - w / 2], [0, -26, zc + w / 2], [0, -52, zc], ["front", "iso"])
        d.cal(f"h_{nm}", nm, "", "rail to rail",
              [0, ytop, zc], [0, ytop + 1, zc], [0, ytop + 30, zc], ["front", "iso"])
    d.dims = [[nm, "Rail-to-rail span (z)", f"{w:g} nm  ({w / w0 * 100:.0f}%)"] for nm, zc, w, yt in cells]
    d.dims.append(["—", "What is being measured", "one inverter, both rails"])
    d.dims.append(["—", "Sheets or fins per device", "2 fins / 3 / 3 / 2 per tier"])
    d.logic = True
    d.note = ("<b>Rail-to-rail span.</b> These values describe the model's lateral z dimension, commonly called cell height in standard-cell layout practice. Routing and contacts change the comparison with device-only spans. A smaller drawn span alone does not demonstrate higher achievable density or speed. For scale, imec's roadmap puts standard-cell height at roughly 115 nm for A14 nanosheets, 98 nm for A10 forksheets and under 80 nm for A7 CFETs; the spans drawn here are the model's own.")
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    zs = B["z"][1] - B["z"][0]
    d.views = {
      "front": dict(n="Head on", s="cell heights, side by side", az=-1.5708, el=0.03, r=zs * 1.52, tgt=ctr, clip=None),
      "iso": dict(n="All four", s="same scale", az=-1.40, el=0.28, r=zs * 1.55, tgt=ctr, clip=None),
      "top": dict(n="Top view", s="straight down", az=-1.5708, el=1.45, r=zs * 1.52, tgt=ctr, clip=None)}
    return d

# =================================================================== MAIN ===
if __name__ == "__main__":
    import findlap
    G = json.load(open(DATA))
    G["devices"] = [x for x in G["devices"] if not x["key"].startswith("inv_")]
    for f in (inv_fin, inv_ns, inv_fs, inv_cfet, inv_cmp):
        d = f(); mx, n = check(d)
        laps = findlap.overlaps(d)
        print(f"{d.key:10s} parts={len(d.parts):3d} boxes={n:4d} max/voxel={mx}" + ("  LAP:" + str(laps) if laps else ""))
        G["devices"].append(dict(key=d.key, name=d.name, tag=d.tag, blurb=d.blurb, parts=d.parts,
            callouts=d.callouts, dims=d.dims, views=d.views, note=d.note, bounds=d.bounds, logic=True,
            groups=list(dict.fromkeys(p["group"] for p in d.parts))))
    json.dump(G, open(DATA, "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize(DATA) // 1024, "KB", len(G["devices"]), "scenes")
