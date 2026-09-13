"""
Single-device scenes, derived from the layout scenes rather than redrawn.

Every proportion in these comes from the Layout figures by construction: the layout
cell is built, the half that belongs to the other device is trimmed away in z, the
Metal 0 rails that make it an inverter are dropped, and what is left is recentred.
Nothing is re-typed by hand, so no dimension can drift out of step with the layout.

The CFET is the exception: its layout is already a single stack — the two tiers are
the n and the p — so only the routing comes off.
"""
import json, os
from build_devices import Dev, box, check
from build_showcase import (show_fin, show_ns, show_fs, show_cfet,
                            L, XMD0, XMD1, XPO, YMD1, YPO1, YV1, YM0, YM1)

# Which slice of the layout cell each architecture keeps, and what it drops.
# The window is centred on the surviving channel, so the device ends up centred too.
PLAN = {
    "fin":  dict(src=show_fin,  keep=(-48.0, 8.0),    drop=("p_", "m0_", "md_vdd", "nwell")),
    "ns":   dict(src=show_ns,   keep=(-48.0, 8.0),    drop=("p_", "m0_", "md_vdd", "nwell")),
    "fs":   dict(src=show_fs,   keep=(-43.5, 12.5),   drop=("p_", "m0_", "md_vdd", "nwell")),
    "cfet": dict(src=show_cfet, keep=None,            drop=("m0_",)),
}
NAMES = {"fin": ("FinFET", "tri-gate · 2 fins", "Fin", "tri", "Tri-gate"),
         "ns": ("Nanosheet FET", "GAA · 2 nanowires", "Nanowire", "gaa", "Gate all around"),
         "fs": ("Forksheet FET", "sheets against a wall", "Sheet", "fork", "The fork"),
         "cfet": ("CFET", "one device above the other", "Nanowire", "tier", "Tier interface")}
NOTE = {
 "fin": "<b>Where the leakage hides.</b> The gate reaches the two sides and the top of each "
        "fin, never underneath, so the path along the bottom of the fin is only ever held shut "
        "by doping. That is the limit the nanosheet removes.",
 "ns": "<b>What the gate touches.</b> The Po closes around every nanowire, so the channel has "
       "no face the gate cannot reach. Cut back to the gate and lift the source contact off to "
       "see it — that wrap is the whole difference from the fin.",
 "fs": "<b>What the wall costs.</b> It replaces the gate metal on one side of each sheet, so "
       "the gate reaches three faces instead of four. The forksheet gives that up to let n and "
       "p sit closer together — it is a footprint trick, not a better channel.",
 "cfet": "<b>Why it is one input.</b> The Po is a single body running from the bottom tier to "
         "the top, so both channels switch together. Stacking is what removes the second device "
         "row from the cell.",
}

def clip_boxes(boxes, lo, hi, shift):
    """Trim boxes to a z window and recentre. Empty results disappear."""
    out = []
    for cx, cy, cz, dx, dy, dz in boxes:
        z0, z1 = max(cz - dz / 2, lo), min(cz + dz / 2, hi)
        if z1 - z0 < 0.05: continue
        out.append([cx, cy, (z0 + z1) / 2 + shift, dx, dy, z1 - z0])
    return out

def carve(arch):
    """The layout cell with the other device and the cell routing taken off it."""
    p = PLAN[arch]
    src = p["src"]()
    nm, tag, chan, vkey, vlabel = NAMES[arch]
    d = Dev(f"simp_{arch}", f"{nm} · single device", tag,
            "The layout figure with the inverter taken out of it: one transistor, the same "
            "films at the same sizes, but no second device and no Metal 0 rails crossing the "
            "cell. Everything here is carried over from the Layout scene unchanged.")
    if p["keep"]:
        lo, hi = p["keep"]; shift = -(lo + hi) / 2
    else:
        lo, hi, shift = -1e9, 1e9, 0.0

    for part in src.parts:
        if any(part["id"].startswith(x) for x in p["drop"]): continue
        boxes = clip_boxes(part["boxes"], lo, hi, shift)
        if not boxes: continue
        pid = part["id"].replace("n_", "").replace("md_gnd", "md_src").replace("md_out", "md_drn")
        name = (part["name"].replace("nMOS ", "").replace("· nMOS source", "· source")
                            .replace("· shared drain", "· drain"))
        d.add(pid, name, part["material"], boxes, part["group"], part["explode"])
        d.parts[-1]["net"] = "body"
    return d, shift

def local_metal(d, ytop=None):
    """A via and a Metal 0 pad on the drain and on the gate — no rails across the cell."""
    ymd1 = YMD1 if ytop is None else ytop[0]
    ypo1 = YPO1 if ytop is None else ytop[1]
    yv1  = YV1 if ytop is None else ytop[2]
    ym0, ym1 = (YM0, YM1) if ytop is None else (ytop[3], ytop[4])
    have = {p["id"] for p in d.parts}
    if "vd_out" not in have:
        d.add("vd_drn", "VD · drain via", "vd", [box(21, 29, ymd1, yv1, 4, 10)], "Vias", [0, 1.1, 0])
        d.parts[-1]["net"] = "body"
    for pid, name, b in (("m0_d", "Metal 0 · drain pad", box(14, 36, ym0, ym1, -2, 16)),
                         ("m0_g", "Metal 0 · gate pad", box(-14, 8, ym0, ym1, -24, -6))):
        d.add(pid, name, "m0", [b], "Metal 0", [0, 1.6, 0])
        d.parts[-1]["net"] = "body"

