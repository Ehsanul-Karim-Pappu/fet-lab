# Changelog

All notable changes to FET Lab. Dates are the release date; versions follow
[semantic versioning](https://semver.org).

## Unreleased

### Consistent view order

Device scenes now use the same view sequence for every architecture: 3D overview, Along
channel, Across channel, then the architecture-specific view. CFET no longer opens in
section, and the nanosheet view names no longer carry figure letters.

### Technology stays put when you change view

Switching between Device, Inverter and Layout used to drop you back on FinFET. It now
keeps the architecture you were looking at: Device › Forksheet to Inverter opens the
forksheet inverter, on to Layout opens the forksheet cell. Compare carries across the
same way, and a CFET left on Sequential comes back as Sequential rather than Monolithic.
Only the viewing mode changes.

### Content and capacitance audit

Reviewed architecture, materials and integration descriptions against primary sources.
Added a shared reference catalog to web/PWA and Android About; exact dimensions and the
complete material palette are explicitly illustrative. Corrected CFET gate/contact
options, inverter sizing language, layout axis labels, and privacy/local-storage wording.
The former perspective preset named Isometric is now accurately called 3D overview.

Capacitance estimates are geometry-only educational approximations, not measured or
TCAD-validated values. Fixed oxide film thickness extraction, integrated dielectric
layers in series across each gap, and excluded channel/body area from the source/drain
junction-area proxy. Removed claims that architecture ratios or a monotonic ranking
are validated. A zero junction proxy does not mean a real device has zero junction
capacitance. Added analytic and grid-convergence tests. See
[the audit](docs/CONTENT_AUDIT.md) for assumptions and before/after values.

## 1.1.0 — 2026-09-13

The layout figures are now drawn to scale, and the numbers the app prints are checked
against the geometry on every build.

### Layout figures redrawn to scale

Everything in the plane of the wafer now comes from the device cross-sections, so one
nanometre means the same thing in the Device, Inverter and Layout scenes.

- Gate drawn at its physical length (18 nm FinFET, 15 nm elsewhere) instead of 14 nm;
  MD drawn at the contacted length of 22 nm instead of 14 nm. The MD-to-gate ratio was
  1.00 as drawn where it should have been 1.22.
- Metal 0 on one uniform track pitch with the rails on the cell boundary. The tracks
  previously sat at three different pitches — 15, 29 and 22 nm — in the same cell.
- Each cell at its real rail-to-rail width: 156 / 136 / 106 / 74 nm. The Layout compare
  scene had drawn FinFET, nanosheet and forksheet all at 116 nm — identical — while
  telling the reader to watch the cell narrow. It now agrees with the Inverter compare.
- MD columns run the full cell height, rail edge to rail edge, and are cut only where the
  net changes. At a cut each piece overhangs its channel by 3 nm rather than sitting flush
  with the end of the channel it contacts.
- Wells, field oxide and gate extend under the far edge of the rail, because a rail
  straddles the cell boundary and is shared with the row above or below.

### Fixed

- **Forksheet output was not connected.** The dielectric wall splits the drain contact in
  two, and the n-side via went nowhere — the OUT track runs on the p side of the wall. A
  transverse Metal 0 jog over the drain now ties the two halves together.
- **Dimension callouts on Android** were dropped onto the geometry with no leader line and
  no reference to what they measured, and piled on top of each other. They now sit at their
  own label point, draw the measured span and a leader to it, and are spaced apart. The
  collision code had been estimating each chip as one line of body text when it is two
  lines of mono inside a padded surface — about half the real height.
- **Layer names on top faces** ran vertically. The axis is now chosen by how the name comes
  out on screen rather than by which in-plane axis is longer.
- **EOT callout** printed 1.35 nm against an arrow spanning the 3 nm physical stack. It now
  reads `t_ox = 3 nm` with `1 SiO₂ + 2 HfO₂ · EOT 1.35 nm` beneath, and on the FinFET the
  arrow no longer runs diagonally across a corner.
- FinFET `W_eff` row said "2H+W per fin" against a value covering both fins.
- Section views framed the cell by its largest extent, which ignored perspective and let
  deep cells overflow the frame by up to 150 px. Framing now solves each bounding-box
  corner exactly, and the aspect correction is no longer defeated by the framing cap.
- Reset restored a light background on layout scenes, against the dark default.
- `build_devices.py`, `build_geometry.py` and `export_meshes.py` wrote to hardcoded
  `/home/claude/...` paths, so the documented "regenerate the geometry" steps could not
  work from a clone.

### Added

- **Slow rotate** toggle on Android, under Section → Display.
- `scripts/build_web.py` — assembles `roadmap.html` and `pwa/index.html` from the template
  and bumps the service-worker cache, a step that had been manual.
- `scripts/verify.py` now checks every callout's printed value against the length of the
  span it draws, and the declared gate length against the high-κ film that defines it.
- `scripts/ktcheck.py` now catches Compose state used above its own declaration — the
  error that broke the previous Android build.

## 1.0.0 — 2026-09-13

First stable build: web viewer, installable PWA and Android app all working from one
geometry file. Sixteen scenes — six device, five inverter, five layout — across FinFET,
nanosheet, forksheet and CFET.
