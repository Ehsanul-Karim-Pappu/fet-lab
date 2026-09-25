"""Analytic, units, selection and grid-convergence checks; not physical validation."""
import copy
import json
import unittest
from pathlib import Path
import numpy as np
import build_parasitics as p

DATA = Path(__file__).resolve().parent.parent / "data/devices.json"

class CapacitanceTests(unittest.TestCase):
    def test_units_and_series_dielectrics(self):
        self.assertAlmostEqual(p.EPS0, 8.8541878128e-12 * 1e-9 * 1e18)
        y = np.array([[.5]]); z = y.copy(); valid = np.array([[True]])
        # 1nm SiO2 + 2nm HfO2: actual EOT 1 + 2*3.9/22, not rounded display EOT.
        boxes = [(0,1,0,1,0,1,"sio2"), (1,3,0,1,0,1,"highk")]
        length, ok = p.electrical_gap(boxes,y,z,np.zeros((1,1)),np.full((1,1),3),valid)
        self.assertTrue(ok[0,0]); self.assertAlmostEqual(length[0,0],1/3.9+2/22)
        self.assertAlmostEqual(p.film_thickness([(0,15,0,1,0,32,"sio2")]),1)

    def test_vacuum_and_shielding(self):
        y=np.array([[.5]]); lo=np.zeros((1,1)); hi=np.ones((1,1))*4; ok=np.ones((1,1),dtype=bool)
        length, valid=p.electrical_gap([],y,y,lo,hi,ok)
        self.assertTrue(valid[0,0]); self.assertEqual(length[0,0],4)
        _,valid=p.electrical_gap([(1,2,0,1,0,1,"mo")],y,y,lo,hi,ok)
        self.assertFalse(valid[0,0])

    def test_parallel_plate_and_mirror(self):
        # One grid cell of area 0.0625nm^2; 7nm Si3N4 gap. Check both x directions.
        y=np.array([[.5]]); a=(0,1,0,1,0,1,"mo"); b=(8,9,0,1,0,1,"cobalt")
        d={"_all":[a,b,(1,8,0,1,0,1,"si3n4")]}
        c,area=p.couple(d,[a],[b],y,y,1)
        self.assertAlmostEqual(c,p.EPS0*7.5*area/7)
        reverse=lambda q:(-q[1],-q[0],*q[2:])
        m={"_all":[reverse(q) for q in d["_all"]]}
        c2,_=p.couple(m,[reverse(a)],[reverse(b)],y,y,-1)
        self.assertAlmostEqual(c,c2)

    def test_shipped_geometry(self):
        data=json.loads(DATA.read_text())
        scenes=[d for d in data["devices"] if d["key"] in ("fin","ns","fs","cfet_mono","cfet_seq")]
        # Independently derive total gated perimeter from the authored channel dimensions.
        widths={"fin":2*(2*45+6),"ns":3*(2*30+2*5),"fs":2*3*(2*22+5),"cfet_mono":2*2*(2*20+2*5),"cfet_seq":2*2*(2*20+2*5)}
        original=p.RES
        try:
            for scene in scenes:
                results=[]
                for resolution in (.5,.25,.125):
                    p.RES=resolution
                    results.append(p.analyse(copy.deepcopy(scene)))
                r=results[1]; key=scene["key"]; lg=18 if key=="fin" else 15
                self.assertAlmostEqual(r["_weff"],widths[key])
                self.assertAlmostEqual(r["C_ox"][0],p.EPS0*widths[key]*lg/(1/3.9+2/22))
                self.assertEqual(r["_tox"],(1,2))
                for term in ("C_ox","C_gc","C_ge","C_j"):
                    self.assertTrue(np.isfinite(r[term][0])); self.assertGreaterEqual(r[term][0],0)
                    for candidate in (results[0],results[2]):
                        self.assertLessEqual(abs(candidate[term][0]-r[term][0]),max(.001,r[term][0]*.03), (key,term))
                epi=p.boxes_of(scene,lambda q:("source" in q["id"] or "drain" in q["id"]) and q["material"] in ("silicon","sige"))
                body=p.boxes_of(scene,lambda q:q["id"]=="substrate" or q["id"].endswith("well"))
                self.assertAlmostEqual(r["C_j"][1],p.touch_area(epi,body))
                if key.startswith("cfet"): self.assertEqual(r["C_j"][0],0)
                p.attach(scene,r)
                for row in scene["parasitics"]["terms"]:
                    self.assertAlmostEqual(row["aF"],round(r[row["id"]][0],2))
                    self.assertAlmostEqual(row["per_um"],round(r[row["id"]][0]/(widths[key]/1000),1))
        finally:
            p.RES=original

if __name__ == "__main__": unittest.main()
