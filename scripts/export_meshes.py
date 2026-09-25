import json, os, os, numpy as np, trimesh
from trimesh.visual.material import PBRMaterial

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, "geometry.json")))
MAT, OUT = G["materials"], "/mnt/user-data/outputs"
os.makedirs(OUT, exist_ok=True)

def hex2rgb(h):
    h = h.lstrip("#"); return [int(h[i:i+2],16) for i in (0,2,4)]

def part_mesh(p):
    ms = []
    for cx,cy,cz,dx,dy,dz in p["boxes"]:
        b = trimesh.creation.box(extents=(dx,dy,dz))
        b.apply_translation((cx,cy,cz)); ms.append(b)
    m = trimesh.util.concatenate(ms)
    m.merge_vertices(); return m

# ---- GLB: one node per part, PBR colour per material -----------------------
scene = trimesh.Scene()
for p in G["parts"]:
    m = part_mesh(p)
    r,g,b = hex2rgb(MAT[p["material"]]["color"])
    metal = 0.9 if p["material"] in ("mo","cobalt","tungsten","tisi","tin","nwf") else 0.05
    rough = 0.35 if metal > 0.5 else 0.55
    m.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(
        name=MAT[p["material"]]["label"], baseColorFactor=[r,g,b,255],
        metallicFactor=metal, roughnessFactor=rough))
    scene.add_geometry(m, node_name=p["id"], geom_name=f'{p["id"]}__{p["material"]}')
scene.export(f"{OUT}/nanosheet_fet.glb")

# ---- STL: single watertight-ish solid --------------------------------------
allm = trimesh.util.concatenate([part_mesh(p) for p in G["parts"]])
allm.export(f"{OUT}/nanosheet_fet.stl")

# ---- OBJ + MTL: grouped by material, colours preserved ---------------------
obj, mtl, vo = ["# 3-stacked gate-all-around nanosheet FET  (1 unit = 1 nm)",
                "mtllib nanosheet_fet.mtl"], [], 1
for key in G["order"]:
    r,g,b = [c/255 for c in hex2rgb(MAT[key]["color"])]
    metal = key in ("mo","cobalt","tungsten","tisi","tin","nwf")
    mtl += [f"newmtl {key}", f"Kd {r:.4f} {g:.4f} {b:.4f}",
            f"Ka {r*0.25:.4f} {g*0.25:.4f} {b*0.25:.4f}",
            "Ks 0.55 0.55 0.55" if metal else "Ks 0.12 0.12 0.12",
            f"Ns {90 if metal else 20}", "d 1.0", "illum 2", ""]
for p in G["parts"]:
    obj.append(f'g {p["id"]}'); obj.append(f'usemtl {p["material"]}')
    for cx,cy,cz,dx,dy,dz in p["boxes"]:
        x0,x1 = cx-dx/2, cx+dx/2; y0,y1 = cy-dy/2, cy+dy/2; z0,z1 = cz-dz/2, cz+dz/2
        for v in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                  (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]:
            obj.append("v %.4f %.4f %.4f" % v)
        f = [(1,2,3,4),(5,8,7,6),(1,5,6,2),(2,6,7,3),(3,7,8,4),(4,8,5,1)]
        for q in f: obj.append("f " + " ".join(str(vo+i-1) for i in q))
        vo += 8
open(f"{OUT}/nanosheet_fet.obj","w").write("\n".join(obj)+"\n")
open(f"{OUT}/nanosheet_fet.mtl","w").write("\n".join(mtl)+"\n")

for f in ("nanosheet_fet.glb","nanosheet_fet.stl","nanosheet_fet.obj","nanosheet_fet.mtl"):
    print(f"{f:24s} {os.path.getsize(OUT+'/'+f)/1024:8.1f} KB")
chk = trimesh.load(f"{OUT}/nanosheet_fet.glb")
print("GLB reload:", len(chk.geometry), "geometries, bounds", np.round(chk.bounds,1).tolist())
