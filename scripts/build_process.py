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
        # Core steps count 1, 2, 3...; the operations leading to core step n are n.1, n.2...,
        # counted along each route: an operation shared by every route after a route's own
        # ones carries its number in each route ("labels"), the first route's as "label".
        routes = list(dict.fromkeys(st["route"] for st in self.steps if st.get("route"))) or [None]
        core, ops = 0, {}
        for k, st in enumerate(self.steps):
            if st["level"] == "core":
                core += 1; ops = {r: 0 for r in routes}; st["label"] = str(core)
            else:
                nxt = next((x for x in self.steps[k + 1:] if x["level"] == "core"), None)
                if nxt is None or nxt["id"] != st["of"]:
                    sys.exit(f"{self.dev.key}: operation '{st['id']}' must lead into core step '{st['of']}'")
                lab = {}
                for r in routes:
                    if st.get("route") in (None, r):
                        ops[r] += 1; lab[r] = f"{core + 1}.{ops[r]}"
                st["label"] = lab[st.get("route") or routes[0]]
                if not st.get("route") and len(set(lab.values())) > 1: st["labels"] = lab
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
            "been compared with these views, and F1's A/B/C section lines are not yet mapped onto "
            "the app's views.",
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
            "is modelled."],
        refs=["R24", "R25", "R22", "R23", "R27", "R26", "R7", "R8", "R16", "R19", "R20", "R21"],
        match={k: v for k, v in dict(MATCH, **PAT_MATCH, **FIN_MATCH).items() if k in used},
        routes=FIN_ROUTES,
        route_title="How the fins are printed", route_join="the fin etch",
        views=dict(cut=FIN_CUT, sd=FIN_SD, cexp=FIN_CEXP, **FIN_TILE_VIEWS, **FIN_FIELD_VIEWS))


FLOWS = {"ns": flow_ns, "fin": flow_fin, "sadp": lesson("sadp"), "saqp": lesson("saqp")}


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
           "nanosheet audit above)."] if flow.get("lesson") else [
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
            "field": "zoom out to the line field around the tile"}
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
    if flow["skipped"]:
        md += ["", "## Source figures not mapped to a state", ""]
        md += [f"- **Fig. {k}**: {v}" for k, v in flow["skipped"].items()]
    md += ["", "## Not yet verified", ""]
    md += ["- " + t for t in flow["audit_unverified"]] if "audit_unverified" in flow else [
           "- **Every figure mapping.** The patent's drawings have not been compared with these views; "
           "orientation, composition and labels may differ from the published artwork.",
           "- Views, cut directions and left/right are the app's own; the patent's section lines "
           "(X1–X1, X2–X2, Y1–Y1, Y2–Y2) are not yet mapped onto the app's axes.",
           "- The lithography operations (resist, exposure, development) are concept-level: no "
           "optics, dose, resist chemistry, overlay or mask count is modelled or claimed."]
    if (routes or flow.get("lesson")) and "audit_unverified" not in flow:
        md += ["- **Patterning routes.** SADP and SAQP are a patterning concept applied to an "
               "illustrative layer: the sources do not say this stack is patterned that way. P, P/2 "
               "and P/4 are ideal (real spacer images show pitch walk); core, spacer and film "
               "materials and thicknesses are illustrative; which lines a cut or block pattern "
               "removes is integration-dependent, and no overlay or placement error is modelled."]
    md += ["", "## Sources cited", ""]
    md += [f"- **[{r}]** {refs[r]['title']} — {refs[r]['publisher']}. <{refs[r]['url']}>"
           for r in flow["refs"]]
    return "\n".join(md) + "\n"


def main():
    out = {}
    refs = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "data/references.json")))["sources"]}
    docs = []
    for key, fn in FLOWS.items():
        dev, steps, extra = fn(out)
        out[key] = dict(extra, steps=steps, badge={k: BADGE[k] for k in extra["match"]})
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
