"""
CMOS inverter cells, each built from its Device model with one metal level added.

The FinFET inverter is the Process lesson's both-sites result on the shared gate (the Device
nFET beside its pFET); the forksheet and CFET inverters are their Device scenes, which already
hold both devices; the nanosheet inverters come from build_cmos.py. Every part carries a `net`
so the viewer can light the conducting path:
  vdd | gnd | out | in | chan_p | chan_n | body
Runs after build_process.py, whose FinFET both-sites flow it reads.
"""
import json, os
from pathlib import Path
from build_devices import Dev, box, check
import build_devices as bd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/devices.json"
T_M1 = 8.0                                   # metal-1 thickness, nm

NOTE_FIN = ("<b>The Device's FinFET, twice.</b> The nFET is the Device scene; the pFET beside it is the "
            "Process lesson's pFET, SiGeB source/drain and TiN work-function metal, after US 9,812,358 B1 "
            "[R29]. One Co gate fill under the AlOₓ hard mask runs across both: the shared-gate ending of "
            "the both-sites lesson. Both transistors use two fins, a geometric width ratio of 1; that does "
            "not guarantee electrical balance. The metal level over the contacts is this drawing's.")
NOTE_FS = ("<b>The Device's forksheet, wired.</b> After imec's EP 3 989 273 A1: one W gate fill runs over "
           "the wall and serves both devices, and the contact partition wall keeps their source/drain "
           "contacts apart [R31]. TSMC's US 2024/0178128 A1 joins the gates differently, with a gate "
           "bridge contact on a wall that splits them [R35]; that variant is not drawn. The metal level "
           "over the contacts is this drawing's. Sheets are drawn 21 nm apart (centre to centre) so every "
           "film shows; real stacks space them roughly 7-12 nm apart.")
NOTE_CFET = ("<b>The Device's monolithic CFET, wired.</b> After US 11,869,812 B2: the pFET below the nFET, "
             "one gate for both, one contact landing on both drains (the output), the nFET source reached "
             "from above and the pFET source through the space a sacrificial TiOₓ spacer left [R33]. All "
             "four nets are on the front; the metal level over the contacts is this drawing's. Sheets are "
             "drawn 20 nm apart (centre to centre) so every film shows.")

COND = ("cobalt", "tungsten", "tisi", "tin", "wfill", "cofill", "mo", "nwf", "copper")


def lim(b):
    return (b[0] - b[3] / 2, b[0] + b[3] / 2, b[1] - b[4] / 2, b[1] + b[4] / 2, b[2] - b[5] / 2, b[2] + b[5] / 2)


def span(p):
    L = [lim(b) for b in p["boxes"]]
    return tuple(f(v[k] for v in L) for k, f in enumerate((min, max, min, max, min, max)))


def build(key, name, tag, blurb, parts, net, m1, note, dims, zcut):
    """[parts] with [net](part) → net; [m1] as (id, name, net, boxes); views and callouts added."""
    d = Dev(key, name, tag, blurb)
    for p in parts:
        d.add(p["id"], p["name"], p["material"], p["boxes"], p["group"], p["explode"])
        d.parts[-1]["net"] = net(p)
    for pid, nm, n, boxes in m1:
        d.add(pid, nm, "tungsten", boxes, "Metal 1", [0, 1.6, 0])
        d.parts[-1]["net"] = n
    for pid, lab, desc in (("m1_vdd", "V<sub>DD</sub>", "rail feeding the pFET source"),
                           ("m1_gnd", "GND", "rail at the nFET source"),
                           ("m1_out", "OUT", "both drains tied together"),
                           ("m1_in", "IN", "one gate across both devices")):
        x0, x1, y0, y1, z0, z1 = span(next(p for p in d.parts if p["id"] == pid))
        c = [(x0 + x1) / 2, y1, (z0 + z1) / 2]
        d.cal(pid[3:], lab, "", desc, c, [c[0], y1 + 1, c[2]], [c[0], y1 + 24, c[2]], None)
    d.logic = True
    d.note = note
    d.dims = dims
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    R = 2.30 * max(B["x"][1] - B["x"][0], B["y"][1] - B["y"][0], B["z"][1] - B["z"][0])
    d.views = {
      "cell": dict(n="3D overview", s="everything wired up", az=-.82, el=.32, r=R, tgt=ctr, clip=None),
      "gate": dict(n="Through the gate", s="both devices in section", az=1.5708, el=0, r=R * .92, tgt=ctr, clip=[0, None, None]),
      "chan": dict(n="Along the channel", s="source · gate · drain", az=0, el=.02, r=R * .76, tgt=ctr, clip=[None, None, zcut]),
      "plan": dict(n="Routing", s="metal 1 over the contacts", az=-1.5708, el=1.02, r=R * .88, tgt=ctr, clip=None),
      "top": dict(n="Top view", s="straight down on the cell", az=-1.5708, el=1.45,
                  r=2.1 * max(B["z"][1] - B["z"][0], (B["x"][1] - B["x"][0]) * 1.5), tgt=ctr, clip=None)}
    return d


