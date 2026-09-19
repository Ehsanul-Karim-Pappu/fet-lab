#!/usr/bin/env python3
"""Derive the parasitic capacitances of each device scene from its own geometry.

Nothing here is typed in. Every number comes from the boxes in devices.json: the facing
area between two conductors, the gap between them, and the material that fills the gap.
That is only defensible because the scenes are drawn to scale — a first-order estimate on
geometry that was not would be decoration.

What is modelled, per device, summing both the source and the drain side:

  C_ox   gate to channel through the interfacial oxide and the high-κ. The useful one;
         everything else is measured against it.
  C_gc   gate to the source/drain contact metal across the spacer. Parallel plate. This
         is the term that scales worst — it is set by gate height, contact height and
         spacer width, and none of the three shrink with the node.
  C_if   gate to the raised epi, from gate metal lying within the channel stack. The
         gate-all-around penalty: metal that wraps between the sheets faces the epi over
         an area a fin never had.
  C_of   gate to the raised epi, from gate metal above the top channel. Classic outer
         fringe, and worse the taller the gate.
  C_j    source/drain to the body underneath. Junction, not a dielectric gap, so it uses
         a stated depletion width rather than a film thickness.

Method: rasterise the y–z plane at RES nm. For every cell, find the facing surfaces of the
two conductor groups along x, take the gap between them, look up which material actually
sits in that gap at that cell, and add ε0·εr·dA/d. A parallel-plate sum over the real
facing area, which for a structure made of axis-aligned films is the honest first order.

It is a first order. There is no field solver here: fringing beyond the facing overlap,
corner enhancement and the bias dependence of the junction are all outside it. Treat the
ratios between architectures as the result, not the absolute femtofarads.
"""
import json, math, os, sys
from paths import DATA
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = 0.25                      # y–z raster, nm
EPS0 = 8.8541878128e-3           # aF/nm  (F/m × 1e18 aF/F × 1e-9 m/nm)
W_DEP = 5.0                      # junction depletion width, nm — an assumption, not geometry

# Relative permittivity. Conductors get None and are never used as a gap filler.
EPS_R = {
    "sio2": 3.9, "si3n4": 7.5, "highk": 22.0, "silicon": 11.7, "sige": 13.0,
    "mdi": 4.2, "bond": 3.9, "wall": 7.5,
    "mo": None, "tin": None, "tungsten": None, "nickel": None, "nisi": None,
}
CONDUCTOR = {m for m, v in EPS_R.items() if v is None}

def boxes_of(dev, pred):
    out = []
    for p in dev["parts"]:
        if not pred(p):
            continue
        for b in p["boxes"]:
            out.append((b[0] - b[3] / 2, b[0] + b[3] / 2,
                        b[1] - b[4] / 2, b[1] + b[4] / 2,
                        b[2] - b[5] / 2, b[2] + b[5] / 2, p["material"]))
    return out

def grid(dev):
    B = dev["bounds"]
    y = np.arange(B["y"][0] + RES / 2, B["y"][1], RES)
    z = np.arange(B["z"][0] + RES / 2, B["z"][1], RES)
    return np.meshgrid(y, z, indexing="ij")

def cover(bx, Y, Z):
    """Boolean mask of the y–z cells this box covers."""
    return (Y >= bx[2]) & (Y < bx[3]) & (Z >= bx[4]) & (Z < bx[5])

def face(bxs, Y, Z, side):
    """The x of the surface each group presents, per cell. side=-1 takes the lowest x
    (the face looking towards -x), side=+1 the highest."""
    out = np.full(Y.shape, np.inf if side < 0 else -np.inf)
    for bx in bxs:
        m = cover(bx, Y, Z)
        if side < 0:
            out = np.where(m, np.minimum(out, bx[0]), out)
        else:
            out = np.where(m, np.maximum(out, bx[1]), out)
    return out

def filler(dielectrics, Y, Z, xm, valid):
    """Relative permittivity of whatever occupies the midpoint of each gap."""
    er = np.where(valid, 1.0, 0.0)          # nothing there means vacuum
    for bx in dielectrics:
        k = EPS_R.get(bx[6])
        if k is None:
            continue
        m = valid & cover(bx, Y, Z) & (xm >= bx[0]) & (xm < bx[1])
        er = np.where(m, k, er)
    return er

