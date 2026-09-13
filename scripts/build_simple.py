"""
Simplified device views: one transistor, only the layers that carry the idea.

The full Device scenes model every film — nine of them — which is the right answer
when you want to see how the thing is actually built and the wrong one when you are
trying to learn what it is. These keep the same footprint and the same scale but
show five bodies: substrate, source, channel, gate, drain. Flat shading and names
lying on the geometry, like the Layout scenes.
"""
import json, os
from build_devices import Dev, box, gaps, check
from build_showcase import L, LAYER_VIEWS

# ---- chunky common frame --------------------------------------------------
# The gap between the gate and the pads is deliberately wide: it is the only place the
# channel is visible, and the channel is the whole point of the drawing.
XE, XSD, XCH = 78.0, 48.0, 26.0     # outer / source-drain inner edge / gate half-width
YSUB0, YSUB1 = -26.0, 0.0
ZW = 26.0                            # half-depth of the active region
YTOP = 52.0                          # top of the gate

def A(d, pid, name, mat, boxes, group, explode):
    d.add(pid, name, mat, boxes, group, explode)
    d.parts[-1]["net"] = "body"

def frame(d, tiers, wall=None, backside=False):
    """Substrate plus the source and drain pads for each tier of channels."""
    A(d, "sub", "Silicon substrate", "silicon",
      [box(-XE, XE, YSUB0, YSUB1, -44, 44)], "Substrate", [0, -1.4, 0])
    for i, (y0, y1, tag) in enumerate(tiers):
        A(d, f"src{i}", f"Source {tag}".strip(), "md",
          [box(-XE, -XSD, y0 - 4, y1 + 4, -ZW, ZW)], "Source / drain", [-1.5, 0, 0])
        A(d, f"drn{i}", f"Drain {tag}".strip(), "md",
          [box(XSD, XE, y0 - 4, y1 + 4, -ZW, ZW)], "Source / drain", [1.5, 0, 0])

def gate(d, holes, zlo=-ZW - 6, zhi=ZW + 6, ylo=2.0, yhi=YTOP, name="Gate"):
    """One gate body, split around whatever the channel occupies."""
    g = []
    edges = [zlo]
    for z0, z1, bands in holes: edges += [z0, z1]
    edges.append(zhi)
    for i in range(0, len(edges), 2):
        if edges[i + 1] > edges[i]:
            g.append(box(-XCH, XCH, ylo, yhi, edges[i], edges[i + 1]))
    for z0, z1, bands in holes:
        for y0, y1 in gaps(ylo, yhi, bands):
            g.append(box(-XCH, XCH, y0, y1, z0, z1))
    A(d, "gate", f"{name} · wraps the channel", "po", g, "Gate", [0, 1.2, 0])

def finish(d, dims, note):
    d.style = "schematic"
    d.logic = False
    d.dims = dims
    d.note = note
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    r = 2.15 * max(B["x"][1] - B["x"][0], B["y"][1] - B["y"][0], B["z"][1] - B["z"][0])
    d.views = {
        "hero":  dict(n="The device", s="three-quarter", az=-0.62, el=0.30, r=r, tgt=ctr, clip=None),
        "along": dict(n="Along the channel", s="source to drain", az=1.5708, el=0.12, r=r * .78, tgt=ctr, clip=None),
        "front": dict(n="Across the gate", s="what the gate touches", az=0.0, el=0.12, r=r * .78, tgt=ctr, clip=None),
        "top":   dict(n="Top view", s="footprint", az=0.0, el=1.42, r=r * .82, tgt=ctr, clip=None)}
    return d

def names(d, chan_label, chan_pids, extra=()):
    L(d, "Substrate", [0, YSUB1, 0], "m", "dark", LAYER_VIEWS, pid="sub")
    L(d, "Source", [-XE, 20, 0], "m", "dark", LAYER_VIEWS, pid=[p for p in d_ids(d, "src")])
    L(d, "Drain", [XE, 20, 0], "m", "dark", LAYER_VIEWS, pid=[p for p in d_ids(d, "drn")])
    L(d, "Gate", [0, YTOP, 0], "m", "dark", LAYER_VIEWS, pid="gate")
    L(d, chan_label, [0, 20, ZW], "s", "dark", LAYER_VIEWS, pid=chan_pids)
    for label, pid in extra:
        L(d, label, [0, 20, 0], "s", "dark", LAYER_VIEWS, pid=pid)

