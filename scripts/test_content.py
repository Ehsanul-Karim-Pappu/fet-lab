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
            # A pFET or both-sites flow carries its own finished parts ("final"), if any.
            lesson = flow.get('lesson', False) or (flow.get('own') and 'final' not in flow)
            # The nanosheet nFET flow ends on its own finished parts (the Process stack) but
            # keeps Device mode's views.
            dev = dict(parts=[], views={}) if lesson else \
                dict(parts=flow['final'], views={}) if flow.get('own') else \
                dict(devs[key], parts=flow.get('final', devs[key]['parts']))
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
                # Tile and field steps bring their own bounds; a site step may, to draw a
                # reticle above the device.
                if step['scale'] != 'site': self.assertIn('bounds', step)
                if step['level'] == 'op':
                    nxt = next(s for s in flow['steps'][n + 1:] if s['level'] == 'core')
                    self.assertEqual(step['of'], nxt['id'])
                    self.assertTrue(step['label'].startswith(nxt['label'] + '.'))
                # Films a step shows depositing are its own parts.
                ids_here = {p if isinstance(p, str) else p['id'] for p in step['parts']}
                self.assertLessEqual(set(step.get('deposit', [])), ids_here, step['id'])
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
        lessons = {k: f for k, f in flows.items() if f.get('lesson') and 'pitchwalk' not in f}
        self.assertEqual(set(lessons), {'sadp', 'saqp'})
        for key, flow in lessons.items():
            fork = next(i for i, s in enumerate(ns['steps']) if s.get('route'))
            want = [s for s in ns['steps'][:fork] if s.get('of') == 'pattern'] + \
                   [s for s in ns['steps'] if s.get('route') == key] + \
                   [s for s in ns['steps'] if s['id'] == 'stacketch']
            self.assertEqual([s['id'] for s in flow['steps']], [s['id'] for s in want])
            for a, b in zip(flow['steps'], want):
                self.assertEqual((a['parts'], a['body'], a['view'], a['match']),
                                 (b['parts'], b['body'], b['view'], b['match']))
                self.assertEqual(a['level'], 'core')
            self.assertEqual([s['label'] for s in flow['steps']],
                             [str(k) for k in range(1, len(want) + 1)])
            self.assertIn('patterning concept applied to an illustrative layer', flow['scope'].lower())
            # The lesson's text names the nanosheet flow's actual default route.
            default = next(r['name'] for r in ns['routes'] if r.get('default'))
            self.assertIn(f'defaults to {default}', flow['scope'])
            self.assertNotIn("that flow's default, a single exposure", flow['scope'])

    def test_badges(self):
        """Every match level a flow uses has a short badge for the stepper."""
        for key, flow in json.loads((ROOT / 'data/process.json').read_text())['flows'].items():
            self.assertEqual(set(flow['badge']), set(flow['match']), key)
            for st in flow['steps']: self.assertTrue(flow['badge'][st['match']], st['id'])

    def test_patterning_routes(self):
        """Each route is one run of operations of the same core step, and every route ends in
        the state the first (the direct print) ends in, so the shared step after them follows
        any of them. SAQP shows its second-core transfer as a step of its own."""
        proc = json.loads((ROOT / 'data/process.json').read_text())
        for key, flow in proc['flows'].items():
            if 'routes' not in flow or flow.get('route_kind') == 'terminal': continue
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
                    # A spacer route is a patterning concept (the nanosheet's), a teaching
                    # reconstruction, or a published example with its own source (SAQP fins).
                    for i in idx:
                        self.assertIn(steps[i]['match'], ('pattern', 'teach', 'source', 'concept'), steps[i]['id'])
                        if steps[i]['match'] == 'source': self.assertTrue(steps[i].get('src'), steps[i]['id'])
            self.assertIn('saqp_core2', [steps[i]['id'] for i in runs['saqp']])
            if 'pattern' in flow['match']: self.assertIn('illustrative layer', flow['match']['pattern'])
            nxt = steps[last + 1]
            self.assertEqual(set(nxt['labels']), set(ids))
            # At most one route is the default; the FinFET's fins default to SAQP.
            defaults = [r['id'] for r in flow['routes'] if r.get('default')]
            self.assertLessEqual(len(defaults), 1)
            if key == 'fin': self.assertEqual(defaults, ['saqp'])
            if key == 'ns': self.assertEqual(defaults, ['sadp'])
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
                if step['match'] not in ('concept', 'pattern', 'teach'):
                    self.assertTrue(step['figs'], step['id'])
                self.assertFalse(skipped & set(step['figs']), step['id'])
                for text in [step['body']] + step['subs'] + step['omitted']:
                    self.assertNotRegex(text.lower(), r'exact (match|reconstruction)|as in fig')
                self.assertIn('| ' + step['title'] + ' |', audit)
            # Once a flow names a source per step, every figure number says whose it is.
            refs = set(flow['refs'])
            if any('src' in st for st in flow['steps']):
                for st in flow['steps']:
                    if st['figs']: self.assertTrue(st.get('src'), st['id'])
            for st in flow['steps']:
                self.assertLessEqual(set(st.get('src', [])), refs, st['id'])
            for fig in skipped:
                self.assertIn('Fig. ' + fig, audit)

    def test_section_planes(self):
        """Each section plane cuts where its name says, at every step that compares against it:
        through the gate for a gate plane, through the source/drain for an S/D plane, along a
        channel for a longitudinal one. Every compare entry names a plane and figure that
        exist, lists what the plane actually cuts, and claims no drawing match."""
        proc = json.loads((ROOT / 'data/process.json').read_text())
        devs = {d['key']: d for d in self.data['devices']}
        def cut(parts, pl):
            k = 0 if pl['axis'] == 'x' else 2
            return [p for p in parts for b in p['boxes']
                    if b[k] - b[k + 3] / 2 < pl['pos'] - 1e-6 < pl['pos'] + 2e-6 < b[k] + b[k + 3] / 2]
        # What a plane must cut, by kind, at the finished device.
        want = {'ns': dict(x2=('sheet1', 'epi_drain', 'mo'), y1=('mo', 'sheet1'), y2=('epi_drain',)),
                'fin': dict(across_gate=('mo', 'fin1', 'fin2'), along_fin=('fin2', 'epi_drain', 'mo'),
                            across_sd=('epi_drain',))}
        avoid = {'ns': dict(y2=('mo', 'sheet1')), 'fin': dict(across_sd=('mo',))}
        for key, flow in proc['flows'].items():
            planes = {p['id']: p for p in flow.get('sections', [])}
            for pl in planes.values():
                for scale, vk in pl['views'].items():
                    self.assertEqual(flow['views'][vk].get('scale', 'site'), scale, (key, vk))
                self.assertNotRegex(pl['text'], r'matches|reproduc')
            if key in want:
                final = flow.get('final', devs[key]['parts'])
                for pid, names in want[key].items():
                    hit = {p['id'] for p in cut(final, planes[pid])}
                    self.assertLessEqual(set(names), hit, (key, pid))
                    self.assertFalse(set(avoid[key].get(pid, ())) & hit, (key, pid))
            if key == 'fin':
                # The FinFET patent's A, B and C lines are unverified: no plane claims one.
                for pl in planes.values():
                    self.assertNotRegex(pl['name'] + pl['short'], r'\b[ABC]\s*[–-]\s*[ABC]\b')
            for st in flow['steps']:
                for c in st.get('compare', []):
                    self.assertIn(c['plane'], planes, st['id'])
                    self.assertIn(st['scale'], planes[c['plane']]['views'], st['id'])
                    self.assertEqual(c['figs'], st['figs'])
                    self.assertIn(c['src'], flow['refs'])
                    self.assertTrue(c['described'] and c['visible'], st['id'])
                    self.assertIn(c['status'], ('text', 'visual', 'unverified'))
                    self.assertNotRegex((c['described'] + c['status_text']).lower(), r'exact|matches fig')

    def test_pitch_walk(self):
        """The pitch-walk lesson: its ideal case is the FinFET flow's own SAQP image, and every
        space it reports is the one its built lines actually leave."""
        flows = json.loads((ROOT / 'data/process.json').read_text())['flows']
        pw, fin = flows['pitchwalk'], flows['fin']
        spans = lambda boxes: sorted({(round(b[2] - b[5] / 2, 4), round(b[2] + b[5] / 2, 4)) for b in boxes})
        gaps = lambda sp: [round(b[0] - a[1], 4) for a, b in zip(sp, sp[1:])]
        part = lambda st, pid: next(p for p in st['parts'] if not isinstance(p, str) and p['id'] == pid)
        route = spans(part(next(s for s in fin['steps'] if s['id'] == 'saqp_pull2'), 'f_sp2')['boxes'])
        cfg = pw['pitchwalk']
        measured = [s for s in pw['steps'] if 'measure' in s]
        self.assertEqual([s['measure']['case'] for s in measured], ['ideal', 'core', 'sp1', 'sp2'])
        for st in measured:
            m = st['measure']
            lines = spans(part(st, 'pw_fins')['boxes'])
            self.assertGreaterEqual(len(lines), 16)
            g = gaps(lines)
            self.assertEqual(g, [w for _, w in m['gaps']])
            self.assertEqual((m['max'], m['min']), (max(g), min(g)))
            self.assertAlmostEqual(m['walk'], max(g) - min(g))
            self.assertTrue(all(w >= cfg['gmin'] for w in g) and all(b > a for a, b in lines))
            # Types follow the construction: a = the second core (s1), b = w1 - 2 s2,
            # c = P1 - w1 - 2 s1 - 2 s2.
            want = dict(a=m['s1'], b=m['w1'] - 2 * m['s2'], c=cfg['P1'] - m['w1'] - 2 * m['s1'] - 2 * m['s2'])
            for t, w in m['gaps']: self.assertAlmostEqual(w, want[t])
            for k, (lo, hi) in cfg['range'].items(): self.assertTrue(lo <= m[k] <= hi, (st['id'], k))
            self.assertIn(f"pitch walk = {m['max']:g} − {m['min']:g} = {m['walk']:g} nm", st['body'])
            if m['case'] == 'ideal':
                self.assertEqual(m['walk'], 0)
                # The FinFET route's lines, shifted: same widths, same spaces.
                self.assertEqual(g, gaps(route))
                self.assertEqual({round(b - a, 4) for a, b in lines}, {round(b - a, 4) for a, b in route})
                self.assertEqual({(m['w1'], m['s1'], m['s2'])}, {tuple(cfg['base'][k] for k in ('w1', 's1', 's2'))})
            else:
                self.assertGreater(m['walk'], 0)
        for st in pw['steps']:
            self.assertTrue(any('illustrative' in x for x in st['subs']), st['id'])
        # The flow's own SAQP route stays ideal: no pitch walk in the FinFET flow.
        self.assertEqual(len(set(gaps(route))), 1)

    def test_site_branches(self):
        """nFET, pFET and both sites: one selector over three flows per technology. The pFET
        keeps its channel material; both-sites states are the two site flows' own states;
        each region mask covers its own region only and leaves the other untouched."""
        flows = json.loads((ROOT / 'data/process.json').read_text())['flows']
        for tech, (n, p, both) in dict(ns=('ns', 'ns_p', 'ns_pair'), fin=('fin', 'fin_p', 'fin_pair')).items():
            sites = flows[n]['sites']
            self.assertEqual([s['flow'] for s in sites], [n, p, both])
            for k, key in zip(('n', 'p', 'both'), (n, p, both)):
                self.assertEqual(flows[key]['sites'], sites)
                self.assertEqual(flows[key]['site'], k)
            # The pFET flow shares the nFET flow's tile and field operations, state for state.
            nops = {s['id']: s for s in flows[n]['steps'] if s['scale'] in ('tile', 'field')}
            pops = {s['id']: s for s in flows[p]['steps'] if s['scale'] in ('tile', 'field')}
            self.assertEqual(set(nops), set(pops))
            for i in nops:
                self.assertEqual(nops[i]['parts'], pops[i]['parts'], i)
            # Every step of each site flow says what both regions are doing.
            for key in (n, p, both):
                for st in flows[key]['steps']:
                    self.assertEqual(set(st.get('regions', {})), {'n', 'p'}, (key, st['id']))
            final = {q['id']: q for q in flows[p]['final']}
            if tech == 'ns':
                chan = [q for q in final.values() if q['group'] == 'Channel stack']
                self.assertEqual({q['material'] for q in chan}, {'sige'})
                self.assertFalse(any('bdi' in q['id'] for q in final.values()))   # BDI is nFET-only
                self.assertIn('pts_n', {q['material'] for q in final.values()})
            wf = {q['material'] for q in final.values() if 'work-function' in q['name']}
            self.assertEqual(wf, {'tin'})     # TiN: the usual p-type work-function metal
            epi = {q['material'] for q in final.values() if q['id'].startswith('epi_')}
            self.assertEqual(epi, {'sige'})
            # Both sites: each side is the named site state, moved into place.
            byid = {k: {s['id']: s for s in flows[f]['steps']} for k, f in (('n', n), ('p', p))}
            fins = {k: {q['id']: q for q in flows[f].get('final') or
                        next(d for d in self.data['devices'] if d['key'] == f)['parts']} for k, f in (('n', n), ('p', p))}
            dz = -flows[both]['bounds']['z'][0] - flows[both]['bounds']['z'][1]
            prev = {}
            for st in flows[both]['steps']:
                src = st['from']
                for k in ('n', 'p'):
                    want = sorted(q if isinstance(q, str) else q['id'] for q in byid[k][src[k]]['parts'])
                    want = [w for w in want if w not in src['drop'] and f'{k}:{w}' not in src['drop']]
                    got = sorted(q['id'][2:] for q in st['parts'] if q.get('site') == k)
                    self.assertEqual(got, want, (both, st['id'], k))
                # Region masks stay inside their region and leave the other side as it was.
                zmid = -dz / 2
                for q in st['parts']:
                    if q['group'] != 'Region masks': continue
                    r = 'n' if 'nFET region' in q['name'] else 'p'
                    for b in q['boxes']:
                        lo, hi = b[2] - b[5] / 2, b[2] + b[5] / 2
                        self.assertTrue(lo >= zmid - 1e-6 if r == 'n' else hi <= zmid + 1e-6, (st['id'], q['id']))
                    last = prev.get(st.get('route'), prev.get(None))
                    if last:
                        side = lambda s_: sorted(json.dumps(q_, sort_keys=True) for q_ in s_['parts'] if q_.get('site') == r)
                        self.assertEqual(side(st), side(last), (both, st['id'], r))
                prev[st.get('route')] = st
                if st.get('route') is None: prev[None] = st

    def test_gate_cut(self):
        """The gate cut leaves no conductive path between the nFET's and pFET's gates and cuts no
        channel, fin or source/drain; the shared gate keeps them one conductor. The two are
        alternative routes: neither follows the other."""
        flows = json.loads((ROOT / 'data/process.json').read_text())['flows']
        metals = {'mo', 'tin', 'nwf', 'tungsten', 'cobalt', 'tisi'}
        def touch(a, b):
            d = [min(a[k] + a[k + 3] / 2, b[k] + b[k + 3] / 2) - max(a[k] - a[k + 3] / 2, b[k] - b[k + 3] / 2) for k in range(3)]
            return min(d) >= -1e-6 and sorted(d)[1] > 1e-6
        def joined(st):
            boxes = [(q['id'], b) for q in st['parts'] if q['material'] in metals for b in q['boxes']]
            parent = list(range(len(boxes)))
            def f(i):
                while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
                return i
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    if touch(boxes[i][1], boxes[j][1]): parent[f(i)] = f(j)
            comp = lambda pid: {f(i) for i, (q, _) in enumerate(boxes) if q == pid}
            return bool(comp('n_mo') & comp('p_mo'))
        for key in ('ns_pair', 'fin_pair'):
            flow = flows[key]
            self.assertEqual(flow['route_kind'], 'terminal')
            self.assertEqual([r['id'] for r in flow['routes']], ['cut', 'shared'])
            by = {s['id']: s for s in flow['steps']}
            ids = [s['id'] for s in flow['steps']]
            # Alternatives: the shared gate is the last step, after the cut route, never on it.
            self.assertEqual(by['shared']['route'], 'shared')
            self.assertTrue(all(by[i].get('route') == 'cut' for i in ids[ids.index('cut_coat'):ids.index('shared')]))
            self.assertEqual(by['shared']['label'], by['gatecut']['label'])
            for sid in ('hkmg' if key == 'ns_pair' else 'metal', 'shared'):
                self.assertTrue(joined(by[sid]), (key, sid))
            for sid in ('cut_etch', 'gatecut', 'contacts_cut'):
                self.assertFalse(joined(by[sid]), (key, sid))
            plug = next(q for q in by['gatecut']['parts'] if q['id'] == 'b_plug')
            for q in by['gatecut']['parts']:
                if q['group'] in ('Channel stack', 'Superlattice', 'Source / drain', 'Fins'):
                    for a in q['boxes']:
                        for b in plug['boxes']:
                            d = [min(a[k] + a[k + 3] / 2, b[k] + b[k + 3] / 2) - max(a[k] - a[k + 3] / 2, b[k] - b[k + 3] / 2) for k in range(3)]
                            self.assertLessEqual(min(d), 1e-6, (key, q['id']))
            # The shared gate has one gate contact; the cut route one per gate.
            gw = lambda st: [q['id'] for q in st['parts'] if q['id'].endswith('gatew')]
            self.assertEqual(sorted(gw(by['contacts_cut'])), ['n_gatew', 'p_gatew'])
            self.assertEqual(gw(by['shared']), ['n_gatew'])

    def test_materials_by_polarity(self):
        """Work-function metals follow practice: an Al-containing n-type metal for nFETs, TiN for
        pFETs. Contacts use a Ti-based silicide, not NiSi, and no nickel plug."""
        for sc in self.data['devices']:
            for p in sc['parts']:
                if 'work-function' in p['name']:
                    pol = 'p' if ('pFET' in p['name'] or 'pMOS' in p['name'] or 'p-type' in p['name']
                                  or p['id'].startswith(('p_', 'tin_p', 'A_p', 'B_p', 'C_p', 'F_p'))) else 'n'
                    self.assertEqual(p['material'], 'tin' if pol == 'p' else 'nwf', (sc['key'], p['id'], p['name']))
                self.assertNotIn(p['material'], ('nisi', 'nickel'), (sc['key'], p['id']))
        for name in ('nisi', 'nickel', 'pwf'):
            self.assertNotIn(name, self.data['materials'])

    def test_references_and_scope(self):
        ids = [r['id'] for r in self.refs['sources']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 27)
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

    def test_nanosheet_process_stack(self):
        """One Si/SiGe stack makes both nanosheet devices, so every channel it leaves is
        channel-thin: the nFET's Si sheets and the pFET's SiGe sheets alike, in every step of
        the nFET, pFET and both-sites flows. The gate films between the sheets fit their gap."""
        flows = json.loads((ROOT / 'data/process.json').read_text())['flows']
        for key in ('ns', 'ns_p', 'ns_pair'):
            # The both-sites flow has no finished list: its last step carries the parts.
            final = {p['id']: p for p in flows[key].get('final') or
                     [q for q in flows[key]['steps'][-1]['parts'] if isinstance(q, dict)]}
            chans = [p for p in final.values() if p['group'] == 'Channel stack']
            self.assertEqual(len(chans), 6 if key == 'ns_pair' else 3, key)
            for p in chans:
                for b in p['boxes']:
                    self.assertLessEqual(b[4], 8.0, (key, p['id']))          # sheet thickness
            # Every stack layer, sacrificial or kept, in every step, is channel-thin too.
            for st in flows[key]['steps']:
                for p in st['parts']:
                    if isinstance(p, dict) and p['group'] in ('Superlattice', 'Channel stack') \
                            and 'base' not in p['name']:
                        for b in p['boxes']:
                            self.assertLessEqual(b[4], 8.0, (key, st['id'], p['id']))
        # Device mode's nanosheet keeps its spaced-out, noted stack.
        ns = next(d for d in self.data['devices'] if d['key'] == 'ns')
        self.assertIn('Process mode', ns['note'])

    def test_guide_learning_aids(self):
        """Both tours name real stops, the learning path opens real scenes in order, and
        every glossary term is defined and used by a step's text or notes, a device scene or a reference."""
        g = json.loads((ROOT / 'data/guide.json').read_text())
        ids = {s['id'] for s in g['stops']}
        for tour in ('tour', 'process_tour'):
            self.assertTrue(g[tour]); self.assertTrue(set(g[tour]) <= ids, tour)
        scenes = {d['key'] for d in self.data['devices']}
        self.assertEqual([l['key'] for l in g['learn']], ['fin', 'ns', 'fs', 'cfet_mono', 'process'])
        for l in g['learn'][:-1]: self.assertIn(l['key'], scenes)
        flows = json.loads((ROOT / 'data/process.json').read_text())['flows']
        text = ' '.join(' '.join([st['body']] + st.get('subs', [])) for f in flows.values() for st in f['steps'])
        dev_text = json.dumps([self.data, self.refs], ensure_ascii=False)
        for t in g['glossary']:
            self.assertTrue(t['term'] and t['name'] and t['text'] and t['match'], t)
            # The app's own rule: an all-capitals match is a whole word, anything else a word start.
            res = [re.compile(r'\b' + re.escape(m) + r'\b') if m == m.upper()
                   else re.compile(r'\b' + re.escape(m), re.I) for m in t['match']]
            self.assertTrue(any(r.search(text) or r.search(dev_text) for r in res), t['term'])

if __name__ == '__main__':
    unittest.main()
