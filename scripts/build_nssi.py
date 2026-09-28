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
from build_devices import box, ring4, carve
from build_process import tmp, subtract, conformal, lim, span

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
    yplug = ycap; ym2 = ycap          # contacts stop level with the gate cap, as in the Si/SiGe design
    hzmo = HZ + F + 5.0
    return dict(t=t, g=g, F=F, y0=y0, sg=sg, si=si, top=top, ymo=ymo, ycap=ycap, ysd=ysd,
                ynisi=ynisi, yplug=yplug, ym2=ym2, hzmo=hzmo, films=(stack["til"], 2.0, 1.0))


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
    # The STI is recessed below the Ge-rich layer only where it is exposed; under the gate and
    # its spacers it keeps the height it had, at the seed's top [R28].
    segs = ((ZLO, ZC["p"] - HZ), (ZC["p"] + HZ, ZC["n"] - HZ), (ZC["n"] + HZ, ZHI))
    sti_hi = [box(-XSP, XSP, 0, D["y0"], a, b) for a, b in segs]
    add("sti", "STI (dielectric; SiO₂ drawn)", "sio2", [box(-XSD, XSD, -8, 0, a, b) for a, b in segs] + sti_hi,
        "Substrate & isolation", (0, -.8, 0))
    gz0, gz1 = ZC["p"] - D["hzmo"], ZC["n"] + D["hzmo"]         # the gate line, over both devices
    stackboxes = []
    for k in ("n", "p"):
        zc, sd = ZC[k], (1 if k == "n" else -1)
        g = f"{WHO[k]} · "
        add(f"{k}_subfin", f"{WHO[k]} · Si sub-fin", "silicon", [foot(k, -8, 0)], g + "Substrate & isolation", (0, -1.0, sd * .6))
        add(f"{k}_bdi", f"{WHO[k]} · Bottom dielectric isolation (where the Ge-rich layer was)", "si3n4",
            [foot(k, 0, TB)], g + "Substrate & isolation", (0, -.8, sd * .6))
        # The seed stays only under the inner spacers and the undoped Si: under the gate it is
        # oxidized and etched away at channel release, and the gate sits on the BDI [R28].
        add(f"{k}_seed", f"{WHO[k]} · Si seed layer (under the inner spacers and the undoped Si)", "silicon",
            [foot(k, TB, D["y0"], -XSD, -XG), foot(k, TB, D["y0"], XG, XSD)], g + "Channel stack", (0, -.4, sd * .6))
        for i, (a, b) in enumerate(D["si"]):
            add(f"{k}_sheet{i+1}", f"{WHO[k]} · Si nanosheet {i+1}", "silicon", [foot(k, a, b, -XSP, XSP)],
                g + "Channel stack", (0, 0, sd * .6), "chan_" + k if wired else "body")
        for s, T in ((-1, "source"), (1, "drain")):
            xa, xb = sorted((s * XG, s * XSP))
            add(f"{k}_inner_{T}", f"{WHO[k]} · Si₃N₄ inner spacers · {T} side", "si3n4",
                [foot(k, a, b, xa, xb) for a, b in D["sg"]], g + "Spacers", (s * 1.2, 0, sd * .6))
        stackboxes += [foot(k, 0, D["top"])]
        # Spacer 130 also lines the stack's sides between the gates; it bounds the source/drain
        # and stays in the finished device (Figs. 10, 13, 52) [R28]. Its foot is at the seed's
        # top, where the STI stood when it was formed.
        FS = XSP - XG
        add(f"{k}_finsp", f"{WHO[k]} · SiBCN spacer 130 · on the stack's sides", "sibcn",
            [box(xa, xb, D["y0"], D["top"], zc + zs * HZ, zc + zs * (HZ + FS)) if zs > 0 else
             box(xa, xb, D["y0"], D["top"], zc - HZ - FS, zc - HZ)
             for xa, xb in ((-XSD, -XSP), (XSP, XSD)) for zs in (1, -1)],
            g + "Spacers", (0, 0, sd * .6))
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
            # Under the lowest sheet the gate stack lies on the BDI, where the seed was removed:
            # high-κ and work-function metal as floor films (no interfacial oxide on the dielectric).
            if nm != "il":
                f0 = TB + (0.0 if nm == "hk" else thk)
                bx = [box(-XG, XG, f0, f0 + t, zc - HZ, zc + HZ)]
                add(f"{k}_{nm}s", f"{WHO[k]} · {lab} · on the bottom isolation", mat, bx,
                    g + "Gate-all-around films", (0, -.3, sd * .6), "in" if nm == "wf" and wired else "body")
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
    # One gate over both: spacers either side, Mo fill, SiN cap (the model's), one contact (over the nFET).
    films = [b for p in out if p["group"].endswith("Gate-all-around films") for b in p["boxes"]]
    for s, T in ((-1, "source"), (1, "drain")):
        xa, xb = sorted((s * XG, s * XSP))
        add(f"spacer_{T}", f"SiBCN outer gate spacer · {T} side", "sibcn",
            subtract((xa, xb, 0, D["ycap"], gz0, gz1), stackboxes + sti_hi), "Spacers", (s * 1.3, 0, 0))
    # What the gate fill wraps: the BDI, the seed, the released sheets and their films.
    solid = [b for p in out if p["id"][2:].startswith(("bdi", "seed", "sheet")) for b in p["boxes"]] + films + sti_hi
    add("gate_mo", "Mo gate fill · one gate over both devices", "mo",
        subtract((-XG, XG, 0, D["ymo"], gz0, gz1), solid),
        "Gate electrode", (0, 1.0, 0), "in" if wired else "body")
    # The application leaves the gate coplanar with the spacers and ILD, with no cap [0126]; the
    # recess and SiN cap are the model's additions, as in the Si/SiGe design, so the gate contact
    # can go down through a cap onto the fill.
    gw = box(-XG, XG, D["ymo"], D["ycap"], -20, 20)
    add("gatecap", "SiN gate cap (material the model's choice)", "si3n4",
        carve((-XG, XG, D["ymo"], D["ycap"], gz0, gz1), [gw]), "Gate electrode", (0, 1.4, 0), "body")
    add("gatew", "W gate contact · one for the shared gate, through the cap", "tungsten",
        [gw], "Gate electrode", (0, 1.8, 0), "in" if wired else "body")
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
SCOPE = ("Si/Si CMOS nanosheet fabrication, after one example route: IBM's patent application "
         "US 2023/0178617 A1, “Nanosheet epitaxy with full bottom isolation” [R28]. "
         "Both the nFET and the pFET have Si channels [R28]. "
         "Undoped Si is grown in the source/drain openings [R28]. "
         "Bottom dielectric isolation lies under both devices; it is made by replacing a Ge-rich "
         "sacrificial layer [R28]. "
         "This is one disclosed example, not a production foundry flow. "
         "It is also a different route from the Si/SiGe lesson's patent [R13]: that patent's isolation "
         "and channel release are not used here. "
         "Dimensions are illustrative.")