def d_ids(d, prefix):
    return [p["id"] for p in d.parts if p["id"].startswith(prefix)]

# ---- the four architectures ----------------------------------------------
def simp_ns():
    d = Dev("simp_ns", "Nanosheet FET · simplified", "GAA · 3 sheets",
            "The same device with everything but the essentials taken away: the substrate "
            "it sits on, a source and a drain, three channel sheets running between them, and "
            "one gate wrapping every sheet on all four sides.")
    bands = [(14.0, 20.0), (26.0, 32.0), (38.0, 44.0)]
    frame(d, [(14.0, 44.0, "")])
    for i, (y0, y1) in enumerate(bands):
        A(d, f"ch{i}", f"Channel sheet {i+1}", "nanowire",
          [box(-XSD, XSD, y0, y1, -18, 18)], "Channel", [0, 0, 0])
    gate(d, [(-18.0, 18.0, bands)])
    names(d, "Sheet", d_ids(d, "ch"))
    return finish(d, [["Node", "Technology generation (a name, not a length)", "1.4 nm"],
                      ["Sheets", "Stacked channels", "3"],
                      ["Gate faces", "Per sheet", "4 (all round)"],
                      ["Bodies drawn", "Simplified from the full stack", "5 of 9"]],
                  "<b>Why it is a gate-all-around.</b> The gate is one body that closes "
                  "around every sheet, so the channel has no face the gate cannot reach. "
                  "That is the whole difference from the fin, where the bottom is left out.")

def simp_fin():
    d = Dev("simp_fin", "FinFET · simplified", "tri-gate · 2 fins",
            "The pre-nanosheet device with everything but the essentials taken away. The "
            "channel is a pair of standing fins and the gate drapes over them, touching "
            "three faces of each and never the bottom.")
    frame(d, [(8.0, 40.0, "")])
    fz = []
    for i, zc in enumerate((-12.0, 12.0)):
        z0, z1 = zc - 5, zc + 5
        A(d, f"ch{i}", f"Fin {i+1}", "nanowire",
          [box(-XSD, XSD, 8.0, 40.0, z0, z1)], "Channel", [0, 0, 0])
        fz.append((z0, z1, [(8.0, 40.0)]))
    gate(d, sorted(fz))
    names(d, "Fin", d_ids(d, "ch"))
    return finish(d, [["Node", "Technology generation (a name, not a length)", "3 nm"],
                      ["Fins", "Standing channels", "2"],
                      ["Gate faces", "Per fin", "3 (not the bottom)"],
                      ["Bodies drawn", "Simplified from the full stack", "5 of 9"]],
                  "<b>Where the leakage hides.</b> The gate reaches the two sides and the "
                  "top of each fin, never underneath, so the path along the bottom of the "
                  "fin is only ever held shut by doping. That is the limit the nanosheet removes.")

