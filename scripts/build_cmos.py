"""
Nanosheet CMOS scenes for the two channel designs, in Device and Inverter modes.

  Si/SiGe CMOS (key part "sige"): the patent-based example [R13]. One alternating Si/SiGe
    stack makes both devices: the nFET keeps the Si layers, the pFET the SiGe ones, so their
    sheets are staggered; bottom dielectric isolation under the nFET only; the pFET's SiGe:B
    source/drain grows from the recessed sub-fin too; one shared gate, no cut. Its devices
    are the Process flows' own finished nFET and pFET, so the Process lesson ends on them.
  Si/Si CMOS (key part "si"): a generic example with Si channels in both devices at the same
    heights and bottom dielectric isolation under both.

Each design comes as the compact geometry and as an exploded gate view, which enlarges the
gaps and films for inspection without changing materials, sheet order or connections.
Keys: "ns~<design>[~x]" (Device) and "inv_ns~<design>[~x]" (Inverter).
"""
import json, os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_devices as bd
import build_process as bp
from build_devices import box, check

DATA = HERE.parent / "data/devices.json"
DESIGNS = {"sige": "Si/SiGe CMOS", "si": "Si/Si CMOS"}
XG, XSP = bd.XG, bd.XSP


def lim(b):
    return [b[i] - b[i + 3] / 2 for i in range(3)] + [b[i] + b[i + 3] / 2 for i in range(3)]


def stack_of(exploded):
    return bd.NS_EXPLODED_STACK if exploded else bd.NS_PROCESS_STACK


def n_device(design, stack):
    d = bd.build_ns(stack)
    if design == "si":
        # Full bottom isolation under both devices: the sub-fin is plain Si, no stopper implant.
        for p in d.parts:
            if p["id"] == "pts":
                p.update(name="Si sub-fin (under the bottom isolation)", material="silicon")
    return d


def p_device(design, stack, exploded):
    if design == "sige":
        sheets = None
        if exploded:
            # The same stagger as the compact stack (half a pitch below each Si sheet), at the
            # exploded view's enlarged spacing.
            n = bd.build_ns(stack)
            t, pitch = stack["tch"], stack["tch"] + stack["tsg"]
            ys = sorted(lim(p["boxes"][0])[1:5:3] for p in n.parts if p["id"].startswith("sheet"))
            sheets = [(a - pitch / 2, a - pitch / 2 + t) for a, b in ys]
        return bp.build_ns_p(stack, sheets)
    # Si/Si: the nFET's structure with Si sheets kept, a TiN work-function metal and SiGe:B epi.
    d = bd.build_ns(stack)
    for p in d.parts:
        i = p["id"]
        if i.startswith("sheet"):
            p["name"] = p["name"].replace("Si nanosheet", "Si nanosheet · pFET channel")
        elif i.startswith("tin"):
            p.update(material=bd.WFM["p"], name=p["name"].replace("n-type work-function metal", bd.WFL["p"]))
        elif i.startswith("epi_"):
            p.update(material="sige", name=p["name"].replace("(Si:P)", "(SiGe:B)"))
        elif i == "pts":
            p.update(name="Si sub-fin (under the bottom isolation)", material="silicon")
    return d