def device_json(key):
    return next(d for d in json.load(open(DATA))["devices"] if d["key"] == key)


def sd_net(pid, pol):
    return ("gnd" if pol == "n" else "vdd") if "source" in pid else "out"


def rails(xs, zs_n, zs_p, y, zlo, zhi, xd, zd, xg, zg):
    """GND strap over the nFET source to a rail on the +z edge, V_DD over the pFET source to the
    -z edge, OUT across both drains, IN on the gate contact."""
    t = T_M1
    return [
        ("m1_gnd", "GND rail and strap (M1) · nFET source", "gnd",
         [box(xs[0], xs[1], y, y + t, zs_n[0], zhi - t), box(-48, 48, y, y + t, zhi - t, zhi)]),
        ("m1_vdd", "V_DD rail and strap (M1) · pFET source", "vdd",
         [box(xs[0], xs[1], y, y + t, zlo + t, zs_p[1]), box(-48, 48, y, y + t, zlo, zlo + t)]),
        ("m1_out", "OUT (M1) · joins both drains", "out", [box(xd[0], xd[1], y, y + t, zd[0], zd[1])]),
        ("m1_in", "IN (M1) · on the gate contact", "in", [box(xg[0], xg[1], y, y + t, zg[0], zg[1])]),
    ]


def dims_of(key, extra):
    rows = [r for r in device_json(key).get("dims", []) if r and r[0] not in ("—",)]
    return rows[:6] + extra


# ------------------------------------------------------------------ FinFET
def inv_fin():
    flow = json.load(open(ROOT / "data/process.json"))["flows"]["fin_pair"]
    st = next(s for s in flow["steps"] if s["id"] == "shared")
    parts = [p for p in st["parts"] if isinstance(p, dict) and p["material"] != "ild"
             and p["group"] not in ("Patterning", "Region masks", "Interlayer dielectric")]
    P = {p["id"]: p for p in parts}

    def net(p):
        i, m = p["id"], p["material"]
        k, b = i[:1], i[2:]
        sd = "source" in b or "drain" in b
        if sd and (m in COND or m in ("silicon", "sige")) and not b.startswith(("seal", "spacer")):
            return sd_net(b, k)
        if b.startswith("fin") and m in ("silicon", "sige"): return "chan_" + k
        if m in ("cofill", "nwf", "wfill") or (m == "tin" and not sd) or b == "gatew" or i == "b_mo":
            return "in"
        return "body"
    ns, ps, nd, pd, gw = (span(P[i]) for i in ("n_ni_source", "p_ni_source", "n_ni_drain", "p_ni_drain", "n_gatew"))
    y = ns[3]
    zlo, zhi = min(span(p)[4] for p in parts), max(span(p)[5] for p in parts)
    m1 = rails((ns[0], ns[1]), (ns[4], ns[5]), (ps[4], ps[5]), y, zlo, zhi,
               (nd[0], nd[1]), (pd[4], nd[5]), (gw[0], gw[1]), (gw[4], gw[5]))
    zc = (span(P["n_fin2"])[4] + span(P["n_fin2"])[5]) / 2
    return build("inv_fin", "FinFET inverter", "tri-gate · 2 fins per device",
                 "The Device's FinFET nFET beside the Process lesson's pFET on one shared gate, wired as a CMOS "
                 "inverter: the pFET source to V_DD, the nFET source to GND, both drains to OUT, the gate to IN.",
                 parts, net, m1, NOTE_FIN,
                 dims_of("fin", [["Devices", "nFET and pFET, one gate", "2 × 2 fins"],
                                 ["Cell z", "Rail-to-rail span (z)", f"{zhi - zlo:g} nm"]]), zc)


