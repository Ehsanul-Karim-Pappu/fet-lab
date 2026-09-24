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
NS_SCOPE = ("Representative silicon nanosheet nFET fabrication using a replacement metal "
            "gate; selected isolation scheme (full bottom dielectric isolation) and "
            "illustrative materials. Not a verified foundry recipe.")

# A cut through the gate centre seen at an angle, so the cavities read as open space
# rather than as the spacer wall behind them.
CUTAWAY = dict(n="Gate cutaway", s="through the gate centre, at an angle",
               az=1.02, el=.34, r=255, tgt=[0, 44, 0], clip=[0, None, None])
# The same idea along the channel: cut at the middle of the sheets' width, seen at an
# angle, so the SiGe indents read as empty pockets under the spacers.
INDENT = dict(n="Channel cutaway", s="along the channel, at an angle",
              az=-.62, el=.30, r=225, tgt=[0, 44, 0], clip=[None, None, 0])


def flow_ns():
    dev = bd.build_ns()
    F = Flow(dev)
    P = F.final
    # Everything is read off the finished parts, so the flow cannot drift from them.
    sheets = [lim(P[f"sheet{i}"]["boxes"][0]) for i in (1, 2, 3)]
    hz = sheets[0][5]
    ys = [(s[2], s[3]) for s in sheets]
    bdi = lim(P["bdi"]["boxes"][0]); STI = bdi[3]
    sub = lim(P["substrate"]["boxes"][0]); zsub = sub[5]
    cap = lim(P["gatecap"]["boxes"][0]); ymo, ycap, hzmo = cap[2], cap[3], cap[5]
    top = ys[-1][1]
    sige = bd.gaps(STI, top, ys)                       # the layers between the sheets
    TOX = 1.0                                          # dummy-gate oxide

    def layers(x0, x1, z0=-hz, z1=hz, sheets_final=False):
        """Sacrificial SiGe and Si alternating from the bottom layer up to the top sheet."""
        F.drop("sige1", "sige2", "sige3", "si1", "si2", "si3", "sheet1", "sheet2", "sheet3")
        for i, (a, b) in enumerate(sige):
            F.put(tmp(f"sige{i+1}", f"SiGe · sacrificial layer {i+1}", "sige", "Superlattice",
                      [box(x0, x1, a, b, z0, z1)]))
        for i, (a, b) in enumerate(ys):
            if sheets_final: F.add(f"sheet{i+1}")
            else: F.put(tmp(f"si{i+1}", f"Si · future nanosheet {i+1}", "silicon", "Superlattice",
                            [box(x0, x1, a, b, z0, z1)]))

    def bottom(x0, x1, z0=-hz, z1=hz):
        F.put(tmp("bsige", "SiGe, high Ge · sacrificial bottom layer", "sige", "Superlattice",
                  [box(x0, x1, 0, STI, z0, z1)], (0, -.6, 0)))

    def ild_around():
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]]
        F.put(tmp("ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, ycap, -zsub, zsub), others), (0, .6, 0)))

    # 1
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", "Substrate & isolation",
              [box(sub[0], sub[1], sub[2], 0, -zsub, zsub)], (0, -1.2, 0)))
    F.snap("substrate", "Silicon substrate",
        "A crystalline silicon wafer, cleaned and prepared for epitaxy. The flow must also stop "
        "current leaking through the silicon beneath the channels: this model uses full bottom "
        "dielectric isolation (BDI) for that; a doped punch-through stopper is another published "
        "approach.")
    # 2
    bottom(-XSD, XSD, -zsub, zsub)
    layers(-XSD, XSD, -zsub, zsub)
    F.snap("superlattice", "Si/SiGe multilayer epitaxy",
        "Alternating SiGe and Si layers are grown as one solid crystalline stack. The Si layers "
        "become the nanosheets; the SiGe occupies the future gate spaces and is removed from the "
        "gate region later. The bottom SiGe, richer in Ge, belongs to the chosen isolation "
        "scheme: it can be etched selectively against the other SiGe layers.")
    # 3
    bottom(-XSD, XSD)
    layers(-XSD, XSD)
    F.drop("wafer"); F.add("substrate", "sti")
    F.snap("pattern", "Stack patterning and STI",
        "Lithography and etch cut the multilayer into narrow stacks, and on into the substrate as a "
        "short sub-fin; the mask sets the sheet width. Trench oxide is deposited, planarised and "
        "recessed: shallow trench isolation (STI) separates neighbouring devices sideways. Here it "
        "is recessed to the bottom of the high-Ge layer, leaving that layer's sidewalls open for "
        "its later removal. How the stack pattern is made depends on the layer, pitch and process: "
        "EUV single exposure allows different sheet widths, and dense arrays can also use "
        "spacer-based pitch splitting (SADP/SAQP), shown as an example in the FinFET flow.")
    # 4
    dox = subtract((-XG, XG, 0, top + TOX, -hz - TOX, hz + TOX), F.boxes())
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", "Dummy gate", dox, (0, .6, 0)))
    poly = subtract((-XG, XG, 0, ymo, -hzmo, hzmo), F.boxes())
    F.put(tmp("dummy", "Dummy gate · polysilicon", "poly", "Dummy gate", poly, (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0)))
    F.snap("dummy", "Dummy gate stack",
        "A thin sacrificial oxide, a polysilicon placeholder gate and a nitride hard mask are "
        "deposited and patterned across the stack. The dummy gate fixes where the gate goes and "
        "its length; the real high-κ/metal gate replaces it near the end (replacement metal gate).")
    # 5
    F.drop("bsige")
    F.snap("bottom", "Bottom-layer removal",
        "Where the stack is not covered by the dummy gate, its sidewalls are exposed (any covering "
        "liner is cleared first), including the high-Ge bottom layer's, which the STI recess left "
        "open. A selective etch removes that layer, working in from the exposed sides and on "
        "underneath the dummy gate, which holds the stack up over the open cavity. This follows "
        "one published early-BDI route [R13].", view="cutb")
    # 6
    F.add("bdi")
    for s, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s*XG, s*XSP))
        F.put(tmp(f"spo_{t}", f"Si₃N₄ gate spacer · {t} side", "si3n4", "Spacers",
                  subtract((xa, xb, 0, ycap, -hzmo, hzmo), F.boxes()), (s*1.3, 0, 0)))
    F.snap("spacers", "Spacer dielectric fill and etch-back",
        "A conformal spacer dielectric is deposited: it fills the cavity under the stack and coats "
        "everything else. Etch-back then clears it from the top and sides, leaving the outer "
        "spacers on the dummy-gate sidewalls and the bottom dielectric isolation (BDI) under the "
        "whole stack [R13]. In that route one dielectric forms both (SiOC, SiCN, SiOCN and SiBCN "
        "are its examples); the oxide BDI and nitride spacers here are illustrative substitutes.", view="cutb")
    # 7
    layers(-XSP, XSP, sheets_final=True)
    F.snap("recess", "Source/drain recess",
        "The stack outside the gate and spacers is etched away, stopping on the bottom isolation, "
        "which stays under the future source and drain. The ends of every Si and SiGe layer are "
        "now exposed at the recess walls.")
    # 8
    for i, (a, b) in enumerate(sige):
        F.put(tmp(f"sige{i+1}", f"SiGe · sacrificial layer {i+1}", "sige", "Superlattice",
                  [box(-XG, XG, a, b, -hz, hz)]))
    F.snap("indent", "SiGe indent",
        "A selective etch recesses the exposed SiGe ends sideways, leaving the Si sheet ends in "
        "place. The small cavities it opens, under the spacers, set the inner-spacer geometry; "
        "stopping at the gate edge is a schematic target, not a perfect alignment. This is a "
        "partial recess, not the channel release.", view="cutb")
    # 9
    F.drop("spo_source", "spo_drain"); F.add("spacer_source", "spacer_drain")
    F.snap("inner", "Inner-spacer deposition and etch-back",
        "Dielectric is deposited into the cavities, where it also coats every exposed surface, then "
        "etched back so it stays only in the cavities and the Si sheet ends are exposed again. The "
        "inner spacers separate the future gate from the source and drain between the sheets.",
        view="cutb")
    # 10
    F.add("epi_source", "epi_drain")
    F.snap("epi", "Source/drain epitaxy and anneal",
        "After a surface clean, doped silicon (Si:P for this nFET; B-doped SiGe is typical for "
        "pFETs) grows from the exposed Si sheet ends. The oxide below is not a crystal seed, so "
        "growth starts at the sheets and merges into one shared source on one side and one shared "
        "drain on the other, joining the sheet ends. The "
        "activation anneal that follows needs no separate step in this model, but it does change "
        "the device: dopant activation and diffusion shape the junction profile.")
    # 11
    ild_around()
    F.snap("ild", "ILD fill and planarisation",
        "Interlayer dielectric is deposited over everything and polished flat (CMP), stopping on "
        "the hard mask. The source and drain are now buried; hide the ILD in Layers to see them.")
    # 12
    F.drop("hardmask", "dummy", "dox")
    F.snap("pull", "Hard-mask opening and dummy-gate removal",
        "The hard mask is opened, the polysilicon is etched out selectively against the spacers "
        "and ILD, and the sacrificial oxide is cleared. The trench left behind is the replacement-"
        "gate cavity; the Si/SiGe stack is still intact at its bottom.", view="cut")
    # 13
    F.drop("sige1", "sige2", "sige3")
    F.snap("release", "Channel release",
        "A selective etch removes the SiGe inside the cavity, including under the lowest sheet. "
        "The Si nanosheets stay connected to the source and drain at their ends, with their gate "
        "surfaces now open above, below and beside each sheet. Etch selectivity, residues and "
        "sheets sticking together are real concerns; both wet and dry etches are used.", view="cut")
    # 14
    F.add(*[f"{k}{i}" for k in ("il", "hk", "tin") for i in (1, 2, 3)], "mo", "gatecap")
    F.snap("hkmg", "High-κ / metal gate",
        "After a surface clean, a thin interfacial oxide is formed on the released Si by "
        "oxidation. A high-κ dielectric and a work-function layer are then deposited conformally "
        "all round each sheet (for example by ALD), and a gate-fill metal joins them into one gate, "
        "with a cap on top. Materials here are illustrative: SiO₂, HfO₂, "
        "TiN and Mo stand for the interfacial, high-κ, work-function and fill layers; real stacks "
        "depend on device type and target threshold voltage.", view="cut")
    # 15
    F.add("nisi_source", "nisi_drain", "ni_source", "ni_drain", "w_source", "w_drain", "gatew")
    ild_around()
    F.snap("contacts", "Middle-of-line contacts",
        "Contact openings are etched through the ILD, the semiconductor contact interface is formed "
        "(a silicide here) and metal fills the openings, with a contact onto the gate. These are "
        "middle-of-line structures; the routing metal and vias above them (back end of line) are "
        "not modelled.")
    # 16
    F.drop("ild")
    F.snap("done", "The finished device",
        "The same model as Device mode, part for part. The ILD is hidden here only for viewing, as "
        "in the Device view; it is not removed in fabrication.")
    return dev, F.done(), dict(scope=NS_SCOPE, refs=["R13"], views=dict(cut=CUTAWAY, cutb=INDENT))


FLOWS = {"ns": flow_ns}


def main():
    out = {}
    for key, fn in FLOWS.items():
        dev, steps, extra = fn()
        out[key] = dict(extra, steps=steps)
        temp = {p["id"] for s in steps for p in s["parts"] if not isinstance(p, str)}
        print(f"{key:10s} steps={len(steps):2d}  temporary parts={len(temp)}  max solids/voxel=1")
    blob = json.dumps(dict(flows=out), ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(ROOT, "data/process.json"), "w") as f:
        f.write(blob)
    print(f"process.json {len(blob)//1024} KB")


if __name__ == "__main__":
    main()
