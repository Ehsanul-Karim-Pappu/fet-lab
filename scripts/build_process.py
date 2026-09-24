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

    def snap(self, sid, title, body, view="iso", *, match, figs=(), subs=(), omitted=()):
        """[match] says how the state relates to its source (a MATCH key); [figs] are the
        source's figure identifiers; [subs] the model's material or dimension substitutions;
        [omitted] what the source shows at this stage that this view leaves out."""
        if match not in MATCH:
            sys.exit(f"{self.dev.key} step '{sid}': unknown match level {match!r}")
        parts = list(self.now.values())
        worst = overlap(parts, self.dev.bounds)
        if worst != 1:
            sys.exit(f"{self.dev.key} step '{sid}': {worst} solids overlap somewhere")
        self.steps.append(dict(id=sid, title=title, body=body, view=view, match=match,
            figs=list(figs), subs=list(subs), omitted=list(omitted),
            parts=[p["id"] if self.final.get(p["id"]) is p else p for p in parts]))

    def done(self):
        last = self.steps[-1]["parts"]
        if sorted(x for x in last if isinstance(x, str)) != sorted(self.final) or \
           any(not isinstance(x, str) for x in last):
            sys.exit(f"{self.dev.key}: the last step is not the finished device")
        return self.steps


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

# Figures of R13 this nFET lesson deliberately does not map to a step, and why.
NS_SKIPPED = {
    "10A/B": "pFET source/drain recess (pFET branch)",
    "11A/B": "pFET source/drain epitaxy (pFET branch)",
    "15A/B": "pFET channel preparation (pFET branch)",
    "19A/B": "an alternative shared-gate arrangement to Fig. 18, not a later step",
}

HKMG_SUB = "SiO₂, HfO₂, TiN and Mo stand for the interfacial, high-κ, work-function and fill layers"


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
        """A conformal film of thickness [t] on every exposed surface inside [window]:
        each solid grown by t, less the solids and the film already laid. A gap narrower
        than 2t closes up, as the cavity under the stack does."""
        solids = F.boxes(); out = []
        for b in solids:
            x0, x1, y0, y1, z0, z1 = lim(b)
            e = (max(x0 - t, window[0]), min(x1 + t, window[1]), max(y0 - t, window[2]),
                 min(y1 + t, window[3]), max(z0 - t, window[4]), min(z1 + t, window[5]))
            if e[0] < e[1] and e[2] < e[3] and e[4] < e[5]:
                out += subtract(e, solids + out)
        return out

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
    bottom(-XSD, XSD)
    layers(-XSD, XSD)
    F.drop("wafer", "pts0"); F.add("substrate", "pts", "sti")
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
    dox = subtract((-XG, XG, 0, top + TOX, -hz - TOX, hz + TOX), F.boxes())
    F.put(tmp("dox", "Dummy-gate oxide (sacrificial)", "sio2", "Dummy gate", dox, (0, .6, 0)))
    poly = subtract((-XG, XG, 0, ymo, -hzmo, hzmo), F.boxes())
    F.put(tmp("dummy", "Dummy gate · Si", "poly", "Dummy gate", poly, (0, 1.0, 0)))
    F.put(tmp("hardmask", "SiN hard mask", "si3n4", "Dummy gate",
              [box(-XG, XG, ymo, ycap, -hzmo, hzmo)], (0, 1.4, 0)))
    F.snap("dummy", "Dummy gate stack",
        "A thin sacrificial oxide, a silicon placeholder gate and a hard mask are deposited and "
        "patterned across the stack. The dummy gate fixes where the gate goes and its length; "
        "the real high-κ/metal gate replaces it near the end (replacement metal gate).",
        match="published", figs=["6A/B"],
        subs=["The patent suggests amorphous Si under a nitride/oxide hard mask; this model's "
              "dummy Si and nitride hard mask are illustrative"])
    # 6
    F.drop("bsige")
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
                               skipped=NS_SKIPPED, refs=["R13", "R1", "R14", "R15"], match=MATCH,
                               views=dict(cut=CUTAWAY, cutb=INDENT))


FLOWS = {"ns": flow_ns}


def audit(key, dev, flow, refs):
    """docs/PROCESS_AUDIT.md: every state against its source, generated from the data."""
    final = {p["id"]: p for p in dev.parts}
    part = lambda x: final[x] if isinstance(x, str) else x
    md = [f"# Process audit: {dev.name}", "",
          "Generated by `scripts/build_process.py` from `data/process.json`; do not edit by hand.", "",
          flow["scope"], "", flow["branch"], "", "**" + flow["figures"] + "**", "",
          "## Match levels", ""]
    md += [f"- **{v}** (`{k}`)" for k, v in flow["match"].items()]
    md += ["", "## States", "",
           "| # | State | Source figures | Match | What changes | Model choices | Not shown |",
           "|---|---|---|---|---|---|---|"]
    prev = {}
    for i, st in enumerate(flow["steps"], 1):
        now = {part(x)["id"]: part(x) for x in st["parts"]}
        added = [now[k]["name"] for k in now if k not in prev]
        gone = [prev[k]["name"] for k in prev if k not in now]
        shaped = [now[k]["name"] for k in now if k in prev and now[k]["boxes"] != prev[k]["boxes"]]
        chg = "; ".join(x for x in ("+ " + ", ".join(added) if added else "",
                                    "− " + ", ".join(gone) if gone else "",
                                    "reshaped: " + ", ".join(shaped) if shaped else "") if x)
        cell = lambda xs: "<br>".join(xs) if xs else "—"
        figs = ", ".join("Fig. " + f for f in st["figs"]) or "—"
        md.append(f"| {i} | {st['title']} | {figs} | {flow['match'][st['match']]} | {chg or '—'} "
                  f"| {cell(st['subs'])} | {cell(st['omitted'])} |")
        prev = now
    md += ["", "## Source figures not mapped to a state", ""]
    md += [f"- **Fig. {k}**: {v}" for k, v in flow["skipped"].items()]
    md += ["", "## Not yet verified", "",
           "- **Every figure mapping.** The patent's drawings have not been compared with these views; "
           "orientation, composition and labels may differ from the published artwork.",
           "- Views, cut directions and left/right are the app's own; the patent's section lines "
           "(X1–X1, X2–X2, Y1–Y1, Y2–Y2) are not yet mapped onto the app's axes.",
           "", "## Sources cited", ""]
    md += [f"- **[{r}]** {refs[r]['title']} — {refs[r]['publisher']}. <{refs[r]['url']}>"
           for r in flow["refs"]]
    return "\n".join(md) + "\n"


def main():
    out = {}
    refs = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "data/references.json")))["sources"]}
    docs = []
    for key, fn in FLOWS.items():
        dev, steps, extra = fn()
        out[key] = dict(extra, steps=steps)
        docs.append(audit(key, dev, out[key], refs))
    with open(os.path.join(ROOT, "docs/PROCESS_AUDIT.md"), "w") as f:
        f.write("\n".join(docs))
        temp = {p["id"] for s in steps for p in s["parts"] if not isinstance(p, str)}
        print(f"{key:10s} steps={len(steps):2d}  temporary parts={len(temp)}  max solids/voxel=1")
    blob = json.dumps(dict(flows=out), ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(ROOT, "data/process.json"), "w") as f:
        f.write(blob)
    print(f"process.json {len(blob)//1024} KB")


if __name__ == "__main__":
    main()
