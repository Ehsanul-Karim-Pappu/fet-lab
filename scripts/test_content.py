"""Regression checks for generated content, references and model caveats."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class ContentTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'data/devices.json').read_text())
        self.refs = json.loads((ROOT / 'data/references.json').read_text())

    def test_bundles_match(self):
        for name in ('devices.json', 'guide.json', 'references.json', 'process.json'):
            self.assertEqual((ROOT / 'data' / name).read_bytes(),
                             (ROOT / 'android/app/src/main/assets' / name).read_bytes())
        for file in ('web/finfet-to-cfet.html', 'pwa/index.html'):
            html = (ROOT / file).read_text()
            payload = re.search(r'^const DATA = (.*);$', html, re.M)
            self.assertIsNotNone(payload)
            self.assertEqual(json.loads(payload[1]), self.data)
            for ref in self.refs['sources']:
                self.assertIn('id="ref-' + ref['id'] + '"', html)
                self.assertIn(ref['url'], html)
        legacy = (ROOT / 'web/nanosheet-only.html').read_text()
        payload = re.search(r'^const GEO = (.*);$', legacy, re.M)
        self.assertEqual(json.loads(payload[1]), json.loads((ROOT / 'data/geometry.json').read_text()))
        self.assertNotIn('(a) Isometric', legacy)
        self.assertIn('GEO.order.map', legacy)

    def test_process_flows(self):
        """Every flow step resolves: its parts, its view and every reference it cites; the
        last step is the finished device. (Tiling is checked when the flows are built.)"""
        proc = json.loads((ROOT / 'data/process.json').read_text())
        ids = {r['id'] for r in self.refs['sources']}
        devs = {d['key']: d for d in self.data['devices']}
        self.assertTrue(proc['flows'])
        for key, flow in proc['flows'].items():
            dev = devs[key]
            final = {p['id'] for p in dev['parts']}
            views = {**dev['views'], **flow.get('views', {})}
            self.assertTrue(flow['scope'])
            cited = set()
            labels = [step['label'] for step in flow['steps']]
            self.assertEqual(len(labels), len(set(labels)))
            for n, step in enumerate(flow['steps']):
                self.assertTrue(step['title'] and step['body'])
                self.assertIn(step['view'], views)
                # A step's view frames its own scale; a tile step brings its own bounds.
                self.assertEqual(views[step['view']].get('scale', 'site'), step['scale'])
                self.assertEqual('bounds' in step, step['scale'] != 'site')
                if step['level'] == 'op':
                    nxt = next(s for s in flow['steps'][n + 1:] if s['level'] == 'core')
                    self.assertEqual(step['of'], nxt['id'])
                    self.assertTrue(step['label'].startswith(nxt['label'] + '.'))
                for part in step['parts']:
                    if isinstance(part, str):
                        self.assertIn(part, final)
                    else:
                        self.assertNotIn(part['id'], final)
                        self.assertIn(part['material'], self.data['materials'])
                cited |= set(re.findall(r'\bR\d+\b', step['body']))
            self.assertLessEqual(cited, set(flow.get('refs', [])))
            self.assertLessEqual(set(flow.get('refs', [])), ids)
            self.assertEqual(sorted(flow['steps'][-1]['parts']), sorted(final))

    def test_process_source_labels(self):
        """Every state says how it relates to its source, never claims a drawing match, and
        never maps to a figure the flow says it skips (the patent's pFET-only steps)."""
        proc = json.loads((ROOT / 'data/process.json').read_text())
        audit = (ROOT / 'docs/PROCESS_AUDIT.md').read_text()
        for key, flow in proc['flows'].items():
            self.assertIn('not available for visual comparison', flow['figures'])
            self.assertTrue(flow['branch'])
            skipped = set(flow['skipped'])
            for step in flow['steps']:
                self.assertIn(step['match'], flow['match'])
                if step['match'] != 'concept':
                    self.assertTrue(step['figs'], step['id'])
                self.assertFalse(skipped & set(step['figs']), step['id'])
                for text in [step['body']] + step['subs'] + step['omitted']:
                    self.assertNotRegex(text.lower(), r'exact (match|reconstruction)|as in fig')
                self.assertIn('| ' + step['title'] + ' |', audit)
            for fig in skipped:
                self.assertIn('Fig. ' + fig, audit)

    def test_references_and_scope(self):
        ids = [r['id'] for r in self.refs['sources']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 21)
        for ref in self.refs['sources']:
            self.assertTrue(ref['url'].startswith('https://'))
            self.assertTrue(ref['supports'])
        for scene in self.data['devices']:
            used = set(re.findall(r'\bR\d+\b', scene['story'] + scene['note']))
            self.assertTrue(used <= set(ids), (scene['key'], used))
            self.assertIn('not a foundry process', scene['story'])
            self.assertIn('architecture ratios depend', scene['story'])
            self.assertNotIn('Rathore', scene['story'])

    def test_scene_names_and_capacitance_scope(self):
        self.assertEqual(len(self.data['devices']), 16)
        count = 0
        for scene in self.data['devices']:
            if 'cmp' not in scene['key']:
                self.assertEqual(next(iter(scene['views'].values()))['n'], '3D overview')
            for view in scene['views'].values():
                self.assertNotRegex(view['n'], r'^\([a-z]\)')
            for row in scene['dims']:
                self.assertNotEqual(row[0], 'Node')
            if 'parasitics' in scene:
                count += 1
                cap = scene['parasitics']
                self.assertIn('not measured or TCAD', cap['note'])
                self.assertIn('not an equal-drive', cap['note'])
                self.assertEqual(cap['method'], 'classical plates; no field solver')
                ids = {part['id'] for part in scene['parts']}
                for term in cap['terms']:
                    self.assertTrue(set(term['a'] + term['b'] + term['via']) <= ids)
        self.assertEqual(count, 5)

if __name__ == '__main__':
    unittest.main()
