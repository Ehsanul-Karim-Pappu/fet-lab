"""
Schematic-layout inverters, in the style of the reference GAAFET model:
flat pastel layers, layout nomenclature (P Well / N Well / SiO2 / Nanowire / MD / Po /
VD / VG / Metal 0), surface labels sitting on the geometry, light background, flat shading.

In-plane the figure is to scale — gate length, contact length, channel width, cell
width and track pitch all come from the device cross-sections. Only the vertical
direction is exaggerated, so the thin films stay visible.
"""
import json, math, os
from paths import DATA
from build_devices import Dev, box, gaps, check, LSP, LSD

def A(d, pid, name, mat, boxes, group, explode, net="body"):
    d.add(pid, name, mat, boxes, group, explode)
    d.parts[-1]["net"] = net

LAYER_VIEWS = ["hero", "front"]
def L(d, text, at, size="m", tone="dark", v=None, lead=True, sd=0, pid=None):
    """A flat label.

    With lead=True the text is parked out in the margin, clear of the model, and a hairline
    runs back to a dot sitting on the layer it names — so there is no doubt which slab the
    name belongs to. `pid` is the part the label is for: the viewer samples that part's
    faces every frame and anchors the dot on a point that is actually visible from where
    the camera is, falling back to `at` if the part is hidden. `sd` forces the column
    (-1 left, +1 right). With lead=False the text is drawn at `at` itself, for titles.
    """
    d.callouts.append(dict(id=f"L{len(d.callouts)}", label=text, value="", desc="",
                           a=at, b=at, lab=at, v=v, flat=True, lead=lead, sd=sd, pid=pid,
                           size=size, tone=tone))

# ------------------------------------------------------------------ geometry
# Everything in the plane of the wafer is taken from the device cross-sections, so a
# nanometre here is the same nanometre there: the gate is drawn at its physical length,
# the contact at the contacted length, the channel at its real width, and the cell at the
# rail-to-rail width the inverter scenes derive. Only the vertical direction is
# exaggerated — drawn to scale, the films would be a pixel or two on a phone.
MW = 16.0                                        # Metal 0 track width
OVH = 3.0                                        # MD overhang past the end of a channel

ARCH = {                        # gate length · rail-to-rail cell · Metal 0 tracks, -z to +z
    "fin":  dict(LG=18.0, cell=156.0, bars=("gnd", "in", "out", "vdd")),
    "ns":   dict(LG=15.0, cell=136.0, bars=("gnd", "in", "out", "vdd")),
    "fs":   dict(LG=15.0, cell=106.0, bars=("gnd", "in", "out", "vdd")),
    "cfet": dict(LG=15.0, cell= 74.0, bars=("in",  "out", "vdd")),   # GND went to the back
}

def plan(arch):
    """Derive the whole in-plane layout from the gate length and the cell width."""
    a = ARCH[arch]
    xpo  = a["LG"] / 2.0                         # gate, at its physical length
    xmd0 = xpo + LSP                             # spacer between gate and contact
    xmd1 = xmd0 + LSD                            # MD, at the contacted source/drain length
    half = a["cell"] / 2.0
    step = a["cell"] / (len(a["bars"]) - 1)      # one uniform track pitch, rails on the edge
    return dict(arch=arch, LG=a["LG"], cell=a["cell"], half=half, step=step, mw=MW,
                xpo=xpo, xmd0=xmd0, xmd1=xmd1, xw=xmd1 + 10.0,
                zbar={n: -half + i * step for i, n in enumerate(a["bars"])})

YPW0, YPW1 = -34.0, -14.0                        # P Well plinth
YWL0, YWL1 = -14.0, -4.0                         # well layer
YOX0, YOX1 = -4.0, 6.0                           # field oxide
YMD1, YPO1 = 38.0, 44.0                          # tops of MD and Po
YV1, YM0, YM1 = 50.0, 50.0, 58.0                 # via top / Metal 0