def sige_pair(design, exploded, wired, stack):
    """The Si/SiGe pair: the Process flows' own finished nFET and pFET, side by side on one gate."""
    nd, pd = n_device(design, stack), p_device(design, stack, exploded)
    P = {p["id"]: p for p in nd.parts}
    zsub = lim(P["substrate"]["boxes"][0])[5]
    dz = 2 * zsub                                    # the two cells abut
    cap = lim(P["gatecap"]["boxes"][0]); ymo, ycap, hzmo = cap[1], cap[4], cap[5]
    ym2 = lim(P["w_drain"]["boxes"][0])[4]
    key, name, tag = scene_names(design, exploded, wired)
    d = bd.Dev(key, name, tag, "")
    who = dict(n="nFET", p="pFET")

    def net(k, p):
        if not wired: return "body"
        i, m = p["id"], p["material"]
        if i.startswith(("sheet", "psheet")): return "chan_" + k
        if m in ("mo", "nwf") or (m == "tin") or i == "gatew": return "in"
        if m in ("silicon", "sige", "tisi", "cobalt", "tungsten") and ("source" in i or "drain" in i):
            return ("gnd" if k == "n" else "vdd") if "source" in i else "out"
        return "body"

    for k, dev, shift in (("n", nd, 0.0), ("p", pd, -dz)):
        for p in dev.parts:
            if k == "p" and p["id"] == "gatew": continue          # one gate contact: the gate is shared
            bx = [list(b) for b in p["boxes"]]
            for b in bx: b[2] = round(b[2] + shift, 4)
            ex = list(p["explode"])
            if ex and ex[0] == "radial":
                ex = ex[:3] + [shift]                       # films open out round their own device
            else:
                ex[2] += 0.6 if k == "n" else -0.6          # and the two devices part a little
            d.add(f"{k}_{p['id']}", f"{who[k]} · {p['name']}", p["material"], bx, f"{who[k]} · {p['group']}", ex)
            d.parts[-1]["net"] = net(k, p)
    # The gate line between the two devices: spacers either side, Mo fill and TiN cap.
    z0, z1 = -dz + hzmo, -hzmo
    g = "Shared gate"
    d.add("b_spacers", "Si₃N₄ gate spacers · between the devices", "si3n4",
          [box(XG, XSP, 0, ycap, z0, z1), box(-XSP, -XG, 0, ycap, z0, z1)], g, [0, 0, 0])
    d.parts[-1]["net"] = "body"
    d.add("b_mo", "Mo gate fill · joins the two gates", "mo", [box(-XG, XG, 0, ymo, z0, z1)], g, [0, 1.0, 0])
    d.parts[-1]["net"] = "in" if wired else "body"
    d.add("b_cap", "TiN gate cap · between the devices", "tin", [box(-XG, XG, ymo, ycap, z0, z1)], g, [0, 1.4, 0])
    d.parts[-1]["net"] = "in" if wired else "body"

    if wired:
        # One metal level over the contacts: V_SS to the nFET source, V_DD to the pFET source,
        # OUT joining both drains, IN on the gate contact.
        t = 8.0
        ya, yb = ym2, ym2 + t
        hz = lim(P["sheet1"]["boxes"][0])[5]
        xs0, xs1 = -bd.XSD, -XSP
        xd0, xd1 = XSP, bd.XSD
        m = "Metal 1"
        d.add("m1_vss", "V_SS (GND) rail and strap · nFET source", "tungsten",
              [box(xs0, xs1, ya, yb, -hz, zsub - t), box(-48, 48, ya, yb, zsub - t, zsub)], m, [0, 1.6, .6])
        d.parts[-1]["net"] = "gnd"
        d.add("m1_vdd", "V_DD rail and strap · pFET source", "tungsten",
              [box(xs0, xs1, ya, yb, -dz - zsub + t, -dz + hz), box(-48, 48, ya, yb, -dz - zsub, -dz - zsub + t)], m, [0, 1.6, -.6])
        d.parts[-1]["net"] = "vdd"
        d.add("m1_out", "OUT · joins both drains", "tungsten", [box(xd0, xd1, ya, yb, -dz - hz, hz)], m, [0, 1.6, 0])
        d.parts[-1]["net"] = "out"
        gw = lim(P["gatew"]["boxes"][0])
        d.add("m1_in", "IN · on the shared gate's contact", "tungsten", [box(gw[0], gw[3], ya, yb, gw[2], gw[5])], m, [0, 1.7, 0])
        d.parts[-1]["net"] = "in"
        d.logic = True

    d.finish()
    return d, dz, 2 * lim(P["sheet1"]["boxes"][0])[5]


def scene_names(design, exploded, wired):
    key = ("inv_" if wired else "") + f"ns~{design}" + ("~x" if exploded else "")
    return (key, "Nanosheet inverter" if wired else "Nanosheet CMOS pair",
            DESIGNS[design] + (" · exploded gate view (not to scale)" if exploded else " · compact geometry"))


