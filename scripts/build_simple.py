"""
One device, drawn exactly like the Layout scenes.

Same palette, same films, same proportions as the inverter layouts — the only thing
removed is the inverter itself: no second device, no Metal 0 rails carrying V_DD, IN,
OUT and GND across the cell. What is left is one transistor with its well, field
oxide, channel, source and drain contacts, gate, vias and a local Metal 0 pad.

Views follow the Layout scenes, plus the one view from the Device scenes that shows
what the gate actually touches — with the source side lifted off.
"""
import json, os
from build_devices import Dev, box, gaps, check
from build_showcase import L, plate, XW, XMD0, XMD1, XPO

# ---- the same frame the layout uses, narrowed to a single device ---------
ZCELL, ZPLINTH = 26.0, 32.0
YPW0, YPW1 = -34.0, -14.0          # well plinth
YWL0, YWL1 = -14.0, -4.0           # well
YOX0, YOX1 = -4.0, 6.0             # field oxide
YMD1, YPO1 = 38.0, 44.0            # tops of MD and Po
YV1, YM0, YM1 = 50.0, 50.0, 58.0   # via top / Metal 0
ZMD, ZPO = 18.0, 20.0              # half-depths of the contacts and the gate

def A(d, pid, name, mat, boxes, group, explode):
    d.add(pid, name, mat, boxes, group, explode)
    d.parts[-1]["net"] = "body"

def deck(d, holes, wall=None):
    """Well, oxide, contacts, gate, vias and one Metal 0 pad — no cell routing."""
    A(d, "pwell", "P Well", "pwell",
      [box(-62, 62, YPW0, YPW1, -ZPLINTH, ZPLINTH)], "Wells & oxide", [0, -1.5, 0])
    A(d, "pwell_u", "P Well", "pwell",
      [box(-54, 54, YWL0, YWL1, -ZCELL, ZCELL)], "Wells & oxide", [0, -1.2, 0])
    A(d, "fox", "SiO₂ field oxide", "fox",
      plate(-54, 54, YOX0, YOX1, -ZCELL, ZCELL, [(-4.0, 4.0, -ZPO, ZPO)]),
      "Wells & oxide", [0, -.8, 0])

    wz0, wz1 = wall if wall else (0.0, 0.0)
    if wall:
        A(d, "md_src", "MD · source", "md",
          [box(-XMD1, -XMD0, YOX1, YMD1, -ZMD, wz0), box(-XMD1, -XMD0, YOX1, YMD1, wz1, ZMD)],
          "Contacts", [-1.3, .3, 0])
        A(d, "md_drn", "MD · drain", "md",
          [box(XMD0, XMD1, YOX1, YMD1, -ZMD, wz0), box(XMD0, XMD1, YOX1, YMD1, wz1, ZMD)],
          "Contacts", [1.3, .3, 0])
    else:
        A(d, "md_src", "MD · source", "md",
          [box(-XMD1, -XMD0, YOX1, YMD1, -ZMD, ZMD)], "Contacts", [-1.3, .3, 0])
        A(d, "md_drn", "MD · drain", "md",
          [box(XMD0, XMD1, YOX1, YMD1, -ZMD, ZMD)], "Contacts", [1.3, .3, 0])

    po = []
    edges = [-ZPO]
    for z0, z1, bands in holes: edges += [z0, z1]
    edges.append(ZPO)
    for i in range(0, len(edges), 2):
        if edges[i + 1] > edges[i]:
            po.append(box(-XPO, XPO, YOX1, YPO1, edges[i], edges[i + 1]))
    for z0, z1, bands in holes:
        for y0, y1 in gaps(YOX1, YPO1, bands):
            po.append(box(-XPO, XPO, y0, y1, z0, z1))
    po.append(box(-4, 4, YOX0, YOX1, -ZPO, ZPO))          # foot, through the oxide
    A(d, "po", "Po · gate electrode", "po", po, "Gate", [0, .9, 0])

    # with a wall down the middle the drain via has to sit to one side of it
    vz = (8.0, 16.0) if wall else (-4.0, 4.0)
    A(d, "vd", "VD · drain via", "vd", [box(21, 29, YMD1, YV1, vz[0], vz[1])], "Vias", [0, 1.1, 0])
    A(d, "vg", "VG · gate via", "vg", [box(-5, 5, YPO1, YV1, -16, -8)], "Vias", [0, 1.2, 0])
    A(d, "m0_d", "Metal 0 · drain pad", "m0",
      [box(14, 36, YM0, YM1, -9, 9)], "Metal 0", [0, 1.6, 0])
    A(d, "m0_g", "Metal 0 · gate pad", "m0",
      [box(-14, 8, YM0, YM1, -21, -3)], "Metal 0", [0, 1.6, 0])

