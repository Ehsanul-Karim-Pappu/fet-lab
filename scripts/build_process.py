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
# The stepper's badge: how the state stands against its source, in a word or two.
BADGE = {"published": "Source stage", "context": "Source stage", "source": "Source stage",
         "intermediate": "Reconstruction", "teach": "Teaching", "concept": "Concept",
         "pattern": "Concept"}
BADGE_NOTE = {
    "Source stage": "Source stage: the cited source describes this stage. The 3D view is the app's own "
                    "schematic geometry, not a copy of the source's drawing.",
    "Reconstruction": "Reconstruction: a state between two stages the source describes, reconstructed "
                      "for teaching.",
    "Teaching": "Teaching: a teaching reconstruction with no source figure; where noted, it differs "
                "from the cited source's own route.",
    "Concept": "Concept: a concept-only operation, such as lithography or pitch splitting, not a "
               "published figure."}
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
        self.route = None           # set while snapping one route's operations (see ROUTES)

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

    def snap(self, sid, title, body, view="iso", *, match, figs=(), subs=(), omitted=(), of=None, src=(), deposit=(), bounds=None):
        """[match] says how the state relates to its source (a MATCH key); [figs] are the
        source's figure identifiers; [subs] the model's material or dimension substitutions;
        [omitted] what the source shows at this stage that this view leaves out. [of] makes
        it an operation substep of the core step with that id, which must come next."""
        key = self.flow.dev.key
        if match not in MATCH and match not in PAT_MATCH and match not in FIN_MATCH:
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
        if src: step["src"] = list(src)          # which reference [figs] belong to, if not the flow's one
        if deposit: step["deposit"] = list(deposit)   # films the viewer shows rising, in order
        if self.route: step["route"] = self.route
        if self.scale != "site": step["bounds"] = self.bounds
        elif bounds: step["bounds"] = bounds         # a site step drawing tools above the device
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
        return relabel(self.steps, self.dev.key)