FIGURES = ("Figure numbers are the application's (US 2023/0178617 A1, in docs/nsfet). "
           "Each state was compared with the drawings it names. "
           "The views are the app's own reconstructions, in its own frame and proportions. "
           "The application's alternate embodiment (Figs. 53–55) is not used.")
BRANCH = ("Both devices are followed together, side by side on one gate line. "
          "This is because their source/drain steps differ: each one is grown while the other "
          "region is protected. "
          "The contacts and the inverter wiring at the end complete the depicted devices for "
          "teaching. The application gives no complete routing recipe.")
SUBS = ["Dimensions are the model's illustrative choices, not the application's: 7 nm Si sheets, "
        "7 nm SiGe layers, an 8 nm Ge-rich layer and a 2 nm seed",
        "Only one site of each line is drawn; the lines run on past its source/drain edges"]
MATCH = {"source": "Source stage, adapted",
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
    FIGS = {"substrate": "2", "stack": "2–4", "lines": "5–7", "sti": "5–7", "dummy": "5–7",
            "spacers": "8–10", "recess": "11–13", "indent": "14–16", "inner": "14–16", "undoped": "17–19",
            "sti_recess": "20–22", "cavity": "23–25", "bdi": "26–28", "cesl": "29–31", "n_protect": "32–34",
            "p_sd": "35–40", "n_sd": "41–43", "ild": "44–46", "pull": "44–46", "release": "47–49",
            "hk": "50–52", "wfm": "50–52", "gate": "50–52"}
    views = dict(dev_views(dev), sd=dict(n="Through the drains", s="both devices, across the source/drain",
                                          az=1.5708, el=0.0, r=390, tgt=[25.5, 45, -42], clip=[25.5, None, None]))

    def snap(sid, title, body, view="iso", match="source", regions=None, **kw):
        figs = [FIGS[sid]] if match == "source" else ()
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

    def opl(k):
        z0, z1 = (ZC[k] - ZSUB, ZC[k] + ZSUB)
        F.drop("t_opl")
        F.put(tmp("t_opl", f"OPL over the {WHO[k]} region", "resist", "Region masks",
                  subtract((-XSD, XSD, 0, ycap + 16.0, z0, z1), F.boxes()), (0, 1.6, 0)))

    def keep_liner(pid, k, drop_in=None):
        """Keep liner [pid] only over region [k] (it is opened elsewhere); drop_in: gone from there too."""
        q = F.now[pid]; F.drop(pid)
        if drop_in == k: return
        z0, z1 = (ZC[k] - ZSUB, ZC[k] + ZSUB)
        F.put(dict(q, boxes=[[round(v, 4) for v in c] for c in bp.clip(q["boxes"], (-XSD, XSD, -1e3, 1e3, z0, z1))]))

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
         "One crystal stack is grown over both regions (epitaxy: new layers continue the wafer's "
         "crystal). From the bottom: a Ge-rich SiGe layer, a thin Si seed layer, then lower-Ge SiGe "
         "and Si in turn, with three Si layers in all [R28]. "
         "The Si layers become the channels of both devices [R28]. "
         "The SiGe layers are sacrificial: they are removed later. The lower-Ge SiGe comes out of "
         "the gate region. The Ge-rich layer, which etches selectively against it, is replaced by "
         "isolation [R28].",
         view="chann", subs=SUBS, deposit=["t_bot", "t_seed"] + [f"t_sg{i+1}" for i in range(3)] +
         [f"t_si{i+1}" for i in range(3)], regions=("shared stack", "shared stack"))
    # 3
    for pid in ["t_wafer", "t_bot", "t_seed"] + [f"t_sg{i+1}" for i in range(3)] + [f"t_si{i+1}" for i in range(3)]:
        F.drop(pid)
    F.add("substrate", "n_subfin", "p_subfin")
    # The seed runs the stack's full length until channel release removes it under the gate.
    for k in ("n", "p"):
        F.put(tmp(f"seed_{k}", f"{WHO[k]} · Si seed layer", "silicon", "Channel stack",
                  [foot(k, TB, Y0)], (0, -.4, 0)))
    for k in ("n", "p"): layers(k)
    for k in ("n", "p"):
        F.put(tmp(f"{k}_thm", f"{WHO[k]} · Stack hard mask", "si3n4", "Patterning", [foot(k, TOP, TOP + 6)], (0, 1.3, 0)))
    snap("lines", "Stack lines etched",
         "A hard mask defines one line per region [R28]. "
         "A directional etch then cuts through the multilayer into the substrate. It leaves two "
         "stack lines, each on a Si sub-fin [R28]. "
         "How the lines are printed (a direct exposure, SADP or SAQP) is a separate choice. The "
         "Lessons chips show those routes on the Si/SiGe lesson's tile.", view="gate", subs=SUBS + ["The hard mask's material and thickness are illustrative"],
         regions=("stack line", "stack line"))
    # 4
    F.drop("n_thm", "p_thm")
    sti = F.final["sti"]
    F.put(tmp("t_sti", sti["name"], sti["material"], sti["group"],
              [box(b[0] - b[3] / 2, b[0] + b[3] / 2, b[1] - b[4] / 2, Y0, b[2] - b[5] / 2, b[2] + b[5] / 2)
               for b in sti["boxes"] if b[1] - b[4] / 2 < -1], (0, -.8, 0)))
    snap("sti", "Shallow trench isolation",
         "A dielectric fills the trenches between the lines and is polished [R28]. "
         "It is then recessed to about the top of the seed layer, so the Ge-rich layer's sides stay "
         "covered for now. The hard mask is removed [R28].",
         view="gate", subs=SUBS, regions=("isolated line", "isolated line"))
    # 5
    stk = [foot(k, 0, TOP) for k in ("n", "p")]
    F.put(tmp("t_dummy", "Sacrificial gate (dummy poly-Si)", "poly", "Dummy gate",
              subtract((-XG, XG, 0, ymo, gz0, gz1), stk + F.boxes()), (0, 1.0, 0)))
    F.put(tmp("t_ghm", "Gate hard mask (SiN)", "si3n4", "Dummy gate", [box(-XG, XG, ymo, ycap, gz0, gz1)], (0, 1.4, 0)))
    snap("dummy", "Sacrificial gate and hard mask",
         "A sacrificial gate and its hard mask are patterned across both lines [R28]. "
         "This placeholder is not the real gate. It holds the channel regions' place and protects "
         "them until the replacement gate goes in [R28].",
         subs=SUBS + ["A thin dummy-gate oxide is not drawn",
                      "The application's sacrificial gate stands 50–100 nm above the stack; it is drawn shorter here",
                      "The SiN hard mask is the model's choice"], regions=("dummy gate", "dummy gate"))
    # 6
    F.add("spacer_source", "spacer_drain", "n_finsp", "p_finsp")
    snap("spacers", "Spacers",
         "Spacer 130 (130 is the application's reference number) is deposited and etched back [R28]. "
         "It is SiBCN here, one of the application's options. "
         "It stays on both sides of the sacrificial gate. It also stays along the stacks' sides "
         "between the gates, where it will bound the source/drain [R28].", view="chann", subs=SUBS, regions=("spacers", "spacers"))
    # 7
    for k in ("n", "p"):
        layers(k, sg=(-XSP, XSP), si=None)
        for i in range(3): F.add(f"{k}_sheet{i+1}")
        a, b = SG[0]
        F.put(tmp(f"{k}_trem", f"{WHO[k]} · SiGe, lower Ge · lowest layer, what the recess leaves", "sige",
                  f"{WHO[k]} · Channel stack", [foot(k, a, (a + b) / 2, -XSD, -XSP), foot(k, a, (a + b) / 2, XSP, XSD)]))
    snap("recess", "Source/drain recess",
         "Outside the gate and spacers, the stacks are etched down [R28]. "
         "The etch stops inside the lowest lower-Ge SiGe layer. The seed and the Ge-rich layer below "
         "stay intact [R28]. "
         "The sacrificial gate protects the channel regions [R28].",
         view="chann", subs=SUBS, regions=("recessed to the seed", "recessed to the seed"))
    # 8
    for k in ("n", "p"):
        layers(k, sg=(-XG, XG), si=None)
    snap("indent", "SiGe indented",
         "A selective etch removes one material and leaves another. Here it pulls the lower-Ge SiGe "
         "layers back from the exposed sheet ends, under the spacers [R28]. "
         "It also clears what was left of the lowest SiGe layer in the openings, exposing the seed. "
         "The Si sheets and the seed stay [R28].", view="chann", subs=SUBS,
         regions=("SiGe indented", "SiGe indented"))
    # 9
    F.add("n_inner_source", "n_inner_drain", "p_inner_source", "p_inner_drain")
    snap("inner", "Inner spacers",
         "Dielectric is deposited into the indents and etched back [R28]. "
         "What remains are the inner spacers. They will separate the gate from the source and "
         "drain [R28].", view="chann", subs=SUBS,
         regions=("inner spacers", "inner spacers"))
    # 10
    for k in ("n", "p"):
        F.put(tmp(f"{k}_ugrow", f"{WHO[k]} · Undoped Si (as grown)", "siu", f"{WHO[k]} · Source / drain",
                  [foot(k, Y0, TOP + 3, -XSD, -XSP), foot(k, Y0, TOP + 3, XSP, XSD)], (0, -.2, 0)))
    snap("undoped", "Undoped Si growth",
         "Undoped Si grows in the source/drain openings, from the exposed Si seed and the channel "
         "ends [R28]. It grows up past the top of the stack. "
         "This undoped layer is a feature of this route. Later, each device's trench etches it back, "
         "and that device's source/drain grows on what is left [R28].", view="chann", subs=SUBS,
         regions=("undoped Si grown", "undoped Si grown"))
    # 10b
    F.drop("t_sti"); F.add("sti")
    snap("sti_recess", "STI recessed",
         "The STI is recessed below the Ge-rich layer [R28]. "
         "This bares the layer's sides beside the source/drain openings.", view="sd", subs=SUBS, regions=("Ge-rich layer bared", "Ge-rich layer bared"))
    # 11
    for k in ("n", "p"): layers(k, sg=(-XG, XG), si=None, bot=False)
    snap("cavity", "Ge-rich layer removed",
         "The Ge-rich layer is removed by a selective etch (vapour HCl), through its sides bared above "
         "the recessed STI [R28]. "
         "This leaves a cavity beneath the stacks and the undoped Si. "
         "The sacrificial gate, the spacers and the growth regions hold the structure [R28].",
         view="sd", subs=SUBS, regions=("cavity below", "cavity below"))
    # 12
    F.add("n_bdi", "p_bdi")
    snap("bdi", "Bottom dielectric isolation",
         "Dielectric fills the cavity and is etched back [R28]. "
         "The result is bottom dielectric isolation (BDI): an insulator under both devices, beneath "
         "the channel stack and the undoped Si alike [R28].", view="sd", subs=SUBS,
         regions=("bottom isolation", "bottom isolation"))
    # 13
    F.put(tmp("t_cesl", "CESL 150 (SiN, 4 nm) · blanket", "si3n4", "Region masks",
              conformal(F.boxes(), 4.0, (-XSD, XSD, 0, ycap + 4.0, ZLO, ZHI)), (0, .8, 0)))
    snap("cesl", "Contact etch-stop liner",
         "A 4 nm etch-stop liner covers everything, in both regions [R28]. "
         "It is a nitride (SiN here).",
         view="sd", subs=SUBS, regions=("lined", "lined"))
    opl("n")
    snap("n_protect", "nFET region masked", "An organic planarisation layer (OPL) is patterned over "
         "the nFET region [R28]. Only the pFET's openings are left exposed.", view="sd", of="p_sd",
         subs=SUBS, regions=("masked", "open"))
    F.drop("t_opl", "p_ugrow"); F.add("p_undoped_source", "p_undoped_drain", "p_epi_source", "p_epi_drain")
    keep_liner("t_cesl", "n")
    snap("p_sd", "pFET source/drain",
         "The liner is opened over the pFET's openings [R28]. "
         "A trench etch recesses the pFET's undoped Si to below the lowest sheet [R28]. "
         "The OPL is removed. Boron-doped SiGe (SiGe:B) then grows from the Si sheet ends and the "
         "undoped Si [R28]. "
         "The pFET's channels stay Si; only its source/drain is SiGe [R28].",
         view="sd", subs=SUBS, regions=("masked", "SiGe:B source/drain"))
    # 14
    F.put(tmp("t_cesl2", "Second liner · blanket", "si3n4", "Region masks",
              conformal(F.boxes(), 4.0, (-XSD, XSD, 0, ycap + 8.0, ZLO, ZHI)), (0, .9, 0)))
    opl("p")
    snap("p_protect", "pFET region masked", "A second liner and a second OPL cover the pFET region. "
         "The application describes these but does not draw them [R28].", view="sd", match="teach", of="n_sd",
         subs=SUBS, regions=("open", "masked"))
    F.drop("t_opl", "n_ugrow"); F.add("n_undoped_source", "n_undoped_drain", "n_epi_source", "n_epi_drain")
    keep_liner("t_cesl", "n", drop_in="n"); keep_liner("t_cesl2", "p")
    snap("n_sd", "nFET source/drain",
         "The nFET now gets the same treatment [R28]. "
         "Its liners are opened, its undoped Si is recessed and the OPL is removed. "
         "Phosphorus-doped SiC (SiC:P) then grows from its sheet ends and undoped Si. SiC:P is one "
         "example the application gives [R28].", view="sd", subs=SUBS, regions=("SiC:P source/drain", "masked"))
    # 15
    F.drop("t_cesl", "t_cesl2")
    ild(ycap)
    snap("ild", "Interlayer dielectric", "Interlayer dielectric (ILD) 170 fills the "
         "structure and is polished down to the gate hard mask [R28]. "
         "In the application it is silicon nitride [R28].", view="chann",
         subs=SUBS + ["The application does not say when the liners come off; they are drawn removed here"],
         regions=("buried in ILD", "buried in ILD"))
    # 16
    F.drop("t_dummy", "t_ghm")                     # the ILD stays as it was: the trench is open
    snap("pull", "Sacrificial gate removed",
         "The hard mask and the sacrificial gate are removed [R28]. "
         "This opens the gate trench over both devices.", view="gate", subs=SUBS + ["The application removes the SiGe in the same step; the lesson "
                                             "shows it next, as the channel release"], regions=("gate trench open", "gate trench open"))
    # 17
    for k in ("n", "p"): F.drop_prefix(f"{k}_t")
    F.drop("seed_n", "seed_p")
    F.add("n_seed", "p_seed")
    snap("release", "Channel release",
         "Inside the gate opening, a selective etch removes the lower-Ge SiGe layers in both devices "
         "[R28]. This frees, or releases, the Si channels. "
         "A controlled oxidation and etch then thin the channels slightly [R28]. "
         "The same steps remove the exposed seed layer, which stays only under the inner spacers and the "
         "undoped Si [R28]. So the gate will sit on the bottom isolation. "
         "This route releases both devices the same way [R28].",
         view="gate", subs=SUBS + ["The thinning (1 nm or less) is not drawn"],
         regions=("Si channels released", "Si channels released"))
    # 18
    F.add(*[f"{k}_il{i}" for k in ("n", "p") for i in ("1", "2", "3")],
          *[f"{k}_hk{i}" for k in ("n", "p") for i in ("1", "2", "3", "s")])
    snap("hk", "Gate dielectric",
         "A high-κ dielectric is deposited all round each sheet and on the bottom isolation below "
         "them [R28]. High-κ means a higher permittivity than SiO₂. The film is about 2 nm "
         "thick [R28].", view="gate", subs=SUBS + [
             "HfO₂ is drawn for the high-κ, one of the application's options",
             "The thin SiO₂ interfacial layer is the model's addition; the application etches the oxide off before the high-κ"],
         regions=("high-κ", "high-κ"))
    # 19
    F.add(*[f"{k}_wf{i}" for k in ("n", "p") for i in ("1", "2", "3", "s")])
    snap("wfm", "Work-function metals",
         "Each device gets its own work-function metal: TiAlC on the nFET, TiN on the pFET [R28]. "
         "This thin metal sets the transistor's threshold voltage.", view="gate",
         subs=SUBS + ["How the two metals are patterned is the model's choice; the application does not say"], regions=("n-type work function", "p-type work function"))
    # 20
    F.add("gate_mo")
    cap = F.final["gatecap"]
    F.put(tmp("t_cap", cap["name"], cap["material"], cap["group"],
              [box(-XG, XG, D["ymo"], D["ycap"], *span(cap)[4:])], (0, 1.4, 0)))
    snap("gate", "Gate fill",
         "The gate stack fills the trench over both devices [R28]. "
         "It is planarised, level with the spacers and the ILD [R28]. "
         "There is one gate line, so the two gates are one electrode: the inverter's input.",
         view="gate", subs=SUBS + ["The Mo fill, its recess and the SiN cap are the model's choices; "
                                   "the application names no fill material and has no cap"],
         regions=("gate", "gate"))
    # 21
    F.drop("t_cap")
    F.add(*[f"{k}_{c}_{T}" for k in ("n", "p") for c in ("nisi", "ni") for T in ("source", "drain")], "gatecap", "gatew")
    ild(D["ym2"])
    snap("contacts", "Middle-of-line contacts",
         "Contact openings are etched through the ILD. "
         "A silicide (a metal–silicon compound that lowers contact resistance) forms on each "
         "source/drain, and metal fills the openings. One contact lands on the shared gate. "
         "These contacts complete the depicted devices for teaching; the application does not give "
         "this contact scheme.", view="sd",
         match="teach", subs=SUBS + ["The TiSiₓ and Co contacts are illustrative"],
         regions=("contacted", "contacted"))
    # 22
    F.drop("t_ild")
    snap("done", "The finished Si/Si pair",
         "Both devices have Si channels and bottom isolation. The undoped Si sits under each "
         "source/drain. One gate carries separate n- and p-type work-function metals. "
         "This is the Si/Si CMOS Device scene; the ILD is hidden for viewing only.", match="teach",
         subs=SUBS + ["The ILD is hidden for viewing only"], regions=("finished", "finished"))
    # 23
    F.add("m1_vss", "m1_vdd", "m1_out", "m1_in")
    snap("wiring", "Wired as an inverter",
         "The lesson completes the pair as an inverter, for teaching. IN goes on the shared gate, the "
         "pFET source to V_DD, the nFET source to V_SS, and both drains to OUT. "
         "This is the Si/Si CMOS Inverter scene. The application does not give a routing recipe.", view="iso", match="teach",
         subs=SUBS + ["One illustrative metal level; real cells route through several"],
         regions=("V_SS · OUT", "V_DD · OUT"))
    steps = F.done()
    return dev, steps, dict(
        scope=SCOPE, figures=FIGURES, branch=BRANCH, skipped={}, refs=["R28", "R13"], match=MATCH,
        views=views, own=True, name=dev.name, bounds=dev.bounds, final=dev.parts,
        audit_tile="Both devices are followed together on one gate line; steps n.k are operations "
                   "leading into core step n. No tile or line field is drawn.",
        audit_unverified=[
            "**Figure placements.** Each state was compared with the drawings it names; the second liner "
            "and OPL over the pFET region (step p_protect) are described but not drawn in the application.",
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
