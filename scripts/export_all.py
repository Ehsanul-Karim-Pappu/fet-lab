import json, os, numpy as np, trimesh
from trimesh.visual.material import PBRMaterial
G=json.load(open("devices.json")); MAT=G["materials"]
OUT="/mnt/user-data/outputs/models"; os.makedirs(OUT,exist_ok=True)
h2=lambda h:[int(h.lstrip('#')[i:i+2],16) for i in (0,2,4)]
METAL={"mo","nickel","tungsten","nisi","tin"}
def pm(p):
    ms=[]
    for cx,cy,cz,dx,dy,dz in p["boxes"]:
        b=trimesh.creation.box(extents=(dx,dy,dz)); b.apply_translation((cx,cy,cz)); ms.append(b)
    m=trimesh.util.concatenate(ms); m.merge_vertices(); return m
for dev in G["devices"]:
    k=dev["key"]; sc=trimesh.Scene()
    for p in dev["parts"]:
        m=pm(p); r,g,b=h2(MAT[p["material"]]["color"]); mt=p["material"] in METAL
        m.visual=trimesh.visual.TextureVisuals(material=PBRMaterial(
            name=MAT[p["material"]]["label"],baseColorFactor=[r,g,b,255],
            metallicFactor=0.9 if mt else 0.05, roughnessFactor=0.35 if mt else 0.55))
        sc.add_geometry(m,node_name=p["id"],geom_name=f'{p["id"]}__{p["material"]}')
    sc.export(f"{OUT}/{k}.glb")
    trimesh.util.concatenate([pm(p) for p in dev["parts"]]).export(f"{OUT}/{k}.stl")
    obj=[f'# {dev["name"]} — 1 unit = 1 nm','mtllib materials.mtl']; vo=1
    for p in dev["parts"]:
        obj += [f'g {p["id"]}', f'usemtl {p["material"]}']
        for cx,cy,cz,dx,dy,dz in p["boxes"]:
            x0,x1=cx-dx/2,cx+dx/2; y0,y1=cy-dy/2,cy+dy/2; z0,z1=cz-dz/2,cz+dz/2
            for v in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                      (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]:
                obj.append("v %.4f %.4f %.4f"%v)
            for q in [(1,2,3,4),(5,8,7,6),(1,5,6,2),(2,6,7,3),(3,7,8,4),(4,8,5,1)]:
                obj.append("f "+" ".join(str(vo+i-1) for i in q))
            vo+=8
    open(f"{OUT}/{k}.obj","w").write("\n".join(obj)+"\n")
mtl=[]
for key in G["order"]:
    r,g,b=[c/255 for c in h2(MAT[key]["color"])]; mt=key in METAL
    mtl+=[f"newmtl {key}",f"Kd {r:.4f} {g:.4f} {b:.4f}",f"Ka {r*.25:.4f} {g*.25:.4f} {b*.25:.4f}",
          "Ks 0.55 0.55 0.55" if mt else "Ks 0.12 0.12 0.12",f"Ns {90 if mt else 20}","d 1.0","illum 2",""]
open(f"{OUT}/materials.mtl","w").write("\n".join(mtl)+"\n")
for f in sorted(os.listdir(OUT)): print(f"  {f:22s}{os.path.getsize(OUT+'/'+f)/1024:8.1f} KB")
