"""Check the shipped feature catalog and synchronized assets without extra dependencies."""
import json
import re
import unittest
from paths import ROOT, DATA


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = json.loads((ROOT / "data/guide.json").read_text())
        cls.data = json.loads(DATA.read_text())

    def test_catalog_destinations(self):
        scenes = {d["key"]: d for d in self.data["devices"]}
        features = {f["id"]: f for f in self.guide["features"]}
        self.assertGreater(self.guide["version"], 0)
        self.assertEqual(len(features), len(self.guide["features"]))
        self.assertGreater(len(self.guide["tour"]), 0)
        self.assertEqual(len(self.guide["tour"]), len(set(self.guide["tour"])))
        for step in self.guide["tour"]:
            self.assertIn(step, features)
        for feature in features.values():
            scene = scenes[feature["scene"]]
            self.assertIn(feature["view"], scene["views"])
            self.assertIn(feature["tab"], ["views", "section", "layers", "specs", "story"])
            if feature["target"] == "logic": self.assertTrue(scene["logic"])
            if feature["target"] == "parasitics": self.assertTrue(scene["parasitics"]["terms"])

    def test_android_assets_match(self):
        for name in ("guide.json", "devices.json"):
            self.assertEqual((ROOT / "data" / name).read_bytes(),
                             (ROOT / "android/app/src/main/assets" / name).read_bytes())

    def test_browser_bundles_match(self):
        for path in ("web/finfet-to-cfet.html", "pwa/index.html"):
            html = (ROOT / path).read_text()
            for key, expected in (("DATA", self.data), ("GUIDE", self.guide)):
                match = re.search(r"const " + key + r" = (.*);", html)
                self.assertIsNotNone(match)
                self.assertEqual(json.loads(match[1].replace(r"\/", "/")), expected)
            for marker in ("/*__DATA__*/", "/*__GUIDE__*/", "/*__EXPLORER_CSS__*/", "/*__EXPLORER_JS__*/"):
                self.assertNotIn(marker, html)
            self.assertIn((ROOT / "scripts/explorer.js").read_text(), html)
            self.assertIn((ROOT / "scripts/explorer.css").read_text(), html)


if __name__ == "__main__":
    unittest.main()