def deck(d, P, holes, arch_note, nband, pband, wall=None):
    """Everything that is not the channel: wells, oxide, contacts, gate, vias, Metal 0.

    `nband` and `pband` are the z extents of the two device rows. The source contacts run
    from their row out to the rail they feed, which is what lets a plain vertical via reach
    Metal 0 — the same reason real source MDs are drawn out to the cell edge.
    """
    XW, XMD0, XMD1, XPO = P["xw"], P["xmd0"], P["xmd1"], P["xpo"]
    half, ZBAR, hw = P["half"], P["zbar"], P["mw"] / 2.0
    # A rail straddles the cell boundary and is shared with the row above or below, so the
    # wells, the oxide and the gate all run out under its far edge rather than stopping at
    # the boundary line.
    ZCELL = half + hw
    ZPLINTH = ZCELL + 2.0
    gate_z = ZCELL

    # --- wells and oxide ---------------------------------------------------
    A(d, "pwell", "P Well", "pwell", [box(-XW - 8, XW + 8, YPW0, YPW1, -ZPLINTH, ZPLINTH)],
      "Wells & oxide", [0, -1.5, 0])
    A(d, "pwell_u", "P Well (nMOS side)", "pwell", [box(-XW, XW, YWL0, YWL1, -ZCELL, 0)],
      "Wells & oxide", [0, -1.2, -.5])
    A(d, "nwell", "N Well", "nwell", [box(-XW, XW, YWL0, YWL1, 0, ZCELL)],
      "Wells & oxide", [0, -1.2, .5])
    gx = 4.0
    ox = [box(-XW, -gx, YOX0, YOX1, -ZCELL, ZCELL), box(gx, XW, YOX0, YOX1, -ZCELL, ZCELL),
          box(-gx, gx, YOX0, YOX1, -ZCELL, -gate_z), box(-gx, gx, YOX0, YOX1, gate_z, ZCELL)]
    ox = [b for b in ox if b[5] > 0.01]
    A(d, "fox", "SiO₂ field oxide", "fox", ox, "Wells & oxide", [0, -.8, 0])

    # --- source / drain contacts ------------------------------------------
    # Two rules, both from how a real cell is drawn. An end that meets a rail runs out to
    # the far edge of that rail, so the contact sits under the whole of it. An end that
    # stops beside a channel overhangs it by OVH — landing a contact flush with the end of
    # the channel it is contacting leaves no margin for overlay, and reads as a short to
    # whatever is on the other side.
    # An MD column runs the full height of the cell, rail edge to rail edge, and is only
    # broken where it has to serve two different nets. The source column is cut, because
    # one half goes to GND and the other to V_DD; each half then overhangs its own channel
    # by OVH, since landing a contact flush with the end of the channel it contacts leaves
    # nothing for overlay. The drain column is one net, so it is not cut at all.
    wz0, wz1 = wall if wall else (0.0, 0.0)
    inner_n = min(nband[1] + OVH, wz0) if wall else nband[1] + OVH
    inner_p = max(pband[0] - OVH, wz1) if wall else pband[0] - OVH
    A(d, "md_gnd", "MD · nMOS source", "md",
      [box(-XMD1, -XMD0, YOX1, YMD1, -ZCELL, inner_n)], "Contacts", [-1.3, .3, -.6], "gnd")
    A(d, "md_vdd", "MD · pMOS source", "md",
      [box(-XMD1, -XMD0, YOX1, YMD1, inner_p, ZCELL)], "Contacts", [-1.3, .3, .6], "vdd")
    if wall:
        # ...except here, where the wall is taller than the contact and splits it anyway.
        A(d, "md_out", "MD · shared drain", "md",
          [box(XMD0, XMD1, YOX1, YMD1, -ZCELL, wz0), box(XMD0, XMD1, YOX1, YMD1, wz1, ZCELL)],
          "Contacts", [1.3, .3, 0], "out")
    else:
        A(d, "md_out", "MD · shared drain", "md",
          [box(XMD0, XMD1, YOX1, YMD1, -ZCELL, ZCELL)], "Contacts", [1.3, .3, 0], "out")

    # --- gate --------------------------------------------------------------
    po = []
    edges = [-gate_z]
    for z0, z1, bands in holes: edges += [z0, z1]
    edges.append(gate_z)
    for i in range(0, len(edges), 2):
        if edges[i + 1] > edges[i]:
            po.append(box(-XPO, XPO, YOX1, YPO1, edges[i], edges[i + 1]))
    for z0, z1, bands in holes:
        for y0, y1 in gaps(YOX1, YPO1, bands):
            po.append(box(-XPO, XPO, y0, y1, z0, z1))
    po.append(box(-gx, gx, YOX0, YOX1, -gate_z, gate_z))      # foot, through the oxide
    A(d, "po", "Po · gate electrode", "po", po, "Gate", [0, .9, 0], "in")

    # --- vias: each sits under its own Metal 0 track -----------------------
    vx = (XMD0 + XMD1) / 2.0
    for nm, net, xc, zc in (("gnd", "gnd", -vx, ZBAR["gnd"]),
                            ("vdd", "vdd", -vx, ZBAR["vdd"]),
                            ("out", "out",  vx, ZBAR["out"])):
        A(d, f"vd_{nm}", f"VD · {net.upper()}", "vd",
          [box(xc - 4, xc + 4, YMD1, YV1, zc - 3, zc + 3)], "Vias", [0, 1.1, 0], net)
    if wall:
        # The wall splits the drain contact in two, so the n side needs its own via up.
        zn = (nband[0] + wz0) / 2.0
        A(d, "vd_out2", "VD · OUT (n side)", "vd",
          [box(vx - 4, vx + 4, YMD1, YV1, zn - 3, zn + 3)], "Vias", [0, 1.1, 0], "out")
    A(d, "vg", "VG · gate via", "vg",
      [box(-5, 5, YPO1, YV1, ZBAR["in"] - 2, ZBAR["in"] + 2)], "Vias", [0, 1.2, 0], "in")

    # --- Metal 0, one uniform track pitch, rails on the cell boundary ------
    # The rails run the length of the cell because the next cell abuts them. IN is a signal
    # track, so it stops once it has reached the gate via — which is also what keeps the
    # drain side of the cell free for the forksheet's jog to get across without shorting it.
    for net, label in (("gnd", "GND"), ("in", "IN"), ("out", "OUT"), ("vdd", "V_DD")):
        z = ZBAR[net]
        x1 = XMD0 if net == "in" else XW
        A(d, f"m0_{net}", f"Metal 0 · {label}", "m0", [box(-XW, x1, YM0, YM1, z - hw, z + hw)],
          "Metal 0", [0, 1.6, 0], net)
    if wall:
        # ...and that second via has to reach the OUT track, which runs on the p side of
        # the wall. A short transverse Metal 0 jog over the drain ties the two together —
        # one of the forksheet's real costs, and the reason its OUT net is not a single bar.
        A(d, "m0_out_jog", "Metal 0 · OUT jog", "m0",
          [box(vx - 4, vx + 4, YM0, YM1, zn - 3, ZBAR["out"] - hw)], "Metal 0", [0, 1.6, 0], "out")

    # --- layer names, each anchored on the edge of the layer it names -------
    mid = lambda a, b: (a + b) / 2.0
    zr = half * 0.55
    # right-hand column, read bottom to top
    L(d, "P Well", [XW + 8, mid(YPW0, YPW1), zr], "m", "dark", LAYER_VIEWS, sd=1, pid="pwell")
    L(d, "N Well", [XW, mid(YWL0, YWL1), zr], "m", "dark", LAYER_VIEWS, sd=1, pid="nwell")
    L(d, "SiO₂", [XW, mid(YOX0, YOX1), zr], "m", "dark", LAYER_VIEWS, sd=1, pid="fox")
    L(d, "MD", [XMD1, mid(YOX1, YMD1), mid(*pband)], "m", "dark", LAYER_VIEWS, sd=1, pid="md_out")
    L(d, "VD", [XMD1, mid(YMD1, YV1), ZBAR["out"]], "s", "dark", LAYER_VIEWS, sd=1, pid="vd_out")
    # left-hand column
    L(d, "MD", [-XMD1, mid(YOX1, YMD1), mid(*nband)], "m", "dark", LAYER_VIEWS, sd=-1, pid="md_gnd")
    L(d, "Po", [-XPO, mid(YMD1, YPO1), -zr], "m", "dark", LAYER_VIEWS, pid="po")
    L(d, "VG", [-5, mid(YPO1, YV1), ZBAR["in"]], "s", "dark", LAYER_VIEWS, pid="vg")
    for net, label in (("gnd", "GND"), ("in", "IN"), ("out", "OUT"), ("vdd", "V_DD")):
        L(d, label, [-XW, mid(YM0, YM1), ZBAR[net]], "m", sd=-1, pid=f"m0_{net}")
    d.note = arch_note

