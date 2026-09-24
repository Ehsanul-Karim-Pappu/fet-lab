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
            # A lesson (the SADP and SAQP chips) has no finished device behind it.
            lesson = flow.get('lesson', False)
            dev = dict(parts=[], views={}) if lesson else devs[key]
            final = {p['id'] for p in dev['parts']}
            views = {**dev['views'], **flow.get('views', {})}
            self.assertTrue(flow['scope'])
            cited = set()
            # Routes are alternatives: along each one the labels are unique.
            routes = [r['id'] for r in flow.get('routes', [])] or [None]
            self.assertEqual(set(routes) - {None}, {s['route'] for s in flow['steps'] if 'route' in s})
            for r in routes:
                seq = [s.get('labels', {}).get(r, s['label']) for s in flow['steps'] if s.get('route') in (None, r)]
                self.assertEqual(len(seq), len(set(seq)), r)
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
            if not lesson:
                self.assertEqual(sorted(flow['steps'][-1]['parts']), sorted(final))

    def test_lessons_are_the_routes(self):
        """The SADP and SAQP chips show the nanosheet flow's route of that name, state for
        state, then its stack etch."""
        flows = json.loads((ROOT / 'data/process.json').read_text())['flows']
        ns = flows['ns']
        lessons = {k: f for k, f in flows.items() if f.get('lesson')}
        self.assertEqual(set(lessons), {'sadp', 'saqp'})
        for key, flow in lessons.items():
            want = [s for s in ns['steps'] if s.get('route') == key] + \
                   [s for s in ns['steps'] if s['id'] == 'stacketch']
            self.assertEqual([s['id'] for s in flow['steps']], [s['id'] for s in want])
            for a, b in zip(flow['steps'], want):
                self.assertEqual((a['parts'], a['body'], a['view'], a['match']),
                                 (b['parts'], b['body'], b['view'], b['match']))
                self.assertEqual(a['level'], 'core')
            self.assertEqual([s['label'] for s in flow['steps']],
                             [str(k) for k in range(1, len(want) + 1)])
            self.assertIn('patterning concept applied to an illustrative layer', flow['scope'].lower())

    def test_patterning_routes(self):
        """Each route is one run of operations of the same core step, and every route ends in
        the state the first (the direct print) ends in, so the shared step after them follows
        any of them. SAQP shows its second-core transfer as a step of its own."""
        proc = json.loads((ROOT / 'data/process.json').read_text())
        for key, flow in proc['flows'].items():
            if 'routes' not in flow: continue
            steps = flow['steps']
            ids = [r['id'] for r in flow['routes']]
            self.assertEqual(ids[0], 'direct')
            runs = {}
            for i, s in enumerate(steps):
                if 'route' in s: runs.setdefault(s['route'], []).append(i)
            first = min(i for v in runs.values() for i in v)
            last = max(i for v in runs.values() for i in v)
            self.assertEqual(sorted(i for v in runs.values() for i in v), list(range(first, last + 1)))
            key_parts = lambda s: sorted(json.dumps(p, sort_keys=True) for p in s['parts'])
            end = key_parts(steps[runs['direct'][-1]])
            for r, idx in runs.items():
                self.assertEqual(idx, list(range(idx[0], idx[-1] + 1)), r)
                self.assertEqual({steps[i]['of'] for i in idx}, {steps[runs['direct'][0]]['of']}, r)
                self.assertEqual(key_parts(steps[idx[-1]]), end, r)
                if r != 'direct':
                    for i in idx: self.assertEqual(steps[i]['match'], 'pattern', steps[i]['id'])
            self.assertIn('saqp_core2', [steps[i]['id'] for i in runs['saqp']])
            self.assertIn('illustrative layer', flow['match']['pattern'])
            nxt = steps[last + 1]
            self.assertEqual(set(nxt['labels']), set(ids))
            # At most one route is the default; the FinFET's fins default to SAQP.
            defaults = [r['id'] for r in flow['routes'] if r.get('default')]
            self.assertLessEqual(len(defaults), 1)
            if key == 'fin': self.assertEqual(defaults, ['saqp'])
            self.assertTrue(flow['route_title'] and flow['route_join'])

    def test_process_source_labels(self):
        """Every state says how it relates to its source, never claims a drawing match, and
        never maps to a figure the flow says it skips (the patent's pFET-only steps)."""
        proc = json.loads((ROOT / 'data/process.json').read_text())
        audit = (ROOT / 'docs/PROCESS_AUDIT.md').read_text()
        for key, flow in proc['flows'].items():
            # A flow that maps figures says the drawings were not compared; one that maps none
            # (the FinFET, so far) says so instead.
            if any(st['figs'] for st in flow['steps']):
                self.assertIn('not available for visual comparison', flow['figures'])
            else:
                self.assertIn('No source figures are mapped', flow['figures'])
            self.assertTrue(flow['branch'])
            skipped = set(flow['skipped'])
            for step in flow['steps']:
                self.assertIn(step['match'], flow['match'])
                if step['match'] not in ('concept', 'pattern', 'generic'):
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
        self.assertEqual(len(ids), 23)
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
