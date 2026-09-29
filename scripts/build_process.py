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
import json, os, re, sys
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
                    "schematic drawing, not a copy of the source's figure.",
    "Reconstruction": "Reconstruction: a state between two stages the source describes, filled in "
                      "for teaching.",
    "Teaching": "Teaching: built for teaching, with no source figure. Where noted, it differs "
                "from the cited source's own route.",
    "Concept": "Concept: a general operation, such as lithography or pitch splitting. It is not a "
               "published figure."}
MATCH = {
    "published": "Source stage, adapted nFET view; artwork not compared",
    "intermediate": "Reconstruction between source-described stages",
    "concept": "Concept-only operation",
    "context": "Source stage, adapted view with pFET context; artwork not compared",
}

# ------------------------------------------------------------------ helpers
def span(part):
    """A part's bounding box over all its boxes, as lim() gives one box's."""
    bs = [lim(b) for b in part["boxes"]]
    return tuple(f(v[k] for v in bs) for k, f in enumerate((min, max, min, max, min, max)))


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
NS_SCOPE = ("How a silicon nanosheet nFET is made with a replacement metal gate. The steps follow "
            "the nFET branch of one published integration route [R13]: a p-type punch-through "
            "stopper plus full bottom dielectric isolation. Materials and dimensions are "
            "illustrative. This is not a verified foundry recipe.")

# Figure identifiers name process states described in R13's text. Its drawings have not
# been compared with these views, so no state claims to reproduce a drawing.
NS_FIGURES = ("Figure numbers are those of US 2023/0420457 A1, the published application of "
              "US 12,568,683 B2 [R13]. Each state was compared with the drawing it names (docs/nsfet). The "
              "views are the app's own reconstructions, in its own frame and proportions, so their "
              "orientation may differ from the drawing's.")
NS_BRANCH = ("The patent makes a pFET and an nFET from one shared stack. This lesson follows "
             "the nFET only. The pFET steps (Figs. 10–11 and 15), and the pFET drawn beside the nFET in "
             "other figures, are left out here. They are in the pFET flow. Both sites shows the "
             "two together, with a choice of gate cut or shared gate. The 2 × 2 tile's four "
             "sites give context for the patterning; only the selected nFET becomes a finished "
             "device. The labels under each step say what each region is doing at that point.")

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
              tgt=[-36.5, 55, -34], clip=None, scale="tile"),
    tileplan=dict(n="Tile from above", s="plan view", az=0.0, el=1.45, r=560,
                  tgt=[-36.5, 0, -34], clip=None, scale="tile"),
    tilecut=dict(n="Across the lines", s="section through the selected gate", az=1.5708, el=0.14,
                 r=470, tgt=[0, 40, -34], clip=[0, None, None], scale="tile"),
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

# The Process stack (bd.NS_PROCESS_STACK), said where it shows.
NS_STACK_SUB = ("Both layers are drawn 7 nm thick, a 14 nm vertical pitch (sheet thickness plus clear "
                "gap). In this route the Si layers become the nFET's channels and the 25 %-Ge SiGe layers "
                "the pFET's, so both must be channel-thin. The Ge contents are the patent's (about 50 % in "
                "the base layer, about 25 % in the others). The 7 nm thicknesses are the model's, not the patent's")
NS_FILMS_SUB = ("Each sheet gets 0.5 nm SiO₂, 1.5 nm HfO₂ and 1.5 nm work-function metal. At these "
                "illustrative thicknesses the films meet in the 7 nm gaps between the sheets. "
                "Real gaps and films vary, and they decide whether any fill metal gets between the sheets")

HKMG_SUB = ("The patent's n-type metals are Hf, Zr, Ti, Ta, Al and their alloys and carbides; an "
            "Al-containing metal is drawn. The interfacial oxide and the film thicknesses are the "
            "model's. The W fill is the patent's")