def fit_r(B, az, el, aspect=1.5, margin=1.06):
    """Distance at which the whole cell just fits, perspective included.

    A standard cell is long and thin, and now that the layout figures carry their real cell
    width they are deep as well as tall. Scaling one number off the largest extent is not
    good enough: viewed near end-on, the near end of a deep cell is much closer than the
    centre and projects far larger. So solve each bounding-box corner for the distance that
    puts it just inside the frame, and stand back as far as the worst one asks.
    """
    ce = math.cos(el)
    f = [-ce * math.sin(az), -math.sin(el), -ce * math.cos(az)]
    rt = [-f[2], 0.0, f[0]]
    n = math.hypot(rt[0], rt[2]) or 1.0
    rt = [rt[0] / n, 0.0, rt[2] / n]
    up = [rt[1] * f[2] - rt[2] * f[1], rt[2] * f[0] - rt[0] * f[2], rt[0] * f[1] - rt[1] * f[0]]
    c = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    t = math.tan(0.31)
    need = 0.0
    for X in B["x"]:
        for Y in B["y"]:
            for Z in B["z"]:
                dv = [X - c[0], Y - c[1], Z - c[2]]
                dot = lambda a: sum(dv[i] * a[i] for i in range(3))
                along = dot(f)                       # +ve is beyond the target, -ve is nearer
                need = max(need, abs(dot(rt)) / (t * aspect) - along,
                                 abs(dot(up)) / t - along)
    return margin * need

def finish(d, dims):
    d.logic = True
    d.style = "schematic"
    d.dims = dims
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    V = lambda az, el: fit_r(B, az, el)
    d.views = {
      "hero": dict(n="The cell", s="three-quarter, all layers", az=-0.62, el=0.30, r=V(-0.62, 0.30), tgt=ctr, clip=None),
      "front": dict(n="Front on", s="stack from the side", az=0.0, el=0.10, r=V(0.0, 0.10), tgt=ctr, clip=None),
      "end": dict(n="Through the gate", s="n and p in section", az=1.5708, el=0.16, r=V(1.5708, 0.16), tgt=ctr, clip=[0.0, None, None]),
      "top": dict(n="Top view", s="Metal 0 routing", az=0.0, el=1.42, r=V(0.0, 1.42), tgt=ctr, clip=None)}
    return d