def simp_fs():
    d = Dev("simp_fs", "Forksheet FET · simplified", "sheets against a wall",
            "A nanosheet cut in half by a dielectric wall. The gate can no longer close "
            "around the sheet on the wall side, so it reaches three faces — the trade the "
            "forksheet makes to let n and p sit closer together.")
    bands = [(16.0, 22.0), (30.0, 36.0)]
    frame(d, [(16.0, 36.0, "")])
    A(d, "wall", "Dielectric wall", "wall",
      [box(-XSD, XSD, 2.0, YTOP, -4, 4)], "Dielectric wall", [0, 1.0, 0])
    for i, (y0, y1) in enumerate(bands):
        A(d, f"ch{i}", f"Channel sheet {i+1}", "nanowire",
          [box(-XSD, XSD, y0, y1, 4, 20)], "Channel", [0, 0, 0])
    gate(d, [(-4.0, 4.0, [(2.0, YTOP)]), (4.0, 20.0, bands)])
    names(d, "Sheet", d_ids(d, "ch"), extra=[("Wall", "wall")])
    return finish(d, [["Node", "Technology generation (a name, not a length)", "1.2 nm"],
                      ["Sheets", "Stacked channels", "2"],
                      ["Gate faces", "Per sheet", "3 (wall on the fourth)"],
                      ["Bodies drawn", "Simplified from the full stack", "6 of 10"]],
                  "<b>What the wall buys.</b> It replaces the gap that used to separate the "
                  "n and p devices, so the pair fits in a narrower cell. The cost is one gate "
                  "face per sheet — the forksheet is a footprint trick, not a better channel.")

def simp_cfet():
    d = Dev("simp_cfet", "CFET · simplified", "one device above the other",
            "Two transistors on the same footprint. The lower tier is the nMOS and the "
            "upper the pMOS; one gate runs through both, which is what makes the pair a "
            "single logic input.")
    low = [(12.0, 18.0), (24.0, 30.0)]
    high = [(44.0, 50.0), (56.0, 62.0)]
    A(d, "sub", "Silicon substrate", "silicon",
      [box(-XE, XE, YSUB0, YSUB1, -44, 44)], "Substrate", [0, -1.4, 0])
    for tag, bands, i in (("(nMOS)", low, 0), ("(pMOS)", high, 1)):
        y0, y1 = bands[0][0], bands[-1][1]
        A(d, f"src{i}", f"Source {tag}", "md",
          [box(-XE, -XSD, y0 - 4, y1 + 4, -ZW, ZW)], "Source / drain", [-1.5, 0, 0])
        A(d, f"drn{i}", f"Drain {tag}", "md",
          [box(XSD, XE, y0 - 4, y1 + 4, -ZW, ZW)], "Source / drain", [1.5, 0, 0])
        for k, (a, b) in enumerate(bands):
            A(d, f"ch{i}{k}", f"Channel sheet {k+1} {tag}", "nanowire",
              [box(-XSD, XSD, a, b, -18, 18)], "Channel", [0, 0, 0])
    # the isolation sits either side of the gate, which runs through both tiers
    A(d, "iso", "Tier isolation", "mdi",
      [box(-XE, -XCH, 34.0, 40.0, -ZW, ZW), box(XCH, XE, 34.0, 40.0, -ZW, ZW)],
      "Tier isolation", [0, 1.0, 0])
    gate(d, [(-18.0, 18.0, low + high)], ylo=2.0, yhi=70.0)
    L(d, "Substrate", [0, YSUB1, 0], "m", "dark", LAYER_VIEWS, pid="sub")
    L(d, "Source", [-XE, 20, 0], "m", "dark", LAYER_VIEWS, pid=d_ids(d, "src"))
    L(d, "Drain", [XE, 20, 0], "m", "dark", LAYER_VIEWS, pid=d_ids(d, "drn"))
    L(d, "Gate", [0, 70, 0], "m", "dark", LAYER_VIEWS, pid="gate")
    L(d, "Sheet", [0, 20, ZW], "s", "dark", LAYER_VIEWS, pid=d_ids(d, "ch"))
    L(d, "Tier isolation", [XE, 37, 0], "s", "dark", LAYER_VIEWS, pid="iso")
    return finish(d, [["Node", "Technology generation (a name, not a length)", "1 nm"],
                      ["Tiers", "pMOS above nMOS", "2"],
                      ["Sheets", "Per tier", "2"],
                      ["Gate", "Through both tiers", "1"],
                      ["Bodies drawn", "Simplified from the full stack", "8 of 12"]],
                  "<b>Why it is one device, not two.</b> The gate is a single body running "
                  "from the bottom tier to the top, so both channels switch on the same input. "
                  "Stacking is what removes the second device row from the cell.")

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