def names(d, chan_label, chan_pids, extra=()):
    L(d, "P Well", [62, (YPW0 + YPW1) / 2, 18], "m", pid=["pwell", "pwell_u"])
    L(d, "SiO₂", [54, (YOX0 + YOX1) / 2, 18], "m", pid="fox")
    L(d, "MD", [-XMD1, 22, -12], "m", pid="md_src")
    L(d, "MD", [XMD1, 22, 12], "m", pid="md_drn")
    L(d, "Po", [-XPO, 40, -ZPO], "m", pid="po")
    L(d, "VD", [29, 44, 4], "s", pid="vd")
    L(d, "VG", [-5, 47, -12], "s", pid="vg")
    L(d, "Metal 0", [36, 54, 0], "m", pid=["m0_d", "m0_g"])
    L(d, chan_label, [XW, 25, 8], "s", pid=chan_pids)
    for label, pid in extra:
        L(d, label, [0, 30, 0], "s", pid=pid)

def finish(d, dims, note, extra_view):
    d.style = "schematic"
    d.logic = False
    d.dims = dims
    d.note = note
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    r = 2.15 * max(B["x"][1] - B["x"][0], B["y"][1] - B["y"][0], B["z"][1] - B["z"][0])
    d.views = {
        "hero":  dict(n="The device", s="three-quarter, all layers", az=-0.62, el=0.30, r=r, tgt=ctr, clip=None),
        "front": dict(n="Front on", s="stack from the side", az=0.0, el=0.10, r=r * .80, tgt=ctr, clip=None),
        "end":   dict(n="Through the gate", s="channel in section", az=1.5708, el=0.16, r=r * .74, tgt=ctr, clip=[0.0, None, None]),
        "top":   dict(n="Top view", s="footprint", az=0.0, el=1.42, r=r * .82, tgt=ctr, clip=None)}
    # the Device-scene view: cut back to the gate and lift the source side away
    d.views[extra_view[0]] = dict(n=extra_view[1], s="source side lifted off",
                                  az=-1.15, el=0.30, r=r * .82, tgt=ctr,
                                  clip=[XPO, None, None], off=["md_src", "m0_g", "vg"])
    return d

# ---- the four architectures, each drawn like its layout scene ------------
def simp_ns():
    d = Dev("simp_ns", "Nanosheet FET · single device", "GAA · 2 nanowires",
            "The layout figure with the inverter taken out of it: one transistor, the "
            "same films in the same proportions, but no second device and no Metal 0 "
            "rails crossing the cell.")
    wires = [(12.0, 17.0), (23.0, 28.0)]
    for i, (y0, y1) in enumerate(wires):
        A(d, f"w{i+1}", f"Nanowire {i+1}", "nanowire",
          [box(-XMD0, XMD0, y0, y1, -10, 10)], "Channel", [0, 0, 0])
        A(d, f"ws{i+1}", f"Nanowire {i+1} · drain stub", "nanowire",
          [box(XMD1, XW, y0, y1, -10, 10)], "Channel", [1.5, 0, 0])
        A(d, f"wsr{i+1}", f"Nanowire {i+1} · source stub", "nanowire",
          [box(-XW, -XMD1, y0, y1, -10, 10)], "Channel", [-1.5, 0, 0])
    deck(d, [(-10.0, 10.0, wires)])
    names(d, "Nanowire", ["ws2", "wsr2", "ws1", "wsr1"])
    return finish(d, [["Node", "Technology generation (a name, not a length)", "1.4 nm"],
                      ["Nanowires", "Stacked channels", "2"],
                      ["Gate faces", "Per wire", "4 (all round)"],
                      ["Contacts", "MD source and drain", "2"]],
                  "<b>What the gate touches.</b> The Po body closes around every nanowire, so "
                  "there is no face of the channel it cannot reach. Cut back to the gate and "
                  "lift the source contact off to see it.", ("gaa", "Gate all around"))