# ------------------------------------------------------------------ NANOSHEET
def show_ns():
    d = Dev("show_ns", "Nanosheet inverter · layout", "GAAFET · 2 nanowires per device",
            "The inverter drawn the way a layout figure draws it: wells, field oxide, the "
            "nanowire channels, MD source/drain contacts, the Po gate crossing both devices, "
            "vias, and four Metal 0 bars carrying V_DD, IN, OUT and GND.")
    P = plan("ns")
    XW, XMD0, XMD1 = P["xw"], P["xmd0"], P["xmd1"]
    WSH = 30.0                                   # sheet width, from the device scene
    rc = P["half"] / 2.0                         # one device row each side of centre
    ZN0, ZN1 = -rc - WSH / 2, -rc + WSH / 2
    ZP0, ZP1 =  rc - WSH / 2,  rc + WSH / 2
    wires = [(12.0, 17.0), (23.0, 28.0)]
    for i, (y0, y1) in enumerate(wires):
        for z0, z1, pol, net in ((ZN0, ZN1, "n", "chan_n"), (ZP0, ZP1, "p", "chan_p")):
            grp = "nMOS channel" if pol == "n" else "pMOS channel"
            A(d, f"{pol}_w{i+1}", f"{pol}MOS nanowire {i+1}", "nanowire",
              [box(-XMD0, XMD0, y0, y1, z0, z1)], grp, [0, 0, 0], net)
            A(d, f"{pol}_ws{i+1}", f"{pol}MOS nanowire {i+1} · drain stub", "nanowire",
              [box(XMD1, XW, y0, y1, z0, z1)], grp, [1.5, 0, 0], "body")
            A(d, f"{pol}_wsr{i+1}", f"{pol}MOS nanowire {i+1} · source stub", "nanowire",
              [box(-XW, -XMD1, y0, y1, z0, z1)], grp, [-1.5, 0, 0], "body")
    deck(d, P, [(ZN0, ZN1, wires), (ZP0, ZP1, wires)],
         "<b>Reading the figure.</b> Two nanowire channels per device run left to right through "
         "the Po gate, which crosses both the nMOS over the P Well and the pMOS over the N Well. "
         "One gate, one input. The shared MD on the right ties both drains together and carries "
         "the output up to Metal 0; the two outer MDs run out to the rails they feed.",
         (ZN0, ZN1), (ZP0, ZP1))
    L(d, "Nanowire", [XW, 25.5, ZP1 - 5], "s", "dark", LAYER_VIEWS, sd=1, pid=["p_ws2", "p_wsr2"])
    return finish(d, [
        ["L_G", "Physical gate length, as drawn", f'{P["LG"]:g} nm'],
        ["Cell z", "Rail-to-rail cell width", f'{P["cell"]:g} nm'],
        ["M0 pitch", "Metal 0 track pitch", f'{P["step"]:.1f} nm'],
        ["Nanowires", "Per device", "2"], ["Devices", "pMOS over N Well, nMOS over P Well", "2"],
        ["Gate", "Po, crossing both", "1"], ["Contacts", "MD columns", "3"],
        ["Metal 0", "V_DD · IN · OUT · GND", "4 bars"],
        ["Vias", "VD to MD, VG to gate", "4"]])

# ------------------------------------------------------------------ FORKSHEET
def show_fs():
    d = Dev("show_fs", "Forksheet inverter · layout", "n and p astride a dielectric wall",
            "The same figure with the two devices pushed together until only a dielectric wall "
            "separates them. The Po gate still crosses both, but the wall runs up through it, so "
            "the n-side and p-side gate metal only meet over the top.")
    P = plan("fs")
    XW, XMD0, XMD1 = P["xw"], P["xmd0"], P["xmd1"]
    WSH, TW = 22.0, 8.0                          # sheet width and wall, from the device scene
    wires = [(12.0, 17.0), (23.0, 28.0)]
    zn0, zn1 = -TW / 2 - WSH, -TW / 2
    zp0, zp1 =  TW / 2,        TW / 2 + WSH
    A(d, "wall", "Dielectric wall", "wall",
      [box(-XW, XW, YOX1, YPO1, -TW / 2, TW / 2)], "Dielectric wall", [0, 1.3, 0])
    for i, (y0, y1) in enumerate(wires):
        for z0, z1, pol, net in ((zn0, zn1, "n", "chan_n"), (zp0, zp1, "p", "chan_p")):
            grp = "nMOS channel" if pol == "n" else "pMOS channel"
            A(d, f"{pol}_w{i+1}", f"{pol}MOS sheet {i+1}", "nanowire",
              [box(-XMD0, XMD0, y0, y1, z0, z1)], grp, [0, 0, 0], net)
            A(d, f"{pol}_ws{i+1}", f"{pol}MOS sheet {i+1} · drain stub", "nanowire",
              [box(XMD1, XW, y0, y1, z0, z1)], grp, [1.5, 0, 0], "body")
            A(d, f"{pol}_wsr{i+1}", f"{pol}MOS sheet {i+1} · source stub", "nanowire",
              [box(-XW, -XMD1, y0, y1, z0, z1)], grp, [-1.5, 0, 0], "body")
    deck(d, P, [(zn0, zn1, wires), (-TW / 2, TW / 2, [(YOX1, YPO1)]), (zp0, zp1, wires)],
         "<b>Where the width goes.</b> Between the two devices there is now a wall instead of a "
         "gate-metal gap, so the whole cell narrows — 106 nm rail to rail against the nanosheet's "
         "136. The Po still shows as one body because the two halves join above the wall.",
         (zn0, zn1), (zp0, zp1), wall=(-TW / 2, TW / 2))
    L(d, "Sheet", [XW, 25.5, zp1 - 5], "s", "dark", LAYER_VIEWS, sd=1, pid=["p_ws2", "p_wsr2"])
    L(d, "Wall", [XMD1 - 6, YPO1 - 4, 0], "s", "dark", LAYER_VIEWS, pid="wall")
    return finish(d, [
        ["L_G", "Physical gate length, as drawn", f'{P["LG"]:g} nm'],
        ["Cell z", "Rail-to-rail cell width", f'{P["cell"]:g} nm'],
        ["M0 pitch", "Metal 0 track pitch", f'{P["step"]:.1f} nm'],
        ["Sheets", "Per device", "2"], ["Separation", "Dielectric wall", "no metal gap"],
        ["Gate", "Po, bridged over the wall", "1"], ["Contacts", "MD columns", "3"],
        ["Metal 0", "V_DD · IN · OUT · GND", "4 bars + drain jog"], ["Gate faces", "Per sheet", "3"]])