# --------------------------------------------------------------- forksheet
def inv_fs():
    dev = bd.build_fs()
    parts = [p for p in dev.parts]
    P = {p["id"]: p for p in parts}

    def net(p):
        i, m = p["id"], p["material"]
        pol = "n" if "_n" in i else "p" if "_p" in i else ""
        sd = "source" in i or "drain" in i
        if sd and pol and i.startswith(("epi", "nisi", "ni_")): return sd_net(i, pol)
        if i.startswith("sheet_"): return "chan_" + pol
        if m in ("wfill", "nwf") or (m == "tin" and not sd) or i == "gatew": return "in"
        return "body"
    ns, ps, nd, pd, gw = (span(P[i]) for i in ("ni_n_source", "ni_p_source", "ni_n_drain", "ni_p_drain", "gatew"))
    y = ns[3]
    zlo, zhi = dev.bounds["z"]
    m1 = rails((ns[0], ns[1]), (ns[4], ns[5]), (ps[4], ps[5]), y, zlo, zhi,
               (nd[0], nd[1]), (pd[4], nd[5]), (gw[0], gw[1]), (gw[4], gw[5]))
    return build("inv_fs", "Forksheet inverter", "n and p astride the wall",
                 "The Device's forksheet wired as a CMOS inverter: the common gate over the wall is IN, the "
                 "pFET source goes to V_DD, the nFET source to GND, and both drains to OUT [R31].",
                 parts, net, m1, NOTE_FS,
                 dims_of("fs", [["Cell z", "Rail-to-rail span (z)", f"{zhi - zlo:g} nm"]]),
                 (ns[4] + ns[5]) / 2)


# -------------------------------------------------------------------- CFET
def inv_cfet():
    dev = bd.build_cfet_mono()
    parts = [p for p in dev.parts]
    P = {p["id"]: p for p in parts}

    def net(p):
        i, m = p["id"], p["material"]
        if i in ("epi_n_source", "nisi_source", "ni_source"): return "gnd"
        if i in ("epi_p_source", "ni_lo_source", "sil_lo_source"): return "vdd"
        if i in ("epi_n_drain", "epi_p_drain", "sil_up_drain", "sil_lo_drain", "ni_drain"): return "out"
        if i.startswith("sheet_"): return "chan_" + i[6]
        if m in ("wfill", "nwf", "tin") or i == "gatew": return "in"
        return "body"
    t = T_M1
    ns, lo, nd, gw = (span(P[i]) for i in ("ni_source", "ni_lo_source", "ni_drain", "gatew"))
    y = ns[3]
    zlo, zhi = dev.bounds["z"]
    # The lower source's riser comes up on the +z side of the source, so V_DD takes the +z edge
    # here and GND the -z edge.
    lo_top = [lim(b) for b in P["ni_lo_source"]["boxes"] if lim(b)[3] >= y - 1e-6][0]
    m1 = [
        ("m1_gnd", "GND rail and strap (M1) · nFET source", "gnd",
         [box(ns[0], ns[1], y, y + t, zlo + t, ns[5]), box(-48, 48, y, y + t, zlo, zlo + t)]),
        ("m1_vdd", "V_DD rail and strap (M1) · pFET source, through its riser", "vdd",
         [box(lo_top[0], lo_top[1], y, y + t, lo_top[4], zhi - t), box(-48, 48, y, y + t, zhi - t, zhi)]),
        ("m1_out", "OUT (M1) · on the common drain contact", "out", [box(nd[0], nd[1], y, y + t, nd[4], nd[5])]),
        ("m1_in", "IN (M1) · on the gate contact", "in", [box(gw[0], gw[1], y, y + t, gw[4], gw[5])]),
    ]
    return build("inv_cfet", "CFET inverter", "one stack, one gate",
                 "The Device's monolithic CFET wired as an inverter: pFET below, nFET above, one gate as IN, "
                 "one contact on both drains as OUT, and both sources contacted from the front [R33].",
                 parts, net, m1, NOTE_CFET,
                 dims_of("cfet_mono", [["Cell z", "Rail-to-rail span (z)", f"{zhi - zlo:g} nm"]]), 0.0)