def simp_fin():
    d = Dev("simp_fin", "FinFET · single device", "tri-gate · 2 fins",
            "The layout figure with the inverter taken out of it. The channel is a pair of "
            "standing fins and the Po gate drapes over them, reaching three faces and never "
            "the bottom.")
    FW, FY0, FY1, FP = 5.0, 6.0, 34.0, 14.0
    holes = []
    for i, zc in enumerate((-FP / 2, FP / 2)):
        z0, z1 = zc - FW / 2, zc + FW / 2
        A(d, f"f{i+1}", f"Fin {i+1}", "nanowire",
          [box(-XMD0, XMD0, FY0, FY1, z0, z1)], "Channel", [0, 0, 0])
        A(d, f"fs{i+1}", f"Fin {i+1} · drain stub", "nanowire",
          [box(XMD1, XW, FY0, FY1, z0, z1)], "Channel", [1.5, 0, 0])
        A(d, f"fsr{i+1}", f"Fin {i+1} · source stub", "nanowire",
          [box(-XW, -XMD1, FY0, FY1, z0, z1)], "Channel", [-1.5, 0, 0])
        holes.append((z0, z1, [(FY0, FY1)]))
    deck(d, sorted(holes))
    names(d, "Fin", ["fs2", "fsr2", "fs1", "fsr1"])
    return finish(d, [["Node", "Technology generation (a name, not a length)", "3 nm"],
                      ["Fins", "Standing channels", "2"],
                      ["Gate faces", "Per fin", "3 (not the bottom)"],
                      ["Contacts", "MD source and drain", "2"]],
                  "<b>Where the leakage hides.</b> The gate reaches the two sides and the top "
                  "of each fin, never underneath, so the path along the bottom is only held "
                  "shut by doping.", ("tri", "Tri-gate"))

def simp_fs():
    d = Dev("simp_fs", "Forksheet FET · single device", "sheets against a wall",
            "The layout figure with the inverter taken out of it. A dielectric wall runs up "
            "through the gate on one side of the channel, which is what lets n and p sit "
            "closer together in a real cell.")
    wires = [(12.0, 17.0), (23.0, 28.0)]
    A(d, "wall", "Dielectric wall", "wall",
      [box(-XW, XW, YOX1, YPO1, -5, 5)], "Dielectric wall", [0, 1.3, 0])
    for i, (y0, y1) in enumerate(wires):
        A(d, f"w{i+1}", f"Sheet {i+1}", "nanowire",
          [box(-XMD0, XMD0, y0, y1, 5, 22)], "Channel", [0, 0, 0])
        A(d, f"ws{i+1}", f"Sheet {i+1} · drain stub", "nanowire",
          [box(XMD1, XW, y0, y1, 5, 22)], "Channel", [1.5, 0, 0])
        A(d, f"wsr{i+1}", f"Sheet {i+1} · source stub", "nanowire",
          [box(-XW, -XMD1, y0, y1, 5, 22)], "Channel", [-1.5, 0, 0])
    deck(d, [(-5.0, 5.0, [(YOX1, YPO1)]), (5.0, 22.0, wires)], wall=(-5.0, 5.0))
    names(d, "Sheet", ["ws2", "wsr2", "ws1", "wsr1"], extra=[("Wall", "wall")])
    return finish(d, [["Node", "Technology generation (a name, not a length)", "1.2 nm"],
                      ["Sheets", "Stacked channels", "2"],
                      ["Gate faces", "Per sheet", "3 (wall on the fourth)"],
                      ["Contacts", "MD source and drain", "2"]],
                  "<b>What the wall costs.</b> It replaces the gate metal on one side of each "
                  "sheet. One gate face is given up so the cell can be narrower.",
                  ("fork", "The fork"))