def flow_ns(done):
    # The Process stack, not Device mode's spaced-out one: its SiGe layers are the pFET's
    # channels in the pFET and Both sites flows (see bd.NS_PROCESS_STACK).
    dev = bd.build_ns(bd.NS_PROCESS_STACK)
    F = Flow(dev)
    P = F.final
    # Everything is read off the finished parts, so the flow cannot drift from them.
    sheets = [lim(P[f"sheet{i}"]["boxes"][0]) for i in (1, 2, 3)]
    hz = sheets[0][5]
    ys = [(s[2], s[3]) for s in sheets]
    bdi = lim(P["bdi"]["boxes"][0]); STI = bdi[3]
    sub = lim(P["substrate"]["boxes"][0]); zsub = sub[5]
    pts = lim(P["pts"]["boxes"][0]); ypts = pts[2]           # bottom of the implanted layer
    cap = span(P["gatecap"]); ymo, ycap, hzmo = cap[2], cap[3], cap[5]
    YHMs = ycap + 6.0                     # the dummy gate fills the gate's full height; its hard mask sits above
    top = ys[-1][1]
    sige = bd.gaps(STI, top, ys)                       # the layers between the sheets
    TOX = 1.0                                          # dummy-gate oxide
    TSP = XSP - XG                                     # spacer film: its thickness is the spacer width

    def layers(x0, x1, z0=-hz, z1=hz, sheets_final=False):
        """Lower-Ge SiGe and Si alternating from the bottom layer up to the top sheet."""
        F.drop("sige1", "sige2", "sige3", "si1", "si2", "si3", "sheet1", "sheet2", "sheet3")
        for i, (a, b) in enumerate(sige):
            F.put(tmp(f"sige{i+1}", f"SiGe, about 25 % Ge · sacrificial layer {i+1}", "sige", "Superlattice",
                      [box(x0, x1, a, b, z0, z1)]))
        for i, (a, b) in enumerate(ys):
            if sheets_final: F.add(f"sheet{i+1}")
            else: F.put(tmp(f"si{i+1}", f"Si · future nanosheet {i+1}", "silicon", "Superlattice",
                            [box(x0, x1, a, b, z0, z1)]))

    def bottom(x0, x1, z0=-hz, z1=hz):
        F.put(tmp("bsige", "SiGe base layer, about 50 % Ge · sacrificial", "sige", "Superlattice",
                  [box(x0, x1, 0, STI, z0, z1)], (0, -.6, 0)))

    def ild_around(ytop=None):
        """The ILD around everything, up to the gate cap's top, or [ytop]: at the contacts, up
        to the S/D metal's top, so the contacts fill holes in it."""
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]]
        F.put(tmp("ild", "ILD (low-κ)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, ytop or ycap, -zsub, zsub), others), (0, .6, 0)))

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
                 f"its width. The tile's gate pitch is about {PG:.0f} nm; a real contacted gate pitch "
                 f"at these nodes is about 45–48 nm (a typical value, not from the cited sources). The stack pitch "
                 f"({PS:.0f} nm) is enlarged too. Real active pitches are a few tens of nm, which is why "
                 "pitch splitting is used"]

    def t_multilayer(lines):
        """The multilayer, blanket over the window, or on each stack line once patterned.
        On the pFET line the patent's route keeps different layers, so they are not named
        sacrificial there."""
        T.drop_prefix("t_ml_")
        x0, x1 = (WX0, WX1) if lines else (SX0, SX1)        # blanket films cover the whole tile
        spans = [("all", WZ0, WZ1, "")] if not lines else \
                [(k, zc - hz, zc + hz, " · " + ("nFET line" if k == "n" else "pFET line (context)")) for zc, k in LINES]
        for k, z0, z1, where in spans:
            T.put(tmp(f"t_ml_base_{k}", "SiGe base layer, about 50 % Ge · sacrificial" + where, "sige", GL,
                      [box(x0, x1, 0, STI, z0, z1)], (0, -.6, 0)))
            for i, (a, b) in enumerate(sige):
                T.put(tmp(f"t_ml_sige{i+1}_{k}", f"SiGe, about 25 % Ge · layer {i+1}" + where, "sige", GL,
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
            "A hard-mask film is deposited over the multilayer. The view zooms out to a tile of four "
            "sites. Two stack lines will run along the channel: one for nFETs through the selected "
            "site, one for pFETs beside it. Two gate lines will cross them later. "
            "Only the selected nFET site is carried to a finished "
            "device; the other three show the pattern's context. The implanted stoppers differ by "
            "region: p-type under the nFET line, n-type under the pFET line [R13].", view="tile", of="pattern",
            match="intermediate", figs=["3A/B", "5A/B"],
            subs=TILE_SUBS + ["Hard-mask material and thickness are illustrative"],
            omitted=["The masks that kept each stopper implant to its own region"], deposit=["t_hm"])
        T.route = "direct"          # the routes part here: how the hard mask gets its lines
        t_resist("t_res", "Photoresist (coated)", "resist", [box(SX0, SX1, top + HMT, top + HMT + RT, WZ0, WZ1)])
        T.snap("coat", "Resist coat",
            "A light-sensitive photoresist is spun on over the hard mask. The resist takes the "
            "pattern first; the hard mask then carries it into the stack [R16]. Coat, expose, "
            "develop and etch is a cycle repeated many times in making a chip [R17].", view="tile",
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
            "the wafer: it sits in the scanner and is imaged down through its optics. It is drawn "
            "above the wafer only to show which areas its chrome keeps dark. This example uses a "
            "positive-tone resist: the exposed resist between the future stack lines becomes "
            "soluble, and the resist over the lines stays as it was. Light does not etch "
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
            "A directional etch cuts the hard mask where the resist is open. The resist pattern "
            "is now a hard-mask pattern [R16].", view="tilecut",
            of="pattern", match="intermediate", figs=["5A/B"])
        T.drop("t_res")
        T.snap("strip", "Resist strip",
            "The leftover resist is stripped. The hard mask alone now defines the stack lines.",
            view="tilecut", of="pattern", match="intermediate", figs=["5A/B"])
        T.route = None
        pitch_routes(F, T, dict(
            what="stack", of="pattern", group=GL, anchor=0.0, drop=[], cut_note="",
            hm_shared=True, layer_x=(SX0, SX1),
            lines="two stack lines", hz=hz, PS=PS, win=(WX0, WX1, WZ0, WZ1), top=top, HMT=HMT, ysub=sub[2],
            layers=[("ml_base", "SiGe base layer, about 50 % Ge · sacrificial", "sige", 0, STI, (0, -.6, 0))] +
                   [(f"ml_sige{i+1}", f"SiGe, about 25 % Ge · layer {i+1}", "sige", a, b, (0, 0, 0)) for i, (a, b) in enumerate(sige)] +
                   [(f"ml_si{i+1}", f"Si · layer {i+1}", "silicon", a, b, (0, 0, 0)) for i, (a, b) in enumerate(ys)]))
        t_multilayer(lines=True)
        T.drop("t_pts_n", "t_pts_p")
        for zc, k in LINES:
            T.put(tmp(f"t_pts_{k}", ("p-type punch-through stopper · nFET sub-fin" if k == "n"
                                     else "n-type punch-through stopper · pFET sub-fin"),
                      "pts" if k == "n" else "pts_n", GS, [box(SX0, SX1, ypts, 0, zc - hz, zc + hz)], (0, -1.0, 0)))
        T.snap("stacketch", "Stack etch",
            "A directional etch cuts the open areas through the multilayer and into the substrate. "
            "Narrow stacks are left standing on short sub-fins, each still capped by the hard mask. "
            "Silicon and SiGe etch alike here; the hard mask protects the lines [R13].",
            view="tilecut", of="pattern", match="intermediate", figs=["5A/B"])
        T.put(tmp("t_sti", "STI low-κ dielectric (filled and polished)", "lowk", GS,
                  subtract((SX0, SX1, ypts, top + HMT, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stifill", "STI fill and CMP",
            "Oxide overfills the trenches and is polished flat by CMP (chemical-mechanical "
            "polishing). The polish stops on the hard mask.", view="tilecut", of="pattern", match="intermediate", figs=["5A/B"])
        T.drop("t_sti", "t_hm")
        T.put(tmp("t_sti", "STI (low-κ dielectric)", "lowk", GS,
                  subtract((SX0, SX1, ypts, 0, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stirecess", "STI recess and hard-mask removal",
            "The oxide is etched back to the bottom of the SiGe base layer (about 50 % Ge), leaving that "
            "layer's sidewalls open. The hard mask is removed. The oxide now isolates neighbouring stacks "
            "sideways: shallow trench isolation (STI) [R13]. Next, the view returns to the selected site.",
            view="tile", of="pattern", match="context", figs=["5A/B"],
            subs=["The hard mask is removed here for clarity; flows differ on when it goes"])

    def tile_dummy():
        """Dummy-gate patterning across both stack lines (the core step 'dummy')."""
        for zc, k in LINES:
            T.put(tmp(f"t_dox_{k}", "Dummy-gate oxide (grown on the stack)", "sio2", "Dummy gate",
                      subtract((WX0, WX1, 0, top + TOX, zc - hz - TOX, zc + hz + TOX), T.boxes()), (0, .6, 0)))
        T.put(tmp("t_dsi", "Dummy gate Si (as deposited)", "poly", "Dummy gate",
                  subtract((WX0, WX1, 0, ycap, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
        T.put(tmp("t_dhm", "Gate hard mask (blanket)", "si3n4", "Dummy gate",
                  [box(WX0, WX1, ycap, YHMs, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("dummydep", "Dummy-gate stack deposition",
            "A thin oxide grows on the exposed Si and SiGe of both stack lines. Silicon is then "
            "deposited over everything and planarised, and a gate hard mask goes on top [R13].",
            view="tile", of="dummy", match="intermediate", figs=["6A/B"],
            subs=["The patent suggests amorphous Si; the model's dummy Si is illustrative"])
        gl = [(xg - XG, xg + XG) for xg in GATES]
        t_resist("t_gres", "Photoresist (coated)", "resist", [box(WX0, WX1, YHMs, YHMs + RT, WZ0, WZ1)])
        T.snap("gcoat", "Gate resist coat",
            "Resist is spun on over the gate hard mask, as for the stacks [R16].", view="tile",
            of="dummy", match="concept", deposit=["t_gres"])
        T.drop("t_gres")
        t_resist("t_gres", "Photoresist (unexposed: over the gates)", "resist",
                 [box(a, b, YHMs, YHMs + RT, WZ0, WZ1) for a, b in gl])
        t_resist("t_gres_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 [box(a, b, YHMs, YHMs + RT, WZ0, WZ1) for a, b in bd.gaps(WX0, WX1, gl)])
        T.put(tmp("t_greticle", "Reticle chrome (in the scanner; not to scale)", "chrome", "Patterning",
                  [box(a, b, RY, RY + 2.0, WZ0, WZ1) for a, b in gl], (0, 2.0, 0)))
        T.snap("gexpose", "Gate exposure",
            "The gate lines are exposed across the stacks. The reticle's chrome keeps the resist "
            "over each future gate dark, and the rest becomes soluble [R16].", view="tile",
            of="dummy", match="concept", subs=["Exposure is simplified, as for the stacks"])
        T.drop("t_greticle", "t_gres_x", "t_dhm")
        for g, (a, b) in enumerate(gl):
            T.put(tmp(f"t_ghm{g}", f"Gate hard mask {g + 1}", "si3n4", "Dummy gate",
                      [box(a, b, ycap, YHMs, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("ghm", "Development and gate hard-mask etch",
            "The developer clears the exposed resist. A directional etch then copies the resist "
            "lines into the gate hard mask [R16].", view="tile", of="dummy", match="intermediate", figs=["6A/B"])
        T.drop("t_gres", "t_dsi", "t_dox_n", "t_dox_p")
        for g, xg in enumerate(GATES):
            for zc, k in LINES:
                T.put(tmp(f"t_dox_{k}{g}", "Dummy-gate oxide", "sio2", "Dummy gate",
                          subtract((xg - XG, xg + XG, 0, top + TOX, zc - hz - TOX, zc + hz + TOX), T.boxes()), (0, .6, 0)))
        for g, xg in enumerate(GATES):
            T.put(tmp(f"t_dummy{g}", f"Dummy gate {g + 1} · Si", "poly", "Dummy gate",
                      subtract((xg - XG, xg + XG, 0, ycap, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
            T.put(tmp(f"t_ghm{g}", f"Gate hard mask {g + 1}", "si3n4", "Dummy gate",
                      [box(xg - XG, xg + XG, ycap, YHMs, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("gatepat", "Dummy-gate etch and resist strip",
            "The dummy stack is etched down to the STI through the gate hard mask, and the resist is "
            "stripped. Two gate lines now cross both stack lines: four sites. On each stack line, "
            "the two sites share the source/drain between their gates. Each gate line crosses an nFET "
            "and a pFET site; without a gate cut (not drawn), those two would share one gate. "
            "Only the selected nFET is completed. Next, the view returns to the selected "
            "site, which shows its gate only across its own stack.",
            view="tile", of="dummy", match="context", figs=["6A/B"],
            omitted=["The gate cut between the lines, which the patent makes later (Fig. 17)"])

    def tile_open():
        """Opening the nFET region while the pFET is protected (the core step 'bottom')."""
        win = (WX0, WX1, 0, YHMs + 1.5, WZ0, WZ1)
        T.put(tmp("t_liner", "Oxide liner (SiO₂)", "liner", "Patterning", conformal(T.boxes(), 1.5, win), (0, .8, 0)))
        T.snap("liner", "Protective liner",
            "A thin protective liner is deposited over the whole tile, covering both regions [R13].",
            view="tile", of="bottom", match="intermediate", figs=["7A/B"],
            subs=["Liner material and thickness are illustrative"])
        liner = T.now["t_liner"]
        t_resist("t_bres", "Photoresist (coated)", "resist",
                 subtract((WX0, WX1, 0, YHMs + 12.0, WZ0, WZ1), T.boxes()))
        T.snap("bcoat", "Block-mask resist coat",
            "Resist is spun on over the whole tile, filling in around the gates [R16].",
            view="tile", of="bottom", match="concept", deposit=["t_bres"])
        T.drop("t_bres")
        others = T.boxes()
        t_resist("t_block", "Photoresist block over the pFET region", "resist",
                 subtract((WX0, WX1, 0, YHMs + 12.0, WZ0, ZMID), others))
        t_resist("t_bres_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 subtract((WX0, WX1, 0, YHMs + 12.0, ZMID, WZ1), others))
        T.put(tmp("t_breticle", "Reticle chrome (in the scanner; not to scale)", "chrome", "Patterning",
                  [box(WX0, WX1, RY, RY + 2.0, WZ0, ZMID)], (0, 2.0, 0)))
        T.snap("bexpose", "Block-mask exposure",
            "The reticle's chrome covers the pFET region, so the resist there stays as it was. Over "
            "the nFET region the resist becomes soluble [R16].", view="tile", of="bottom", match="concept",
            subs=["Exposure is simplified, as for the stacks"])
        T.drop("t_breticle", "t_bres_x")
        T.put(tmp("t_liner", "Protective liner · pFET region", "liner", "Patterning",
                  clip(liner["boxes"], (WX0, WX1, 0, YHMs + 1.5, WZ0, ZMID)), (0, .8, 0)))
        T.snap("mask", "nFET-open mask",
            "The developer clears the exposed resist, leaving a block over the pFET region. The "
            "liner is then etched away where the resist is open, over the nFET region. The pFET line "
            "stays sealed. The nFET line's sidewalls are exposed, including those of its SiGe base "
            "layer (about 50 % Ge) [R13].",
            view="tile", of="bottom", match="context", figs=["7A/B"])
        T.drop("t_ml_base_n")
        T.snap("base", "nFET base-layer removal",
            "A selective etch removes the SiGe base layer (about 50 % Ge) from the nFET line only. It "
            "works in from the exposed sides and on under both dummy gates, which hold the stack up "
            "over the cavity. The pFET line, sealed by liner and resist, keeps its base layer [R13].",
            view="tilelow", of="bottom", match="context", figs=["8A/B"],
            subs=["The etch front is not modelled: only the before and after shapes are drawn"])
        T.drop("t_block")
        T.snap("unmask", "Mask strip",
            "The resist block is stripped. The liner stays on the pFET region for now. Next, the view "
            "returns to the selected site, where the cavity is filled.",
            view="tile", of="bottom", match="intermediate", figs=["8A/B"],
            omitted=["What happens to the pFET line next (Figs. 10–11, 15)"])

    # 1
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", "Substrate & isolation",
              [box(sub[0], sub[1], sub[2], 0, -zsub, zsub)], (0, -1.2, 0)))
    F.snap("substrate", "Silicon substrate",
        "The flow starts from a crystalline silicon wafer, cleaned and ready for epitaxy (growing "
        "new crystal on the crystal below). Everything above it is grown, deposited or etched in "
        "the steps that follow.",
        match="published", figs=["2A/B"])
    # 2
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", "Substrate & isolation",
              [box(sub[0], sub[1], sub[2], ypts, -zsub, zsub)], (0, -1.2, 0)))
    F.put(tmp("pts0", "p-type punch-through stopper (implanted)", "pts", "Substrate & isolation",
              [box(sub[0], sub[1], ypts, 0, -zsub, zsub)], (0, -1.0, 0)))
    F.snap("pts", "Punch-through-stopper implant",
        "Dopant is implanted just below the surface: p-type under this nFET. This punch-through "
        "stopper blocks leakage through the silicon beneath the future channels. In the route "
        "followed here [R13] it is used together with the bottom dielectric isolation made "
        "later; the two are not alternatives. The pFET region beside it (not shown) gets an "
        "n-type stopper. The layer's depth is illustrative and it has no edge line: real "
        "profiles are graded, and dose, energy and diffusion are not modelled.",
        match="published", figs=["3A/B"],
        subs=["Stopper depth and a uniform doped region are illustrative"],
        omitted=["The pFET region and its n-type stopper"])
    # 3
    bottom(sub[0], sub[1], -zsub, zsub)
    layers(sub[0], sub[1], -zsub, zsub)
    F.snap("superlattice", "Si/SiGe multilayer epitaxy",
        "One alternating stack is grown as a single crystal: a SiGe base layer (about 50 % Ge), then "
        "25 %-Ge SiGe and Si in turn. For this nFET the Si layers become the channels. The "
        "25 %-Ge SiGe is removed from the gate region later. The base layer can be etched "
        "selectively against the other SiGe, which the isolation step uses. In the patent the "
        "same stack also makes a SiGe-channel pFET, where different layers survive. So not every "
        "SiGe layer is sacrificial everywhere [R13].",
        match="published", figs=["4A/B"],
        subs=[NS_STACK_SUB],
        omitted=["The pFET's use of the same stack"])
    # 4
    tile_patterning()
    bottom(-XSD, XSD)
    layers(-XSD, XSD)
    F.drop("wafer", "pts0"); F.add("substrate", "pts", "sti")
    same_site(T, F, SITE4, "stack patterning")
    F.snap("pattern", "Stack patterning and STI",
        "A hard mask defines narrow stacks. A directional etch cuts through the multilayer "
        "and into the substrate, leaving a short sub-fin that keeps the implanted stopper. "
        "Trench oxide is deposited, planarised and recessed to the bottom of the SiGe base layer "
        "(about 50 % Ge), leaving its sidewalls open for its later removal [R13]. This shallow "
        "trench isolation (STI) isolates neighbouring devices sideways; it is not the bottom "
        "isolation. How the stack pattern is made depends on the layer, pitch and process. A "
        "direct print (EUV single exposure, for example) allows different sheet widths [R18]. "
        "Dense arrays can use spacer-based pitch splitting instead. The Steps tab's patterning "
        "route shows SADP, the default here, beside SAQP and a direct print.",
        match="published", figs=["5A/B"],
        subs=["Stack width, pitch and trench depth are illustrative"])
    # 5
    tile_dummy()
    dox = subtract((-XG, XG, 0, top + TOX, -hz - TOX, hz + TOX), F.boxes())
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", "Dummy gate", dox, (0, .6, 0)))
    poly = subtract((-XG, XG, 0, ycap, -hzmo, hzmo), F.boxes())
    F.put(tmp("dummy", "Dummy gate · a-Si", "poly", "Dummy gate", poly, (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ycap, YHMs, -hzmo, hzmo)], (0, 1.4, 0)))
    same_site(T, F, SITE5, "dummy-gate patterning")
    F.snap("dummy", "Dummy gate stack",
        "A thin sacrificial oxide, a silicon placeholder gate and a hard mask are deposited and "
        "patterned across the stack [R13]. This dummy gate fixes where the gate goes and how long it "
        "is. The real high-κ/metal gate replaces it near the end (replacement metal gate) [R13].",
        match="published", figs=["6A/B"],
        subs=["The patent suggests amorphous Si under a nitride/oxide hard mask; this model's "
              "dummy Si and nitride hard mask are illustrative",
              "The thin oxide under the dummy gate is conventional; the patent shows only the a-Si and "
              "its hard mask"])
    # 6
    tile_open()
    F.drop("bsige")
    same_site(T, F, SITE5, "nFET opening")
    F.snap("bottom", "nFET opening and base-layer removal",
        "A selective etch removes the nFET's SiGe base layer (about 50 % Ge), leaving a cavity "
        "under the stack. First a protective liner and mask cover the pFET region and open the "
        "nFET (Fig. 7, not shown here). Outside the dummy gate the nFET stack's sidewalls are "
        "exposed, including the base layer's, which the STI recess left open. The etch works in "
        "from those sides and on under the dummy gate, which holds the stack up over the cavity. "
        "The 25 %-Ge SiGe layers stay until channel release [R13].", view="cutb",
        match="published", figs=["7A/B", "8A/B"],
        subs=["The etch front is not modelled: only the before and after shapes are drawn"],
        omitted=["The protective liner and mask over the pFET region (Fig. 7)"])
    # 7
    window = (-XSD, XSD, 0, YHMs + TSP, -hzmo, hzmo)
    F.put(tmp("spfilm", "SiBCN spacer film (as deposited)", "sibcn", "Spacers",
              film(TSP, window), (0, .5, 0)))
    F.snap("spacerdep", "Conformal spacer deposition",
        "A conformal spacer dielectric (one that coats every surface evenly) is deposited over "
        "every exposed surface. It also fills the cavity under the stack. The film in the cavity "
        "becomes the bottom dielectric isolation (BDI) [R13]; it is drawn thick enough to close "
        "the cavity. BDI has been studied for cutting sub-channel leakage and effective "
        "capacitance [R15]. The film is drawn only within the gate's width, where this model's "
        "cell ends.", view="cutb",
        match="published", figs=["9A/B"],
        subs=["The patent's examples for this one film are SiOC, SiCN, SiOCN and SiBCN; SiBCN is "
              "drawn, for the spacers and the BDI alike"])
    # 8
    F.drop("spfilm"); F.add("bdi", "spacer_source", "spacer_drain")
    F.snap("spaceretch", "Spacer etch-back",
        "The spacer film is etched back over the nFET, stopping on the top of the BDI. It stays on "
        "the dummy-gate sidewalls as the outer spacers, and in the filled cavity as the BDI under "
        "the whole stack. In the patent the nFET first keeps its unetched film through all the "
        "pFET's steps (Figs. 10–11), which protects it. The etch-back then happens with an AlOₓ "
        "liner and a mask over the pFET [R13].", view="cutb",
        match="published", figs=["12A/B"],
        omitted=["The pFET's steps in between, and the liner and mask over it (see Both sites)"])
    # 9
    layers(-XSP, XSP, sheets_final=True)
    F.snap("recess", "nFET source/drain recess",
        "Under the same mask, the nFET stack outside the gate and spacers is etched away. The "
        "etch stops on the BDI, which stays under the future source and drain. The "
        "ends of every Si and SiGe layer are now exposed at the recess walls [R13].",
        match="published", figs=["12A/B"],
        omitted=["The pFET's own recess and epitaxy (Figs. 10–11) and the nFET protective mask"])
    # 10
    for i, (a, b) in enumerate(sige):
        F.put(tmp(f"sige{i+1}", f"SiGe, about 25 % Ge · sacrificial layer {i+1}", "sige", "Superlattice",
                  [box(-XG, XG, a, b, -hz, hz)]))
    F.snap("indent", "SiGe indent",
        "A selective etch recesses the exposed 25 %-Ge SiGe ends sideways and leaves the Si sheet "
        "ends in place [R13][R14]. The small cavities it opens under the spacers set the shape of "
        "the inner spacers. Stopping at the gate edge is a schematic target, not a perfect "
        "alignment. This is a partial recess, not the channel release.", view="cutb",
        match="intermediate", figs=["13A/B"])
    # 11
    F.add("inner_source", "inner_drain")
    F.snap("inner", "Inner-spacer deposition and etch-back",
        "Dielectric is deposited into the cavities; it also coats every other exposed surface. An "
        "etch-back leaves it only in the cavities and exposes the Si sheet ends again. These "
        "inner spacers sit between the sheets. They separate the future gate from the source and "
        "drain and reduce the capacitance between them [R1]. The outer spacers are the larger ones "
        "on the dummy-gate sidewalls.", view="cutb",
        match="intermediate", figs=["13A/B"],
        subs=["The patent's inner spacers are low-κ; one low-κ material is drawn"])
    # 12
    F.add("epi_source", "epi_drain")
    F.snap("epi", "Source/drain epitaxy and anneal",
        "After a surface clean, n-doped silicon grows from the exposed Si sheet tips. Si:P is drawn; "
        "the patent names no nFET source/drain material. The BDI below is not a crystal seed, so "
        "growth starts at the sheets. It merges into one shared source on one side and one shared "
        "drain on the other, joining the sheet ends [R13]. Its top sits higher than the pFET's "
        "source/drain by H, at least the BDI's thickness (Fig. 13). An activation anneal follows. "
        "This model gives it no separate step, but it does change the device: dopant activation "
        "and diffusion shape the junction profile.",
        match="published", figs=["13A/B"],
        subs=["The anneal is a conventional concept, not a separately described patent state; "
              "no dopant profile, diffusion or stress is calculated"])
    # 13
    F.drop("hardmask")
    ild_around()
    F.snap("ild", "ILD fill and planarisation",
        "A low-κ interlayer dielectric (ILD, the insulator between the device and its wiring) is "
        "deposited over everything and polished flat. The CMP removes the hard mask and stops on "
        "the dummy gate [R13]. The source and drain are now buried; hide the ILD in Layers to see them.",
        match="intermediate", figs=["14A/B"])
    # 14
    F.drop("dummy", "dox")
    F.snap("pull", "Dummy-gate removal",
        "The dummy gate is etched out, leaving the spacers and ILD in place, and the sacrificial "
        "oxide is cleared. The trench left behind is the cavity for the replacement gate. The Si "
        "and 25 %-Ge SiGe layers are still stacked at its bottom [R13].", view="cut",
        match="published", figs=["14A/B"])
    # 15
    F.drop("sige1", "sige2", "sige3")
    F.snap("release", "nFET channel release",
        "A selective etch removes the 25 %-Ge SiGe inside the cavity, including under the lowest "
        "sheet, and keeps the Si [R13]. The Si nanosheets stay joined to the source and drain "
        "at their ends. Each sheet is now open above, below and on both sides, ready for the gate. "
        "Etch selectivity, residues, surface roughness and sheets sticking together are real "
        "concerns. Both wet and dry etches are used [R1][R14].", view="cut",
        match="published", figs=["16A/B"],
        omitted=["The pFET's channel preparation (Fig. 15)"])
    # 16
    F.add(*[f"{k}{i}" for k in ("il", "hk", "tin") for i in (1, 2, 3)], "mo")
    F.snap("hkmg", "High-κ / metal gate",
        "After a surface clean, a thin interfacial oxide forms on the released Si. A Hf-based high-κ "
        "dielectric goes all round each sheet. Then come the work-function metals. A p-type metal "
        "goes into both regions and is removed from the nFET; an n-type metal goes on the nFET. "
        "W fills the rest of the "
        "trench and is recessed below the top of the spacers [R13]. Reaching every surface between "
        "the sheets is the key step [R1].", view="cut",
        match="published", figs=["17A/B"],
        subs=[HKMG_SUB, NS_FILMS_SUB],
        omitted=["The pFET's own work-function stack beside it, and the gate cut between the two "
                 "(see Both sites)"])
    # 17
    F.add("gatecap")
    F.snap("cap", "Self-aligned-contact cap",
        "An insulating fill goes into the recess over the W and is polished: the SiN self-aligned-"
        "contact (SAC) cap. In the patent the same fill also fills the gate cut between the nFET and "
        "the pFET, so one deposition makes the cut and the caps [R13]. A cap like this, with the "
        "spacers beside the gate, keeps a source/drain contact from shorting to the gate [R26].", view="cut",
        match="published", figs=["17A/B"],
        subs=["The patent's examples for the cap are SiN, SiNC and SiBCN; SiN is drawn"])
    # 18
    F.add("nisi_source", "nisi_drain", "ni_source", "ni_drain", "gatew")
    ild_around(span(F.final["gatecap"])[3])
    F.snap("contacts", "Middle-of-line contacts",
        "Source/drain trenches are etched through the ILD, and a gate trench through the SAC cap. A "
        "conductive fill, which may include a silicide, forms the source/drain contacts and the gate "
        "contact [R13]. These are middle-of-line structures, between the device and the wiring "
        "[R12]. The wiring above them is not modelled.",
        match="published", figs=["18A/B"],
        subs=["The patent names no contact metal, only that it may include a silicide: the TiSiₓ, "
              "Co and W stack is the model's choice"],
        omitted=["Fig. 19A/B, an alternative shared-gate arrangement, not a later step"])
    # 18
    F.drop("ild")
    F.snap("done", "The finished device",
        "The finished nFET: three Si sheets, each wrapped by the gate films. With Channel design set "
        "to Si/SiGe CMOS, Device and Inverter modes show this nFET beside its pFET on a shared gate. "
        "The ILD is hidden here only for viewing, as in the Device view; it is not removed in "
        "fabrication.",
        match="published", figs=["18A/B"],
        subs=["The ILD is hidden for viewing only", NS_STACK_SUB],
        omitted=["The patent's final figures show the pFET beside this nFET"])
    return dev, F.done(), dict(scope=NS_SCOPE, figures=NS_FIGURES, branch=NS_BRANCH,
                               skipped=NS_SKIPPED, refs=["R13", "R1", "R12", "R14", "R15", "R16", "R17", "R18", "R19", "R20", "R21", "R26"],
                               match=dict(MATCH, **PAT_MATCH), routes=ROUTES,
                               route_title="How the stack lines are printed", route_join="the stack etch",
                               views=dict(dev.views, cut=CUTAWAY, cutb=INDENT, **TILE_VIEWS, **FIELD_VIEWS),
                               # Its own finished parts, views and frame: Device mode's nanosheet
                               # scenes are the CMOS variants, not this single nFET site.
                               final=dev.parts, own=True, name=dev.name, bounds=dev.bounds)


# ================================================= PITCH-SPLITTING ROUTES ===
# How the stack hard mask gets its lines, as a choice of route through operations
# 4.1-4.6: the direct print, or SADP or SAQP on the field of lines around the tile. Every
# route ends with the same hard-mask lines in the tile, so the stack etch that follows is
# the same step whichever route led to it.
PAT_MATCH = {"pattern": "Concept: patterning applied to an illustrative layer"}
ROUTES = [
    dict(id="direct", name="Direct print",
         note="One exposure prints the stack lines at their final pitch, with EUV for example. A "
              "printed line can differ in width from its neighbours, which lets nanosheets have "
              "adjustable sheet widths [R18]. Spacer routes make every line one film thickness "
              "wide."),
    dict(id="sadp", name="SADP", default=True,
         note="Self-aligned double patterning: cores printed at twice the final pitch, then one "
              "spacer step halves the pitch [R21]. It is the default here as a teaching choice. It "
              "is a patterning concept applied to an illustrative layer: the sources do not say "
              "this stack is patterned this way."),
    dict(id="saqp", name="SAQP",
         note="Self-aligned quadruple patterning: cores at four times the final pitch, then two "
              "spacer steps; the first spacer image becomes the second set of cores [R19][R20]. "
              "It is a patterning concept applied to an illustrative layer: the sources do not say "
              "this stack is patterned this way."),
]
FIELD_SUB = ("The field around the tile is illustrative: its lines stand for neighbouring devices. "
             "Implants outside the tile are not drawn")
FIELD_VIEWS = {}
for _mod, _r in (("sadp", 1.0), ("saqp", 1.6)):
    FIELD_VIEWS[_mod + "field"] = dict(n="Line field", s="the tile and the lines around it", az=-0.95,
                                       el=0.55, r=1050 * _r, tgt=[-36.5, 60, -34], clip=None, scale="field")
    FIELD_VIEWS[_mod + "cut"] = dict(n="Across the lines", s="section, mid-field", az=1.5708, el=0.08,
                                     r=800 * _r, tgt=[-36.5, 70, -34], clip=[-36.5, None, None], scale="field")
    FIELD_VIEWS[_mod + "plan"] = dict(n="From above", s="count the lines", az=1.5708, el=1.45,
                                      r=950 * _r, tgt=[-36.5, 60, -34], clip=None, scale="field")


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
            "The spacers are stripped. Resist is spun on over the hard-mask lines for a second, "
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
            f"lines that stay, cut to length. The resist becomes soluble over the line ends and the "
            f"lines at the edge of the array{g['cut_note']} [R16][R19].", view=f"{mode}field",
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
            f"as the direct route's, at the same width and pitch (checked when the data is built). So "
            f"the flow goes on with the same {w} etch. {what} changed only how the mask was made.",
            view="tilecut", of=of, match="pattern")

    def pull_sub(extra=""):
        return [f"Ideal spacing. In practice alternate spaces can differ (pitch walk){extra} [R20]"]

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
        (f"A mandrel film for the cores goes over the {w} hard mask. " if g.get("hm_shared") else
         f"The {w} hard mask is deposited as in the direct route, then a mandrel film for the cores. ") +
        "A mandrel is the temporary core that spacers form against [R21]. The view zooms out past "
        "the tile to the array of lines around it: the tile sits in the middle, and the lines beyond "
        "it belong to neighbouring devices. This route changes only how the hard-mask lines are made.",
        view="sadpfield", of=of, match="pattern",
        subs=[FIELD_SUB, "Mandrel material and thickness are illustrative"], deposit=["f_man"])
    litho(S, "sadp", yman + MAN, mand, z0, z1, (0, 2.0, 0),
        "The scanner images the reticle's pattern onto the resist, as in the direct route, but "
        f"prints only the cores. The chrome keeps four lines dark at pitch P = {2 * P2:g} nm, twice "
        "the final pitch, which one exposure resolves more easily. The rest becomes soluble "
        "[R16][R21].", ["The core count, width and pitch are illustrative"])
    S.snap("sadp_litho", "Core development",
        "The developer dissolves the exposed resist, leaving four resist cores on the mandrel "
        "film [R16].", view="sadpfield", of=of, match="pattern")
    S.drop("f_man", "f_res")
    S.put(tmp("f_man", "Mandrels (cores)", "mandrel", GP,
              [box(X0, X1, yman, yman + MAN, a, b) for a, b in mand], (0, 1.6, 0)))
    S.snap("sadp_mandrel", "Mandrel etch and resist strip",
        "The resist pattern is etched into the mandrel film, and the resist is stripped. What is "
        "left are durable mandrels: the cores the spacers will form against [R21].",
        view="sadpcut", of=of, match="pattern")
    film(S, "Patterning spacer film (as deposited)", W, yman, yman + MAN + W, z0, z1, (0, 1.8, 0))
    S.snap("sadp_dep", "Conformal spacer deposition",
        f"A spacer film {W:g} nm thick is deposited evenly over the mandrel tops, down their "
        "sidewalls and across the floor between them. Its thickness will set the final line "
        "width [R21]. This patterning spacer is a temporary mask, not the transistor's gate spacer.",
        view="sadpcut", of=of, match="pattern")
    S.drop("f_spfilm")
    sp = sorted([(a - W, a) for a, b in mand] + [(b, b + W) for a, b in mand])
    S.put(tmp("f_sp", "Patterning spacers", "patspacer", GP,
              [box(X0, X1, yman, yman + MAN, a, b) for a, b in sp], (0, 1.8, 0)))
    S.snap("sadp_etch", "Spacer etch-back",
        "A directional etch removes the film from every flat surface: the mandrel tops and "
        "the floor. The film is left standing on the mandrel sidewalls, two spacers per mandrel "
        "[R21].", view="sadpcut", of=of, match="pattern")
    S.drop("f_man")
    S.snap("sadp_pull", "Mandrel removal: the spacer image",
        f"The mandrels are removed selectively, leaving only the spacers. Four cores gave eight "
        f"lines, at about P/2 = {P2:g} nm: the {w}s' pitch [R21].", view="sadpplan", of=of,
        match="pattern", subs=pull_sub())
    hm(S, sp, f"{w.capitalize()} hard mask (patterned)")
    S.snap("sadp_hm", "Transfer into the hard mask",
        "The hard mask is etched where the spacers leave it exposed. The spacer pattern is now "
        "a hard-mask pattern.", view="sadpcut", of=of, match="pattern")
    S.drop("f_sp")
    cutmask(S, "sadp", sp, z0, z1, "cut")
    hm(S, cut(sp), f"{w.capitalize()} hard mask (patterned)", WX0, WX1)
    check(S, "SADP")
    S.snap("sadp_cut", "Cut etch and resist strip",
        "The developer clears the exposed resist. The open hard mask is etched away, and the "
        "resist is stripped. The lines are now trimmed to length, and the two at the edge of the "
        "array are gone" + g["cut_note"] + ". Which lines a cut removes is an integration choice [R19].",
        view="sadpfield", of=of, match="pattern", subs=["Which lines are cut is illustrative"])
    back("sadp", "SADP")

    # ---------------------------------------------------------------- SAQP --
    n = 16
    c = centres(n)
    z0, z1 = field(n)
    H22 = g.get("hm22", 0.0)                         # a hard mask between the core films, if drawn
    S = Stage(F, "field", dict(x=[X0, X1], y=[ysub, yman + MAN + H22 + MAN1 + RES + 60], z=[z0, z1]), grid=2.0)
    S.route = "saqp"
    man2 = [(c[2 * i] + W / 2, c[2 * i + 1] - W / 2) for i in range(n // 2)]     # the second cores
    T1 = man2[0][1] - man2[0][0]                                                  # first spacer = their width
    man1 = [(man2[2 * i][1], man2[2 * i + 1][0]) for i in range(n // 4)]          # the first cores
    ym2 = yman + MAN                                                              # the second cores' top
    y1 = ym2 + H22                                                                # first-core film
    base(S, z0, z1)
    S.put(tmp("f_man2", "Second-core film", "mandrel2", GP, [box(X0, X1, yman, ym2, z0, z1)], (0, 1.5, 0)))
    if H22:
        S.put(tmp("f_hm22", "Hard mask 22 (SiN)", "si3n4", GP, [box(X0, X1, ym2, y1, z0, z1)], (0, 1.65, 0)))
    S.put(tmp("f_man1", "First-core film", "mandrel", GP, [box(X0, X1, y1, y1 + MAN1, z0, z1)], (0, 1.8, 0)))
    S.snap("saqp_films", "Two core films" if g.get("hm_shared") else "Hard mask and two core films",
        f"Two core films go over the {w} hard mask: first a second-core film, then a first-core "
        "film. SAQP needs this second core layer [R19]" +
        (". The tile's hard mask did not have these two layers." if g.get("hm_shared") else ".") +
        " The view zooms out past the tile to the array of lines around it.",
        view="saqpfield", of=of, match="pattern",
        subs=[FIELD_SUB, "Core materials and thicknesses are illustrative"],
        deposit=["f_man2"] + (["f_hm22"] if H22 else []) + ["f_man1"])
    litho(S, "saqp", y1 + MAN1, man1, z0, z1, (0, 2.2, 0),
        "The scanner images the reticle's pattern onto the resist. The chrome keeps four cores "
        f"dark at pitch P = {4 * P2:g} nm, four times the final pitch, and the rest becomes "
        "soluble [R16].", ["The core count, width and pitch are illustrative"])
    S.snap("saqp_litho", "Core development",
        "The developer dissolves the exposed resist, leaving four resist cores on the first-core "
        "film [R16].", view="saqpfield", of=of, match="pattern")
    S.drop("f_man1", "f_res")
    S.put(tmp("f_man1", "First cores", "mandrel", GP, [box(X0, X1, y1, y1 + MAN1, a, b) for a, b in man1], (0, 1.8, 0)))
    S.snap("saqp_core1", "First-core etch and resist strip",
        "The pattern is etched into the first-core film, and the resist is stripped [R19].",
        view="saqpcut", of=of, match="pattern")
    film(S, "First patterning spacer film (as deposited)", T1, y1, y1 + MAN1 + T1, z0, z1, (0, 2.0, 0))
    S.snap("saqp_dep1", "First spacer deposition",
        f"A first spacer film, {T1:g} nm thick, coats the first cores. Its thickness sets the "
        "width of the second cores to come [R19].", view="saqpcut", of=of, match="pattern")
    S.drop("f_spfilm")
    sp1 = sorted([(a - T1, a) for a, b in man1] + [(b, b + T1) for a, b in man1])
    S.put(tmp("f_sp1", "First patterning spacers", "patspacer", GP,
              [box(X0, X1, y1, y1 + MAN1, a, b) for a, b in sp1], (0, 2.0, 0)))
    S.snap("saqp_etch1", "First spacer etch-back",
        "An etch-back leaves the first spacers on the core sidewalls [R19].", view="saqpcut", of=of,
        match="pattern")
    S.drop("f_man1")
    S.snap("saqp_pull1", "First-core removal: the first spacer image",
        f"The first cores are removed. Eight spacer lines remain at about P/2 = {2 * P2:g} nm: the "
        "first-generation image [R20].", view="saqpplan", of=of, match="pattern", subs=pull_sub())
    S.drop("f_man2", "f_sp1", "f_hm22")
    S.put(tmp("f_man2", "Second cores", "mandrel2", GP, [box(X0, X1, yman, ym2, a, b) for a, b in sp1], (0, 1.5, 0)))
    S.snap("saqp_core2", "Second cores: the first image transferred",
        "The first spacer image is etched " + ("through hard mask 22 " if H22 else "") + "into the "
        "second-core film, and the first spacers " + ("and hard mask 22 are" if H22 else "are") + " "
        "removed. The first-generation image is now the second set of cores; it is not etched "
        "into the hard mask. This transfer is one way to make the second cores; there are others [R19].",
        view="saqpcut", of=of, match="pattern")
    film(S, "Second patterning spacer film (as deposited)", W, yman, ym2 + W, z0, z1, (0, 1.8, 0))
    S.snap("saqp_dep2", "Second spacer deposition",
        f"A second spacer film, {W:g} nm thick, coats the second cores. This thickness sets the "
        "final line width [R19].", view="saqpcut", of=of, match="pattern")
    S.drop("f_spfilm")
    sp2 = sorted([(a - W, a) for a, b in sp1] + [(b, b + W) for a, b in sp1])
    S.put(tmp("f_sp2", "Second patterning spacers", "patspacer", GP,
              [box(X0, X1, yman, ym2, a, b) for a, b in sp2], (0, 1.8, 0)))
    S.snap("saqp_etch2", "Second spacer etch-back",
        "An etch-back leaves the second spacers on the second cores' sidewalls [R19].", view="saqpcut",
        of=of, match="pattern")
    S.drop("f_man2")
    S.snap("saqp_pull2", "Second-core removal: the final spacer image",
        f"The second cores are removed. Sixteen spacer lines remain at about P/4 = {P2:g} nm, the "
        f"{w}s' pitch: four times the density of the printed cores, from one exposure [R20].",
        view="saqpplan", of=of, match="pattern",
        subs=pull_sub(", and the variation adds up over the two generations"))
    hm(S, sp2, f"{w.capitalize()} hard mask (patterned)")
    S.snap("saqp_hm", "Transfer into the hard mask",
        "The pattern is etched into the hard mask, with the second spacers as the etch mask [R19].",
        view="saqpcut", of=of, match="pattern")
    S.drop("f_sp2")
    cutmask(S, "saqp", sp2, z0, z1, "block")
    hm(S, cut(sp2), f"{w.capitalize()} hard mask (patterned)", WX0, WX1)
    check(S, "SAQP")
    S.snap("saqp_cut", "Block etch and resist strip",
        "The developer clears the exposed resist. The open hard mask is etched away, and the "
        "resist is stripped. The lines are now trimmed to length, and the edge lines are gone" + g["cut_note"] +
        ". In a real integration the block pattern also decides which lines become devices. imec's "
        "metal-line example keeps groups of six [R19].",
        view="saqpfield", of=of, match="pattern", subs=["Which lines are cut is illustrative"])
    back("saqp", "SAQP")


# ============================================================ LESSON CHIPS ===
# SADP and SAQP on their own chips: each is the nanosheet flow's route of that name, taken
# out of the flow and ending with the stack etch that follows it, so the lesson and the
# route are the same steps and cannot drift apart.
LESSONS = dict(
    sadp=dict(name="SADP · double patterning",
              branch="SADP splits the printed pitch once, from P to P/2: every core leaves two spacer "
                     "lines [R21]. The SAQP chip splits it twice."),
    saqp=dict(name="SAQP · quadruple patterning",
              branch="SAQP splits the printed pitch twice, from P to P/4. The first spacer image becomes "
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
                  f"patterning) on its own. These are the steps the Nanosheet flow shows when its stack "
                  f"patterning route is set to {route['name']}, from the film stack to the stack etch. "
                  "Where a step says “as in the direct route”, it means that flow's single-exposure "
                  "alternative; the flow itself defaults to SADP. This is a patterning concept "
                  "applied to an illustrative layer, the nanosheet tile's Si/SiGe multilayer. The "
                  "sources do not say this stack is patterned this way. A direct print (EUV single "
                  "exposure, for example) is another way to make it [R18]. The route patterns the stack "
                  "lines: the hard mask, then the multilayer and sub-fin under it. It does not decide "
                  "whether a finished pFET's channels are Si or SiGe. That is set later, by which layers "
                  "each device keeps, not by how the lines are printed.",
            figures="Every step but the last is a patterning concept and matches no figure. "
                    "The last, the stack etch, is the nanosheet flow's own: a teaching reconstruction "
                    "of the patent's Fig. 5A/B [R13], compared with that drawing (docs/nsfet).",
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
FIN_MATCH = {"source": "Source stage, adapted; artwork not compared",
             "teach": "Teaching reconstruction; no source figure"}
FIN_SCOPE = ("How a bulk silicon FinFET nFET is made, gate last: a dummy gate holds the gate's place "
             "and the real gate replaces it near the end [R29][R24]. The stages follow TSMC's "
             "US 9,812,358 B1 [R29]. The fins are printed by self-aligned quadruple patterning (SAQP) "
             "after GlobalFoundries' US 9,171,764 B2 [R30]. The replacement gate sits under a hard "
             "mask, and the replacement contacts are made where a spin-on-carbon dummy contact stood. "
             "Dimensions are the model's. This is not a verified foundry recipe.")
FIN_FIGURES = ("Figure numbers follow the patents' written descriptions: US 9,812,358 B1 for the device [R29], "
               "US 9,171,764 B2 for the SAQP route [R30]. Each state was compared with the drawing it names "
               "(docs/finfet), and the differences are named under each step. In the device "
               "patent's Figs. 14–22, B is the section along the gate (across the fins) and C the section along "
               "a fin: the reverse of Figs. 7–13. The views are the app's own reconstructions in its own "
               "frame, so their orientation may differ.")
FIN_BRANCH = ("The flow follows the nFET. The 2 × 2 tile's four sites give context for the "
              "patterning; only the selected nFET becomes a finished device. The pFET's own "
              "steps, such as its masked SiGeB epitaxy and its own gate materials [R29], are "
              "in the pFET flow. Both sites shows the two together, with a choice of gate "
              "cut or shared gate. The labels under each step say what each region is doing.")
FIN_ROUTES = [
    dict(id="direct", name="Direct print",
         note="A hypothetical single immersion (193i) exposure at this model's 27 nm fin pitch. "
              "That is far below what one such exposure resolves [R22]. It is shown for comparison, "
              "not as a claim about every lithography option."),
    dict(id="sadp", name="SADP",
         note="Self-aligned double patterning: cores at twice the fin pitch, then one spacer "
              "step halves the pitch [R21]. Whether it suits depends on the lithography, the target "
              "dimensions and the integration."),
    dict(id="saqp", name="SAQP", default=True,
         note="Self-aligned quadruple patterning, the default here. It is used for 7 nm-class "
              "FinFET fins [R23]. A published N7 example has cores at 96 nm pitch, 48 nm after the "
              "first split and 24 nm fins [R22]. This model's 108 → 54 → 27 nm is an illustrative "
              "adaptation."),
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
F1, F2, F3, F4, F6 = "R29", "R25", "R30", "R27", "R26"
SPACER_SUB = ("F1 forms its gate spacers by selective deposition with no etch-back (its Figs. "
              "8–15). This conventional deposition and etch-back is a separate teaching "
              "reconstruction, of the kind F2 describes for gate seal and spacer films [R25]")
SUBFIN_NOTE = ("Leakage under the fin: STI isolates sideways, not beneath the channel. One separately "
               "published option is a punch-through stopper in the sub-fin, doped from an STI liner "
               "and diffused by anneal [R27]. This model does not resolve sub-fin leakage")


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
    ymo = max(b[3] for b in mo)                        # 75
    cap = span(P["gatecap"]); ycap, hzmo = cap[3], cap[5]      # 81, 27.5
    XG = cap[1]                                        # 9: the gate trench's half-length
    XD = XG - 1.0                                      # 8: the dummy gate's; a 1 nm seal spacer each side
    XSP = max(lim(b)[1] for b in P["spacer_drain"]["boxes"])              # 16
    TOX, TSP = 1.0, XSP - XG                           # dummy dielectric; spacer width
    hzenv = extent("ni_drain")[5] + 1.0                # the contact opening's half-width (liner included)
    YHM = ycap + 6.0                                   # mask 72 on the dummy gate, until the CMP
    CB = dict(dev.bounds, y=[dev.bounds["y"][0], YHM + 40.0])     # tall enough for masks and reticles
    F.bounds = CB

    def ild_around(ytop=ycap, holes=(), name="Interlayer dielectric (ILD)"):
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]] + list(holes)
        F.put(tmp("ild", name, "ild", "Interlayer dielectric",
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
                 f"sites' fins sit three fin pitches apart. The tile's gate pitch is about {PG:.0f} nm; "
                 "a real 3 nm-class contacted gate pitch is about 45–48 nm (a typical value, not from the cited sources)"]
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
            "A hard-mask film goes on the bare wafer, whose own silicon will become the fins. It is "
            "the SAQP patent's hard mask 16: silicon nitride, about 40 nm thick there, drawn 6 nm "
            "here [R30]. The FinFET patent names no fin mask. The view zooms out to a tile of four "
            "sites: an nFET pair of fins in a p-well through the selected site, and a pFET pair in "
            "an n-well beside it. Two gate lines will cross them later. "
            "Only the selected nFET is carried to a finished device; the other three are context.",
            view="tile", of="fins", match="source", figs=["1"], src=[F3],
            deposit=["t_hm"],
            subs=TILE_SUBS + ["The wells are named regions only, not doping profiles",
                              "Hard-mask material and thickness are illustrative"],
            omitted=["The pad oxide, and the well implants and anneal"])
        T.route = "direct"          # the routes part here: how the hard mask gets its lines
        t_resist("t_res", "Photoresist (coated)", "resist", [box(SX0, SX1, top + HMT, top + HMT + RT, WZ0, WZ1)])
        T.snap("coat", "Resist coat",
            "A light-sensitive photoresist is spun on over the hard mask [R16]. Coat, expose, "
            "develop and etch is a cycle repeated many times in making a chip [R17].", view="tile",
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
            "The scanner images the reticle's pattern onto the resist. The reticle is drawn above "
            "the wafer only to show which areas its chrome keeps dark. With a positive-tone resist, "
            "the exposed resist between the future fins becomes soluble [R16]. This route is a "
            "hypothetical single immersion exposure at a 27 nm fin pitch, far below what one "
            "resolves. It is shown for comparison with the spacer routes [R22].",
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
            "A directional etch copies the resist lines into the hard mask [R16].", view="tilecut",
            of="fins", match="concept",
            subs=["The FinFET patent draws its fins without a mask (Fig. 3); the hard mask is the SAQP patent's [R30]"])
        T.drop("t_res")
        T.snap("strip", "Resist strip",
            "The resist is stripped. The hard mask alone now defines the fins.",
            view="tilecut", of="fins", match="teach")
        T.route = None
        pitch_routes(F, T, dict(
            what="fin", of="fins", group=GFN, anchor=ZMID, drop=[ZMID],
            cut_note=", and the extra line between the nFET and pFET fin groups, so no fin is "
                     "ever etched there",
            lines="four fin lines", films=(16.0, 26.0, 8.0), hm22=4.0, hm_shared=True, layer_x=(SX0, SX1), hz=hw, PS=FP, win=(WX0, WX1, WZ0, WZ1),
            top=top, HMT=HMT, ysub=sub[2],
            layers=[("fl", "Si · upper substrate (fins to be)", "silicon", 0, top, (0, 0, 0))]))
        # The spacer routes' provenance: SAQP for fins follows US 9,171,764 B2 (F3), step for
        # step; SADP for these fins is a teaching reconstruction; resist steps are concept only.
        LITHO = ("_coat", "_expose", "_litho", "_cutcoat", "_cutexpose")
        SAQP_FIG = dict(saqp_films=["1"], saqp_core1=["2"], saqp_dep1=["3"], saqp_etch1=["4"], saqp_pull1=["5"],
                        saqp_core2=["5", "6"], saqp_dep2=["6"], saqp_etch2=["7"], saqp_pull2=["8"], saqp_hm=["9"],
                        saqp_coat=["1"], saqp_expose=["1", "2"], saqp_litho=["2"])
        NAMES = {"First-core film": "Upper mandrel layer 20 (a-Si; about 100 nm in the patent, drawn thinner)",
                 "Second-core film": "Lower mandrel layer 14 (a-Si; about 100 nm in the patent, drawn thinner)",
                 "First cores": "Upper mandrels (a-Si)", "Second cores": "Lower mandrels (a-Si)",
                 "First patterning spacers": "Upper spacers 52 (SiN; the patent gives about 14–30 nm)",
                 "Second patterning spacers": "Lower spacers 70 (SiN): mask 73"}
        for st in F.steps:
            r = st.get("route")
            if r == "saqp":
                for q in st["parts"]:
                    if isinstance(q, dict):
                        for a, b in NAMES.items():
                            if q["name"].startswith(a): q["name"] = b + q["name"][len(a):]
                        if q["material"] == "patspacer" and "spacer" in q["name"].lower() and "(SiN" not in q["name"]:
                            q["name"] += " · SiN"
            if r in ("sadp", "saqp") and st["id"].endswith(LITHO):
                st["match"] = "concept"
                if r == "saqp" and st["id"] in SAQP_FIG: st["figs"], st["src"] = SAQP_FIG[st["id"]], [F3]
                continue
            if r == "sadp": st["match"] = "teach"
            if r == "saqp":
                if st["id"] in ("saqp_back", "saqp_cut"):
                    st["match"] = "teach"
                    if st["id"] == "saqp_cut":
                        st["subs"] = st["subs"] + ["US 9,171,764 B2 removes unwanted fins after the fin etch, "
                                                   "through a mask (its Figs. 10–11, for SRAM cells); the "
                                                   "extra line is blocked before the etch here"]
                    continue
                st["match"], st["figs"], st["src"] = "source", SAQP_FIG[st["id"]], [F3]
                if st["id"] == "saqp_films":
                    st["subs"] = st["subs"] + ["The patent's stack is hard mask 16 (SiN, about 40 nm), lower mandrel "
                                               "layer 14 (a-Si, about 100 nm), hard mask 22 (about 40 nm), upper "
                                               "mandrel layer 20 (a-Si, about 100 nm) and resist; all are drawn "
                                               "thinner, not to scale"]
                if st["id"] == "saqp_dep2":
                    st["subs"] = st["subs"] + ["The patent gives the lower spacers about 10–20 nm; 6 nm is drawn, "
                                               "the fin width"]
                if st["id"] == "saqp_hm":
                    st["subs"] = st["subs"] + ["The patent etches hard mask 16 and the substrate in one step with the "
                                               "lower spacers on (its Fig. 9); the fin etch is drawn after the block "
                                               "cut here"]
                if st["id"] == "saqp_pull2":
                    st["subs"] = st["subs"] + ["The patent lets the mandrel widths and spacings differ to give "
                                               "variably spaced fins; uniform ones are drawn, and the Pitch walk "
                                               "lesson varies them"]

        T.drop("t_fl")
        for zc, k in PAIRS:
            for i, z in enumerate(ZF):
                T.put(tmp(f"t_fin_{k}{i+1}", f"Si fin {i+1} · {who(k)}", "silicon", GFN,
                          [box(WX0, WX1, 0, top, zc + z - hw, zc + z + hw)]))
        T.snap("finetch", "Fin etch",
            f"A directional etch cuts {top:g} nm down into the silicon between the hard-mask lines. "
            f"Four fins {2 * hw:g} nm wide remain, each capped by the hard mask [R30]. The etch is an "
            "anisotropic RIE (reactive-ion etch) or a neutral-beam etch [R29]. The fins are not "
            "separate pieces: each is the wafer's own crystal, continuous with the bulk below [R29].",
            view="tilecut", of="fins", match="source", figs=["3"], src=[F1],
            subs=["Fins are drawn with vertical walls; the patent's Fig. 3 fins taper"])
        T.put(tmp("t_sti", "Silicon oxide (FCVD), filled and polished", "sio2", GS,
                  subtract((SX0, SX1, 0, top + HMT, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stifill", "STI fill and CMP",
            "Silicon oxide fills the trenches by flowable CVD (FCVD, a deposition that flows into narrow "
            "gaps). It is annealed and polished flat by CMP (chemical-mechanical polishing) [R29]. The "
            "patent polishes it level with the fins' tops; here the polish stops on the hard mask "
            "over them.", view="tilecut", of="fins", match="source", figs=["4"], src=[F1],
            subs=["The polish stopping on the hard mask, and the mask's removal with the recess, are the model's"])
        T.drop("t_sti", "t_hm")
        T.put(tmp("t_sti", "STI oxide", "sio2", GS,
                  subtract((SX0, SX1, 0, STI, WZ0, WZ1), T.boxes()), (0, -.8, 0)))
        T.snap("stirecess", "STI recess and hard-mask removal",
            f"The oxide is etched back so each fin stands {top - STI:g} nm above it. This exposed "
            f"height is what the gate will wrap; the etch cut {top:g} nm. Below the oxide top the "
            "same fin continues into the bulk. The oxide isolates neighbouring fins sideways: "
            "shallow trench isolation (STI). It is recessed with a selective etch such as dilute HF "
            "[R29]. Next, the view returns to the selected site.",
            view="tile", of="fins", match="source", figs=["5"], src=[F1],
            subs=["Exposed fin height is the model's; it sets the effective width with the fin width"],
            omitted=[SUBFIN_NOTE])

    def tile_dummy():
        """Dummy-gate deposition and patterning across both fin pairs (the core step 'dummy')."""
        for zc, k in PAIRS:
            for i, z in enumerate(ZF):
                T.put(tmp(f"t_dox_{k}{i+1}", "Dummy dielectric (silicon oxide)", "sio2", GD,
                          subtract((WX0, WX1, STI, top + TOX, zc + z - hw - TOX, zc + z + hw + TOX), T.boxes()),
                          (0, .6, 0)))
        T.put(tmp("t_dsi", "Dummy gate · polysilicon (as deposited)", "poly", GD,
                  subtract((WX0, WX1, STI, ycap, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
        T.put(tmp("t_dhm", "Mask layer 62 (SiN)", "si3n4", GD,
                  [box(WX0, WX1, ycap, YHM, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("dummydep", "Dummy-gate stack deposition",
            "A dummy dielectric (silicon oxide) goes on the exposed fins. Amorphous silicon is deposited, "
            "recrystallised to polysilicon and planarised by CMP. A SiN mask layer goes on top "
            "[R29].", view="tile", of="dummy", match="source", figs=["6"], src=[F1],
            subs=["Layer heights are illustrative"])
        gl = [(xg - XD, xg + XD) for xg in GATES]
        gaps_x = bd.gaps(WX0, WX1, gl)
        t_resist("t_gres", "Photoresist (coated)", "resist", [box(WX0, WX1, YHM, YHM + RT, WZ0, WZ1)])
        T.snap("gcoat", "Gate resist coat",
            "Resist is spun on over the gate hard mask, as for the fins [R16].", view="tile",
            of="dummy", match="concept", deposit=["t_gres"])
        T.drop("t_gres")
        t_resist("t_gres", "Photoresist (unexposed: over the gates)", "resist",
                 [box(a, b, YHM, YHM + RT, WZ0, WZ1) for a, b in gl])
        t_resist("t_gres_x", "Photoresist (exposed: made soluble)", "resist_exp",
                 [box(a, b, YHM, YHM + RT, WZ0, WZ1) for a, b in gaps_x])
        T.put(tmp("t_greticle", "Reticle chrome (in the scanner; not to scale)", "chrome", GP,
                  [box(a, b, RY, RY + 2.0, WZ0, WZ1) for a, b in gl], (0, 2.0, 0)))
        T.snap("gexpose", "Gate exposure",
            "The gate lines are exposed across the fins. The reticle's chrome keeps the resist "
            "over each future gate dark, and the rest becomes soluble [R16].", view="tile",
            of="dummy", match="concept", subs=["Exposure is simplified, as for the fins"])
        T.drop("t_greticle", "t_gres_x", "t_dhm")
        for g, (a, b) in enumerate(gl):
            T.put(tmp(f"t_ghm{g}", f"Mask 72 · gate {g + 1}", "si3n4", GD,
                      [box(a, b, ycap, YHM, WZ0, WZ1)], (0, 1.4, 0)))
        T.snap("ghm", "Development and gate hard-mask etch",
            "The developer clears the exposed resist. A directional etch then copies the resist "
            "lines into the mask layer. These are the patent's masks 72, patterned by photolithography "
            "and etching [R29].",
            view="tile", of="dummy", match="source", figs=["7A", "7B"], src=[F1])
        T.drop("t_gres", "t_dsi", *[f"t_dox_{k}{i+1}" for _, k in PAIRS for i in range(len(ZF))])
        for g, xg in enumerate(GATES):
            for zc, k in PAIRS:
                for i, z in enumerate(ZF):
                    T.put(tmp(f"t_dox_{k}{i+1}_{g}", "Dummy dielectric", "sio2", GD,
                              subtract((xg - XD, xg + XD, STI, top + TOX, zc + z - hw - TOX, zc + z + hw + TOX),
                                       T.boxes()), (0, .6, 0)))
        for g, xg in enumerate(GATES):
            T.put(tmp(f"t_dummy{g}", f"Dummy gate {g + 1} · polysilicon", "poly", GD,
                      subtract((xg - XD, xg + XD, STI, ycap, WZ0, WZ1), T.boxes()), (0, 1.0, 0)))
        T.snap("gatepat", "Dummy-gate etch and resist strip",
            "The dummy stack is etched down to the STI through the hard mask and cleared off the fins "
            "between the gates. The resist is stripped [R29]. Two gate lines now cross both fin pairs: "
            "four sites, with the source/drain between two gates shared. Left uncut, each gate line is "
            "one gate shared by an nFET and a pFET, as in an inverter; a gate cut would separate them. "
            "Only the selected nFET is completed. Next, the view returns to the selected site.",
            view="tile", of="dummy", match="source", figs=["7A", "7B"], src=[F1],
            omitted=["A gate cut between the sites, if the two gates are to be separate"])

    # 1
    F.put(tmp("wafer", "Si substrate (unpatterned)", "silicon", GS,
              [box(sub[0], sub[1], sub[2], top, -zsub, zsub)], (0, -1.2, 0)))
    F.snap("substrate", "Silicon substrate",
        "The flow starts from a bulk silicon wafer with two regions: 50B for n-type devices, as here, "
        "and 50C for p-type ones. In a bulk FinFET the fins are cut from the wafer itself. So the "
        "channel is the same single crystal as the substrate [R29].",
        match="source", figs=["2"], src=[F1])
    # 2
    tile_fins()
    F.drop("wafer"); F.add("substrate", "sti"); full_fins()
    same_site(T, F, SITE2, "fin patterning")
    F.snap("fins", "Fins, isolation and wells",
        f"Fins are etched into the wafer (Fig. 3). The trenches are filled with FCVD silicon oxide, "
        f"annealed and polished (Fig. 4). The oxide is recessed so each fin stands {top - STI:g} nm "
        f"above it (Fig. 5). Then the wells are implanted through photoresist masks: a P well here "
        f"(boron, up to 10¹⁸ cm⁻³) and an N well in the p-type region, followed by an anneal [R29]. "
        "The Steps tab's patterning route shows how the fin lines are printed: SAQP [R30], beside "
        "SADP and a direct print.",
        match="source", figs=["3", "4", "5"], src=[F1],
        subs=["Fin width, height and pitch are the model's; the wells are named regions, not doping profiles"],
        omitted=[SUBFIN_NOTE])
    # 3
    tile_dummy()
    dox = []
    for z in ZF:
        dox += subtract((-XD, XD, STI, top + TOX, z - hw - TOX, z + hw + TOX), F.boxes())
    F.put(tmp("dox", "Dummy dielectric (silicon oxide)", "sio2", GD, dox, (0, .6, 0)))
    F.put(tmp("dummy", "Dummy gate · polysilicon", "poly", GD,
              subtract((-XD, XD, STI, ycap, -hzmo, hzmo), F.boxes()), (0, 1.0, 0)))
    F.put(tmp("hardmask", "Mask 72 (SiN)", "si3n4", GD,
              [box(-XD, XD, ycap, YHM, -hzmo, hzmo)], (0, 1.4, 0)))
    same_site(T, F, SITE3, "dummy-gate patterning")
    F.snap("dummy", "Dummy gate",
        "A dummy dielectric, a polysilicon dummy gate and a SiN mask cross both fins, over their "
        "tops and down their sides. The polysilicon starts as amorphous Si, which is deposited, "
        "recrystallised and planarised [R29]. The dummy gate fixes where the gate goes and how long it is. The real "
        "gate replaces it near the end (gate last) [R29][R24].", view="iso", match="source", figs=["6", "7A", "7B"], src=[F1],
        bounds=CB, subs=["Heights are illustrative"])
    # 4
    for sx, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((sx * XD, sx * XG))
        F.put(tmp(f"seal_{t}", f"Gate seal spacer 80 (oxide) · {t} side", "sio2", "Spacers",
                  subtract((xa, xb, STI, ycap, -hzmo, hzmo), F.boxes()), (sx * 1.1, 0, 0)))
    F.snap("seal", "Gate seal spacers and LDD implants",
        "Gate seal spacers form on the dummy gate's sidewalls, by thermal oxidation or by a deposition "
        "and anisotropic etch. Then lightly doped source/drain (LDD) regions are implanted, one region "
        "at a time through a mask, and annealed [R29].", view="iso", match="source", figs=["7A", "7B"],
        src=[F1], bounds=CB, subs=["The LDD doping is named, not drawn"])
    # 5
    for sx, t in ((-1, "source"), (1, "drain")):
        F.put(tmp(f"dsp_{t}", f"Dummy gate spacer (SiN) · {t} side", "si3n4", "Spacers",
                  P[f"spacer_{t}"]["boxes"], (sx * 1.3, 0, 0)))
    F.snap("dspacer", "Dummy gate spacers",
        "With the p-type region masked, a dummy spacer layer is deposited over the n-type region. A "
        "directional etch leaves dummy gate spacers on the seal spacers. They set where the "
        "recess starts and are removed after the epitaxy [R29].", view="iso", match="source",
        figs=["8A", "8B"], src=[F1], bounds=CB, omitted=["The mask over the p-type region"])
    # 6
    F.drop("fin1_full", "fin2_full"); F.add("fin1", "fin2")
    F.snap("recess", "Source/drain fin recess",
        "The exposed fin ends beside the dummy gate spacers are etched into recesses. Under the gate "
        "and spacers the fin stays whole: that part is the channel [R29].",
        view="b", match="source", figs=["8A", "8B"], src=[F1], bounds=CB,
        subs=["The recess floor is drawn at the STI top; its depth and shape are illustrative"])
    # 7
    F.add("epi_source", "epi_drain")
    F.snap("epi", "Source/drain epitaxy",
        "SiP grows epitaxially in the recesses, seeded by the fin's silicon. It rises above the fin "
        "surface with facets. The patent's n-type options are Si, SiC, SiCP and SiP. The p-type region "
        "is grown the same way in a separate pass, with this one masked [R29].",
        view="sd", match="source", figs=["8A", "8B"], src=[F1], bounds=CB,
        subs=["The facets are drawn as two steps; the patent's epitaxy is faceted and may reach into the fin"],
        omitted=["The p-type region's own pass (SiGe, SiGeB, Ge or GeSn), shown in the pFET flow"])
    # 8
    F.drop("dsp_source", "dsp_drain"); F.add("spacer_source", "spacer_drain")
    F.snap("spacers", "Gate spacers",
        "The dummy spacers are removed. A SiN (or SiCN) layer is deposited evenly and etched "
        "directionally, leaving the gate spacers on the gate seal spacers. A heavier source/drain "
        "implant is an option; the epitaxy can also be doped as it grows [R29].", view="iso", match="source",
        figs=["9A", "9B"], src=[F1], bounds=CB,
        omitted=["The dummy dielectric left under the gate spacers (Fig. 9B)"])
    # 9
    ild_around(YHM, name="Dummy ILD (PSG)")
    F.snap("dild", "Dummy ILD",
        "A dummy interlayer dielectric (ILD) is deposited over everything. Phosphosilicate glass "
        "(PSG) is drawn, one of the patent's options (PSG, BSG, BPSG, USG) [R29].", view="iso", match="source",
        figs=["10A", "10B"], src=[F1], bounds=CB)
    # 10
    F.drop("hardmask"); ild_around(ycap, name="Dummy ILD (PSG)")
    F.snap("cmp", "Planarisation to the dummy gate",
        "CMP levels the dummy ILD with the dummy gates' tops and removes the masks on them [R29].",
        view="iso", match="source", figs=["11A", "11B"], src=[F1])
    # 11
    F.drop("dummy", "dox", "seal_source", "seal_drain")
    F.snap("pull", "Dummy-gate removal",
        "A selective dry etch removes the exposed dummy gates. The gate seal spacers go too, and so "
        "does the dummy dielectric under the gates, which served as the etch stop. Each channel now "
        "sits in a recess walled by the SiN gate spacers, with the fins' top and sides bare at its "
        "bottom [R29].",
        view="cut", match="source", figs=["12A", "12B"], src=[F1])
    # 12
    # Before the recess the wall films and the fill run up to the spacers' tops.
    TW = bd.THK + bd.TTIN
    wall = lambda a, b: [box(-XG + a, -XG + b, ymo, ycap, -hzmo, hzmo), box(XG - b, XG - a, ymo, ycap, -hzmo, hzmo)]
    F.add("il1", "il2", "hk1", "hk2", "tin1", "tin2")
    F.put(dict(P["floor_hk"], id="floor_hk_dep", boxes=P["floor_hk"]["boxes"] + wall(0, bd.THK)))
    F.put(dict(P["floor_wf"], id="floor_wf_dep", boxes=P["floor_wf"]["boxes"] + wall(bd.THK, TW)))
    full_fill = P["mo"]["boxes"] + [box(-XG + TW, XG - TW, ymo, ycap, -hzmo, hzmo)]
    F.put(tmp("mo_dep", "Co gate fill (as deposited, polished)", "cofill", "Gate electrode", full_fill, (0, 1.0, 0)))
    F.snap("metal", "Replacement gate",
        "A gate dielectric coats the trench evenly: the fins' tops and sidewalls, the STI floor "
        "between them and the gate spacers' walls. A Hf-based high-κ is drawn, on an interfacial "
        "oxide over the silicon. Then comes the gate electrode: an Al-containing n-type work-function "
        "layer and a Co fill, from the patent's list (TiN, TaN, TaC, Co, Ru, Al), then CMP. The n- and "
        "p-type regions can have different gate materials, each deposited with the other masked. The "
        "metal wraps three faces of each fin: the tri-gate [R29].", view="c", match="source",
        figs=["13A", "13B"], src=[F1],
        subs=["The interfacial oxide is the model's; the patent names none",
              "The work-function metal's composition and thickness are not modelled, so no threshold "
              "voltage follows from them"],
        omitted=["The p-type region's own gate materials"])
    # 13
    F.drop("mo_dep", "floor_hk_dep", "floor_wf_dep"); F.add("floor_hk", "floor_wf", "mo")
    F.snap("grecess", "Gate recess",
        "The gate dielectric and electrode are etched back below the spacers' tops, leaving a recess "
        "over each gate. The dummy ILD and the spacers are not etched [R29].", view="c", match="source",
        figs=["14A", "14B", "14C"], src=[F1])
    # 14
    hm_full = tmp("hm112", "Hard mask 112 (AlOₓ)", "alox", "Gate electrode",
                  [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0))
    F.put(hm_full)
    F.snap("hmask", "Gate hard mask",
        "A hard mask fills each recess and is polished level with the spacers and the dummy ILD. It "
        "is a metal oxide here: AlOₓ (the patent also names TiO, HfO, ZrO and ZrN). It protects the "
        "gate and spacers when the self-aligned contacts are etched, so a contact cannot short to the "
        "gate [R29][R26].", view="c", match="source", figs=["15A", "15B", "15C"], src=[F1])
    # 15
    F.drop("ild")
    F.snap("dildout", "Dummy ILD removed",
        "An etch removes the dummy ILD but spares the spacers and the hard mask. This opens "
        "recesses down to the source/drain epitaxy [R29].", view="sd", match="source",
        figs=["16A", "16B", "16C"], src=[F1])
    # 16
    socbox = (-XSD, XSD, 0, ycap + 3.0, -zsub, zsub)
    F.put(tmp("soc", "Spin-on carbon (dummy contact material)", "soc", "Dummy contact",
              subtract(socbox, F.boxes()), (0, .9, 0)))
    F.snap("soc", "Spin-on-carbon dummy contact",
        "A spin-on carbon (SOC), 50–95 % carbon, is dispensed as a liquid and fills the recesses. "
        "It is then baked, for example at about 180 °C and then about 350 °C. The bake hardens it "
        "and sets its polish and etch rates [R29].", view="sd", match="source", figs=["17A", "17B", "17C"], src=[F1],
        deposit=["soc"], subs=["An optional liner under the SOC is not drawn"])
    # 17
    F.put(tmp("soc", "Spin-on carbon (baked, polished)", "soc", "Dummy contact",
              subtract((-XSD, XSD, 0, ycap, -zsub, zsub), F.boxes(but=("soc",))), (0, .9, 0)))
    F.snap("soccmp", "Dummy contact planarised",
        "After an optional furnace anneal, CMP polishes the SOC level with the spacers and the hard "
        "mask. It stays only in the recesses [R29].", view="sd", match="source",
        figs=["18A", "18B", "18C"], src=[F1])
    # 18: tri-layer lithography over the SOC
    zf_ = max(hzenv, extent("nisi_drain")[5])        # the dummy contact covers the silicide's footprint too
    foot = [box(xa, xb, 0, ycap, -zf_, zf_) for xa, xb in ((-XSD, -XSP), (XSP, XSD))]
    TL = [("tl_barc", "BARC (bottom anti-reflective coating)", "barc", 3.0),
          ("tl_hm", "Si-containing hard mask", "sihm", 3.0), ("tl_res", "Photoresist", "resist", 8.0)]
    yt = ycap
    tl = []
    for pid, nm, mat, t in TL:
        tl.append((pid, nm, mat, yt, yt + t)); yt += t
    RYC = yt + 14.0
    for pid, nm, mat, y0, y1 in tl:
        F.put(tmp(pid, nm, mat, "Patterning", [box(-XSD, XSD, y0, y1, -zsub, zsub)], (0, 1.6, 0)))
    F.snap("tlcoat", "Tri-layer coat",
        "The replacement-contact pattern is made with tri-layer lithography. Three layers go on the "
        "SOC: a bottom anti-reflective coating (BARC), a silicon-containing hard mask and a "
        "photoresist. The SOC can take the heat of the hard-mask deposition [R29].", view="cexp", of="socpat", match="source",
        figs=["19A", "19B", "19C"], src=[F1], bounds=CB, deposit=[x[0] for x in tl])
    rs = tl[-1]
    keep = [box(lim(f)[0], lim(f)[1], rs[3], rs[4], -hzenv, hzenv) for f in foot]
    F.put(tmp("tl_res", "Photoresist (unexposed: over the contacts)", "resist", "Patterning", keep, (0, 1.6, 0)))
    F.put(tmp("tl_res_x", "Photoresist (exposed: made soluble)", "resist_exp", "Patterning",
              subtract((-XSD, XSD, rs[3], rs[4], -zsub, zsub), keep), (0, 1.6, 0)))
    F.put(tmp("c_ret", "Reticle chrome (in the scanner; not to scale)", "chrome", "Patterning",
              [box(lim(f)[0], lim(f)[1], RYC, RYC + 2.0, -hzenv, hzenv) for f in foot], (0, 2.0, 0)))
    F.snap("tlexpose", "Contact-pattern exposure",
        "The photoresist is exposed through a mask and developed [R29][R16]. The light can be 193 nm "
        "ArF, for example, or the exposure can use immersion lithography. A trim etch then narrows "
        "the resist [R29].", view="cexp",
        of="socpat", match="source", figs=["19A", "19B", "19C"], src=[F1], bounds=CB,
        subs=["Exposure is simplified: no optics, proximity, dose or overlay effects"])
    F.drop("c_ret", "tl_res_x")
    for pid, nm, mat, y0, y1 in tl[:2]:
        F.put(tmp(pid, nm + " (patterned)", mat, "Patterning",
                  [box(lim(f)[0], lim(f)[1], y0, y1, -hzenv, hzenv) for f in foot], (0, 1.6, 0)))
    F.snap("tlopen", "Pattern into the hard mask",
        "The resist pattern is etched into the silicon-containing hard mask and the BARC [R29].",
        view="cexp", of="socpat", match="source", figs=["19A", "19B", "19C"], src=[F1], bounds=CB)
    F.drop("tl_barc", "tl_hm", "tl_res")
    socp = F.now["soc"]
    soc_keep = [c for b in socp["boxes"] for c in [lim(b)]]
    kept = []
    for c in soc_keep:
        for f in foot:
            L = lim(f)
            r = (max(c[0], L[0]), min(c[1], L[1]), max(c[2], L[2]), min(c[3], L[3]), max(c[4], L[4]), min(c[5], L[5]))
            if r[0] < r[1] and r[2] < r[3] and r[4] < r[5]: kept.append(box(*r))
    F.put(tmp("soc", "Spin-on carbon (patterned: over the source/drain)", "soc", "Dummy contact", kept, (0, .9, 0)))
    F.snap("socpat", "Dummy contacts patterned",
        "A dry etch (O₂, SO₂, N₂, H₂) cuts the SOC through the hard mask. The SOC stays over the "
        "source/drain regions that will be contacted. Openings form elsewhere: over the gates' "
        "hard masks and between the fin groups [R29].", view="sd", match="source",
        figs=["19A", "19B", "19C"], src=[F1])
    # 19
    ild_around(ycap, name="ILD 126 (PSG)")
    F.snap("ild", "ILD around the dummy contacts",
        "An interlayer dielectric fills the openings around the dummy contacts. PSG is drawn, again "
        "one of the patent's options. This is the dielectric that stays [R29].", view="sd", match="source",
        figs=["20A", "20B", "20C"], src=[F1])
    # 20
    F.drop("soc")
    F.snap("socout", "Dummy contacts removed",
        "A similar dry etch removes the SOC. This leaves openings in the ILD down to the "
        "source/drain epitaxy: the replacement-contact openings [R29].", view="sd", match="source",
        figs=["21A", "21B", "21C"], src=[F1])
    # 21
    F.drop("hm112")
    F.add("nisi_source", "nisi_drain", "liner_source", "liner_drain", "ni_source", "ni_drain", "gatecap", "gatew")
    F.snap("contacts", "Replacement contacts",
        "A TiN liner and Co fill the openings, and CMP removes the excess. An anneal forms a silicide "
        "(a metal-silicon compound) where the contact meets the epitaxy. A gate contact is then made "
        "through the hard mask onto the gate electrode [R29].", view="sd", match="source", figs=["22A", "22B", "22C"], src=[F1],
        subs=["The patent's liner options are Ti, TiN, Ta and TaN, and its conductors include Cu, W, Co, "
              "Al and Ni. TiN and Co are drawn, with a Ti-based silicide for the silicide it does not name", "The gate "
              "contact's metal is the model's choice (W)", "The patent's contacts wrap the epitaxy's facets; "
              "a flat contact floor is drawn"])
    # 22
    F.drop("ild")
    F.snap("done", "The finished device",
        "The finished FinFET, with the ILD hidden. Two fins are each wrapped on three faces by the "
        "high-κ/metal gate, which sits under its hard mask. The SiP source and drain grew from the "
        "recessed fin ends. The Co contacts stand where the carbon dummy contacts were [R29].", view="iso",
        match="source", figs=["22A", "22C"], src=[F1], subs=["The ILD is hidden for viewing only"])
    steps = F.done()
    used = {st["match"] for st in steps}
    return dev, steps, dict(
        scope=FIN_SCOPE, figures=FIN_FIGURES, branch=FIN_BRANCH, skipped={},
        audit_tile=(
            "Steps numbered n.k are operation substeps leading into core step n. Those at tile "
            "scale show a 2 × 2 context: an nFET pair of fins (P well) and a pFET pair (N well, "
            "context only), crossed by two gate lines, with the selected nFET site at the "
            "single-site model's origin. The build checks that the tile, cropped to that site, "
            "matches the single-site model at steps 2 and 3."),
        audit_unverified=[
            "**Model choices.** The patent fixes no fin pitch, width, height or spacer width. The 27 nm, "
            "6 nm, 45 nm and 1 + 6 nm are the model's; the wells are named regions.",
            "The lithography operations are concept-level: no optics, dose, resist chemistry, overlay "
            "or mask count is modelled or claimed.",
            "**Patterning routes.** SAQP follows US 9,171,764 B2 with uniform mandrels; its variable "
            "spacing is shown in the Pitch walk lesson. SADP and the direct print are shown for "
            "comparison."],
        refs=["R29", "R30", "R24", "R25", "R26", "R27", "R7", "R16", "R17", "R19", "R20", "R21", "R22", "R23"],
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
    a=("Blue · inside a coated core", "the first coating's thickness"),
    b=("Orange · where a printed core was", "the core's width less two second coatings"),
    c=("Green · between neighbouring cores", "the printed space less both coatings on each side"))
# The gap markers' materials, one colour per kind of gap (see MAT in build_devices.py).
PW_GAP_MAT = dict(a="gap_a", b="gap_b", c="gap_c")
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
        return (f"Measured off the lines, the spaces are: {PW_TYPES['a'][0]} {t['a']} nm, "
                f"{PW_TYPES['b'][0]} {t['b']} nm, {PW_TYPES['c'][0]} {t['c']} nm. "
                f"Largest {fmt(m['max'])} nm, smallest {fmt(m['min'])} nm, so pitch walk = "
                f"{fmt(m['max'])} − {fmt(m['min'])} = {fmt(m['walk'])} nm.")

    SUBS = ["Dimensions are illustrative: Baudot et al.'s example runs 96 → 48 → 24 nm, this lesson 108 → 54 → "
            "27 nm [R22]", "Etch bias, core taper and fin-height effects are described, not simulated"]

    def markers(g, y0, y1, x0=X0, x1=X1, tag=""):
        """A coloured strip in every gap between two lines, one colour per kind of gap."""
        spans = g["lines"]
        by = {}
        for (t, _), l, r in zip(g["gaps"], spans, spans[1:]):
            by.setdefault(t, []).append(box(x0, x1, y0, y1, l[1], r[0]))
        for t in "abc":
            if by.get(t):
                S.put(tmp(f"pw_gap_{t}{tag}", "Gap marker · " + PW_TYPES[t][0].split(" · ")[1] +
                          f" ({PW_TYPES[t][0].split(' · ')[0].lower()})", PW_GAP_MAT[t], "Gap markers",
                          by[t], (0, 0.4, 0)))

    def fins_row(g, x0, x1, tag, name):
        S.put(tmp(f"pw_fins{tag}", name, "silicon", "Fins", [box(x0, x1, YF, 0, a, b) for a, b in g["lines"]], (0, 0, 0)))
        S.put(tmp(f"pw_hm{tag}", "Fin hard mask (patterned)", "si3n4", GP,
                  [box(x0, x1, 0, HM, a, b) for a, b in g["lines"]], (0, 1.0, 0)))
        markers(g, YF, YF + 3.0, x0, x1, tag)

    def plan(g, name="Si fins (etched through the hard mask)"):
        S.now = {}
        S.put(tmp("pw_sub", "Si substrate", "silicon", GS, [box(X0, X1, YS, YF, Z0, Z1)], (0, -1.2, 0)))
        fins_row(g, X0, X1, "", name)

    def say(m):
        return (f"Largest {fmt(m['max'])} nm, smallest {fmt(m['min'])} nm, so pitch walk = "
                f"{fmt(m['max'])} − {fmt(m['min'])} = {fmt(m['walk'])} nm.")

    for case, name, p in PW_CASES:
        if not pw_check(**p): sys.exit(f"pitch walk {case}: outside the allowed limits")
    P0 = PW_BASE
    g_ideal, g_wide = pw_geometry(**P0), pw_geometry(**dict(P0, w1=39.0))
    wide = {t: sorted({w for tt, w in g_wide["gaps"] if tt == t}) for t in "abc"}
    ww = [w for _, w in g_wide["gaps"]]

    # 1. What it is: the even comb, and the same route with the cores printed too wide.
    S.now = {}
    S.put(tmp("pw_sub", "Si substrate", "silicon", GS, [box(X0, X1, YS, YF, Z0, Z1)], (0, -1.2, 0)))
    fins_row(g_ideal, X0, -3.0, "", "Si fins · on target (top row)")
    fins_row(g_wide, 3.0, X1, "_w", "Si fins · cores printed 6 nm too wide (bottom row)")
    S.snap("what", "What pitch walk is",
        f"SAQP makes lines four times as dense as one exposure can print [R20]. They should come out evenly "
        f"spaced, like the teeth of a comb. The top row is on target: {len(g_ideal['lines'])} lines, every gap "
        f"{fmt(g_ideal['gaps'][0][1])} nm. The bottom row is the same route with the printed cores 6 nm too wide. "
        f"Its gaps alternate between {fmt(max(ww))} nm and {fmt(min(ww))} nm. That unevenness is pitch walk, "
        f"measured as the largest gap minus the smallest: {fmt(max(ww))} − {fmt(min(ww))} = "
        f"{fmt(max(ww) - min(ww))} nm here [R22][R20]. It matters because a wide gap etches differently from a "
        "narrow one, so uneven gaps can leave fins of different height [R22]. The coloured strips mark three "
        "kinds of gap; the next step shows where each comes from.",
        view="pwplan", match="teach", subs=SUBS)

    # 2. Where the gaps come from: the route's second stage, cut open, with the gaps marked.
    S.now = {}
    S.put(tmp("pw_sub", "Si substrate (fins to be)", "silicon", GS, [box(X0, X1, YS, 0, Z0, Z1)], (0, -1.2, 0)))
    S.put(tmp("pw_hm", "Fin hard mask (blanket)", "si3n4", GP, [box(X0, X1, 0, HM, Z0, Z1)], (0, 1.0, 0)))
    S.put(tmp("pw_c2", "First coating, kept as the second cores", "mandrel2", GP,
              [box(X0, X1, HM, Y2, a, b) for a, b in g_ideal["core2"]], (0, 1.4, 0)))
    S.put(tmp("pw_sp2", "Second coating: the lines", "patspacer", GP,
              [box(X0, X1, HM, Y2, a, b) for a, b in g_ideal["lines"]], (0, 1.8, 0)))
    markers(g_ideal, Y2 + 3.0, Y2 + 6.0)
    ia, ib, ic = (P0["s1"], P0["w1"] - 2 * P0["s2"], PW_P1 - P0["w1"] - 2 * P0["s1"] - 2 * P0["s2"])
    S.snap("how", "Where the gaps come from",
        f"SAQP starts from printed cores, {fmt(PW_P1)} nm apart and {fmt(P0['w1'])} nm wide, and coats them twice "
        f"[R22]. The first coating ({fmt(P0['s1'])} nm, the first spacer) is kept as a new set of cores: the "
        f"blocks drawn between the lines. The second coating ({fmt(P0['s2'])} nm, the second spacer) on those "
        "becomes the lines. So every gap between two lines is one of three kinds. "
        f"Blue, inside a coated core: it is the first coating itself, {fmt(ia)} nm. "
        f"Orange, where a printed core was: the core's width less two second coatings, "
        f"{fmt(P0['w1'])} − 2 × {fmt(P0['s2'])} = {fmt(ib)} nm. "
        f"Green, between neighbouring cores: the printed space less the coatings on both sides, "
        f"{fmt(PW_P1)} − {fmt(P0['w1'])} − 2 × {fmt(P0['s1'])} − 2 × {fmt(P0['s2'])} = {fmt(ic)} nm. "
        f"On target, all three are {fmt(ia)} nm.",
        view="pwcut", match="source", figs=["1"], src=["R22"], subs=SUBS)

    # 3–5. One size off at a time; the gaps measured off the built fins.
    TEXT = {
        "w1": ("Cores printed too wide",
               lambda p, d, t: f"The printed cores come out {fmt(abs(d))} nm wider: {fmt(p['w1'])} nm instead of "
               f"{fmt(P0['w1'])} nm. Orange gaps widen to {t['b']} nm and green gaps shrink to {t['c']} nm. Blue "
               f"gaps stay {t['a']} nm, because the first coating did not change, and the lines keep their width. ",
               "This is an error in the printing itself. Keeping pitch walk acceptable needs tight control of "
               "the printed core size [R23]."),
        "s1": ("First coating too thin",
               lambda p, d, t: f"The first coating comes out {fmt(abs(d))} nm thinner: {fmt(p['s1'])} nm instead of "
               f"{fmt(P0['s1'])} nm. Blue gaps shrink to {t['a']} nm, since they are the first coating. Green gaps "
               f"widen to {t['c']} nm, and orange gaps stay {t['b']} nm. ",
               "The first coating makes the second cores, so its error moves the gaps inside and around them."),
        "s2": ("Second coating too thick",
               lambda p, d, t: f"The second coating comes out {fmt(abs(d))} nm thicker: {fmt(p['s2'])} nm instead of "
               f"{fmt(P0['s2'])} nm. The lines grow to {fmt(p['s2'])} nm. Orange gaps shrink to {t['b']} nm and "
               f"green gaps to {t['c']} nm, while blue gaps stay {t['a']} nm. ",
               "The second coating sets the line width, so this error changes the fins as well as the gaps."),
    }
    for case, name, p in PW_CASES[1:]:
        ch = {k: p[k] - P0[k] for k in p if p[k] != P0[k]}
        (k, d), = ch.items()
        g = pw_geometry(**p)
        plan(g)
        m = measured(case, p)
        t = {kk: fmt(v[0]) if len(v) == 1 else "/".join(map(fmt, v)) for kk, v in m["types"].items()}
        title, lead, tail = TEXT[k]
        S.snap(case, title, lead(p, d, t) + say(m) + " " + tail, view="pwplan", match="teach", subs=SUBS)
        F.steps[-1]["measure"] = m

    # 6. Back on target; the rule; what is left out.
    plan(g_ideal)
    m = measured("ideal", dict(P0))
    S.snap("rule", "The rule, and what is not simulated",
        f"Back on target, every gap is {fmt(m['max'])} nm. " + say(m) + " The rule: each kind of gap depends on "
        "different films. Blue follows the first coating only. Orange follows the core width and the second "
        "coating. Green follows all three. So an error in one film moves only its own kinds of gap, and the "
        "gaps start to alternate [R22][R20]. What this lesson leaves out: its walls are vertical and every etch "
        "copies its mask exactly. Real cores can taper, so the coatings lean, and etch bias grows or shrinks "
        "every line. Wide and narrow gaps also etch differently, leaving fins of different height [R22]. That "
        "is why in-line metrology tracks these sizes [R20].",
        view="pwplan", match="teach", subs=SUBS)
    F.steps[-1]["measure"] = m
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
        scope="Why SAQP lines can come out unevenly spaced. The lesson shows the even result, where each "
              "kind of gap comes from, and what one film coming out a few nanometres off does to each kind: "
              "pitch walk [R20][R23]. The ideal case is the FinFET route's own lines, checked when the data is "
              "built; the FinFET flow itself always uses the ideal case. Sizes are illustrative (Baudot et al.'s "
              "example is 96 → 48 → 24 nm [R22]). Every gap shown is measured off the built lines; nothing is "
              "simulated.",
        figures="The ideal states are adapted from Baudot et al.'s Fig. 1, as its text describes it [R22]. The "
                "drawings were not available for visual comparison. The varied cases are teaching "
                "reconstructions: Baudot et al. study pitch walk, but these particular variations are the "
                "app's.",
        branch="A separate lesson. It does not change the FinFET flow, whose SAQP route stays ideal.",
        skipped={}, refs=["R22", "R20", "R23"],
        audit_tile="A lesson of its own at line-field scale. When the data is built, the ideal case is "
                   "checked to leave the same line widths and spaces as the FinFET flow's SAQP route. "
                   "Every space in the table below is measured off the built fin boxes.",
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
                       note="Dimensions are illustrative. The controls stop before any space closes. A "
                            "space that closed would merge its two lines into one wide line. One that "
                            "opened past a spacer's thickness would leave a line missing from the "
                            "pattern."))


# ============================================================ pFET BRANCHES ===
# The patent builds a pFET and an nFET from one shared stack [R13]. The nFET flow above is
# left as it is; the pFET is a flow of its own with the same early stages (the tile's
# patterning operations are the nFET flow's own steps, copied), and "both sites" puts the
# two single-site models side by side, one stack pitch apart, joined by their gate line.
# A site selector moves between the three.
PWF = "tin"                              # the pFET's work-function metal: TiN, the usual p-type one
# The pFET's gate films, the same as the nFET's: between its SiGe sheets the Si layers leave
# the same 7 nm the SiGe layers leave between the nFET's Si sheets.
TP_IL, TP_HK, TP_WF = (bd.NS_PROCESS_STACK[k] for k in ("til", "thk", "twf"))
NS_P_REC = 4.0                           # how far the pFET's S/D recess goes into the sub-fin


def ns_dims(stack=None):
    """The nanosheet site's dimensions, read off the finished nFET so nothing can drift."""
    n = bd.build_ns(stack or bd.NS_PROCESS_STACK)
    P = {p["id"]: p for p in n.parts}
    sheets = [lim(P[f"sheet{i}"]["boxes"][0]) for i in (1, 2, 3)]
    D = dict(dev=n, P=P, hz=sheets[0][5], ys=[(s[2], s[3]) for s in sheets],
             STI=lim(P["bdi"]["boxes"][0])[3], sub=lim(P["substrate"]["boxes"][0]),
             ypts=lim(P["pts"]["boxes"][0])[2], ysd=lim(P["epi_drain"]["boxes"][0])[3])
    cap = span(P["gatecap"])
    D.update(zsub=D["sub"][5], ymo=cap[2], ycap=cap[3], hzmo=cap[5], top=D["ys"][-1][1])
    D["sige"] = bd.gaps(D["STI"], D["top"], D["ys"])
    return D


def build_ns_p(stack=None, sheets=None):
    """The nanosheet pFET of the patent's route [R13], in the nFET's frame and dimensions:
    the 25 %-Ge SiGe layers are its channels, the Si layers and SiGe base (about 50 % Ge) are gone from
    its gate region, there is no bottom dielectric isolation (the n-type stopper is under
    it instead), and its p-type source/drain grows from the SiGe ends and the recessed
    sub-fin."""
    # [stack] sets the frame and films (the Process stack by default); [sheets] the channel
    # heights, by default the SiGe layers between the nFET's Si sheets (the exploded view
    # passes the same staggered positions at its enlarged spacing).
    stack = stack or bd.NS_PROCESS_STACK
    D = ns_dims(stack); P = D["P"]
    hz, STI, zsub, hzmo, ymo, ycap = D["hz"], D["STI"], D["zsub"], D["hzmo"], D["ymo"], D["ycap"]
    sub, ysd, sige, ys = D["sub"], D["ysd"], sheets or D["sige"], D["ys"]
    TP_IL, TP_HK, TP_WF = stack["til"], stack["thk"], stack["twf"]
    SUBFIN = -D["ypts"]
    d = bd.Dev("ns_p", "Nanosheet pFET", "GAA · 3 SiGe sheets",
               "The pFET the same stack makes: three 25 %-Ge SiGe sheets, a TiN p-type "
               "work-function metal and a SiGe:B source/drain. Illustrative.")
    d.add("substrate", "Si substrate", "silicon", P["substrate"]["boxes"], "Substrate & isolation", [0, -1.2, 0])
    rec = [box(*sorted((s * XSP, s * XSD)), -NS_P_REC, 0, -hz, hz) for s in (-1, 1)]
    d.add("pts_n", "n-type punch-through stopper (sub-fin)", "pts_n",
          subtract((sub[0], sub[1], -SUBFIN, 0, -hz, hz), rec), "Substrate & isolation", [0, -1.0, 0])
    d.add("sti", "STI (low-κ dielectric)", "lowk", P["sti"]["boxes"], "Substrate & isolation", [0, -.8, 0])
    for i, (a, b) in enumerate(sige):
        d.add(f"psheet{i+1}", f"SiGe nanosheet {i+1} (about 25 % Ge) · pFET channel", "sige",
              [box(-XSP, XSP, a, b, -hz, hz)], "Channel stack", [0, 0, 0])
    films = []
    for k, (name, mat, t0, t) in enumerate((("SiO₂ interfacial layer", "sio2", 0, TP_IL),
                                           ("HfO₂ high-κ", "highk", TP_IL, TP_HK),
                                           ("TiN p-type work-function metal", PWF, TP_IL + TP_HK, TP_WF))):
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
    d.add("mo", "W gate fill (recessed)", "wfill", subtract((-XG, XG, 0, ymo, -hzmo, hzmo), sheets + films),
          "Gate electrode", [0, 1.0, 0])
    d.add("gatecap", "SiN self-aligned-contact (SAC) cap", "si3n4", P["gatecap"]["boxes"], "Gate electrode", [0, 1.4, 0])
    d.add("gatew", "W gate contact (through the SAC cap)", "tungsten", P["gatew"]["boxes"], "Gate electrode", [0, 1.8, 0])
    top = D["top"]
    for s, t in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s * XG, s * XSP))
        # Outer spacer: the SiBCN film on the dummy gate. Inner spacers: the low-κ fill of the
        # pockets the Si and base-layer indent left, between and under the SiGe sheets [R13].
        d.add(f"spacer_{t}", f"SiBCN gate spacer · {t} side", "sibcn",
              [box(xa, xb, 0, ycap, hz, hzmo), box(xa, xb, 0, ycap, -hzmo, -hz), box(xa, xb, top, ycap, -hz, hz)],
              "Spacers", [s * 1.3, 0, 0])
        d.add(f"inner_{t}", f"Low-κ inner spacers · {t} side", "lowk",
              subtract((xa, xb, 0, top, -hz, hz), sheets), "Spacers", [s * 1.1, 0, 0])
    # The nFET's source/drain top is higher than the pFET's by H, at least the BDI's
    # thickness (Fig. 13): drawn with H equal to it, so the pFET's contacts are longer.
    ysd_p = ysd - STI
    ynisi_p = ysd_p + (lim(P["nisi_drain"]["boxes"][0])[3] - lim(P["nisi_drain"]["boxes"][0])[2])
    for s, T in ((-1, "Source"), (1, "Drain")):
        xa, xb = sorted((s * XSP, s * XSD))
        d.add(f"sib_{T.lower()}", f"{T} epi, first layer (Si:B) · from the recessed sub-fin", "silicon",
              [box(xa, xb, -NS_P_REC, 0, -hz, hz)], "Source / drain", [s * 1.5, -.3, 0])
        d.add(f"epi_{T.lower()}", f"{T} epi (SiGe:B)", "sige", [box(xa, xb, 0, ysd_p, -hz, hz)],
              "Source / drain", [s * 1.6, 0, 0])
        ns_, ni_ = (P[f"{k}_{T.lower()}"] for k in ("nisi", "ni"))
        d.add(ns_["id"], ns_["name"], ns_["material"], [box(xa, xb, ysd_p, ynisi_p, -hz, hz)], ns_["group"], ns_["explode"])
        c = lim(ni_["boxes"][0])
        d.add(ni_["id"], ni_["name"], ni_["material"], [box(c[0], c[1], ynisi_p, c[3], c[4], c[5])], ni_["group"], ni_["explode"])
    d.views = dict(bd.build_ns(stack).views)
    d.views["gaa"] = dict(d.views["gaa"], off=d.views["gaa"]["off"] + ["sib_source"])
    d.ysd = ysd_p
    d.finish()
    worst, _ = bd.check(d)
    if worst != 1: sys.exit(f"ns_p: {worst} solids overlap in the finished pFET")
    return d


NS_P_SCOPE = ("How a silicon-germanium nanosheet pFET is made. The steps follow the pFET branch of "
              "the same published route as the nFET flow [R13]: the shared Si/SiGe stack, an n-type "
              "punch-through stopper instead of bottom dielectric isolation, 25 %-Ge SiGe channels "
              "and a boron-doped source/drain. Materials and dimensions are illustrative, in the "
              "nFET model's frame. This is not a verified foundry recipe.")
NS_P_BRANCH = ("The pFET branch starts with the same wafer, stack and patterning as the nFET (the "
               "tile's operations are the nFET flow's own). Then come its own masked operations, in "
               "the patent's order. The nFET beside it is left out here. The Both sites view shows the "
               "two together, with the masks that keep each region's steps to itself and the choice "
               "between a gate cut and a shared gate.")
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
     "selected nFET. The other sites show the pattern's context."),
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
    YHMs = ycap + 6.0
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
        """The pFET stack: [si], [base] and [sg] are the x spans of its Si layers, SiGe base (about 50 % Ge)
        and 25 %-Ge SiGe layers (None: gone); [sheets] puts the finished SiGe channels in."""
        F.drop_prefix("psg"); F.drop_prefix("psi"); F.drop("pbase", "psheet1", "psheet2", "psheet3")
        if base:
            F.put(tmp("pbase", "SiGe base layer, about 50 % Ge (kept under the pFET)", "sige", GL,
                      [box(base[0], base[1], 0, STI, -hz, hz)], (0, -.6, 0)))
        for i, (a, b) in enumerate(sige):
            if sheets: F.add(f"psheet{i+1}")
            elif sg: F.put(tmp(f"psg{i+1}", f"SiGe, about 25 % Ge · layer {i+1} (pFET channel to be)", "sige", GL,
                               [box(sg[0], sg[1], a, b, -hz, hz)]))
        if si:
            for i, (a, b) in enumerate(ys):
                F.put(tmp(f"psi{i+1}", f"Si · layer {i+1} (removed from the pFET's gate later)", "silicon", GL,
                          [box(si[0], si[1], a, b, -hz, hz)]))

    def ild_around(ytop=None):
        """The ILD around everything, up to the gate cap's top, or [ytop]: at the contacts, up
        to the S/D metal's top, so the contacts fill holes in it."""
        others = [b for p in F.now.values() if p["id"] != "ild" for b in p["boxes"]]
        F.put(tmp("ild", "ILD (low-κ)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, ytop or ycap, -zsub, zsub), others), (0, .6, 0)))

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
        "Dopant is implanted just below the surface: n-type under this pFET. The nFET region gets a "
        "p-type stopper. A mask keeps each implant to its own region (shown in the Both sites view). "
        "The patent forms bottom dielectric isolation under the nFET only. Under the pFET the "
        "stopper sits below the channels instead, and the patent credits it with enabling strain "
        "engineering [R13]. Depth and doping are illustrative; real profiles are graded.",
        match="published", figs=["3A/B"],
        subs=["Stopper depth and a uniform doped region are illustrative"],
        omitted=["The nFET region and its p-type stopper"])
    # 3
    F.put(tmp("pbase", "SiGe base layer, about 50 % Ge", "sige", GL,
              [box(sub[0], sub[1], 0, STI, -zsub, zsub)], (0, -.6, 0)))
    for i, (a, b) in enumerate(sige):
        F.put(tmp(f"psg{i+1}", f"SiGe, about 25 % Ge · layer {i+1} (pFET channel to be)", "sige", GL,
                  [box(sub[0], sub[1], a, b, -zsub, zsub)]))
    for i, (a, b) in enumerate(ys):
        F.put(tmp(f"psi{i+1}", f"Si · layer {i+1} (removed from the pFET's gate later)", "silicon", GL,
                  [box(sub[0], sub[1], a, b, -zsub, zsub)]))
    F.snap("superlattice", "Si/SiGe multilayer epitaxy",
        "The same stack as the nFET's, grown once for both: a SiGe base layer (about 50 % Ge), then "
        "25 %-Ge SiGe and Si in turn. For this pFET the roles swap. The 25 %-Ge SiGe layers "
        "become the channels. The Si layers and the SiGe base are removed from its gate region near "
        "the end [R13].",
        match="published", figs=["4A/B"],
        subs=[NS_STACK_SUB])
    # 4
    F.drop("wafer", "pts0")
    F.add("substrate", "sti")
    F.put(tmp("pts_sub", "n-type punch-through stopper (sub-fin)", "pts_n", GS,
              [box(sub[0], sub[1], ypts, 0, -hz, hz)], (0, -1.0, 0)))
    layers((-XSD, XSD), (-XSD, XSD), (-XSD, XSD))
    core("pattern", "Stack patterning and STI",
        "This stack is patterned together with the nFET's, in the same operations (the tile, above). "
        "A hard mask defines the stack lines. A directional etch cuts through the multilayer into the "
        "substrate. Trench oxide is filled, planarised and recessed to the bottom of the SiGe base (about 50 % Ge) "
        "layer [R13]. On the pFET line the sub-fin carries the n-type stopper.",
        match="published", figs=["5A/B"],
        subs=["Stack width, pitch and trench depth are illustrative"])
    # 5
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", "Dummy gate",
              subtract((-XG, XG, 0, top + TOX, -hz - TOX, hz + TOX), F.boxes()), (0, .6, 0)))
    F.put(tmp("dummy", "Dummy gate · a-Si", "poly", "Dummy gate",
              subtract((-XG, XG, 0, ycap, -hzmo, hzmo), F.boxes()), (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ycap, YHMs, -hzmo, hzmo)], (0, 1.4, 0)))
    core("dummy", "Dummy gate stack",
        "The dummy gate is made for both regions at once: a thin sacrificial oxide, a silicon "
        "placeholder gate and a hard mask, patterned across the stacks. The gate line carries on "
        "over the nFET stack beside this one [R13].",
        match="published", figs=["6A/B"],
        subs=["The dummy Si and nitride hard mask are illustrative"])
    # 6
    win = (-XSD, XSD, 0, YHMs + 1.5, -zsub, zsub)
    F.put(tmp("liner", "Oxide liner (SiO₂)", "liner", "Patterning", conformal(F.boxes(), 1.5, win), (0, .8, 0)))
    core("bottom", "pFET protected: the nFET's base layer is removed",
        "A liner and a resist block seal the pFET region (the operations above, on the tile). "
        "Meanwhile the nFET region is opened and its SiGe base layer (about 50 % Ge) etched out. The "
        "pFET keeps its base layer, so no bottom dielectric isolation forms under it. Its n-type "
        "stopper does that job [R13].", match="published", figs=["7A/B", "8A/B"],
        subs=["Liner material and thickness are illustrative"])
    # 7
    F.drop("liner")
    F.put(tmp("spfilm", "SiBCN spacer film (as deposited)", "sibcn", "Spacers",
              conformal(F.boxes(), TSP, (-XSD, XSD, 0, YHMs + TSP, -hzmo, hzmo)), (0, .5, 0)))
    F.snap("spacerdep", "Conformal spacer deposition",
        "The liner comes off, and the spacer dielectric is deposited over both regions. Under the "
        "nFET it fills the cavity left by the base layer. The pFET's stack has no cavity, so here "
        "the film only coats the stack and the dummy gate [R13].", view="cutb",
        match="published", figs=["9A/B"],
        subs=["The patent strips the liner before the spacer film (Fig. 8)",
              "SiBCN is drawn for the spacer film, one of the patent's four examples"])
    # 8
    F.drop("spfilm"); F.add("spacer_source", "spacer_drain")
    F.snap("spaceretch", "Spacer etch-back",
        "The film is etched back over the pFET only (fluorocarbon chemistry), leaving its gate "
        "spacers. The nFET is masked meanwhile (the operation above, on both sites) and keeps its "
        "film whole. Nothing stays under the pFET's stack, which still stands on its base layer [R13].", view="cutb",
        match="published", figs=["10A/B"])
    # 9
    F.drop("pts_sub"); F.add("pts_n")
    layers((-XSP, XSP), (-XSP, XSP), sheets=True)
    F.snap("p_recess", "pFET source/drain recess",
        "The pFET stack outside the gate and spacers is etched away, while a mask protects the nFET "
        "(the operation above, on both sites). The etch goes through the Si and SiGe layers, through "
        "the SiGe base (about 50 % Ge), and on into the implanted sub-fin. The ends of every layer are now "
        "exposed at the recess walls, and so is the sub-fin's silicon at the bottom [R13].",
        match="published", figs=["10A/B"],
        subs=["The recess depth into the sub-fin is illustrative"],
        omitted=["The mask over the nFET (see the operation above)"])
    # 10
    layers((-XG, XG), (-XG, XG), sheets=True)
    F.snap("p_indent", "Si and base-layer indent",
        "A selective etch recesses the exposed Si layers and the SiGe base (about 50 % Ge) sideways. "
        "It leaves the 25 %-Ge SiGe ends in place. This is the reverse of the nFET's indent, where "
        "the SiGe is recessed and the Si kept. The pockets it opens under the spacers set the shape "
        "of the inner spacers [R13].", view="cutb", match="intermediate", figs=["11A/B"])
    # 11
    F.add("inner_source", "inner_drain")
    F.snap("p_inner", "Inner-spacer fill and etch-back",
        "Dielectric fills the pockets and is etched back. It stays only between the SiGe sheet "
        "ends and under the lowest one: these are the inner spacers. The SiGe sheet ends are "
        "exposed again at the recess walls [R13].", view="cutb", match="intermediate", figs=["11A/B"],
        subs=["The patent's inner spacers are low-κ; one low-κ material is drawn"])
    # 12
    F.add("sib_source", "sib_drain", "epi_source", "epi_drain")
    F.snap("p_epi", "p-type source/drain epitaxy",
        "Boron-doped epitaxy grows from two seeds: the SiGe sheet ends at the recess walls and "
        "the silicon of the recessed sub-fin below. Here a thin Si:B layer grows first from the "
        "sub-fin. Then SiGe:B fills the recess and joins the sheet ends [R13]. Grown from the "
        "substrate, the SiGe source/drain has a larger lattice than the silicon under it. So it "
        "pushes on the channel along its length: compressive strain, which helps hole mobility. "
        "That is general background, not the patent's text, and no strain is calculated here.",
        match="published", figs=["11A/B"],
        subs=["Si:B then SiGe:B is an example sequence; layer thicknesses, Ge content and doping "
              "are illustrative"])
    # 13
    F.drop("hardmask")
    ild_around()
    F.snap("ild", "ILD fill and planarisation",
        "Interlayer dielectric (ILD) is deposited over both regions and polished flat. The CMP "
        "removes the hard mask [R13].", match="intermediate", figs=["14A/B"])
    # 14
    F.drop("dummy", "dox")
    F.snap("pull", "Dummy-gate removal",
        "The dummy gate and its oxide are removed from both regions. "
        "At the bottom of the trench the pFET's stack is still whole: Si, 25 %-Ge SiGe and the "
        "SiGe base (about 50 % Ge) [R13].", view="cut", match="published", figs=["14A/B"])
    # 15
    F.drop("pbase"); F.drop_prefix("psi")
    F.snap("p_release", "pFET channel preparation",
        "A selective etch removes the SiGe base (about 50 % Ge) and the Si layers inside the pFET's "
        "gate trench, while the nFET is covered (the operation above). It keeps the 25 %-Ge SiGe: "
        "three SiGe sheets, held at their ends by the source and drain [R13].", view="cut",
        match="published", figs=["15A/B"])
    # 16
    F.add(*[f"p{k}{i}" for k in ("il", "hk", "wf") for i in (1, 2, 3)],
          "pfloor_il", "pfloor_hk", "pfloor_wf", "mo")
    F.snap("p_hkmg", "High-κ and p-type work-function metal",
        "An interfacial oxide and a Hf-based high-κ go round each SiGe sheet. Then comes the p-type "
        "work-function metal. It is deposited in both regions and removed from the nFET, so only the "
        "pFET keeps it. W fills the rest of the trench and is recessed [R13]. With no bottom "
        "isolation, the same films also line the sub-fin's top under the gate. The n-type stopper "
        "keeps that surface from conducting. The gate reaches lower than the top of the nFET's BDI "
        "(claim 3) [R13].",
        view="cut", match="published", figs=["17A/B"],
        subs=["Between the SiGe sheets the Si layers leave 7 nm, the same as between the nFET's "
              "sheets. So the pFET's films are drawn at the nFET's thicknesses and fill those spaces",
              "TiN is drawn as the p-type work-function metal, one of the patent's p-type options (Ru, Pd, "
              "Pt, Co, Ni, metal oxides, TiN, TiSiN, TaN, TaSiN, TiAlN, TaAlN) [R13]"])
    # 17
    F.add("gatecap")
    F.snap("p_cap", "Self-aligned-contact cap",
        "SiN fills the recess over the W: the SAC (self-aligned-contact) cap. The same deposition "
        "fills the gate cut [R13].", view="cut", match="published", figs=["17A/B"],
        subs=["SiN is drawn; the patent also names SiNC and SiBCN"])
    # 18
    F.add("nisi_source", "nisi_drain", "ni_source", "ni_drain", "gatew")
    ild_around(span(F.final["gatecap"])[3])
    F.snap("p_contacts", "Middle-of-line contacts",
        "Source/drain trenches are etched through the ILD, and a gate trench through the SAC cap. The "
        "fill, which may include a silicide, makes the contacts [R13]. The pFET's source/drain top sits "
        "lower than the nFET's, so its contacts reach further down.", match="published", figs=["18A/B"],
        subs=["The TiSiₓ, Co and W contact stack is illustrative; SiGe contacts can need a "
              "different silicide treatment"])
    # 18
    F.drop("ild")
    F.snap("p_done", "The finished pFET",
        "The finished pFET from the shared stack. It has SiGe channels where the nFET has Si ones, an "
        "n-type stopper where the nFET has bottom dielectric isolation, and its own work-function "
        "metal. The ILD is hidden for viewing only.", match="published", figs=["18A/B"],
        subs=["The ILD is hidden for viewing only"])
    return dev, F, dict(
        scope=NS_P_SCOPE, figures=NS_FIGURES, branch=NS_P_BRANCH, skipped=NS_P_SKIPPED,
        refs=["R13", "R1", "R14", "R16", "R17", "R18", "R19", "R20", "R21"],
        audit_unverified=[
            "**Every figure mapping.** The patent's drawings have not been compared with these views. "
            "Orientation, composition and labels may differ from the published artwork.",
            "**Section planes.** X1–X1 (along the pFET stack), Y1–Y1 and Y2–Y2 are placed from the "
            "patent's written description only.",
            "**The shared stack's thicknesses.** Both layers are drawn 7 nm so that each device's "
            "sheets are channel-thin and each gate's films fill the 7 nm between its sheets. The "
            "patent's own layer thicknesses were not checked.",
            "Two things are model choices: when the protective liner over the pFET is removed, and the "
            "Si:B then SiGe:B epitaxy sequence. The recess depth into the sub-fin is illustrative.",
            "The lithography operations are concept-level. The stack patterning routes are the nFET "
            "flow's: a patterning concept applied to an illustrative layer."],
        match=dict(MATCH, **PAT_MATCH), routes=ROUTES,
        route_title="How the stack lines are printed", route_join="the stack etch",
        views=dict(dev.views, cut=CUTAWAY, cutb=INDENT, **TILE_VIEWS, **FIELD_VIEWS))


# ------------------------------------------------------------- both sites ----
# The nFET and pFET single-site models side by side, the pFET one stack pitch across (-z),
# in the tile's frame. What joins them is drawn here: the gate line between the two stacks
# (dummy, spacers, then metal, or metal with a cut) and the masks that keep each region's
# steps to itself. Everything else is the two site flows' own states, part for part.
GATE_METALS = ("mo", "tin", "nwf", "tungsten")


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

    YD, YH = G.get("ydum", ymo), G.get("yhm", ycap)        # dummy gate top; its mask's top
    SPM, SPN = G.get("spm", ("si3n4", "SiN gate spacers"))
    FLM, FLN = G.get("fill", ("mo", "Mo gate fill"))
    CPM, CPN = G.get("capm", ("tin", "TiN gate cap"))

    XDg = G.get("xd", XGg)                              # the dummy gate's half-length
    LN = G.get("liners")                                # gate films lining the trench, if drawn

    def linings(kind, ytop, z0, z1):
        """The gate films on the trench's floor and walls between the stacks: (parts, the
        fill's region). The work-function layer is each device's own, meeting mid-way."""
        if not LN: return [], (-XGg, XGg, y0)
        t1, t2 = LN["hk"], LN["hk"] + LN["wf"]
        inner = lambda t: [box(-XGg + t, XGg - t, y0 + t, ytop, z0, z1)]
        outer = (-XGg, XGg, y0, ytop, z0, z1)
        hk = bd.carve(outer, inner(t1))
        out = [tmp("b_hk", "HfO₂ high-κ · lining the trench between the stacks", "highk", "Tri-gate films", hk, (0, .6, 0))]
        for (a, b), k in (((max(z0, ZMID), z1), "n"), ((z0, min(z1, ZMID)), "p")):
            if a >= b: continue
            wf = bd.carve((-XGg + t1, XGg - t1, y0 + t1, ytop, a, b), [box(-XGg + t2, XGg - t2, y0 + t2, ytop, a, b)])
            out.append(tmp(f"b_wf_{k}", LN[k][1] + " · lining the trench between the stacks", LN[k][0],
                           "Tri-gate films", wf, (0, .8, 0)))
        return out, (-XGg + t2, XGg - t2, y0 + t2)

    def bridge(kind):
        """The gate line's stretch between the stacks, at a stage of [kind]: the dummy gate,
        its spacer film, spacers; the metal with its cap ("metal") or recessed without one
        ("metal0"); the cut opened in the metal ("cutopen"), or filled ("cut"), where one
        dielectric fill makes the cut and the caps."""
        z0, z1 = zb
        out = []
        if kind in ("dummy", "film", "spacers", "spacers0"):
            out.append(tmp("b_dummy", "Dummy gate · Si · between the stacks", "poly", "Dummy gate",
                           [box(-XDg, XDg, y0, YD, z0, z1)], (0, 1.0, 0)))
            if kind != "spacers0":
                out.append(tmp("b_hm", "SiN hard mask · between the stacks", "si3n4", "Dummy gate",
                               [box(-XDg, XDg, YD, YH, z0, z1)], (0, 1.4, 0)))
            if XDg < XGg:
                out.append(tmp("b_seal", "Gate seal spacers (oxide) · between the stacks", "sio2", "Spacers",
                               [box(XDg, XGg, y0, ycap, z0, z1), box(-XGg, -XDg, y0, ycap, z0, z1)], (0, 0, 0)))
        if kind in ("spacers", "spacers0", "trench", "metal", "metal0", "metalfull", "cut", "cutopen"):
            out.append(tmp("b_spacers", SPN + " · between the stacks", SPM, "Spacers",
                           [box(XGg, XSPg, y0, ycap, z0, z1), box(-XSPg, -XGg, y0, ycap, z0, z1)], (0, 0, 0)))
        if kind in ("metal", "metal0", "metalfull"):
            yt = ycap if kind == "metalfull" else ymo
            ln, (fx0, fx1, fy0) = linings(kind, yt, z0, z1)
            out += ln
            out.append(tmp("b_mo", FLN + " · the connection between the two gates", FLM, "Gate electrode",
                           [box(fx0, fx1, fy0, yt, z0, z1)], (0, 1.0, 0)))
        if kind == "metal":
            out.append(tmp("b_cap", CPN + " · between the stacks", CPM, "Gate electrode",
                           [box(-XGg, XGg, ymo, ycap, z0, z1)], (0, 1.4, 0)))
        if kind in ("cut", "cutopen"):
            c0, c1 = ZMID - CW / 2, ZMID + CW / 2
            for (a, b), side in (((c1, z1), "nFET"), ((z0, c0), "pFET")):
                ln, (fx0, fx1, fy0) = linings(kind, ymo, a, b)
                out += [dict(q, id=q["id"] + "_" + side[0]) for q in ln]
                out.append(tmp(f"b_mo_{side[0]}", f"{FLN} · {side} side of the cut", FLM, "Gate electrode",
                               [box(fx0, fx1, fy0, ymo, a, b)], (0, 1.0, 0)))
                if kind == "cut":
                    out.append(tmp(f"b_cap_{side[0]}", f"{CPN} · {side} side of the cut", CPM, "Gate electrode",
                                   [box(-XGg, XGg, ymo, ycap, a, b)], (0, 1.4, 0)))
            if kind == "cut":
                out.append(tmp("b_plug", G.get("plugname", "Gate-cut dielectric (SiN fill)"), G.get("plugm", "si3n4"), "Gate cut",
                               [box(-XGg, XGg, y0, ycap, c0, c1)], (0, 1.6, 0)))
        return out

    def voids(kind):
        """What stands empty on the gate line at [kind]: the whole trench once the dummy gate
        is pulled, the recess over a capless fill, the slot once the cut is etched. The sites'
        dielectrics give way there."""
        z0, z1 = zb
        if kind == "trench": return [box(-XGg, XGg, y0, ycap, z0, z1)]
        if kind == "metal0": return [box(-XGg, XGg, ymo, ycap, z0, z1)]
        if kind == "cutopen": return [box(-XGg, XGg, y0, ycap, ZMID - CW / 2, ZMID + CW / 2),
                                      box(-XGg, XGg, ymo, ycap, z0, z1)]
        return []

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
             extra=(), of=None, view="pair", match="published", figs=(), regions=None, route=None,
             liner_name="Protective liner", liner_mat="liner", block_name="Resist block", **kw):
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
        parts = carve(parts, [x for q in b for x in q["boxes"]] + (voids(br) if br else [])) + b
        S.now = {q["id"]: q for q in parts}
        if film:        # the spacer film over the gate line between the stacks
            # Grown from what it lands on there, the dummy gate and the floor, not from the sites'
            # own film, which already coats the stacks' facing sides.
            base = [x for q in S.now.values() if q["id"].startswith(("b_", "g_")) or
                    q["group"] == "Substrate & isolation" for x in q["boxes"]]
            win = (-XSDg, XSDg, y0, ycap + film, zb[0], zb[1])
            fb = []
            for c in base:
                x0, x1, ya, yb, za, zb_ = lim(c)
                e = (max(x0 - film, win[0]), min(x1 + film, win[1]), max(ya - film, win[2]),
                     min(yb + film, win[3]), max(za - film, win[4]), min(zb_ + film, win[5]))
                if e[0] < e[1] and e[2] < e[3] and e[4] < e[5]:
                    fb += subtract(e, S.boxes() + fb)
            S.put(tmp("b_film", G.get("filmname", "Spacer dielectric (as deposited)") + " · between the stacks", SPM, "Spacers",
                      fb, (0, .5, 0)))
        if liner:       # a protective liner over one region
            z0, z1 = ZR[liner]
            S.put(tmp("m_liner", f"{liner_name} over the {who[liner]} region", liner_mat, "Region masks",
                      conformal(S.boxes(), 1.5, (-XSDg, XSDg, y0, YH + 1.5, z0, z1)), (0, .8, 0)))
        if block:       # a resist block over one region
            z0, z1 = ZR[block]
            S.put(tmp("m_block", f"{block_name} over the {who[block]} region", "resist", "Region masks",
                      subtract((-XSDg, XSDg, y0, YH + 12.0, z0, z1), S.boxes()), (0, 1.6, 0)))
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
         note="The gate line is cut between the two stacks, and the cut is filled with dielectric. "
              "This gives two gates, contacted independently."),
    dict(id="shared", name="Shared gate",
         note="No cut: one gate electrode runs over both stacks, as a CMOS inverter's input needs."),
]
PAIR_SUB = ("The two sites are the nFET and pFET flows' own models, one stack pitch apart. The gate "
            "line between them and the region masks are drawn here. Region masks, their materials and "
            "extents are illustrative")
BRANCH_CACHE = {}


def regions(n, p):
    return dict(n=n, p=p)


def ns_pair(ns, nfinal, psteps, pfinal):
    D = ns_dims()
    G = dict(key="ns_pair", name="Nanosheet · both sites", dz=2 * D["zsub"], y0=0.0, XG=XG, XSP=XSP, XSD=XSD,
             ymo=D["ymo"], ycap=D["ycap"], hzmo=D["hzmo"], zsub=D["zsub"], cut=12.0,
             x=(D["sub"][0], D["sub"][1]), y=(D["sub"][2], 0), r=560.0, yt=40.0, zn=0.0, zp=-2 * D["zsub"],
             spm=("sibcn", "SiBCN gate spacers"), fill=("wfill", "W gate fill"), capm=("si3n4", "SiN SAC cap"),
             ydum=D["ycap"], yhm=D["ycap"] + 6.0, filmname="SiBCN spacer film (as deposited)",
             plugname="SiN fill · the gate cut and the SAC caps, one deposition")
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
    snap("pts_nmask", "n-type implant, nFET masked", "The block moves: now the nFET region is "
         "covered, and the pFET region receives its n-type stopper [R13].", n="pts", p="pts",
         block="n", of="pts", match="intermediate", figs=["3A/B"], subs=SUBS,
         regions=regions("masked", "implanted n-type"))
    snap("pts", "Both stoppers implanted", "Each region has its own stopper: p-type under the nFET, "
         "n-type under the pFET [R13].", n="pts", p="pts", figs=["3A/B"], subs=SUBS,
         regions=regions("p-type stopper", "n-type stopper"))
    snap("superlattice", "One Si/SiGe stack for both", "One multilayer grows over both regions, on a "
         "SiGe base of about 50 % Ge. The nFET will keep its Si layers as channels, and the pFET its "
         "SiGe layers of about 25 % Ge [R13].",
         n="superlattice", p="superlattice", figs=["4A/B"], subs=SUBS + [NS_STACK_SUB],
         regions=regions("shared stack", "shared stack"))
    snap("pattern", "Both stacks patterned", "The two stack lines are patterned together, with shallow "
         "trench isolation (STI) between them [R13]. The nFET and pFET flows show the operations, on "
         "the tile.", n="pattern", p="pattern", figs=["5A/B"], subs=SUBS,
         regions=regions("stack line and sub-fin", "stack line and sub-fin"))
    snap("dummy", "One dummy gate across both", "The dummy gate runs over both stacks and the "
         "isolation between them [R13].", n="dummy", p="dummy", br="dummy", figs=["6A/B"], subs=SUBS,
         regions=regions("dummy gate", "dummy gate"))
    snap("n_open7", "pFET protected, nFET opened", "An oxide liner and an OPL (organic planarising "
         "layer) mask cover the pFET region. The nFET region is open, and the sidewalls of its SiGe base "
         "layer (about 50 % Ge) are exposed [R13].", n="dummy",
         p="dummy", br="dummy", liner="p", block="p", of="bottom", match="intermediate", figs=["7A/B"],
         subs=SUBS, regions=regions("open", "masked"), liner_name="Oxide liner (SiO₂)", block_name="OPL mask")
    snap("bottom", "nFET base layer removed", "Vapor-phase HCl etches the nFET's SiGe base layer (about "
         "50 % Ge) out from under its stack. The dummy gate holds the stack up. The mask is stripped, and "
         "the liner keeps the pFET sealed. The pFET keeps its base layer [R13].", n="bottom", p="bottom", drop=("liner",),
         br="dummy", liner="p", view="pairn", figs=["8A/B"], subs=SUBS, liner_name="Oxide liner (SiO₂)",
         regions=regions("base layer removed: a cavity", "protected; base kept"))
    snap("spacerdep", "Spacer film over both", "The liner comes off, and the SiBCN spacer film is "
         "deposited over both regions. Under the nFET it fills the cavity, which becomes the bottom "
         "dielectric isolation. The pFET has no cavity [R13].", n="spacerdep", p="spacerdep",
         br="dummy", film=XSP - XG, view="paircut", figs=["9A/B"], subs=SUBS,
         regions=regions("spacer film; cavity filled (BDI)", "spacer film"))
    FILM = dict(br="dummy", film=XSP - XG)
    OPL = dict(block_name="OPL mask")
    snap("p_open", "nFET masked, pFET open", "A mask covers the nFET and the gate regions. The pFET "
         "region is open [R13].", n="spacerdep", p="spacerdep", block="n", of="p_etch",
         match="intermediate", figs=["10A/B"], subs=SUBS, regions=regions("masked", "open"), **FILM, **OPL)
    snap("p_etch", "pFET spacer etch-back", "The spacer film is etched back over the pFET only, "
         "leaving its gate spacers. The nFET keeps its film whole: it is what protects the nFET "
         "through all the pFET's steps [R13].", n="spacerdep", p="spaceretch", block="n",
         match="published", figs=["10A/B"], subs=SUBS, regions=regions("film kept, masked", "spacers"),
         **FILM, **OPL)
    for sid, title, body, fig, view in (
            ("p_recess", "pFET source/drain recess", "The pFET stack is recessed outside its spacers, "
             "through its base layer and into the n-type punch-through stopper [R13].", "10A/B", "pairp"),
            ("p_indent", "pFET Si and base-layer indent", "The pFET's Si layers (NH₄OH) and its SiGe base "
             "(HCl or ClF₃) are indented under its spacers. The mask is gone; the nFET is still under its "
             "unetched film [R13].", "11A/B", "pairp"),
            ("p_inner", "pFET inner spacers", "Low-κ inner spacers fill the pFET's pockets [R13].", "11A/B", "pairp"),
            ("p_epi", "pFET source/drain epitaxy", "Si:B then SiGe:B grow from the pFET's SiGe sheet ends "
             "and its recessed stopper. The nFET, sealed in its spacer film, gets none [R13].", "11A/B", "pairp")):
        snap(sid, title, body, n="spacerdep", p=sid, view=view, block="n" if sid == "p_recess" else None,
             match="published" if sid in ("p_recess", "p_epi") else "intermediate", figs=[fig],
             subs=SUBS, regions=regions("film kept" + (", masked" if sid == "p_recess" else ""),
                                        {"p_recess": "recessed", "p_indent": "Si and base indented",
                                         "p_inner": "inner spacers", "p_epi": "SiGe:B source/drain"}[sid]),
             **FILM, **(OPL if sid == "p_recess" else {}))
    AL = dict(liner="p", liner_name="AlOₓ liner", liner_mat="alox")
    snap("n_open", "pFET protected, nFET open", "A 2–3 nm AlOₓ liner and a mask cover the pFET. The "
         "nFET region is open [R13].", n="spacerdep", p="p_epi", block="p", of="n_etch",
         match="intermediate", figs=["12A/B"], subs=SUBS, regions=regions("open", "masked"), **FILM, **OPL, **AL)
    snap("n_etch", "nFET spacer etch-back", "The liner is cleared over the nFET. Its spacer film is "
         "etched back, stopping on the top of the BDI [R13].", n="spaceretch", p="p_epi", br="spacers",
         block="p", match="published", figs=["12A/B"], subs=SUBS, regions=regions("spacers; BDI", "masked"),
         **OPL, **AL)
    for sid, title, body, fig, st in (
            ("recess", "nFET source/drain recess", "The nFET stack is recessed outside its spacers, "
             "stopping on its BDI [R13].", "12A/B", "recessed to the BDI"),
            ("indent", "nFET SiGe indent", "The nFET's SiGe (about 25 % Ge) is indented under its spacers "
             "[R13].", "13A/B", "SiGe indented"),
            ("inner", "nFET inner spacers", "Low-κ inner spacers fill the nFET's pockets [R13].", "13A/B", "inner spacers"),
            ("epi", "nFET source/drain epitaxy", "The mask is removed, and n-type Si grows from the nFET's "
             "Si sheet ends. The pFET, under its AlOₓ liner, gets none. The nFET's top sits higher than the "
             "pFET's by H, at least the BDI's thickness. The AlOₓ liner is then etched back [R13]. Si:P is "
             "the model's choice: the patent names no nFET source/drain material.", "13A/B", "n-type source/drain")):
        snap(sid, title, body, n=sid, p="p_epi", br="spacers", view="pairn", block="p" if sid == "recess" else None,
             match="published" if sid in ("recess", "epi") else "intermediate", figs=[fig],
             subs=SUBS, regions=regions(st, "protected"), **({} if sid == "epi" else AL), **(OPL if sid == "recess" else {}))
    snap("ild", "ILD over both", "A low-κ interlayer dielectric (ILD) fills over both regions. The CMP "
         "that planarises it removes the gate hard mask [R13].", n="ild", p="ild", br="spacers0",
         match="intermediate", figs=["14A/B"], subs=SUBS, regions=regions("buried in ILD", "buried in ILD"))
    snap("pull", "One gate trench over both", "The dummy gate is removed along its whole length. One "
         "trench now runs over both stacks and the isolation between them [R13].", n="pull", p="pull",
         br="trench", view="paircut", figs=["14A/B"], subs=SUBS,
         regions=regions("gate trench open", "gate trench open"))
    snap("p_chopen", "nFET covered, pFET's trench open", "A mask fills the nFET's part of the trench "
         "[R13].", n="pull", p="pull", br="trench", block="n", of="p_release", match="intermediate",
         view="paircut", figs=["15A/B"], subs=SUBS, regions=regions("masked", "open"), **OPL)
    snap("p_release", "pFET channels prepared", "In the pFET's trench, vapor HCl removes the SiGe base and "
         "vapor NH₄OH removes the Si layers. Three SiGe sheets are left [R13].", n="pull", p="p_release", br="trench",
         block="n", view="paircut", figs=["15A/B"], subs=SUBS, regions=regions("masked", "SiGe sheets released"), **OPL)
    snap("n_chopen", "pFET covered, nFET's trench open", "The mask moves to the pFET's part of the "
         "trench [R13].", n="pull", p="p_release", br="trench", block="p", of="release",
         match="intermediate", view="paircut", figs=["16A/B"], subs=SUBS, regions=regions("open", "masked"), **OPL)
    snap("release", "nFET channels released", "In the nFET's trench, ClF₃ removes the 25 % SiGe. Three "
         "Si sheets are left over the BDI [R13].", n="release", p="p_release", br="trench", block="p",
         view="paircut", figs=["16A/B"], subs=SUBS, regions=regions("Si sheets released", "masked"), **OPL)
    snap("hkmg", "Two work functions, one W fill", "High-κ goes into both regions. A p-type "
         "work-function metal is deposited in both and removed from the nFET, and an n-type metal goes "
         "on the nFET. W fills the gate line and is recessed. At this point the two gates are one "
         "conductor [R13].",
         n="hkmg", p="p_hkmg", br="metal0", view="paircut", figs=["17A/B"], subs=SUBS + [
             "Where each work-function stack ends between the stacks is drawn at the stacks' edges"],
         regions=regions("n-type work function", "p-type work function"))
    gate_ends(snap, G, g, n_state="hkmg", p_state="p_hkmg", n_cap="cap", p_cap="p_cap",
              n_done="contacts", p_done="p_contacts",
              figs_cut=["17A/B", "18A/B"], figs_shared=["19A/B"], src={}, SUBS=SUBS,
              fill=[[b[0], b[1], round(b[2] - G["dz"], 4), b[3], b[4], b[5]] for b in pfinal["gatew"]["boxes"]])
    return G, F


def gate_ends(snap, G, g, *, n_state, p_state, n_cap, p_cap, n_done, p_done, figs_cut, figs_shared, src, SUBS,
              shared_note=None, fill=()):
    """The two ways the gate line ends, as alternative routes that never follow each other:
    a cut through the recessed gate metal between the stacks, filled with the same dielectric
    that caps the gate (two gates), or no cut (one gate)."""
    XGg, XSDg, ymo, ycap, CW, ZMID, RT = G["XG"], G["XSD"], G["ymo"], G["ycap"], g["CW"], g["ZMID"], g["RT"]
    RY = ycap + RT + 30.0
    z0, z1 = g["B"]["z"]
    op = (-XGg, XGg, ycap, ycap + RT, ZMID - CW / 2, ZMID + CW / 2)
    rec = (-XGg, XGg, ymo, ycap, -G["dz"] - G["hzmo"], G["hzmo"])      # the recess over the whole gate line
    slot = (-XGg, XGg, ymo, ycap, ZMID - CW / 2, ZMID + CW / 2)
    res = lambda pid, name, mat, bx: tmp(pid, name, mat, "Patterning", bx, (0, 1.6, 0))
    blanket = (-XSDg, XSDg, ycap, ycap + RT, z0, z1)
    sourced = bool(figs_cut) and not shared_note
    m_src = "published" if not src else "source"
    subs_x = [] if not shared_note else [shared_note]
    R = regions("gate line joined", "gate line joined")
    common = dict(n=n_state, p=p_state, drop=("gatecap",), of="gatecut", route="cut", match="concept", subs=SUBS)
    fill_rec = lambda: res("c_rfill", "Photoresist (in the recess over the gate line)", "resist", [box(*rec)])
    snap("cut_coat", "Gate-cut resist", "Resist is spun on, filling the recess over the gate metal [R16].",
         br="metal0", extra=[res("c_res", "Photoresist (coated)", "resist", [box(*blanket)]), fill_rec()],
         regions=R, **common)
    snap("cut_expose", "Gate-cut exposure", "The reticle's chrome covers everything except a short slot "
         "across the gate line, midway between the stacks. The resist in the slot becomes soluble [R16].",
         br="metal0", extra=[res("c_res", "Photoresist (unexposed)", "resist", subtract(blanket, [box(*op)])),
                             res("c_res_x", "Photoresist (exposed: the cut)", "resist_exp", [box(*op)]),
                             res("c_rfill", "Photoresist (in the recess over the gate line)", "resist",
                                 subtract(rec, [box(*slot)])),
                             res("c_rfill_x", "Photoresist (exposed: the cut)", "resist_exp", [box(*slot)]),
                             res("c_ret", "Reticle chrome (in the scanner; not to scale)", "chrome",
                                 subtract((-XSDg, XSDg, RY, RY + 2.0, z0, z1), [box(-XGg, XGg, RY, RY + 2.0, op[4], op[5])]))],
         regions=R, **dict(common, subs=SUBS + ["Exposure is simplified: no optics, proximity, dose or overlay effects"]))
    opened = lambda: [res("c_res", "Photoresist (with the cut opening)", "resist", subtract(blanket, [box(*op)])),
                      res("c_rfill", "Photoresist (in the recess over the gate line)", "resist", subtract(rec, [box(*slot)]))]
    snap("cut_open", "Gate-cut opening", "The developer opens the slot in the resist [R16].", br="metal0",
         extra=opened(), view="paircut", regions=R, **common)
    snap("cut_etch", "Gate-cut etch", "Through the opening, the recessed gate metal and both work-function "
         "stacks are etched down to the isolation at the boundary between the regions. The conductive "
         "link between the two gates is gone. The etch does not touch either device's channels or "
         "source/drain" + (" [R13]." if sourced else "."), br="cutopen", extra=opened(),
         view="paircut", regions=regions("own gate", "own gate"),
         **dict(common, match="teach" if not sourced else "published", figs=figs_cut[:1] if sourced else [],
                subs=SUBS + subs_x))
    cut_ref = " [R13]" if sourced else ""
    snap("gatecut", "Cut and caps filled: two gates", "The resist is stripped. One insulating fill goes "
         "into the slot and over the recessed metal, and is polished. So one deposition makes the cut "
         "and the gate caps" + cut_ref + ". The nFET and pFET now have separate gates, to be contacted "
         "independently" + cut_ref + ".", n=n_cap, p=p_cap, br="cut", route="cut", view="paircut",
         match=m_src if sourced else "teach", figs=figs_cut[:1] if sourced else [],
         subs=SUBS + subs_x + ["The cut is drawn square-walled and exactly as long as the gate. Its "
                               "width is illustrative"],
         regions=regions("own gate", "own gate"), **(src if sourced else {}))
    snap("contacts_cut", "Contacts: two gate contacts", "Each device gets source, drain and gate "
         "contacts. With the cut, each gate has its own contact, through its cap" + (" [R13]" if sourced else
         " [R29]") + ".", n=n_done, p=p_done, br="cut", route="cut", view="pair",
         match=m_src if sourced else "teach", figs=figs_cut[-1:], subs=SUBS + subs_x,
         regions=regions("contacted; own gate", "contacted; own gate"), **src)
    snap("shared", "Shared gate: one input", "The alternative: the gate line is not cut. One gate "
         "fill runs over both devices, each with its own work-function metal" + (
         ". This is Fig. 19's arrangement, an alternative to the cut, not a step after it. Fig. 19 still "
         "draws two gate contacts on the one gate. One is drawn here, as a CMOS inverter's input needs "
         "[R13]." if sourced else ". There is one gate contact, as a CMOS inverter's input needs."),
         n=n_done, p=p_done, drop=("p:gatew",), br="metal", route="shared", view="paircut",
         extra=[q for q in (
             tmp("b_capfill", G.get("capm", ("tin", ""))[1] + " · no second gate contact here", G.get("capm", ("tin", ""))[0],
                 "Gate electrode", [c for b in fill for c in clip([b], (-1e3, 1e3, ymo, ycap, -1e3, 1e3))], (0, 1.4, 0)),
             tmp("b_ildfill", "ILD · no second gate contact here", "ild", "Interlayer dielectric",
                 [c for b in fill for c in clip([b], (-1e3, 1e3, ycap, 1e4, -1e3, 1e3))], (0, .6, 0))) if q["boxes"]],
         match=m_src, figs=figs_shared, subs=SUBS + subs_x + [
             "One gate contact is drawn, over the nFET. Where it lands is illustrative"] +
             (["This is the arrangement the Si/SiGe CMOS Device and Inverter scenes show"] if sourced else []),
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
        op.pop("pair", None); op.pop("route", None); op.pop("from", None)      # its own regions stay
        k = next(i for i, s in enumerate(F.steps) if s["level"] == "core" and s["id"] == op["of"])
        F.steps.insert(k, op)


def attach_regions(steps, pair_steps, side):
    """Each step says what state both regions are in, read off the both-sites flow."""
    cores = [s for s in pair_steps if s["level"] == "core" and not s.get("route")] + \
            [s for s in pair_steps if s["level"] == "core" and s.get("route") == "cut"]
    last = None
    for st in steps:
        if st["level"] != "core": continue
        # The first state of the both-sites flow where this side has reached this step (the
        # pFET's epitaxy is the pair's p_epi, not its nFET epi), else the step of the same id.
        m = next((s for s in cores if s["pair"][side] == st["id"]), None) or \
            next((s for s in cores if s["id"] == st["id"]), None)
        # A step the both-sites flow does not show (the finished device, say) keeps the last state.
        if m:
            last = m["regions"]
            # A single-site flow draws neither ending, so a route's state is said neutrally.
            if m.get("route"):
                last = {k: "contacted" if v.startswith("contacted") else "gate cut or shared (see Both sites)"
                        for k, v in last.items()}
        if last: st["regions"] = last
    nxt = None
    for st in reversed(steps):
        if st["level"] == "core": nxt = st.get("regions")
        elif nxt and "regions" not in st: st["regions"] = nxt


def flow_ns_p_all(done):
    dev, F, extra = flow_ns_p(done)
    ns = done["ns"]
    nfinal = {p["id"]: p for p in bd.build_ns(bd.NS_PROCESS_STACK).parts}
    G, PF = ns_pair(ns, nfinal, F.steps, F.final)
    insert_pair_ops(F, PF.steps, ["pts_nmask", ("p_open", "spaceretch"), "p_chopen"])
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
        scope="The nanosheet nFET and pFET together, as the patent makes them from one stack [R13]. "
              "The two single-site models sit one stack pitch apart, joined by their gate line, with the "
              "masks that keep each region's steps to itself. At the end the gate line is either cut "
              "into two gates or kept as one shared gate: two alternatives, not two steps. "
              "Materials and dimensions are illustrative. This is not a verified foundry recipe.",
        figures=NS_FIGURES,
        branch="Both sites: one nFET and one pFET, not a finished circuit. Each site is its own "
               "flow's model at that stage. The gate line between the stacks and the region masks are "
               "drawn here. The 2 × 2 tile's patterning operations are in the nFET and pFET flows.",
        skipped={}, refs=["R13", "R16"],
        match={k: v for k, v in dict(MATCH, **FIN_MATCH).items() if k in {st["match"] for st in steps}},
        routes=GATE_ROUTES,
        route_title="How the gate line ends", route_join="", route_kind="terminal",
        views=pair_views(G),
        audit_tile="Every state is the nFET flow's state and the pFET flow's state named in the "
                   "Match column's step, side by side one stack pitch apart. The build checks four "
                   "things: the composition has no overlaps; each region mask covers only its own region; "
                   "the gate cut leaves no conductive path between the two gates and cuts no "
                   "stack, sheet or source/drain; and the shared gate keeps them connected.")




# ------------------------------------------------------------ FinFET pFET ----
# The FinFET model's pFET is the nFET's geometry with its own materials: the fins in an
# n-well, a selectively grown SiGe:B source/drain with the nFET masked, and a separate
# p-type work-function metal. Every state is the nFET flow's, part for part, with those
# parts swapped, so the two cannot drift apart; the region masks are in Both sites.
FIN_P_BODY = dict(
    substrate="The flow starts from a bulk silicon wafer. This pFET is made in region 50C, for p-type "
              "devices; the nFET beside it is made in region 50B [R29].",
    fins="Fins are etched into the wafer (Fig. 3). The trenches are filled with FCVD silicon oxide, "
         "annealed and polished (Fig. 4). The oxide is recessed so each fin stands 45 nm above it "
         "(Fig. 5). Then the wells are implanted through photoresist masks: an N well here (phosphorus "
         "or arsenic, up to 10¹⁸ cm⁻³) and a P well in the n-type region, followed by an anneal [R29]. "
         "The Steps tab's patterning route shows how the fin lines are printed: SAQP [R30], beside "
         "SADP and a direct print.",
    dspacer="With the n-type region masked, a dummy spacer layer is deposited over the p-type region. A "
            "directional etch leaves dummy gate spacers on the seal spacers. They set where the "
            "recess starts and are removed after the epitaxy [R29].",
    epi="SiGeB grows epitaxially in the recesses, with the nFET region masked (see Both sites). The "
        "patent's p-type options are SiGe, SiGeB, Ge and GeSn [R29]. Grown on the silicon fin, the larger "
        "SiGe lattice squeezes the channel along its length: compressive strain, which helps holes. "
        "That is general background. The patent does not discuss strain, and none is calculated here.",
    metal="The pFET gets its own gate electrode, formed with the nFET masked. It is TiN, the first on "
          "the patent's list and the usual p-type work-function metal. The Co fill and CMP follow. The "
          "metal wraps three faces of each fin: the tri-gate [R29].",
    done="The finished FinFET pFET, with the ILD hidden. Two fins in an N well are wrapped on three faces "
         "by the high-κ and TiN gate, under its hard mask. They sit between a SiGeB source and drain, "
         "with Co replacement contacts. Its geometry is the nFET model's; only its materials and doping differ.")
FIN_P_SUBS = dict(
    epi=["The SiGeB composition and facets are illustrative. The two-step facet is the nFET model's shape"],
    metal=["TiN is drawn as the pFET's work-function metal; its thickness is illustrative"])
FIN_P_TEXT = [
    ("Only the selected nFET is carried to a finished device; the other three are context.",
     "In this flow the pFET pair beside the selected nFET is the one followed. The other sites are "
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
            q.update(material="sige", name=p["name"].replace("(SiP)", "(SiGeB)"))
        elif (p["id"].startswith("tin") and p["id"] != "tin") or p["id"] == "floor_wf":
            q.update(material=PWF, name=p["name"].replace(" (Al-containing)", "")
                     .replace("n-type work-function metal", "TiN p-type work-function metal"))
        elif p["id"].startswith("fin"):
            q.update(name=p["name"].replace("(P well)", "(N well)"))
        elif p["id"] == "substrate":
            q.update(name="Si substrate · N well (pFET region)")
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
        if st["scale"] == "site" and st["id"] == "dspacer":
            st["omitted"] = ["The mask over the n-type region"]
        if st["scale"] == "site":
            st["omitted"] = [o for o in st["omitted"] if "pFET" not in o] + (
                ["The nFET region beside it and the masks over it (see Both sites)"]
                if st["id"] in ("epi", "metal") else [])
            for p in st["parts"]:
                if isinstance(p, dict) and p["id"] in ("fin1_full", "fin2_full"):
                    p["name"] += " (N well)"
                if isinstance(p, dict) and p["id"] == "floor_wf_dep":
                    p.update(material=PWF, name=p["name"].replace(" (Al-containing)", "")
                             .replace("n-type work-function metal", "TiN p-type work-function metal"))
        if st["id"] == "epi" and st["level"] == "core":
            st["title"] = "SiGeB source/drain epitaxy"
        if st["id"] == "metal": st["title"] = "Replacement gate (p-type)"
        if st["id"] == "done": st["title"] = "The finished pFET"
    extra = {k: v for k, v in fin.items() if k not in ("steps", "sections", "badge", "badge_note", "site", "sites")}
    extra = json.loads(json.dumps(extra))
    extra.update(
        scope="How a bulk silicon FinFET pFET is made, gate last. It follows the FinFET flow's stages, "
              "with the pFET's own steps: an n-well, a SiGe:B source/drain grown with the nFET masked "
              "[R25], and a separate p-type work-function metal. The geometry is the nFET model's; "
              "materials, masks and dimensions are illustrative. This is not a verified foundry recipe.",
        branch="The pFET branch starts with the same wafer, fins and gate patterning as the nFET (the "
               "tile's operations are the nFET flow's own). Then come its own masked operations. The "
               "Both sites view shows the two together, with the region masks and the choice between "
               "a gate cut and a shared gate.",
        own=True, name=dev.name, bounds=dev.bounds, final=dev.parts)
    extra["views"] = dict(bd.build_fin().views, **extra["views"])
    extra["audit_unverified"] = extra.get("audit_unverified", []) + [
        "**The pFET's model.** Its geometry is the nFET model's. The n-well, SiGe:B source/drain and "
        "p-type work-function metal are named and coloured, not dimensioned. No strain or "
        "threshold is calculated.",
        "The masks that keep each region's steps to itself are shown in Both sites. Their materials "
        "and the order of the masked steps are illustrative."]
    return dev, steps, extra


def fin_pair(fin, nfinal, psteps, pfinal):
    fd = bd.build_fin()
    P = {p["id"]: p for p in fd.parts}
    cap = span(P["gatecap"]); zsub = lim(P["substrate"]["boxes"][0])[5]
    G = dict(key="fin_pair", name="FinFET · both sites", dz=81.0, y0=12.0, XG=9.0, xd=8.0, XSP=16.0, XSD=38.0,
             liners=dict(hk=bd.THK, wf=bd.TTIN, n=("nwf", "n-type work-function metal (Al-containing)"),
                         p=(PWF, "TiN p-type work-function metal")),
             ymo=cap[2], ycap=cap[3], hzmo=cap[5], zsub=zsub, cut=10.0, x=(-48.0, 48.0), y=(-26.0, 0),
             r=500.0, yt=35.0, zn=13.5, zp=13.5 - 81.0, ydum=cap[3], yhm=cap[3] + 6.0,
             spm=("si3n4", "SiN gate spacers"), fill=("cofill", "Co gate fill"), capm=("alox", "AlOₓ hard mask"),
             plugm="alox", plugname="AlOₓ fill · the cut and the hard mask in one deposition (teaching)")
    snap, S, F, g = pair_builder(G, fin, nfinal, psteps, pfinal)
    SUBS = [PAIR_SUB, "The wells are named regions, not doping profiles"]
    src = dict(src=["R29"])
    no_dsp = ("n:dsp_source", "n:dsp_drain")
    snap("substrate", "One wafer, two regions", "Region 50B for n-type devices, 50C for p-type ones [R29].",
         n="substrate", p="substrate", match="source", figs=["2"], subs=SUBS,
         regions=regions("n-type region", "p-type region"), **src)
    snap("fins", "Both fin pairs", "The fins of both devices are patterned together, with STI (shallow "
         "trench isolation) between them [R29]. The nFET and pFET flows show the operations, on the tile.", n="fins",
         p="fins", match="source", figs=["3", "4", "5"], subs=SUBS, regions=regions("fins", "fins"), **src)
    snap("nwell", "N-well implant, nFET masked", "A photoresist covers the n-type region while the p-type "
         "region is implanted for its N well (phosphorus or arsenic). The patent's example also does "
         "the N well first [R29].", n="fins", p="fins", block="n", block_name="Photoresist", of="wells",
         match="source", figs=["5"], subs=SUBS, regions=regions("masked", "N-well implant"), **src)
    snap("pwell", "P-well implant, pFET masked", "That photoresist is removed. A second one covers the "
         "p-type region while the n-type region is implanted for its P well (boron or BF₂) [R29].",
         n="fins", p="fins", block="p", block_name="Photoresist",
         of="wells", match="source", figs=["5"], subs=SUBS, regions=regions("P-well implant", "masked"), **src)
    snap("wells", "Two wells", "There is now a P well under the nFET's fins and an N well under the "
         "pFET's. An anneal follows [R29].", n="fins", p="fins", match="source", figs=["5"], subs=SUBS,
         regions=regions("P well", "N well"), **src)
    snap("dummy", "One dummy gate across both", "The dummy gate runs over both fin pairs and the STI "
         "between them [R29].", n="dummy", p="dummy", br="dummy", match="source", figs=["6", "7A"],
         subs=SUBS, regions=regions("dummy gate", "dummy gate"), **src)
    snap("seal", "Seal spacers on both", "Gate seal spacers form on the dummy gate over both regions. "
         "The LDD (lightly doped drain) implants follow, region by region [R29].", n="seal", p="seal", br="dummy", match="source",
         figs=["7A", "7B"], subs=SUBS, regions=regions("seal spacers", "seal spacers"), **src)
    snap("n_mask", "pFET masked", "A mask covers the p-type region [R29].", n="seal", p="seal", br="dummy",
         block="p", block_name="Mask", of="n_dsp", match="source", figs=["8A"], subs=SUBS,
         regions=regions("open", "masked"), view="pairsd", **src)
    for sid, nsid, title, body in (
            ("n_dsp", "dspacer", "nFET dummy spacers", "A dummy spacer layer is deposited over the n-type "
             "region and etched directionally [R29]."),
            ("recess", "recess", "nFET fins recessed", "The nFET's fins are recessed beside its dummy "
             "spacers [R29]."),
            ("epi", "epi", "nFET SiP epitaxy", "SiP grows in the nFET's recesses. The pFET, masked, gets "
             "none [R29].")):
        snap(sid, title, body, n=nsid, p="seal", br="dummy", block="p", block_name="Mask", view="pairsd",
             match="source", figs=["8A", "8B"], subs=SUBS,
             regions=regions({"n_dsp": "dummy spacers", "recess": "recessed", "epi": "SiP source/drain"}[sid], "masked"), **src)
    snap("n_clean", "nFET dummy spacers removed", "The mask and the nFET's dummy spacers are removed [R29].",
         n="epi", p="seal", br="dummy", drop=no_dsp, view="pairsd", match="source", figs=["8A", "8B"],
         subs=SUBS, regions=regions("SiP source/drain", "seal spacers"), **src)
    snap("p_mask", "nFET masked", "Now a mask covers the n-type region [R29].", n="epi", p="seal", br="dummy",
         drop=no_dsp, block="n", block_name="Mask",
         of="p_dsp", match="source", figs=["8A", "8B"], subs=SUBS, regions=regions("masked", "open"),
         view="pairsd", **src)
    for sid, psid, title, body in (
            ("p_dsp", "dspacer", "pFET dummy spacers", "The same over the p-type region [R29]."),
            ("p_recess", "recess", "pFET fins recessed", "The pFET's fins are recessed [R29]."),
            ("p_epi", "epi", "pFET SiGeB epitaxy", "SiGeB grows in the pFET's recesses. The nFET, masked, "
             "gets none [R29].")):
        snap(sid, title, body, n="epi", p=psid, br="dummy", drop=no_dsp, block="n", block_name="Mask",
             view="pairsd", match="source", figs=["8A", "8B"], subs=SUBS,
             regions=regions("masked", {"p_dsp": "dummy spacers", "p_recess": "recessed", "p_epi": "SiGeB source/drain"}[sid]), **src)
    snap("spacers", "Gate spacers on both", "The pFET's dummy spacers and the mask are removed. SiN gate "
         "spacers form along the whole gate line [R29].", n="spacers", p="spacers", br="spacers", match="source",
         figs=["9A", "9B"], subs=SUBS, regions=regions("gate spacers", "gate spacers"), **src)
    snap("dild", "Dummy ILD over both", "The dummy ILD (PSG) covers both regions [R29].", n="dild", p="dild",
         br="spacers", match="source", figs=["10A"], subs=SUBS, regions=regions("buried in dummy ILD", "buried in dummy ILD"), **src)
    snap("cmp", "Polished to the dummy gate", "CMP polishes down to the dummy gates' tops and removes their "
         "mask [R29].",
         n="cmp", p="cmp", br="spacers0", match="source", figs=["11A"], subs=SUBS,
         regions=regions("dummy gate exposed", "dummy gate exposed"), **src)
    snap("pull", "One gate trench over both", "The dummy gate is removed along its whole length [R29].",
         n="pull", p="pull", br="trench", view="paircut", match="source", figs=["12A"], subs=SUBS,
         regions=regions("gate trench open", "gate trench open"), **src)
    snap("wf_mask", "nFET covered for the p-type gate", "A mask covers the nFET's part of the trench while "
         "the pFET gets its own gate materials. The patent lets the two regions' gate dielectrics and "
         "electrodes be formed in separate processes [R29].", n="pull", p="metal", drop=("p:mo_dep",),
         br="trench", block="n", block_name="Mask", of="metal", view="paircut", match="source", figs=["13A"],
         subs=SUBS + ["The p-type gate is drawn without its fill until the shared fill step"],
         regions=regions("masked", "p-type gate materials"), **src)
    snap("metal", "Two gates, one Co fill", "The nFET has an Al-containing work-function layer and the pFET "
         "has TiN, each on the high-κ that lines the whole trench. The Co fill carries on between the fin "
         "pairs and is polished [R29].", n="metal", p="metal",
         br="metalfull", view="paircut", match="source", figs=["13A"],
         subs=SUBS + ["One Co fill for both is the model's choice. The patent lets the two regions' electrodes "
                      "be the same or different [R29], and its Fig. 13A draws two that meet"],
         regions=regions("n-type gate", "p-type gate"), **src)
    snap("grecess", "Gate line recessed", "The whole gate line is recessed [R29].", n="grecess", p="grecess",
         br="metal0", view="paircut", match="source", figs=["14A"], subs=SUBS,
         regions=regions("recessed gate", "recessed gate"), **src)
    gate_ends(snap, G, g, n_state="grecess", p_state="grecess", n_cap="hmask", p_cap="hmask",
              n_done="contacts", p_done="contacts", figs_cut=[], figs_shared=["15A", "22A"], src=src, SUBS=SUBS,
              shared_note="The FinFET patent does not describe a gate cut. The cut route is a teaching "
                          "reconstruction, cut before the hard mask so that the same deposition fills it",
              fill=[[b[0], b[1], round(b[2] - G["dz"], 4), b[3], b[4], b[5]] for b in pfinal["gatew"]["boxes"]])
    return G, F


def flow_fin_p_all(done):
    dev, steps, extra = flow_fin_p(done)
    fin = done["fin"]
    nfinal = {p["id"]: p for p in bd.build_fin().parts}
    pfinal = {p["id"]: p for p in dev.parts}
    G, PF = fin_pair(fin, nfinal, steps, pfinal)
    tmpF = type("F", (), dict(steps=steps))
    insert_pair_ops(tmpF, PF.steps, [("nwell", "fins"), ("p_mask", "dspacer"), "wf_mask"])
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
        scope="The FinFET nFET and pFET together. The two single-site models sit one site width apart, "
              "joined by their gate line. Masks keep each region's own steps to itself: its wells, its "
              "source/drain epitaxy and its work-function metal. At the end the gate line is either cut "
              "into two gates or kept as one shared gate: alternatives, not two steps. This is "
              "illustrative, not a verified foundry recipe.",
        figures=FIN_FIGURES,
        branch="Both sites: one nFET and one pFET, not a finished circuit. Each site is its own "
               "flow's model at that stage. The gate line between them and the region masks are drawn "
               "here. The tile's patterning operations are in the nFET and pFET flows.",
        skipped={}, refs=["R29", "R16"],
        match={k: v for k, v in dict(MATCH, **FIN_MATCH).items() if k in used}, routes=GATE_ROUTES,
        route_title="How the gate line ends", route_join="", route_kind="terminal",
        views=pair_views(G),
        audit_tile="Every state is the nFET and pFET flows' own states side by side, one site width "
                   "apart. The build checks the composition for overlaps. The tests check that "
                   "each region mask covers only its own region, that the gate cut leaves no "
                   "conductive path between the two gates and cuts no fin or source/drain, and that "
                   "the shared gate keeps them connected.",
        audit_unverified=["**Every figure mapping.** F1's drawings have not been compared with these "
                          "views.", "The gate cut and shared gate are teaching reconstructions. The "
                          "F1 text read here does not describe a gate cut.",
                          "Region masks, their materials and the order of the masked steps are "
                          "illustrative."])


FLOWS = {"ns": flow_ns, "fin": flow_fin, "sadp": lesson("sadp"), "saqp": lesson("saqp"), "pitchwalk": flow_pitchwalk,
         "ns_p": flow_ns_p_all, "ns_pair": flow_ns_pair, "fin_p": flow_fin_p_all, "fin_pair": flow_fin_pair,
         # The Si/Si CMOS design's lesson: a separate route (scripts/build_nssi.py), not a branch of these.
         "ns~si": lambda done: __import__("build_nssi").flow(done)}


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
TEXT_STATUS = ("The source's text describes this stage. Its drawing has not been compared "
               "with this section")
NS_PLANES = [
    dict(id="x2", name="Along the nFET stack, through the gate", short="Along nFET", axis="z", pos=0.0,
         text="The patent's X2–X2 direction: along the nFET stack, crossing its gate. The direction "
              "comes from the patent's text and drawings."),
    dict(id="y1", name="Across the stacks, through the gate", short="Across · gate", axis="x", pos=0.0,
         text="The patent's Y1–Y1 direction: across the stacks, through the gate region. The direction "
              "comes from the patent's text and drawings. Before the gate is made, the plane "
              "is where it will be."),
    dict(id="y2", name="Across the stacks, through the source/drain", short="Across · S/D", axis="x",
         pos=(XSP + XSD) / 2,
         text="The patent's Y2–Y2 direction: across the stacks, through the source/drain region (here "
              "the drain side). The direction comes from the patent's text and drawings."),
]
FIN_PLANES = [
    dict(id="across_gate", name="Across the fins, at the gate", short="Across · gate", axis="x", pos=0.0,
         text="The direction of the patent's A–A line (its Fig. 1): across the channel, the gate "
              "dielectric and the gate electrode. Before the gate is made, the plane is where it will "
              "be. In the line field it crosses every patterned line."),
    dict(id="along_fin", name="Along fin 2, source to drain", short="Along fin", axis="z", pos=13.5,
         text="The direction of the patent's B–B line (its Fig. 1): along the fin, the direction "
              "current flows between source and drain. Here it runs through the middle of fin 2."),
    dict(id="across_sd", name="Across the fins, through the drain", short="Across · S/D", axis="x",
         pos=27.0,
         text="The app's own section, through the drain epitaxy, parallel to A–A."),
]
# The pFET flows follow the pFET: in their single-site views it is at the origin, in the tile
# and the field around it one site pitch across (-z).
FIN_P_PLANES = [FIN_PLANES[0], dict(FIN_PLANES[1], name="Along a pFET fin, source to drain",
                                    at=dict(tile=13.5 - 81.0, field=13.5 - 81.0)), FIN_PLANES[2]]
NS_FIG_TEXT = {
    "2A/B": "The starting substrate.",
    "3A/B": "Punch-through-stopper implants: p-type under the nFET region, n-type under the pFET region.",
    "4A/B": "One shared Si/SiGe stack for both devices, over a 50 %-Ge SiGe base layer.",
    "5A/B": "The stack patterned into lines, with shallow trench isolation between them.",
    "6A/B": "A dummy gate across the stacks.",
    "7A/B": "The pFET region protected by a liner and mask while the nFET region is opened.",
    "8A/B": "The nFET's 50 %-Ge base layer removed selectively, leaving a cavity under its stack.",
    "9A/B": "Spacer dielectric deposited; it also fills the nFET's bottom-isolation cavity.",
    "12A/B": "The nFET's source/drain regions recessed, with the pFET protected.",
    "13A/B": "The nFET's 25 %-Ge SiGe indented, inner spacers formed and its source/drain grown.",
    "14A/B": "ILD deposited and polished, and the dummy gate removed.",
    "16A/B": "The nFET's 25 %-Ge SiGe removed in the gate region, releasing its Si channels.",
    "17A/B": "Separate work-function treatments for the nFET and the pFET, and an optional gate cut.",
    "18A/B": "Contacts, with the two gates contacted independently after the gate cut.",
    "10A/B": "The pFET's source/drain regions recessed through its 50 %-Ge base layer and into the "
             "implanted substrate, with the nFET protected.",
    "11A/B": "The pFET's Si layers and 50 %-Ge base indented, inner spacers formed so the 25 %-Ge SiGe "
             "remains as channels, and p-type source/drain grown from the SiGe edges and the substrate.",
    "15A/B": "With the nFET protected, the pFET's 50 %-Ge base and Si layers removed in the gate "
             "region, keeping the 25 %-Ge SiGe sheets.",
    "19A/B": "An alternative arrangement in which the two devices share one gate.",
}
FIN_FIG_TEXT = {
    ("R29", "2"): "The substrate, with a region for n-type devices and one for p-type devices.",
    ("R29", "3"): "Fins etched into the substrate as semiconductor strips.",
    ("R29", "4"): "Insulation material (FCVD oxide) between the fins, annealed and planarised.",
    ("R29", "5"): "The isolation recessed so the fins protrude (STI); wells implanted, region by region.",
    ("R29", "6"): "A dummy dielectric, a dummy gate layer (polysilicon) and a mask layer deposited.",
    ("R29", "7"): "The masks patterned, dummy gates formed over the fins; gate seal spacers, LDD implants.",
    ("R29", "8"): "Dummy gate spacers, the fins recessed and epitaxial source/drain grown, region by region.",
    ("R29", "9"): "Gate spacers formed on the gate seal spacers.",
    ("R29", "10"): "A dummy ILD deposited.",
    ("R29", "11"): "Planarisation to the dummy gates' tops, removing their masks.",
    ("R29", "12"): "The dummy gates and dummy dielectric removed, opening recesses over the channels.",
    ("R29", "13"): "Gate dielectric and gate electrodes deposited in the recesses and polished.",
    ("R29", "14"): "The gate dielectric and electrodes recessed.",
    ("R29", "15"): "A hard mask formed in the recesses over the gates and polished.",
    ("R29", "16"): "The dummy ILD removed, exposing the source/drain.",
    ("R29", "17"): "Spin-on-carbon dummy contact material filled in and baked.",
    ("R29", "18"): "The dummy contact material planarised to the spacers and hard mask.",
    ("R29", "19"): "Tri-layer lithography and an etch pattern the dummy contact material.",
    ("R29", "20"): "An ILD formed in the openings.",
    ("R29", "21"): "The dummy contact material removed, opening the contact openings.",
    ("R29", "22"): "Replacement contacts (liner and conductor) formed; a silicide at the epitaxy; a gate contact through the hard mask.",
    ("R30", "1"): "The mask stack: hard mask, lower mandrel layer, hard mask, upper mandrel layer, photoresist.",
    ("R30", "2"): "Upper mandrels etched from the upper mandrel layer.",
    ("R30", "3"): "A spacer-forming layer deposited conformally over the upper mandrels.",
    ("R30", "4"): "The layer etched to upper sidewall spacers.",
    ("R30", "5"): "The upper mandrels removed and the lower mandrels etched under the upper spacers.",
    ("R30", "6"): "A spacer-forming layer deposited over the lower mandrels.",
    ("R30", "7"): "The layer etched to lower sidewall spacers.",
    ("R30", "8"): "The lower mandrels removed: the lower spacers are the mask.",
    ("R30", "9"): "The hard mask and substrate etched into fin pairs.",
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
    dummy=["across_gate", "along_fin"], seal=["along_fin"], dspacer=["along_fin"],
    recess=["along_fin", "across_sd"], epi=["along_fin", "across_sd"], spacers=["along_fin"],
    dild=["along_fin", "across_sd"], cmp=["along_fin"], pull=["across_gate", "along_fin"],
    metal=["across_gate", "along_fin"], grecess=["across_gate", "along_fin"], hmask=["across_gate", "along_fin"],
    dildout=["across_sd"], soc=["across_sd", "along_fin"], soccmp=["across_sd"], socpat=["across_sd"],
    ild=["across_sd"], socout=["across_sd"], contacts=["along_fin", "across_sd"], done=["along_fin", "across_sd"])


def plane_view(pl, scale, bounds):
    """The camera for a plane at a scale: square on to the cut face, the kept half behind it."""
    b = bounds
    pos = pl.get("at", {}).get(scale, pl["pos"])
    fr = "pair" if pl.get("wide") else scale       # framing: a site scene may hold both devices
    ym = (b["y"][0] + b["y"][1]) / 2 if fr != "site" else 40.0
    r = {"site": 255.0, "tile": 460.0, "field": 660.0, "pair": 440.0}[fr]
    if pl["axis"] == "x":
        return dict(n=pl["name"], s="section plane", az=1.5708, el=0.1, r=r,
                    tgt=[pos, min(ym, 60.0), (b["z"][0] + b["z"][1]) / 2 if fr != "site" else 0.0],
                    clip=[pos, None, None], scale=scale)
    return dict(n=pl["name"], s="section plane", az=0.0, el=0.1, r=r,
                tgt=[(b["x"][0] + b["x"][1]) / 2 if fr != "site" else 0.0, min(ym, 60.0), pos],
                clip=[None, None, pos], scale=scale)


def cut_by(parts, pl, scale="site"):
    """Names of the parts the plane passes through, in drawing order."""
    k = 0 if pl["axis"] == "x" else 2
    pos = pl.get("at", {}).get(scale, pl["pos"])
    names = []
    for p in parts:
        for b in p["boxes"]:
            lo, hi = b[k] - b[k + 3] / 2, b[k] + b[k + 3] / 2
            if lo < pos - 1e-6 and hi > pos + 1e-6:
                if p["name"] not in names: names.append(p["name"])
                break
    return names


NS_P_PLANES = [
    dict(id="x1", name="Along the pFET stack, through the gate", short="Along pFET", axis="z", pos=0.0,
         at=dict(tile=-84.0, field=-84.0),
         text="The patent's X1–X1 direction: along the pFET stack, crossing its gate. The direction "
              "comes from the patent's text and drawings."),
] + NS_PLANES[1:]
NS_PAIR_PLANES = [
    dict(NS_PLANES[0], scales=("pair",)),
    dict(NS_P_PLANES[0], pos=-84.0, scales=("pair",)),
    dict(NS_PLANES[1], scales=("pair",),
         text="The patent's Y1–Y1 direction: across both stacks, through the gate region, where the gate "
              "line joins them or is cut. The direction comes from the patent's text and drawings."),
    dict(NS_PLANES[2], scales=("pair",)),
]
FIN_PAIR_PLANES = [
    dict(FIN_PLANES[0], name="Across both fin pairs, at the gate", scales=("pair",)),
    dict(FIN_PLANES[2], name="Across both fin pairs, through the drains", scales=("pair",)),
    dict(FIN_PLANES[1], id="along_nfin", name="Along an nFET fin", short="Along nFET fin", scales=("pair",)),
    dict(FIN_PLANES[1], id="along_pfin", name="Along a pFET fin", short="Along pFET fin", pos=13.5 - 81.0,
         scales=("pair",)),
]
# The Si/Si lesson: both devices in one site scene, the nFET in front (z = 0), the pFET behind.
# The application's drawings are not in the repository, so these are the app's own planes.
NSSI_PLANES = [
    dict(id="xn", name="Along the nFET stack, through the gate", short="Along nFET", axis="z", pos=0.0,
         wide=True, text="Along the nFET's stack, crossing its gate. This is the app's own plane; the "
                         "application's drawings were not compared."),
    dict(id="xp", name="Along the pFET stack, through the gate", short="Along pFET", axis="z", pos=-84.0,
         wide=True, text="Along the pFET's stack, crossing its gate. The app's own plane."),
    dict(id="y1", name="Across both stacks, through the gate", short="Across · gate", axis="x", pos=0.0,
         wide=True, text="Across both stacks through the gate region, where one gate line joins them. "
                         "The app's own plane."),
    dict(id="y2", name="Across both stacks, through the source/drain", short="Across · S/D", axis="x",
         pos=None, wide=True, text="Across both stacks through the source/drain regions. The app's own "
                                   "plane. Before the source/drain is grown, the plane is where it will be."),
]
NSSI_PLANE_OF = dict(
    {k: ["xn", "y2"] for k in ("recess", "indent", "inner", "undoped", "sti_recess", "cavity", "bdi", "cesl", "n_sd")},
    p_sd=["xp", "y2"], release=["xn", "y1"], hk=["xn", "y1"], wfm=["y1", "xn"], gate=["y1", "xn"],
    contacts=["y2", "xn"], done=["xn", "y1"], wiring=["y2", "y1"])


PW_PLANES = [
    dict(id="pw_across", name="Across the lines, mid-length", short="Across lines", axis="x", pos=0.0,
         scales=("field",),
         text="Across the lines, the orientation of the SAQP patent's cross-sections (its Figs. 1–11)."),
]


NS_P_PLANE_OF = dict(NS_PLANE_OF, p_recess=["x1", "y2"], p_indent=["x1"], p_inner=["x1"], p_epi=["x1", "y2"],
                     p_release=["y1", "x1"], p_hkmg=["y1", "x1"], p_contacts=["x1", "y2"], p_done=["x1", "y2"],
                     spaceretch=["x1", "y1"])
FIN_PAIR_PLANE_OF = dict(p_epi=["across_sd", "along_pfin"], epi=["across_sd", "along_nfin"],
                         recess=["across_sd"], p_recess=["across_sd"], n_mask=["across_sd"], p_mask=["across_sd"],
                         n_clean=["across_sd"])


def attach_sections(key, flow, dev):
    tech = "fin" if key.startswith("fin") or key == "pitchwalk" else "ns"
    planes = dict(pitchwalk=PW_PLANES, ns_p=NS_P_PLANES, ns_pair=NS_PAIR_PLANES, fin_p=FIN_P_PLANES,
                  fin_pair=FIN_PAIR_PLANES).get(key, FIN_PLANES if tech == "fin" else NS_PLANES)
    if key == "ns~si":
        planes = [dict(p, pos=NS_PLANES[2]["pos"]) if p["pos"] is None else p for p in NSSI_PLANES]
    plane_of = dict(ns_p={k: [("x1" if x == "x2" else x) for x in v] for k, v in NS_P_PLANE_OF.items()},
                    fin_pair=FIN_PAIR_PLANE_OF, **{"ns~si": NSSI_PLANE_OF}).get(
        key, FIN_PLANE_OF if tech == "fin" else NS_PLANE_OF)
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
            if sc not in pl.get("scales", ("site", "tile", "field")): continue
            b = next((st["bounds"] for st in flow["steps"] if st["scale"] == sc and "bounds" in st), None) \
                if sc != "site" else dev.bounds
            if b is None: continue
            vk = f"sec_{pl['id']}" + ("" if sc == "site" else "_" + sc[0])
            flow["views"][vk] = plane_view(pl, sc, b)
            views[sc] = vk
        if views:
            secs.append(dict(id=pl["id"], name=pl["name"], short=pl["short"], axis=pl["axis"],
                             pos=round(pl["pos"], 4), text=pl["text"], views=views,
                             **({"at": {k: round(v, 4) for k, v in pl["at"].items() if k in views}}
                                if any(k in views for k in pl.get("at", {})) else {})))
    flow["sections"] = secs
    byid = {s["id"]: s for s in secs}
    for st in flow["steps"]:
        # Steps are tied to planes through their figures; the Si/Si lesson maps no figures, so
        # every step gets its planes directly.
        if not st["figs"] and key != "ns~si": continue
        src = "R28" if key == "ns~si" else (st.get("src") or ["R13" if tech == "ns" else "R29"])[0]
        if key == "ns~si":
            described = ("The application's Figs. " + ", ".join(st["figs"]) + ": " + st["body"]) if st["figs"] \
                else st["body"]
        elif tech == "ns":
            described = " ".join(NS_FIG_TEXT[f] for f in st["figs"] if f in NS_FIG_TEXT)
        else:
            described = " ".join(dict.fromkeys(FIN_FIG_TEXT[(src, f.rstrip("ABC"))] for f in st["figs"]))
        want = plane_of.get(st["id"]) or [planes[0]["id"] if tech == "fin" else "y1"]
        parts = [final[x] if isinstance(x, str) else x for x in st["parts"]]
        entries = []
        for pid in want:
            pl = byid.get(pid)
            if not pl or st["scale"] not in pl["views"]: continue
            vis = cut_by(parts, next(p for p in planes if p["id"] == pid), st["scale"])
            if not vis and key == "ns~si": continue        # nothing named in this plane yet
            entries.append(dict(plane=pid, figs=st["figs"], src=src, described=described,
                                visible=vis,
                                omitted=list(st["omitted"]) + (
                                    ["The source's figures show the pFET beside the nFET; this site "
                                     f"view shows the {'pFET' if key == 'ns_p' else 'nFET'} only"]
                                    if tech == "ns" and st["scale"] == "site" and key != "ns~si" else []),
                                status="text", status_text=TEXT_STATUS))
        if entries: st["compare"] = entries


from process_why import WHY


# ------------------------------------------------------ STEP ANIMATIONS ---
# Which parts the viewer grows on entering a step. A step that lists its films ("deposit")
# grows them one after another. Every other step that adds material grows its new parts
# from the bottom up, those starting at one level together and the levels in turn, so a
# stack rises layer by layer and a gate's films in the order they were laid. Parts that
# stand where solid material stood before are what an etch or a polish left behind, not
# something added, so they do not grow; nor does anything a step only patterns, exposes,
# implants or removes.
ADDS = re.compile(r"deposit|fill|growth|grow|epitax|coat|liner|film|oxid|dispens|multilayer|masked|"
                  r"protected|covered|seal|resist|\bcaps?\b", re.I)
TAKES = re.compile(r"etch|recess|remov|strip|pull|release|open|clean|trim|cmp|polish|planari|pattern|"
                   r"develop|expos|implant|\bcut\b|printed|thinner|thicker|wider|ideal", re.I)
NO_GROW = {"resist_exp", "chrome"}
STACK_ORDER = {"sio2": 0, "tisi": 0, "highk": 1, "nwf": 2, "tin": 2, "cofill": 3, "wfill": 3, "mo": 3,
               "cobalt": 3, "tungsten": 3, "copper": 3, "alox": 4, "si3n4": 4}


def step_growth(key, steps, final):
    if key == "pitchwalk": return                 # a comparison of line sets, not a process
    def boxes(q):
        p = final.get(q) if isinstance(q, str) else q
        return p, [lim(b) for b in p["boxes"]] if p else []
    def vol(b): return max(0.0, b[1] - b[0]) * max(0.0, b[3] - b[2]) * max(0.0, b[5] - b[4])
    def inter(a, b):
        return vol((max(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), min(a[3], b[3]),
                    max(a[4], b[4]), min(a[5], b[5])))
    prev = None
    for st in steps:
        here = {}
        for q in st["parts"]:
            p, bx = boxes(q)
            if p: here[p["id"]] = (p, bx)
        if st.get("deposit"):
            st["deposit_groups"] = [[i] for i in st["deposit"]]
        elif prev is not None and prev[0] == st["scale"] and (ADDS.search(st["title"]) or not TAKES.search(st["title"])):
            grow = []
            for pid, (p, bx) in here.items():
                if pid in prev[1] or p["material"] in NO_GROW: continue
                v = sum(vol(b) for b in bx)
                if v <= 0: continue
                # Left behind: where the same material stood before (a spacer out of its film,
                # a fin out of the wafer), not added in a space an etch opened.
                same = [c for q, cb in prev[1].values() if q["material"] == p["material"] for c in cb]
                if sum(inter(b, c) for b in bx for c in same) > 0.9 * v: continue
                grow.append((p["material"], round(min(b[2] for b in bx) * 2) / 2, pid))
            if grow:
                # A gate or contact stack goes on film by film, inside out; anything else
                # rises level by level.
                if any(m in ("highk", "tisi") for m, _, _ in grow):
                    key = lambda g: STACK_ORDER.get(g[0], 2.5)
                else:
                    key = lambda g: g[1]
                levels = sorted({key(g) for g in grow})
                st["deposit_groups"] = [[g[2] for g in sorted(grow, key=lambda g: g[2]) if key(g) == lv] for lv in levels]
                st["deposit"] = [pid for g in st["deposit_groups"] for pid in g]
        prev = (st["scale"], here)


def main():
    out = {}
    refs = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "data/references.json")))["sources"]}
    docs = []
    for key, fn in FLOWS.items():
        dev, steps, extra = fn(out)
        if any(st["figs"] for st in steps) or key == "ns~si":       # the Si/Si lesson: its own planes
            whole = dict(extra, steps=steps)
            attach_sections(key, whole, dev)
            extra["sections"] = whole["sections"]
        if key in ("ns", "ns_p", "ns_pair"):
            # The two channel designs' lessons, each named with its own source.
            extra["lesson_label"] = "Si/SiGe CMOS · Patent example: US 2023/0420457 A1 (US 12,568,683 B2)"
        if key == "ns~si":
            extra["lesson_label"] = "Si/Si CMOS · Patent-application example: US 2023/0178617 A1"
        step_growth(key, steps, dict({p["id"]: p for p in getattr(dev, "parts", [])},
                                     **{p["id"]: p for p in extra.get("final", []) or []}))
        out[key] = dict(extra, steps=steps, badge={k: BADGE[k] for k in extra["match"]},
                        badge_note={BADGE[k]: BADGE_NOTE[BADGE[k]] for k in extra["match"]},
                        why=WHY[key])
        # A lesson's source list is exactly what its texts cite, so it can neither miss one
        # nor list one it never uses.
        blob_ = json.dumps({x: v for x, v in out[key].items() if x not in ("final", "bounds")}, ensure_ascii=False)
        cited = {r for m in re.findall(r"\[(R\d+(?:, R\d+)*)\]", blob_) for r in m.split(", ")}
        out[key]["refs"] = sorted(cited, key=lambda r: int(r[1:]))
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