# --------------------------------------------------------------------- FINFET
def show_fin():
    d = Dev("show_fin", "FinFET inverter · layout", "tri-gate · 2 fins per device",
            "The pre-nanosheet version of the same figure. The channel is a standing fin rather "
            "than a stack of wires, so the Po gate drapes over it on three sides and drive comes "
            "in whole fins.")
    P = plan("fin")
    XW, XMD0, XMD1 = P["xw"], P["xmd0"], P["xmd1"]
    FW, FP = 6.0, 27.0                           # fin width and fin pitch, from the device scene
    FY0, FY1 = 6.0, 34.0                         # fin height stays exaggerated for legibility
    rc = P["half"] / 2.0
    fins, holes = [], []
    for zc, pol in ((-rc, "n"), (rc, "p")):
        grp = "nMOS channel" if pol == "n" else "pMOS channel"
        net = "chan_n" if pol == "n" else "chan_p"
        for i, z in enumerate((zc - FP / 2, zc + FP / 2)):
            z0, z1 = z - FW / 2, z + FW / 2
            A(d, f"{pol}_f{i+1}", f"{pol}MOS fin {i+1}", "nanowire",
              [box(-XMD0, XMD0, FY0, FY1, z0, z1)], grp, [0, 0, 0], net)
            A(d, f"{pol}_fs{i+1}", f"{pol}MOS fin {i+1} · drain stub", "nanowire",
              [box(XMD1, XW, FY0, FY1, z0, z1)], grp, [1.5, 0, 0], "body")
            A(d, f"{pol}_fsr{i+1}", f"{pol}MOS fin {i+1} · source stub", "nanowire",
              [box(-XW, -XMD1, FY0, FY1, z0, z1)], grp, [-1.5, 0, 0], "body")
            holes.append((z0, z1, [(FY0, FY1)]))
    band = FP / 2 + FW / 2
    deck(d, P, sorted(holes),
         "<b>Drive in whole fins.</b> Two fins each gives a balanced inverter. Wanting a stronger "
         "pull-up means a third fin, which widens the cell by a whole 27 nm fin pitch and "
         "overshoots — the granularity the nanosheet removed by making width continuous.",
         (-rc - band, -rc + band), (rc - band, rc + band))
    L(d, "Fin", [XW, FY1, rc + FP / 2], "s", "dark", LAYER_VIEWS, sd=1, pid=["p_fs2", "p_fsr2"])
    return finish(d, [
        ["L_G", "Physical gate length, as drawn", f'{P["LG"]:g} nm'],
        ["Cell z", "Rail-to-rail cell width", f'{P["cell"]:g} nm'],
        ["Fin pitch", "Fin-to-fin, as drawn", f'{FP:g} nm'],
        ["Fins", "Per device", "2"], ["Gate faces", "Per fin", "3 (tri-gate)"],
        ["Gate", "Po, crossing all four fins", "1"], ["Contacts", "MD columns", "3"],
        ["Metal 0", "V_DD · IN · OUT · GND", "4 bars"],
        ["Drive", "Granularity", "one whole fin"]])


# ------------------------------------------------------------------------ CFET
def plate(x0, x1, y0, y1, z0, z1, holes=()):
    """A slab in the x-z plane with rectangular holes punched through it."""
    xs = sorted({x0, x1} | {v for h in holes for v in (h[0], h[1]) if x0 < v < x1})
    out = []
    for i in range(len(xs) - 1):
        a, b = xs[i], xs[i + 1]
        blocked = [(h[2], h[3]) for h in holes if h[0] <= a and h[1] >= b]
        for c, e in gaps(z0, z1, blocked):
            out.append(box(a, b, y0, y1, c, e))
    return out

