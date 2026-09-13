import numpy as np
def overlaps(d, step=0.5, limit=8):
    B=d.bounds; out=[]
    gx=np.arange(B["x"][0],B["x"][1],step); gy=np.arange(B["y"][0],B["y"][1],step); gz=np.arange(B["z"][0],B["z"][1],step)
    occ=np.zeros((len(gx),len(gy),len(gz)),np.int16)-1
    for pi,p in enumerate(d.parts):
        for cx,cy,cz,dx,dy,dz in p["boxes"]:
            ix=(gx>cx-dx/2)&(gx<cx+dx/2); iy=(gy>cy-dy/2)&(gy<cy+dy/2); iz=(gz>cz-dz/2)&(gz<cz+dz/2)
            sl=np.ix_(ix,iy,iz); prev=occ[sl]
            hit=prev>=0
            if hit.any():
                for other in np.unique(prev[hit]):
                    pair=(d.parts[int(other)]["id"], p["id"], int(hit.sum()))
                    if pair[:2] not in [o[:2] for o in out]: out.append(pair)
                    if len(out)>=limit: return out
            occ[sl]=pi
    return out
