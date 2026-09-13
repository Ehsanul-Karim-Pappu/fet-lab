"""
Audit every scene in devices.json.

Catches the things a render will not: a callout pointing at a part that does not
exist, a view preset hiding an id that was renamed, a clip plane outside the model,
a material with no entry in the palette, geometry that overlaps, and a dimensions
table that disagrees with the geometry it describes.

    python scripts/verify.py          # report
    python scripts/verify.py -q       # exit status only
"""
import json, sys, math
from collections import defaultdict

G = json.load(open("devices.json"))
MAT = G["materials"]
PROBLEMS, NOTES = [], []

def bad(scene, msg):  PROBLEMS.append(f"{scene:11s} {msg}")
def note(scene, msg): NOTES.append(f"{scene:11s} {msg}")

def extent(boxes, axis):
    lo = min(b[axis] - b[axis + 3] / 2 for b in boxes)
    hi = max(b[axis] + b[axis + 3] / 2 for b in boxes)
    return lo, hi

def span(boxes, axis):
    lo, hi = extent(boxes, axis); return hi - lo

# ---------------------------------------------------------------- structure
for d in G["devices"]:
    k = d["key"]
    ids = [p["id"] for p in d["parts"]]
    byid = {p["id"]: p for p in d["parts"]}
    dup = {i for i in ids if ids.count(i) > 1}
    if dup: bad(k, f"duplicate part ids: {sorted(dup)}")
    if not d["parts"]: bad(k, "no parts")

    for p in d["parts"]:
        if p["material"] not in MAT:
            bad(k, f"part {p['id']} uses material '{p['material']}' which is not in the palette")
        if not p["boxes"]:
            bad(k, f"part {p['id']} has no boxes")
        for b in p["boxes"]:
            if len(b) != 6: bad(k, f"part {p['id']} has a malformed box {b}")
            elif min(b[3], b[4], b[5]) <= 0:
                bad(k, f"part {p['id']} has a box with a non-positive dimension {b}")

    # callouts must point at parts that exist
    for c in d.get("callouts", []):
        pid = c.get("pid")
        if pid is None: continue
        for one in (pid if isinstance(pid, list) else [pid]):
            if one not in byid:
                bad(k, f"callout '{c['label']}' points at missing part '{one}'")
        if c.get("lead") and not pid:
            bad(k, f"callout '{c['label']}' asks for a surface name but names no part")

    # view presets
    if not d.get("views"): bad(k, "no view presets")
    B = d["bounds"]
    for vk, v in d.get("views", {}).items():
        for oid in v.get("off", []) or []:
            if oid not in byid:
                bad(k, f"view '{vk}' hides missing part '{oid}'")
        cl = v.get("clip")
        if cl:
            for ax, name in enumerate("xyz"):
                if cl[ax] is None: continue
                lo, hi = B[name]
                if not (lo < cl[ax] < hi):
                    bad(k, f"view '{vk}' clips {name} at {cl[ax]}, outside the model ({lo}…{hi})")
        if v.get("r", 0) <= 0: bad(k, f"view '{vk}' has a non-positive camera distance")

    # bounds must match the geometry
    allb = [b for p in d["parts"] for b in p["boxes"]]
    for ax, name in enumerate("xyz"):
        lo, hi = extent(allb, ax)
        if abs(lo - B[name][0]) > 0.01 or abs(hi - B[name][1]) > 0.01:
            bad(k, f"declared {name} bounds {B[name]} but the geometry spans [{lo}, {hi}]")

    # groups
    groups = {p["group"] for p in d["parts"]}
    for g in d.get("groups", []):
        if g not in groups: bad(k, f"layer group '{g}' has no parts")

# ------------------------------------------------------- declared dimensions
def find(d, pid):
    for p in d["parts"]:
        if p["id"] == pid: return p
    return None

def dimval(d, sym):
    for row in d.get("dims", []):
        if row[0] == sym: return row[2]
    return None

def num(s):
    if s is None: return None
    t = "".join(ch for ch in str(s).split()[0] if ch in "0123456789.-")
    try: return float(t)
    except ValueError: return None

for d in G["devices"]:
    k = d["key"]
    # gate length: the x span of the gate body, wherever one is named
    gate = find(d, "po") or find(d, "gate") or find(d, "mo")
    lg = num(dimval(d, "L_G")) or num(dimval(d, "LG"))
    if gate and lg:
        got = span(gate["boxes"], 0)
        if abs(got - lg) > 0.51:
            bad(k, f"L_G says {lg} nm but the gate body is {got:g} nm along the channel")
    # sheet / fin count
    for sym, prefix in (("Sheets", "sheet"), ("Nanowires", "w"), ("Fins", "f")):
        want = num(dimval(d, sym))
        if want is None: continue
        have = len([p for p in d["parts"]
                    if p["group"].lower().startswith("channel") and "stub" not in p["name"]])
        if have and abs(have - want) > 0.5 and "cfet" not in k:
            note(k, f"'{sym}' says {want:g} but {have} channel bodies are drawn")

# ------------------------------------------------------------------ overlaps
def inter(a, b, eps=0.02):
    """Overlap volume of two boxes, ignoring faces that merely touch."""
    v = 1.0
    for i in range(3):
        alo, ahi = a[i] - a[i + 3] / 2, a[i] + a[i + 3] / 2
        blo, bhi = b[i] - b[i + 3] / 2, b[i] + b[i + 3] / 2
        d = min(ahi, bhi) - max(alo, blo) - eps
        if d <= 0: return 0.0
        v *= d
    return v

for d in G["devices"]:
    flat = [(p["id"], b) for p in d["parts"] for b in p["boxes"]]
    seen, worst = set(), []
    for i in range(len(flat)):
        ida, ba = flat[i]
        for j in range(i + 1, len(flat)):
            idb, bb = flat[j]
            if ida == idb: continue
            v = inter(ba, bb)
            if v > 0.5:
                key = tuple(sorted((ida, idb)))
                if key not in seen:
                    seen.add(key); worst.append((key, v))
    for (a, b), v in sorted(worst, key=lambda kv: -kv[1])[:4]:
        bad(d["key"], f"'{a}' and '{b}' overlap by {v:.0f} nm\u00b3")

# every scene should carry its written background
for d in G["devices"]:
    if not d.get("story", "").strip():
        bad(d["key"], "no background text attached (run build_story.py last)")

# --------------------------------------------------------------------- report
q = "-q" in sys.argv
if not q:
    fam = defaultdict(list)
    for d in G["devices"]:
        fam["inverter" if d["key"].startswith("inv_") else
            "layout"   if d["key"].startswith("show_") else "device"].append(d["key"])
    print(f"{len(G['devices'])} scenes: " + " · ".join(f"{k} {len(v)}" for k, v in fam.items()))
    for line in PROBLEMS: print("  FAIL  " + line)
    for line in NOTES:    print("  note  " + line)
    if not PROBLEMS: print("  no structural problems found")
sys.exit(1 if PROBLEMS else 0)