def couple(dev, A, B, Y, Z, sign, band=None):
    """Capacitance between conductor groups A and B, facing each other along x.

    sign=-1 looks at the source side (A's -x face towards B's +x face); +1 the drain side.
    band optionally restricts the sum to a y range, which is how inner and outer fringe
    are separated: they are the same coupling, counted over different heights.
    """
    if not A or not B:
        return 0.0, 0.0
    if sign < 0:
        aX, bX = face(A, Y, Z, -1), face(B, Y, Z, +1)
    else:
        aX, bX = face(A, Y, Z, +1), face(B, Y, Z, -1)
        aX, bX = -aX, -bX                    # mirror so the same comparison works
    with np.errstate(invalid="ignore"):
        gap = aX - bX
    ok = np.isfinite(gap) & (gap > 1e-6)
    if band is not None:
        ok &= (Y >= band[0]) & (Y < band[1])
    if not ok.any():
        return 0.0, 0.0
    with np.errstate(invalid="ignore"):
        mid = (aX + bX) / 2.0 * (1 if sign < 0 else -1)
    xm = np.where(ok, mid, 0.0)
    er = filler([b for b in dev["_all"] if b[6] not in CONDUCTOR], Y, Z, xm, ok)
    dA = RES * RES
    c = float(np.sum(np.where(ok, EPS0 * er * dA / np.maximum(gap, 1e-6), 0.0)))
    return c, float(np.sum(ok) * dA)

def touch_area(A, B):
    """Shared-face area where two groups abut — used for C_ox and the junction."""
    tot = 0.0
    for a in A:
        for b in B:
            dx = min(a[1], b[1]) - max(a[0], b[0])
            dy = min(a[3], b[3]) - max(a[2], b[2])
            dz = min(a[5], b[5]) - max(a[4], b[4])
            if abs(dx) < 1e-6 and dy > 1e-6 and dz > 1e-6: tot += dy * dz
            if abs(dy) < 1e-6 and dx > 1e-6 and dz > 1e-6: tot += dx * dz
            if abs(dz) < 1e-6 and dx > 1e-6 and dy > 1e-6: tot += dx * dy
    return tot

def volume(bxs):
    return sum((b[1] - b[0]) * (b[3] - b[2]) * (b[5] - b[4]) for b in bxs)

def analyse(dev):
    dev["_all"] = boxes_of(dev, lambda p: True)
    # Selected by id and material rather than by group: the CFET files its source and
    # drain under "Bottom tier (n)" and "Top tier (p)", not under "Source / drain".
    sd = lambda p: "source" in p["id"] or "drain" in p["id"]
    ids = lambda pred: [q["id"] for q in dev["parts"] if pred(q)]
    P_GATE = lambda q: q["material"] in ("mo", "tin") or q["id"] == "gatew"
    P_MET  = lambda q: sd(q) and q["material"] in ("nisi", "nickel", "tungsten")
    P_EPI  = lambda q: sd(q) and q["material"] in ("silicon", "sige")
    P_CH   = lambda q: q["id"].startswith(("sheet", "fin")) and q["material"] == "silicon"
    P_BODY = lambda q: q["id"] == "substrate" or q["id"].endswith("well")
    P_OX   = lambda q: q["material"] == "highk" or (q["material"] == "sio2" and q["id"].startswith("il"))
    gate    = boxes_of(dev, lambda p: p["material"] in ("mo", "tin") or p["id"] == "gatew")
    il      = boxes_of(dev, lambda p: p["material"] == "sio2" and p["id"].startswith("il"))
    hk      = boxes_of(dev, lambda p: p["material"] == "highk")
    chan    = boxes_of(dev, lambda p: p["id"].startswith(("sheet", "fin")) and p["material"] == "silicon")
    body    = boxes_of(dev, lambda p: p["id"] == "substrate" or p["id"].endswith("well"))
    metal   = boxes_of(dev, lambda p: sd(p) and p["material"] in ("nisi", "nickel", "tungsten"))
    epi     = boxes_of(dev, lambda p: sd(p) and p["material"] in ("silicon", "sige"))
    side    = lambda bxs, s: [b for b in bxs if ((b[0] + b[1]) / 2) * s > 0]

    Y, Z = grid(dev)

    out = {}
    for name, target, band in (("C_gc", metal, None),
                               ("C_ge", epi, None)):
        c = a = 0.0
        for s in (-1, +1):
            ci, ai = couple(dev, gate, side(target, s), Y, Z, s, band)
            c += ci; a += ai
        out[name] = (c, a)

    # gate to channel: two conformal films in series, both thicknesses taken from the model
    a_ox = touch_area(chan, il)
    t_il = volume(il) / a_ox if a_ox else 0.0
    a_hk = touch_area(il, hk)
    t_hk = volume(hk) / a_hk if a_hk else 0.0
    cox = EPS0 * a_ox / (t_il / EPS_R["sio2"] + t_hk / EPS_R["highk"]) if a_ox else 0.0
    out["C_ox"] = (cox, a_ox)

    a_j = touch_area(epi + chan, body)
    out["C_j"] = (EPS0 * EPS_R["silicon"] * a_j / W_DEP, a_j)

    lg = max(b[1] for b in il) - min(b[0] for b in il) if il else 1.0
    tin = boxes_of(dev, lambda p: p["material"] == "tin" and p["id"] != "gatecap")
    out["_lg"] = lg
    out["_weff"] = a_ox / lg if lg else 0.0        # gated channel perimeter
    out["_foot"] = (max(b[5] for b in tin) - min(b[4] for b in tin)) if tin else 0.0
    out["_tox"] = (t_il, t_hk)
    out["_ids"] = {"gate": ids(P_GATE), "metal": ids(P_MET), "epi": ids(P_EPI),
                   "chan": ids(P_CH), "body": ids(P_BODY), "ox": ids(P_OX)}
    return out

