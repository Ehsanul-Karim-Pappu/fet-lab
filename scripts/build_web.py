#!/usr/bin/env python3
"""Assemble the shipped HTML from the template and the scene data.

  scripts/roadmap.tpl.html + data/{devices,process,guide,references}.json
                                              -> web/finfet-to-cfet.html
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

def payload(obj):
    # </script> inside a JS string literal would close the tag early.
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")

guide = json.loads((ROOT / "data/guide.json").read_text())
proc = json.loads((ROOT / "data/process.json").read_text())
html = tpl
# The scenes, the fabrication flows, the glossary and learning path, and the references.
for mark, obj in (("DATA", data), ("PROC", proc), ("GUIDE", guide), ("REFS", refs)):
    MARK = "/*__" + mark + "__*/null"
    if html.count(MARK) != 1:
        sys.exit(f"expected exactly one {MARK} in roadmap.tpl.html, found {html.count(MARK)}")
    html = html.replace(MARK, payload(obj))
# The tour's hand, a small copy of the app's drawable, inlined so the page stays one file.
import base64
HAND = '"/*__HAND__*/"'
assert html.count(HAND) == 1, "expected one hand marker in roadmap.tpl.html"
html = html.replace(HAND, '"data:image/webp;base64,' +
                    base64.b64encode((ROOT / "scripts/tour_hand.webp").read_bytes()).decode() + '"')
reference_html = '<section class="refs" id="technical-references"><h2>Technical references</h2><p>' + escape(refs['scope']) + '</p><ol>'
for r in refs['sources']:
    reference_html += '<li id="ref-' + r['id'] + '"><a href="' + escape(r['url'], quote=True) + '" target="_blank" rel="noopener">' + escape(r['id'] + ' — ' + r['title']) + '</a> — ' + escape(r['publisher']) + '<p>' + escape(r['supports']) + '</p></li>'
reference_html += '</ol><p>Reviewed ' + refs['reviewed'] + '.</p></section>'
assert html.count('<!-- TECHNICAL_REFERENCES -->') == 1
html = html.replace('<!-- TECHNICAL_REFERENCES -->', reference_html)
# The standalone viewer is a whole document of its own; the PWA wraps the same page below.
(ROOT / "web/finfet-to-cfet.html").write_text(
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    + html.rstrip("\n") + '\n</html>\n')
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
