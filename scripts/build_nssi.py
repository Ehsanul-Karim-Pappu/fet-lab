"""
The Si/Si CMOS nanosheet pair and its fabrication lesson, after the example route of IBM's
patent application US 2023/0178617 A1, "Nanosheet epitaxy with full bottom isolation",
Figs. 2–52 [R28]: one example process, not a production foundry flow, and a different route
from the Si/SiGe-channel patent the other nanosheet lesson follows [R13].

The route, as modelled here:
  a Ge-rich sacrificial bottom layer, a thin Si seed, then lower-Ge SiGe and Si in turn (three
  Si channel sheets per device, Si in both the nFET and the pFET); stack lines, STI; dummy gates,
  gate hard masks and outer spacers; the stacks recessed in the source/drain openings down to
  the seed, the SiGe indented and inner spacers formed; undoped Si grown in the openings from
  the seed; the Ge-rich layer removed through its exposed sides and the cavity filled with
  bottom dielectric isolation under both devices; the pFET source/drain (SiGe:B) with the nFET
  protected, then the nFET's (SiC:P) with the pFET protected; ILD, dummy gates removed, the SiGe
  removed to release the Si channels in both devices; gate dielectrics, n- and p-type
  work-function metals and one conductive gate; contacts; and, as the lesson's educational
  completion, inverter wiring.

The finished Device and Inverter scenes of the Si/Si design come from [si_device] below, so the
lesson's last frames are those scenes part for part.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_devices as bd
import build_process as bp
from build_devices import box, ring4
from build_process import tmp, subtract, conformal, lim

XG, XSP, XSD = bd.XG, bd.XSP, bd.XSD          # gate, spacer and site half-lengths: 7.5 / 14.5 / 36.5
HZ, DZ, ZSUB = 15.0, 84.0, 42.0               # sheet half-width; pFET line 84 nm behind; cell half-width
ZC = dict(n=0.0, p=-DZ)
TB, TS = 8.0, 2.0                             # Ge-rich bottom layer and Si seed thicknesses (illustrative)
WHO = dict(n="nFET", p="pFET")
WF = dict(n=("nwf", "n-type work-function metal"), p=("tin", "TiN work-function metal (p-type)"))
SD = dict(n=("sic", "SiC:P source/drain epi (n-type)"), p=("sige", "SiGe:B source/drain epi (p-type)"))
ZLO, ZHI = -DZ - ZSUB, ZSUB                   # the pair's z extent


def dims(stack):
    """Every height of the route, from [stack] (bd.NS_PROCESS_STACK or bd.NS_EXPLODED_STACK)."""
    t, g = stack["tch"], stack["tsg"]
    F = stack["til"] + stack["thk"] + stack["twf"]
    y0 = TB + TS                                               # top of the seed
    sg = [(y0 + i * (t + g), y0 + i * (t + g) + g) for i in range(3)]      # lower-Ge SiGe
    si = [(b, b + t) for a, b in sg]                                          # Si channels
    top = si[-1][1]
    ymo = top + F + 9.0; ycap = ymo + 6.0
    ysd = top + 3.0; ynisi = ysd + 5.0
    yplug = max(92.0, ycap + 6.0); ym2 = yplug + 10.0
    hzmo = HZ + F + 5.0
    return dict(t=t, g=g, F=F, y0=y0, sg=sg, si=si, top=top, ymo=ymo, ycap=ycap, ysd=ysd,
                ynisi=ynisi, yplug=yplug, ym2=ym2, hzmo=hzmo, films=(stack["til"], stack["thk"], stack["twf"]))


def foot(k, y0, y1, x0=-XSD, x1=XSD):
    zc = ZC[k]
    return box(x0, x1, y0, y1, zc - HZ, zc + HZ)


def final_parts(stack, wired):
    """The finished Si/Si pair: (id, name, material, boxes, group, explode, net) for each part."""
    D = dims(stack)
    out = []

    def add(pid, name, mat, boxes, group, explode=(0, 0, 0), net="body"):
        out.append(dict(id=pid, name=name, material=mat, group=group,
                        boxes=[[round(float(v), 4) for v in b] for b in boxes], explode=list(explode), net=net))

    add("substrate", "Si substrate", "silicon", [box(-XSD, XSD, -26, -8, ZLO, ZHI)], "Substrate & isolation", (0, -1.2, 0))
    add("sti", "STI oxide", "sio2", [box(-XSD, XSD, -8, 0, a, b) for a, b in
                                    ((ZLO, ZC["p"] - HZ), (ZC["p"] + HZ, ZC["n"] - HZ), (ZC["n"] + HZ, ZHI))],
        "Substrate & isolation", (0, -.8, 0))
    gz0, gz1 = ZC["p"] - D["hzmo"], ZC["n"] + D["hzmo"]         # the gate line, over both devices
    stackboxes = []
    for k in ("n", "p"):
        zc, sd = ZC[k], (1 if k == "n" else -1)
        g = f"{WHO[k]} · "
        add(f"{k}_subfin", f"{WHO[k]} · Si sub-fin", "silicon", [foot(k, -8, 0)], g + "Substrate & isolation", (0, -1.0, sd * .6))
        add(f"{k}_bdi", f"{WHO[k]} · Bottom dielectric isolation (where the Ge-rich layer was)", "si3n4",
            [foot(k, 0, TB)], g + "Substrate & isolation", (0, -.8, sd * .6))
        add(f"{k}_seed", f"{WHO[k]} · Si seed layer", "silicon", [foot(k, TB, D["y0"])], g + "Channel stack", (0, -.4, sd * .6))
        for i, (a, b) in enumerate(D["si"]):
            add(f"{k}_sheet{i+1}", f"{WHO[k]} · Si nanosheet {i+1}", "silicon", [foot(k, a, b, -XSP, XSP)],
                g + "Channel stack", (0, 0, sd * .6), "chan_" + k if wired else "body")
        for s, T in ((-1, "source"), (1, "drain")):
            xa, xb = sorted((s * XG, s * XSP))
            add(f"{k}_inner_{T}", f"{WHO[k]} · Si₃N₄ inner spacers · {T} side", "si3n4",
                [foot(k, a, b, xa, xb) for a, b in D["sg"]], g + "Spacers", (s * 1.2, 0, sd * .6))
        stackboxes += [foot(k, 0, D["top"])]
        # Gate films: round each sheet, and over the seed's top and sides (the BDI is below it).
        til, thk, twf = D["films"]
        o = 0.0
        for nm, mat, t, lab in (("il", "sio2", til, "SiO₂ interfacial layer"), ("hk", "highk", thk, "HfO₂ high-κ"),
                                ("wf", WF[k][0], twf, WF[k][1])):
            for i, (a, b) in enumerate(D["si"]):
                yc, hy = (a + b) / 2, (b - a) / 2
                bx = ring4(yc, hy + o, HZ + o, t, XG)
                for q in bx: q[2] += zc
                add(f"{k}_{nm}{i+1}", f"{WHO[k]} · {lab} · sheet {i+1}", mat, bx, g + "Gate-all-around films",
                    ["radial", yc, 1.0 + 1.1 * ("il", "hk", "wf").index(nm), zc], "in" if nm == "wf" and wired else "body")
            y0 = D["y0"]
            bx = [box(-XG, XG, y0 + o, y0 + o + t, zc - HZ - o - t, zc + HZ + o + t),
                  box(-XG, XG, TB, y0 + o, zc + HZ + o, zc + HZ + o + t),
                  box(-XG, XG, TB, y0 + o, zc - HZ - o - t, zc - HZ - o)]
            add(f"{k}_{nm}s", f"{WHO[k]} · {lab} · over the seed layer", mat, bx, g + "Gate-all-around films",
                (0, -.3, sd * .6), "in" if nm == "wf" and wired else "body")
            o += t
        for s, T in ((-1, "source"), (1, "drain")):
            xa, xb = sorted((s * XSP, s * XSD)); xc = (xa + xb) / 2
            net = ("gnd" if k == "n" else "vdd") if T == "source" else "out"
            if not wired: net = "body"
            add(f"{k}_undoped_{T}", f"{WHO[k]} · Undoped Si growth region · {T}", "siu",
                [foot(k, D["y0"], D["si"][0][0], xa, xb)], g + "Source / drain", (s * 1.5, -.2, sd * .6), net)
            add(f"{k}_epi_{T}", f"{WHO[k]} · {T.capitalize()} · {SD[k][1]}", SD[k][0],
                [foot(k, D["si"][0][0], D["ysd"], xa, xb)], g + "Source / drain", (s * 1.6, 0, sd * .6), net)
            add(f"{k}_nisi_{T}", f"{WHO[k]} · {T.capitalize()} TiSiₓ silicide", "tisi",
                [foot(k, D["ysd"], D["ynisi"], xa, xb)], g + "Source / drain", (s * 1.9, .3, sd * .6), net)
            add(f"{k}_ni_{T}", f"{WHO[k]} · {T.capitalize()} Co contact plug", "cobalt",
                [box(xc - 8, xc + 8, D["ynisi"], D["yplug"], zc - 8, zc + 8)], g + "Source / drain", (s * 2.1, .8, sd * .6), net)
            add(f"{k}_w_{T}", f"{WHO[k]} · {T.capitalize()} W metal", "tungsten",
                [foot(k, D["yplug"], D["ym2"], xa, xb)], g + "Source / drain", (s * 2.3, 1.3, sd * .6), net)
    # One gate over both: spacers either side, Mo fill, TiN cap, one contact (over the nFET).
    films = [b for p in out if p["group"].endswith("Gate-all-around films") for b in p["boxes"]]
    for s, T in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s * XG, s * XSP))
        add(f"spacer_{T}", f"Si₃N₄ outer gate spacer · {T} side", "si3n4",
            subtract((xa, xb, 0, D["ycap"], gz0, gz1), stackboxes), "Spacers", (s * 1.3, 0, 0))
    # What the gate fill wraps: the BDI, the seed, the released sheets and their films.
    solid = [b for p in out if p["id"][2:].startswith(("bdi", "seed", "sheet")) for b in p["boxes"]] + films
    add("gate_mo", "Mo gate fill · one gate over both devices", "mo",
        subtract((-XG, XG, 0, D["ymo"], gz0, gz1), solid),
        "Gate electrode", (0, 1.0, 0), "in" if wired else "body")
    add("gatecap", "TiN gate cap", "tin", [box(-XG, XG, D["ymo"], D["ycap"], gz0, gz1)], "Gate electrode",
        (0, 1.4, 0), "in" if wired else "body")
    add("gatew", "W gate contact · one for the shared gate", "tungsten",
        [box(-XG, XG, D["ycap"], D["ym2"], -20, 20)], "Gate electrode", (0, 1.8, 0), "in" if wired else "body")
    if wired:
        # Educational completion: one metal level wiring the pair as an inverter.
        y0, y1 = D["ym2"], D["ym2"] + 8.0
        xs0, xs1, xd0, xd1 = -XSD, -XSP, XSP, XSD
        add("m1_vss", "V_SS (GND) rail and strap · nFET source", "tungsten",
            [box(xs0, xs1, y0, y1, -HZ, ZHI - 8), box(-XSD, XSD, y0, y1, ZHI - 8, ZHI)], "Metal 1", (0, 1.6, .6), "gnd")
        add("m1_vdd", "V_DD rail and strap · pFET source", "tungsten",
            [box(xs0, xs1, y0, y1, ZLO + 8, ZC["p"] + HZ), box(-XSD, XSD, y0, y1, ZLO, ZLO + 8)], "Metal 1", (0, 1.6, -.6), "vdd")
        add("m1_out", "OUT · joins both drains", "tungsten", [box(xd0, xd1, y0, y1, ZC["p"] - HZ, HZ)],
            "Metal 1", (0, 1.6, 0), "out")
        add("m1_in", "IN · on the shared gate's contact", "tungsten", [box(-XG, XG, y0, y1, -20, 20)],
            "Metal 1", (0, 1.7, 0), "in")
    return out, D


def si_device(stack, wired, key, name, tag):
    """The finished Si/Si pair (with inverter wiring if [wired]) as a Dev."""
    parts, D = final_parts(stack, wired)
    d = bd.Dev(key, name, tag, "")
    for p in parts:
        d.add(p["id"], p["name"], p["material"], p["boxes"], p["group"], p["explode"])
        d.parts[-1]["net"] = p["net"]
    if wired: d.logic = True
    d.finish()
    return d, D


# ================================================================== the lesson ===
SCOPE = ("Si/Si CMOS nanosheet fabrication after one example route, IBM's patent application "
         "US 2023/0178617 A1, “Nanosheet epitaxy with full bottom isolation” [R28]: Si channels in "
         "both the nFET and the pFET, an undoped Si growth region in the source/drain openings, and "
         "bottom dielectric isolation under both devices, formed by replacing a Ge-rich sacrificial "
         "layer. One disclosed example, not a production foundry flow, and a different route from "
         "the Si/SiGe lesson's patent [R13]: its isolation and channel release are not used here. "
         "Illustrative dimensions.")
FIGURES = ("The application's sequence spans its Figs. 2–52; each state below is placed in that "
           "range from its written description, not mapped to an individual figure. Its drawings "
           "were not available for visual comparison: every view is a teaching reconstruction.")
BRANCH = ("Both devices are followed together, side by side on one gate line, because their "
          "source/drain steps differ: each is grown with the other region protected. The contacts "
          "and the inverter wiring at the end are the lesson's educational completion of the "
          "depicted devices; the application gives no complete routing recipe.")
SUBS = ["Dimensions are illustrative: 7 nm Si sheets and 7 nm SiGe layers, an 8 nm Ge-rich layer "
        "and a 2 nm seed are the model's choices, not the application's",
        "Only one site of each line is drawn; the lines run on past its source/drain edges"]
MATCH = {"source": "Source stage, adapted; artwork not compared",
         "teach": "Teaching reconstruction; no source figure",
         "concept": "Concept-only operation"}


def flow(done=None):
    stack = bd.NS_PROCESS_STACK
    dev, D = si_device(stack, True, "ns~si", "Nanosheet · Si/Si CMOS", "")
    F = bp.Flow(dev)
    FIN = F.final
    Y0, SG, SI, TOP = D["y0"], D["sg"], D["si"], D["top"]
    ymo, ycap = D["ymo"], D["ycap"]
    gz0, gz1 = ZC["p"] - D["hzmo"], ZC["n"] + D["hzmo"]
    FIGS = ["2–52"]
    views = dict(dev_views(dev), sd=dict(n="Through the drains", s="both devices, across the source/drain",
                                          az=1.5708, el=0.0, r=390, tgt=[25.5, 45, -42], clip=[25.5, None, None]))

    def snap(sid, title, body, view="iso", match="source", regions=None, **kw):
        figs = FIGS if match == "source" else ()
        src = ["R28"] if match == "source" else ()
        F.snap(sid, title, body, view, match=match, figs=figs, src=src, **kw)
        if regions: F.steps[-1]["regions"] = dict(n=regions[0], p=regions[1])

    def layers(k, sg=(-XSD, XSD), si=(-XSD, XSD), bot=True):
        """Device [k]'s sacrificial layers still in place: the Ge-rich bottom layer if [bot], the
        lower-Ge SiGe over [sg] and the not-yet-final Si layers over [si] (None: gone or final)."""
        F.drop_prefix(f"{k}_t")
        if bot: F.put(tmp(f"{k}_tbot", f"{WHO[k]} · SiGe, Ge-rich · sacrificial bottom layer", "sige",
                          f"{WHO[k]} · Channel stack", [foot(k, 0, TB)], (0, -.6, 0)))
        for i, (a, b) in enumerate(SG):
            if sg: F.put(tmp(f"{k}_tsg{i+1}", f"{WHO[k]} · SiGe, lower Ge · sacrificial layer {i+1}", "sige",
                             f"{WHO[k]} · Channel stack", [foot(k, a, b, *sg)]))
        for i, (a, b) in enumerate(SI):
            if si: F.put(tmp(f"{k}_tsi{i+1}", f"{WHO[k]} · Si · future channel sheet {i+1}", "silicon",
                             f"{WHO[k]} · Channel stack", [foot(k, a, b, *si)]))

    def ild(top):
        F.drop("t_ild")
        F.put(tmp("t_ild", "Interlayer dielectric (ILD)", "ild", "Interlayer dielectric",
                  subtract((-XSD, XSD, 0, top, ZLO, ZHI), F.boxes(but=("t_ild",))), (0, .6, 0)))

    def liner(k):
        z0, z1 = (ZC[k] - ZSUB, ZC[k] + ZSUB)
        F.drop("t_liner")
        F.put(tmp("t_liner", f"Protective hard-mask liner over the {WHO[k]} region", "liner", "Region masks",
                  conformal(F.boxes(), 1.5, (-XSD, XSD, 0, ycap + 1.5, z0, z1)), (0, .8, 0)))

    # 1
    F.put(tmp("t_wafer", "Si substrate", "silicon", "Substrate & isolation", [box(-XSD, XSD, -26, 0, ZLO, ZHI)], (0, -1.2, 0)))
    snap("substrate", "Silicon substrate",
         "The route starts from a bulk silicon wafer [R28]. The two future device regions lie side by "
         "side: the nFET in front, the pFET behind.", subs=SUBS)
    # 2
    F.put(tmp("t_bot", "SiGe, Ge-rich · sacrificial bottom layer", "sige", "Channel stack",
              [box(-XSD, XSD, 0, TB, ZLO, ZHI)], (0, -.6, 0)))
    F.put(tmp("t_seed", "Si seed layer", "silicon", "Channel stack", [box(-XSD, XSD, TB, Y0, ZLO, ZHI)], (0, -.4, 0)))
    for i, (a, b) in enumerate(SG):
        F.put(tmp(f"t_sg{i+1}", f"SiGe, lower Ge · sacrificial layer {i+1}", "sige", "Channel stack",
                  [box(-XSD, XSD, a, b, ZLO, ZHI)]))
    for i, (a, b) in enumerate(SI):
        F.put(tmp(f"t_si{i+1}", f"Si · future channel sheet {i+1}", "silicon", "Channel stack",
                  [box(-XSD, XSD, a, b, ZLO, ZHI)]))
    snap("stack", "Multilayer epitaxy",
         "One stack is grown over both regions: a Ge-rich sacrificial SiGe bottom layer, a thin Si seed "
         "layer, then lower-Ge SiGe and Si in turn, three Si layers in all. In this route the Si layers "
         "are the channels of both devices; the lower-Ge SiGe is removed later from the gate region, and "
         "the Ge-rich layer, which etches selectively against it, is replaced by isolation [R28].",
         view="chann", subs=SUBS, deposit=["t_bot", "t_seed"] + [f"t_sg{i+1}" for i in range(3)] +
         [f"t_si{i+1}" for i in range(3)], regions=("shared stack", "shared stack"))
    # 3
    for pid in ["t_wafer", "t_bot", "t_seed"] + [f"t_sg{i+1}" for i in range(3)] + [f"t_si{i+1}" for i in range(3)]:
        F.drop(pid)
    F.add("substrate", "n_subfin", "p_subfin", "n_seed", "p_seed")
    for k in ("n", "p"): layers(k)
    for k in ("n", "p"):
        F.put(tmp(f"{k}_thm", f"{WHO[k]} · Stack hard mask", "si3n4", "Patterning", [foot(k, TOP, TOP + 6)], (0, 1.3, 0)))
    snap("lines", "Stack lines etched",
         "A hard mask defines one line per region, and a directional etch cuts through the multilayer "
         "into the substrate, leaving two stack lines on Si sub-fins [R28]. How the lines are printed "
         "(a direct exposure, SADP or SAQP) is a separate choice; the Lessons chips show those routes on "
         "the Si/SiGe lesson's tile.", view="gate", subs=SUBS + ["The hard mask's material and thickness are illustrative"],
         regions=("stack line", "stack line"))
    # 4
    F.drop("n_thm", "p_thm")
    F.add("sti")
    snap("sti", "Shallow trench isolation",
         "Oxide fills the trenches, is polished, and is recessed until it stops level with the bottom of "
         "the Ge-rich layer, so that layer's sides stay exposed for later; the hard mask is removed [R28].",
         view="gate", subs=SUBS, regions=("isolated line", "isolated line"))
    # 5
    stk = [foot(k, 0, TOP) for k in ("n", "p")]
    F.put(tmp("t_dummy", "Sacrificial gate (dummy poly-Si)", "poly", "Dummy gate",
              subtract((-XG, XG, 0, ymo, gz0, gz1), stk), (0, 1.0, 0)))
    F.put(tmp("t_ghm", "Gate hard mask (SiN)", "si3n4", "Dummy gate", [box(-XG, XG, ymo, ycap, gz0, gz1)], (0, 1.4, 0)))
    snap("dummy", "Sacrificial gate and hard mask",
         "A sacrificial gate and its hard mask are patterned across both lines. They hold the channel "
         "regions' place, and protect them, until the replacement gate [R28].",
         subs=SUBS + ["A thin dummy-gate oxide is not drawn"], regions=("dummy gate", "dummy gate"))
    # 6
    F.add("spacer_source", "spacer_drain")
    snap("spacers", "Outer gate spacers",
         "Dielectric spacers are formed on both sides of the sacrificial gate, by deposition and a "
         "directional etch back [R28].", view="chann", subs=SUBS, regions=("spacers", "spacers"))
    # 7
    for k in ("n", "p"):
        layers(k, sg=(-XSP, XSP), si=None)
        for i in range(3): F.add(f"{k}_sheet{i+1}")
    snap("recess", "Source/drain recess",
         "Outside the gate and spacers the stacks are etched down to the Si seed layer, which stays, "
         "with the Ge-rich layer under it. The sacrificial gate protects the channel regions [R28].",
         view="chann", subs=SUBS, regions=("recessed to the seed", "recessed to the seed"))
    # 8
    for k in ("n", "p"):
        layers(k, sg=(-XG, XG), si=None)
    snap("indent", "SiGe indented",
         "A selective etch pulls the lower-Ge SiGe layers back from the exposed sheet ends, under the "
         "spacers; the Si sheets and the seed stay [R28].", view="chann", subs=SUBS,
         regions=("SiGe indented", "SiGe indented"))
    # 9
    F.add("n_inner_source", "n_inner_drain", "p_inner_source", "p_inner_drain")
    snap("inner", "Inner spacers",
         "Dielectric is deposited into the indents and etched back, leaving inner spacers that will "
         "separate the gate from the source and drain [R28].", view="chann", subs=SUBS,
         regions=("inner spacers", "inner spacers"))
    # 10
    F.add(*[f"{k}_undoped_{T}" for k in ("n", "p") for T in ("source", "drain")])
    snap("undoped", "Undoped Si growth",
         "Undoped Si grows in the source/drain openings from the exposed Si seed and the channel ends, "
         "a feature of this route: the later source/drain grows on it [R28].", view="chann",
         subs=SUBS + ["The model draws the undoped region filling the bottom of each opening, up to the "
                      "lowest sheet; how far it grows up the sheet ends is not drawn"],
         regions=("undoped Si grown", "undoped Si grown"))
    # 11
    for k in ("n", "p"): layers(k, sg=(-XG, XG), si=None, bot=False)
    snap("cavity", "Ge-rich layer removed",
         "Beside the source/drain openings the Ge-rich layer's sides are bare above the STI. A selective "
         "etch removes the whole layer through them, leaving a cavity beneath the stacks and the undoped "
         "Si; the structure is held by the sacrificial gate, the spacers and the growth regions [R28].",
         view="sd", subs=SUBS, regions=("cavity below", "cavity below"))
    # 12
    F.add("n_bdi", "p_bdi")
    snap("bdi", "Bottom dielectric isolation",
         "Dielectric fills the cavity and is etched back: bottom dielectric isolation under both devices, "
         "beneath the channel stack and the undoped Si alike [R28].", view="sd", subs=SUBS,
         regions=("bottom isolation", "bottom isolation"))
    # 13
    liner("n")
    snap("n_protect", "nFET region protected", "A hard-mask liner covers the nFET region, so only the "
         "pFET's openings are exposed for its epitaxy [R28].", view="sd", match="teach", of="p_sd",
         subs=SUBS + ["The liner's material and thickness are illustrative"], regions=("protected", "open"))
    F.add("p_epi_source", "p_epi_drain")
    liner("n")
    snap("p_sd", "pFET source/drain",
         "With the nFET protected, boron-doped SiGe grows from the Si sheet ends and the undoped Si "
         "region in the pFET's openings. The pFET's channels stay Si; only its source/drain is SiGe [R28].",
         view="sd", subs=SUBS, regions=("protected", "SiGe:B source/drain"))
    # 14
    F.drop("t_liner"); liner("p")
    snap("p_protect", "pFET region protected", "The liner is removed from the nFET and a new one covers "
         "the pFET region [R28].", view="sd", match="teach", of="n_sd",
         subs=SUBS + ["The liner's material and thickness are illustrative"], regions=("open", "protected"))
    F.add("n_epi_source", "n_epi_drain")
    liner("p")
    snap("n_sd", "nFET source/drain",
         "With the pFET protected, n-doped epitaxy grows from the nFET's sheet ends and its undoped Si "
         "region: phosphorus-doped SiC here, one example the application gives [R28].", view="sd",
         subs=SUBS, regions=("SiC:P source/drain", "protected"))
    # 15
    F.drop("t_liner")
    ild(ycap)
    snap("ild", "Interlayer dielectric", "The liner is removed, interlayer dielectric fills the "
         "structure and is polished down to the gate hard mask [R28].", view="chann", subs=SUBS,
         regions=("buried in ILD", "buried in ILD"))
    # 16
    F.drop("t_dummy", "t_ghm")                     # the ILD stays as it was: the trench is open
    snap("pull", "Sacrificial gate removed",
         "The hard mask and the sacrificial gate are removed, opening the gate trench over both devices "
         "[R28].", view="gate", subs=SUBS, regions=("gate trench open", "gate trench open"))
    # 17
    for k in ("n", "p"): F.drop_prefix(f"{k}_t")
    snap("release", "Channel release",
         "Inside the gate opening a selective etch removes the lower-Ge SiGe layers in both devices, "
         "releasing the Si channels; the Si sheets, the seed and the inner spacers stay. This route "
         "releases both devices the same way [R28].", view="gate", subs=SUBS,
         regions=("Si channels released", "Si channels released"))
    # 18
    F.add(*[f"{k}_{nm}{i}" for k in ("n", "p") for nm in ("il", "hk") for i in ("1", "2", "3", "s")])
    snap("hk", "Gate dielectric",
         "An interfacial oxide forms on the released Si, and a high-κ dielectric is deposited all round "
         "each sheet and over the seed [R28].", view="gate", subs=SUBS + [
             "SiO₂ and HfO₂ stand for the interfacial and high-κ layers; thicknesses are illustrative"],
         regions=("high-κ", "high-κ"))
    # 19
    F.add(*[f"{k}_wf{i}" for k in ("n", "p") for i in ("1", "2", "3", "s")])
    snap("wfm", "Work-function metals",
         "Each device gets its own work-function metal, each deposited with the other region masked: an "
         "n-type metal on the nFET, TiN on the pFET [R28].", view="gate",
         subs=SUBS + ["The n-type metal stands for an Al-containing stack such as TiAl or TiAlC; its masks "
                      "are not drawn"], regions=("n-type work function", "p-type work function"))
    # 20
    F.add("gate_mo", "gatecap")
    snap("gate", "Gate fill",
         "A conductive gate material fills the trench over both devices, is planarized and capped: one "
         "gate line, so the two gates are one electrode, the inverter's input [R28].", view="gate",
         subs=SUBS + ["Mo fill and a TiN cap are illustrative"], regions=("gate", "gate"))
    # 21
    F.add(*[f"{k}_{c}_{T}" for k in ("n", "p") for c in ("nisi", "ni", "w") for T in ("source", "drain")], "gatew")
    ild(D["ym2"])
    snap("contacts", "Middle-of-line contacts",
         "Contact openings are etched through the ILD; a silicide forms on each source/drain and metal "
         "fills the openings, with one contact on the shared gate. The contacts complete the depicted "
         "devices for teaching; the application does not give this contact scheme.", view="sd",
         match="teach", subs=SUBS + ["The TiSiₓ, Co and W contact stack is illustrative"],
         regions=("contacted", "contacted"))
    # 22
    F.drop("t_ild")
    snap("done", "The finished Si/Si pair",
         "Si channels in both devices, bottom isolation under both, the undoped Si under each "
         "source/drain, and one gate with separate n- and p-type work-function metals. This is the Si/Si "
         "CMOS Device scene; the ILD is hidden for viewing only.", match="teach",
         subs=SUBS + ["The ILD is hidden for viewing only"], regions=("finished", "finished"))
    # 23
    F.add("m1_vss", "m1_vdd", "m1_out", "m1_in")
    snap("wiring", "Wired as an inverter",
         "The lesson's educational completion: IN on the shared gate, the pFET source to V_DD, the nFET "
         "source to V_SS, and both drains to OUT. This is the Si/Si CMOS Inverter scene; the application "
         "does not give a routing recipe.", view="iso", match="teach",
         subs=SUBS + ["One illustrative metal level; real cells route through several"],
         regions=("V_SS · OUT", "V_DD · OUT"))
    steps = F.done()
    return dev, steps, dict(
        scope=SCOPE, figures=FIGURES, branch=BRANCH, skipped={}, refs=["R28", "R13"], match=MATCH,
        views=views, own=True, name=dev.name, bounds=dev.bounds, final=dev.parts,
        audit_tile="Both devices are followed together on one gate line; steps n.k are operations "
                   "leading into core step n. No tile or line field is drawn.",
        audit_unverified=[
            "**Every figure placement.** The application's drawings (Figs. 2–52) have not been compared "
            "with these views; each state is placed from its written description, as summarised in the "
            "scope.",
            "**Dimensions.** All thicknesses are the model's illustrative choices.",
            "**Contacts and wiring.** The educational completion of the depicted devices, not the "
            "application's."])


def dev_views(d):
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    R = 2.3 * max(B["x"][1] - B["x"][0], B["y"][1] - B["y"][0], B["z"][1] - B["z"][0])
    yc = ctr[1]
    return {
        "iso": dict(n="3D overview", s="nFET in front, pFET behind", az=-0.76, el=0.36, r=R * .95, tgt=ctr, clip=None),
        "gate": dict(n="Through the gate", s="both devices in section", az=1.5708, el=0.0, r=R * .9, tgt=ctr, clip=[0, None, None]),
        "chann": dict(n="Along the nFET channel", s="source · gate · drain", az=0.0, el=0.02, r=R * .62,
                      tgt=[0, yc, 0], clip=[None, None, 0]),
        "chanp": dict(n="Along the pFET channel", s="source · gate · drain", az=0.0, el=0.02, r=R * .62,
                      tgt=[0, yc, -DZ], clip=[None, None, -DZ]),
    }