def compose(design, exploded, wired):
    stack = stack_of(exploded)
    if design == "si":
        # The Si/Si pair is its lesson's own finished structure (scripts/build_nssi.py).
        import build_nssi as nssi
        d, _ = nssi.si_device(stack, wired, *scene_names(design, exploded, wired))
        dz, wsh = nssi.DZ, 2 * nssi.HZ
    else:
        d, dz, wsh = sige_pair(design, exploded, wired, stack)
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    R = 2.3 * max(B["x"][1] - B["x"][0], B["y"][1] - B["y"][0], B["z"][1] - B["z"][0])
    yc = ctr[1]
    d.views = {
        "iso": dict(n="3D overview", s="nFET in front, pFET behind", az=-0.76, el=0.36, r=R * .95, tgt=ctr, clip=None),
        "gate": dict(n="Through the gate", s="both devices in section", az=1.5708, el=0.0, r=R * .9, tgt=ctr, clip=[0, None, None]),
        "chann": dict(n="Along the nFET channel", s="source · gate · drain", az=0.0, el=0.02, r=R * .62,
                      tgt=[0, yc, 0], clip=[None, None, 0]),
        "chanp": dict(n="Along the pFET channel", s="source · gate · drain", az=0.0, el=0.02, r=R * .62,
                      tgt=[0, yc, -dz], clip=[None, None, -dz]),
    }
    if wired:
        d.views["plan"] = dict(n="Routing", s="V_DD · V_SS · IN · OUT", az=-1.5708, el=1.02, r=R * .9, tgt=ctr, clip=None)

    # --- what the design is, in numbers and words --------------------------------------
    t, gap = stack["tch"], stack["tsg"]
    pitch = t + gap
    enl = " (enlarged)" if exploded else ""
    eot = round(stack["til"] + stack["thk"] * 3.9 / 22.0, 2)
    n_sheets = sorted(lim(q["boxes"][0])[1] for q in d.parts if q["id"].startswith("n_sheet"))
    p_sheets = sorted(lim(q["boxes"][0])[1] for q in d.parts if q["id"].startswith(("p_sheet", "p_psheet")))
    off = n_sheets[0] - p_sheets[0]
    d.dims = [
        ["Design", "Channel design", DESIGNS[design] + (" · patent-based example (US 12,568,683 B2)" if design == "sige" else "")],
        ["Display", "Geometry shown", "exploded gate view: not to scale" if exploded else "compact"],
        ["Channels", "nFET · pFET", "3 Si sheets · 3 SiGe sheets" if design == "sige" else "3 Si sheets · 3 Si sheets"],
        ["t_ch", "Sheet thickness, both devices", f"{t:g} nm"],
        ["Gap", "Clear gap between one device's sheets" + enl, f"{gap:g} nm"],
        ["Pitch", "Vertical pitch = sheet thickness + clear gap" + enl, f"{pitch:g} nm"],
        ["Stagger", "pFET sheets relative to the nFET's",
         f"{off:g} nm lower (half a pitch)" if design == "sige" else "same heights"],
        ["BDI", "Bottom dielectric isolation", "under the nFET only" if design == "sige" else
         "under both devices, where a Ge-rich layer was"],
        ["WFM", "Work-function metal", "n-type (nFET) · TiN (pFET)"],
        ["S/D", "Source/drain epitaxy",
         "Si:P (nFET) · SiGe:B, also from the sub-fin (pFET)" if design == "sige" else
         "SiC:P (nFET) · SiGe:B (pFET), each on an undoped Si region"],
        ["Gate", "Gate arrangement", "one shared gate, no gate cut"],
        ["L_G", "Physical gate length", f"{bd.LG:g} nm"],
        ["W_sh", "Sheet width", f"{wsh:g} nm"],
        ["EOT", "Equivalent oxide thickness of the drawn films" + enl, f"{eot:g} nm"],
        ["—", "These numbers", "the model's illustrative choices" + (", not the patent's" if design == "sige" else "")],
    ]
    if design == "si": d.dims.insert(8, ["Seed", "Si seed layer under each stack, on the isolation", "2 nm"])
    if wired: d.dims.append(["Nets", "V_DD · V_SS · IN · OUT", "4"])
    if exploded: d.dims.append(["—", "Capacitance estimates", "shown with Exploded gate view off"])

    if design == "sige":
        body = ("<b>Si/SiGe CMOS: the patent-based example.</b> One alternating Si/SiGe stack makes both "
                "devices: the nFET keeps its three Si layers as channels and the pFET its three lower-Ge SiGe "
                "layers, so the pFET's sheets sit between the nFET's heights, staggered. Bottom dielectric "
                "isolation is under the nFET only; the pFET's SiGe:B source/drain grows from the recessed "
                "sub-fin as well as from the sheet ends, which helps put its channels under compressive strain. "
                "Each device has its own work-function metal on one shared gate: this uses the patent's "
                "shared-gate arrangement, with no gate cut. One disclosed example [R13], not a universal "
                "foundry flow; the thicknesses are the model's illustrative choices, not the patent's. The "
                "Process lesson ends on these same two devices.")
    else:
        body = ("<b>Si/Si CMOS: the full-bottom-isolation example.</b> Si nanosheet channels in both "
                "devices, at the same heights, after the example route of IBM's application US 2023/0178617 A1 "
                "[R28]: a Ge-rich bottom layer, a Si seed and Si layers between lower-Ge SiGe; the Ge-rich layer "
                "replaced by bottom dielectric isolation under both devices; undoped Si grown in each "
                "source/drain opening from the seed, under a SiGe:B (pFET) or SiC:P (nFET) source/drain; the "
                "SiGe removed at channel release in both. A separate route from the Si/SiGe lesson's, not its "
                "finished state. Each device has its own work-function metal on one shared gate. One example, "
                "not a production foundry flow; the thicknesses are the model's illustrative choices. The "
                "Process lesson ends on these same two devices.")
    if exploded:
        body += (" <b>Exploded gate view: schematic enlargement; dimensions are not to scale.</b> The gaps "
                 f"between sheets are drawn {gap:g} nm and the films {stack['til']:g}/{stack['thk']:g}/"
                 f"{stack['twf']:g} nm so each can be seen and tapped; materials, sheet order and connections "
                 "are the compact view's.")
    else:
        body += (" In this compact geometry the drawn films meet in the gaps between one device's sheets; "
                 "turn on Exploded gate view to see each film.")
    if wired:
        body += (" The inverter: both gates take IN through the shared gate, the pFET source connects to V_DD, "
                 "the nFET source to V_SS (GND), and the two drains join at OUT.")
    d.note = body
    d.blurb = ("An nFET and a pFET on one shared gate" + (", wired as an inverter" if wired else "") +
               (": Si nFET channels and SiGe pFET channels, from one stack." if design == "sige"
                else ": Si channels in both devices."))
    # A few measurements on the nFET, in the section views.
    s = sorted((lim(q["boxes"][0]) for q in d.parts if q["id"].startswith("n_sheet")), key=lambda b: b[1])
    zc = s[0][5]
    d.cal("tch", "t<sub>ch</sub>", f"{t:g} nm", "Sheet thickness", [0, s[1][1], zc], [0, s[1][4], zc],
          [0, s[1][1] + 3, zc + 34], ["gate"])
    d.cal("gap", "Gap" + (" (enlarged)" if exploded else ""), f"{gap:g} nm", "Clear gap between sheets",
          [0, s[0][4], -zc], [0, s[1][1], -zc], [0, (s[0][4] + s[1][1]) / 2, -zc - 30], ["gate"])
    d.cal("pitch", "Pitch", f"{pitch:g} nm", "Sheet thickness + clear gap", [0, s[1][1], zc + 6], [0, s[2][1], zc + 6],
          [0, (s[1][1] + s[2][1]) / 2, zc + 40], ["gate"])
    return d


def scenes():
    out = []
    for wired in (False, True):
        for design in ("sige", "si"):
            for exploded in (False, True):
                d = compose(design, exploded, wired)
                mx, n = check(d)
                if mx != 1: sys.exit(f"{d.key}: {mx} solids overlap")
                out.append(d)
    return out


if __name__ == "__main__":
    G = json.load(open(DATA))
    G["devices"] = [x for x in G["devices"] if x["key"] not in ("ns", "inv_ns") and "~" not in x["key"]]
    for d in scenes():
        entry = dict(key=d.key, name=d.name, tag=d.tag, blurb=d.blurb, parts=d.parts, callouts=d.callouts,
                     dims=d.dims, views=d.views, note=d.note, bounds=d.bounds,
                     groups=list(dict.fromkeys(p["group"] for p in d.parts)))
        if getattr(d, "logic", False): entry["logic"] = True
        G["devices"].append(entry)
        print(f"{d.key:16s} parts={len(d.parts):3d}  no overlaps")
    json.dump(G, open(DATA, "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize(DATA) // 1024, "KB", len(G["devices"]), "scenes")