def show_cfet():
    d = Dev("show_cfet", "CFET inverter · layout", "one stack, power from the back",
            "The same figure once the pMOS moves on top of the nMOS. There is no N Well beside "
            "the P Well any more — the top tier sits on the tier isolation, GND arrives from the "
            "back of the wafer, and the output has to climb past the isolation in its own riser.")
    P = plan("cfet")
    XW, XMD0, XMD1, XPO = P["xw"], P["xmd0"], P["xmd1"], P["xpo"]
    ZB, hw = P["zbar"], P["mw"] / 2.0
    ZCH = 20.0 / 2.0                             # sheet width, from the device scene
    ZC = P["half"] + hw                          # wells and oxide run under the far rail edge
    ZPL, GZ = ZC + 2.0, ZC
    YBM = (-56.0, -46.0); YBI = (-46.0, -34.0); YPW = (-34.0, -4.0); YOX = (-4.0, 6.0)
    WN = [(12.0, 17.0), (22.0, 27.0)]          # bottom tier, nMOS
    WP = [(42.0, 47.0), (52.0, 57.0)]          # top tier, pMOS
    YMDI = (30.0, 38.0)
    MDB = (6.0, 30.0); MDT = (38.0, 60.0)
    YPO = (6.0, 64.0); YVD = (60.0, 70.0); YVG = (64.0, 70.0); YM = (70.0, 78.0)
    vx = (XMD0 + XMD1) / 2.0
    VIA = (-vx - 4, -vx + 4, -6.0, 6.0)        # backside GND via footprint
    RIS = (vx - 5, vx + 5, ZCH + 2, ZCH + 12)  # output riser footprint

    # --- backside power ----------------------------------------------------
    A(d, "bm", "Backside Metal · GND", "m0",
      [box(-XW - 8, XW + 8, YBM[0], YBM[1], -ZPL, ZPL)], "Backside power", [0, -2.0, 0], "gnd")
    A(d, "bild", "Backside ILD", "fox",
      plate(-XW, XW, YBI[0], YBI[1], -ZC, ZC, [VIA]), "Backside power", [0, -1.7, 0])
    A(d, "via_gnd", "Buried power via · GND", "vd",
      [box(VIA[0], VIA[1], YBI[0], MDB[0], VIA[2], VIA[3])], "Backside power", [-1.0, -1.3, 0], "gnd")
    A(d, "pwell", "P Well", "pwell",
      plate(-XW, XW, YPW[0], YPW[1], -ZC, ZC, [VIA]), "Wells & oxide", [0, -1.2, 0])
    A(d, "fox", "SiO₂ field oxide", "fox",
      plate(-XW, XW, YOX[0], YOX[1], -ZC, ZC, [VIA, (-4.0, 4.0, -GZ, GZ)]),
      "Wells & oxide", [0, -.8, 0])

    # --- channels ----------------------------------------------------------
    for tier, bands, pol, net, grp in (("n", WN, "n", "chan_n", "nMOS channel (bottom tier)"),
                                       ("p", WP, "p", "chan_p", "chan_p_grp")):
        g = "nMOS channel (bottom tier)" if pol == "n" else "pMOS channel (top tier)"
        for i, (y0, y1) in enumerate(bands):
            A(d, f"{pol}_w{i+1}", f"{pol}MOS nanowire {i+1}", "nanowire",
              [box(-XMD0, XMD0, y0, y1, -ZCH, ZCH)], g, [0, 0, 0], net)
            A(d, f"{pol}_ws{i+1}", f"{pol}MOS nanowire {i+1} · drain stub", "nanowire",
              [box(XMD1, XW, y0, y1, -ZCH, ZCH)], g, [1.5, 0, 0], "body")
            A(d, f"{pol}_wsr{i+1}", f"{pol}MOS nanowire {i+1} · source stub", "nanowire",
              [box(-XW, -XMD1, y0, y1, -ZCH, ZCH)], g, [-1.5, 0, 0], "body")

    # --- tier isolation, punched for the gate and the riser ----------------
    A(d, "mdi", "Tier isolation", "mdi",
      plate(-XW, XW, YMDI[0], YMDI[1], -ZC, ZC, [(-XPO, XPO, -ZC, ZC), RIS]),
      "Tier isolation", [0, 1.0, 0])

    # --- contacts -----------------------------------------------------------
    A(d, "md_gnd", "MD · nMOS source (bottom)", "md",
      [box(-XMD1, -XMD0, MDB[0], MDB[1], -ZC, ZC)], "Contacts", [-1.3, -.3, 0], "gnd")
    A(d, "md_outb", "MD · nMOS drain (bottom)", "md",
      [box(XMD0, XMD1, MDB[0], MDB[1], -ZC, ZC)], "Contacts", [1.3, -.3, 0], "out")
    A(d, "md_vdd", "MD · pMOS source (top)", "md",
      [box(-XMD1, -XMD0, MDT[0], MDT[1], -ZC, ZC)], "Contacts", [-1.3, .5, 0], "vdd")
    A(d, "md_outt", "MD · pMOS drain (top)", "md",
      [box(XMD0, XMD1, MDT[0], MDT[1], -ZC, ZC)], "Contacts", [1.3, .5, 0], "out")
    A(d, "riser", "Output riser · past the isolation", "vd",
      [box(RIS[0], RIS[1], YMDI[0], YMDI[1], RIS[2], RIS[3])], "Contacts", [1.4, .1, .8], "out")

    # --- gate ---------------------------------------------------------------
    po = []
    for a, b in ((-GZ, -ZCH), (ZCH, GZ)):
        po.append(box(-XPO, XPO, YPO[0], YPO[1], a, b))
    for y0, y1 in gaps(YPO[0], YPO[1], WN + WP):
        po.append(box(-XPO, XPO, y0, y1, -ZCH, ZCH))
    po.append(box(-4, 4, YOX[0], YOX[1], -GZ, GZ))
    A(d, "po", "Po · gate through both tiers", "po", po, "Gate", [0, .9, 0], "in")

    # --- vias and Metal 0 ---------------------------------------------------
    A(d, "vd_vdd", "VD · V_DD", "vd",
      [box(-vx - 4, -vx + 4, YVD[0], YVD[1], ZB["vdd"] - 3, ZB["vdd"] + 3)], "Vias", [0, 1.2, 0], "vdd")
    A(d, "vd_out", "VD · OUT", "vd",
      [box(vx - 4, vx + 4, YVD[0], YVD[1], ZB["out"] - 3, ZB["out"] + 3)], "Vias", [0, 1.2, 0], "out")
    A(d, "vg", "VG · gate via", "vg",
      [box(-5, 5, YPO[1], YVG[1], ZB["in"] - 2, ZB["in"] + 2)], "Vias", [0, 1.3, 0], "in")
    for net, label in (("in", "IN"), ("out", "OUT"), ("vdd", "V_DD")):
        A(d, f"m0_{net}", f"Metal 0 · {label}", "m0",
          [box(-XW, XW, YM[0], YM[1], ZB[net] - hw, ZB[net] + hw)], "Metal 0", [0, 1.7, 0], net)

    # --- labels --------------------------------------------------------------
    mid = lambda a, b: (a + b) / 2.0
    # right-hand column, read bottom to top
    L(d, "Backside M0", [XW + 8, mid(*YBM), ZC * .6], "m", "dark", LAYER_VIEWS, sd=1, pid="bm")
    L(d, "P Well", [XW, mid(*YPW), ZC * .6], "m", "dark", LAYER_VIEWS, sd=1, pid="pwell")
    L(d, "SiO₂", [XW, mid(*YOX), ZC * .6], "m", "dark", LAYER_VIEWS, sd=1, pid="fox")
    L(d, "Nanowire", [XW, 24.5, ZCH - 3], "s", "dark", LAYER_VIEWS, pid=["n_ws2", "n_wsr2", "p_ws2", "p_wsr2"])
    L(d, "Tier isolation", [XW, mid(*YMDI), ZC * .6], "m", "dark", LAYER_VIEWS, sd=1, pid="mdi")
    L(d, "MD", [XMD1, mid(*MDT), ZCH + OVH], "m", "dark", LAYER_VIEWS, sd=1, pid=["md_outt", "md_vdd"])
    L(d, "VD", [vx, mid(*YVD), ZB["out"]], "s", "dark", LAYER_VIEWS, sd=1, pid="vd_out")
    # left-hand column
    L(d, "GND", [-XW - 8, mid(*YBM), -ZC * .6], "m", "dark", LAYER_VIEWS, sd=-1, pid="bm")
    L(d, "MD", [-XMD1, mid(*MDB), -ZCH - OVH], "m", "dark", LAYER_VIEWS, sd=-1, pid="md_gnd")
    L(d, "Po", [-XPO, 52, -ZC * .7], "m", "dark", LAYER_VIEWS, pid="po")
    L(d, "VG", [-5, mid(*YVG), ZB["in"]], "s", "dark", LAYER_VIEWS, pid="vg")
    for net, label in (("in", "IN"), ("out", "OUT"), ("vdd", "V_DD")):
        L(d, label, [-XW, mid(*YM), ZB[net]], "m", sd=-1, pid=f"m0_{net}")

    d.note = ("<b>No second device row.</b> The pMOS sits directly above the nMOS, so the figure "
              "grows upwards instead of sideways and there is no N Well beside the P Well. Two "
              "things had to move: GND now comes up from a backside metal through a buried via, "
              "because nothing reaches the bottom tier from above, and the output needs its own "
              "riser through the tier isolation to tie the two drains together.")
    return finish(d, [
        ["L_G", "Physical gate length, as drawn", f'{P["LG"]:g} nm'],
        ["Cell z", "Rail-to-rail cell width", f'{P["cell"]:g} nm'],
        ["M0 pitch", "Metal 0 track pitch", f'{P["step"]:.1f} nm'],
        ["Tiers", "pMOS above nMOS", "2"], ["Nanowires", "Per tier", "2"],
        ["Gate", "Po, continuous through both", "1"], ["Contacts", "MD, split top and bottom", "4"],
        ["Metal 0", "V_DD · IN · OUT", "3 bars"], ["GND", "Reached from", "backside metal"]])