def ids(d, *prefixes):
    return [p["id"] for p in d.parts if any(p["id"].startswith(x) for x in prefixes)]

def label(d, arch):
    chan = NAMES[arch][2]
    wells = ids(d, "pwell")
    L(d, "P Well", [0, 0, 0], "m", pid=wells)
    L(d, "SiO₂", [0, 0, 0], "m", pid=ids(d, "fox", "bild"))
    L(d, "MD", [0, 0, 0], "m", pid=ids(d, "md_src"))
    L(d, "MD", [0, 0, 0], "m", pid=ids(d, "md_drn", "md_out"))
    L(d, "Po", [0, 0, 0], "m", pid="po")
    L(d, "VD", [0, 0, 0], "s", pid=ids(d, "vd"))
    L(d, "VG", [0, 0, 0], "s", pid="vg")
    L(d, "Metal 0", [0, 0, 0], "m", pid=ids(d, "m0", "bm"))
    L(d, chan, [0, 0, 0], "s", pid=ids(d, "w", "f", "ws", "fs"))
    if arch == "fs":   L(d, "Wall", [0, 0, 0], "s", pid="wall")
    if arch == "cfet": L(d, "Tier isolation", [0, 0, 0], "s", pid="mdi")

def finish(d, arch, dims):
    nm, tag, chan, vkey, vlabel = NAMES[arch]
    d.style = "schematic"; d.logic = False
    d.dims = dims; d.note = NOTE[arch]
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    r = 2.15 * max(B["x"][1] - B["x"][0], B["y"][1] - B["y"][0], B["z"][1] - B["z"][0])
    off = [p["id"] for p in d.parts if p["id"].startswith("md_src")]
    d.views = {
      "hero":  dict(n="The device", s="three-quarter, all layers", az=-0.62, el=0.30, r=r, tgt=ctr, clip=None),
      "front": dict(n="Front on", s="stack from the side", az=0.0, el=0.10, r=r * .80, tgt=ctr, clip=None),
      "end":   dict(n="Through the gate", s="channel in section", az=1.5708, el=0.16, r=r * .74, tgt=ctr, clip=[0.0, None, None]),
      "top":   dict(n="Top view", s="footprint", az=0.0, el=1.42, r=r * .82, tgt=ctr, clip=None),
      vkey:    dict(n=vlabel, s="cut to the gate, source contact off", az=-1.15, el=0.30,
                    r=r * .84, tgt=ctr, clip=[XPO, None, None], off=off)}
    return d

DIMS = {
 "fin": [["Node", "Technology generation (a name, not a length)", "3 nm"],
         ["Fins", "Standing channels", "2"], ["Gate faces", "Per fin", "3 (not the bottom)"],
         ["Contacts", "MD source and drain", "2"], ["Carried from", "the FinFET layout cell", "every size"]],
 "ns":  [["Node", "Technology generation (a name, not a length)", "1.4 nm"],
         ["Nanowires", "Stacked channels", "2"], ["Gate faces", "Per wire", "4 (all round)"],
         ["Contacts", "MD source and drain", "2"], ["Carried from", "the nanosheet layout cell", "every size"]],
 "fs":  [["Node", "Technology generation (a name, not a length)", "1.2 nm"],
         ["Sheets", "Stacked channels", "2"], ["Gate faces", "Per sheet", "3 (wall on the fourth)"],
         ["Contacts", "MD source and drain", "2"], ["Carried from", "the forksheet layout cell", "every size"]],
 "cfet":[["Node", "Technology generation (a name, not a length)", "1 nm"],
         ["Tiers", "pMOS above nMOS", "2"], ["Nanowires", "Per tier", "2"],
         ["Gate", "Po, through both tiers", "1"], ["Carried from", "the CFET layout cell", "every size"]],
}

def build(arch):
    d, shift = carve(arch)
    if arch == "cfet":
        local_metal(d, ytop=(60.0, 64.0, 70.0, 70.0, 78.0))
    else:
        local_metal(d)
    label(d, arch)
    return finish(d, arch, DIMS[arch])

if __name__ == "__main__":
    import findlap
    G = json.load(open("devices.json"))
    G["devices"] = [x for x in G["devices"] if not x["key"].startswith("simp_")]
    for arch in ("fin", "ns", "fs", "cfet"):
        d = build(arch); mx, n = check(d); laps = findlap.overlaps(d)
        print(f"{d.key:9s} parts={len(d.parts):3d} boxes={n:4d} max/voxel={mx}"
              + ("  LAP:" + str(laps) if laps else ""))
        G["devices"].append(dict(key=d.key, name=d.name, tag=d.tag, blurb=d.blurb, parts=d.parts,
            callouts=d.callouts, dims=d.dims, views=d.views, note=d.note, bounds=d.bounds,
            logic=False, style="schematic",
            groups=list(dict.fromkeys(p["group"] for p in d.parts))))
    json.dump(G, open("devices.json", "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize("devices.json") // 1024, "KB", len(G["devices"]), "scenes")
