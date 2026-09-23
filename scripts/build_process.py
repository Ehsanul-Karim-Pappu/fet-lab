"""
Fabrication-process steps for the device scenes, written to data/process.json.

Each step is a complete scene state: the finished device's parts that exist by then
(referenced by id) plus temporary structures that do not survive to the end, such as
the sacrificial SiGe layers, the dummy poly gate and the interlayer dielectric. Every
step must tile exactly, like the finished models, and the last step must be the
finished device part for part.

The flows are representative teaching sequences, not any foundry's process recipe:
real flows add many cleans, implants, anneals and lithography steps left out here.
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_devices as bd
from build_devices import box, XG, XSP, XSD

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ helpers
def lim(b):
    cx, cy, cz, dx, dy, dz = b
    return (cx-dx/2, cx+dx/2, cy-dy/2, cy+dy/2, cz-dz/2, cz+dz/2)


def subtract(region, obstacles, eps=1e-6):
    """Disjoint boxes filling `region` (x0,x1,y0,y1,z0,z1) wherever no obstacle box
    is: the grid of every obstacle face, emptied cell by cell, then regrown greedily
    into as few boxes as the grid allows."""
    obs = [lim(b) for b in obstacles]
    def cuts(a, i):
        lo, hi = region[a], region[a+1]
        v = {lo, hi} | {o[i] for o in obs for i in (a, a+1) if lo < o[i] < hi}
        return sorted(v)
    xs, ys, zs = cuts(0, 0), cuts(2, 0), cuts(4, 0)
    nx, ny, nz = len(xs)-1, len(ys)-1, len(zs)-1
    free = np.ones((nx, ny, nz), bool)
    for o in obs:
        ix = [i for i in range(nx) if o[0] < (xs[i]+xs[i+1])/2 < o[1]]
        iy = [j for j in range(ny) if o[2] < (ys[j]+ys[j+1])/2 < o[3]]
        iz = [k for k in range(nz) if o[4] < (zs[k]+zs[k+1])/2 < o[5]]
        if ix and iy and iz:
            free[np.ix_(ix, iy, iz)] = False
    out = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                if not free[i, j, k]:
                    continue
                i1 = i
                while i1+1 < nx and free[i1+1, j, k]: i1 += 1
                j1 = j
                while j1+1 < ny and free[i:i1+1, j1+1, k].all(): j1 += 1
                k1 = k
                while k1+1 < nz and free[i:i1+1, j:j1+1, k1+1].all(): k1 += 1
                free[i:i1+1, j:j1+1, k:k1+1] = False
                out.append(box(xs[i], xs[i1+1], ys[j], ys[j1+1], zs[k], zs[k1+1]))
    return out


def tmp(pid, name, material, group, boxes, explode=(0, 0, 0)):
    """A temporary part: shown during the flow, gone from the finished device."""
    return dict(id=pid, name=name, material=material, group=group,
                boxes=[[round(float(v), 4) for v in b] for b in boxes], explode=list(explode))


def overlap(parts, bounds, step=0.5):
    """Most solids sharing one voxel: 1 means the step tiles without overlaps."""
    B = bounds
    gx = np.arange(B["x"][0], B["x"][1], step); gy = np.arange(B["y"][0], B["y"][1], step)
    gz = np.arange(B["z"][0], B["z"][1], step)
    cnt = np.zeros((len(gx), len(gy), len(gz)), np.uint8)
    for p in parts:
        for cx, cy, cz, dx, dy, dz in p["boxes"]:
            ix = (gx > cx-dx/2) & (gx < cx+dx/2); iy = (gy > cy-dy/2) & (gy < cy+dy/2)
            iz = (gz > cz-dz/2) & (gz < cz+dz/2)
            cnt[np.ix_(ix, iy, iz)] += 1
    return int(cnt.max())


class Flow:
    """Steps are built by editing one running set of parts, then snapshotting it."""
    def __init__(self, dev):
        self.dev = dev
        self.final = {p["id"]: p for p in dev.parts}
        self.now = {}            # id -> part (finished parts by reference, temporary inline)
        self.steps = []

    def add(self, *ids):
        for i in ids: self.now[i] = self.final[i]
    def put(self, part):
        self.now[part["id"]] = part
    def drop(self, *ids):
        for i in ids: self.now.pop(i, None)
    def boxes(self):
        return [b for p in self.now.values() for b in p["boxes"]]

    def snap(self, sid, title, body, view="iso"):
        parts = list(self.now.values())
        worst = overlap(parts, self.dev.bounds)
        if worst != 1:
            sys.exit(f"{self.dev.key} step '{sid}': {worst} solids overlap somewhere")
        self.steps.append(dict(id=sid, title=title, body=body, view=view,
            parts=[p["id"] if self.final.get(p["id"]) is p else p for p in parts]))

    def done(self):
        last = self.steps[-1]["parts"]
        if sorted(x for x in last if isinstance(x, str)) != sorted(self.final) or \
           any(not isinstance(x, str) for x in last):
            sys.exit(f"{self.dev.key}: the last step is not the finished device")
        return self.steps


# ============================================================== NANOSHEET ===
def flow_ns():
    dev = bd.build_ns()
    F = Flow(dev)
    P = F.final
    # Everything is read off the finished parts, so the flow cannot drift from them.
    sheets = [lim(P[f"sheet{i}"]["boxes"][0]) for i in (1, 2, 3)]
    hz = sheets[0][5]
    ys = [(s[2], s[3]) for s in sheets]
    sti = lim(P["sti"]["boxes"][0]); STI = sti[3]; zsub = sti[5]
    cap = lim(P["gatecap"]["boxes"][0]); ymo, ycap, hzmo = cap[2], cap[3], cap[5]
    top = ys[-1][1]
    sige = bd.gaps(STI, top, ys)                       # the layers between the sheets

    def stack(x0, x1, z0=-hz, z1=hz, bottom=True, sheets_final=False):
        """The Si/SiGe superlattice over x0..x1: an optional high-Ge bottom layer,
        then SiGe and Si alternating up to the top sheet."""
        F.drop("bsige", "sige1", "sige2", "sige3", "si1", "si2", "si3",
               "sheet1", "sheet2", "sheet3")
        if bottom:
            F.put(tmp("bsige", "SiGe, high Ge · sacrificial bottom layer", "sige", "Superlattice",
                      [box(x0, x1, 0, STI, z0, z1)], (0, -.6, 0)))
        for i, (a, b) in enumerate(sige):
            F.put(tmp(f"sige{i+1}", f"SiGe · sacrificial layer {i+1}", "sige", "Superlattice",
                      [box(x0, x1, a, b, z0, z1)]))
        for i, (a, b) in enumerate(ys):
            if sheets_final: F.add(f"sheet{i+1}")
            else: F.put(tmp(f"si{i+1}", f"Si · future nanosheet {i+1}", "silicon", "Superlattice",
                            [box(x0, x1, a, b, z0, z1)]))

    def sige_only(x0, x1):
        for i, (a, b) in enumerate(sige):
            F.put(tmp(f"sige{i+1}", f"SiGe · sacrificial layer {i+1}", "sige", "Superlattice",
                      [box(x0, x1, a, b, -hz, hz)]))

    # 1
    F.add("substrate")
    F.snap("substrate", "Silicon substrate",
        "The flow starts from a bulk silicon wafer. Everything above it is built up, or "
        "etched back, in the steps that follow.")
    # 2
    stack(-XSD, XSD, -zsub, zsub)
    F.snap("superlattice", "Si/SiGe superlattice epitaxy",
        "Alternating SiGe and Si layers are grown epitaxially across the wafer. The Si "
        "layers become the nanosheets; the SiGe between them is sacrificial and holds the "
        "gaps open until the gate goes in. The bottom SiGe, richer in Ge here, is removed "
        "separately later on, to isolate the stack from the substrate.")
    # 3
    stack(-XSD, XSD)
    F.put(tmp("sti_side", "STI oxide", "sio2", "Substrate & isolation",
              [box(-XSD, XSD, 0, STI, hz, zsub), box(-XSD, XSD, 0, STI, -zsub, -hz)], (0, -.8, 0)))
    F.snap("pattern", "Stack patterning and STI",
        "The superlattice is etched into a narrow stack, the width of the future sheets, and "
        "shallow-trench-isolation oxide fills the trenches beside it up to the bottom of the "
        "stack.")
    # 4
    poly = subtract((-XG, XG, STI, ymo, -hzmo, hzmo), F.boxes())
    F.put(tmp("dummy", "Dummy gate · polysilicon", "poly", "Dummy gate", poly, (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0)))
    F.snap("dummy", "Dummy gate and hard mask",
        "A polysilicon placeholder is patterned across the stack where the gate will be, "
        "capped by a nitride hard mask. It fixes the gate position and length now; the real "
        "high-κ/metal gate replaces it near the end (a replacement-metal-gate flow).")
    # 5
    F.drop("bsige")
    F.put(tmp("bdi", "Bottom dielectric isolation", "sio2", "Substrate & isolation",
              [box(-XSD, XSD, 0, STI, -hz, hz)], (0, -.8, 0)))
    for s, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s*XG, s*XSP))
        F.put(tmp(f"spo_{t}", f"Si₃N₄ gate spacer · {t} side", "si3n4", "Spacers",
                  subtract((xa, xb, STI, ycap, -hzmo, hzmo), F.boxes()), (s*1.3, 0, 0)))
    F.snap("spacers", "Gate spacers and bottom isolation",
        "Nitride spacers are formed on both sides of the dummy gate; they set how far the "
        "source and drain sit from the gate. In this model the high-Ge bottom layer is also "
        "removed selectively and replaced by oxide, cutting the stack off from the substrate.")
    # 6
    stack(-XSP, XSP, bottom=False, sheets_final=True)
    F.drop("sti_side", "bdi"); F.add("sti")
    F.snap("recess", "Source/drain recess",
        "The stack is etched away outside the spacers, down to the substrate, exposing the "
        "ends of every Si and SiGe layer. What remains under the gate and spacers is the "
        "channel region.")
    # 7
    sige_only(-XG, XG)
    F.drop("spo_source", "spo_drain"); F.add("spacer_source", "spacer_drain")
    F.snap("inner", "SiGe indent and inner spacers",
        "The SiGe layers are etched sideways from the exposed ends, back to the gate edge, and "
        "the pockets are filled with nitride. These inner spacers separate the future gate "
        "from the source and drain between the sheets.")
    # 8
    F.add("epi_source", "epi_drain")
    F.snap("epi", "Source/drain epitaxy",
        "Doped silicon (Si:P for this nFET) is grown from the exposed sheet ends and the "
        "substrate, forming the source and drain that every sheet connects to.")
    # 9
    ild = subtract((-XSD, XSD, 0, ycap, -zsub, zsub), F.boxes())
    F.put(tmp("ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric", ild, (0, .6, 0)))
    F.snap("ild", "ILD fill and planarisation",
        "Oxide is deposited over everything and polished flat (CMP) down to the top of the "
        "gate stack. The source and drain are now buried; hide the ILD in Layers to see them.")
    # 10
    F.drop("dummy", "hardmask")
    F.snap("pull", "Dummy gate removal",
        "The hard mask and the polysilicon are etched out, leaving a trench between the "
        "spacers. At its bottom the Si/SiGe stack is exposed again.", view="c")
    # 11
    F.drop("sige1", "sige2", "sige3")
    F.snap("release", "Channel release",
        "A selective etch removes the SiGe between the sheets inside the trench. The Si "
        "nanosheets are left suspended between the inner spacers, open on all four sides "
        "for the gate to wrap.", view="c")
    # 12
    F.add(*[f"{k}{i}" for k in ("il", "hk", "tin") for i in (1, 2, 3)], "mo", "gatecap")
    F.snap("hkmg", "High-κ / metal gate",
        "An interfacial oxide, HfO₂ and a TiN work-function layer coat each sheet all the "
        "way round, and Mo fills the rest of the trench, with a cap on top. This is the "
        "gate-all-around.", view="c")
    # 13
    F.add("nisi_source", "nisi_drain", "ni_source", "ni_drain", "w_source", "w_drain", "gatew")
    F.put(tmp("ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric",
              subtract((-XSD, XSD, 0, ycap, -zsub, zsub),
                       [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]]), (0, .6, 0)))
    F.snap("contacts", "Contacts and metal",
        "Openings are etched through the ILD, silicide forms on the source and drain, and "
        "metal fills the contact holes, with a contact onto the gate.")
    # 14
    F.drop("ild")
    F.snap("done", "The finished device",
        "The ILD is left out here, as in the Device view, so the structure shows. Compare "
        "with Device mode: this is the same model, part for part.")
    return dev, F.done()


FLOWS = {"ns": flow_ns}


def main():
    out = {}
    for key, fn in FLOWS.items():
        dev, steps = fn()
        out[key] = dict(steps=steps)
        temp = {p["id"] for s in steps for p in s["parts"] if not isinstance(p, str)}
        print(f"{key:10s} steps={len(steps):2d}  temporary parts={len(temp)}  max solids/voxel=1")
    blob = json.dumps(dict(flows=out), ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(ROOT, "data/process.json"), "w") as f:
        f.write(blob)
    print(f"process.json {len(blob)//1024} KB")


if __name__ == "__main__":
    main()
