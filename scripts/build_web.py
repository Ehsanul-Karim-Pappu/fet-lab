#!/usr/bin/env python3
"""Assemble the shipped HTML from the template and the scene data.

  scripts/roadmap.tpl.html + data/devices.json -> web/finfet-to-cfet.html
  standalone viewer + pwa/parts/*             -> pwa/index.html

Also bumps the service-worker cache name so an installed PWA picks the new
build up instead of serving the cached one. Run after every build_* script.
"""
import json, pathlib, re, sys
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
tpl  = (ROOT / "scripts/roadmap.tpl.html").read_text()
data = json.loads((ROOT / "data/devices.json").read_text())
refs = json.loads((ROOT / "data/references.json").read_text())

MARK = "/*__DATA__*/null"
if tpl.count(MARK) != 1:
    sys.exit(f"expected exactly one {MARK} in roadmap.tpl.html, found {tpl.count(MARK)}")

blob = json.dumps(data, separators=(",", ":"))
# </script> inside a JS string literal would close the tag early.
blob = blob.replace("</", "<\\/")
html = tpl.replace(MARK, blob)
reference_html = '<section class="panel" id="technical-references"><h2>Technical references</h2><p>' + escape(refs['scope']) + '</p><ol>'
for r in refs['sources']:
    reference_html += '<li id="ref-' + r['id'] + '"><a href="' + escape(r['url'], quote=True) + '">' + escape(r['id'] + ' — ' + r['title']) + '</a> — ' + escape(r['publisher']) + '<p>' + escape(r['supports']) + '</p></li>'
reference_html += '</ol><p>Reviewed ' + refs['reviewed'] + '.</p></section>'
assert html.count('<!-- TECHNICAL_REFERENCES -->') == 1
html = html.replace('<!-- TECHNICAL_REFERENCES -->', reference_html)
(ROOT / "web/finfet-to-cfet.html").write_text(html)
legacy_path = ROOT / 'web/nanosheet-only.html'
legacy = legacy_path.read_text()
geo = json.loads((ROOT / 'data/geometry.json').read_text())
geo_blob = json.dumps(geo, separators=(',', ':')).replace('</', '<\\/')
legacy, count = re.subn(r'^const GEO = .*;$', lambda _: 'const GEO = ' + geo_blob + ';', legacy, flags=re.M)
assert count == 1, 'Expected one legacy geometry payload'
legacy_path.write_text(legacy)
for name in ('devices.json', 'guide.json', 'references.json', 'process.json'):
    (ROOT / 'android/app/src/main/assets' / name).write_bytes((ROOT / 'data' / name).read_bytes())
md = '# Technical references\n\nGenerated from data/references.json. Reviewed ' + refs['reviewed'] + '.\n\n' + refs['scope'] + '\n\n'
for r in refs['sources']:
    md += '- **' + r['id'] + '** [' + r['title'] + '](' + r['url'] + ') — ' + r['publisher'] + '. ' + r['supports'] + '\n\n'
md += '## Unverified historical credit\n\n' + refs['unverified_legacy_credit'] + '\n'
(ROOT / 'docs/TECHNICAL_REFERENCES.md').write_text(md)

lines = html.split("\n")
title = lines[0]
if "<title>" not in title:
    sys.exit("roadmap.tpl.html must start with its <title> line")

p = ROOT / "pwa" / "parts"
pwa = "\n".join([
    (p / "head-open.html").read_text().rstrip("\n"),
    title,
    (p / "head-meta.html").read_text().rstrip("\n"),
    "\n".join(lines[1:]).rstrip("\n"),
    (p / "foot.html").read_text().rstrip("\n"),
]) + "\n"
(ROOT / "pwa" / "index.html").write_text(pwa)

# bump the cache so installed copies refresh
swp = ROOT / "pwa" / "sw.js"
sw  = swp.read_text()
m = re.search(r'CACHE\s*=\s*"fetlab-v(\d+)"', sw)
if not m:
    sys.exit("could not find the cache name in pwa/sw.js")
new = int(m.group(1)) + 1
swp.write_text(sw[:m.start(1)] + str(new) + sw[m.end(1):])

n = len(data["devices"]) if isinstance(data, dict) and "devices" in data else len(data)
print(f"Web, PWA, Android data and references synchronized ({n} scenes, cache fetlab-v{new})")