def simp_cfet():
    d = Dev("simp_cfet", "CFET · single stack", "one device above the other",
            "The layout figure with the routing taken out of it. Two transistors share one "
            "footprint — the lower tier and the upper tier — with a single Po gate running "
            "through both and tier isolation between them.")
    low = [(12.0, 17.0), (23.0, 28.0)]
    high = [(44.0, 49.0), (55.0, 60.0)]
    YMDI = (32.0, 40.0)
    A(d, "pwell", "P Well", "pwell",
      [box(-62, 62, YPW0, YPW1, -ZPLINTH, ZPLINTH)], "Wells & oxide", [0, -1.5, 0])
    A(d, "pwell_u", "P Well", "pwell",
      [box(-54, 54, YWL0, YWL1, -ZCELL, ZCELL)], "Wells & oxide", [0, -1.2, 0])
    A(d, "fox", "SiO₂ field oxide", "fox",
      plate(-54, 54, YOX0, YOX1, -ZCELL, ZCELL, [(-4.0, 4.0, -ZPO, ZPO)]),
      "Wells & oxide", [0, -.8, 0])
    for tier, bands in (("n", low), ("p", high)):
        for i, (y0, y1) in enumerate(bands):
            A(d, f"{tier}w{i+1}", f"{tier}MOS nanowire {i+1}", "nanowire",
              [box(-XMD0, XMD0, y0, y1, -10, 10)], "Channel", [0, 0, 0])
            A(d, f"{tier}ws{i+1}", f"{tier}MOS nanowire {i+1} · drain stub", "nanowire",
              [box(XMD1, XW, y0, y1, -10, 10)], "Channel", [1.5, 0, 0])
            A(d, f"{tier}wsr{i+1}", f"{tier}MOS nanowire {i+1} · source stub", "nanowire",
              [box(-XW, -XMD1, y0, y1, -10, 10)], "Channel", [-1.5, 0, 0])
    A(d, "mdi", "Tier isolation", "mdi",
      plate(-XW, XW, YMDI[0], YMDI[1], -ZMD, ZMD, [(-XPO, XPO, -ZMD, ZMD)]),
      "Tier isolation", [0, 1.0, 0])
    for tag, y0, y1, ex in (("bot", YOX1, YMDI[0], -.3), ("top", YMDI[1], 62.0, .5)):
        A(d, f"md_src_{tag}", f"MD · source ({tag})", "md",
          [box(-XMD1, -XMD0, y0, y1, -ZMD, ZMD)], "Contacts", [-1.3, ex, 0])
        A(d, f"md_drn_{tag}", f"MD · drain ({tag})", "md",
          [box(XMD0, XMD1, y0, y1, -ZMD, ZMD)], "Contacts", [1.3, ex, 0])
    po = []
    for z0, z1 in ((-ZPO, -10.0), (10.0, ZPO)):
        po.append(box(-XPO, XPO, YOX1, 66.0, z0, z1))
    for y0, y1 in gaps(YOX1, 66.0, low + high):
        po.append(box(-XPO, XPO, y0, y1, -10, 10))
    po.append(box(-4, 4, YOX0, YOX1, -ZPO, ZPO))
    A(d, "po", "Po · gate through both tiers", "po", po, "Gate", [0, .9, 0])
    A(d, "vd", "VD · drain via", "vd", [box(21, 29, 62.0, 72.0, -4, 4)], "Vias", [0, 1.1, 0])
    A(d, "vg", "VG · gate via", "vg", [box(-5, 5, 66.0, 72.0, -16, -8)], "Vias", [0, 1.2, 0])
    A(d, "m0_d", "Metal 0 · drain pad", "m0", [box(14, 36, 72.0, 80.0, -9, 9)], "Metal 0", [0, 1.6, 0])
    A(d, "m0_g", "Metal 0 · gate pad", "m0", [box(-14, 8, 72.0, 80.0, -21, -3)], "Metal 0", [0, 1.6, 0])
    L(d, "P Well", [62, (YPW0 + YPW1) / 2, 18], "m", pid=["pwell", "pwell_u"])
    L(d, "SiO₂", [54, (YOX0 + YOX1) / 2, 18], "m", pid="fox")
    L(d, "MD", [-XMD1, 20, -12], "m", pid=["md_src_bot", "md_src_top"])
    L(d, "MD", [XMD1, 50, 12], "m", pid=["md_drn_top", "md_drn_bot"])
    L(d, "Tier isolation", [XW, 36, 12], "s", pid="mdi")
    L(d, "Po", [-XPO, 55, -ZPO], "m", pid="po")
    L(d, "VD", [29, 67, 0], "s", pid="vd")
    L(d, "Metal 0", [36, 76, 0], "m", pid=["m0_d", "m0_g"])
    L(d, "Nanowire", [XW, 25, 8], "s", pid=["nws2", "nwsr2", "pws2", "pwsr2"])
    d.views = {}
    return finish(d, [["Node", "Technology generation (a name, not a length)", "1 nm"],
                      ["Tiers", "pMOS above nMOS", "2"],
                      ["Nanowires", "Per tier", "2"],
                      ["Gate", "Po, through both tiers", "1"]],
                  "<b>Why it is one input.</b> The Po is a single body from the bottom tier to "
                  "the top, so both channels switch together. Stacking is what removes the "
                  "second device row from a cell.", ("tier", "Tier interface"))

if __name__ == "__main__":
    import findlap
    G = json.load(open("devices.json"))
    G["devices"] = [x for x in G["devices"] if not x["key"].startswith("simp_")]
    for f in (simp_fin, simp_ns, simp_fs, simp_cfet):
        d = f(); mx, n = check(d); laps = findlap.overlaps(d)
        print(f"{d.key:9s} parts={len(d.parts):3d} boxes={n:4d} max/voxel={mx}"
              + ("  LAP:" + str(laps) if laps else ""))
        G["devices"].append(dict(key=d.key, name=d.name, tag=d.tag, blurb=d.blurb, parts=d.parts,
            callouts=d.callouts, dims=d.dims, views=d.views, note=d.note, bounds=d.bounds,
            logic=False, style="schematic",
            groups=list(dict.fromkeys(p["group"] for p in d.parts))))
    json.dump(G, open("devices.json", "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize("devices.json") // 1024, "KB", len(G["devices"]), "scenes")