TERMS = [
    ("C_ox", "C<sub>ox</sub>", "gate", "chan", "ox", "gate → channel",
     "Gate to channel through the interfacial oxide and the high-κ, in series. "
     "The capacitance you want. Everything below is measured against it."),
    ("C_gc", "C<sub>gc</sub>", "gate", "metal", None, "gate → contact",
     "Gate to the source/drain contact metal, across the spacer. The parasitic that "
     "scales worst: gate height, contact height and spacer width set it, and none of "
     "the three shrink with the node."),
    ("C_ge", "C<sub>ge</sub>", "gate", "epi", None, "gate → epi",
     "Gate to the raised source/drain epitaxy, across the spacer. Gate metal that wraps "
     "between the channels faces the epi over area a fin never had. Note the model draws "
     "one uniform spacer thickness everywhere, including between the sheets, so per "
     "nanometre of footprint this lands at much the same value for all four — the "
     "published inner-fringe penalty comes from the inner spacer being thinner and "
     "shaped differently, which is not drawn here."),
    ("C_j", "C<sub>j</sub>", "epi", "body", None, "S/D → body",
     "Source and drain to the body beneath. Large where the epi lands on silicon, and "
     "gone entirely where the device sits on isolation — one of the architecture's "
     "quieter wins."),
]

def attach(dev, r):
    """Write the result onto the scene in the shape the viewers read."""
    w, fp, cox = r["_weff"], r["_foot"], r["C_ox"][0]
    out = []
    for key, sym, a, b, via, pair, desc in TERMS:
        c, area = r[key]
        out.append(dict(
            id=key, sym=sym, pair=pair, desc=desc,
            aF=round(c, 2), area=round(area, 1),
            per_um=round(c / (w / 1000.0), 1) if w else 0.0,
            per_nm=round(c / fp, 3) if fp else 0.0,
            pct=round(c / cox * 100, 1) if cox else 0.0,
            a=r["_ids"][a], b=r["_ids"][b], via=r["_ids"][via] if via else []))
    par = sum(r[k][0] for k in ("C_gc", "C_ge"))
    dev["parasitics"] = dict(
        terms=out, weff=round(w, 1), foot=round(fp, 1), lg=round(r["_lg"], 1),
        wdep=W_DEP, res=RES,
        gate_par=round(par, 2), gate_par_pct=round(par / cox * 100, 1) if cox else 0.0,
        note=("Estimated from this model's own geometry: facing area between two "
              "conductors, the gap between them, and the material in the gap. Parallel "
              "plate only — no field solver. True fringing past the facing overlap, the "
              "inter-layer dielectric (not modelled, so gaps above the spacer count as "
              "vacuum) and the bias dependence of the junction are all outside it, and "
              "C<sub>j</sub> assumes a " + f"{W_DEP:g}" + " nm depletion width. Read the "
              "ratios between architectures, not the absolute femtofarads."))

if __name__ == "__main__":
    path = DATA
    G = json.load(open(path))
    for dev in G["devices"]:
        if dev["key"].startswith(("show_", "inv_")) or dev["key"] == "cmp":
            continue
        r = analyse(dev)
        attach(dev, r)
        w, fp = r["_weff"], r["_foot"]
        print(f"=== {dev['key']:10s} L_G {r['_lg']:.0f} · W_eff {w:.0f} nm · "
              f"footprint {fp:.0f} nm · IL {r['_tox'][0]:.2f} + HfO2 {r['_tox'][1]:.2f} nm")
        print(f"      {'':5s} {'aF':>8s} {'area nm2':>10s} {'aF/um Weff':>11s} {'aF/nm foot':>11s} {'% of Cox':>9s}")
        tot_par = sum(r[k][0] for k in ("C_gc", "C_ge"))
        for k in ("C_ox", "C_gc", "C_ge", "C_j"):
            c, a = r[k]
            print(f"      {k:5s} {c:8.2f} {a:10.0f} {c / (w / 1000.0):11.1f} {c / fp:11.3f}"
                  f" {c / r['C_ox'][0] * 100:8.1f}%")
        print(f"      gate parasitic {tot_par:.2f} aF = {tot_par / r['C_ox'][0] * 100:.0f}% of C_ox"
              f"   ({tot_par / (w / 1000.0):.0f} aF/um, {tot_par / fp:.3f} aF/nm)\n")

    for dev in G["devices"]:
        dev.pop("_all", None)
    json.dump(G, open(path, "w"), separators=(",", ":"))
    n = sum(1 for d in G["devices"] if "parasitics" in d)
    print(f"devices.json {os.path.getsize(path)//1024} KB — parasitics on {n} device scenes")
