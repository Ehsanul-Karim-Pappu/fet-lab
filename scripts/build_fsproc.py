"""
The forksheet pair's fabrication lesson, after imec's patent application EP 3 989 273 A1, "A
method for forming a semiconductor device and a semiconductor device" [R31]: its Fig. 5 flow
chart for the front end and the gate, its Figs. 3a–3g for the liner, the contact partition wall
and the source/drain contacts, and its Fig. 6 for the finished pair.

The route, as modelled here:
  a Si/SiGe stack with a thicker top SiGe layer; the wall trench etched through it into the
  substrate and filled with SiN (the order the application gives as its alternative, the wall
  before the lines); the stack lines patterned either side of the wall, STI; the sacrificial
  gate across both lines and the wall, gate spacers; the stacks recessed, the SiGe indented and
  inner spacers formed; the P-doped source/drain grown with the N region masked, then the
  N-doped one with the P region masked; liner 133; ILD 134; the contact partition trench etched
  above the wall and filled; the source/drain contact trenches either side of it, TiN and W;
  the replacement metal gate (the sacrificial gate removed, the SiGe released, high-κ, the
  P-type metal on both sides and off the N side, the N-type metal, the W fill); the gate
  recessed and capped; and, as the lesson's educational completion, a gate contact and the
  inverter wiring.

The finished frames are the Forksheet Device and Inverter scenes part for part: the lesson is
built on build_inverters.inv_fs(), the Device's forksheet with one metal level added.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_devices as bd
import build_process as bp
import build_inverters as bi
from build_devices import box
from build_process import tmp, subtract, conformal, clip, lim, span

XG, XSP, XSD = bd.XG, bd.XSP, bd.XSD          # gate, spacer and site half-lengths: 7.5 / 14.5 / 36.5
WHO = dict(n="nFET", p="pFET")
SUBS = ["Dimensions are the model's, within the application's ranges where it gives them: an 8 nm "
        "wall, 22 nm wide and 5 nm thick Si sheets; the 16 nm SiGe layers are drawn thick so every "
        "film shows",
        "Only one site of each line is drawn; the lines run on past its source/drain edges"]
MATCH = {"source": "Source stage, adapted",
         "teach": "Teaching reconstruction; no source figure",
         "concept": "Concept-only operation"}
SCOPE = ("Forksheet fabrication after one example route: imec's patent application EP 3 989 273 A1 "
         "[R31]. An insulating wall stands between the pFET's and the nFET's stacks of Si sheets, so "
         "the two can sit closer together than two separate nanosheet devices [R31]. "
         "The front end and the replacement gate follow the application's flow chart (its Fig. 5). "
         "The liner, the contact partition wall and the source/drain contacts follow its Figs. 3a–3g, "
         "and the finished pair its Fig. 6 [R31]. "
         "This is one disclosed example, not a production foundry flow. "
         "Dimensions are illustrative.")
FIGURES = ("Figure numbers are the application's (EP 3 989 273 A1, in docs/fsfet). Fig. 5 is its flow "
           "chart, so a step that cites it is one of the chart's boxes, which the text describes but no "
           "drawing shows. Each state that cites Figs. 3a–3g or 6 was compared with that drawing. "
           "The views are the app's own reconstructions, in its own frame and proportions: the "
           "application draws three sections, along each stack and across both at one side of the gate.")
BRANCH = ("Both devices are followed together, one on each side of the wall, the pFET behind and the "
          "nFET in front. Their source/drain steps differ: each one is grown while the other region "
          "is masked, and each gets its own work-function metal. "
          "The gate contact and the inverter wiring at the end complete the depicted devices for "
          "teaching. The application gives no routing recipe.")
SKIPPED = {"3h": "the optional contact recess and re-deposited ILD; the Device scene's contacts are not recessed",
           "4a–4b": "a variation that forms the contact partition wall in a sacrificial planarising layer "
                    "instead of the ILD"}


def flow(done=None):
    dev = bi.inv_fs()                                # the Device's forksheet, wired
    F = bp.Flow(dev)
    FIN = F.final
    sp = lambda pid: span(FIN[pid])
    _, _, YB, YW, _, ZI = sp("wall"); YB = -YB       # wall base depth, wall top, wall half-width
    STI, ZSUB = sp("sti")[3], sp("sti")[5]
    ZO = sp("sheet_n1")[5]
    SI = [sp(f"sheet_n{i}")[2:4] for i in (1, 2, 3)]
    TOP = SI[-1][1]
    SG = [(STI, SI[0][0]), (SI[0][1], SI[1][0]), (SI[1][1], SI[2][0])]
    _, _, YMO, YCAP, _, ZMO = sp("gatecap")
    YSD = sp("epi_n_source")[3]
    ZP = sp("cpw_source")[5]
    YI = YCAP + 3.0                                  # ILD over the gate caps (Figs. 3b, 3e)
    ZS = dict(n=(ZI, ZO), p=(-ZO, -ZI))
    SDX = dict(source=(-XSD, -XSP), drain=(XSP, XSD))
    FIGS = {"stack": "5", "trench": "5", "wall": "5", "lines": "5", "sti": "5", "dummy": "5",
            "spacers": "5", "recess": "5", "indent": "5", "inner": "5", "n_mask": "5", "p_sd": "5",
            "p_mask": "5", "n_sd": "5", "liner": "3a", "ild": "3b", "pw_mask": "3b", "pw_trench": "3c",
            "pw": "3d", "sd_mask": "3e", "sd_trench": "3f", "contacts": "3g", "pull": "5", "release": "5",
            "hk": "5", "pwfm": "5", "pmask": "5", "pwfm_off": "5", "nwfm": "5", "fill": "5", "grecess": "5", "done": "6"}
    fsd = bd.build_fs()
    views = dict(fsd.views, b=dict(fsd.views["b"], n="Along the nFET stack"),
                 sd=dict(n="Through the drains", s="both stacks, across the source/drain", az=1.5708, el=0.0,
                         r=300, tgt=[25.5, 48, 0], clip=[25.5, None, None]),
                 chp=dict(n="Along the pFET stack", s="source · gate · drain", az=0.0, el=0.0, r=280,
                          tgt=[0, 44, 0], clip=[None, None, -(ZI + ZO) / 2]))

    def snap(sid, title, body, view="iso", match="source", regions=None, **kw):
        figs = [FIGS[sid]] if match == "source" else ()
        F.snap(sid, title, body, view, match=match, figs=figs, src=["R31"] if figs else (), **kw)
        if regions: F.steps[-1]["regions"] = dict(n=regions[0], p=regions[1])

    def carve(pid, *regions):
        """Part [pid] less the [regions] (x0,x1,y0,y1,z0,z1); gone if nothing is left."""
        q = F.now[pid]; F.drop(pid)
        bx = [c for b in q["boxes"] for c in subtract(lim(b), [box(*r) for r in regions])]
        if bx: F.put(dict(q, boxes=[[round(v, 4) for v in c] for c in bx]))

    def trim(pid, region):
        """Part [pid] cut down to [region]."""
        q = F.now[pid]; F.drop(pid)
        bx = clip(q["boxes"], region)
        if bx: F.put(dict(q, boxes=[[round(v, 4) for v in c] for c in bx]))

    def mask(pid, name, z0, z1, top):
        F.drop(pid)
        F.put(tmp(pid, name, "resist", "Region masks", subtract((-XSD, XSD, 0, top, z0, z1), F.boxes()), (0, 1.6, 0)))

    # 1 -------------------------------------------------------------------------------- S502
    F.put(tmp("t_wafer", "Si substrate", "silicon", "Substrate & isolation",
              [box(-48, 48, -26, 0, -ZSUB, ZSUB), box(-XSD, XSD, 0, STI, -ZSUB, ZSUB)], (0, -1.2, 0)))
    lay = []
    for i in range(3):
        F.put(tmp(f"t_sg{i+1}", f"SiGe, higher Ge · second layer {i+1}", "sige", "Channel stack",
                  [box(-XSD, XSD, *SG[i], -ZSUB, ZSUB)]))
        F.put(tmp(f"t_si{i+1}", f"Si · channel layer {i+1}", "silicon", "Channel stack",
                  [box(-XSD, XSD, *SI[i], -ZSUB, ZSUB)]))
        lay += [f"t_sg{i+1}", f"t_si{i+1}"]
    F.put(tmp("t_sga", "SiGe · thicker top second layer (116a)", "sige", "Channel stack",
              [box(-XSD, XSD, TOP, YW, -ZSUB, ZSUB)]))
    snap("stack", "Si/SiGe stack",
         "Si channel layers and SiGe second layers are grown in turn, as one crystal [R31]. "
         "The SiGe has more Ge than the Si, so it can later be etched away and leave the Si [R31]. "
         "The top SiGe layer is thicker than the others. It sets how far the wall will rise above the "
         "top channel [R31].",
         view="c", subs=SUBS, deposit=lay + ["t_sga"], regions=("shared stack", "shared stack"))
    # 2
    slot = (-XSD, XSD, -YB, YW, -ZI, ZI)
    for pid in ["t_wafer", "t_sga"] + lay: carve(pid, slot)
    snap("trench", "Wall trench",
         "A narrow trench is etched through the stack, along the boundary between the pFET and nFET "
         "regions [R31]. "
         "It goes on into the substrate, so the wall that fills it will have its base embedded there. "
         "That steadies the wall and improves the isolation between the two devices [R31].",
         view="c", subs=SUBS + ["The trench is drawn 8 nm wide, within the application's 5–20 nm"],
         regions=("boundary", "boundary"))
    # 3 -------------------------------------------------------------------------------- S504
    F.add("wall")
    snap("wall", "Insulating wall",
         "SiN fills the trench: it is deposited conformally until the films on the two sidewalls "
         "meet and close it, then removed outside the trench [R31]. "
         "This is the insulating wall. Its top is level with the top of the thick SiGe layer, so it "
         "stands above the top channel [R31].",
         view="c", subs=SUBS + ["SiN is the first of the application's wall materials (SiN, SiCO, SiCN, SiOCN)"],
         regions=("wall beside", "wall beside"))
    # 4 -------------------------------------------------------------------------------- S502
    outer = [(-XSD, XSD, 0, YW, ZO, ZSUB), (-XSD, XSD, 0, YW, -ZSUB, -ZO)]
    for pid in ["t_sga"] + lay:
        q = F.now[pid]; F.drop(pid)
        for k in ("n", "p"):
            z0, z1 = ZS[k]
            bx = clip(q["boxes"], (-XSD, XSD, -1e3, 1e3, z0, z1))
            F.put(dict(q, id=f"{k}_t{pid[2:]}",
                       name=f"{WHO[k]} · {q['name']}", group=f"{WHO[k]} · Channel stack",
                       boxes=[[round(v, 4) for v in c] for c in bx]))
    F.drop("t_wafer"); F.add("substrate")
    snap("lines", "Stack lines",
         "With the wall in place, the stack is patterned into two lines, one each side of it [R31]. "
         "The application gives this order as its alternative. In the other, the trench and the "
         "lines are etched together and the trench filled afterwards [R31]. "
         "The etch goes on into the substrate beside the pair, for the isolation trenches [R31]. "
         "How the lines are printed (a single exposure, SADP or SAQP) is a separate choice [R31].",
         view="c", subs=SUBS, regions=("stack line", "stack line"))
    # 5
    F.add("sti")
    snap("sti", "Shallow trench isolation",
         "Silicon oxide fills the trenches beside the pair. This is the shallow trench isolation "
         "(STI) [R31]. It is recessed to the sub-fins' top, so the whole stack stands above it.",
         view="c", subs=SUBS + ["The recess depth is the model's choice"], regions=("isolated", "isolated"))
    # 6 -------------------------------------------------------------------------------- S506
    F.put(tmp("t_dummy", "Sacrificial gate 128 (amorphous Si)", "poly", "Sacrificial gate",
              subtract((-XG, XG, STI, YMO, -ZMO, ZMO), F.boxes()), (0, 1.0, 0)))
    F.put(tmp("t_cap130", "Gate cap 130 (hard mask; SiN drawn)", "si3n4", "Sacrificial gate",
              [box(-XG, XG, YMO, YCAP, -ZMO, ZMO)], (0, 1.4, 0)))
    snap("dummy", "Sacrificial gate",
         "A sacrificial gate of amorphous Si runs across both stack lines and over the wall [R31]. "
         "It is one gate for the two devices. On top is gate cap 130, the hard mask left from "
         "patterning it [R31]. "
         "The gate is a placeholder: the real gate replaces it later [R31]. Where it crosses the "
         "lines it marks the channels; the stack either side becomes source and drain [R31].",
         view="iso", subs=SUBS + ["The cap's material is the model's choice; the application says hard-mask material"],
         regions=("dummy gate", "dummy gate"))
    # 7
    # Over the stacks the spacer stands on the thick top layer for now; the finished spacer
    # also fills that layer's indent (step 10).
    for k in ("n", "p"):
        beside = (ZO, ZMO) if k == "n" else (-ZMO, -ZO)
        for T, (xa, xb) in (("source", (-XSP, -XG)), ("drain", (XG, XSP))):
            F.put(tmp(f"t_sp_{k}_{T}", f"SiBCN gate spacer · {k} {T}", "sibcn", "Spacers",
                      [box(xa, xb, STI, YCAP, *beside), box(xa, xb, YW, YCAP, *ZS[k])]))
    F.add("spacer_c")
    snap("spacers", "Gate spacers",
         "A spacer film is deposited conformally and etched back from the top. What stays on the "
         "sacrificial gate's sides is gate spacer 132 [R31]. "
         "It is SiBCN here, one of the application's options.",
         view="iso", subs=SUBS + ["The application notes the film also stays on the source/drain sides "
                                  "and the wall's sides; only the gate's spacers are drawn"],
         regions=("spacers", "spacers"))
    # 8 -------------------------------------------------------------------------------- S508
    for k in ("n", "p"):
        for pid in [x for x in F.now if x.startswith(f"{k}_t")]:
            trim(pid, (-XSP, XSP, -1e3, 1e3, -1e3, 1e3))
        for i in range(3):
            F.drop(f"{k}_tsi{i+1}")
            F.add(f"sheet_{k}{i+1}")
    snap("recess", "Stack recess",
         "Outside the gate and its spacers, both stacks are etched down to the sub-fins [R31]. "
         "What stays under the gate is each device's own stack: its Si sheets, the SiGe between "
         "them, and the wall at their inner side [R31].",
         view="b", subs=SUBS, regions=("recessed", "recessed"))
    # 9 -------------------------------------------------------------------------------- S510
    for k in ("n", "p"):
        for pid in [x for x in F.now if x.startswith(f"{k}_tsg")]:
            trim(pid, (-XG, XG, -1e3, 1e3, -1e3, 1e3))
    snap("indent", "SiGe indented",
         "A selective etch pulls the SiGe layers back from the recess walls, under the spacers. The Si "
         "sheets stay [R31].",
         view="b", subs=SUBS, of="inner", regions=("SiGe indented", "SiGe indented"))
    # 10
    for k in ("n", "p"):
        for T in ("source", "drain"):
            F.drop(f"t_sp_{k}_{T}")
            F.add(f"spacer_{k}_{T}", f"inner_{k}_{T}")
    snap("inner", "Inner spacers",
         "Dielectric fills the indents and is etched back, so it stays only in them. These are the "
         "inner spacers: they cover the SiGe's ends, where the gate will later be [R31].",
         view="b", subs=SUBS + ["SiN, the first of the application's options",
                                "In the thick top layer's indent the model draws the gate spacer's SiBCN"],
         regions=("inner spacers", "inner spacers"))
    # 11 ------------------------------------------------------------------------------- S512
    mask("t_mask", "Mask over the nFET region", 0, ZSUB, YCAP + 6)
    snap("n_mask", "nFET region masked",
         "The nFET region is masked, so the pFET's source/drain can grow alone [R31].",
         view="sd", of="p_sd", subs=SUBS + ["The mask is drawn as one layer; its material is the model's"],
         regions=("masked", "open"))
    F.drop("t_mask"); F.add("epi_p_source", "epi_p_drain")
    snap("p_sd", "pFET source/drain",
         "P-doped Si grows from the exposed ends of the pFET's sheets: selective-area epitaxy, which "
         "grows only on the exposed silicon [R31]. "
         "The wall bounds it on the inside, so it cannot spread over to the nFET [R31]. "
         "The mask is then removed.",
         view="sd", subs=SUBS + ["Boron is the model's choice of P-type dopant"], regions=("masked", "P-doped Si"))
    mask("t_mask", "Mask over the pFET region", -ZSUB, 0, YCAP + 6)
    snap("p_mask", "pFET region masked", "Now the pFET region is masked [R31].", view="sd", of="n_sd",
         subs=SUBS + ["The mask is drawn as one layer; its material is the model's"], regions=("open", "masked"))
    F.drop("t_mask"); F.add("epi_n_source", "epi_n_drain")
    snap("n_sd", "nFET source/drain",
         "N-doped Si grows from the nFET's sheet ends in the same way [R31]. "
         "The two source/drains face each other across the wall and never touch [R31].",
         view="sd", subs=SUBS + ["Phosphorus is the model's choice of N-type dopant"], regions=("N-doped Si", "P-doped Si"))
    # 12 -------------------------------------------------------------------------- Fig. 3a
    win = (-XSD, XSD, 0, YCAP + 1, -ZSUB, ZSUB)
    F.put(tmp("t_liner", "SiN liner 133 (ALD) · conformal", "si3n4", "Liner", conformal(F.boxes(), 1.0, win), (0, .8, 0)))
    snap("liner", "Liner",
         "A thin SiN liner, liner 133, is deposited conformally by ALD over everything: the gate, the "
         "source/drains, the STI and the exposed wall [R31]. "
         "It is optional in the application, but its figures draw it. It will act as an etch stop "
         "and protects the source/drains [R31].",
         view="sd", subs=SUBS + ["Drawn 1 nm thick"], regions=("lined", "lined"))
    # 13 ------------------------------------------------------------------- S514, Fig. 3b
    F.put(tmp("t_ild", "ILD 134 (silicon oxide)", "ild", "Interlayer dielectric",
              subtract((-XSD, XSD, 0, YI, -ZSUB, ZSUB), F.boxes()), (0, .6, 0)))
    snap("ild", "Interlayer dielectric",
         "Silicon oxide is deposited over everything by flowable CVD and polished flat. This "
         "interlayer dielectric (ILD), material layer 134 in the application, buries the gates [R31].",
         view="sd", subs=SUBS, regions=("buried", "buried"))
    # 14 ------------------------------------------------------------------------------- S520
    hole = [(-XSD, XSD, YI, YI + 4, -ZSUB, -ZP), (-XSD, XSD, YI, YI + 4, ZP, ZSUB)]
    F.put(tmp("t_m136", "Etch mask 136 (a lithographic stack, drawn as one layer)", "resist", "Region masks",
              [box(*r) for r in hole], (0, 1.6, 0)))
    snap("pw_mask", "Partition-trench mask",
         "An etch mask goes on the ILD. Its long, narrow opening, opening 138, runs directly above the "
         "wall [R31].",
         view="sd", of="pw", subs=SUBS, regions=("masked", "masked"))
    tr = [(-XSD, -XSP, YW, YI, -ZP, ZP), (XSP, XSD, YW, YI, -ZP, ZP), (-XSP, XSP, YCAP + 1, YI, -ZP, ZP)]
    carve("t_ild", *tr); carve("t_liner", *tr[:2])
    snap("pw_trench", "Partition trench",
         "A dry etch cuts through the ILD under the opening, down to the wall's top [R31]. "
         "It does not etch the gate, so one opening gives a trench on each side of the gate, joined "
         "above it [R31].",
         view="sd", of="pw", subs=SUBS + ["The trench is drawn 12 nm wide, wider than the wall, within the application's 10–24 nm",
                                          "The application lets this etch stop on the wall or on the liner; the model opens the "
                                          "liner, which is drawn removed where the trench passes"],
         regions=("trench above the wall", "trench above the wall"))
    F.drop("t_m136"); F.add("cpw_source", "cpw_drain")
    for pid in ("t_ild", "t_liner"): trim(pid, (-1e3, 1e3, -1e3, YCAP, -1e3, 1e3))
    snap("pw", "Contact partition wall",
         "The trench is filled with SiN and polished back until the gate caps show, level with the "
         "ILD [R31]. "
         "What is left either side of the gate is the contact partition wall. It stands on the "
         "insulating wall and is wider than it, which makes the trench easier to etch and fill [R31].",
         view="sd", subs=SUBS, regions=("partition wall", "partition wall"))
    # 15 ------------------------------------------------------------------------------- S522
    F.put(tmp("t_ild2", "ILD 134 · upper thickness, re-deposited", "ild", "Interlayer dielectric",
              [box(-XSD, XSD, YCAP, YI, -ZSUB, ZSUB)], (0, .6, 0)))
    F.put(tmp("t_m144", "Etch mask 144 (a lithographic stack, drawn as one layer)", "resist", "Region masks",
              [box(-XSD, XSD, YI, YI + 4, -ZSUB, -ZO), box(-XSD, XSD, YI, YI + 4, ZO, ZSUB)], (0, 1.6, 0)))
    snap("sd_mask", "Contact mask",
         "More ILD covers the gates again, and a second mask goes on. Its one wide opening, opening "
         "146, spans the source/drains on both sides of the wall and both sides of the gate [R31].",
         view="sd", of="contacts", subs=SUBS, regions=("opening over it", "opening over it"))
    opening = [(-XSD, XSD, YCAP, YI, -ZO, ZO)] + [(a, b, YSD, YCAP, -ZO, ZO) for a, b in SDX.values()]
    carve("t_ild2", *opening[:1]); carve("t_ild", *opening[1:])
    snap("sd_trench", "Contact trenches",
         "The ILD is etched through the opening. The etch removes the oxide but not the partition "
         "wall, the gate or the liner, so it stops on the liner over each source/drain [R31]. "
         "One opening thus gives four trenches: two each side of the gate, split by the partition "
         "wall [R31].",
         view="sd", of="contacts", subs=SUBS, regions=("trenches", "trenches"))
    F.drop("t_m144", "t_ild2")
    fin_liner = [b for k in "np" for T in ("source", "drain") for b in FIN[f"liner_{k}_{T}"]["boxes"]]
    floor = [b for k in "np" for T in ("source", "drain") for b in FIN[f"nisi_{k}_{T}"]["boxes"]]
    q = F.now["t_liner"]; F.drop("t_liner")
    rest = [c for b in q["boxes"] for c in subtract(lim(b), fin_liner + floor)]
    F.put(dict(q, name="SiN liner 133 · under the ILD", boxes=[[round(v, 4) for v in c] for c in rest]))
    F.add(*[f"{c}_{k}_{T}" for c in ("liner", "nisi", "ni") for k in "np" for T in ("source", "drain")])
    snap("contacts", "Source/drain contacts",
         "A short nitride etch opens the liner at each trench's floor, baring the source/drain [R31]. "
         "TiN is deposited by ALD, then W fills the trenches by CVD [R31]. "
         "Polishing removes the metal outside the trenches, down to the gate caps. That leaves four "
         "separate contacts: the gate splits each device's pair, and the partition wall splits the "
         "pFET's from the nFET's [R31].",
         view="sd", subs=SUBS + ["The TiN is drawn only at the floor",
                                 "The contacts stay within the source/drain's width"],
         regions=("contacts", "contacts"))
    # 16 ------------------------------------------------------------------------------- S516
    F.drop("t_cap130", "t_dummy")
    snap("pull", "Sacrificial gate removed",
         "The gate cap is opened and the amorphous Si removed by a selective etch [R31]. "
         "This opens a gate trench each side of the wall, one over each stack [R31].",
         view="c", subs=SUBS + ["The application also allows the contacts to be made after the gate; "
                                "this lesson follows its figures, which make them first"],
         regions=("gate trench", "gate trench"))
    for pid in [x for x in F.now if x.startswith(("n_t", "p_t"))]: F.drop(pid)
    snap("release", "Channel release",
         "Inside the gate trenches, an HCl-based dry etch removes the SiGe and leaves the Si [R31]. "
         "The sheets are only partly released. Their tops, bottoms and outer sides are bared, but "
         "their inner sides stay on the wall [R31]. "
         "Each sheet is held by the wall and its source/drain.",
         view="fork", subs=SUBS, regions=("sheets released", "sheets released"))
    F.add(*[f"{f}_{k}{i}" for f in ("il", "hk") for k in "np" for i in (1, 2, 3)],
          *[f"floor_{f}_{k}" for f in ("il", "hk") for k in "np"])
    snap("hk", "Gate dielectric",
         "A high-κ dielectric is deposited in both gate trenches [R31]. High-κ means a higher "
         "permittivity than SiO₂. "
         "It covers each sheet's three bared faces, and the sub-fin under the lowest sheet.",
         view="c", subs=SUBS + ["HfO₂, the first of the application's options",
                                "The thin SiO₂ interfacial layer is the model's addition"],
         regions=("high-κ", "high-κ"))
    wf = lambda k: [f"tin_{k}{i}" for i in (1, 2, 3)] + [f"floor_wf_{k}"]
    F.add(*wf("p"))
    for pid in wf("n"):
        q = FIN[pid]
        F.put(tmp("t_" + pid, "TiN p-type work-function metal · on the nFET side, for now", "tin",
                  q["group"], q["boxes"], q["explode"]))
    snap("pwfm", "P-type metal, both sides",
         "The P-type work-function metal, TiN, is deposited conformally by ALD in both gate trenches "
         "[R31]. This thin metal sets the transistor's threshold voltage.",
         view="c", subs=SUBS, regions=("TiN", "TiN"))
    mask("t_mask", "Mask over the pFET region", -ZSUB, 0, YCAP + 6)
    snap("pmask", "pFET region masked", "The pFET region is masked [R31].", view="c", of="pwfm_off",
         subs=SUBS + ["The mask is drawn as one layer; its material is the model's"], regions=("open", "masked"))
    F.drop("t_mask", *["t_" + pid for pid in wf("n")])
    snap("pwfm_off", "P-type metal off the nFET",
         "The TiN is etched away on the nFET's side, and the mask removed [R31]. "
         "The wall is what stops this etch from reaching sideways under the mask into the pFET's "
         "metal, which is why it rises above the top channel [R31].",
         view="c", subs=SUBS, regions=("TiN removed", "TiN"))
    F.add(*wf("n"))
    snap("nwfm", "N-type metal",
         "The N-type work-function metal, TiAlC, is deposited in the nFET's gate trench [R31]. "
         "Each device now has its own metal, and the wall keeps them 8 nm apart.",
         view="c", subs=SUBS + ["The application lets this metal go on both sides; the model draws it on the nFET only"],
         regions=("TiAlC", "TiN"))
    F.add("mo_n", "mo_p", "mo_c")
    F.put(tmp("t_wtop", "W gate fill · to the cap's level", "wfill", "Gate electrode",
              [box(-XG, XG, YMO, YCAP, -ZMO, ZMO)], (0, 1.2, 0)))
    snap("fill", "Gate fill",
         "W fills both gate trenches and is polished flat [R31]. "
         "Above the wall the fill is common, joining the two gates into one electrode. That is the "
         "option the application's background describes; its own figures do not cut through the "
         "gate at the wall [R31].",
         view="c", subs=SUBS + ["W, the first of the application's fills (W, Al, Co, Ru)"],
         regions=("gate", "gate"))
    # 17 ------------------------------------------------------------------------------- S518
    F.drop("t_wtop")
    F.put(tmp("t_cap", "SiN gate cap (material the model's choice)", "si3n4", "Gate electrode",
              [box(-XG, XG, YMO, YCAP, -ZMO, ZMO)], (0, 1.4, 0)))
    snap("grecess", "Gate recessed",
         "The gate is recessed [R31]. A gate cut, which the application also allows here, is not "
         "made: one gate serves both devices. "
         "The model caps the recess with SiN, as its other designs do, so a gate contact can go "
         "down through the cap.",
         view="c", subs=SUBS + ["The SiN cap is the model's choice; the application only recesses the gate"],
         regions=("recessed and capped", "recessed and capped"))
    F.drop("t_cap"); F.add("gatecap", "gatew")
    snap("gatecontact", "Gate contact",
         "A contact is etched through the cap and filled with W, onto the shared gate. "
         "This completes the depicted devices for teaching; the application does not give it.",
         view="c", match="teach", subs=SUBS, regions=("contacted", "contacted"))
    F.drop("t_ild", "t_liner")
    snap("done", "The finished forksheet pair",
         "Each device's Si sheets are gated on three faces, their fourth on the wall [R31]. "
         "The pFET has TiN, the nFET TiAlC, and one W fill joins them over the wall. "
         "The partition wall keeps their contacts apart [R31]. "
         "This is the Forksheet Device scene; the ILD and the liner it buries are hidden for viewing only.",
         view="fork", subs=SUBS + ["The ILD and the liner under it are hidden for viewing only"],
         regions=("finished", "finished"))
    F.add("m1_vdd", "m1_gnd", "m1_out", "m1_in")
    snap("wiring", "Wired as an inverter",
         "The lesson completes the pair as an inverter, for teaching. IN goes on the shared gate, the "
         "pFET source to V_DD, the nFET source to GND, and both drains to OUT. "
         "This is the Forksheet Inverter scene. The application does not give a routing recipe.",
         view="iso", match="teach", subs=SUBS + ["One illustrative metal level; real cells route through several"],
         regions=("GND · OUT", "V_DD · OUT"))
    steps = F.done()
    return dev, steps, dict(
        scope=SCOPE, figures=FIGURES, branch=BRANCH, skipped=SKIPPED, refs=["R31"], match=MATCH,
        views=views, own=True, name="Forksheet FET", bounds=dev.bounds, final=dev.parts,
        audit_tile="Both devices are followed together, one each side of the wall; steps n.k are "
                   "operations leading into core step n. No tile or line field is drawn.",
        audit_unverified=[
            "**Fig. 5 steps.** A step that cites Fig. 5 is one of the flow chart's boxes. The application "
            "describes it in its text but draws no state for it, so the model's geometry there is its own.",
            "**Order.** The wall is formed before the lines, the application's alternative order; the "
            "contacts come before the replacement gate, as in its Figs. 3a–3g and 6.",
            "**Dimensions.** All thicknesses are the model's illustrative choices, within the "
            "application's ranges where it gives them.",
            "**Gate contact and wiring.** The educational completion of the depicted devices, not the "
            "application's."])