# --------------------------------------------------------------- LAYOUT COMPARE
def show_cmp():
    d = Dev("show_cmp", "Layout compare", "four cells, one scale",
            "The same inverter figure drawn four ways at one scale, each at its own rail-to-rail "
            "cell width. Read it left to right and you can watch the cell stop growing sideways "
            "and start growing upwards.")
    builders = [(show_fin, "FinFET", "2 fins per device", "fin"),
                (show_ns, "Nanosheet", "2 nanowires per device", "ns"),
                (show_fs, "Forksheet", "wall between n and p", "fs"),
                (show_cfet, "CFET", "pMOS stacked on nMOS", "cfet")]
    cur, GAP, cells = -320.0, 28.0, []
    for build, nm, sub, arch in builders:
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
        cells.append((nm, sub, cur + w / 2.0, ARCH[arch]["cell"], src.bounds["y"][1]))
        w = src.bounds["z"][1] - src.bounds["z"][0]
        cur += w + GAP

    # Straight down, a title floating above a cell lands on top of it, so the names only
    # show in the views that look at the row from the side.
    for nm, sub, zc, w, ytop in cells:
        L(d, nm, [0, ytop + 26, zc], "l", lead=False, v=["front", "hero"])
        L(d, sub, [0, ytop + 12, zc], "s", lead=False, v=["front", "hero"])
    w0 = cells[0][3]
    d.dims = [[nm, sub, f"{w:g} nm  ({w / w0 * 100:.0f}%)"] for nm, sub, zc, w, yt in cells]
    d.dims.insert(0, ["—", "Rail-to-rail cell width", "same number the Inverter scenes use"])
    d.dims.append(["—", "Metal 0 bars on top", "4 / 4 / 4 / 3 (CFET GND is on the back)"])
    d.dims.append(["—", "What grows", "sideways, then upwards"])
    d.logic = True
    d.style = "schematic"
    d.note = ("<b>Left to right.</b> FinFET and nanosheet spend their width on two device rows "
              "with a work-function-metal gap between them. The forksheet replaces that gap with "
              "a wall. The CFET deletes the second row altogether and pays for it in height — "
              "note it carries only three Metal 0 bars, because GND has moved to the back of the "
              "wafer. <b>These are the same widths as the Inverter comparison</b>, because both "
              "are drawn from the same numbers: gate length, contacted pitch and track pitch all "
              "come from the device cross-sections.")
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    d.views = {
      "front": dict(n="Head on", s="all four, same scale", az=-1.5708, el=0.05, r=fit_r(B, -1.5708, 0.05), tgt=ctr, clip=None),
      "hero": dict(n="All four", s="three-quarter", az=-1.30, el=0.28, r=fit_r(B, -1.30, 0.28), tgt=ctr, clip=None),
      "top": dict(n="Top view", s="Metal 0 routing", az=-1.5708, el=1.42, r=fit_r(B, -1.5708, 1.42), tgt=ctr, clip=None)}
    return d