def relabel(steps, key="flow"):
    """Core steps count 1, 2, 3...; the operations leading to core step n are n.1, n.2...,
    counted along each route: an operation shared by every route after a route's own ones
    carries its number in each route ("labels"), the first route's as "label"."""
    if True:
        routes = list(dict.fromkeys(st["route"] for st in steps if st.get("route"))) or [None]
        core, ops = 0, {r: 0 for r in routes}
        for k, st in enumerate(steps):
            if st["level"] == "core":
                core += 1; ops = {r: 0 for r in routes}; st["label"] = str(core)
            else:
                nxt = next((x for x in steps[k + 1:] if x["level"] == "core"), None)
                if nxt is None or nxt["id"] != st["of"]:
                    sys.exit(f"{key}: operation '{st['id']}' must lead into core step '{st['of']}'")
                lab = {}
                for r in routes:
                    if st.get("route") in (None, r):
                        ops[r] += 1; lab[r] = f"{core + 1}.{ops[r]}"
                st["label"] = lab[st.get("route") or routes[0]]
                if not st.get("route") and len(set(lab.values())) > 1: st["labels"] = lab
        return steps


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
             "other figures are left out. The 2 × 2 tile's four sites are context for the "
             "patterning: only the selected nFET is carried to a finished device, and no gate cut "
             "is drawn, so each gate line would still be shared by an nFET and a pFET site.")

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
    tile=dict(n="Tile overview", s="four sites; the selected nFET is followed", az=-0.70, el=0.42, r=660,
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
        x0, x1 = (WX0, WX1) if lines else (SX0, SX1)        # blanket films cover the whole tile
        spans = [("all", WZ0, WZ1, "")] if not lines else \
                [(k, zc - hz, zc + hz, " · " + ("nFET line" if k == "n" else "pFET line (context)")) for zc, k in LINES]
        for k, z0, z1, where in spans:
            T.put(tmp(f"t_ml_base_{k}", "SiGe, high Ge · sacrificial base layer" + where, "sige", GL,
                      [box(x0, x1, 0, STI, z0, z1)], (0, -.6, 0)))
            for i, (a, b) in enumerate(sige):
                T.put(tmp(f"t_ml_sige{i+1}_{k}", f"SiGe, lower Ge · layer {i+1}" + where, "sige", GL,
                          [box(x0, x1, a, b, z0, z1)]))
            for i, (a, b) in enumerate(ys):
                T.put(tmp(f"t_ml_si{i+1}_{k}", f"Si · layer {i+1}" + where, "silicon", GL,
                          [box(x0, x1, a, b, z0, z1)]))

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
                  [box(SX0, SX1, top, top + HMT, WZ0, WZ1)], (0, 1.3, 0)))
        T.snap("hm", "Hard-mask deposition",
            "Zoomed out to a tile of four gate/stack sites: two stack lines will run along the "
            "channel, one for nFETs through the selected site and one for pFETs beside it, each "
            "crossed later by two gate lines. Only the selected nFET site is carried to a finished "
            "device; the other three show the pattern's context. First a hard-mask film is deposited "
            "over the multilayer. The implanted stoppers differ by region: p-type under the nFET line, "
            "n-type under the pFET line [R13].", view="tile", of="pattern",
            match="intermediate", figs=["3A/B", "5A/B"],
            subs=TILE_SUBS + ["Hard-mask material and thickness are illustrative"],
            omitted=["The masks that kept each stopper implant to its own region"], deposit=["t_hm"])
        T.route = "direct"          # the routes part here: how the hard mask gets its lines
        t_resist("t_res", "Photoresist (coated)", "resist", [box(SX0, SX1, top + HMT, top + HMT + RT, WZ0, WZ1)])
        T.snap("coat", "Resist coat",
            "A light-sensitive photoresist is spun on over the hard mask. It will carry the "
            "pattern first; the hard mask then carries it into the stack [R16].", view="tile",
            of="pattern", match="concept", subs=["Resist thickness is illustrative"], deposit=["t_res"])
        T.drop("t_res")
        lines = [(zc - hz, zc + hz) for zc, _ in LINES]
        t_resist("t_res", "Photoresist (unexposed: over the stack lines)", "resist",
                 [box(WX0, WX1, top + HMT, top + HMT + RT, a, b) for a, b in lines])
        t_resist("t_res_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 subtract((SX0, SX1, top + HMT, top + HMT + RT, WZ0, WZ1),
                          [box(WX0, WX1, top + HMT, top + HMT + RT, a, b) for a, b in lines]))
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
        T.route = None
        pitch_routes(F, T, dict(
            what="stack", of="pattern", group=GL, anchor=0.0, drop=[], cut_note="",
            hm_shared=True, layer_x=(SX0, SX1),
            lines="two stack lines", hz=hz, PS=PS, win=(WX0, WX1, WZ0, WZ1), top=top, HMT=HMT, ysub=sub[2],
            layers=[("ml_base", "SiGe, high Ge · sacrificial base layer", "sige", 0, STI, (0, -.6, 0))] +
                   [(f"ml_sige{i+1}", f"SiGe, lower Ge · layer {i+1}", "sige", a, b, (0, 0, 0)) for i, (a, b) in enumerate(sige)] +
                   [(f"ml_si{i+1}", f"Si · layer {i+1}", "silicon", a, b, (0, 0, 0)) for i, (a, b) in enumerate(ys)]))
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
        gl = [(xg - XG, xg + XG) for xg in GATES]
        t_resist("t_gres", "Photoresist (coated)", "resist", [box(WX0, WX1, ycap, ycap + RT, WZ0, WZ1)])
        T.snap("gcoat", "Gate resist coat",
            "Resist is spun on over the gate hard mask, as for the stacks [R16].", view="tile",
            of="dummy", match="concept", deposit=["t_gres"])
        T.drop("t_gres")
        t_resist("t_gres", "Photoresist (unexposed: over the gates)", "resist",
                 [box(a, b, ycap, ycap + RT, WZ0, WZ1) for a, b in gl])
        t_resist("t_gres_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 [box(a, b, ycap, ycap + RT, WZ0, WZ1) for a, b in bd.gaps(WX0, WX1, gl)])
        T.put(tmp("t_greticle", "Reticle chrome (in the scanner; not to scale)", "chrome", "Patterning",
                  [box(a, b, RY, RY + 2.0, WZ0, WZ1) for a, b in gl], (0, 2.0, 0)))
        T.snap("gexpose", "Gate exposure",
            "The gate lines are exposed crossways to the stacks: the reticle's chrome keeps the resist "
            "over each future gate dark, and the rest becomes soluble [R16].", view="tile",
            of="dummy", match="concept", subs=["Exposure is simplified, as for the stacks"])
        T.drop("t_greticle", "t_gres_x", "t_dhm")
        for g, (a, b) in enumerate(gl):
            T.put(tmp(f"t_ghm{g}", f"Gate hard mask {g + 1}", "si3n4", "Dummy gate",
                      [box(a, b, ymo, ycap, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("ghm", "Development and gate hard-mask etch",
            "The developer clears the exposed resist, and a directional etch transfers the resist "
            "lines into the gate hard mask.", view="tile", of="dummy", match="intermediate", figs=["6A/B"])
        T.drop("t_gres", "t_dsi", "t_dox_n", "t_dox_p")
        for g, xg in enumerate(GATES):
            for zc, k in LINES:
                T.put(tmp(f"t_dox_{k}{g}", "Dummy-gate oxide", "sio2", "Dummy gate",
                          subtract((xg - XG, xg + XG, 0, top + TOX, zc - hz - TOX, zc + hz + TOX), T.boxes()), (0, .6, 0)))
        for g, xg in enumerate(GATES):
            T.put(tmp(f"t_dummy{g}", f"Dummy gate {g + 1} · Si", "poly", "Dummy gate",
                      subtract((xg - XG, xg + XG, 0, ymo, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
            T.put(tmp(f"t_ghm{g}", f"Gate hard mask {g + 1}", "si3n4", "Dummy gate",
                      [box(xg - XG, xg + XG, ymo, ycap, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("gatepat", "Dummy-gate etch and resist strip",
            "With the gate hard mask as the etch mask, the dummy stack is etched down to the STI and "
            "the resist is stripped. Two gate lines cross both stack lines: four sites. On each "
            "line the two sites share the source/drain between their gates, and each gate line runs "
            "across an nFET and a pFET site: without the gate cut, not drawn, those two would share "
            "one gate. Only the selected nFET is completed. Next, the view returns to the selected "
            "site, which shows its gate only across its own stack.",
            view="tile", of="dummy", match="context", figs=["6A/B"],
            omitted=["The gate cut between the lines, which the patent makes later (Fig. 17)"])

    def tile_open():
        """Opening the nFET region while the pFET is protected (the core step 'bottom')."""
        win = (WX0, WX1, 0, ycap + 1.5, WZ0, WZ1)
        T.put(tmp("t_liner", "Protective liner", "liner", "Patterning", conformal(T.boxes(), 1.5, win), (0, .8, 0)))
        T.snap("liner", "Protective liner",
            "A thin protective liner is deposited over the whole tile, both regions [R13].",
            view="tile", of="bottom", match="intermediate", figs=["7A/B"],
            subs=["Liner material and thickness are illustrative"])
        liner = T.now["t_liner"]
        t_resist("t_bres", "Photoresist (coated)", "resist",
                 subtract((WX0, WX1, 0, ycap + 12.0, WZ0, WZ1), T.boxes()))
        T.snap("bcoat", "Block-mask resist coat",
            "Resist is spun on over the whole tile, filling in around the gates [R16].",
            view="tile", of="bottom", match="concept", deposit=["t_bres"])
        T.drop("t_bres")
        others = T.boxes()
        t_resist("t_block", "Photoresist block over the pFET region", "resist",
                 subtract((WX0, WX1, 0, ycap + 12.0, WZ0, ZMID), others))
        t_resist("t_bres_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 subtract((WX0, WX1, 0, ycap + 12.0, ZMID, WZ1), others))
        T.put(tmp("t_breticle", "Reticle chrome (in the scanner; not to scale)", "chrome", "Patterning",
                  [box(WX0, WX1, RY, RY + 2.0, WZ0, ZMID)], (0, 2.0, 0)))
        T.snap("bexpose", "Block-mask exposure",
            "The reticle's chrome covers the pFET region: the resist there stays as it was, and over "
            "the nFET region it becomes soluble [R16].", view="tile", of="bottom", match="concept",
            subs=["Exposure is simplified, as for the stacks"])
        T.drop("t_breticle", "t_bres_x")
        T.put(tmp("t_liner", "Protective liner · pFET region", "liner", "Patterning",
                  clip(liner["boxes"], (WX0, WX1, 0, ycap + 1.5, WZ0, ZMID)), (0, .8, 0)))
        T.snap("mask", "nFET-open mask",
            "The developer clears the exposed resist, leaving a block over the pFET region, and the "
            "liner is etched away where the resist is open: over the nFET region. The pFET line stays "
            "sealed; the nFET line's sidewalls, including its high-Ge base layer's, are exposed [R13].",
            view="tile", of="bottom", match="context", figs=["7A/B"])
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
    bottom(sub[0], sub[1], -zsub, zsub)
    layers(sub[0], sub[1], -zsub, zsub)
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
        "made depends on the layer, pitch and process: a direct print (EUV single exposure, for "
        "example) allows different sheet widths [R18], and dense arrays can use spacer-based "
        "pitch splitting instead; the Steps tab's patterning route shows SADP, the default here, "
        "beside SAQP and a direct print.",
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
                               skipped=NS_SKIPPED, refs=["R13", "R1", "R14", "R15", "R16", "R18", "R19", "R20", "R21"],
                               match=dict(MATCH, **PAT_MATCH), routes=ROUTES,
                               route_title="How the stack lines are printed", route_join="the stack etch",
                               views=dict(cut=CUTAWAY, cutb=INDENT, **TILE_VIEWS, **FIELD_VIEWS))


# ================================================= PITCH-SPLITTING ROUTES ===
# How the stack hard mask gets its lines, as a choice of route through operations
# 4.1-4.6: the direct print, or SADP or SAQP on the field of lines around the tile. Every
# route ends with the same hard-mask lines in the tile, so the stack etch that follows is
# the same step whichever route led to it.
PAT_MATCH = {"pattern": "Patterning concept applied to an illustrative layer"}
ROUTES = [
    dict(id="direct", name="Direct print",
         note="One exposure prints the stack lines at their final pitch, EUV for example. A "
              "printed line can differ in width from its neighbours, which the adjustable sheet "
              "widths of nanosheets use [R18]; spacer routes make every line one film thickness "
              "wide."),
    dict(id="sadp", name="SADP", default=True,
         note="Self-aligned double patterning: cores printed at twice the final pitch, then one "
              "spacer pitch split [R21]. Shown by default as a teaching choice; a patterning "
              "concept applied to an illustrative layer: the sources do not say this stack is "
              "patterned this way."),
    dict(id="saqp", name="SAQP",
         note="Self-aligned quadruple patterning: cores at four times the final pitch and two "
              "spacer pitch splits, the first spacer image becoming the second cores [R19][R20]. "
              "A patterning concept applied to an illustrative layer: the sources do not say this "
              "stack is patterned this way."),
]
FIELD_SUB = ("The field around the tile is illustrative: its lines stand for neighbouring devices, "
             "and implants outside the tile are not drawn")
FIELD_VIEWS = {}
for _mod, _r in (("sadp", 1.0), ("saqp", 1.6)):
    FIELD_VIEWS[_mod + "field"] = dict(n="Line field", s="the tile and the lines around it", az=-0.95,
                                       el=0.55, r=1050 * _r, tgt=[-36.5, 60, -42], clip=None, scale="field")
    FIELD_VIEWS[_mod + "cut"] = dict(n="Across the lines", s="section, mid-field", az=1.5708, el=0.08,
                                     r=800 * _r, tgt=[-36.5, 70, -42], clip=[-36.5, None, None], scale="field")
    FIELD_VIEWS[_mod + "plan"] = dict(n="From above", s="count the lines", az=1.5708, el=1.45,
                                      r=950 * _r, tgt=[-36.5, 60, -42], clip=None, scale="field")


def pitch_routes(F, T, g):
    """SADP and SAQP as routes to the direct print's hard-mask lines, built on a field of
    lines around the tile: the tile's own parts, plus the substrate and multilayer carrying
    on beyond it. Each ends back in the tile with the direct route's state after its resist
    strip, which the build checks the spacer image reproduces inside the tile's window."""
    W, P2 = 2 * g["hz"], g["PS"]                     # final line width and pitch
    w, of = g["what"], g["of"]                       # "stack" or "fin"; the core step they lead into
    WX0, WX1, WZ0, WZ1 = g["win"]
    X0, X1 = WX0 - 50.0, WX1 + 50.0                  # the field runs past the tile's window
    top, HMT, ysub = g["top"], g["HMT"], g["ysub"]
    MAN, MAN1, RES = g.get("films", (40.0, 80.0, 16.0))    # core films and resist: illustrative
    yman = top + HMT
    GS, GL, GP = "Substrate & isolation", g["group"], "Patterning"
    strip = dict(T.now)                              # the direct route after its resist strip
    tile_parts = [p for p in strip.values() if p["id"] != "t_hm"]
    tile_hm = strip["t_hm"]

    def centres(n):                                  # n lines at the final pitch, one at the anchor
        return [g["anchor"] + P2 * (k - n // 2) for k in range(n)]

    def cut(spans):
        """The cut pattern: the lines at the edge of the array go, and any the tile does not
        use (the dummy fin between the nFET and pFET sites, say)."""
        return [(a, b) for a, b in spans[1:-1] if not any(a < d < b for d in g["drop"])]

    def field(n):
        c = centres(n)
        return c[0] - W / 2 - 60, c[-1] + W / 2 + 60

    def hm(S, spans, name, x0=X0, x1=X1):
        S.put(tmp("t_hm", name, "si3n4", GP, [box(x0, x1, top, top + HMT, a, b) for a, b in spans], (0, 1.3, 0)))

    def base(S, z0, z1):
        for p in tile_parts: S.put(p)
        S.put(tmp("f_sub", "Si substrate · beyond the tile", "silicon", GS,
                  subtract((X0, X1, ysub, 0, z0, z1), [b for p in tile_parts if p["group"] == GS for b in p["boxes"]]),
                  (0, -1.2, 0)))
        lx0, lx1 = g.get("layer_x", (WX0, WX1))        # the tile's own layers span this in x
        win = [box(lx0, lx1, 0, top, WZ0, WZ1)]
        for pid, name, mat, a, b, ex in g["layers"]:
            S.put(tmp("f_" + pid, name + " · beyond the tile", mat, GL, subtract((X0, X1, a, b, z0, z1), win), ex))
        hm(S, [(z0, z1)], f"{w.capitalize()} hard mask (blanket)")

    def litho(S, mode, ytop, cores, z0, z1, ex, text, subs):
        """Core lithography as the direct route does it: coat, then an exposure with the
        reticle drawn above the wafer; the development step follows."""
        RYF = ytop + RES + 30.0                          # reticle height (not to scale)
        S.put(tmp("f_res", "Photoresist (coated)", "resist", GP, [box(X0, X1, ytop, ytop + RES, z0, z1)], ex))
        S.snap(f"{mode}_coat", "Core resist coat", "Photoresist is spun on over the core film [R16].",
               view=f"{mode}field", of=of, match="pattern", deposit=["f_res"])
        S.drop("f_res")
        S.put(tmp("f_res", "Photoresist (unexposed: over the cores)", "resist", GP,
                  [box(X0, X1, ytop, ytop + RES, a, b) for a, b in cores], ex))
        S.put(tmp("f_res_x", "Photoresist (exposed: made soluble)", "resist_exp", GP,
                  [box(X0, X1, ytop, ytop + RES, a, b) for a, b in bd.gaps(z0, z1, cores)], ex))
        S.put(tmp("f_ret", "Reticle chrome (in the scanner; not to scale)", "chrome", GP,
                  [box(X0, X1, RYF, RYF + 2.0, a, b) for a, b in cores], (0, 2.6, 0)))
        S.snap(f"{mode}_expose", "Core exposure", text, view=f"{mode}field", of=of, match="pattern",
               subs=["Exposure is simplified: no optics, proximity, dose or overlay effects"] + subs)
        S.drop("f_ret", "f_res_x", "f_res")
        S.put(tmp("f_res", "Photoresist cores", "resist", GP,
                  [box(X0, X1, ytop, ytop + RES, a, b) for a, b in cores], ex))

    def cutmask(S, mode, spans, z0, z1, what):
        """The cut (or block) pattern's own lithography: resist over the hard-mask lines, and a
        second reticle whose chrome keeps the resist over the lines that stay, cut to length."""
        keep = cut(spans)
        regs = []                                      # each kept line, out to half the gap either side
        for a, b in keep:
            i = spans.index((a, b))
            regs.append(((spans[i - 1][1] + a) / 2 if i else a, (b + spans[i + 1][0]) / 2 if i + 1 < len(spans) else b))
        y0, y1 = top, top + HMT + RES
        hmb = S.now["t_hm"]["boxes"]
        keepb = [box(WX0, WX1, y0, y1, a, b) for a, b in regs]
        S.put(tmp("f_cres", "Photoresist (coated)", "resist", GP, subtract((X0, X1, y0, y1, z0, z1), hmb), (0, 2.0, 0)))
        S.snap(f"{mode}_cutcoat", f"Spacer strip and {what}-mask resist",
            "The spacers are stripped, and resist is spun on over the hard-mask lines for a second, "
            f"separately printed pattern: the {what} mask [R16].", view=f"{mode}field", of=of,
            match="pattern", deposit=["f_cres"])
        S.drop("f_cres")
        S.put(tmp("f_cres", "Photoresist (unexposed: over the lines that stay)", "resist", GP,
                  [c for kb in keepb for c in subtract(tuple(lim(kb)), hmb)], (0, 2.0, 0)))
        S.put(tmp("f_cres_x", "Photoresist (exposed: made soluble)", "resist_exp", GP,
                  subtract((X0, X1, y0, y1, z0, z1), hmb + keepb), (0, 2.0, 0)))
        RYC = y1 + 30.0
        S.put(tmp("f_cret", "Reticle chrome (in the scanner; not to scale)", "chrome", GP,
                  [box(WX0, WX1, RYC, RYC + 2.0, a, b) for a, b in regs], (0, 2.6, 0)))
        S.snap(f"{mode}_cutexpose", f"{what.capitalize()}-mask exposure",
            f"A second reticle is imaged onto this resist. Its chrome keeps the resist dark over the "
            f"lines that stay, cut to length; over the line ends and the lines at the edge of the "
            f"array{g['cut_note']} the resist becomes soluble [R16][R19].", view=f"{mode}field",
            of=of, match="pattern", subs=["Exposure is simplified: no optics, proximity, dose or overlay effects"])
        S.drop("f_cret", "f_cres_x", "f_cres")

    def film(S, name, t, y0, y1, z0, z1, ex):
        S.put(tmp("f_spfilm", name, "patspacer", GP, conformal(S.boxes(), t, (X0, X1, y0, y1, z0, z1)), ex))

    def check(S, what):
        """The spacer image, inside the tile's window, is the direct route's hard mask; and
        nothing of the tile itself was touched on the way."""
        reg = (WX0, WX1, top, top + HMT, WZ0, WZ1)
        a = volumes({"si3n4": S.now["t_hm"]["boxes"]}, reg)
        b = volumes({"si3n4": tile_hm["boxes"]}, reg)
        if a != b:
            sys.exit(f"{what}: the hard-mask lines in the tile differ from the direct route's\n  {a}\n  {b}")
        for p in tile_parts:
            if S.now.get(p["id"]) is not p: sys.exit(f"{what}: the tile's part {p['id']} changed")

    def back(mode, what):
        R = Stage(F, "tile", T.bounds)
        R.route, R.now = mode, dict(strip)
        R.snap(f"{mode}_back", "Back to the tile: the same hard-mask lines",
            f"Back at the 2 × 2 tile. Inside its window the hard mask holds the same {g['lines']} "
            f"as the direct route's, at the same width and pitch (checked when the data is built), so "
            f"the flow goes on with the same {w} etch. {what} changed only how the mask was made.",
            view="tilecut", of=of, match="pattern")

    def pull_sub(extra=""):
        return [f"Ideal spacing; in practice alternate spaces can differ (pitch walk){extra} [R20]"]

    # ---------------------------------------------------------------- SADP --
    n = 8
    c = centres(n)
    z0, z1 = field(n)
    S = Stage(F, "field", dict(x=[X0, X1], y=[ysub, yman + MAN + RES + 40], z=[z0, z1]), grid=2.0)
    S.route = "sadp"
    mand = [(c[2 * i] + W / 2, c[2 * i + 1] - W / 2) for i in range(n // 2)]
    base(S, z0, z1)
    S.put(tmp("f_man", "Mandrel film", "mandrel", GP, [box(X0, X1, yman, yman + MAN, z0, z1)], (0, 1.6, 0)))
    S.snap("sadp_films", "Mandrel film" if g.get("hm_shared") else "Hard mask and mandrel film",
        "Zoomed out past the tile to the array of lines around it: the tile sits in the middle, "
        f"and the lines beyond it belong to neighbouring devices. " + (
            f"Over the {w} hard mask goes a mandrel film for the cores. " if g.get("hm_shared") else
            f"The {w} hard mask is deposited as in the direct route, then a mandrel film for the cores. ") +
        "This route changes only how the hard-mask lines are made.", view="sadpfield", of=of, match="pattern",
        subs=[FIELD_SUB, "Mandrel material and thickness are illustrative"], deposit=["f_man"])
    litho(S, "sadp", yman + MAN, mand, z0, z1, (0, 2.0, 0),
        "The scanner images the reticle's pattern onto the resist, as in the direct route, but it "
        f"prints only the cores: the chrome keeps four lines dark at pitch P = {2 * P2:g} nm, twice "
        "the final pitch, which one exposure resolves more easily; the rest becomes soluble "
        "[R16][R21].", ["The core count, width and pitch are illustrative"])
    S.snap("sadp_litho", "Core development",
        "The developer dissolves the exposed resist, leaving four resist cores on the mandrel "
        "film [R16].", view="sadpfield", of=of, match="pattern")
    S.drop("f_man", "f_res")
    S.put(tmp("f_man", "Mandrels (cores)", "mandrel", GP,
              [box(X0, X1, yman, yman + MAN, a, b) for a, b in mand], (0, 1.6, 0)))
    S.snap("sadp_mandrel", "Mandrel etch and resist strip",
        "The resist pattern is etched into the mandrel film and the resist is stripped, leaving "
        "durable mandrels: the cores the spacers will form against.",
        view="sadpcut", of=of, match="pattern")
    film(S, "Patterning spacer film (as deposited)", W, yman, yman + MAN + W, z0, z1, (0, 1.8, 0))
    S.snap("sadp_dep", "Conformal spacer deposition",
        f"A spacer film {W:g} nm thick is deposited conformally: over the mandrel tops, down their "
        "sidewalls and across the floor between them. Its thickness will set the final line "
        "width. This patterning spacer is a temporary mask, not the transistor's gate spacer.",
        view="sadpcut", of=of, match="pattern")
    S.drop("f_spfilm")
    sp = sorted([(a - W, a) for a, b in mand] + [(b, b + W) for a, b in mand])
    S.put(tmp("f_sp", "Patterning spacers", "patspacer", GP,
              [box(X0, X1, yman, yman + MAN, a, b) for a, b in sp], (0, 1.8, 0)))
    S.snap("sadp_etch", "Spacer etch-back",
        "A directional etch removes the film from every horizontal surface, the mandrel tops and "
        "the floor, and leaves it standing on the mandrel sidewalls: two spacers per mandrel.",
        view="sadpcut", of=of, match="pattern")
    S.drop("f_man")
    S.snap("sadp_pull", "Mandrel removal: the spacer image",
        f"The mandrels are removed selectively, leaving only the spacers: eight lines from four "
        f"cores, at about P/2 = {P2:g} nm, the {w}s' pitch [R21].", view="sadpplan", of=of,
        match="pattern", subs=pull_sub())
    hm(S, sp, f"{w.capitalize()} hard mask (patterned)")
    S.snap("sadp_hm", "Transfer into the hard mask",
        "With the spacers as the etch mask, the hard mask is etched where it is exposed. The "
        "spacer image is now a hard-mask image.", view="sadpcut", of=of, match="pattern")
    S.drop("f_sp")
    cutmask(S, "sadp", sp, z0, z1, "cut")
    hm(S, cut(sp), f"{w.capitalize()} hard mask (patterned)", WX0, WX1)
    check(S, "SADP")
    S.snap("sadp_cut", "Cut etch and resist strip",
        "The developer clears the exposed resist, the hard mask left open is etched away and the "
        "resist is stripped: the lines are trimmed to length and the two at the edge of the array "
        "are gone" + g["cut_note"] + ". Which lines a cut removes is an integration choice [R19].",
        view="sadpfield", of=of, match="pattern", subs=["Which lines are cut is illustrative"])
    back("sadp", "SADP")

    # ---------------------------------------------------------------- SAQP --
    n = 16
    c = centres(n)
    z0, z1 = field(n)
    S = Stage(F, "field", dict(x=[X0, X1], y=[ysub, yman + MAN + MAN1 + RES + 60], z=[z0, z1]), grid=2.0)
    S.route = "saqp"
    man2 = [(c[2 * i] + W / 2, c[2 * i + 1] - W / 2) for i in range(n // 2)]     # the second cores
    T1 = man2[0][1] - man2[0][0]                                                  # first spacer = their width
    man1 = [(man2[2 * i][1], man2[2 * i + 1][0]) for i in range(n // 4)]          # the first cores
    y1 = yman + MAN                                                               # first-core film
    base(S, z0, z1)
    S.put(tmp("f_man2", "Second-core film", "mandrel2", GP, [box(X0, X1, yman, y1, z0, z1)], (0, 1.5, 0)))
    S.put(tmp("f_man1", "First-core film", "mandrel", GP, [box(X0, X1, y1, y1 + MAN1, z0, z1)], (0, 1.8, 0)))
    S.snap("saqp_films", "Two core films" if g.get("hm_shared") else "Hard mask and two core films",
        "Zoomed out past the tile to the array of lines around it. SAQP needs a second core "
        f"layer: over the {w} hard mask go a second-core film and then a first-core film [R19]" +
        (", two layers the tile's hard mask did not have." if g.get("hm_shared") else "."),
        view="saqpfield", of=of, match="pattern",
        subs=[FIELD_SUB, "Core materials and thicknesses are illustrative"], deposit=["f_man2", "f_man1"])
    litho(S, "saqp", y1 + MAN1, man1, z0, z1, (0, 2.2, 0),
        "The scanner images the reticle's pattern onto the resist: the chrome keeps four cores "
        f"dark at pitch P = {4 * P2:g} nm, four times the final pitch, and the rest becomes "
        "soluble [R16].", ["The core count, width and pitch are illustrative"])
    S.snap("saqp_litho", "Core development",
        "The developer dissolves the exposed resist, leaving four resist cores on the first-core "
        "film [R16].", view="saqpfield", of=of, match="pattern")
    S.drop("f_man1", "f_res")
    S.put(tmp("f_man1", "First cores", "mandrel", GP, [box(X0, X1, y1, y1 + MAN1, a, b) for a, b in man1], (0, 1.8, 0)))
    S.snap("saqp_core1", "First-core etch and resist strip",
        "The pattern is etched into the first-core film and the resist is stripped.",
        view="saqpcut", of=of, match="pattern")
    film(S, "First patterning spacer film (as deposited)", T1, y1, y1 + MAN1 + T1, z0, z1, (0, 2.0, 0))
    S.snap("saqp_dep1", "First spacer deposition",
        f"A first spacer film, {T1:g} nm thick, coats the first cores. Its thickness sets the "
        "width of the second cores to come.", view="saqpcut", of=of, match="pattern")
    S.drop("f_spfilm")
    sp1 = sorted([(a - T1, a) for a, b in man1] + [(b, b + T1) for a, b in man1])
    S.put(tmp("f_sp1", "First patterning spacers", "patspacer", GP,
              [box(X0, X1, y1, y1 + MAN1, a, b) for a, b in sp1], (0, 2.0, 0)))
    S.snap("saqp_etch1", "First spacer etch-back",
        "Etch-back leaves the first spacers on the core sidewalls.", view="saqpcut", of=of,
        match="pattern")
    S.drop("f_man1")
    S.snap("saqp_pull1", "First-core removal: the first spacer image",
        f"With the first cores removed, eight spacer lines remain at about P/2 = {2 * P2:g} nm: the "
        "first-generation image [R20].", view="saqpplan", of=of, match="pattern", subs=pull_sub())
    S.drop("f_man2", "f_sp1")
    S.put(tmp("f_man2", "Second cores", "mandrel2", GP, [box(X0, X1, yman, y1, a, b) for a, b in sp1], (0, 1.5, 0)))
    S.snap("saqp_core2", "Second cores: the first image transferred",
        "The first spacer image is etched into the second-core film and the first spacers are "
        "removed. The first-generation image has become the second set of cores; it is not etched "
        "into the hard mask. This transfer is one way to make the second cores; others exist [R19].",
        view="saqpcut", of=of, match="pattern")
    film(S, "Second patterning spacer film (as deposited)", W, yman, y1 + W, z0, z1, (0, 1.8, 0))
    S.snap("saqp_dep2", "Second spacer deposition",
        f"A second spacer film, {W:g} nm thick, coats the second cores; this thickness sets the "
        "final line width.", view="saqpcut", of=of, match="pattern")
    S.drop("f_spfilm")
    sp2 = sorted([(a - W, a) for a, b in sp1] + [(b, b + W) for a, b in sp1])
    S.put(tmp("f_sp2", "Second patterning spacers", "patspacer", GP,
              [box(X0, X1, yman, y1, a, b) for a, b in sp2], (0, 1.8, 0)))
    S.snap("saqp_etch2", "Second spacer etch-back",
        "Etch-back leaves the second spacers on the second cores' sidewalls.", view="saqpcut",
        of=of, match="pattern")
    S.drop("f_man2")
    S.snap("saqp_pull2", "Second-core removal: the final spacer image",
        f"With the second cores removed, sixteen spacer lines remain at about P/4 = {P2:g} nm, the "
        f"{w}s' pitch: four times the density of the printed cores, from one exposure [R20].",
        view="saqpplan", of=of, match="pattern",
        subs=pull_sub(", and the variation adds up over the two generations"))
    hm(S, sp2, f"{w.capitalize()} hard mask (patterned)")
    S.snap("saqp_hm", "Transfer into the hard mask",
        "With the second spacers as the etch mask, the pattern goes into the hard mask.",
        view="saqpcut", of=of, match="pattern")
    S.drop("f_sp2")
    cutmask(S, "saqp", sp2, z0, z1, "block")
    hm(S, cut(sp2), f"{w.capitalize()} hard mask (patterned)", WX0, WX1)
    check(S, "SAQP")
    S.snap("saqp_cut", "Block etch and resist strip",
        "The developer clears the exposed resist, the hard mask left open is etched away and the "
        "resist is stripped: the lines are trimmed to length and the edge lines are gone" + g["cut_note"] +
        ". In a real integration the block pattern also decides which lines become devices; imec's "
        "metal-line example keeps groups of six [R19].",
        view="saqpfield", of=of, match="pattern", subs=["Which lines are cut is illustrative"])
    back("saqp", "SAQP")


# ============================================================ LESSON CHIPS ===
# SADP and SAQP on their own chips: each is the nanosheet flow's route of that name, taken
# out of the flow and ending with the stack etch that follows it, so the lesson and the
# route are the same steps and cannot drift apart.
LESSONS = dict(
    sadp=dict(name="SADP · double patterning",
              branch="SADP splits the printed pitch once, P to P/2: every core leaves two spacer "
                     "lines [R21]. The SAQP chip splits it twice."),
    saqp=dict(name="SAQP · quadruple patterning",
              branch="SAQP splits the printed pitch twice, P to P/4: the first spacer image becomes "
                     "a second set of cores, and each of those leaves two spacer lines [R19][R20]. "
                     "The SADP chip splits it once."))


def lesson(mode):
    def build(done):
        ns = done["ns"]
        route = next(r for r in ns["routes"] if r["id"] == mode)
        fork = next(i for i, s in enumerate(ns["steps"]) if s.get("route"))
        shared = [dict(s) for s in ns["steps"][:fork] if s.get("of") == "pattern"]   # the hard mask
        steps = shared + [dict(s) for s in ns["steps"] if s.get("route") == mode]
        steps.append(dict(next(s for s in ns["steps"] if s["id"] == "stacketch")))
        for k, st in enumerate(steps, 1):
            for key in ("of", "route", "labels"): st.pop(key, None)
            st["level"], st["label"] = "core", str(k)
        views = {k: v for k, v in dict(TILE_VIEWS, **FIELD_VIEWS).items()
                 if k in {st["view"] for st in steps}}
        dev = type("Lesson", (), dict(key=mode, name=LESSONS[mode]["name"], parts=[]))
        return dev, steps, dict(
            lesson=True, name=dev.name, bounds=steps[0]["bounds"],
            scope=f"{route['name']} ({'self-aligned double' if mode == 'sadp' else 'self-aligned quadruple'} "
                  f"patterning) on its own: the steps the Nanosheet flow shows when its stack "
                  f"patterning route is set to {route['name']}, from the film stack to the stack etch. "
                  "Where a step says “as in the direct route”, it means that flow's single-exposure "
                  "alternative; the flow itself defaults to SADP. A patterning concept "
                  "applied to an illustrative layer, the nanosheet tile's Si/SiGe multilayer: the "
                  "sources do not say this stack is patterned this way, and a direct print (EUV single "
                  "exposure, for example) is another way to make it [R18].",
            figures="Every step but the last is a patterning concept and corresponds to no figure. "
                    "The last, the stack etch, is the nanosheet flow's own, a teaching reconstruction "
                    "of the patent's Fig. 5A/B [R13], whose drawings were not available for visual "
                    "comparison.",
            branch=LESSONS[mode]["branch"], skipped={},
            refs=["R13", "R16", "R18", "R19", "R20", "R21"],
            match={k: v for k, v in ns["match"].items() if k in {st["match"] for st in steps}},
            views=views)
    return build


# ================================================================ FINFET ===
# The nFET path follows the stages F1 (R24) describes, with each state naming its own
# source: SAQP fin patterning from a research example (R22, F3), the gate spacers as a
# conventional deposition and etch-back (F1's own route deposits them selectively), and
# separately sourced notes on sub-fin isolation (R27) and gate caps (R26).
FIN_MATCH = {"source": "Source-described stage, adapted; artwork not compared",
             "teach": "Teaching reconstruction; no source figure"}
FIN_SCOPE = ("Representative bulk silicon FinFET nFET fabrication, gate last: the stages of one "
             "disclosed route [R24] where it describes them, SAQP fin patterning from a research "
             "example [R22], and other operations from separate sources, each named at its step. "
             "Illustrative materials and dimensions; not a verified foundry recipe.")
FIN_FIGURES = ("Figure numbers follow each source's written description. The drawings were not "
               "available for visual comparison: each view is a source-described stage, adapted, "
               "not a copy of a figure, and its orientation may differ. F1's A, B and C suffixes are "
               "its own section lines (its Fig. 1), not yet mapped onto the app's views.")
FIN_BRANCH = ("The flow follows the nFET. The 2 × 2 tile's four sites are context for the "
              "patterning: only the selected nFET is carried to a finished device. The tile's pFET "
              "region (its n-well and two fins) receives none of its own steps, such as its masked "
              "SiGe:B epitaxy or its work-function metal [R24][R25], and no gate cut is drawn, so "
              "each gate line would still be shared by an nFET and a pFET site.")
FIN_ROUTES = [
    dict(id="direct", name="Direct print",
         note="A hypothetical single immersion (193i) exposure at this model's 27 nm fin pitch, "
              "far below what one such exposure resolves [R22]; shown for comparison, not as a "
              "claim about every lithography option."),
    dict(id="sadp", name="SADP",
         note="Self-aligned double patterning: cores at twice the fin pitch, then one spacer "
              "pitch split [R21]. Whether it suits depends on the lithography, the target "
              "dimensions and the integration."),
    dict(id="saqp", name="SAQP", default=True,
         note="Self-aligned quadruple patterning, as in a published N7 fin-patterning example "
              "(cores at 96 nm pitch, 48 nm after the first split, 24 nm fins) [R22]. This model's "
              "108 → 54 → 27 nm is an illustrative adaptation; the default here."),
]
FIN_CUT = dict(n="Gate cutaway", s="through the gate centre, at an angle",
               az=1.02, el=.34, r=205, tgt=[0, 38, 0], clip=[0, None, None])
FIN_CEXP = dict(n="Contact mask", s="resist and reticle over the site", az=-0.78, el=0.40, r=330,
                tgt=[0, 62, 0], clip=None)
FIN_SD = dict(n="Across the source/drain", s="section through the drain", az=1.5708, el=0.12,
              r=230, tgt=[27, 40, 0], clip=[27, None, None])
FIN_TILE_VIEWS = dict(
    tile=dict(n="Tile overview", s="four sites; the selected nFET is followed", az=-0.70, el=0.42, r=560,
              tgt=[-38, 30, -40.5], clip=None, scale="tile"),
    tileplan=dict(n="Tile from above", s="plan view", az=0.0, el=1.45, r=500,
                  tgt=[-38, 0, -40.5], clip=None, scale="tile"),
    tilecut=dict(n="Across the fins", s="section through the selected gate", az=1.5708, el=0.14,
                 r=400, tgt=[0, 32, -40.5], clip=[0, None, None], scale="tile"),
    tilechan=dict(n="Along an nFET fin", s="section through fin 2", az=-0.62, el=0.30,
                  r=330, tgt=[-38, 35, 13.5], clip=[None, None, 13.5], scale="tile"))
FIN_FIELD_VIEWS = {}
for _mod, _r in (("sadp", 1.0), ("saqp", 1.65)):
    FIN_FIELD_VIEWS[_mod + "field"] = dict(n="Fin field", s="the tile and the fins around it", az=-0.95,
                                           el=0.55, r=640 * _r, tgt=[-38, 45, -40.5], clip=None, scale="field")
    FIN_FIELD_VIEWS[_mod + "cut"] = dict(n="Across the fins", s="section, mid-field", az=1.5708, el=0.08,
                                         r=400 * _r, tgt=[-38, 60, -40.5], clip=[-38, None, None], scale="field")
    FIN_FIELD_VIEWS[_mod + "plan"] = dict(n="From above", s="count the lines", az=1.5708, el=1.45,
                                          r=560 * _r, tgt=[-38, 45, -40.5], clip=None, scale="field")
F1, F2, F3, F4, F6 = "R24", "R25", "R22", "R27", "R26"
SPACER_SUB = ("F1 forms its gate spacers by selective deposition with no etch-back (its Figs. "
              "8–15); this conventional deposition and etch-back is an independent teaching "
              "reconstruction, of the kind F2 describes for gate seal and spacer films [R25]")
SUBFIN_NOTE = ("Leakage under the fin: STI isolates sideways, not beneath the channel. One separately "
               "disclosed option is a punch-through stopper in the sub-fin, doped from an STI liner "
               "and diffused by anneal [R27]; this model does not resolve sub-fin leakage")


def flow_fin(done):
    dev = bd.build_fin()
    F = Flow(dev)
    P = F.final

    def extent(pid):                                   # a part's bounding box, over all its boxes
        bs = [lim(b) for b in P[pid]["boxes"]]
        return [f(v[k] for v in bs) for k, f in enumerate((min, max, min, max, min, max))]
    fins = [extent(f"fin{i}") for i in (1, 2)]
    hw = (fins[0][5] - fins[0][4]) / 2                 # fin half-width: 3
    FP = (fins[1][4] + fins[1][5]) / 2 - (fins[0][4] + fins[0][5]) / 2    # fin pitch: 27
    ZF = [(f[4] + f[5]) / 2 for f in fins]            # -13.5, 13.5
    top = fins[0][3]                                   # 57: the fin top, the original surface
    sub = lim(P["substrate"]["boxes"][0]); zsub = sub[5]
    STI = max(lim(b)[3] for b in P["sti"]["boxes"])    # 12: the STI top, and the recess floor
    XSD = fins[0][1]                                   # 38: the fin ends, the site's S/D edge
    mo = [lim(b) for b in P["mo"]["boxes"]]
    XG = mo[0][1]; ymo = max(b[3] for b in mo)         # 9, 75
    cap = lim(P["gatecap"]["boxes"][0]); ycap, hzmo = cap[3], cap[5]      # 81, 27.5
    XSP = max(lim(b)[1] for b in P["spacer_drain"]["boxes"])              # 16
    ym2 = extent("w_drain")[3]                                            # 95
    TOX, TSP, TCE = 1.0, XSP - XG, 3.0                 # dummy oxide, spacer film, CESL
    HOLES = [b for k in ("nisi_source", "nisi_drain", "ni_source", "ni_drain", "w_source",
                         "w_drain", "gatew") for b in P[k]["boxes"]]      # where the contacts go

    def ild_around(ytop=ycap, holes=()):
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]] + list(holes)
        F.put(tmp("ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, ytop, -zsub, zsub), others), (0, .6, 0)))

    def full_fins():                                   # the fins before the source/drain recess
        for i, z in enumerate(ZF):
            F.put(tmp(f"fin{i+1}_full", f"Si fin {i+1}", "silicon", "Fins",
                      [box(-XSD, XSD, 0, top, z - hw, z + hw)]))

    # ---------------------------------------------------------- the 2 x 2 tile ----
    # Fins on one grid at the fin pitch: the nFET site's two at +-13.5, the pFET site's two
    # three pitches away. The grid line between them is an extra mask line that the spacer
    # routes' cut removes before the fin etch, so no fin is ever etched there.
    PG, PS = 2 * XSD, 3 * FP                  # gate pitch = a site's length; pFET site 81 nm over
    GATES = (0.0, -PG)
    PAIRS = ((0.0, "n"), (-PS, "p"))
    ZMID = -PS / 2                            # the extra line's grid position, between the sites
    WX0, WX1, WZ0, WZ1 = -XSD - PG, XSD, -PS - zsub, zsub
    SX0, SX1 = sub[0] - PG, sub[1]
    HMT, RT, RY = 6.0, 10.0, 120.0            # fin hard mask, resist; reticle height (not to scale)
    T = Stage(F, "tile", dict(x=[SX0, SX1], y=[sub[2], RY + 2.0], z=[WZ0, WZ1]))
    GS, GFN, GP, GD = "Substrate & isolation", "Fins", "Patterning", "Dummy gate"
    KEPT = [zc + z for zc, _ in PAIRS for z in ZF]     # the four fins the tile keeps
    SITE2 = (-XSD, XSD, sub[2], RY + 2.0, -zsub, zsub)
    SITE3 = (-XSD, XSD, sub[2], RY + 2.0, -hzmo, hzmo)
    TILE_SUBS = ["Pitches are illustrative: the gate pitch is one site's length, and the two "
                 "sites' fins sit three fin pitches apart"]
    who = lambda k: "nFET, p-well" if k == "n" else "pFET, n-well · context only"

    def t_resist(pid, name, mat, boxes):
        T.put(tmp(pid, name, mat, GP, boxes, (0, 1.6, 0)))

    def tile_fins():
        """Fin patterning and isolation, operation by operation (the core step 'fins')."""
        T.put(tmp("t_sub_n", "Si substrate · p-well region (nFET)", "silicon", GS,
                  [box(SX0, SX1, sub[2], 0, ZMID, WZ1)], (0, -1.2, 0)))
        T.put(tmp("t_sub_p", "Si substrate · n-well region (pFET, context only)", "silicon", GS,
                  [box(SX0, SX1, sub[2], 0, WZ0, ZMID)], (0, -1.2, 0)))
        T.put(tmp("t_fl", "Si · upper substrate (fins to be)", "silicon", GFN,
                  [box(SX0, SX1, 0, top, WZ0, WZ1)]))
        T.put(tmp("t_hm", "Fin hard mask (blanket)", "si3n4", GP,
                  [box(SX0, SX1, top, top + HMT, WZ0, WZ1)], (0, 1.3, 0)))
        T.snap("hm", "Hard-mask deposition",
            "Zoomed out to a tile of four sites: an nFET pair of fins in a p-well through the "
            "selected site, and a pFET pair in an n-well beside it, each crossed later by two gate "
            "lines. Only the selected nFET is carried to a finished device; the other three are "
            "context. A hard-mask film goes on the bare wafer, whose own silicon will become the "
            "fins. In practice a thin pad oxide usually sits under the nitride; it is a separate "
            "layer, not drawn here [R24].", view="tile", of="fins", match="source", figs=["2A"], src=[F1],
            deposit=["t_hm"],
            subs=TILE_SUBS + ["The wells are named regions only, not doping profiles",
                              "Hard-mask material and thickness are illustrative"],
            omitted=["The pad oxide, and the well implants and anneal"])
        T.route = "direct"          # the routes part here: how the hard mask gets its lines
        t_resist("t_res", "Photoresist (coated)", "resist", [box(SX0, SX1, top + HMT, top + HMT + RT, WZ0, WZ1)])
        T.snap("coat", "Resist coat",
            "A light-sensitive photoresist is spun on over the hard mask [R16].", view="tile",
            of="fins", match="concept", subs=["Resist thickness is illustrative"], deposit=["t_res"])
        T.drop("t_res")
        lines = [(z - hw, z + hw) for z in KEPT]
        t_resist("t_res", "Photoresist (unexposed: over the fins)", "resist",
                 [box(WX0, WX1, top + HMT, top + HMT + RT, a, b) for a, b in lines])
        t_resist("t_res_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 subtract((SX0, SX1, top + HMT, top + HMT + RT, WZ0, WZ1),
                          [box(WX0, WX1, top + HMT, top + HMT + RT, a, b) for a, b in lines]))
        T.put(tmp("t_reticle", "Reticle chrome (in the scanner; not to scale)", "chrome", GP,
                  [box(WX0, WX1, RY, RY + 2.0, a, b) for a, b in lines], (0, 2.0, 0)))
        T.snap("expose", "Exposure",
            "The scanner images the reticle's pattern onto the resist; the reticle is drawn above "
            "the wafer only to show which areas its chrome keeps dark. With a positive-tone resist "
            "the exposed resist between the future fins becomes soluble. This route is a "
            "hypothetical single immersion exposure at a 27 nm fin pitch, far below what one "
            "resolves: it is shown for comparison with the spacer routes [R16][R22].",
            view="tile", of="fins", match="concept",
            subs=["Exposure is simplified: no optics, proximity, dose or overlay effects"])
        T.drop("t_reticle", "t_res_x")
        T.snap("develop", "Development",
            "The developer dissolves the exposed resist, leaving resist lines over the four fins "
            "to be and the hard mask bare in between [R16].", view="tilecut", of="fins", match="concept")
        T.drop("t_hm")
        T.put(tmp("t_hm", "Fin hard mask (patterned)", "si3n4", GP,
                  [box(WX0, WX1, top, top + HMT, a, b) for a, b in lines], (0, 1.3, 0)))
        T.snap("hmetch", "Hard-mask etch",
            "A directional etch transfers the resist lines into the hard mask [R24].", view="tilecut",
            of="fins", match="source", figs=["3A"], src=[F1],
            subs=["F1 describes the mask etch and the silicon trench etch as one stage; they are "
                  "split here"])
        T.drop("t_res")
        T.snap("strip", "Resist strip",
            "The resist is stripped; the hard mask alone now defines the fins.",
            view="tilecut", of="fins", match="teach")
        T.route = None
        pitch_routes(F, T, dict(
            what="fin", of="fins", group=GFN, anchor=ZMID, drop=[ZMID],
            cut_note=", and the extra line between the nFET and pFET fin groups, so no fin is "
                     "ever etched there",
            lines="four fin lines", films=(16.0, 26.0, 8.0), hm_shared=True, layer_x=(SX0, SX1), hz=hw, PS=FP, win=(WX0, WX1, WZ0, WZ1),
            top=top, HMT=HMT, ysub=sub[2],
            layers=[("fl", "Si · upper substrate (fins to be)", "silicon", 0, top, (0, 0, 0))]))
        # The spacer routes' provenance: SAQP for fins is a published research example (F3,
        # its Fig. 1); SADP for these fins is a teaching reconstruction.
        LITHO = ("_coat", "_expose", "_litho", "_cutcoat", "_cutexpose")   # resist steps: concept only
        for st in F.steps:
            r = st.get("route")
            if r in ("sadp", "saqp") and st["id"].endswith(LITHO):
                st["match"] = "concept"
                if st["id"] == "saqp_cutexpose":
                    st["subs"] = st["subs"] + ["The extra mask line removed here is not a fabricated dummy "
                                               "fin: some flows deliberately build dielectric dummy fins [R25]"]
                if st["id"] == "saqp_expose":
                    st["subs"] = st["subs"] + ["F3's example runs 96 → 48 → 24 nm; this model's 108 → 54 → "
                                               "27 nm is an illustrative adaptation [R22]"]
                continue
            if r == "sadp": st["match"] = "teach"
            if r == "saqp":
                if st["id"] in ("saqp_back", "saqp_cut"): st["match"] = "teach"; continue   # F3 shows no block
                st["match"], st["figs"], st["src"] = "source", ["1"], [F3]
                if st["id"] == "saqp_films":
                    st["subs"] = st["subs"] + ["F3 uses carbon first cores, an oxide first spacer and an "
                                               "amorphous-Si second core over a silicon nitride hard mask; "
                                               "the materials here are illustrative"]
                if st["id"] == "saqp_pull2":
                    st["subs"] = st["subs"] + ["F3's example runs 96 → 48 → 24 nm; this model's 108 → 54 → "
                                               "27 nm is an illustrative adaptation"]

        T.drop("t_fl")
        for zc, k in PAIRS:
            for i, z in enumerate(ZF):
                T.put(tmp(f"t_fin_{k}{i+1}", f"Si fin {i+1} · {who(k)}", "silicon", GFN,
                          [box(WX0, WX1, 0, top, zc + z - hw, zc + z + hw)]))
        T.snap("finetch", "Fin etch",
            f"A directional etch cuts {top:g} nm down into the silicon between the hard-mask lines. "
            f"Four fins {2 * hw:g} nm wide remain, each capped by hard mask. They are not "
            "free-standing pieces: each fin is the wafer's own crystal, continuous with the bulk "
            "below [R24].", view="tilecut", of="fins", match="source", figs=["3A"], src=[F1],
            subs=["Fins are drawn with vertical walls; etched fins taper"])
        T.put(tmp("t_sti", "STI oxide (filled and polished)", "sio2", GS,
                  subtract((SX0, SX1, 0, top + HMT, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stifill", "STI fill and CMP",
            "Oxide fills the trenches, overfilled, annealed and polished flat (CMP). In this model "
            "the polish stops on the hard mask; F1 also allows the mask to be removed during the "
            "CMP [R24].", view="tilecut", of="fins", match="source", figs=["4A"], src=[F1],
            subs=["The optional conformal liner under the fill is not drawn"])
        T.drop("t_sti", "t_hm")
        T.put(tmp("t_sti", "STI oxide", "sio2", GS,
                  subtract((SX0, SX1, 0, STI, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stirecess", "STI recess and hard-mask removal",
            f"The oxide is recessed so each fin stands {top - STI:g} nm above it: the exposed height, "
            f"which the gate will wrap, against the {top:g} nm the etch cut. Below the STI top the "
            "same fin continues into the bulk. The oxide isolates neighbouring fins sideways: "
            "shallow trench isolation [R24]. Next, the view returns to the selected site.",
            view="tile", of="fins", match="source", figs=["5A"], src=[F1],
            subs=["Exposed fin height is the model's; it sets the effective width with the fin width"],
            omitted=[SUBFIN_NOTE])

    def tile_dummy():
        """Dummy-gate deposition and patterning across both fin pairs (the core step 'dummy')."""
        for zc, k in PAIRS:
            for i, z in enumerate(ZF):
                T.put(tmp(f"t_dox_{k}{i+1}", "Dummy-gate oxide (grown on the fin)", "sio2", GD,
                          subtract((WX0, WX1, STI, top + TOX, zc + z - hw - TOX, zc + z + hw + TOX), T.boxes()),
                          (0, .6, 0)))
        T.put(tmp("t_dsi", "Dummy gate Si (as deposited)", "poly", GD,
                  subtract((WX0, WX1, STI, ymo, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
        T.put(tmp("t_dhm", "Gate hard mask (blanket)", "si3n4", GD,
                  [box(WX0, WX1, ymo, ycap, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("dummydep", "Dummy-gate stack deposition",
            "A thin sacrificial oxide forms on the exposed fins, then silicon is deposited over "
            "everything and planarised, and a gate hard mask goes on top [R24].", view="tile",
            of="dummy", match="source", figs=["6A", "6B"], src=[F1],
            subs=["Dummy-gate Si (often polysilicon) and its nitride hard mask are illustrative"])
        gl = [(xg - XG, xg + XG) for xg in GATES]
        gaps_x = bd.gaps(WX0, WX1, gl)
        t_resist("t_gres", "Photoresist (coated)", "resist", [box(WX0, WX1, ycap, ycap + RT, WZ0, WZ1)])
        T.snap("gcoat", "Gate resist coat",
            "Resist is spun on over the gate hard mask, as for the fins [R16].", view="tile",
            of="dummy", match="concept", deposit=["t_gres"])
        T.drop("t_gres")
        t_resist("t_gres", "Photoresist (unexposed: over the gates)", "resist",
                 [box(a, b, ycap, ycap + RT, WZ0, WZ1) for a, b in gl])
        t_resist("t_gres_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 [box(a, b, ycap, ycap + RT, WZ0, WZ1) for a, b in gaps_x])
        T.put(tmp("t_greticle", "Reticle chrome (in the scanner; not to scale)", "chrome", GP,
                  [box(a, b, RY, RY + 2.0, WZ0, WZ1) for a, b in gl], (0, 2.0, 0)))
        T.snap("gexpose", "Gate exposure",
            "The gate lines are exposed crossways to the fins: the reticle's chrome keeps the resist "
            "over each future gate dark, and the rest becomes soluble [R16].", view="tile",
            of="dummy", match="concept", subs=["Exposure is simplified, as for the fins"])
        T.drop("t_greticle", "t_gres_x", "t_dhm")
        for g, (a, b) in enumerate(gl):
            T.put(tmp(f"t_ghm{g}", f"Gate hard mask {g + 1}", "si3n4", GD,
                      [box(a, b, ymo, ycap, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("ghm", "Development and gate hard-mask etch",
            "The developer clears the exposed resist, and a directional etch transfers the resist "
            "lines into the gate hard mask.", view="tile", of="dummy", match="teach")
        T.drop("t_gres", "t_dsi", *[f"t_dox_{k}{i+1}" for _, k in PAIRS for i in range(len(ZF))])
        for g, xg in enumerate(GATES):
            for zc, k in PAIRS:
                for i, z in enumerate(ZF):
                    T.put(tmp(f"t_dox_{k}{i+1}_{g}", "Dummy-gate oxide", "sio2", GD,
                              subtract((xg - XG, xg + XG, STI, top + TOX, zc + z - hw - TOX, zc + z + hw + TOX),
                                       T.boxes()), (0, .6, 0)))
        for g, xg in enumerate(GATES):
            T.put(tmp(f"t_dummy{g}", f"Dummy gate {g + 1} · Si", "poly", GD,
                      subtract((xg - XG, xg + XG, STI, ymo, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
        T.snap("gatepat", "Dummy-gate etch and resist strip",
            "With the hard mask as the etch mask, the dummy stack is etched down to the STI and "
            "cleared off the fins between the gates, and the resist is stripped. Two gate lines "
            "cross both fin pairs: four sites, with the source/drain between two gates shared. Left "
            "uncut, each gate line is one gate shared by an nFET and a pFET, as in an inverter; a "
            "gate cut would separate them. Only the selected nFET is completed. Next, the view "
            "returns to the selected site [R24].",
            view="tile", of="dummy", match="source", figs=["7A", "7B", "7C"], src=[F1],
            omitted=["F1's optional lightly doped extension implants, masked by region",
                     "A gate cut between the sites, if the two gates are to be separate"])

    # 1
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", GS,
              [box(sub[0], sub[1], sub[2], top, -zsub, zsub)], (0, -1.2, 0)))
    F.snap("substrate", "Silicon substrate",
        "The flow starts from a bare silicon wafer. In a bulk FinFET the fins are cut from the wafer "
        "itself, so the channel is the same single crystal as the substrate. F1 describes optional "
        "wells here, a p-well for nFETs and an n-well for pFETs [R24].",
        match="source", figs=["2A"], src=[F1],
        omitted=["The wells' doping profiles, which this model does not draw"])
    # 2
    tile_fins()
    F.drop("wafer"); F.add("substrate", "sti"); full_fins()
    same_site(T, F, SITE2, "fin patterning")
    F.snap("fins", "Fin patterning and STI",
        f"Fins are etched into the wafer through a hard mask, the trenches are filled with oxide "
        f"and polished, and the oxide is recessed: each fin stands {top - STI:g} nm above the STI "
        f"of the {top:g} nm the etch cut. How the fin lines are printed matters most here: the Steps "
        "tab's patterning route shows SAQP, as in a published fin example [R22], beside SADP and a "
        "hypothetical direct print [R24].",
        match="source", figs=["5A"], src=[F1],
        subs=["Fin width, height and pitch are the model's illustrative values"],
        omitted=[SUBFIN_NOTE])
    # 3
    tile_dummy()
    dox = []
    for z in ZF:
        dox += subtract((-XG, XG, STI, top + TOX, z - hw - TOX, z + hw + TOX), F.boxes())
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", GD, dox, (0, .6, 0)))
    F.put(tmp("dummy", "Dummy gate · Si", "poly", GD,
              subtract((-XG, XG, STI, ymo, -hzmo, hzmo), F.boxes()), (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", GD,
              [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0)))
    same_site(T, F, SITE3, "dummy-gate patterning")
    F.snap("dummy", "Dummy gate stack",
        "A sacrificial oxide, a silicon placeholder gate and a hard mask cross both fins, over "
        "their tops and down their sides. The dummy gate fixes where the gate goes and its length; "
        "the real high-κ/metal gate replaces it near the end (replacement metal gate, or gate "
        "last) [R24].", view="iso", match="source", figs=["7A", "7B", "7C"], src=[F1],
        subs=["Dummy-gate materials and heights are illustrative"])
    # 4
    window = (-XSD, XSD, STI, ycap + TSP, -hzmo, hzmo)
    F.put(tmp("spfilm", "Gate spacer dielectric (as deposited)", "si3n4", "Spacers",
              conformal(F.boxes(), TSP, window), (0, .5, 0)))
    F.snap("spacerdep", "Conformal spacer deposition",
        f"A dielectric film {TSP:g} nm thick is deposited evenly over everything: the dummy gate's "
        "top and sidewalls, the fins and the STI between them. Its thickness sets the spacer's "
        "width. This gate spacer stays in the device, unlike the temporary spacers of fin "
        "patterning [R25].", view="iso", match="teach",
        subs=[SPACER_SUB, "Low-κ spacer materials (SiOCN, SiBCN) are common; nitride stands in"])
    # 5
    F.drop("spfilm"); F.add("spacer_source", "spacer_drain")
    F.snap("spaceretch", "Spacer etch-back",
        "A directional etch clears the film from every horizontal surface and, with extra etch, "
        "from the fins' sidewalls outside the gate, leaving spacers only on the dummy gate's two "
        "sides [R25].", view="iso", match="teach",
        subs=[SPACER_SUB, "The fin sidewall spacers are drawn fully removed; some flows keep a remnant"])
    # 6
    F.drop("fin1_full", "fin2_full"); F.add("fin1", "fin2")
    F.snap("recess", "Source/drain fin recess",
        "With the dummy gate and its spacers as the mask, the exposed fin ends are etched down to "
        "the STI top. Under the gate and spacers the fin stays whole: that is the channel. The "
        "recess leaves clean crystalline silicon to grow the source/drain from [R24].",
        view="b", match="source", figs=["16A", "16B", "16C"], src=[F1],
        subs=["The recess floor is drawn at the STI top; its depth and shape are illustrative"])
    # 7
    F.add("epi_source", "epi_drain")
    F.snap("epi", "Source/drain epitaxy and anneal",
        "Phosphorus-doped silicon grows epitaxially from the recessed fin's exposed silicon, the "
        "recess floor and the channel's end, not from the STI, and facets outward above it. An "
        "anneal activates the dopant. Each fin's epitaxy stays separate here; F1 also shows a "
        "merged form [R24].", view="sd", match="source", figs=["17A", "17B", "17C"], src=[F1],
        subs=["F1's examples for nFET epitaxy include Si, SiC and SiP; Si:P is drawn",
              "The facets are drawn as two steps"],
        omitted=["F1's merged source/drain alternative (its Fig. 22)",
                 "The mask over the pFET region during this growth, and the pFET's own SiGe:B "
                 "epitaxy with the nFET masked [R25]"])
    # 8
    cesl = conformal(F.boxes(), TCE, (-XSD, XSD, STI, ycap, -zsub, zsub))
    F.put(tmp("cesl", "Contact etch-stop layer (CESL)", "si3n4", "Interlayer dielectric", cesl, (0, .3, 0)))
    ild_around()
    F.snap("ild", "Etch-stop layer, ILD and CMP",
        f"A thin etch-stop film ({TCE:g} nm) lines the source/drain, spacers and STI, an "
        "interlayer dielectric fills around the gate, and CMP polishes both down until the dummy "
        "gate's hard mask is exposed [R24].", view="iso", match="source",
        figs=["18A", "18B", "18C"], src=[F1],
        subs=["The etch-stop film is drawn in nitride; its thickness is illustrative"])
    # 9
    F.drop("hardmask", "dummy", "dox")
    F.snap("pull", "Dummy-gate removal",
        "Only inside the gate: the hard mask is opened and the dummy silicon and its oxide are "
        "etched away, leaving a trench between the spacers with the fins' top and sides bare at its "
        "bottom. Removing the dummy oxide too and growing a fresh interfacial layer is one of the "
        "options F1 describes [R24].", view="cut", match="source", figs=["19A", "19B", "19C"], src=[F1])
    # 10
    F.add("il1", "il2", "hk1", "hk2")
    F.snap("hk", "Interfacial layer and high-κ",
        "A thin interfacial oxide forms on the fin's three faces, then HfO₂ is deposited by atomic "
        "layer deposition. High-κ keeps the gate's capacitance high with less tunnelling than a thin "
        "SiO₂ alone [R7][R24].", view="c", match="source", figs=["20A", "20B", "20C"], src=[F1],
        subs=["The films are drawn only where they wrap the fins; the high-κ also lines the trench "
              "walls in practice"])
    # 11
    F.add("tin1", "tin2", "mo", "gatecap")
    F.snap("metal", "Work-function metal, gate fill and cap",
        "A TiN work-function metal goes on the high-κ [R8]; molybdenum fills the rest of the "
        "trench and is polished, then recessed and capped. The metal wraps three faces of each "
        "fin, not underneath it: the tri-gate [R24].", view="c", match="source",
        figs=["20A", "20B", "20C"], src=[F1],
        subs=["TiN, Mo and a TiN cap are this model's illustrative choice; for self-aligned "
              "contacts a dielectric cap is usual, protecting the gate from a misplaced contact "
              "[R26]", "TiN alone does not set an nFET threshold voltage"],
        omitted=["The pFET's separate work-function metal, applied with the nFET masked"])
    # 12
    ild_around(ym2)
    CRT = 10.0; RYC = ym2 + CRT + 14.0                 # contact resist; reticle height (not to scale)
    foot = [lim(b) for k in ("ni_source", "ni_drain", "gatew") for b in P[k]["boxes"]]   # hole outlines
    CBOUNDS = dict(dev.bounds, y=[dev.bounds["y"][0], RYC + 4.0])     # tall enough for the reticle
    F.put(tmp("c_res", "Photoresist (coated)", "resist", "Interlayer dielectric",
              [box(-XSD, XSD, ym2, ym2 + CRT, -zsub, zsub)], (0, 1.6, 0)))
    F.snap("ccoat", "Second ILD and contact resist",
        "More dielectric goes on top and is polished flat, then resist is spun on for the contact "
        "pattern [R16][R24].", view="cexp", of="openings", match="concept", deposit=["c_res"],
        bounds=CBOUNDS)
    F.drop("c_res")
    holes_r = [box(b[0], b[1], ym2, ym2 + CRT, b[4], b[5]) for b in foot]
    F.put(tmp("c_res", "Photoresist (unexposed)", "resist", "Interlayer dielectric",
              subtract((-XSD, XSD, ym2, ym2 + CRT, -zsub, zsub), holes_r), (0, 1.6, 0)))
    F.put(tmp("c_res_x", "Photoresist (exposed: over the contacts)", "resist_exp", "Interlayer dielectric",
              holes_r, (0, 1.6, 0)))
    F.put(tmp("c_ret", "Reticle chrome (in the scanner; not to scale)", "chrome", "Interlayer dielectric",
              subtract((-XSD, XSD, RYC, RYC + 2.0, -zsub, zsub),
                       [box(b[0], b[1], RYC, RYC + 2.0, b[4], b[5]) for b in foot]), (0, 2.0, 0)))
    F.snap("cexpose", "Contact exposure",
        "This reticle is chrome everywhere except over the contacts, so only the resist above each "
        "future hole is exposed and becomes soluble: one opening over the gate, one over each "
        "source/drain [R16].", view="cexp", of="openings", match="concept", bounds=CBOUNDS,
        subs=["Exposure is simplified: no optics, proximity, dose or overlay effects",
              "One exposure is drawn for all three openings; flows often print gate and source/drain "
              "contacts with separate masks"])
    F.drop("c_ret", "c_res_x")
    ild_around(ym2, HOLES)
    F.put(tmp("cesl", "Contact etch-stop layer (CESL)", "si3n4", "Interlayer dielectric",
              [c for b in cesl for c in subtract(tuple(lim(b)), HOLES)], (0, .3, 0)))
    F.drop("c_res")
    F.snap("openings", "Contact openings",
        "The developer opens the resist over each contact, the holes are etched through the ILD and "
        "the etch-stop film, down to the epitaxy for the source and drain and onto the gate, and the "
        "resist is stripped. The gate and the source/drain never share an opening [R24].",
        view="sd", match="source", figs=["21A", "21B", "21C"], src=[F1])
    # 13
    F.add("nisi_source", "nisi_drain")
    ild_around(ym2, HOLES)
    F.snap("silicide", "Silicide",
        "Nickel reacts with the exposed epitaxy at the bottom of each source/drain hole, forming a "
        "NiSi silicide that lowers the contact resistance; only exposed silicon reacts [R25].",
        view="sd", match="teach", subs=["NiSi is illustrative; F1 does not specify it"])
    # 14
    F.add("ni_source", "ni_drain", "w_source", "w_drain", "gatew")
    ild_around(ym2)
    F.snap("contacts", "Contact fill",
        "Ni and W fill the holes: the source and drain contacts reach the silicide, and the gate "
        "contact lands on the gate through its own opening. The ILD keeps them apart [R24].",
        view="iso", match="source", figs=["21A", "21B", "21C"], src=[F1],
        subs=["The Ni and W contact stack is illustrative; a liner or barrier is not drawn"])
    # 15
    F.drop("ild", "cesl")
    F.snap("done", "The finished device",
        "The finished FinFET, with the ILD and etch-stop film hidden: two fins, each wrapped on "
        "three faces by the high-κ/metal gate, between Si:P source and drain grown from the "
        "recessed fin ends.", view="iso", match="teach",
        subs=["The ILD and etch-stop film are hidden for viewing only"])
    steps = F.done()
    used = {st["match"] for st in steps}
    return dev, steps, dict(
        scope=FIN_SCOPE, figures=FIN_FIGURES, branch=FIN_BRANCH, skipped={},
        audit_tile=(
            "Steps numbered n.k are operation substeps leading into core step n; those at tile "
            "scale show a 2 × 2 context of an nFET pair of fins (p-well) and a pFET pair (n-well, "
            "context only) crossed by two gate lines, with the selected nFET site at the "
            "single-site model's origin. The fins sit on one grid at the fin pitch; the grid line "
            "between the two pairs is an extra mask line the spacer routes cut before the fin "
            "etch. The build checks that the tile, cropped to that site, matches the single-site "
            "model at steps 2 and 3."),
        audit_unverified=[
            "**Artwork.** Figure numbers follow each source's written description; no drawing has "
            "been compared with these views.",
            "**Outstanding visual check: F1's Fig. 1.** It defines the A–A, B–B and C–C lines its "
            "other figures are cut along; their directions have not been verified, so the app's "
            "section planes are named for what they cut and none is labelled A, B or C.",
            "**Gate spacers.** F1 deposits its spacers selectively (Figs. 8–15); the app's "
            "conventional deposition and etch-back is mapped to no F1 figure.",
            "**Model choices.** No F1 figure establishes the 27 nm fin pitch, 6 nm fin width, 45 nm "
            "exposed height, 7 nm spacer, Mo fill, TiN cap or NiSi/Ni/W contacts; the wells are "
            "named regions, and sub-fin leakage is not resolved.",
            "The lithography operations (resist, exposure, development) are concept-level: no "
            "optics, dose, resist chemistry, overlay or mask count is modelled or claimed.",
            "**Patterning routes.** P, P/2 and P/4 are ideal (real spacer images show pitch walk); "
            "core, spacer and film materials and thicknesses are illustrative; which lines a cut "
            "or block pattern removes is integration-dependent, and no overlay or placement error "
            "is modelled. The separate Pitch walk lesson lets the SAQP dimensions vary."],
        refs=["R24", "R25", "R22", "R23", "R27", "R26", "R7", "R8", "R16", "R19", "R20", "R21"],
        match={k: v for k, v in dict(MATCH, **PAT_MATCH, **FIN_MATCH).items() if k in used},
        routes=FIN_ROUTES,
        route_title="How the fins are printed", route_join="the fin etch",
        views=dict(cut=FIN_CUT, sd=FIN_SD, cexp=FIN_CEXP, **FIN_TILE_VIEWS, **FIN_FIELD_VIEWS))


# ============================================================ PITCH WALK ===
# The FinFET's SAQP route with its three dimensions let go: the first-core width and the
# two spacer thicknesses. Every line and space here is built from those three numbers
# the way the route builds them, and every space reported is measured off the built lines,
# so the numbers shown and the 3D model are the same geometry.
PW_P1 = 108.0                    # printed core pitch (illustrative; Baudot et al.'s example uses 96 nm)
PW_BASE = dict(w1=33.0, s1=21.0, s2=6.0)     # the FinFET route's own: 27 nm pitch, 6 nm lines
PW_RANGE = dict(w1=(21.0, 45.0), s1=(15.0, 27.0), s2=(4.0, 9.0))
PW_GMIN = 2.0                    # no space may close below this (the controls stop there)
PW_TYPES = dict(
    a=("inside a second core", "the second core's width, which is the first spacer's thickness"),
    b=("where a first core was", "the first core's width less two second spacers"),
    c=("between first-core spacer pairs", "the printed space less two first and two second spacers"))
PW_CASES = [
    ("ideal", "Ideal", dict(PW_BASE)),
    ("core", "First cores printed wider", dict(PW_BASE, w1=39.0)),
    ("sp1", "First spacer thinner", dict(PW_BASE, s1=17.0)),
    ("sp2", "Second spacer thicker", dict(PW_BASE, s2=8.0)),
]


def pw_geometry(w1, s1, s2, cores=4, P1=PW_P1):
    """The SAQP image from its three dimensions: first cores at pitch P1, the first spacers
    on their sides (which become the second cores), the second spacers on those (the final
    lines). Each final line keeps where it came from, so each space knows its type."""
    cc = [P1 * (i - (cores - 1) / 2) for i in range(cores)]
    core1 = [(c - w1 / 2, c + w1 / 2) for c in cc]
    core2 = []                                     # (span, first core it came from)
    for i, (a, b) in enumerate(core1):
        core2 += [((a - s1, a), i), ((b, b + s1), i)]
    lines = []                                     # (span, second core, first core)
    for j, ((a, b), i) in enumerate(core2):
        lines += [((a - s2, a), j, i), ((b, b + s2), j, i)]
    lines.sort()
    gaps = []
    for (l, j, i), (r, j2, i2) in zip(lines, lines[1:]):
        t = "a" if j == j2 else ("b" if i == i2 else "c")
        gaps.append((t, round(r[0] - l[1], 4)))
    return dict(core1=core1, core2=[s for s, _ in core2], lines=[s for s, _, _ in lines], gaps=gaps)


def pw_check(w1, s1, s2, P1=PW_P1):
    """The limits the controls keep to: every width positive, no two spacers touching."""
    return min(w1, s1, s2, w1 - 2 * s2, P1 - w1 - 2 * s1, P1 - w1 - 2 * s1 - 2 * s2) >= PW_GMIN


def pw_measure(boxes):
    """Spaces measured off built line boxes (their z extents), not from the formula."""
    spans = sorted({(round(b[2] - b[5] / 2, 4), round(b[2] + b[5] / 2, 4)) for b in boxes})
    return [round(b[0] - a[1], 4) for a, b in zip(spans, spans[1:])], spans


def flow_pitchwalk(done):
    X0, X1 = -45.0, 45.0                            # the lines' length (along x)
    YS, YF, HM, Y2, Y1 = -62.0, -40.0, 6.0, 22.0, 48.0     # substrate, fin foot, film tops
    g0 = pw_geometry(**PW_BASE)
    Z0, Z1 = g0["core1"][0][0] - PW_BASE["s1"] - 60.0, g0["core1"][-1][1] + PW_BASE["s1"] + 60.0
    B = dict(x=[X0, X1], y=[YS, Y1 + 10.0], z=[Z0, Z1])
    dev = type("Lesson", (), dict(key="pitchwalk", name="SAQP pitch walk", parts=[], bounds=B))
    F = Flow(dev)
    S = Stage(F, "field", B, grid=1.0)
    GP, GS = "Patterning", "Substrate & isolation"
    # The ideal case must be the FinFET route's own lines: same widths, same spaces.
    fin = done["fin"]
    route = next(s for s in fin["steps"] if s["id"] == "saqp_pull2")
    sp2 = next(p for p in route["parts"] if not isinstance(p, str) and p["id"] == "f_sp2")
    rg, rs = pw_measure(sp2["boxes"])
    ig = [w for _, w in g0["gaps"]]
    iw = sorted({round(b - a, 4) for a, b in g0["lines"]})
    if rg != ig or iw != sorted({round(b - a, 4) for a, b in rs}):
        sys.exit(f"pitch walk: the ideal case is not the FinFET route's SAQP image\n  {rg}\n  {ig}")

    def fmt(x): return f"{x:g}"

    def films(g, stage):
        """Substrate and hard mask, then the cores and spacers of one stage."""
        S.now = {}
        S.put(tmp("pw_sub", "Si substrate (fins to be)", "silicon", GS, [box(X0, X1, YS, 0, Z0, Z1)], (0, -1.2, 0)))
        S.put(tmp("pw_hm", "Fin hard mask (blanket)", "si3n4", GP, [box(X0, X1, 0, HM, Z0, Z1)], (0, 1.0, 0)))
        if stage == 1:
            S.put(tmp("pw_c2f", "Second-core film (a-Si in Baudot et al.)", "mandrel2", GP, [box(X0, X1, HM, Y2, Z0, Z1)], (0, 1.4, 0)))
            S.put(tmp("pw_c1", "First cores (carbon in Baudot et al.)", "mandrel", GP,
                      [box(X0, X1, Y2, Y1, a, b) for a, b in g["core1"]], (0, 1.8, 0)))
            S.put(tmp("pw_sp1", "First spacers (oxide in Baudot et al.)", "patspacer", GP,
                      [box(X0, X1, Y2, Y1, a, b) for a, b in g["core2"]], (0, 2.2, 0)))
        else:
            S.put(tmp("pw_c2", "Second cores (the first image, transferred)", "mandrel2", GP,
                      [box(X0, X1, HM, Y2, a, b) for a, b in g["core2"]], (0, 1.4, 0)))
            S.put(tmp("pw_sp2", "Second spacers (the final image)", "patspacer", GP,
                      [box(X0, X1, HM, Y2, a, b) for a, b in g["lines"]], (0, 1.8, 0)))

    def fins(g):
        S.now = {}
        S.put(tmp("pw_sub", "Si substrate", "silicon", GS, [box(X0, X1, YS, YF, Z0, Z1)], (0, -1.2, 0)))
        S.put(tmp("pw_fins", "Si fins (etched through the hard mask)", "silicon", "Fins",
                  [box(X0, X1, YF, 0, a, b) for a, b in g["lines"]], (0, 0, 0)))
        S.put(tmp("pw_hm", "Fin hard mask (patterned)", "si3n4", GP,
                  [box(X0, X1, 0, HM, a, b) for a, b in g["lines"]], (0, 1.0, 0)))

    def measured(case, p):
        """The spaces as built: measured off the fin boxes just snapped, typed by origin."""
        g = pw_geometry(**p)
        widths, spans = pw_measure(S.now["pw_fins"]["boxes"])
        if widths != [w for _, w in g["gaps"]]:
            sys.exit(f"pitch walk {case}: built spaces differ from the construction")
        by = {}
        for t, w in g["gaps"]: by.setdefault(t, set()).add(w)
        return dict(case=case, **p, lines=[list(s) for s in spans],
                    gaps=[[t, w] for t, w in g["gaps"]], max=max(widths), min=min(widths),
                    walk=round(max(widths) - min(widths), 4),
                    types={t: sorted(v) for t, v in by.items()})

    def say(m):
        t = {k: fmt(v[0]) if len(v) == 1 else "/".join(map(fmt, v)) for k, v in m["types"].items()}
        return (f"Measured off the lines: spaces {PW_TYPES['a'][0]} {t['a']} nm, "
                f"{PW_TYPES['b'][0]} {t['b']} nm, {PW_TYPES['c'][0]} {t['c']} nm. "
                f"Largest {fmt(m['max'])} nm, smallest {fmt(m['min'])} nm: pitch walk = "
                f"{fmt(m['max'])} − {fmt(m['min'])} = {fmt(m['walk'])} nm.")

    SUBS = ["Dimensions are illustrative: Baudot et al.'s example runs 96 → 48 → 24 nm, this lesson 108 → 54 → "
            "27 nm [R22]", "Etch bias, core taper and fin-height effects are described, not simulated"]
    steps = []
    for case, name, p in PW_CASES:
        if not pw_check(**p): sys.exit(f"pitch walk {case}: outside the allowed limits")
        g = pw_geometry(**p)
        ch = {k: p[k] - PW_BASE[k] for k in p if p[k] != PW_BASE[k]}
        what = {"w1": "first-core width", "s1": "first-spacer thickness", "s2": "second-spacer thickness"}
        if case == "ideal":
            films(g, 1)
            S.snap("ideal_1", "Ideal: first cores and first spacers",
                "The FinFET flow's SAQP route, taken on its own. Four first cores are printed at "
                f"P = {fmt(PW_P1)} nm, {fmt(p['w1'])} nm wide, and a first spacer {fmt(p['s1'])} nm "
                "thick forms on each side. The two numbers are chosen so the first spacers sit at an "
                f"even {fmt(PW_P1 / 2)} nm pitch: core width plus spacer thickness is half the printed "
                "pitch. In Baudot et al.'s example the cores are carbon and the first spacer oxide [R22].",
                view="pwcut", match="source", figs=["1"], src=["R22"], subs=SUBS)
            films(g, 2)
            S.snap("ideal_2", "Ideal: second cores and second spacers",
                "The first cores are removed and the first spacer image is transferred into the "
                "second-core film (amorphous Si in Baudot et al.), then that is removed and a second spacer "
                f"{fmt(p['s2'])} nm thick forms on each second core. First spacer plus second spacer is "
                f"a quarter of the printed pitch, {fmt(PW_P1 / 4)} nm, so sixteen lines come out evenly "
                "spaced [R22].", view="pwcut", match="source", figs=["1"], src=["R22"], subs=SUBS)
            fins(g)
            m = measured(case, p)
            S.snap("ideal_fins", "Ideal: sixteen lines, three kinds of space",
                "The second cores go, the second spacers are transferred into the silicon nitride hard "
                "mask and the fins are etched into silicon through it [R22]. Every space between "
                "neighbouring fins has one of three origins: " + "; ".join(
                    f"{PW_TYPES[k][0]} ({PW_TYPES[k][1]})" for k in "abc") + ". Here they are all equal. "
                + say(m), view="pwplan", match="source", figs=["1"], src=["R22"], subs=SUBS)
            F.steps[-1]["measure"] = m
            continue
        (k, d), = ch.items()
        films(g, 1 if k != "s2" else 2)
        S.snap(f"{case}_before", name,
            f"The same route with one dimension off: the {what[k]} is {fmt(p[k])} nm instead of "
            f"{fmt(PW_BASE[k])} nm ({'+' if d > 0 else '−'}{fmt(abs(d))} nm), everything else as in the "
            "ideal case. " + {
                "w1": "A wider core pushes its two spacers apart and narrows the space between "
                      "neighbouring cores' spacers by the same amount.",
                "s1": "A thinner first spacer makes narrower second cores, and widens the space between "
                      "first-core spacer pairs.",
                "s2": "A thicker second spacer makes wider lines, and every space around them shrinks, "
                      "but not all by the same amount."}[k],
            view="pwcut", match="teach", subs=SUBS)
        fins(g)
        m = measured(case, p)
        S.snap(f"{case}_after", f"{name}: the lines",
            "After the rest of the route and the fin etch. " + say(m) + " " + {
                "w1": "The error sits in the first-core lithography, so it shows up as two space "
                      "types trading width; the lines themselves keep their width.",
                "s1": "The first spacer sets the second cores, so its error moves the spaces inside "
                      "and around them.",
                "s2": "The second spacer is the line width, so its error changes the fin width as "
                      "well as the spaces."}[k],
            view="pwcut", match="teach", subs=SUBS)
        F.steps[-1]["measure"] = m
    fins(pw_geometry(**PW_BASE))
    S.snap("transfer", "What this lesson does not simulate",
        "The lines here have vertical walls and every etch copies its mask exactly. In practice a "
        "core with sloped sides (taper) gives spacers that lean, so the spacer's footprint and the "
        "transferred line width depend on where the etch stops; etch bias grows or shrinks every "
        "line; and a wider space etches differently from a narrow one, so spaces of different width "
        "can leave fins of different height. Baudot et al. model pitch walk, core taper and fin-height "
        "variation together [R22]; these are described here, not calculated.",
        view="pwcut", match="teach", subs=SUBS)
    for k, st in enumerate(F.steps, 1):
        st["level"], st["label"] = "core", str(k)
    views = dict(
        pwcut=dict(n="Across the lines", s="section, mid-length", az=1.5708, el=0.08, r=560,
                   tgt=[0, 0, (Z0 + Z1) / 2], clip=[0, None, None], scale="field"),
        pwplan=dict(n="From above", s="plan view of the lines", az=1.5708, el=1.45, r=640,
                    tgt=[0, 0, (Z0 + Z1) / 2], clip=None, scale="field"),
        pw3d=dict(n="Line field", s="the sixteen lines", az=-0.95, el=0.55, r=620,
                  tgt=[0, -10, (Z0 + Z1) / 2], clip=None, scale="field"))
    return dev, F.steps, dict(
        lesson=True, name=dev.name, bounds=B,
        scope="The FinFET flow's SAQP fin patterning with its dimensions let go: how a small error in "
              "the first-core width or either spacer's thickness turns an even array of lines into "
              "one whose spaces alternate (pitch walk). The ideal case is the FinFET route's own "
              "lines, checked when the data is built; the flow itself always uses the ideal case. "
              "Dimensions are illustrative (Baudot et al.'s example is 96 → 48 → 24 nm [R22]). Every space "
              "shown is measured off the built lines; nothing is simulated.",
        figures="The ideal states are adapted from Baudot et al.'s Fig. 1 as its text describes it [R22]; the "
                "drawings were not available for visual comparison. The varied cases are teaching "
                "reconstructions: Baudot et al. study pitch walk but these particular variations are the "
                "app's.",
        branch="A separate lesson: it does not change the FinFET flow, whose SAQP route stays ideal.",
        skipped={}, refs=["R22", "R20"],
        audit_tile="A lesson of its own at line-field scale. The ideal case is checked, when the data is "
                   "built, to leave the same line widths and spaces as the FinFET flow's SAQP route; "
                   "every space in the table below is measured off the built fin boxes.",
        audit_unverified=[
            "**Fig. 1 of Baudot et al.** Its text was read; its drawing has not been compared with these "
            "views. The ideal states are text-verified only.",
            "The varied cases (wider first cores, thinner first spacer, thicker second spacer) and their "
            "sizes are the app's own, not values from the paper.",
            "Core taper, etch bias and fin-height (aspect-ratio) effects are described, not simulated: "
            "every wall is vertical and every transfer exact."],
        match={"source": FIN_MATCH["source"], "teach": FIN_MATCH["teach"]}, views=views,
        pitchwalk=dict(P1=PW_P1, cores=4, base=PW_BASE, range={k: list(v) for k, v in PW_RANGE.items()},
                       gmin=PW_GMIN, types={k: dict(name=v[0], rule=v[1]) for k, v in PW_TYPES.items()},
                       note="Dimensions illustrative. The controls stop before any space closes: a "
                            "space that closed would merge its two lines into one wide line, and "
                            "one that opened past a spacer's thickness would leave a line missing "
                            "from the pattern."))


# ============================================================ pFET BRANCHES ===
# The patent builds a pFET and an nFET from one shared stack [R13]. The nFET flow above is
# left as it is; the pFET is a flow of its own with the same early stages (the tile's
# patterning operations are the nFET flow's own steps, copied), and "both sites" puts the
# two single-site models side by side, one stack pitch apart, joined by their gate line.
# A site selector moves between the three.
PWF = "pwf"                              # the pFET's own work-function metal (a material)
TP_IL, TP_HK, TP_WF = 0.5, 1.0, 1.0     # the pFET's gate films: they must fit the 5 nm Si gaps
NS_P_REC = 4.0                           # how far the pFET's S/D recess goes into the sub-fin


def ns_dims():
    """The nanosheet site's dimensions, read off the finished nFET so nothing can drift."""
    n = bd.build_ns()
    P = {p["id"]: p for p in n.parts}
    sheets = [lim(P[f"sheet{i}"]["boxes"][0]) for i in (1, 2, 3)]
    D = dict(dev=n, P=P, hz=sheets[0][5], ys=[(s[2], s[3]) for s in sheets],
             STI=lim(P["bdi"]["boxes"][0])[3], sub=lim(P["substrate"]["boxes"][0]),
             ypts=lim(P["pts"]["boxes"][0])[2], ysd=lim(P["epi_drain"]["boxes"][0])[3])
    cap = lim(P["gatecap"]["boxes"][0])
    D.update(zsub=D["sub"][5], ymo=cap[2], ycap=cap[3], hzmo=cap[5], top=D["ys"][-1][1])
    D["sige"] = bd.gaps(D["STI"], D["top"], D["ys"])
    return D


def build_ns_p():
    """The nanosheet pFET of the patent's route [R13], in the nFET's frame and dimensions:
    the lower-Ge SiGe layers are its channels, the Si layers and high-Ge base are gone from
    its gate region, there is no bottom dielectric isolation (the n-type stopper is under
    it instead), and its p-type source/drain grows from the SiGe ends and the recessed
    sub-fin."""
    D = ns_dims(); P = D["P"]
    hz, STI, zsub, hzmo, ymo, ycap = D["hz"], D["STI"], D["zsub"], D["hzmo"], D["ymo"], D["ycap"]
    sub, ysd, sige, ys = D["sub"], D["ysd"], D["sige"], D["ys"]
    SUBFIN = -D["ypts"]
    d = bd.Dev("ns_p", "Nanosheet pFET", "GAA · 3 SiGe sheets",
               "The pFET the same stack makes: three lower-Ge SiGe sheets, its own p-type "
               "work-function metal and a SiGe:B source/drain. Illustrative.")
    d.add("substrate", "Si substrate", "silicon", P["substrate"]["boxes"], "Substrate & isolation", [0, -1.2, 0])
    rec = [box(*sorted((s * XSP, s * XSD)), -NS_P_REC, 0, -hz, hz) for s in (-1, 1)]
    d.add("pts_n", "n-type punch-through stopper (sub-fin)", "pts_n",
          subtract((sub[0], sub[1], -SUBFIN, 0, -hz, hz), rec), "Substrate & isolation", [0, -1.0, 0])
    d.add("sti", "STI oxide", "sio2", P["sti"]["boxes"], "Substrate & isolation", [0, -.8, 0])
    for i, (a, b) in enumerate(sige):
        d.add(f"psheet{i+1}", f"SiGe nanosheet {i+1} (lower Ge) · pFET channel", "sige",
              [box(-XSP, XSP, a, b, -hz, hz)], "Channel stack", [0, 0, 0])
    films = []
    for k, (name, mat, t0, t) in enumerate((("SiO₂ interfacial layer", "sio2", 0, TP_IL),
                                           ("HfO₂ high-κ", "highk", TP_IL, TP_HK),
                                           ("p-type work-function metal", PWF, TP_IL + TP_HK, TP_WF))):
        for i, (a, b) in enumerate(sige):
            yc, hy = (a + b) / 2, (b - a) / 2
            bx = bd.ring4(yc, hy + t0, hz + t0, t, XG)
            d.add(f"p{('il', 'hk', 'wf')[k]}{i+1}", f"{name} · sheet {i+1}", mat, bx,
                  "Gate-all-around films", ["radial", yc, 1.0 + 1.1 * k])
            films += bx
        # The same films on the sub-fin's top: the base layer left it open under the gate.
        fl = [box(-XG, XG, t0, t0 + t, -hz, hz)]
        d.add(f"pfloor_{('il', 'hk', 'wf')[k]}", f"{name} · on the sub-fin (bottom of the gate)", mat, fl,
              "Gate-all-around films", [0, -.4, 0])
        films += fl
    sheets = [b for i in range(3) for b in d.parts[3 + i]["boxes"]]
    d.add("mo", "Mo gate fill", "mo", subtract((-XG, XG, 0, ymo, -hzmo, hzmo), sheets + films),
          "Gate electrode", [0, 1.0, 0])
    d.add("gatecap", "TiN gate cap", "tin", P["gatecap"]["boxes"], "Gate electrode", [0, 1.4, 0])
    d.add("gatew", "W gate contact", "tungsten", P["gatew"]["boxes"], "Gate electrode", [0, 1.8, 0])
    for s, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s * XG, s * XSP))
        # Inner spacers where the Si layers and the high-Ge base were indented; the outer
        # spacer above and beside the stack.
        d.add(f"spacer_{t}", f"Si₃N₄ spacer · {t} side", "si3n4",
              subtract((xa, xb, 0, ycap, -hzmo, hzmo), sheets), "Spacers", [s * 1.3, 0, 0])
    for s, T in ((-1, "Source"), (1, "Drain")):
        xa, xb = sorted((s * XSP, s * XSD))
        d.add(f"sib_{T.lower()}", f"{T} epi, first layer (Si:B) · from the recessed sub-fin", "silicon",
              [box(xa, xb, -NS_P_REC, 0, -hz, hz)], "Source / drain", [s * 1.5, -.3, 0])
        d.add(f"epi_{T.lower()}", f"{T} epi (SiGe:B)", "sige", [box(xa, xb, 0, ysd, -hz, hz)],
              "Source / drain", [s * 1.6, 0, 0])
        for k in ("nisi", "ni", "w"):
            q = P[f"{k}_{T.lower()}"]
            d.add(q["id"], q["name"], q["material"], q["boxes"], q["group"], q["explode"])
    d.views = dict(bd.build_ns().views)
    d.views["gaa"] = dict(d.views["gaa"], off=d.views["gaa"]["off"] + ["sib_source"])
    d.finish()
    worst, _ = bd.check(d)
    if worst != 1: sys.exit(f"ns_p: {worst} solids overlap in the finished pFET")
    return d


NS_P_SCOPE = ("Representative silicon-germanium nanosheet pFET fabrication, following the pFET "
              "branch of the same disclosed route as the nFET flow [R13]: the shared Si/SiGe stack, "
              "an n-type punch-through stopper instead of bottom dielectric isolation, lower-Ge SiGe "
              "channels and a boron-doped source/drain. Illustrative materials and dimensions, in the "
              "nFET model's frame. Not a verified foundry recipe.")
NS_P_BRANCH = ("The pFET branch: the same wafer, stack and patterning as the nFET (the tile's "
               "operations are the nFET flow's own), then its own masked operations in the patent's "
               "order. The nFET beside it is left out here; the Both sites view shows the two together, "
               "with the masks that keep each region's steps to itself and the choice between a gate "
               "cut and a shared gate.")
NS_P_SKIPPED = {
    "12A/B": "nFET source/drain recess (nFET branch)",
    "13A/B": "nFET inner spacers and source/drain epitaxy (nFET branch)",
    "16A/B": "nFET channel release (nFET branch)",
    "19A/B": "an alternative shared-gate arrangement to Fig. 18, shown in the Both sites view",
}
# Tile operations whose text names the nFET as the device followed: the pFET flow says so.
NS_P_TILE_TEXT = [
    ("Only the selected nFET site is carried to a finished device; the other three show the "
     "pattern's context.", "In this flow the pFET line is the one followed, at the site beside the "
     "selected nFET; the other sites show the pattern's context."),
    ("Only the selected nFET is completed. Next, the view returns to the selected "
     "site, which shows its gate only across its own stack.", "In this flow the pFET site on the same "
     "gate line is the one followed. Next, the view returns to that site, which shows its gate only "
     "across its own stack."),
    ("Next, the view returns to the selected site, where the cavity is filled.",
     "Next, the view returns to the pFET site, which kept its base layer."),
    ("Next, the view returns to the selected site.", "Next, the view returns to the pFET site."),
]


def flow_ns_p(done):
    D = ns_dims()
    dev = build_ns_p()
    F = Flow(dev)
    hz, STI, zsub, hzmo, ymo, ycap, top = (D[k] for k in ("hz", "STI", "zsub", "hzmo", "ymo", "ycap", "top"))
    sub, sige, ys, ypts = D["sub"], D["sige"], D["ys"], D["ypts"]
    TOX, TSP = 1.0, XSP - XG
    ns = done["ns"]
    GS, GL = "Substrate & isolation", "Superlattice"

    def ops_of(core):
        """The nFET flow's operations leading into its core step [core], as they are."""
        out = []
        for st in ns["steps"]:
            if st.get("of") == core:
                c = json.loads(json.dumps(st))
                for a, b in NS_P_TILE_TEXT: c["body"] = c["body"].replace(a, b)
                if any(isinstance(p, str) for p in c["parts"]): sys.exit(f"ns_p: op {c['id']} uses final parts")
                out.append(c)
        return out

    def layers(si, base=None, sg=None, sheets=False):
        """The pFET stack: [si], [base] and [sg] are the x spans of its Si layers, high-Ge base
        and lower-Ge SiGe layers (None: gone); [sheets] puts the finished SiGe channels in."""
        F.drop_prefix("psg"); F.drop_prefix("psi"); F.drop("pbase", "psheet1", "psheet2", "psheet3")
        if base:
            F.put(tmp("pbase", "SiGe, high Ge · base layer (kept under the pFET)", "sige", GL,
                      [box(base[0], base[1], 0, STI, -hz, hz)], (0, -.6, 0)))
        for i, (a, b) in enumerate(sige):
            if sheets: F.add(f"psheet{i+1}")
            elif sg: F.put(tmp(f"psg{i+1}", f"SiGe, lower Ge · layer {i+1} (pFET channel to be)", "sige", GL,
                               [box(sg[0], sg[1], a, b, -hz, hz)]))
        if si:
            for i, (a, b) in enumerate(ys):
                F.put(tmp(f"psi{i+1}", f"Si · layer {i+1} (removed from the pFET's gate later)", "silicon", GL,
                          [box(si[0], si[1], a, b, -hz, hz)]))

    def ild_around():
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]]
        F.put(tmp("ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, ycap, -zsub, zsub), others), (0, .6, 0)))

    def core(sid, title, body, **kw):
        F.steps.extend(ops_of(sid))
        F.snap(sid, title, body, **kw)

    # 1
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", GS,
              [box(sub[0], sub[1], sub[2], 0, -zsub, zsub)], (0, -1.2, 0)))
    s1 = next(s for s in ns["steps"] if s["id"] == "substrate")
    F.snap("substrate", s1["title"], s1["body"], match="published", figs=["2A/B"])
    # 2
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", GS,
              [box(sub[0], sub[1], sub[2], ypts, -zsub, zsub)], (0, -1.2, 0)))
    F.put(tmp("pts0", "n-type punch-through stopper (implanted)", "pts_n", GS,
              [box(sub[0], sub[1], ypts, 0, -zsub, zsub)], (0, -1.0, 0)))
    F.snap("pts", "Punch-through-stopper implant",
        "Dopant is implanted just below the surface: n-type under this pFET, where the nFET region "
        "receives a p-type stopper; each implant is kept to its own region by a mask (shown in the "
        "Both sites view). For the pFET the stopper is the isolation under the channels: the patent "
        "forms bottom dielectric isolation under the nFET only [R13]. Depth and doping are "
        "illustrative; real profiles are graded.",
        match="published", figs=["3A/B"],
        subs=["Stopper depth and a uniform doped region are illustrative"],
        omitted=["The nFET region and its p-type stopper"])
    # 3
    F.put(tmp("pbase", "SiGe, high Ge · base layer", "sige", GL,
              [box(sub[0], sub[1], 0, STI, -zsub, zsub)], (0, -.6, 0)))
    for i, (a, b) in enumerate(sige):
        F.put(tmp(f"psg{i+1}", f"SiGe, lower Ge · layer {i+1} (pFET channel to be)", "sige", GL,
                  [box(sub[0], sub[1], a, b, -zsub, zsub)]))
    for i, (a, b) in enumerate(ys):
        F.put(tmp(f"psi{i+1}", f"Si · layer {i+1} (removed from the pFET's gate later)", "silicon", GL,
                  [box(sub[0], sub[1], a, b, -zsub, zsub)]))
    F.snap("superlattice", "Si/SiGe multilayer epitaxy",
        "The same stack as the nFET's, grown once for both: a high-Ge SiGe base layer, then "
        "lower-Ge SiGe and Si in turn. For this pFET the roles swap: the lower-Ge SiGe layers "
        "become the channels, and the Si layers and the high-Ge base are removed from its gate "
        "region near the end [R13].",
        match="published", figs=["4A/B"],
        subs=["Layer thicknesses and Ge contents are illustrative, chosen for the nFET model"])
    # 4
    F.drop("wafer", "pts0")
    F.add("substrate", "sti")
    F.put(tmp("pts_sub", "n-type punch-through stopper (sub-fin)", "pts_n", GS,
              [box(sub[0], sub[1], ypts, 0, -hz, hz)], (0, -1.0, 0)))
    layers((-XSD, XSD), (-XSD, XSD), (-XSD, XSD))
    core("pattern", "Stack patterning and STI",
        "Patterned with the nFET's stack in the same operations (the tile, above): a hard mask "
        "defines the stack lines, a directional etch cuts through the multilayer into the "
        "substrate, and trench oxide is filled, planarised and recessed to the bottom of the "
        "high-Ge base layer [R13]. On the pFET line the sub-fin carries the n-type stopper.",
        match="published", figs=["5A/B"],
        subs=["Stack width, pitch and trench depth are illustrative"])
    # 5
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", "Dummy gate",
              subtract((-XG, XG, 0, top + TOX, -hz - TOX, hz + TOX), F.boxes()), (0, .6, 0)))
    F.put(tmp("dummy", "Dummy gate · Si", "poly", "Dummy gate",
              subtract((-XG, XG, 0, ymo, -hzmo, hzmo), F.boxes()), (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0)))
    core("dummy", "Dummy gate stack",
        "The dummy gate is made for both regions at once: a thin sacrificial oxide, a silicon "
        "placeholder gate and a hard mask, patterned across the stacks. The gate line runs on "
        "over the nFET stack beside this one [R13].",
        match="published", figs=["6A/B"],
        subs=["The dummy Si and nitride hard mask are illustrative"])
    # 6
    win = (-XSD, XSD, 0, ycap + 1.5, -zsub, zsub)
    F.put(tmp("liner", "Protective liner", "liner", "Patterning", conformal(F.boxes(), 1.5, win), (0, .8, 0)))
    core("bottom", "pFET protected: the nFET's base layer is removed",
        "While the nFET region is opened and its high-Ge base layer etched out, the pFET region is "
        "sealed by a liner and a resist block (the operations above, on the tile). The pFET keeps "
        "its base layer, so no bottom dielectric isolation forms under it: its n-type stopper "
        "does that job [R13].", match="published", figs=["7A/B", "8A/B"],
        subs=["Liner material and thickness are illustrative"])
    # 7
    F.drop("liner")
    F.put(tmp("spfilm", "Spacer dielectric (as deposited)", "si3n4", "Spacers",
              conformal(F.boxes(), TSP, (-XSD, XSD, 0, ycap + TSP, -hzmo, hzmo)), (0, .5, 0)))
    F.snap("spacerdep", "Conformal spacer deposition",
        "The liner comes off, and the spacer dielectric is deposited over both regions. Under the "
        "nFET it fills the cavity left by its base layer; the pFET's stack has no cavity, so here "
        "the film only coats the stack and the dummy gate [R13].", view="cutb",
        match="published", figs=["9A/B"],
        subs=["When the liner is removed is not stated in the text read; it is removed here "
              "before the spacer film", "Nitride is drawn for the spacer dielectric"])
    # 8
    F.drop("spfilm")
    for s, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s * XG, s * XSP))
        F.put(tmp(f"spo_{t}", f"Si₃N₄ gate spacer · {t} side", "si3n4", "Spacers",
                  subtract((xa, xb, 0, ycap, -hzmo, hzmo), F.boxes()), (s * 1.3, 0, 0)))
    F.snap("spaceretch", "Spacer etch-back",
        "A directional etch leaves the film on the dummy-gate sidewalls as the outer spacers. "
        "Nothing stays under the pFET's stack: it still stands on its base layer.", view="cutb",
        match="intermediate", figs=["9A/B", "10A/B"],
        subs=["A separate etch-back state between the deposition (Fig. 9) and the recess "
              "(Fig. 10) is a teaching reconstruction"])
    # 9
    F.drop("pts_sub"); F.add("pts_n")
    layers((-XSP, XSP), (-XSP, XSP), sheets=True)
    F.snap("p_recess", "pFET source/drain recess",
        "With the nFET protected by a mask (the operation above, on both sites), the pFET stack "
        "outside the gate and spacers is etched away: through the Si and SiGe layers, through "
        "its high-Ge base, and on into the implanted sub-fin. The ends of every layer are now "
        "exposed at the recess walls, and so is the sub-fin's silicon at the bottom [R13].",
        match="published", figs=["10A/B"],
        subs=["The recess depth into the sub-fin is illustrative"],
        omitted=["The mask over the nFET (see the operation above)"])
    # 10
    layers((-XG, XG), (-XG, XG), sheets=True)
    F.snap("p_indent", "Si and base-layer indent",
        "A selective etch recesses the exposed Si layers and the high-Ge base sideways, leaving "
        "the lower-Ge SiGe ends in place: the reverse of the nFET's indent, where the SiGe is "
        "recessed and the Si kept. The pockets it opens under the spacers set the inner spacers "
        "[R13].", view="cutb", match="intermediate", figs=["11A/B"])
    # 11
    F.drop("spo_source", "spo_drain"); F.add("spacer_source", "spacer_drain")
    F.snap("p_inner", "Inner-spacer fill and etch-back",
        "Dielectric fills the pockets and is etched back, so it stays only between the SiGe sheet "
        "ends and under the lowest one: the inner spacers. The SiGe sheet ends are exposed again "
        "at the recess walls [R13].", view="cutb", match="intermediate", figs=["11A/B"],
        subs=["Inner spacers are drawn in the outer spacers' nitride"])
    # 12
    F.add("sib_source", "sib_drain", "epi_source", "epi_drain")
    F.snap("p_epi", "p-type source/drain epitaxy",
        "Boron-doped epitaxy grows from two seeds: the SiGe sheet ends at the recess walls and "
        "the silicon of the recessed sub-fin below. Here a thin Si:B layer grows first from the "
        "sub-fin, then SiGe:B fills the recess and joins the sheet ends [R13]. Grown from the "
        "substrate, the SiGe source/drain has a larger lattice than the silicon under it, so it "
        "pushes on the channel along its length: compressive strain, which helps hole mobility. "
        "No strain is calculated here.",
        match="published", figs=["11A/B"],
        subs=["Si:B then SiGe:B is an example sequence; layer thicknesses, Ge content and doping "
              "are illustrative"])
    # 13
    ild_around()
    F.snap("ild", "ILD fill and planarisation",
        "Interlayer dielectric is deposited over both regions and polished flat, stopping on the "
        "hard mask [R13].", match="intermediate", figs=["14A/B"])
    # 14
    F.drop("hardmask", "dummy", "dox")
    F.snap("pull", "Hard-mask opening and dummy-gate removal",
        "The hard mask is opened and the dummy gate and its oxide are removed from both regions. "
        "At the bottom of the trench the pFET's stack is still whole: Si, lower-Ge SiGe and the "
        "high-Ge base [R13].", view="cut", match="published", figs=["14A/B"])
    # 15
    F.drop("pbase"); F.drop_prefix("psi")
    F.snap("p_release", "pFET channel preparation",
        "With the nFET covered (the operation above), a selective etch removes the high-Ge base "
        "and the Si layers inside the pFET's gate trench and keeps the lower-Ge SiGe: three SiGe "
        "sheets, held at their ends by the source and drain [R13].", view="cut",
        match="published", figs=["15A/B"])
    # 16
    F.add(*[f"p{k}{i}" for k in ("il", "hk", "wf") for i in (1, 2, 3)],
          "pfloor_il", "pfloor_hk", "pfloor_wf", "mo", "gatecap")
    F.snap("p_hkmg", "High-κ and p-type work-function metal",
        "An interfacial oxide, a high-κ dielectric and the pFET's own work-function metal are "
        "deposited round each SiGe sheet, and a gate fill joins them. The work-function "
        "treatment is the pFET's, separate from the nFET's [R13]. With no bottom isolation, the "
        "same films also line the sub-fin's top under the gate: the n-type stopper keeps that "
        "surface from conducting.", view="cut", match="published", figs=["17A/B"],
        subs=["The spaces between the SiGe sheets are the Si layers' 5 nm, set by the nFET model; "
              "the pFET's films are drawn thinner (0.5 + 1 + 1 nm) so they fit and meet between the "
              "sheets. A real shared stack is designed so both gates fit",
              "The p-type work-function metal is a generic illustrative material"])
    # 17
    F.add("nisi_source", "nisi_drain", "ni_source", "ni_drain", "w_source", "w_drain", "gatew")
    ild_around()
    F.snap("p_contacts", "Middle-of-line contacts",
        "Contacts are opened through the ILD, the silicide is formed on the SiGe:B and metal fills "
        "the openings, with a contact onto the gate [R13].", match="published", figs=["18A/B"],
        subs=["The NiSi, Ni and W contact stack is illustrative; SiGe contacts can need a "
              "different silicide treatment"])
    # 18
    F.drop("ild")
    F.snap("p_done", "The finished pFET",
        "The pFET the shared stack makes: SiGe channels where the nFET has Si ones, an n-type "
        "stopper where the nFET has bottom dielectric isolation, and its own work-function metal. "
        "The ILD is hidden for viewing only.", match="published", figs=["18A/B"],
        subs=["The ILD is hidden for viewing only"])
    return dev, F, dict(
        scope=NS_P_SCOPE, figures=NS_FIGURES, branch=NS_P_BRANCH, skipped=NS_P_SKIPPED,
        refs=["R13", "R1", "R14", "R16", "R18", "R19", "R20", "R21"],
        audit_unverified=[
            "**Every figure mapping.** The patent's drawings have not been compared with these views; "
            "orientation, composition and labels may differ from the published artwork.",
            "**Section planes.** X1–X1 (along the pFET stack), Y1–Y1 and Y2–Y2 are placed from the "
            "patent's written description only.",
            "**The pFET's gate films.** Between its SiGe sheets the shared stack leaves the Si layers' "
            "5 nm, set by the nFET model, so the pFET's films are drawn 0.5 + 1 + 1 nm and meet in the "
            "middle; a real shared stack is designed so both gates fit.",
            "When the protective liner over the pFET is removed, and the Si:B then SiGe:B epitaxy "
            "sequence, are model choices; the recess depth into the sub-fin is illustrative.",
            "The lithography operations are concept-level; the stack patterning routes are the nFET "
            "flow's, a patterning concept applied to an illustrative layer."],
        match=dict(MATCH, **PAT_MATCH), routes=ROUTES,
        route_title="How the stack lines are printed", route_join="the stack etch",
        views=dict(dev.views, cut=CUTAWAY, cutb=INDENT, **TILE_VIEWS, **FIELD_VIEWS))


# ------------------------------------------------------------- both sites ----
# The nFET and pFET single-site models side by side, the pFET one stack pitch across (-z),
# in the tile's frame. What joins them is drawn here: the gate line between the two stacks
# (dummy, spacers, then metal, or metal with a cut) and the masks that keep each region's
# steps to itself. Everything else is the two site flows' own states, part for part.
GATE_METALS = ("mo", "tin", PWF, "tungsten")


def pair_builder(G, nflow, nfinal, pflow, pfinal):
    """[G]: the tech's dimensions. Returns (snap, stage): snap(...) composes one state of
    the pair from a state of each site and records it as a step."""
    dz, y0, XGg, XSPg, XSDg = G["dz"], G["y0"], G["XG"], G["XSP"], G["XSD"]
    ymo, ycap, hzmo, zsub, ZMID = G["ymo"], G["ycap"], G["hzmo"], G["zsub"], -G["dz"] / 2
    zb = (-dz + hzmo, -hzmo)                    # the gate line between the two stacks
    ZR = dict(n=(ZMID, zsub), p=(-dz - zsub, ZMID))
    RT, CW = 10.0, G["cut"]
    B = dict(x=[G["x"][0], G["x"][1]], y=[G["y"][0], ycap + RT + 34.0], z=[-dz - zsub, zsub])
    host = type("Pair", (), dict(key=G["key"], name=G["name"], parts=[], bounds=B))
    F = Flow(host)
    S = Stage(F, "pair", B)
    nby = {s["id"]: s for s in nflow["steps"]}
    pby = {s["id"]: s for s in pflow}
    who = dict(n="nFET", p="pFET")

    def site(k, sid, drop):
        st = (nby if k == "n" else pby)[sid]
        fin = nfinal if k == "n" else pfinal
        out = []
        for x in st["parts"]:
            p = fin[x] if isinstance(x, str) else x
            if p["id"] in drop or f"{k}:{p['id']}" in drop: continue
            bx = [list(b) for b in p["boxes"]]
            if k == "p":
                for b in bx: b[2] = round(b[2] - dz, 4)
            out.append(dict(p, id=f"{k}_{p['id']}", name=f"{who[k]} · {p['name']}", boxes=bx, site=k))
        return out

    def bridge(kind):
        """The gate line's stretch between the stacks, at a stage of [kind]."""
        z0, z1 = zb
        out = []
        if kind in ("dummy", "film", "spacers"):
            out += [tmp("b_dummy", "Dummy gate · Si · between the stacks", "poly", "Dummy gate",
                        [box(-XGg, XGg, y0, ymo, z0, z1)], (0, 1.0, 0)),
                    tmp("b_hm", "SiN hard mask · between the stacks", "si3n4", "Dummy gate",
                        [box(-XGg, XGg, ymo, ycap, z0, z1)], (0, 1.4, 0))]
        if kind in ("spacers", "trench", "metal", "cut", "cutopen"):
            out.append(tmp("b_spacers", "Si₃N₄ gate spacers · between the stacks", "si3n4", "Spacers",
                           [box(XGg, XSPg, y0, ycap, z0, z1), box(-XSPg, -XGg, y0, ycap, z0, z1)], (0, 0, 0)))
        if kind == "metal":
            out += [tmp("b_mo", "Mo gate fill · the connection between the two gates", "mo", "Gate electrode",
                        [box(-XGg, XGg, y0, ymo, z0, z1)], (0, 1.0, 0)),
                    tmp("b_cap", "TiN gate cap · between the stacks", "tin", "Gate electrode",
                        [box(-XGg, XGg, ymo, ycap, z0, z1)], (0, 1.4, 0))]
        if kind in ("cut", "cutopen"):
            c0, c1 = ZMID - CW / 2, ZMID + CW / 2
            for (a, b), side in (((c1, z1), "nFET"), ((z0, c0), "pFET")):
                out += [tmp(f"b_mo_{side[0]}", f"Mo gate fill · {side} side of the cut", "mo", "Gate electrode",
                            [box(-XGg, XGg, y0, ymo, a, b)], (0, 1.0, 0)),
                        tmp(f"b_cap_{side[0]}", f"TiN gate cap · {side} side of the cut", "tin", "Gate electrode",
                            [box(-XGg, XGg, ymo, ycap, a, b)], (0, 1.4, 0))]
            if kind == "cut":
                out.append(tmp("b_plug", "Gate-cut dielectric (SiN fill)", "si3n4", "Gate cut",
                               [box(-XGg, XGg, y0, ycap, c0, c1)], (0, 1.6, 0)))
        return out

    def hits(a, b):
        a, b = lim(a), lim(b)
        return all(min(a[k + 1], b[k + 1]) > max(a[k], b[k]) + 1e-6 for k in (0, 2, 4))

    def carve(parts, holes):
        """Dielectrics drawn by each site out to its own edge give way to the gate line
        between the stacks."""
        out = []
        for p in parts:
            if (p["material"] in ("ild", "liner") or p["group"] == "Interlayer dielectric") and \
                    any(hits(a, h) for a in p["boxes"] for h in holes):
                p = dict(p, boxes=[[round(float(v), 4) for v in c]
                                   for a in p["boxes"] for c in subtract(lim(a), holes)])
            out.append(p)
        return out

    def snap(sid, title, body, *, n, p, br=None, drop=(), liner=None, block=None, film=None,
             extra=(), of=None, view="pair", match="published", figs=(), regions=None, route=None, **kw):
        parts = site("n", n, drop) + site("p", p, drop)
        if dz > 2 * zsub + 1e-6:
            # The site cells are narrower than the pitch: what the nFET cell has at its -z edge
            # (wafer, STI, ILD) carries on across the strip between the two cells.
            gap = []
            for q in parts:
                if q.get("site") != "n": continue
                bx = [box(lim(c)[0], lim(c)[1], lim(c)[2], lim(c)[3], -dz + zsub, -zsub)
                      for c in q["boxes"] if abs(lim(c)[4] + zsub) < 1e-6]
                if bx: gap.append(tmp(f"g_{q['id'][2:]}", "Between the sites · " + q["name"].split(" · ", 1)[1],
                                      q["material"], q["group"], bx, q["explode"]))
            parts += gap
        b = bridge(br) if br else []
        parts = carve(parts, [x for q in b for x in q["boxes"]]) + b
        S.now = {q["id"]: q for q in parts}
        if film:        # the spacer film over the gate line between the stacks
            S.put(tmp("b_film", "Spacer dielectric (as deposited) · between the stacks", "si3n4", "Spacers",
                      conformal(S.boxes(), film, (-XSDg, XSDg, y0, ycap + film, zb[0], zb[1])), (0, .5, 0)))
        if liner:       # a protective liner over one region
            z0, z1 = ZR[liner]
            S.put(tmp("m_liner", f"Protective liner over the {who[liner]} region", "liner", "Region masks",
                      conformal(S.boxes(), 1.5, (-XSDg, XSDg, y0, ycap + 1.5, z0, z1)), (0, .8, 0)))
        if block:       # a resist block over one region
            z0, z1 = ZR[block]
            S.put(tmp("m_block", f"Resist block over the {who[block]} region", "resist", "Region masks",
                      subtract((-XSDg, XSDg, y0, ycap + 12.0, z0, z1), S.boxes()), (0, 1.6, 0)))
        for q in extra: S.put(q)
        S.route = route
        S.snap(sid, title, body, view, match=match, figs=figs, of=of, **kw)
        st = F.steps[-1]
        st["pair"] = dict(n=n, p=p, bridge=br, liner=liner, block=block)
        st["from"] = dict(n=n, p=p, drop=sorted(drop))
        if regions: st["regions"] = regions
        return st

    return snap, S, F, dict(zb=zb, ZMID=ZMID, ZR=ZR, B=B, CW=CW, RT=RT)


def pair_views(G):
    zc = -G["dz"] / 2
    sd = (G["XSP"] + G["XSD"]) / 2
    return dict(
        pair=dict(n="Both sites", s="nFET in front, pFET behind", az=-0.70, el=0.42, r=G["r"],
                  tgt=[0, G["yt"], zc], clip=None, scale="pair"),
        pairplan=dict(n="From above", s="plan view", az=0.0, el=1.45, r=G["r"] * 0.9,
                      tgt=[0, 0, zc], clip=None, scale="pair"),
        paircut=dict(n="Across both, at the gate", s="section through the gate line", az=1.5708, el=0.12,
                     r=G["r"] * 0.78, tgt=[0, G["yt"], zc], clip=[0, None, None], scale="pair"),
        pairsd=dict(n="Across both, at the drains", s="section through the drains", az=1.5708, el=0.12,
                    r=G["r"] * 0.78, tgt=[sd, G["yt"], zc], clip=[sd, None, None], scale="pair"),
        pairn=dict(n="Along the nFET", s="section along its channel", az=-0.62, el=0.30, r=G["r"] * 0.62,
                   tgt=[0, G["yt"], G["zn"]], clip=[None, None, G["zn"]], scale="pair"),
        pairp=dict(n="Along the pFET", s="section along its channel", az=-0.62, el=0.30, r=G["r"] * 0.62,
                   tgt=[0, G["yt"], G["zp"]], clip=[None, None, G["zp"]], scale="pair"))


SITES = dict(
    ns=[dict(id="n", name="nFET", flow="ns"), dict(id="p", name="pFET", flow="ns_p"),
        dict(id="both", name="Both sites", flow="ns_pair")],
    fin=[dict(id="n", name="nFET", flow="fin"), dict(id="p", name="pFET", flow="fin_p"),
         dict(id="both", name="Both sites", flow="fin_pair")])
GATE_ROUTES = [
    dict(id="cut", name="Gate cut", default=True,
         note="The gate line is cut between the two stacks and the cut filled with dielectric: two "
              "gates, contacted independently."),
    dict(id="shared", name="Shared gate",
         note="No cut: one gate electrode runs over both stacks, as a CMOS inverter's input needs."),
]
PAIR_SUB = ("The two sites are the nFET and pFET flows' own models, one stack pitch apart; the gate "
            "line between them and the region masks are drawn here. Region masks, their materials and "
            "extents are illustrative")
BRANCH_CACHE = {}


def regions(n, p):
    return dict(n=n, p=p)


def ns_pair(ns, nfinal, psteps, pfinal):
    D = ns_dims()
    G = dict(key="ns_pair", name="Nanosheet · both sites", dz=2 * D["zsub"], y0=0.0, XG=XG, XSP=XSP, XSD=XSD,
             ymo=D["ymo"], ycap=D["ycap"], hzmo=D["hzmo"], zsub=D["zsub"], cut=12.0,
             x=(D["sub"][0], D["sub"][1]), y=(D["sub"][2], 0), r=560.0, yt=40.0, zn=0.0, zp=-2 * D["zsub"])
    snap, S, F, g = pair_builder(G, ns, nfinal, psteps, pfinal)
    ycap, CW, ZMID, RT = G["ycap"], g["CW"], g["ZMID"], g["RT"]
    SUBS = [PAIR_SUB]
    R0 = regions("not yet processed", "not yet processed")
    snap("substrate", "Silicon substrate", "One wafer for both devices: the nFET region in front, the "
         "pFET region behind it, one stack pitch away [R13].", n="substrate", p="substrate",
         figs=["2A/B"], subs=SUBS, regions=R0)
    snap("pts_pmask", "p-type implant, pFET masked", "A resist block covers the pFET region while "
         "the nFET region receives its p-type punch-through stopper [R13].", n="pts", p="substrate",
         block="p", of="pts", match="intermediate", figs=["3A/B"], subs=SUBS,
         regions=regions("implanted p-type", "masked"))
    snap("pts_nmask", "n-type implant, nFET masked", "The block is moved: now the nFET region is "
         "covered and the pFET region receives its n-type stopper [R13].", n="pts", p="pts",
         block="n", of="pts", match="intermediate", figs=["3A/B"], subs=SUBS,
         regions=regions("masked", "implanted n-type"))
    snap("pts", "Both stoppers implanted", "Each region has its own stopper: p-type under the nFET, "
         "n-type under the pFET [R13].", n="pts", p="pts", figs=["3A/B"], subs=SUBS,
         regions=regions("p-type stopper", "n-type stopper"))
    snap("superlattice", "One Si/SiGe stack for both", "One multilayer grows over both regions: the "
         "nFET will keep its Si layers as channels, the pFET its lower-Ge SiGe layers [R13].",
         n="superlattice", p="superlattice", figs=["4A/B"], subs=SUBS,
         regions=regions("shared stack", "shared stack"))
    snap("pattern", "Both stacks patterned", "The two stack lines are patterned together, with shallow "
         "trench isolation between them [R13]. The operations are shown in the nFET and pFET flows, on "
         "the tile.", n="pattern", p="pattern", figs=["5A/B"], subs=SUBS,
         regions=regions("stack line and sub-fin", "stack line and sub-fin"))
    snap("dummy", "One dummy gate across both", "The dummy gate runs over both stacks and the "
         "isolation between them [R13].", n="dummy", p="dummy", br="dummy", figs=["6A/B"], subs=SUBS,
         regions=regions("dummy gate", "dummy gate"))
    snap("n_open", "pFET protected, nFET opened", "A liner and a resist block cover the pFET region; the "
         "nFET region is open, with its high-Ge base layer's sidewalls exposed [R13].", n="dummy",
         p="dummy", br="dummy", liner="p", block="p", of="bottom", match="intermediate", figs=["7A/B"],
         subs=SUBS, regions=regions("open", "masked"))
    snap("bottom", "nFET base layer removed", "The nFET's high-Ge base layer is etched out from under "
         "its stack, which the dummy gate holds up; the resist is stripped and the liner keeps the pFET "
         "sealed. The pFET keeps its base layer [R13].", n="bottom", p="bottom", drop=("liner",),
         br="dummy", liner="p", view="pairn", figs=["8A/B"], subs=SUBS,
         regions=regions("base layer removed: a cavity", "protected; base kept"))
    snap("spacerdep", "Spacer dielectric over both", "The liner comes off and the spacer dielectric "
         "is deposited over both regions: under the nFET it fills the cavity, the future bottom "
         "dielectric isolation; the pFET has no cavity [R13].", n="spacerdep", p="spacerdep",
         br="dummy", film=XSP - XG, view="paircut", figs=["9A/B"], subs=SUBS,
         regions=regions("spacer film; cavity filled (BDI)", "spacer film"))
    snap("spaceretch", "Spacers on both", "The etch-back leaves spacers on the dummy gate's sidewalls "
         "along its whole length, over both stacks and between them.", n="spaceretch", p="spaceretch",
         br="spacers", match="intermediate", figs=["9A/B"], subs=SUBS,
         regions=regions("spacers; BDI", "spacers"))
    snap("p_open", "nFET protected, pFET opened", "A liner and a resist block now cover the nFET; the "
         "pFET region is open [R13].", n="spaceretch", p="spaceretch", br="spacers", liner="n",
         block="n", of="p_recess", match="intermediate", figs=["10A/B"], subs=SUBS,
         regions=regions("masked", "open"))
    for sid, title, body, fig, view in (
            ("p_recess", "pFET source/drain recess", "The pFET stack is recessed outside its spacers, "
             "through its base layer and into the n-type sub-fin, while the liner protects the nFET "
             "[R13].", "10A/B", "pairp"),
            ("p_indent", "pFET Si and base-layer indent", "The pFET's Si layers and high-Ge base are "
             "indented under its spacers [R13].", "11A/B", "pairp"),
            ("p_inner", "pFET inner spacers", "Inner spacers fill the pFET's pockets [R13].", "11A/B", "pairp"),
            ("p_epi", "pFET source/drain epitaxy", "SiGe:B grows from the pFET's SiGe sheet ends and its "
             "recessed sub-fin; the nFET, still under its liner, gets none [R13].", "11A/B", "pairp")):
        snap(sid, title, body, n="spaceretch", p=sid, br="spacers", liner="n", view=view,
             match="published" if sid in ("p_recess", "p_epi") else "intermediate", figs=[fig],
             subs=SUBS, regions=regions("protected", {"p_recess": "recessed", "p_indent": "Si and base indented",
                                                      "p_inner": "inner spacers", "p_epi": "SiGe:B source/drain"}[sid]))
    snap("n_open2", "pFET protected, nFET opened", "The masks swap: a liner and resist block over the "
         "pFET, and the nFET open [R13].", n="spaceretch", p="p_epi", br="spacers", liner="p", block="p",
         of="recess", match="intermediate", figs=["12A/B"], subs=SUBS, regions=regions("open", "masked"))
    for sid, title, body, fig, st in (
            ("recess", "nFET source/drain recess", "The nFET stack is recessed outside its spacers, "
             "stopping on its BDI [R13].", "12A/B", "recessed to the BDI"),
            ("indent", "nFET SiGe indent", "The nFET's lower-Ge SiGe is indented under its spacers "
             "[R13].", "13A/B", "SiGe indented"),
            ("inner", "nFET inner spacers", "Inner spacers fill the nFET's pockets [R13].", "13A/B", "inner spacers"),
            ("epi", "nFET source/drain epitaxy", "Si:P grows from the nFET's Si sheet ends; the pFET, "
             "under its liner, gets none [R13].", "13A/B", "Si:P source/drain")):
        snap(sid, title, body, n=sid, p="p_epi", br="spacers", liner="p", view="pairn",
             match="published" if sid in ("recess", "epi") else "intermediate", figs=[fig],
             subs=SUBS, regions=regions(st, "protected"))
    snap("ild", "ILD over both", "The liner comes off and interlayer dielectric fills over both "
         "regions, polished down to the gate hard mask [R13].", n="ild", p="ild", br="spacers",
         match="intermediate", figs=["14A/B"], subs=SUBS, regions=regions("buried in ILD", "buried in ILD"))
    snap("pull", "One gate trench over both", "The dummy gate is removed along its whole length: one "
         "trench runs over both stacks and the isolation between them [R13].", n="pull", p="pull",
         br="trench", view="paircut", figs=["14A/B"], subs=SUBS,
         regions=regions("gate trench open", "gate trench open"))
    snap("p_chopen", "nFET covered, pFET's trench open", "Resist fills the nFET's part of the trench "
         "[R13].", n="pull", p="pull", br="trench", block="n", of="p_release", match="intermediate",
         view="paircut", figs=["15A/B"], subs=SUBS, regions=regions("masked", "open"))
    snap("p_release", "pFET channels prepared", "In the pFET's trench the high-Ge base and the Si layers "
         "are removed, leaving three SiGe sheets [R13].", n="pull", p="p_release", br="trench", block="n",
         view="paircut", figs=["15A/B"], subs=SUBS, regions=regions("masked", "SiGe sheets released"))
    snap("n_chopen", "pFET covered, nFET's trench open", "The resist moves to the pFET's part of the "
         "trench [R13].", n="pull", p="p_release", br="trench", block="p", of="release",
         match="intermediate", view="paircut", figs=["16A/B"], subs=SUBS, regions=regions("open", "masked"))
    snap("release", "nFET channels released", "In the nFET's trench the lower-Ge SiGe is removed, "
         "leaving three Si sheets over the BDI [R13].", n="release", p="p_release", br="trench", block="p",
         view="paircut", figs=["16A/B"], subs=SUBS, regions=regions("Si sheets released", "masked"))
    snap("hkmg", "Two work functions, one gate line", "Each region gets its own work-function treatment: "
         "TiN round the nFET's Si sheets, the pFET's own p-type metal round its SiGe sheets [R13]. The "
         "gate fill runs on between the stacks, so at this point the two gates are one conductor.",
         n="hkmg", p="p_hkmg", br="metal", view="paircut", figs=["17A/B"], subs=SUBS + [
             "How each work-function layer is kept to its own region (deposit, mask, remove) is not drawn"],
         regions=regions("n-type work function", "p-type work function"))
    gate_ends(snap, G, g, n_state="hkmg", p_state="p_hkmg", n_done="contacts", p_done="p_contacts",
              figs_cut=["17A/B", "18A/B"], figs_shared=["19A/B"], src={}, SUBS=SUBS)
    return G, F


def gate_ends(snap, G, g, *, n_state, p_state, n_done, p_done, figs_cut, figs_shared, src, SUBS,
              shared_note=None, fill=()):
    """The two ways the gate line ends, as alternative routes that never follow each other:
    a cut between the stacks, filled with dielectric (two gates), or no cut (one gate)."""
    XGg, XSDg, ycap, CW, ZMID, RT = G["XG"], G["XSD"], G["ycap"], g["CW"], g["ZMID"], g["RT"]
    RY = ycap + RT + 30.0
    z0, z1 = g["B"]["z"]
    op = (-XGg, XGg, ycap, ycap + RT, ZMID - CW / 2, ZMID + CW / 2)
    res = lambda pid, name, mat, bx: tmp(pid, name, mat, "Patterning", bx, (0, 1.6, 0))
    blanket = (-XSDg, XSDg, ycap, ycap + RT, z0, z1)
    sourced = bool(figs_cut) and not shared_note
    m_src = "published" if not src else "source"
    subs_x = [] if not shared_note else [shared_note]
    R = regions("gate line joined", "gate line joined")
    common = dict(n=n_state, p=p_state, of="gatecut", route="cut", match="concept", subs=SUBS)
    snap("cut_coat", "Gate-cut resist", "Resist is spun on over the polished surface [R16].",
         br="metal", extra=[res("c_res", "Photoresist (coated)", "resist", [box(*blanket)])], regions=R, **common)
    snap("cut_expose", "Gate-cut exposure", "The reticle's chrome covers everything but a short slot "
         "across the gate line, midway between the stacks; the resist there becomes soluble [R16].",
         br="metal", extra=[res("c_res", "Photoresist (unexposed)", "resist", subtract(blanket, [box(*op)])),
                            res("c_res_x", "Photoresist (exposed: the cut)", "resist_exp", [box(*op)]),
                            res("c_ret", "Reticle chrome (in the scanner; not to scale)", "chrome",
                                subtract((-XSDg, XSDg, RY, RY + 2.0, z0, z1), [box(-XGg, XGg, RY, RY + 2.0, op[4], op[5])]))],
         regions=R, **dict(common, subs=SUBS + ["Exposure is simplified: no optics, proximity, dose or overlay effects"]))
    snap("cut_open", "Gate-cut opening", "The developer opens the slot in the resist [R16].", br="metal",
         extra=[res("c_res", "Photoresist (with the cut opening)", "resist", subtract(blanket, [box(*op)]))],
         view="paircut", regions=R, **common)
    snap("cut_etch", "Gate-cut etch", "Through the opening, the gate cap and gate fill are etched down to "
         "the isolation: the conductive connection between the two gates is gone. The etch stays between "
         "the stacks: neither device's channels nor its source/drain is touched.", br="cutopen",
         extra=[res("c_res", "Photoresist (with the cut opening)", "resist", subtract(blanket, [box(*op)]))],
         view="paircut", regions=regions("own gate", "own gate"),
         **dict(common, match="teach", subs=SUBS + subs_x))
    cut_ref = " [R13]" if sourced else ""
    snap("gatecut", "Cut filled: two gates", "The slot is filled with dielectric and polished, and the "
         "resist is gone. The nFET and pFET now have separate gates, to be contacted independently" +
         cut_ref + ".", n=n_state, p=p_state, br="cut", route="cut", view="paircut",
         match=m_src if sourced else "teach", figs=figs_cut if sourced else [],
         subs=SUBS + subs_x + ["The cut is drawn exactly the gate's length and square-walled; its "
                               "width is illustrative"],
         regions=regions("own gate", "own gate"), **(src if sourced else {}))
    snap("contacts_cut", "Contacts: two gate contacts", "Source, drain and gate contacts on each "
         "device; with the cut, each gate has its own contact" + (" [R13]" if sourced else
         " [R24]") + ".", n=n_done, p=p_done, br="cut", route="cut", view="pair",
         match=m_src, figs=figs_cut[-1:], subs=SUBS + subs_x,
         regions=regions("contacted; own gate", "contacted; own gate"), **src)
    snap("shared", "Shared gate: one input", "The alternative: the gate line is not cut. One gate "
         "electrode runs over both, each device with its own work-function metal, and one contact "
         "serves both, as a CMOS inverter's input needs" + (". This is Fig. 19's arrangement, an "
         "alternative to the cut, not a step after it [R13]." if sourced else " [R24]."),
         n=n_done, p=p_done, drop=("p:gatew",), br="metal", route="shared", view="paircut",
         extra=[tmp("b_ildfill", "ILD · no second gate contact here", "ild", "Interlayer dielectric",
                    fill, (0, .6, 0))] if fill else [],
         match=m_src, figs=figs_shared, subs=SUBS + subs_x + [
             "One gate contact is drawn, over the nFET; where it lands is illustrative"],
         regions=regions("contacted; shared gate", "shared gate"), **src)


def pair_labels(steps):
    """Core steps count 1, 2, 3... along each route (the two ways the gate line ends are
    terminal alternatives); the operations leading to core step n are n.1, n.2..."""
    routes = list(dict.fromkeys(st["route"] for st in steps if st.get("route")))
    for r in routes:
        core, ops = 0, 0
        for k, st in enumerate(steps):
            if st.get("route") not in (None, r): continue
            if st["level"] == "core": core += 1; ops = 0; lab = str(core)
            else: ops += 1; lab = f"{core + 1}.{ops}"
            st.setdefault("labels", {})[r] = lab
    for st in steps:
        lab = st.pop("labels")
        st["label"] = lab[st.get("route") or routes[0]]
        if not st.get("route") and len(set(lab.values())) > 1: st["labels"] = lab
    return steps


def insert_pair_ops(F, pair_steps, ids):
    """Copy the both-sites operations [ids] into a site flow, each before its core step."""
    for oid in ids:
        oid, to = oid if isinstance(oid, tuple) else (oid, None)
        op = json.loads(json.dumps(next(s for s in pair_steps if s["id"] == oid)))
        if to: op["of"] = to
        op.pop("pair", None); op.pop("regions", None); op.pop("route", None); op.pop("from", None)
        k = next(i for i, s in enumerate(F.steps) if s["level"] == "core" and s["id"] == op["of"])
        F.steps.insert(k, op)


def attach_regions(steps, pair_steps, side):
    """Each step says what state both regions are in, read off the both-sites flow."""
    cores = [s for s in pair_steps if s["level"] == "core" and not s.get("route")] + \
            [s for s in pair_steps if s["level"] == "core" and s.get("route") == "cut"]
    last = None
    for st in steps:
        if st["level"] != "core": continue
        m = next((s for s in cores if s["id"] == st["id"]), None) or \
            next((s for s in cores if s["pair"][side] == st["id"]), None)
        # A step the both-sites flow does not show (the finished device, say) keeps the last state.
        last = m["regions"] if m else last
        if last: st["regions"] = last
    nxt = None
    for st in reversed(steps):
        if st["level"] == "core": nxt = st.get("regions")
        elif nxt and "regions" not in st: st["regions"] = nxt


def flow_ns_p_all(done):
    dev, F, extra = flow_ns_p(done)
    ns = done["ns"]
    nfinal = {p["id"]: p for p in bd.build_ns().parts}
    G, PF = ns_pair(ns, nfinal, F.steps, F.final)
    insert_pair_ops(F, PF.steps, ["pts_nmask", "p_open", "p_chopen"])
    extra["views"].update(pair_views(G))
    steps = F.done()
    attach_regions(steps, PF.steps, "p")
    attach_regions(ns["steps"], PF.steps, "n")
    for fl in (ns, extra): fl["sites"] = SITES["ns"]
    ns["site"], extra["site"] = "n", "p"
    BRANCH_CACHE["ns_pair"] = (G, PF, dev)
    extra.update(own=True, name=dev.name, bounds=dev.bounds, final=dev.parts)
    return dev, steps, extra


def flow_ns_pair(done):
    G, PF, pdev = BRANCH_CACHE["ns_pair"]
    steps = pair_labels(PF.steps)
    for st in steps: st.pop("pair", None)
    host = type("Pair", (), dict(key="ns_pair", name=G["name"], parts=[], bounds=PF.dev.bounds))
    return host, steps, dict(
        own=True, name=G["name"], bounds=PF.dev.bounds, site="both", sites=SITES["ns"],
        scope="The nanosheet nFET and pFET together, as the patent makes them from one stack [R13]: "
              "the two single-site models one stack pitch apart, joined by their gate line, with the "
              "masks that keep each region's steps to itself. At the end the gate line is either cut "
              "into two gates or kept as one shared gate: two alternatives, not two steps. "
              "Illustrative materials and dimensions; not a verified foundry recipe.",
        figures=NS_FIGURES,
        branch="Both sites: one nFET and one pFET, not a finished circuit. Each site is its own "
               "flow's model at that stage; the gate line between the stacks and the region masks are "
               "drawn here. The 2 × 2 tile's patterning operations are in the nFET and pFET flows.",
        skipped={}, refs=["R13", "R16"],
        match={k: v for k, v in dict(MATCH, **FIN_MATCH).items() if k in {st["match"] for st in steps}},
        routes=GATE_ROUTES,
        route_title="How the gate line ends", route_join="", route_kind="terminal",
        views=pair_views(G),
        audit_tile="Every state is the nFET flow's state and the pFET flow's state named in the "
                   "Match column's step, side by side one stack pitch apart; the build checks the "
                   "composition for overlaps, that each region mask covers only its own region, "
                   "that the gate cut leaves no conductive path between the two gates and cuts no "
                   "stack, sheet or source/drain, and that the shared gate keeps them connected.")




# ------------------------------------------------------------ FinFET pFET ----
# The FinFET model's pFET is the nFET's geometry with its own materials: the fins in an
# n-well, a selectively grown SiGe:B source/drain with the nFET masked, and a separate
# p-type work-function metal. Every state is the nFET flow's, part for part, with those
# parts swapped, so the two cannot drift apart; the region masks are in Both sites.
FIN_P_BODY = dict(
    substrate="The flow starts from a bare silicon wafer; the fins will be cut from it. This pFET "
              "sits in an n-well, the nFET beside it in a p-well; F1 describes the wells as optional "
              "implants here [R24]. The wells are named, not drawn as doping profiles.",
    epi="With the nFET region masked (the operation above, on both sites), boron-doped SiGe grows "
        "selectively from the recessed fins' exposed silicon, not from the STI or the mask, and "
        "facets outward above it; an anneal activates the dopant [R25]. Grown on the silicon fin, "
        "the larger SiGe lattice squeezes the channel along its length: compressive strain, which "
        "helps holes. No strain is calculated here. Each fin's epitaxy stays separate; merged "
        "neighbours are an alternative [R24].",
    metal="The pFET's own work-function metal goes on the high-κ, applied while the nFET is masked, "
          "separate from the nFET's TiN; molybdenum fills the rest of the trench and is polished, "
          "then recessed and capped. The metal wraps three faces of each fin: the tri-gate [R24].",
    done="The finished FinFET pFET, with the ILD and etch-stop film hidden: two fins in an n-well, "
         "wrapped on three faces by the high-κ and p-type metal gate, between SiGe:B source and "
         "drain. Its geometry is the nFET model's; only its materials and doping differ.")
FIN_P_SUBS = dict(
    epi=["The SiGe:B composition and facets are illustrative; the two-step facet is the nFET "
         "model's shape"],
    metal=["The p-type work-function metal is a generic illustrative material; TiN, Mo and a TiN "
           "cap are otherwise the nFET model's choices"])
FIN_P_TEXT = [
    ("Only the selected nFET is carried to a finished device; the other three are context.",
     "In this flow the pFET pair beside the selected nFET is the one followed; the other sites are "
     "context."),
    ("Only the selected nFET is completed. Next, the view returns to the selected site",
     "In this flow the pFET site on the same gate line is completed. Next, the view returns to "
     "that site"),
]


def fin_p_final():
    d = bd.build_fin()
    out = []
    for p in d.parts:
        q = dict(p)
        if p["id"].startswith("epi_"):
            q.update(material="sige", name=p["name"].replace("(Si:P)", "(SiGe:B)"))
        elif p["id"].startswith("tin") and p["id"] != "tin":
            q.update(material=PWF, name=p["name"].replace("TiN work-function metal", "p-type work-function metal"))
        elif p["id"].startswith("fin"):
            q.update(name=p["name"] + " (n-well)")
        elif p["id"] == "substrate":
            q.update(name="Si substrate (n-well region)")
        out.append(q)
    d.parts = out
    d.key, d.name = "fin_p", "FinFET pFET"
    return d


def flow_fin_p(done):
    fin = done["fin"]
    dev = fin_p_final()
    steps = json.loads(json.dumps(fin["steps"]))
    for st in steps:
        st.pop("compare", None); st.pop("regions", None)
        for a, b in FIN_P_TEXT: st["body"] = st["body"].replace(a, b)
        st["body"] = FIN_P_BODY.get(st["id"], st["body"]) if st["scale"] == "site" else st["body"]
        if st["scale"] == "site" and st["id"] in FIN_P_SUBS: st["subs"] = FIN_P_SUBS[st["id"]]
        if st["scale"] == "site":
            st["omitted"] = [o for o in st["omitted"] if "pFET" not in o] + (
                ["The nFET region beside it and the masks over it (see Both sites)"]
                if st["id"] in ("epi", "metal") else [])
            for p in st["parts"]:
                if isinstance(p, dict) and p["id"] in ("fin1_full", "fin2_full"):
                    p["name"] += " (n-well)"
        if st["id"] == "epi" and st["level"] == "core":
            st["title"] = "SiGe:B source/drain epitaxy"
            st["src"] = sorted(set(st.get("src", []) + ["R25"]))
        if st["id"] == "metal": st["title"] = "p-type work-function metal, gate fill and cap"
        if st["id"] == "done": st["title"] = "The finished pFET"
    extra = {k: v for k, v in fin.items() if k not in ("steps", "sections", "badge", "badge_note", "site", "sites")}
    extra = json.loads(json.dumps(extra))
    extra.update(
        scope="Representative bulk silicon FinFET pFET fabrication, gate last: the FinFET flow's stages "
              "with the pFET's own steps, an n-well, SiGe:B source/drain grown with the nFET masked "
              "[R25], and a separate p-type work-function metal. The geometry is the nFET model's; "
              "materials, masks and dimensions are illustrative. Not a verified foundry recipe.",
        branch="The pFET branch: the same wafer, fins and gate patterning as the nFET (the tile's "
               "operations are the nFET flow's own), then its own masked operations. The Both sites "
               "view shows the two together, with the region masks and the choice between a gate cut "
               "and a shared gate.",
        own=True, name=dev.name, bounds=dev.bounds, final=dev.parts)
    extra["views"] = dict(bd.build_fin().views, **extra["views"])
    extra["audit_unverified"] = extra.get("audit_unverified", []) + [
        "**The pFET's model.** Its geometry is the nFET model's; the n-well, SiGe:B source/drain and "
        "p-type work-function metal are named and coloured, not dimensioned, and no strain or "
        "threshold is calculated.",
        "The masks that keep each region's steps to itself are shown in Both sites; their materials "
        "and the order of the masked steps are illustrative."]
    return dev, steps, extra


def fin_pair(fin, nfinal, psteps, pfinal):
    fd = bd.build_fin()
    P = {p["id"]: p for p in fd.parts}
    cap = lim(P["gatecap"]["boxes"][0]); zsub = lim(P["substrate"]["boxes"][0])[5]
    G = dict(key="fin_pair", name="FinFET · both sites", dz=81.0, y0=12.0, XG=9.0, XSP=16.0, XSD=38.0,
             ymo=cap[2], ycap=cap[3], hzmo=cap[5], zsub=zsub, cut=10.0, x=(-48.0, 48.0), y=(-26.0, 0),
             r=500.0, yt=35.0, zn=13.5, zp=13.5 - 81.0)
    snap, S, F, g = pair_builder(G, fin, nfinal, psteps, pfinal)
    SUBS = [PAIR_SUB, "The wells are named regions, not doping profiles"]
    src = dict(src=["R24"])
    snap("pwell", "p-well implant, pFET masked", "A resist block covers the pFET region while the "
         "nFET region is implanted for its p-well [R24].", n="substrate", p="substrate", block="p",
         of="substrate", match="source", figs=["2A"], subs=SUBS, regions=regions("p-well implant", "masked"), **src)
    snap("nwell", "n-well implant, nFET masked", "The block is moved and the pFET region is implanted "
         "for its n-well [R24].", n="substrate", p="substrate", block="n", of="substrate", match="source",
         figs=["2A"], subs=SUBS, regions=regions("masked", "n-well implant"), **src)
    snap("substrate", "One wafer, two wells", "A p-well under the nFET region, an n-well under the pFET "
         "region; F1 describes the wells as optional [R24].", n="substrate", p="substrate",
         match="source", figs=["2A"], subs=SUBS, regions=regions("p-well", "n-well"), **src)
    snap("fins", "Both fin pairs", "The fins of both devices are patterned together, with STI between "
         "them [R24]. The operations are shown in the nFET and pFET flows, on the tile.", n="fins",
         p="fins", match="source", figs=["3A", "4A", "5A"], subs=SUBS, regions=regions("fins", "fins"), **src)
    snap("dummy", "One dummy gate across both", "The dummy gate runs over both fin pairs and the STI "
         "between them [R24].", n="dummy", p="dummy", br="dummy", match="source", figs=["6A", "7A"],
         subs=SUBS, regions=regions("dummy gate", "dummy gate"), **src)
    snap("spacerdep", "Spacer dielectric over both", "The gate spacer film is deposited over both "
         "regions and along the gate line between them.", n="spacerdep", p="spacerdep", br="dummy",
         film=G["XSP"] - G["XG"], view="paircut", match="teach", subs=SUBS + [SPACER_SUB],
         regions=regions("spacer film", "spacer film"))
    snap("spaceretch", "Spacers on both", "The etch-back leaves spacers along the whole gate line.",
         n="spaceretch", p="spaceretch", br="spacers", match="teach", subs=SUBS + [SPACER_SUB],
         regions=regions("spacers", "spacers"))
    snap("recess", "Both recessed", "The fins of both regions are recessed beside the spacers [R24].",
         n="recess", p="recess", br="spacers", view="pairsd", match="source", figs=["16A"], subs=SUBS,
         regions=regions("recessed", "recessed"), **src)
    snap("p_open", "nFET protected, pFET open", "A liner and a resist block cover the nFET region "
         "[R25].", n="recess", p="recess", br="spacers", liner="n", block="n", of="p_epi", match="source",
         figs=["17A"], subs=SUBS, regions=regions("masked", "open"), view="pairsd", src=["R24", "R25"])
    snap("p_epi", "pFET SiGe:B epitaxy", "SiGe:B grows selectively on the pFET's recessed fins; the "
         "nFET, under its liner, gets none [R25].", n="recess", p="epi", br="spacers", liner="n",
         view="pairsd", match="source", figs=["17A"], subs=SUBS, src=["R24", "R25"],
         regions=regions("protected", "SiGe:B source/drain"))
    snap("n_open", "pFET protected, nFET open", "The masks swap to the pFET region [R25].", n="recess",
         p="epi", br="spacers", liner="p", block="p", of="epi", match="source", figs=["17A"], subs=SUBS,
         view="pairsd", regions=regions("open", "masked"), src=["R24", "R25"])
    snap("epi", "nFET Si:P epitaxy", "Si:P grows on the nFET's recessed fins; the pFET, under its liner, "
         "gets none [R24][R25].", n="epi", p="epi", br="spacers", liner="p", view="pairsd", match="source",
         figs=["17A"], subs=SUBS, src=["R24", "R25"], regions=regions("Si:P source/drain", "protected"))
    snap("ild", "Etch-stop layer and ILD over both", "The liner comes off; the etch-stop film and ILD "
         "cover both regions, polished to the gate [R24].", n="ild", p="ild", br="spacers",
         match="source", figs=["18A"], subs=SUBS, regions=regions("buried in ILD", "buried in ILD"), **src)
    snap("pull", "One gate trench over both", "The dummy gate is removed along its whole length [R24].",
         n="pull", p="pull", br="trench", view="paircut", match="source", figs=["19A"], subs=SUBS,
         regions=regions("gate trench open", "gate trench open"), **src)
    snap("hk", "High-κ over both", "The interfacial layer and high-κ go into the whole trench [R24].",
         n="hk", p="hk", br="trench", view="paircut", match="source", figs=["20A"], subs=SUBS,
         regions=regions("high-κ", "high-κ"), **src)
    snap("wf_mask", "nFET covered for the p-type metal", "Resist covers the nFET's part of the trench "
         "while the pFET gets its own work-function metal and fill [R25].", n="hk", p="metal", br="trench", block="n",
         of="metal", view="paircut", match="teach", subs=SUBS + ["How each work-function layer is kept "
         "to its region is drawn as one resist block; the deposition order is illustrative"],
         regions=regions("masked", "p-type work function"))
    snap("metal", "Two work functions, one gate line", "The nFET has TiN, the pFET its own p-type "
         "metal; the Mo fill runs on between the fin pairs, so the two gates are one conductor [R24].",
         n="metal", p="metal", br="metal", view="paircut", match="source", figs=["20A"], subs=SUBS,
         regions=regions("n-type work function", "p-type work function"), **src)
    gate_ends(snap, G, g, n_state="metal", p_state="metal", n_done="contacts", p_done="contacts",
              figs_cut=["21A"], figs_shared=["21A"], src=src, SUBS=SUBS,
              shared_note="F1's text read here does not describe the gate cut; both endings are "
                          "teaching reconstructions of standard practice",
              # The FinFET's second ILD surrounds its gate contacts: without the pFET's, the
              # opening it would have filled is ILD.
              fill=[[b[0], b[1], round(b[2] - G["dz"], 4), b[3], b[4], b[5]] for b in pfinal["gatew"]["boxes"]])
    return G, F


def flow_fin_p_all(done):
    dev, steps, extra = flow_fin_p(done)
    fin = done["fin"]
    nfinal = {p["id"]: p for p in bd.build_fin().parts}
    pfinal = {p["id"]: p for p in dev.parts}
    G, PF = fin_pair(fin, nfinal, steps, pfinal)
    tmpF = type("F", (), dict(steps=steps))
    insert_pair_ops(tmpF, PF.steps, ["nwell", ("p_open", "epi"), "wf_mask"])
    relabel(steps)
    extra["views"].update(pair_views(G))
    attach_regions(steps, PF.steps, "p")
    attach_regions(fin["steps"], PF.steps, "n")
    for fl in (fin, extra): fl["sites"] = SITES["fin"]
    fin["site"], extra["site"] = "n", "p"
    BRANCH_CACHE["fin_pair"] = (G, PF)
    return dev, steps, extra


def flow_fin_pair(done):
    G, PF = BRANCH_CACHE["fin_pair"]
    steps = pair_labels(PF.steps)
    for st in steps: st.pop("pair", None)
    host = type("Pair", (), dict(key="fin_pair", name=G["name"], parts=[], bounds=PF.dev.bounds))
    used = {st["match"] for st in steps}
    return host, steps, dict(
        own=True, name=G["name"], bounds=PF.dev.bounds, site="both", sites=SITES["fin"],
        scope="The FinFET nFET and pFET together: the two single-site models one site width apart, "
              "joined by their gate line, with the masks that keep each region's own steps to itself "
              "(its wells, its source/drain epitaxy, its work-function metal). At the end the gate "
              "line is either cut into two gates or kept as one shared gate: alternatives, not two "
              "steps. Illustrative; not a verified foundry recipe.",
        figures=FIN_FIGURES,
        branch="Both sites: one nFET and one pFET, not a finished circuit. Each site is its own "
               "flow's model at that stage; the gate line between them and the region masks are drawn "
               "here. The tile's patterning operations are in the nFET and pFET flows.",
        skipped={}, refs=["R24", "R25", "R16"],
        match={k: v for k, v in dict(MATCH, **FIN_MATCH).items() if k in used}, routes=GATE_ROUTES,
        route_title="How the gate line ends", route_join="", route_kind="terminal",
        views=pair_views(G),
        audit_tile="Every state is the nFET and pFET flows' own states side by side, one site width "
                   "apart; the build checks the composition for overlaps, and the tests check that "
                   "each region mask covers only its own region, that the gate cut leaves no "
                   "conductive path between the two gates and cuts no fin or source/drain, and that "
                   "the shared gate keeps them connected.",
        audit_unverified=["**Every figure mapping.** F1's drawings have not been compared with these "
                          "views.", "The gate cut and shared gate are teaching reconstructions: the "
                          "F1 text read here does not describe a gate cut.",
                          "Region masks, their materials and the order of the masked steps are "
                          "illustrative."])


FLOWS = {"ns": flow_ns, "fin": flow_fin, "sadp": lesson("sadp"), "saqp": lesson("saqp"), "pitchwalk": flow_pitchwalk,
         "ns_p": flow_ns_p_all, "ns_pair": flow_ns_pair, "fin_p": flow_fin_p_all, "fin_pair": flow_fin_pair}


def audit(key, dev, flow, refs):
    """docs/PROCESS_AUDIT.md: every state against its source, generated from the data."""
    final = {p["id"]: p for p in dev.parts}
    part = lambda x: final[x] if isinstance(x, str) else x
    routes = {r["id"]: r for r in flow.get("routes", [])}
    md = [f"# Process audit: {dev.name}", "",
          "Generated by `scripts/build_process.py` from `data/process.json`; do not edit by hand.", "",
          flow["scope"], "", flow["branch"], "", "**" + flow["figures"] + "**", "",
          "## Match levels", ""]
    md += [f"- **{v}** (`{k}`)" for k, v in flow["match"].items()]
    md += ["", "## States", ""]
    md += ["This lesson is generated from the nanosheet flow's route of the same name and its "
           "stack etch, so every state, check and caveat below is that route's (see the "
           "nanosheet audit above)."] if flow.get("lesson") and not flow.get("audit_tile") else [
           flow.get("audit_tile") or
           "Steps numbered n.k are operation substeps leading into core step n; those at tile "
           "scale show a 2 × 2 context of two stack lines (nFET and pFET) crossed by two gate "
           "lines, with the selected nFET site at the single-site model's origin. The build checks "
           "that the tile, cropped to that site, matches the single-site model at steps 4, 5 and 6."]
    md += [""]
    if routes:
        md += ["Operations marked with a route are alternatives: the viewer shows one route at a "
               "time and numbers each route's operations on their own, so a shared operation after "
               "them carries one number per route. Field-scale states zoom out to the lines around "
               "the tile. Every route ends in the same tile state, which the build checks.", ""]
        md += [f"- **{r['name']}** (`{k}`): {r['note']}" for k, r in routes.items()] + [""]
    md += ["| # | Route | Scale | State | Source figures | Match | What changes | Model choices | Not shown |",
           "|---|---|---|---|---|---|---|---|---|"]
    # Each route has its own "previous state": a route's first operation follows core step
    # 3, and the shared operation after the routes follows each route's last one alike.
    prev = {r: ({}, None) for r in (routes or {None: None})}
    zoom = {"site": "zoom to the selected site", "tile": "zoom to the 2 × 2 tile",
            "field": "zoom out to the line field around the tile",
            "pair": "zoom out to both sites, nFET and pFET"}
    for st in flow["steps"]:
        now = {part(x)["id"]: part(x) for x in st["parts"]}
        r = st.get("route")
        was, was_scale = prev[r] if r else prev[next(iter(prev))]
        if was_scale is not None and st["scale"] != was_scale:
            chg = zoom[st["scale"]]
        else:
            added = [now[k]["name"] for k in now if k not in was]
            gone = [was[k]["name"] for k in was if k not in now]
            shaped = [now[k]["name"] for k in now if k in was and now[k]["boxes"] != was[k]["boxes"]]
            chg = "; ".join(x for x in ("+ " + ", ".join(added) if added else "",
                                        "− " + ", ".join(gone) if gone else "",
                                        "reshaped: " + ", ".join(shaped) if shaped else "") if x)
        cell = lambda xs: "<br>".join(xs) if xs else "—"
        figs = ", ".join("Fig. " + f for f in st["figs"]) or "—"
        lab = " · ".join(f"{routes[k]['name']} {v}" for k, v in st["labels"].items()) if "labels" in st else st["label"]
        md.append(f"| {lab} | {routes[r]['name'] if r else 'all'} | {st['scale']} | {st['title']} | {figs} "
                  f"| {flow['match'][st['match']]} | {chg or '—'} | {cell(st['subs'])} | {cell(st['omitted'])} |")
        for k in ([r] if r else list(prev)): prev[k] = (now, st["scale"])
    meas = [st for st in flow["steps"] if "measure" in st]
    if meas:
        md += ["", "## Spaces measured off the built lines", "",
               "Every value is read off the fin boxes of the state named; types by origin: " +
               "; ".join(f"{k}: {v['name']} ({v['rule']})" for k, v in flow["pitchwalk"]["types"].items()) + ".", "",
               "| State | First core | First spacer | Second spacer | Lines | Space a | Space b | Space c | Largest − smallest |",
               "|---|---|---|---|---|---|---|---|---|"]
        for st in meas:
            m = st["measure"]
            t = {k: "/".join(f"{w:g}" for w in m["types"].get(k, [])) for k in "abc"}
            md.append(f"| {st['title']} | {m['w1']:g} | {m['s1']:g} | {m['s2']:g} | {len(m['lines'])} | "
                      f"{t['a']} | {t['b']} | {t['c']} | {m['max']:g} − {m['min']:g} = {m['walk']:g} nm |")
    if flow["skipped"]:
        md += ["", "## Source figures not mapped to a state", ""]
        md += [f"- **Fig. {k}**: {v}" for k, v in flow["skipped"].items()]
    md += ["", "## Not yet verified", ""]
    md += ["- " + t for t in flow["audit_unverified"]] if "audit_unverified" in flow else [
           "- **Every figure mapping.** The patent's drawings have not been compared with these views; "
           "orientation, composition and labels may differ from the published artwork.",
           "- **Section planes.** The patent's section directions (X1–X1 along the pFET stack, "
           "X2–X2 along the nFET stack, Y1–Y1 across the stacks at the gate, Y2–Y2 across them at "
           "the source/drain) are placed from its written description only; where its drawings put "
           "each line, and which side each drawing is seen from, has not been checked.",
           "- The lithography operations (resist, exposure, development) are concept-level: no "
           "optics, dose, resist chemistry, overlay or mask count is modelled or claimed."]
    if (routes or flow.get("lesson")) and "audit_unverified" not in flow:
        md += ["- **Patterning routes.** SADP and SAQP are a patterning concept applied to an "
               "illustrative layer: the sources do not say this stack is patterned that way. P, P/2 "
               "and P/4 are ideal (real spacer images show pitch walk); core, spacer and film "
               "materials and thicknesses are illustrative; which lines a cut or block pattern "
               "removes is integration-dependent, and no overlay or placement error is modelled."]
    cmp = [(st, c) for st in flow["steps"] for c in st.get("compare", [])]
    if cmp:
        planes = {pl["id"]: pl for pl in flow.get("sections", [])}
        STATUS = dict(text="text-verified", visual="visually checked", unverified="unverified")
        md += ["", "## Section-plane mappings", "",
               "Each row sets one state against its source in one plane. **text-verified**: the "
               "source's text describes this stage and the plane's direction; the drawing has not "
               "been compared. **visually checked**: compared with the source's drawing (none yet). "
               "A row is upgraded by setting its status in `scripts/build_process.py`.", "",
               "| # | State | Plane | Source | Status | What the plane cuts in the model |",
               "|---|---|---|---|---|---|"]
        for st, c in cmp:
            figs = ", ".join("Fig. " + f for f in c["figs"])
            md.append(f"| {st['label']} | {st['title']} | {planes[c['plane']]['name']} | [{c['src']}] {figs} | "
                      f"{STATUS[c['status']]} | {', '.join(c['visible'][:8])}{' …' if len(c['visible']) > 8 else ''} |")
    md += ["", "## Sources cited", ""]
    md += [f"- **[{r}]** {refs[r]['title']} — {refs[r]['publisher']}. <{refs[r]['url']}>"
           for r in flow["refs"]]
    return "\n".join(md) + "\n"


# ======================================================== SECTION PLANES ===
# Named section planes through the model, and for every step that cites a figure, what the
# source describes against what the model shows in that plane. A plane is a cut the app makes
# through its own geometry: the nanosheet's follow directions the patent's text defines; the
# FinFET's are the app's own, not claimed to be its patent's A, B or C lines.
TEXT_STATUS = ("Stage described in the source's text; the source's drawing has not been compared "
               "with this section")
NS_PLANES = [
    dict(id="x2", name="Along the nFET stack, through the gate", short="Along nFET", axis="z", pos=0.0,
         text="The patent's X2–X2 direction: along the nFET stack, crossing its gate. Direction from "
              "the patent's text; not compared with its drawings."),
    dict(id="y1", name="Across the stacks, through the gate", short="Across · gate", axis="x", pos=0.0,
         text="The patent's Y1–Y1 direction: across the stacks through the gate region. Direction from "
              "the patent's text; not compared with its drawings."),
    dict(id="y2", name="Across the stacks, through the source/drain", short="Across · S/D", axis="x",
         pos=(XSP + XSD) / 2,
         text="The patent's Y2–Y2 direction: across the stacks through the source/drain region, here "
              "the drain side. Direction from the patent's text; not compared with its drawings."),
]
FIN_PLANES = [
    dict(id="across_gate", name="Across the fins, at the gate", short="Across · gate", axis="x", pos=0.0,
         text="The app's own section. Not claimed to be the patent's A, B or C line: its Fig. 1, which "
              "defines them, has not been inspected."),
    dict(id="along_fin", name="Along fin 2, source to drain", short="Along fin", axis="z", pos=13.5,
         text="The app's own section, through the middle of fin 2. Not claimed to be the patent's A, B "
              "or C line: its Fig. 1 has not been inspected."),
    dict(id="across_sd", name="Across the fins, through the drain", short="Across · S/D", axis="x",
         pos=27.0,
         text="The app's own section, through the drain epitaxy. Not claimed to be the patent's A, B or "
              "C line: its Fig. 1 has not been inspected."),
    dict(id="field_across", name="Across the fin lines, mid-field", short="Across lines", axis="x",
         pos=-38.0, scales=("field",),
         text="Across the patterned lines, the orientation of the SAQP paper's cross-sections as "
              "described in its text; not compared with its drawings."),
]
NS_FIG_TEXT = {
    "2A/B": "The starting substrate.",
    "3A/B": "Punch-through-stopper implants: p-type under the nFET region, n-type under the pFET region.",
    "4A/B": "One shared Si/SiGe stack for both devices, over a high-Ge SiGe base layer.",
    "5A/B": "The stack patterned into lines, with shallow trench isolation between them.",
    "6A/B": "A dummy gate across the stacks.",
    "7A/B": "The pFET region protected by a liner and mask while the nFET region is opened.",
    "8A/B": "The nFET's high-Ge base layer removed selectively, leaving a cavity under its stack.",
    "9A/B": "Spacer dielectric deposited; it also fills the nFET's bottom-isolation cavity.",
    "12A/B": "The nFET's source/drain regions recessed, with the pFET protected.",
    "13A/B": "The nFET's lower-Ge SiGe indented, inner spacers formed and its source/drain grown.",
    "14A/B": "ILD deposited and polished, and the dummy gate removed.",
    "16A/B": "The nFET's lower-Ge SiGe removed in the gate region, releasing its Si channels.",
    "17A/B": "Separate work-function treatments for the nFET and the pFET, and an optional gate cut.",
    "18A/B": "Contacts, with the two gates contacted independently after the gate cut.",
    "10A/B": "The pFET's source/drain regions recessed through its high-Ge base layer and into the "
             "implanted substrate, with the nFET protected.",
    "11A/B": "The pFET's Si layers and high-Ge base indented, inner spacers formed so the lower-Ge SiGe "
             "remains as channels, and p-type source/drain grown from the SiGe edges and the substrate.",
    "15A/B": "With the nFET protected, the pFET's high-Ge base and Si layers removed in the gate "
             "region, keeping the lower-Ge SiGe sheets.",
    "19A/B": "An alternative arrangement in which the two devices share one gate.",
}
FIN_FIG_TEXT = {
    ("R24", "2A"): "The substrate, with optional wells, and a first mask and resist over it.",
    ("R24", "3A"): "The mask patterned and fins etched into the substrate.",
    ("R24", "4A"): "Isolation filled around the fins and planarised.",
    ("R24", "5A"): "The isolation recessed so the fins stand above it.",
    ("R24", "6A"): "A dummy-gate dielectric, dummy-gate material and mask deposited.",
    ("R24", "7A"): "The dummy gate patterned over the fins; optional lightly doped extensions.",
    ("R24", "16A"): "The fins recessed in the source/drain regions beside the gate spacers.",
    ("R24", "17A"): "Epitaxial source/drain grown in the recesses; merged neighbours are an alternative (Fig. 22).",
    ("R24", "18A"): "An etch-stop layer and ILD deposited and polished to expose the dummy gate.",
    ("R24", "19A"): "The dummy gate removed; its dielectric may stay or be removed.",
    ("R24", "20A"): "Replacement gate dielectric and metal deposited and polished.",
    ("R24", "21A"): "Further ILD, and contacts to the source/drain and to the gate.",
    ("R22", "1"): "The SAQP fin sequence: carbon cores at 96 nm pitch, an oxide first spacer, core removal, "
                  "transfer into an amorphous-Si second core at 48 nm, a second spacer to a 24 nm pitch, "
                  "and transfer through a silicon nitride hard mask into silicon.",
}
NS_PLANE_OF = dict(
    dummydep=["y1", "x2"], ghm=["y1", "x2"], gatepat=["y1", "x2"], dummy=["y1", "x2"],
    liner=["y1", "x2"], mask=["y1", "x2"], base=["x2", "y1"], unmask=["y1", "x2"], bottom=["x2", "y1"],
    spacerdep=["x2", "y1"], spaceretch=["x2", "y1"], recess=["x2", "y2"], indent=["x2"], inner=["x2"],
    epi=["x2", "y2"], ild=["x2", "y2"], pull=["y1", "x2"], release=["y1", "x2"], hkmg=["y1", "x2"],
    contacts=["x2", "y2"], done=["x2", "y2"])
FIN_PLANE_OF = dict(
    dummydep=["across_gate", "along_fin"], gatepat=["across_gate", "along_fin"],
    dummy=["across_gate", "along_fin"], recess=["along_fin", "across_sd"], epi=["along_fin", "across_sd"],
    ild=["along_fin", "across_sd"], pull=["across_gate", "along_fin"], hk=["across_gate", "along_fin"],
    metal=["across_gate", "along_fin"], openings=["along_fin", "across_sd"],
    contacts=["along_fin", "across_sd"])


def plane_view(pl, scale, bounds):
    """The camera for a plane at a scale: square on to the cut face, the kept half behind it."""
    b = bounds
    ym = (b["y"][0] + b["y"][1]) / 2 if scale != "site" else 40.0
    r = {"site": 255.0, "tile": 460.0, "field": 660.0, "pair": 440.0}[scale]
    if pl["axis"] == "x":
        return dict(n=pl["name"], s="section plane", az=1.5708, el=0.1, r=r,
                    tgt=[pl["pos"], min(ym, 60.0), (b["z"][0] + b["z"][1]) / 2 if scale != "site" else 0.0],
                    clip=[pl["pos"], None, None], scale=scale)
    return dict(n=pl["name"], s="section plane", az=0.0, el=0.1, r=r,
                tgt=[(b["x"][0] + b["x"][1]) / 2 if scale != "site" else 0.0, min(ym, 60.0), pl["pos"]],
                clip=[None, None, pl["pos"]], scale=scale)


def cut_by(parts, pl):
    """Names of the parts the plane passes through, in drawing order."""
    k = 0 if pl["axis"] == "x" else 2
    names = []
    for p in parts:
        for b in p["boxes"]:
            lo, hi = b[k] - b[k + 3] / 2, b[k] + b[k + 3] / 2
            if lo < pl["pos"] - 1e-6 and hi > pl["pos"] + 1e-6:
                if p["name"] not in names: names.append(p["name"])
                break
    return names


NS_P_PLANES = [
    dict(id="x1", name="Along the pFET stack, through the gate", short="Along pFET", axis="z", pos=0.0,
         scales=("site",),
         text="The patent's X1–X1 direction: along the pFET stack, crossing its gate. Direction from "
              "the patent's text; not compared with its drawings."),
] + NS_PLANES[1:]
NS_PAIR_PLANES = [
    dict(NS_PLANES[0], scales=("pair",)),
    dict(NS_P_PLANES[0], pos=-84.0, scales=("pair",)),
    dict(NS_PLANES[1], scales=("pair",),
         text="The patent's Y1–Y1 direction: across both stacks through the gate region, where the gate "
              "line joins them or is cut. Direction from the patent's text; not compared with its drawings."),
    dict(NS_PLANES[2], scales=("pair",)),
]
FIN_PAIR_PLANES = [
    dict(FIN_PLANES[0], name="Across both fin pairs, at the gate", scales=("pair",)),
    dict(FIN_PLANES[2], name="Across both fin pairs, through the drains", scales=("pair",)),
    dict(FIN_PLANES[1], id="along_nfin", name="Along an nFET fin", short="Along nFET fin", scales=("pair",)),
    dict(FIN_PLANES[1], id="along_pfin", name="Along a pFET fin", short="Along pFET fin", pos=13.5 - 81.0,
         scales=("pair",)),
]
PW_PLANES = [
    dict(id="pw_across", name="Across the lines, mid-length", short="Across lines", axis="x", pos=0.0,
         scales=("field",),
         text="Across the lines, the orientation of F3's SAQP cross-sections as described in its text; "
              "not compared with its drawings."),
]


NS_P_PLANE_OF = dict(NS_PLANE_OF, p_recess=["x1", "y2"], p_indent=["x1"], p_inner=["x1"], p_epi=["x1", "y2"],
                     p_release=["y1", "x1"], p_hkmg=["y1", "x1"], p_contacts=["x1", "y2"], p_done=["x1", "y2"],
                     spaceretch=["x1", "y1"])
FIN_PAIR_PLANE_OF = dict(p_epi=["across_sd", "along_pfin"], epi=["across_sd", "along_nfin"],
                         recess=["across_sd"], p_open=["across_sd"], n_open=["across_sd"])


def attach_sections(key, flow, dev):
    tech = "fin" if key.startswith("fin") or key == "pitchwalk" else "ns"
    planes = dict(pitchwalk=PW_PLANES, ns_p=NS_P_PLANES, ns_pair=NS_PAIR_PLANES,
                  fin_pair=FIN_PAIR_PLANES).get(key, FIN_PLANES if tech == "fin" else NS_PLANES)
    plane_of = dict(ns_p={k: [("x1" if x == "x2" else x) for x in v] for k, v in NS_P_PLANE_OF.items()},
                    fin_pair=FIN_PAIR_PLANE_OF).get(key, FIN_PLANE_OF if tech == "fin" else NS_PLANE_OF)
    if key == "ns_pair":
        plane_of = {k: (["x1", "y1"] if k.startswith("p_") else ["x2", "y1"]) for k in
                    {st["id"] for st in flow["steps"]}}
        for k in ("gatecut", "contacts_cut", "shared", "cut_etch", "hkmg", "pull", "dummy"): plane_of[k] = ["y1"]
    if key == "fin_pair":
        plane_of = dict({st["id"]: ["across_gate"] for st in flow["steps"]}, **FIN_PAIR_PLANE_OF)
    final = {p["id"]: p for p in dev.parts}
    scales = sorted({st["scale"] for st in flow["steps"]})
    secs = []
    for pl in planes:
        views = {}
        for sc in scales:
            if sc not in pl.get("scales", ("site", "tile")): continue
            b = next((st["bounds"] for st in flow["steps"] if st["scale"] == sc and "bounds" in st), None) \
                if sc != "site" else dev.bounds
            if b is None: continue
            vk = f"sec_{pl['id']}" + ("" if sc == "site" else "_" + sc[0])
            flow["views"][vk] = plane_view(pl, sc, b)
            views[sc] = vk
        if views:
            secs.append(dict(id=pl["id"], name=pl["name"], short=pl["short"], axis=pl["axis"],
                             pos=round(pl["pos"], 4), text=pl["text"], views=views))
    flow["sections"] = secs
    byid = {s["id"]: s for s in secs}
    for st in flow["steps"]:
        if not st["figs"]: continue
        src = (st.get("src") or ["R13" if tech == "ns" else "R24"])[0]
        if tech == "ns":
            described = " ".join(NS_FIG_TEXT[f] for f in st["figs"] if f in NS_FIG_TEXT)
        else:
            described = " ".join(dict.fromkeys(FIN_FIG_TEXT[(src, f[:-1] + "A" if src == "R24" and f[-1] in "ABC" else f)]
                                               for f in st["figs"]))
        want = plane_of.get(st["id"]) or ([planes[0]["id"] if key == "pitchwalk" else "field_across"]
                                          if st["scale"] == "field" else
                                          [planes[0]["id"] if tech == "fin" else "y1"])
        parts = [final[x] if isinstance(x, str) else x for x in st["parts"]]
        entries = []
        for pid in want:
            pl = byid.get(pid)
            if not pl or st["scale"] not in pl["views"]: continue
            entries.append(dict(plane=pid, figs=st["figs"], src=src, described=described,
                                visible=cut_by(parts, next(p for p in planes if p["id"] == pid)),
                                omitted=list(st["omitted"]) + (
                                    ["The source's figures show the pFET beside the nFET; this site "
                                     f"view shows the {'pFET' if key == 'ns_p' else 'nFET'} only"]
                                    if tech == "ns" and st["scale"] == "site" else []),
                                status="text", status_text=TEXT_STATUS))
        if entries: st["compare"] = entries


def main():
    out = {}
    refs = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "data/references.json")))["sources"]}
    docs = []
    for key, fn in FLOWS.items():
        dev, steps, extra = fn(out)
        if any(st["figs"] for st in steps):
            whole = dict(extra, steps=steps)
            attach_sections(key, whole, dev)
            extra["sections"] = whole["sections"]
        out[key] = dict(extra, steps=steps, badge={k: BADGE[k] for k in extra["match"]},
                        badge_note={BADGE[k]: BADGE_NOTE[BADGE[k]] for k in extra["match"]})
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
