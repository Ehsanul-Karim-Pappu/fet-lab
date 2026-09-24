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


# How a process state relates to its source, in the words the app shows. No state claims
# to match a drawing: the figure mappings follow the source's written description.
MATCH = {
    "published": "Published stage, adapted nFET view",
    "intermediate": "Intermediate teaching reconstruction",
    "concept": "Concept-only operation",
    "context": "Published stage, adapted view with pFET context",
}

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


def conformal(solids, t, window):
    """A conformal film of thickness [t] on every exposed surface inside [window]: each
    solid grown by t, less the solids and the film already laid. A gap narrower than 2t
    closes up."""
    out = []
    for b in solids:
        x0, x1, y0, y1, z0, z1 = lim(b)
        e = (max(x0 - t, window[0]), min(x1 + t, window[1]), max(y0 - t, window[2]),
             min(y1 + t, window[3]), max(z0 - t, window[4]), min(z1 + t, window[5]))
        if e[0] < e[1] and e[2] < e[3] and e[4] < e[5]:
            out += subtract(e, solids + out)
    return out


def clip(boxes, region):
    """The parts of [boxes] inside [region]."""
    out = []
    for b in boxes:
        x0, x1, y0, y1, z0, z1 = lim(b)
        c = (max(x0, region[0]), min(x1, region[1]), max(y0, region[2]), min(y1, region[3]),
             max(z0, region[4]), min(z1, region[5]))
        if c[0] < c[1] and c[2] < c[3] and c[4] < c[5]: out.append(box(*c))
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


class Stage:
    """One running set of parts at one scale (the single site, or the 2 x 2 tile), edited
    and then snapshotted into a step list the stages share. Finished parts are held by
    reference, stage-specific ones inline."""
    def __init__(self, flow, scale, bounds, grid=0.5):
        self.flow, self.scale, self.bounds, self.grid = flow, scale, bounds, grid
        self.now = {}

    def add(self, *ids):
        for i in ids: self.now[i] = self.flow.final[i]
    def put(self, part):
        self.now[part["id"]] = part
    def drop(self, *ids):
        for i in ids: self.now.pop(i, None)
    def drop_prefix(self, prefix):
        for i in [k for k in self.now if k.startswith(prefix)]: self.now.pop(i)
    def boxes(self, but=()):
        return [b for p in self.now.values() if p["id"] not in but for b in p["boxes"]]

    def snap(self, sid, title, body, view="iso", *, match, figs=(), subs=(), omitted=(), of=None):
        """[match] says how the state relates to its source (a MATCH key); [figs] are the
        source's figure identifiers; [subs] the model's material or dimension substitutions;
        [omitted] what the source shows at this stage that this view leaves out. [of] makes
        it an operation substep of the core step with that id, which must come next."""
        key = self.flow.dev.key
        if match not in (PAT_MATCH if isinstance(self.flow, Lesson) else MATCH):
            sys.exit(f"{key} step '{sid}': unknown match level {match!r}")
        parts = list(self.now.values())
        worst = overlap(parts, self.bounds, self.grid)
        if worst != 1:
            sys.exit(f"{key} step '{sid}': {worst} solids overlap somewhere")
        step = dict(id=sid, title=title, body=body, view=view, match=match,
                    figs=list(figs), subs=list(subs), omitted=list(omitted),
                    level="op" if of else "core", scale=self.scale,
                    parts=[p["id"] if self.flow.final.get(p["id"]) is p else p for p in parts])
        if of: step["of"] = of
        if self.scale != "site": step["bounds"] = self.bounds
        self.flow.steps.append(step)


class Flow(Stage):
    """The single-site stage, which owns the step list and the finished device."""
    def __init__(self, dev):
        self.dev = dev
        self.final = {p["id"]: p for p in dev.parts}
        self.steps = []
        super().__init__(self, "site", dev.bounds)

    def done(self):
        last = self.steps[-1]["parts"]
        if sorted(x for x in last if isinstance(x, str)) != sorted(self.final) or \
           any(not isinstance(x, str) for x in last):
            sys.exit(f"{self.dev.key}: the last step is not the finished device")
        # Core steps count 1, 2, 3...; the operations leading to core step n are n.1, n.2...
        core, ops = 0, 0
        for k, st in enumerate(self.steps):
            if st["level"] == "core":
                core += 1; ops = 0; st["label"] = str(core)
            else:
                nxt = next((x for x in self.steps[k + 1:] if x["level"] == "core"), None)
                if nxt is None or nxt["id"] != st["of"]:
                    sys.exit(f"{self.dev.key}: operation '{st['id']}' must lead into core step '{st['of']}'")
                ops += 1; st["label"] = f"{core + 1}.{ops}"
        return self.steps


def volumes(boxes_by_material, region):
    """Volume of each material inside [region] (x0,x1,y0,y1,z0,z1)."""
    out = {}
    for mat, boxes in boxes_by_material.items():
        v = 0.0
        for b in boxes:
            x0, x1, y0, y1, z0, z1 = lim(b)
            d = [min(x1, region[1]) - max(x0, region[0]), min(y1, region[3]) - max(y0, region[2]),
                 min(z1, region[5]) - max(z0, region[4])]
            if min(d) > 0: v += d[0] * d[1] * d[2]
        if v > 1e-6: out[mat] = round(v, 3)
    return out


def same_site(tile, site, region, what):
    """The tile, cropped to the selected site, must hold the same materials in the same
    amounts as the single-site model at that step."""
    def by_mat(stage):
        m = {}
        for p in stage.now.values(): m.setdefault(p["material"], []).extend(p["boxes"])
        return m
    a, b = volumes(by_mat(tile), region), volumes(by_mat(site), region)
    if a != b:
        sys.exit(f"{what}: the tile's selected site differs from the single-site model\n"
                 f"  tile {a}\n  site {b}")


# ============================================================== NANOSHEET ===
NS_SCOPE = ("Representative silicon nanosheet nFET fabrication using a replacement metal "
            "gate, following the nFET branch of one disclosed integration route [R13]: a p-type "
            "punch-through stopper and full bottom dielectric isolation, with illustrative "
            "materials and dimensions. Not a verified foundry recipe.")

# Figure identifiers name process states described in R13's text. Its drawings have not
# been compared with these views, so no state claims to reproduce a drawing.
NS_FIGURES = ("Figure numbers follow the patent's written description [R13]. Its drawings were "
              "not available for visual comparison: each view is a source-aligned teaching "
              "reconstruction, not a copy of a figure, and its orientation may differ.")
NS_BRANCH = ("The patent builds a pFET and an nFET from one shared stack. This lesson follows "
             "the nFET only: the pFET steps (Figs. 10–11 and 15) and the pFET beside it in the "
             "other figures are left out.")

# A cut through the gate centre seen at an angle, so the cavities read as open space
# rather than as the spacer wall behind them.
CUTAWAY = dict(n="Gate cutaway", s="through the gate centre, at an angle",
               az=1.02, el=.34, r=255, tgt=[0, 44, 0], clip=[0, None, None])
# The same idea along the channel: cut at the middle of the sheets' width, seen at an
# angle, so the SiGe indents read as empty pockets under the spacers.
INDENT = dict(n="Channel cutaway", s="along the channel, at an angle",
              az=-.62, el=.30, r=225, tgt=[0, 44, 0], clip=[None, None, 0])
# The 2 x 2 tile's views, in the same frame: the selected site at the origin, the second
# gate at x = -73, the pFET line at z = -84. A view belongs to one scale.
TILE_VIEWS = dict(
    tile=dict(n="Tile overview", s="four sites, two lines each way", az=-0.70, el=0.42, r=660,
              tgt=[-36.5, 55, -42], clip=None, scale="tile"),
    tileplan=dict(n="Tile from above", s="plan view", az=0.0, el=1.45, r=560,
                  tgt=[-36.5, 0, -42], clip=None, scale="tile"),
    tilecut=dict(n="Across the lines", s="section through the selected gate", az=1.5708, el=0.14,
                 r=470, tgt=[0, 40, -42], clip=[0, None, None], scale="tile"),
    tilechan=dict(n="Along the nFET line", s="section through the selected site", az=-0.62, el=0.30,
                  r=380, tgt=[-36.5, 45, 0], clip=[None, None, 0], scale="tile"),
    tilelow=dict(n="nFET line, low", s="under the stack, between the gates", az=0.32, el=0.07,
                 r=300, tgt=[-36.5, 22, 0], clip=None, scale="tile"))