# Technology-generation labels. These are node NAMES, not lengths — since roughly the
# 90 nm generation the number on the label has not matched any dimension on the wafer.
# They sit in the table next to the physical gate length on purpose: the contrast is the
# point. Change a value here and it updates every scene for that architecture.
NODE = {"fin": "3 nm", "ns": "1.4 nm", "fs": "1.2 nm", "cfet": "1 nm"}
NODE_ROW = ["Node", "Technology generation (a name, not a length)"]
CMP_ROW = ["Node", "FinFET · nanosheet · forksheet · CFET", "3 · 1.4 · 1.2 · 1 nm"]

def tag_nodes(devices):
    """Put the generation label at the top of every scene's table."""
    for dv in devices:
        k = dv["key"].replace("show_", "").replace("inv_", "")
        rows = [r for r in dv["dims"] if r[0] != "Node"]
        if k.startswith("cmp"):
            dv["dims"] = [list(CMP_ROW)] + rows
        else:
            arch = "cfet" if k.startswith("cfet") else k
            if arch in NODE:
                dv["dims"] = [NODE_ROW + [NODE[arch]]] + rows
            else:
                dv["dims"] = rows
    return devices

if __name__ == "__main__":
    import findlap
    G = json.load(open(DATA))
    G["devices"] = [x for x in G["devices"] if not x["key"].startswith("show_")]
    for f in (show_fin, show_ns, show_fs, show_cfet, show_cmp):
        d = f(); mx, n = check(d); laps = findlap.overlaps(d)
        print(f"{d.key:9s} parts={len(d.parts):3d} boxes={n:4d} max/voxel={mx}"
              + ("  LAP:" + str(laps) if laps else ""))
        G["devices"].append(dict(key=d.key, name=d.name, tag=d.tag, blurb=d.blurb, parts=d.parts,
            callouts=d.callouts, dims=d.dims, views=d.views, note=d.note, bounds=d.bounds,
            logic=True, style="schematic",
            groups=list(dict.fromkeys(p["group"] for p in d.parts))))
    tag_nodes(G["devices"])          # runs last, so every scene in the file gets the row
    json.dump(G, open(DATA, "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize(DATA) // 1024, "KB", len(G["devices"]), "scenes")
    print("nodes:", ", ".join(f"{k}={v}" for k, v in NODE.items()))
