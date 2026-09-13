#!/usr/bin/env python3
"""Assemble the shipped HTML from the template and the scene data.

  roadmap.tpl.html + devices.json  ->  roadmap.html        (standalone viewer)
  roadmap.html     + pwa/parts/*   ->  pwa/index.html      (installable PWA)

Also bumps the service-worker cache name so an installed PWA picks the new
build up instead of serving the cached one. Run after every build_* script.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
tpl  = (ROOT / "roadmap.tpl.html").read_text()
data = json.loads((ROOT / "devices.json").read_text())

MARK = "/*__DATA__*/null"
if tpl.count(MARK) != 1:
    sys.exit(f"expected exactly one {MARK} in roadmap.tpl.html, found {tpl.count(MARK)}")

blob = json.dumps(data, separators=(",", ":"))
# </script> inside a JS string literal would close the tag early.
blob = blob.replace("</", "<\\/")
html = tpl.replace(MARK, blob)
(ROOT / "roadmap.html").write_text(html)

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
print(f"roadmap.html + pwa/index.html rebuilt  ({n} scenes, cache fetlab-v{new})")