# Figures of R13 this nFET lesson deliberately does not map to a step, and why.
NS_SKIPPED = {
    "10A/B": "pFET source/drain recess (pFET branch)",
    "11A/B": "pFET source/drain epitaxy (pFET branch)",
    "15A/B": "pFET channel preparation (pFET branch)",
    "19A/B": "an alternative shared-gate arrangement to Fig. 18, not a later step",
}

HKMG_SUB = "SiO₂, HfO₂, TiN and Mo stand for the interfacial, high-κ, work-function and fill layers"


def flow_ns(done):
    dev = bd.build_ns()
    F = Flow(dev)
    P = F.final
    # Everything is read off the finished parts, so the flow cannot drift from them.
    sheets = [lim(P[f"sheet{i}"]["boxes"][0]) for i in (1, 2, 3)]
    hz = sheets[0][5]
    ys = [(s[2], s[3]) for s in sheets]
    bdi = lim(P["bdi"]["boxes"][0]); STI = bdi[3]
    sub = lim(P["substrate"]["boxes"][0]); zsub = sub[5]
    pts = lim(P["pts"]["boxes"][0]); ypts = pts[2]           # bottom of the implanted layer
    cap = lim(P["gatecap"]["boxes"][0]); ymo, ycap, hzmo = cap[2], cap[3], cap[5]
    top = ys[-1][1]
    sige = bd.gaps(STI, top, ys)                       # the layers between the sheets
    TOX = 1.0                                          # dummy-gate oxide
    TSP = XSP - XG                                     # spacer film: its thickness is the spacer width

    def layers(x0, x1, z0=-hz, z1=hz, sheets_final=False):
        """Lower-Ge SiGe and Si alternating from the bottom layer up to the top sheet."""
        F.drop("sige1", "sige2", "sige3", "si1", "si2", "si3", "sheet1", "sheet2", "sheet3")
        for i, (a, b) in enumerate(sige):
            F.put(tmp(f"sige{i+1}", f"SiGe, lower Ge · sacrificial layer {i+1}", "sige", "Superlattice",
                      [box(x0, x1, a, b, z0, z1)]))
        for i, (a, b) in enumerate(ys):
            if sheets_final: F.add(f"sheet{i+1}")
            else: F.put(tmp(f"si{i+1}", f"Si · future nanosheet {i+1}", "silicon", "Superlattice",
                            [box(x0, x1, a, b, z0, z1)]))

    def bottom(x0, x1, z0=-hz, z1=hz):
        F.put(tmp("bsige", "SiGe, high Ge · sacrificial base layer", "sige", "Superlattice",
                  [box(x0, x1, 0, STI, z0, z1)], (0, -.6, 0)))

    def ild_around():
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]]
        F.put(tmp("ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, ycap, -zsub, zsub), others), (0, .6, 0)))

    def film(t, window):
        return conformal(F.boxes(), t, window)

    # ---------------------------------------------------------- the 2 x 2 tile ----
    # Two stack lines crossed by two gate lines, in the single site's own frame: the
    # selected nFET site (gate 0 on the nFET line) sits at the origin, the second gate one
    # pitch along the channel, the pFET line one pitch across. Adjacent sites on a line
    # share a source/drain, so they are sites, not four isolated transistors.
    PG, PS = 2 * XSD, 2 * zsub               # gate pitch = a site's length; stack pitch = its width
    GATES = (0.0, -PG)
    LINES = ((0.0, "n"), (-PS, "p"))
    ZMID = -PS / 2                            # boundary between the nFET and pFET regions
    WX0, WX1, WZ0, WZ1 = -XSD - PG, XSD, -zsub - PS, zsub      # the patterned window
    SX0, SX1 = sub[0] - PG, sub[1]            # the substrate, one gate pitch longer than the site's
    HMT, RT, RY = 6.0, 10.0, 140.0            # stack hard mask, resist; reticle height (not to scale)
    T = Stage(F, "tile", dict(x=[SX0, SX1], y=[sub[2], RY + 2.0], z=[WZ0, WZ1]))
    GS, GL = "Substrate & isolation", "Superlattice"
    SITE4 = (-XSD, XSD, sub[2], RY + 2.0, -zsub, zsub)    # the selected site, cropped out of the tile
    SITE5 = (-XSD, XSD, sub[2], RY + 2.0, -hzmo, hzmo)    # the same, across its gate's own width
    TILE_SUBS = ["Pitches are illustrative: the gate pitch is one site's length, the stack pitch "
                 "its width"]

    def t_multilayer(lines):
        """The multilayer, blanket over the window, or on each stack line once patterned.
        On the pFET line the patent's route keeps different layers, so they are not named
        sacrificial there."""
        T.drop_prefix("t_ml_")
        spans = [("all", WZ0, WZ1, "")] if not lines else \
                [(k, zc - hz, zc + hz, " · " + ("nFET" if k == "n" else "pFET") + " line") for zc, k in LINES]
        for k, z0, z1, where in spans:
            T.put(tmp(f"t_ml_base_{k}", "SiGe, high Ge · sacrificial base layer" + where, "sige", GL,
                      [box(WX0, WX1, 0, STI, z0, z1)], (0, -.6, 0)))
            for i, (a, b) in enumerate(sige):
                T.put(tmp(f"t_ml_sige{i+1}_{k}", f"SiGe, lower Ge · layer {i+1}" + where, "sige", GL,
                          [box(WX0, WX1, a, b, z0, z1)]))
            for i, (a, b) in enumerate(ys):
                T.put(tmp(f"t_ml_si{i+1}_{k}", f"Si · layer {i+1}" + where, "silicon", GL,
                          [box(WX0, WX1, a, b, z0, z1)]))

    def t_resist(pid, name, mat, boxes):
        T.put(tmp(pid, name, mat, "Patterning", boxes, (0, 1.6, 0)))

    def tile_patterning():
        """Stack patterning, operation by operation (the core step 'pattern')."""
        T.put(tmp("t_sub", "Si substrate", "silicon", GS, [box(SX0, SX1, sub[2], ypts, WZ0, WZ1)], (0, -1.2, 0)))
        T.put(tmp("t_pts_n", "p-type punch-through stopper · nFET region", "pts", GS,
                  [box(SX0, SX1, ypts, 0, ZMID, WZ1)], (0, -1.0, 0)))
        T.put(tmp("t_pts_p", "n-type punch-through stopper · pFET region", "pts_n", GS,
                  [box(SX0, SX1, ypts, 0, WZ0, ZMID)], (0, -1.0, 0)))
        t_multilayer(lines=False)
        T.put(tmp("t_hm", "Stack hard mask (blanket)", "si3n4", "Patterning",
                  [box(WX0, WX1, top, top + HMT, WZ0, WZ1)], (0, 1.3, 0)))
        T.snap("hm", "Hard-mask deposition",
            "Zoomed out to a tile of four gate/stack sites: two stack lines will run along the "
            "channel, one for nFETs through the selected site and one for pFETs beside it, each "
            "crossed later by two gate lines. First a hard-mask film is deposited over the "
            "multilayer. The implanted stoppers differ by region: p-type under the nFET line, "
            "n-type under the pFET line [R13].", view="tile", of="pattern",
            match="intermediate", figs=["3A/B", "5A/B"],
            subs=TILE_SUBS + ["Hard-mask material and thickness are illustrative"],
            omitted=["The masks that kept each stopper implant to its own region"])
        t_resist("t_res", "Photoresist (coated)", "resist", [box(WX0, WX1, top + HMT, top + HMT + RT, WZ0, WZ1)])
        T.snap("coat", "Resist coat",
            "A light-sensitive photoresist is spun on over the hard mask. It will carry the "
            "pattern first; the hard mask then carries it into the stack [R16].", view="tile",
            of="pattern", match="concept", subs=["Resist thickness is illustrative"])
        T.drop("t_res")
        lines = [(zc - hz, zc + hz) for zc, _ in LINES]
        gaps_z = bd.gaps(WZ0, WZ1, sorted(lines))
        t_resist("t_res", "Photoresist (unexposed: over the stack lines)", "resist",
                 [box(WX0, WX1, top + HMT, top + HMT + RT, a, b) for a, b in lines])
        t_resist("t_res_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 [box(WX0, WX1, top + HMT, top + HMT + RT, a, b) for a, b in gaps_z])
        T.put(tmp("t_reticle", "Reticle chrome (in the scanner; not to scale)", "chrome", "Patterning",
                  [box(WX0, WX1, RY, RY + 2.0, a, b) for a, b in lines], (0, 2.0, 0)))
        T.snap("expose", "Exposure",
            "The scanner projects the reticle's pattern onto the resist. The reticle is not on "
            "the wafer: it sits in the scanner and is imaged down through its optics; it is drawn "
            "above the wafer here only to show which areas its chrome keeps dark. With the "
            "positive-tone resist of this example, the exposed resist between the future stack "
            "lines becomes soluble; the resist over the lines stays as it was. Light does not etch "
            "anything [R16].", view="tile", of="pattern", match="concept",
            subs=["Positive-tone resist is chosen for the example; a negative-tone resist reverses "
                  "which areas remain",
                  "Exposure is simplified: no optics, proximity, dose or overlay effects"])
        T.drop("t_reticle", "t_res_x")
        T.snap("develop", "Development",
            "The developer dissolves the exposed resist, leaving resist stripes over the future "
            "stack lines and the hard mask bare in between [R16].", view="tilecut", of="pattern",
            match="concept")
        T.drop("t_hm")
        T.put(tmp("t_hm", "Stack hard mask (patterned)", "si3n4", "Patterning",
                  [box(WX0, WX1, top, top + HMT, a, b) for a, b in lines], (0, 1.3, 0)))
        T.snap("hmetch", "Hard-mask etch",
            "A directional etch transfers the resist pattern into the hard mask where the resist "
            "is open. The resist image has become a hard-mask image [R16].", view="tilecut",
            of="pattern", match="intermediate", figs=["5A/B"])
        T.drop("t_res")
        T.snap("strip", "Resist strip",
            "The remaining resist is stripped; the hard mask alone now defines the stack lines.",
            view="tilecut", of="pattern", match="intermediate", figs=["5A/B"])
        t_multilayer(lines=True)
        T.drop("t_pts_n", "t_pts_p")
        for zc, k in LINES:
            T.put(tmp(f"t_pts_{k}", ("p-type punch-through stopper · nFET sub-fin" if k == "n"
                                     else "n-type punch-through stopper · pFET sub-fin"),
                      "pts" if k == "n" else "pts_n", GS, [box(SX0, SX1, ypts, 0, zc - hz, zc + hz)], (0, -1.0, 0)))
        T.snap("stacketch", "Stack etch",
            "A directional etch cuts the open areas through the multilayer and into the substrate, "
            "leaving narrow stacks on short sub-fins, each still capped by the hard mask. Silicon "
            "and SiGe are etched alike here; the hard mask protects the lines [R13].",
            view="tilecut", of="pattern", match="intermediate", figs=["5A/B"])
        T.put(tmp("t_sti", "STI oxide (filled and polished)", "sio2", GS,
                  subtract((SX0, SX1, ypts, top + HMT, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stifill", "STI fill and CMP",
            "Oxide fills the trenches, overfilled and then polished flat (CMP), stopping on the hard "
            "mask.", view="tilecut", of="pattern", match="intermediate", figs=["5A/B"])
        T.drop("t_sti", "t_hm")
        T.put(tmp("t_sti", "STI oxide", "sio2", GS,
                  subtract((SX0, SX1, ypts, 0, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stirecess", "STI recess and hard-mask removal",
            "The oxide is recessed to the bottom of the high-Ge base layer, which leaves that layer's "
            "sidewalls open, and the hard mask is removed. The oxide isolates neighbouring stacks "
            "sideways: shallow trench isolation [R13]. Next, the view returns to the selected site.",
            view="tile", of="pattern", match="context", figs=["5A/B"],
            subs=["The hard mask is removed here for clarity; flows differ on when it goes"])

    def tile_dummy():
        """Dummy-gate patterning across both stack lines (the core step 'dummy')."""
        for zc, k in LINES:
            T.put(tmp(f"t_dox_{k}", "Dummy-gate oxide (grown on the stack)", "sio2", "Dummy gate",
                      subtract((WX0, WX1, 0, top + TOX, zc - hz - TOX, zc + hz + TOX), T.boxes()), (0, .6, 0)))
        T.put(tmp("t_dsi", "Dummy gate Si (as deposited)", "poly", "Dummy gate",
                  subtract((WX0, WX1, 0, ymo, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
        T.put(tmp("t_dhm", "Gate hard mask (blanket)", "si3n4", "Dummy gate",
                  [box(WX0, WX1, ymo, ycap, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("dummydep", "Dummy-gate stack deposition",
            "A thin oxide grows on the exposed Si and SiGe of both stack lines, then silicon is "
            "deposited over everything and planarised, and a gate hard mask goes on top.",
            view="tile", of="dummy", match="intermediate", figs=["6A/B"],
            subs=["The patent suggests amorphous Si; the model's dummy Si is illustrative"])
        T.drop("t_dsi", "t_dhm", "t_dox_n", "t_dox_p")
        for g, xg in enumerate(GATES):
            for zc, k in LINES:
                T.put(tmp(f"t_dox_{k}{g}", "Dummy-gate oxide", "sio2", "Dummy gate",
                          subtract((xg - XG, xg + XG, 0, top + TOX, zc - hz - TOX, zc + hz + TOX), T.boxes()), (0, .6, 0)))
        for g, xg in enumerate(GATES):
            T.put(tmp(f"t_dummy{g}", f"Dummy gate {g + 1} · Si", "poly", "Dummy gate",
                      subtract((xg - XG, xg + XG, 0, ymo, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
            T.put(tmp(f"t_ghm{g}", f"Gate hard mask {g + 1}", "si3n4", "Dummy gate",
                      [box(xg - XG, xg + XG, ymo, ycap, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("gatepat", "Gate patterning",
            "The gate lines are patterned with the same sequence as the stacks (resist, exposure, "
            "development, hard-mask etch), now in the crossing direction, and the dummy stack is "
            "etched down to the STI. Two gate lines cross both stack lines: four sites. On each "
            "line the two sites share the source/drain between their gates. Next, the view returns "
            "to the selected site, which shows its gate only across its own stack.",
            view="tile", of="dummy", match="context", figs=["6A/B"],
            omitted=["The gate layer's own lithography steps (as for the stacks)",
                     "The gate cut between the lines, which the patent makes later (Fig. 17)"])

    def tile_open():
        """Opening the nFET region while the pFET is protected (the core step 'bottom')."""
        win = (WX0, WX1, 0, ycap + 1.5, WZ0, WZ1)
        T.put(tmp("t_liner", "Protective liner", "liner", "Patterning", conformal(T.boxes(), 1.5, win), (0, .8, 0)))
        T.snap("liner", "Protective liner",
            "A thin protective liner is deposited over the whole tile, both regions [R13].",
            view="tile", of="bottom", match="intermediate", figs=["7A/B"],
            subs=["Liner material and thickness are illustrative"])
        liner = T.now["t_liner"]
        T.put(tmp("t_liner", "Protective liner · pFET region", "liner", "Patterning",
                  clip(liner["boxes"], (WX0, WX1, 0, ycap + 1.5, WZ0, ZMID)), (0, .8, 0)))
        t_resist("t_block", "Photoresist block over the pFET region", "resist",
                 subtract((WX0, WX1, 0, ycap + 12.0, WZ0, ZMID), T.boxes()))
        T.snap("mask", "nFET-open mask",
            "A resist block is patterned over the pFET region, and the liner is etched away where the "
            "resist is open: over the nFET region. The pFET line stays sealed; the nFET line's "
            "sidewalls, including its high-Ge base layer's, are exposed [R13].",
            view="tile", of="bottom", match="context", figs=["7A/B"],
            omitted=["The mask's own lithography steps"])
        T.drop("t_ml_base_n")
        T.snap("base", "nFET base-layer removal",
            "A selective etch removes the high-Ge base layer from the nFET line only, working in from "
            "its exposed sides and on under both dummy gates, which hold the stack up over the cavity. "
            "The pFET line, sealed by liner and resist, keeps its base layer [R13].",
            view="tilelow", of="bottom", match="context", figs=["8A/B"],
            subs=["The etch front is not modelled: only the before and after shapes are drawn"])
        T.drop("t_block")
        T.snap("unmask", "Mask strip",
            "The resist block is stripped; the liner stays on the pFET region for now. Next, the view "
            "returns to the selected site, where the cavity is filled.",
            view="tile", of="bottom", match="intermediate", figs=["8A/B"],
            omitted=["What happens to the pFET line next (Figs. 10–11, 15)"])

    # 1
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", "Substrate & isolation",
              [box(sub[0], sub[1], sub[2], 0, -zsub, zsub)], (0, -1.2, 0)))
    F.snap("substrate", "Silicon substrate",
        "A crystalline silicon wafer, cleaned and prepared for epitaxy. Everything above it is "
        "grown, deposited or etched in the steps that follow.",
        match="published", figs=["2A/B"])
    # 2
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", "Substrate & isolation",
              [box(sub[0], sub[1], sub[2], ypts, -zsub, zsub)], (0, -1.2, 0)))
    F.put(tmp("pts0", "p-type punch-through stopper (implanted)", "pts", "Substrate & isolation",
              [box(sub[0], sub[1], ypts, 0, -zsub, zsub)], (0, -1.0, 0)))
    F.snap("pts", "Punch-through-stopper implant",
        "Dopant is implanted just below the surface: p-type under this nFET, to block leakage "
        "through the silicon beneath the future channels. In the route followed here [R13] this "
        "punch-through stopper is used together with the bottom dielectric isolation formed "
        "later; the two are not alternatives. The pFET region beside it (not shown) receives an "
        "n-type stopper. The layer is drawn with an illustrative depth and no edge line: real "
        "profiles are graded, and dose, energy and diffusion are not modelled.",
        match="published", figs=["3A/B"],
        subs=["Stopper depth and a uniform doped region are illustrative"],
        omitted=["The pFET region and its n-type stopper"])
    # 3
    bottom(-XSD, XSD, -zsub, zsub)
    layers(-XSD, XSD, -zsub, zsub)
    F.snap("superlattice", "Si/SiGe multilayer epitaxy",
        "One alternating stack is grown as a single crystal: a high-Ge SiGe base layer, then "
        "lower-Ge SiGe and Si in turn. For this nFET the Si layers become the channels and the "
        "lower-Ge SiGe is removed from the gate region later; the high-Ge base can be etched "
        "selectively against the other SiGe, which the isolation step uses. In the patent the "
        "same stack also makes a SiGe-channel pFET, where different layers survive, so not every "
        "SiGe layer is sacrificial everywhere [R13].",
        match="published", figs=["4A/B"],
        subs=["Layer thicknesses and Ge contents are illustrative, not the patent's examples"],
        omitted=["The pFET's use of the same stack"])
    # 4
    tile_patterning()
    bottom(-XSD, XSD)
    layers(-XSD, XSD)
    F.drop("wafer", "pts0"); F.add("substrate", "pts", "sti")
    same_site(T, F, SITE4, "stack patterning")
    F.snap("pattern", "Stack patterning and STI",
        "A hard mask defines narrow stacks and a directional etch cuts through the multilayer "
        "and into the substrate, leaving a short sub-fin that keeps the implanted stopper. "
        "Trench oxide is deposited, planarised and recessed to the bottom of the high-Ge base "
        "layer, leaving its sidewalls open for its later removal [R13]. The STI isolates "
        "neighbouring devices sideways; it is not the bottom isolation. How the stack pattern is "
        "made depends on the layer, pitch and process: EUV single exposure allows different "
        "sheet widths, and dense arrays can also use spacer-based pitch splitting (SADP/SAQP); a "
        "worked example is planned for this lesson.",
        match="published", figs=["5A/B"],
        subs=["Stack width, pitch and trench depth are illustrative"])
    # 5
    tile_dummy()
    dox = subtract((-XG, XG, 0, top + TOX, -hz - TOX, hz + TOX), F.boxes())
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", "Dummy gate", dox, (0, .6, 0)))
    poly = subtract((-XG, XG, 0, ymo, -hzmo, hzmo), F.boxes())
    F.put(tmp("dummy", "Dummy gate · Si", "poly", "Dummy gate", poly, (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0)))
    same_site(T, F, SITE5, "dummy-gate patterning")
    F.snap("dummy", "Dummy gate stack",
        "A thin sacrificial oxide, a silicon placeholder gate and a hard mask are deposited and "
        "patterned across the stack. The dummy gate fixes where the gate goes and its length; "
        "the real high-κ/metal gate replaces it near the end (replacement metal gate).",
        match="published", figs=["6A/B"],
        subs=["The patent suggests amorphous Si under a nitride/oxide hard mask; this model's "
              "dummy Si and nitride hard mask are illustrative"])
    # 6
    tile_open()
    F.drop("bsige")
    same_site(T, F, SITE5, "nFET opening")
    F.snap("bottom", "nFET opening and base-layer removal",
        "A protective liner and mask cover the pFET region and open the nFET (Fig. 7, not shown "
        "here). Where the nFET stack is not covered by the dummy gate its sidewalls are exposed, "
        "including the high-Ge base layer's, which the STI recess left open. A selective etch "
        "removes that layer, working in from the exposed sides and on underneath the dummy gate, "
        "which holds the stack up over the open cavity. The lower-Ge SiGe layers stay until "
        "channel release [R13].", view="cutb",
        match="published", figs=["7A/B", "8A/B"],
        subs=["The etch front is not modelled: only the before and after shapes are drawn"],
        omitted=["The protective liner and mask over the pFET region (Fig. 7)"])
    # 7
    window = (-XSD, XSD, 0, ycap + TSP, -hzmo, hzmo)
    F.put(tmp("spfilm", "Spacer dielectric (as deposited)", "si3n4", "Spacers",
              film(TSP, window), (0, .5, 0)))
    F.snap("spacerdep", "Conformal spacer deposition",
        "A conformal spacer dielectric is deposited over every exposed surface. It is thicker "
        "than half the cavity's height, so the cavity under the stack closes up: the film that "
        "fills it becomes the bottom dielectric isolation (BDI) [R13], studied for cutting "
        "sub-channel leakage and effective capacitance [R15]. The film is drawn only "
        "within the gate's width, where this model's cell ends.", view="cutb",
        match="published", figs=["9A/B"],
        subs=["The patent's examples for this one film are SiOC, SiCN, SiOCN and SiBCN; nitride is "
              "drawn, for the spacers and the BDI alike"])
    # 8
    F.drop("spfilm"); F.add("bdi")
    for s, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s*XG, s*XSP))
        F.put(tmp(f"spo_{t}", f"Si₃N₄ gate spacer · {t} side", "si3n4", "Spacers",
                  subtract((xa, xb, 0, ycap, -hzmo, hzmo), F.boxes()), (s*1.3, 0, 0)))
    F.snap("spaceretch", "Spacer etch-back",
        "A directional etch removes the film from the top surfaces and, with over-etch, from the "
        "stack sidewalls outside the gate. It stays on the dummy-gate sidewalls, as the outer "
        "spacers, and in the filled cavity, as the BDI under the whole stack: under the gate and "
        "the future source and drain alike.", view="cutb",
        match="intermediate", figs=["9A/B", "12A/B"],
        subs=["A separate etch-back state between the deposition (Fig. 9) and the recess "
              "(Fig. 12) is a teaching reconstruction",
              "Nitride spacers and BDI stand for the patent's single spacer dielectric"])
    # 9
    layers(-XSP, XSP, sheets_final=True)
    F.snap("recess", "nFET source/drain recess",
        "With the pFET protected again, the exposed nFET stack outside the gate and spacers is "
        "etched away, stopping on the BDI, which stays under the future source and drain. The "
        "ends of every Si and SiGe layer are now exposed at the recess walls [R13].",
        match="published", figs=["12A/B"],
        omitted=["The pFET's own recess and epitaxy (Figs. 10–11) and the nFET protective mask"])
    # 10
    for i, (a, b) in enumerate(sige):
        F.put(tmp(f"sige{i+1}", f"SiGe, lower Ge · sacrificial layer {i+1}", "sige", "Superlattice",
                  [box(-XG, XG, a, b, -hz, hz)]))
    F.snap("indent", "SiGe indent",
        "A selective etch recesses the exposed lower-Ge SiGe ends sideways, leaving the Si sheet "
        "ends in place [R13][R14]. The small cavities it opens, under the spacers, set the "
        "inner-spacer geometry; stopping at the gate edge is a schematic target, not a perfect "
        "alignment. This is a partial recess, not the channel release.", view="cutb",
        match="intermediate", figs=["13A/B"])
    # 11
    F.drop("spo_source", "spo_drain"); F.add("spacer_source", "spacer_drain")
    F.snap("inner", "Inner-spacer deposition and etch-back",
        "Dielectric is deposited into the cavities, where it also coats every exposed surface, then "
        "etched back so it stays only in the cavities and the Si sheet ends are exposed again. The "
        "inner spacers, between the sheets, separate the future gate from the source and drain and "
        "reduce the capacitance between them [R1]; the outer spacers are the larger ones on the "
        "dummy-gate sidewalls.", view="cutb",
        match="intermediate", figs=["13A/B"],
        subs=["Inner spacers are drawn in the outer spacers' nitride"])
    # 12
    F.add("epi_source", "epi_drain")
    F.snap("epi", "Source/drain epitaxy and anneal",
        "After a surface clean, doped silicon (Si:P for this nFET) grows from the exposed Si "
        "sheet tips. The BDI below is not a crystal seed, so growth starts at the sheets and "
        "merges into one shared source on one side and one shared drain on the other, joining "
        "the sheet ends [R13]. The activation anneal that follows needs no separate step in this "
        "model, but it does change the device: dopant activation and diffusion shape the "
        "junction profile.",
        match="published", figs=["13A/B"],
        subs=["The anneal is a conventional concept, not a separately described patent state; "
              "no dopant profile, diffusion or stress is calculated"])
    # 13
    ild_around()
    F.snap("ild", "ILD fill and planarisation",
        "Interlayer dielectric is deposited over everything and polished flat (CMP), stopping on "
        "the hard mask. The source and drain are now buried; hide the ILD in Layers to see them.",
        match="intermediate", figs=["14A/B"])
    # 14
    F.drop("hardmask", "dummy", "dox")
    F.snap("pull", "Hard-mask opening and dummy-gate removal",
        "The hard mask is opened, the dummy gate is etched out selectively against the spacers and "
        "ILD, and the sacrificial oxide is cleared. The trench left behind is the replacement-gate "
        "cavity; the Si and lower-Ge SiGe layers are still stacked at its bottom [R13].", view="cut",
        match="published", figs=["14A/B"])
    # 15
    F.drop("sige1", "sige2", "sige3")
    F.snap("release", "nFET channel release",
        "A selective etch removes the lower-Ge SiGe inside the cavity, including under the lowest "
        "sheet, and keeps the Si [R13]. The Si nanosheets stay connected to the source and drain "
        "at their ends, with their gate surfaces now open above, below and beside each sheet. "
        "Etch selectivity, residues, surface roughness and sheets sticking together are real "
        "concerns; both wet and dry etches are used [R1][R14].", view="cut",
        match="published", figs=["16A/B"],
        omitted=["The pFET's channel preparation (Fig. 15)"])
    # 16
    F.add(*[f"{k}{i}" for k in ("il", "hk", "tin") for i in (1, 2, 3)], "mo", "gatecap")
    F.snap("hkmg", "High-κ / metal gate",
        "After a surface clean, a thin interfacial oxide is formed on the released Si by oxidation. "
        "A high-κ dielectric and a work-function layer are then deposited conformally all round "
        "each sheet (for example by ALD), and a gate-fill metal joins them into one gate, with a "
        "cap on top. Reaching every surface between the sheets is the key step [R1].", view="cut",
        match="published", figs=["17A/B"],
        subs=[HKMG_SUB + "; the patent does not verify this combination, its thicknesses or its "
              "work function"],
        omitted=["The patent's separate pFET and nFET work-function treatments, gate cut and "
                 "self-aligned cap"])
    # 17
    F.add("nisi_source", "nisi_drain", "ni_source", "ni_drain", "w_source", "w_drain", "gatew")
    ild_around()
    F.snap("contacts", "Middle-of-line contacts",
        "Contact openings are etched through the ILD, the semiconductor contact interface is formed "
        "(a silicide here) and metal fills the openings, with a contact onto the gate. These are "
        "middle-of-line structures; the routing metal and vias above them (back end of line) are "
        "not modelled [R13].",
        match="published", figs=["18A/B"],
        subs=["The NiSi, Ni and W contact stack is illustrative; the patent says the metal contact "
              "may include a silicide"],
        omitted=["Fig. 19A/B, an alternative shared-gate arrangement, not a later step"])
    # 18
    F.drop("ild")
    F.snap("done", "The finished device",
        "The same model as Device mode, part for part. Hiding the ILD here is a display choice, as "
        "in the Device view; the ILD is not removed in fabrication.",
        match="published", figs=["18A/B"],
        subs=["The ILD is hidden for viewing only"],
        omitted=["The patent's final figures show the pFET beside this nFET"])
    return dev, F.done(), dict(scope=NS_SCOPE, figures=NS_FIGURES, branch=NS_BRANCH,
                               skipped=NS_SKIPPED, refs=["R13", "R1", "R14", "R15", "R16"], match=MATCH,
                               views=dict(cut=CUTAWAY, cutb=INDENT, **TILE_VIEWS))


# ====================================================== SADP / SAQP LESSON ===
class Lesson(Flow):
    """A concept flow with no finished device behind it: every part is its own."""
    def __init__(self, key, name, bounds):
        self.dev = type("Dev", (), dict(key=key, name=name, bounds=bounds, parts=[]))()
        self.final = {}
        self.steps = []
        Stage.__init__(self, self, "field", bounds, grid=2.0)

    def done(self):
        for k, st in enumerate(self.steps, 1):
            st["label"] = str(k)
        return self.steps


PAT_MATCH = {"pattern": "Patterning concept applied to an illustrative layer"}
PAT_SCOPE = ("Spacer-based pitch splitting: a patterning concept applied to an illustrative layer, the Si/SiGe multilayer "
             "that the nanosheet tile patterns into stacks. It shows how the mechanics work, not how "
             "any particular flow patterns its layers: the route the nanosheet lesson follows [R13] "
             "does not establish SADP or SAQP for its stack or gate masks, and EUV single exposure is "
             "another way to print them.")
PAT_FIGURES = ("Concept lesson: no step corresponds to a figure of the patent. Pitches and counts are "
               "ideal and illustrative; real line ends, cuts and edge exclusions change how many lines "
               "survive, and small variations in core width or spacer thickness make alternate spaces "
               "differ (pitch walk) [R20].")
PAT_BRANCH = ("Two modules: SADP splits the core pitch once (P to P/2); SAQP splits it twice (P to P/4), "
              "cutting a second set of cores from the first spacer image [R19][R21].")


def flow_sadp(done):
    """SADP then SAQP on a field of parallel lines, sized so both end at the nanosheet tile's
    stack lines: 30 nm wide at 84 nm pitch, one pair at z = 0 and z = -84 (the tile's frame)."""
    W, P2 = 30.0, 84.0                     # final line width and pitch
    dev_ns = bd.build_ns()
    sheets = [lim(p["boxes"][0]) for p in dev_ns.parts if p["id"].startswith("sheet")]
    ys = [(sh[2], sh[3]) for sh in sheets]; STI = lim(next(p for p in dev_ns.parts if p["id"] == "bdi")["boxes"][0])[3]
    top = ys[-1][1]
    sige = bd.gaps(STI, top, ys)
    WX0, WX1, WZ0, WZ1 = -XSD - 2 * XSD, XSD, -42.0 - 84.0, 42.0      # the nanosheet tile's window
    X0, X1 = WX0 - 50.0, WX1 + 50.0        # the field runs past the tile's window
    SUB = -20.0; HM = 10.0; MAN = 40.0; MAN1 = 80.0; RES = 16.0
    yhm, yman = top, top + HM

    def centres(n):                        # n lines at pitch 84 with one pair at 0 and -84
        return [-42.0 + P2 * (k - (n - 1) / 2) for k in range(n)]

    def field(n):
        c = centres(n)
        return (c[0] - W / 2 - 60, c[-1] + W / 2 + 60)

    def base(L, z0, z1):
        L.put(tmp("f_sub", "Si substrate", "silicon", "Substrate", [box(X0, X1, SUB, 0, z0, z1)], (0, -1.2, 0)))
        L.put(tmp("f_base", "SiGe, high Ge · base layer", "sige", "Target layer", [box(X0, X1, 0, STI, z0, z1)]))
        for i, (a, b) in enumerate(sige):
            L.put(tmp(f"f_sige{i+1}", f"SiGe, lower Ge · layer {i+1}", "sige", "Target layer", [box(X0, X1, a, b, z0, z1)]))
        for i, (a, b) in enumerate(ys):
            L.put(tmp(f"f_si{i+1}", f"Si · layer {i+1}", "silicon", "Target layer", [box(X0, X1, a, b, z0, z1)]))
        L.put(tmp("f_hm", "Hard mask (receives the final pattern)", "si3n4", "Masks", [box(X0, X1, yhm, yman, z0, z1)], (0, 1.2, 0)))

    def etch_target(L, spans, x0=X0, x1=X1):
        """Etch the multilayer (and the hard mask above it) everywhere but under [spans]."""
        for pid in [k for k in list(L.now) if k in ("f_hm", "f_base") or k.startswith(("f_sige", "f_si"))]:
            part = L.now[pid]; b = lim(part["boxes"][0])
            L.put(dict(part, boxes=[[round(float(v), 4) for v in box(x0, x1, b[2], b[3], a, z)] for a, z in spans]))

    def crop_to_tile(L):
        region = (WX0, WX1, SUB, 1e3, WZ0, WZ1)
        for pid in list(L.now):
            cut = clip(L.now[pid]["boxes"], region)
            if cut: L.put(dict(L.now[pid], boxes=[[round(float(v), 4) for v in b] for b in cut]))
            else: L.drop(pid)

    def check_tile(L, what):
        """The map into the tile is checked, not claimed: the same multilayer lines as the
        nanosheet tile's operation 4.7, inside the tile's window."""
        st = next(x for x in done["ns"]["steps"] if x["id"] == "stacketch")
        tile, mine = {}, {}
        for p in st["parts"]:
            if isinstance(p, dict) and p["id"].startswith("t_ml_"): tile.setdefault(p["material"], []).extend(p["boxes"])
        for p in L.now.values():
            if p["id"] == "f_base" or p["id"].startswith(("f_sige", "f_si")): mine.setdefault(p["material"], []).extend(p["boxes"])
        reg = (WX0, WX1, 0, top, WZ0, WZ1)
        if volumes(tile, reg) != volumes(mine, reg):
            sys.exit(f"{what}: the cropped lines differ from the nanosheet tile's\n"
                     f"  tile {volumes(tile, reg)}\n  field {volumes(mine, reg)}")

    # ---------------------------------------------------------------- SADP --
    n = 8
    c = centres(n)
    z0, z1 = field(n)
    TILEB = dict(x=[WX0, WX1], y=[SUB, yman + MAN + RES + 40], z=[WZ0, WZ1])
    L = Lesson("sadp", "Pitch splitting (SADP · SAQP)", dict(x=[X0, X1], y=[SUB, yman + MAN + RES + 40], z=[z0, z1]))
    mand = [(c[2 * i] + W / 2, c[2 * i + 1] - W / 2) for i in range(n // 2)]        # 54 wide, pitch 168
    base(L, z0, z1)
    L.put(tmp("f_man", "Mandrel film", "mandrel", "Masks", [box(X0, X1, yman, yman + MAN, z0, z1)], (0, 1.6, 0)))
    L.snap("sadp_stack", "SADP · Film stack",
        "The layer to be patterned, here the Si/SiGe multilayer the nanosheet stacks are cut from, is "
        "covered by a hard mask that will receive the final pattern, and a mandrel film for the cores. "
        "The materials are illustrative.", view="sadpfield", match="pattern")
    L.put(tmp("f_res", "Photoresist cores", "resist", "Masks", [box(X0, X1, yman + MAN, yman + MAN + RES, a, b) for a, b in mand], (0, 2.0, 0)))
    L.snap("sadp_litho", "SADP · Core lithography",
        f"Lithography prints widely spaced core lines in resist: four here, at pitch P = {2*P2:g} nm "
        "(coat, expose and develop, as in the nanosheet tile's operations 4.2–4.4) [R16][R21].",
        view="sadpfield", match="pattern", subs=["Four cores, their width and pitch are illustrative"])
    L.drop("f_man", "f_res")
    L.put(tmp("f_man", "Mandrels (cores)", "mandrel", "Masks", [box(X0, X1, yman, yman + MAN, a, b) for a, b in mand], (0, 1.6, 0)))
    L.snap("sadp_mandrel", "SADP · Mandrel etch and resist strip",
        "The resist pattern is etched into the mandrel film and the resist is stripped, leaving durable "
        "mandrels: the cores the spacers will form against.", view="sadpcut", match="pattern")
    win = (X0, X1, yman, yman + MAN + W, z0, z1)
    L.put(tmp("f_spfilm", "Spacer film (as deposited)", "patspacer", "Masks", conformal(L.boxes(), W, win), (0, 1.8, 0)))
    L.snap("sadp_dep", "SADP · Conformal spacer deposition",
        f"A spacer film {W:g} nm thick is deposited conformally: over the mandrel tops, down their "
        "sidewalls and across the floor between them. Its thickness will set the final line width.",
        view="sadpcut", match="pattern")
    L.drop("f_spfilm")
    spacers = [(a - W, a) for a, b in mand] + [(b, b + W) for a, b in mand]
    L.put(tmp("f_sp", "Sidewall spacers", "patspacer", "Masks", [box(X0, X1, yman, yman + MAN, a, b) for a, b in sorted(spacers)], (0, 1.8, 0)))
    L.snap("sadp_etch", "SADP · Spacer etch-back",
        "A directional etch removes the film from every horizontal surface, the mandrel tops and the "
        "floor, and leaves it standing on the mandrel sidewalls: two spacers per mandrel.",
        view="sadpcut", match="pattern")
    L.drop("f_man")
    L.snap("sadp_pull", "SADP · Mandrel removal: the spacer image",
        f"The mandrels are removed selectively, leaving only the spacers: eight lines from four cores, "
        f"at about P/2 = {P2:g} nm. This is the doubled-density pattern; the layer below has not been "
        "etched yet [R21].", view="sadpplan", match="pattern",
        subs=["Ideal spacing; in practice alternate spaces can differ (pitch walk)"])
    L.drop("f_hm")
    L.put(tmp("f_hm", "Hard mask (patterned)", "si3n4", "Masks", [box(X0, X1, yhm, yman, a, b) for a, b in sorted(spacers)], (0, 1.2, 0)))
    L.snap("sadp_hm", "SADP · Transfer into the hard mask",
        "With the spacers as the active etch mask, the hard mask is etched where it is exposed. The "
        "spacer image is now a hard-mask image.", view="sadpcut", match="pattern")
    L.drop("f_sp")
    lines = sorted(spacers)
    etch_target(L, lines)
    L.snap("sadp_target", "SADP · Spacer strip and target etch",
        "The spacers are stripped and the hard mask alone carries the pattern into the multilayer: "
        "eight stack lines, each capped by hard mask.", view="sadpfield", match="pattern")
    etch_target(L, lines[1:-1], WX0, WX1)
    L.snap("sadp_cut", "SADP · Cut (block) pattern",
        "A separately printed cut pattern trims the lines to length and removes the two outermost, at "
        "the edge of the pattern. Which lines survive is an integration choice [R19].",
        view="sadpfield", match="pattern", subs=["Which lines are cut is illustrative"])
    crop_to_tile(L)
    L.bounds = TILEB
    L.snap("sadp_tile", "SADP · The nanosheet tile's two lines",
        "Cropped to the nanosheet tile's window, the pair of lines left matches that tile's two stack "
        "lines in width, pitch and layers (checked when the data is built) (compare operation 4.7 of the nanosheet flow, where the etch "
        "also goes on into the substrate). The crop is a view, not a process step.",
        view="fieldtile", match="pattern")
    check_tile(L, "SADP")
    # ---------------------------------------------------------------- SAQP --
    n = 16
    c = centres(n)
    z0, z1 = field(n)
    L.now = {}
    L.bounds = dict(x=[X0, X1], y=[SUB, yman + MAN + MAN1 + RES + 60], z=[z0, z1])
    man2 = [(c[2 * i] + W / 2, c[2 * i + 1] - W / 2) for i in range(n // 2)]         # 54 wide, pitch 168
    T1 = man2[0][1] - man2[0][0]                                                     # first spacer = second core width
    man1 = [(man2[2 * i][1], man2[2 * i + 1][0]) for i in range(n // 4)]              # 114 wide, pitch 336
    y2, y1 = yman, yman + MAN                       # second-core film, then first-core film above it
    base(L, z0, z1)
    L.put(tmp("f_man2", "Second-core film", "mandrel2", "Masks", [box(X0, X1, y2, y2 + MAN, z0, z1)], (0, 1.5, 0)))
    L.put(tmp("f_man1", "First-core film", "mandrel", "Masks", [box(X0, X1, y1, y1 + MAN1, z0, z1)], (0, 1.8, 0)))
    L.snap("saqp_stack", "SAQP · Film stack",
        "SAQP adds a second core layer: from the bottom, the multilayer, the hard mask that will receive "
        "the final pattern, the second-core film, and the first-core film [R19].",
        view="saqpfield", match="pattern", subs=["Layer materials and thicknesses are illustrative"])
    L.put(tmp("f_res", "Photoresist cores", "resist", "Masks",
              [box(X0, X1, y1 + MAN1, y1 + MAN1 + RES, a, b) for a, b in man1], (0, 2.2, 0)))
    L.snap("saqp_litho", "SAQP · Core lithography",
        f"Four widely spaced cores are printed at pitch P = {4*P2:g} nm, twice the SADP example's [R16].",
        view="saqpfield", match="pattern", subs=["Four cores, their width and pitch are illustrative"])
    L.drop("f_man1", "f_res")
    L.put(tmp("f_man1", "First cores", "mandrel", "Masks", [box(X0, X1, y1, y1 + MAN1, a, b) for a, b in man1], (0, 1.8, 0)))
    L.snap("saqp_mandrel", "SAQP · First-core etch and resist strip",
        "The pattern is etched into the first-core film and the resist stripped.", view="saqpcut", match="pattern")
    L.put(tmp("f_spfilm", "First spacer film (as deposited)", "patspacer", "Masks",
              conformal(L.boxes(), T1, (X0, X1, y1, y1 + MAN1 + T1, z0, z1)), (0, 2.0, 0)))
    L.snap("saqp_dep1", "SAQP · First spacer deposition",
        f"A first spacer film, {T1:g} nm thick, coats the first cores. Its thickness sets the width of the "
        "second cores to come.", view="saqpcut", match="pattern")
    L.drop("f_spfilm")
    sp1 = sorted([(a - T1, a) for a, b in man1] + [(b, b + T1) for a, b in man1])
    L.put(tmp("f_sp1", "First spacers", "patspacer", "Masks", [box(X0, X1, y1, y1 + MAN1, a, b) for a, b in sp1], (0, 2.0, 0)))
    L.snap("saqp_etch1", "SAQP · First spacer etch-back",
        "Etch-back leaves the first spacers on the core sidewalls.", view="saqpcut", match="pattern")
    L.drop("f_man1")
    L.snap("saqp_pull1", "SAQP · First-core removal: the first spacer image",
        f"With the first cores removed, eight spacer lines remain at about P/2 = {2*P2:g} nm: the "
        "first-generation image [R20].", view="saqpplan", match="pattern",
        subs=["Ideal spacing; in practice alternate spaces can differ (pitch walk)"])
    L.drop("f_man2")
    L.put(tmp("f_man2", "Second cores", "mandrel2", "Masks", [box(X0, X1, y2, y2 + MAN, a, b) for a, b in sp1], (0, 1.5, 0)))
    L.drop("f_sp1")
    L.snap("saqp_core2", "SAQP · Second cores: the first image transferred",
        "The first spacer image is etched into the second-core film and the first spacers are removed. The "
        "first-generation image has become the second set of cores; it is not etched into the target. This "
        "transfer is one way to make the second cores; others exist [R19].", view="saqpcut", match="pattern")
    L.put(tmp("f_spfilm", "Second spacer film (as deposited)", "patspacer", "Masks",
              conformal(L.boxes(), W, (X0, X1, y2, y2 + MAN + W, z0, z1)), (0, 1.8, 0)))
    L.snap("saqp_dep2", "SAQP · Second spacer deposition",
        f"A second spacer film, {W:g} nm thick, coats the second cores; this thickness sets the final line "
        "width.", view="saqpcut", match="pattern")
    L.drop("f_spfilm")
    sp2 = sorted([(a - W, a) for a, b in sp1] + [(b, b + W) for a, b in sp1])
    L.put(tmp("f_sp2", "Second spacers", "patspacer", "Masks", [box(X0, X1, y2, y2 + MAN, a, b) for a, b in sp2], (0, 1.8, 0)))
    L.snap("saqp_etch2", "SAQP · Second spacer etch-back",
        "Etch-back leaves the second spacers on the second cores' sidewalls.", view="saqpcut", match="pattern")
    L.drop("f_man2")
    L.snap("saqp_pull2", "SAQP · Second-core removal: the final spacer image",
        f"With the second cores removed, sixteen spacer lines remain at about P/4 = {P2:g} nm: four times the "
        "density of the printed cores, from one lithography step [R20].", view="saqpplan", match="pattern",
        subs=["Ideal spacing; in practice the spaces vary, and the variation accumulates over the two "
              "generations (pitch walk)"])
    L.drop("f_hm")
    L.put(tmp("f_hm", "Hard mask (patterned)", "si3n4", "Masks", [box(X0, X1, yhm, yman, a, b) for a, b in sp2], (0, 1.2, 0)))
    L.snap("saqp_hm", "SAQP · Transfer into the hard mask",
        "With the second spacers as the active etch mask, the pattern goes into the hard mask.",
        view="saqpcut", match="pattern")
    L.drop("f_sp2")
    etch_target(L, sp2)
    L.snap("saqp_target", "SAQP · Spacer strip and target etch",
        "The spacers are stripped and the hard mask carries the pattern into the multilayer: sixteen stack "
        "lines.", view="saqpfield", match="pattern")
    etch_target(L, sp2[1:-1], WX0, WX1)
    L.snap("saqp_cut", "SAQP · Cut (block) pattern",
        "A separately printed block pattern trims the lines to length and removes the edge lines. In a real "
        "integration the block pattern also decides which lines become devices; imec's metal-line example "
        "keeps groups of six [R19].", view="saqpfield", match="pattern",
        subs=["Which lines are cut is illustrative"])
    crop_to_tile(L)
    L.bounds = TILEB
    L.snap("saqp_tile", "SAQP · The nanosheet tile's two lines",
        "Cropped to the tile's window, SAQP leaves the same pair of lines as SADP did: the nanosheet tile's "
        "stack lines. Same final pattern, reached with one pitch split (SADP) or two (SAQP), from cores "
        "printed at twice the pitch. The crop is a view, not a process step.",
        view="fieldtile", match="pattern")
    check_tile(L, "SAQP")
    views = {}
    for mod, r in (("sadp", 1.0), ("saqp", 1.6)):
        views[mod + "field"] = dict(n="Line field", s="the whole pattern", az=-0.95, el=0.55, r=1050 * r,
                                    tgt=[-36.5, 60, -42], clip=None, scale="field")
        views[mod + "cut"] = dict(n="Across the lines", s="section, mid-field", az=1.5708, el=0.08, r=800 * r,
                                  tgt=[-36.5, 70, -42], clip=[-36.5, None, None], scale="field")
        views[mod + "plan"] = dict(n="From above", s="count the lines", az=1.5708, el=1.45, r=950 * r,
                                   tgt=[-36.5, 60, -42], clip=None, scale="field")
    views["fieldtile"] = dict(n="The tile's window", s="two lines, as in the nanosheet tile", az=-0.70,
                              el=0.42, r=520, tgt=[-36.5, 45, -42], clip=None, scale="field")
    return L.dev, L.done(), dict(lesson=True, name=L.dev.name, bounds=L.dev.bounds, scope=PAT_SCOPE, figures=PAT_FIGURES, branch=PAT_BRANCH, skipped={},
                                 refs=["R13", "R16", "R19", "R20", "R21"], match=PAT_MATCH, views=views)


FLOWS = {"ns": flow_ns, "sadp": flow_sadp}


def audit(key, dev, flow, refs):
    """docs/PROCESS_AUDIT.md: every state against its source, generated from the data."""
    final = {p["id"]: p for p in dev.parts}
    part = lambda x: final[x] if isinstance(x, str) else x
    md = [f"# Process audit: {dev.name}", "",
          "Generated by `scripts/build_process.py` from `data/process.json`; do not edit by hand.", "",
          flow["scope"], "", flow["branch"], "", "**" + flow["figures"] + "**", "",
          "## Match levels", ""]
    md += [f"- **{v}** (`{k}`)" for k, v in flow["match"].items()]
    lesson = flow.get("lesson", False)
    md += ["", "## States", ""]
    md += ["Every state is a concept operation on an illustrative line field, sized so that the "
           "final lines have the nanosheet tile's stack width (30 nm) and pitch (84 nm). The build "
           "checks that each module's last state, cropped to the tile's window, has the same "
           "multilayer lines as the nanosheet tile's operation 4.7.", ""] if lesson else [
           "Steps numbered n.k are operation substeps leading into core step n; those at tile "
           "scale show a 2 × 2 context of two stack lines (nFET and pFET) crossed by two gate "
           "lines, with the selected nFET site at the single-site model's origin. The build checks "
           "that the tile, cropped to that site, matches the single-site model at steps 4, 5 and 6.", ""]
    md += ["| # | Scale | State | Source figures | Match | What changes | Model choices | Not shown |",
           "|---|---|---|---|---|---|---|---|"]
    prev, prev_scale = {}, None
    for st in flow["steps"]:
        now = {part(x)["id"]: part(x) for x in st["parts"]}
        if prev_scale is not None and st["scale"] != prev_scale:
            chg = "zoom to the selected site" if st["scale"] == "site" else "zoom out to the 2 × 2 tile"
        else:
            added = [now[k]["name"] for k in now if k not in prev]
            gone = [prev[k]["name"] for k in prev if k not in now]
            shaped = [now[k]["name"] for k in now if k in prev and now[k]["boxes"] != prev[k]["boxes"]]
            chg = "; ".join(x for x in ("+ " + ", ".join(added) if added else "",
                                        "− " + ", ".join(gone) if gone else "",
                                        "reshaped: " + ", ".join(shaped) if shaped else "") if x)
        cell = lambda xs: "<br>".join(xs) if xs else "—"
        figs = ", ".join("Fig. " + f for f in st["figs"]) or "—"
        md.append(f"| {st['label']} | {st['scale']} | {st['title']} | {figs} | {flow['match'][st['match']]} "
                  f"| {chg or '—'} | {cell(st['subs'])} | {cell(st['omitted'])} |")
        prev, prev_scale = now, st["scale"]
    if not lesson:
        md += ["", "## Source figures not mapped to a state", ""]
        md += [f"- **Fig. {k}**: {v}" for k, v in flow["skipped"].items()]
    md += ["", "## Not yet verified", ""]
    md += ["- **Pitch values.** P, P/2 and P/4 are ideal; real spacer images show pitch walk, and "
           "the core, spacer and hard-mask materials and thicknesses here are illustrative.",
           "- **Cut and block patterns** are integration-dependent; which lines are removed is "
           "illustrative, and no cut-mask overlay or placement error is modelled.",
           "- **Where this is used.** The lesson applies the patterning concept to the nanosheet "
           "tile's stack lines as an illustrative layer; it does not claim that a given product "
           "patterns that layer by SADP or SAQP.",
           "", "## Sources cited", ""] if lesson else [
           "- **Every figure mapping.** The patent's drawings have not been compared with these views; "
           "orientation, composition and labels may differ from the published artwork.",
           "- Views, cut directions and left/right are the app's own; the patent's section lines "
           "(X1–X1, X2–X2, Y1–Y1, Y2–Y2) are not yet mapped onto the app's axes.",
           "- The lithography operations (resist, exposure, development) are concept-level: no "
           "optics, dose, resist chemistry, overlay or mask count is modelled or claimed.",
           "", "## Sources cited", ""]
    md += [f"- **[{r}]** {refs[r]['title']} — {refs[r]['publisher']}. <{refs[r]['url']}>"
           for r in flow["refs"]]
    return "\n".join(md) + "\n"


def main():
    out = {}
    refs = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "data/references.json")))["sources"]}
    docs = []
    for key, fn in FLOWS.items():
        dev, steps, extra = fn(out)
        out[key] = dict(extra, steps=steps)
        docs.append(audit(key, dev, out[key], refs))
        temp = {p["id"] for s in steps for p in s["parts"] if not isinstance(p, str)}
        print(f"{key:10s} steps={len(steps):2d}  temporary parts={len(temp)}  max solids/voxel=1")
    with open(os.path.join(ROOT, "docs/PROCESS_AUDIT.md"), "w") as f:
        f.write("\n".join(docs))
    blob = json.dumps(dict(flows=out), ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(ROOT, "data/process.json"), "w") as f:
        f.write(blob)
    print(f"process.json {len(blob)//1024} KB")


if __name__ == "__main__":
    main()