# ----------------------------------------------------------------- compare
def inv_cmp(cells_in):
    d = Dev("inv_cmp", "Inverter compare", "four cells, one scale",
            "The four Inverter scenes at a common geometric scale. The z spans include the drawn rails. "
            "They are not iso-performance or foundry-library comparisons.")
    cells, cur, GAP = [], -300.0, 45.0
    for src, nm in cells_in:
        B = src["bounds"]
        w = B["z"][1] - B["z"][0]
        zoff = cur - B["z"][0]
        for p in src["parts"]:
            boxes = [[b[0], b[1], b[2] + zoff, b[3], b[4], b[5]] for b in p["boxes"]]
            e = p["explode"]
            if isinstance(e, list) and len(e) and e[0] == "radial":
                e = ["radial", e[1], e[2], (e[3] if len(e) > 3 else 0.0) + zoff]
            d.add(f"{src['key'].split('~')[0]}_{p['id']}", p["name"], p["material"], boxes, f"{nm} cell", e)
            d.parts[-1]["net"] = p.get("net", "body")
        cells.append((nm, cur + w / 2.0, w, B["y"][1]))
        cur += w + GAP
    w0 = cells[0][2]
    for nm, zc, w, ytop in cells:
        d.cal(f"w_{nm}", nm, f"{w:g} nm", f"cell height (rail-to-rail span) · {w / w0 * 100:.0f}% of FinFET",
              [0, -26, zc - w / 2], [0, -26, zc + w / 2], [0, -52, zc], ["front", "iso"])
        d.cal(f"h_{nm}", nm, "", "rail to rail", [0, ytop, zc], [0, ytop + 1, zc], [0, ytop + 30, zc], ["front", "iso"])
    d.dims = [[nm, "Rail-to-rail span (z)", f"{w:g} nm  ({w / w0 * 100:.0f}%)"] for nm, zc, w, yt in cells]
    d.dims.append(["—", "What is being measured", "one inverter, both rails"])
    d.dims.append(["—", "Sheets or fins per device", "2 fins / 3 / 3 / 2 per tier"])
    d.logic = True
    d.note = ("<b>Rail-to-rail span.</b> These are the four Inverter scenes side by side; the values describe "
              "the model's lateral z dimension, commonly called cell height in standard-cell layout practice. "
              "A smaller drawn span alone does not demonstrate higher achievable density or speed. For scale, "
              "imec's roadmap puts standard-cell height at roughly 115 nm for A14 nanosheets, 98 nm for A10 "
              "forksheets and under 80 nm for A7 CFETs; the spans drawn here are the model's own.")
    d.finish()
    B = d.bounds
    ctr = [(B["x"][0] + B["x"][1]) / 2, (B["y"][0] + B["y"][1]) / 2, (B["z"][0] + B["z"][1]) / 2]
    zs = B["z"][1] - B["z"][0]
    d.views = {
      "front": dict(n="Head on", s="cell heights, side by side", az=-1.5708, el=0.03, r=zs * 1.52, tgt=ctr, clip=None),
      "iso": dict(n="All four", s="same scale", az=-1.40, el=0.28, r=zs * 1.55, tgt=ctr, clip=None),
      "top": dict(n="Top view", s="straight down", az=-1.5708, el=1.45, r=zs * 1.52, tgt=ctr, clip=None)}
    return d


def entry(d):
    return dict(key=d.key, name=d.name, tag=d.tag, blurb=d.blurb, parts=d.parts, callouts=d.callouts,
                dims=d.dims, views=d.views, note=d.note, bounds=d.bounds, logic=True,
                groups=list(dict.fromkeys(p["group"] for p in d.parts)))


if __name__ == "__main__":
    import sys, findlap
    G = json.load(open(DATA))
    G["devices"] = [x for x in G["devices"] if x["key"] not in ("inv_fin", "inv_ns", "inv_fs", "inv_cfet", "inv_cmp")]
    made = {}
    for f in (inv_fin, inv_fs, inv_cfet):
        d = f(); mx, n = check(d)
        laps = findlap.overlaps(d)
        print(f"{d.key:10s} parts={len(d.parts):3d} boxes={n:4d} max/voxel={mx}" + ("  LAP:" + str(laps) if laps else ""))
        if mx != 1: sys.exit(f"{d.key}: overlapping solids")
        made[d.key] = entry(d)
    ns = next(x for x in G["devices"] if x["key"] == "inv_ns~sige")
    cmp_ = inv_cmp([(made["inv_fin"], "FinFET"), (ns, "Nanosheet"), (made["inv_fs"], "Forksheet"),
                    (made["inv_cfet"], "CFET")])
    mx, n = check(cmp_)
    print(f"{cmp_.key:10s} parts={len(cmp_.parts):3d} boxes={n:4d} max/voxel={mx}")
    G["devices"] += list(made.values()) + [entry(cmp_)]
    json.dump(G, open(DATA, "w"), separators=(",", ":"))
    print("devices.json", os.path.getsize(DATA) // 1024, "KB", len(G["devices"]), "scenes")
