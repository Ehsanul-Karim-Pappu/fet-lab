#!/usr/bin/env python3
"""Geometry-only capacitance estimates for the drawn box models.

C_ox is a classical flat-face oxide-stack approximation, not terminal C_gg.
C_gc and C_ge sum direct facing-area couplings along x with dielectric layers
in series. Unfilled gaps have k=1. Fringing and bias-dependent semiconductor
response are not solved. C_j is only a contacted-area depletion proxy at an
assumed width, not an extracted junction capacitance.

Units: epsilon_0 = 8.8541878128e-3 aF/nm; lengths nm; areas nm^2.
Both absolute values AND cross-architecture ratios are assumption-dependent.
"""
import json, math, os, sys
import numpy as np
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
RES  = 0.25                      # y–z raster, nm
EPS0 = 8.8541878128e-3           # aF/nm  (F/m × 1e18 aF/F × 1e-9 m/nm)
W_DEP = 5.0                      # junction depletion width, nm — an assumption, not geometry

# Relative permittivity. Conductors get None and are never used as a gap filler.
EPS_R = {
    "sio2": 3.9, "si3n4": 7.5, "highk": 22.0, "silicon": 11.7, "pts": 11.7, "sige": 13.0,
    "mdi": 4.2, "bond": 3.9, "wall": 7.5,
    "mo": None, "tin": None, "nwf": None, "tungsten": None, "cobalt": None, "tisi": None,
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

def electrical_gap(boxes, Y, Z, lo, hi, valid):
    """Sum thickness/k along x, not just the material at the gap midpoint.

    Boxes must not overlap. Unfilled space has k=1. A conductor crossing the gap
    shields this direct plate-pair term; it is not treated as a dielectric.
    """
    length = np.where(valid, hi - lo, 0.0)
    blocked = np.zeros(Y.shape, dtype=bool)
    for bx in boxes:
        overlap = np.maximum(0.0, np.minimum(hi, bx[1]) - np.maximum(lo, bx[0]))
        overlap = np.where(valid & cover(bx, Y, Z), overlap, 0.0)
        k = EPS_R[bx[6]]
        if k is None:
            blocked |= overlap > 1e-6
        else:
            length += overlap * (1.0 / k - 1.0)
    return length, valid & ~blocked & (length > 1e-9)

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
    lo = np.where(ok, bX if sign < 0 else -aX, 0.0)
    hi = np.where(ok, aX if sign < 0 else -bX, 0.0)
    length, ok = electrical_gap(dev["_all"], Y, Z, lo, hi, ok)
    dA = RES * RES
    c = float(np.sum(np.where(ok, EPS0 * dA / np.maximum(length, 1e-9), 0.0)))
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

def film_thickness(bxs):
    """Actual normal thickness of the uniform axis-aligned plates used by the builders.

    Volume/interface-area includes corner volume and overestimates thickness.
    Reject nonuniform films rather than silently applying a single-thickness model.
    """
    values = {round(min(b[3] - b[2], b[5] - b[4]), 6) for b in bxs}
    if len(values) != 1 or min(values) <= 0:
        raise ValueError("Expected a nonempty uniform rectangular film")
    return values.pop()

def analyse(dev):
    dev["_all"] = boxes_of(dev, lambda p: True)
    # Selected by id and material rather than by group: the CFET files its source and
    # drain under "Bottom tier (n)" and "Top tier (p)", not under "Source / drain".
    sd = lambda p: "source" in p["id"] or "drain" in p["id"]
    ids = lambda pred: [q["id"] for q in dev["parts"] if pred(q)]
    P_GATE = lambda q: q["material"] in ("mo", "tin", "nwf") or q["id"] == "gatew"
    P_MET  = lambda q: sd(q) and q["material"] in ("tisi", "cobalt", "tungsten")
    P_EPI  = lambda q: sd(q) and q["material"] in ("silicon", "sige")
    P_CH   = lambda q: q["id"].startswith(("sheet", "fin")) and q["material"] == "silicon"
    P_BODY = lambda q: q["id"] == "substrate" or q["id"].endswith("well")
    P_OX   = lambda q: q["material"] == "highk" or (q["material"] == "sio2" and q["id"].startswith("il"))
    gate    = boxes_of(dev, lambda p: p["material"] in ("mo", "tin", "nwf") or p["id"] == "gatew")
    il      = boxes_of(dev, lambda p: p["material"] == "sio2" and p["id"].startswith("il"))
    hk      = boxes_of(dev, lambda p: p["material"] == "highk")
    chan    = boxes_of(dev, lambda p: p["id"].startswith(("sheet", "fin")) and p["material"] == "silicon")
    body    = boxes_of(dev, lambda p: p["id"] == "substrate" or p["id"].endswith("well"))
    metal   = boxes_of(dev, lambda p: sd(p) and p["material"] in ("tisi", "cobalt", "tungsten"))
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
    t_il = film_thickness(il)
    t_hk = film_thickness(hk)
    cox = EPS0 * a_ox / (t_il / EPS_R["sio2"] + t_hk / EPS_R["highk"]) if a_ox else 0.0
    out["C_ox"] = (cox, a_ox)

    # Channel/body interface is NOT a source/drain junction. No sidewall or
    # depletion-profile inference is possible without doping and bias data.
    a_j = touch_area(epi, body)
    out["C_j"] = (EPS0 * EPS_R["silicon"] * a_j / W_DEP, a_j)

    lg = max(b[1] for b in il) - min(b[0] for b in il) if il else 1.0
    tin = boxes_of(dev, lambda p: p["material"] in ("tin", "nwf") and p["id"] != "gatecap")
    out["_lg"] = lg
    out["_weff"] = a_ox / lg if lg else 0.0        # gated channel perimeter
    out["_foot"] = (max(b[5] for b in tin) - min(b[4] for b in tin)) if tin else 0.0
    out["_tox"] = (t_il, t_hk)
    out["_ids"] = {"gate": ids(P_GATE), "metal": ids(P_MET), "epi": ids(P_EPI),
                   "chan": ids(P_CH), "body": ids(P_BODY), "ox": ids(P_OX)}
    return out

TERMS = [
    [
        "C_ox",
        "C<sub>ox</sub>",
        "gate",
        "chan",
        "ox",
        "oxide stack → channel",
        "Classical oxide-stack estimate from gated area and the actual SiO2/HfO2 film thicknesses in series. Not the bias-dependent terminal gate capacitance: depletion, quantum capacitance and corner fields are omitted."
    ],
    [
        "C_gc",
        "C<sub>gc</sub>",
        "gate",
        "metal",
        None,
        "gate → S/D contact",
        "Direct facing-area coupling to source/drain contact conductors along x, summed over both ends. Materials crossed by each ray are combined in series; empty gaps have relative permittivity 1. This is not a 3D fringe-field extraction."
    ],
    [
        "C_ge",
        "C<sub>ge</sub>",
        "gate",
        "epi",
        None,
        "gate → S/D epitaxy",
        "Facing-area estimate treating source/drain epitaxy as equipotential. Uniform spacers, missing ILD and omitted fringe fields limit comparison with real devices. Semiconductor doping and bias are not modeled."
    ],
    [
        "C_j",
        "C<sub>j</sub>*",
        "epi",
        "body",
        None,
        "S/D → body proxy",
        "Junction-contribution proxy: epsilon(Si) times the drawn S/D-to-body contact area divided by an assumed 5nm depletion width. It counts only a direct S/D-to-substrate junction; channel-to-body area is excluded. Zero means no such junction is drawn (for example under full bottom dielectric isolation). That does not imply zero total parasitic capacitance: S/D-to-substrate coupling through dielectric and fringe fields remains, and is not estimated here."
    ]
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
        method="classical plates; no field solver",
        note=("Geometry-only estimates, not measured or TCAD-extracted values. "
              "W_eff is the total gated perimeter represented in THIS scene "
              "(both polarities in forksheet/CFET); normalization is not an equal-drive comparison. "
              "The gate-stack span is not a cell area or necessarily the footprint in Compare. "
              "C_ox uses planar series films; C_gc/C_ge integrate thickness/k along x. "
              "Missing inter-layer dielectric is treated as vacuum (k=1); "
              "3D fringe fields, quantum effects and bias-dependent semiconductor response are omitted. "
              "C_j* uses only drawn S/D-body contact area with an assumed "
              + f"{W_DEP:g}nm" + " depletion width and silicon permittivity. "
              "Real doping, SiGe composition and depletion widths are unspecified. "
              "Both numerical values and architecture ratios depend on these assumptions."))


if __name__ == "__main__":
    path = Path(HERE).parent / "data/devices.json"
    G = json.load(open(path))
    for dev in G["devices"]:
        if dev["key"].startswith(("show_", "inv_")) or dev["key"] == "cmp":
            continue
        r = analyse(dev)
        attach(dev, r)
        w, fp = r["_weff"], r["_foot"]
        print(f"=== {dev['key']:10s} L_G {r['_lg']:.0f} · W_eff {w:.0f} nm · "
              f"gate-stack span {fp:.0f} nm · IL {r['_tox'][0]:.2f} + HfO2 {r['_tox'][1]:.2f} nm")
        print(f"      {'':5s} {'aF':>8s} {'area nm2':>10s} {'aF/um Weff':>11s} {'aF/nm span':>11s} {'% of Cox':>9s}")
        tot_par = sum(r[k][0] for k in ("C_gc", "C_ge"))
        for k in ("C_ox", "C_gc", "C_ge", "C_j"):
            c, a = r[k]
            print(f"      {k:5s} {c:8.2f} {a:10.0f} {c / (w / 1000.0):11.1f} {c / fp:11.3f}"
                  f" {c / r['C_ox'][0] * 100:8.1f}%")
        print(f"      gate parasitic {tot_par:.2f} aF = {tot_par / r['C_ox'][0] * 100:.0f}% of C_ox"
              f"   ({tot_par / (w / 1000.0):.0f} aF/um, {tot_par / fp:.3f} aF/nm)\n")

    for dev in G["devices"]:
        dev.pop("_all", None)
        # Camera values come out of trigonometry, whose last digit can differ between
        # machines; rounded, a rebuild anywhere writes the same bytes.
        for v in dev["views"].values():
            for k in ("az", "el", "r"):
                v[k] = round(v[k], 4)
            v["tgt"] = [round(t, 4) for t in v["tgt"]]
    json.dump(G, open(path, "w"), separators=(",", ":"))
    n = sum(1 for d in G["devices"] if "parasitics" in d)
    print(f"devices.json {os.path.getsize(path)//1024} KB — parasitics on {n} device scenes")
