<div align="center">

<img src="store/icon-512.png" width="104" alt="FET Lab">

# FET Lab

**Transistor architectures in 3D — FinFET, nanosheet, forksheet and CFET, film by film.**

[![Android](https://github.com/ehsanul-karim-pappu/fet-lab/actions/workflows/android.yml/badge.svg)](../../actions/workflows/android.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-0E7C8C.svg)](LICENSE)
[![minSdk](https://img.shields.io/badge/minSdk-26-4FC7D8.svg)](android/app/build.gradle.kts)
[![Kotlin](https://img.shields.io/badge/Kotlin-2.0.21-7F52FF.svg)](https://kotlinlang.org)

**[Open it in your browser →](https://ehsanul-karim-pappu.github.io/fet-lab/)**
No install; add it to your home screen and it works offline.

</div>

---

<img src="docs/device.png" alt="Nanosheet FET, 3D overview, with dimension callouts">

Selected films are modeled: the silicon channel, the 1 nm interfacial oxide, the high-κ HfO₂,
the TiN work-function metal, the gate fill, the spacers, the source/drain epitaxy, the
silicide and the contacts. Slice along any axis and the cut face is **solid**, not hollow,
so a section reads like a real cross-section rather than a shell.

**1 unit = 1 nm.** `x` = source→drain, `y` = vertical stacking, `z` = lateral n/p span.

## Four ways to look at them

| | |
|---|---|
| **Device** | Technical cross-sections of each architecture — section planes, exploded view, tap-to-identify. |
| **Inverter** | An illustrative CMOS inverter cell for each architecture. Drive the input and the conducting path lights up. |
| **Layout** | Schematic inverter layouts with simplified film stacks and exaggerated vertical dimensions; two representative nanosheets instead of the technical model's three. |
| **Process** | How a nanosheet FET or a FinFET is made, step by step, as real geometry: films, lithography, etch and fill on a 2 × 2 tile, then the selected site to the finished device, as the nFET, the pFET, or both sites with a gate cut or a shared gate. The stack lines or fins can be printed directly or by SADP or SAQP; a Pitch walk lesson lets the SAQP dimensions vary. Named section planes show a 2D section beside the 3D view, set against what each source's text describes. Android app for now; forksheet and CFET flows are coming. |

<table>
<tr>
<td width="50%"><img src="docs/inverter.png" alt="Nanosheet inverter, section through the gate"><br><sub><b>Inverter</b> — pMOS conducting, nMOS dimmed</sub></td>
<td width="50%"><img src="docs/layout.png" alt="Nanosheet inverter as a layout figure"><br><sub><b>Layout</b> — schematic stack, with lateral dimensions to model scale</sub></td>
</tr>
</table>

<img src="docs/compare.png" alt="Four inverter layouts side by side at one scale">

On Android, a guided tour on first launch shows the gestures and every tool, with an
animated hand doing each one; replay it from **?** › Help & features.

## What it shows—and what it does not

- FinFET: a tri-gate example with discrete fin-count sizing.
- Nanosheet FET: gate-all-around channels with adjustable sheet width.
- Forksheet: the classic inner-wall arrangement, not the later outer-wall variant.
- CFET: a stacked nFET/pFET pair, with monolithic and sequential examples.

This is one educational roadmap, not a universal process sequence. FinFETs remain in use.
Process mode follows one disclosed integration route for the nanosheet nFET and pFET, and
disclosed FinFET stages, as a teaching sequence: each step names the source it follows and
how closely, and none is a foundry recipe or a copy of a published drawing. A 2D section is
cut from the app's own model, not taken from a patent figure; every figure mapping is
text-verified only (the drawings have not been compared). The SADP and SAQP routes for the
nanosheet are illustrative alternatives, the FinFET's SAQP is adapted from a published
example, and the pitch-walk variations are the app's own.
Materials and dimensions are illustrative; the complete stack is not a verified foundry
recipe. Work-function tuning, doping, strain, self-heating and electrical drive are not simulated.
IN/OUT colors demonstrate ideal logic states, not current or timing calculations.

Comparison scenes report drawn lateral spans, not equal-performance area comparisons.
The rail-to-rail z dimension is commonly called cell height in standard-cell design.
Gate-stack span, device-pair span and rail-to-rail span are distinct measurements.
The example-node labels do not assign an architecture to one universal technology node.

Capacitances are geometry-only approximations. Their absolute values **and ratios** depend
on missing dielectrics, omitted 3D fields and assumed material properties. See the
[numerical audit](docs/CONTENT_AUDIT.md) and [technical references](docs/TECHNICAL_REFERENCES.md).
Gate-stack thickness and the plotted dimensions can be checked against the box model;
that is not physical validation against manufactured devices.

## Repository layout

```
android/    Native app — Kotlin, Jetpack Compose, hand-written OpenGL ES 2.0 renderer
pwa/        Installable web app, works offline
web/        Desktop viewers, standalone HTML
models/     Every scene exported as GLB / STL / OBJ
scripts/    The parametric generators
data/       devices.json — the box list the app, the viewers and the exporters all read
store/      Play Store assets and listing copy
docs/       Screenshots and the written background
```

## Build the app

```bash
cd android
./gradlew assembleDebug      # → app/build/outputs/apk/debug/
./gradlew installDebug       # straight onto a connected device
```

JDK 17, Android SDK 35, minSdk 26. No third-party 3D library — the renderer, section
capping, ray picking and exploded view are all in `Renderer.kt`. CI builds a debug APK on
pushes to main and pull requests, and attaches it to the run.

Publishing: see [`android/PLAY_STORE.md`](android/PLAY_STORE.md).

## Run the web version

```bash
cd pwa && python3 -m http.server 8000
```

Open it on a phone on the same network and use **Add to Home screen** — it installs
standalone and works offline afterwards. The `pages.yml` workflow deploys the same folder
to GitHub Pages if you enable it.

## Regenerate the geometry

Do not hand-edit `data/devices.json`; it is generated.

```bash
python3 -m pip install numpy
python3 scripts/build.py             # all scenes, background, capacitances and viewer assets
python3 scripts/test_parasitics.py   # analytic cases, selection and grid convergence
python3 scripts/test_content.py      # synchronized bundles and reference coverage
python3 scripts/verify.py            # structural/geometry checks
```

Every scene must tile exactly — no overlapping solids, no gaps. The build prints
`max/voxel=1` when it does; `scripts/findlap.py` names the offending pair when it does not.

## Background

[docs/BACKGROUND.md](docs/BACKGROUND.md) is the written history behind each architecture —
what it replaced, what broke, why the industry moved, and what the move cost. The same text
appears in the app.

## Caveats

- Dimensions are representative teaching values, not any foundry's process data.
- The `Node` row is a generation label, not a measurement. Modern node names do not specify a unique physical feature size. The example labels here are
  illustrative, not a claim that each architecture belongs to one node.
- The inverter cells route on one metal level plus local interconnect — the topology, not a
  layout you could tape out.
- The forksheet modelled is the classic inner-wall device; imec's later outer-wall variant
  is not included.
- In the plane of the wafer every scene is to scale: gate length, contacted length,
  channel width, cell width and Metal 0 track pitch all come from one set of constants in
  `build_devices.py`, so the same nanometre means the same thing in the Device,
  Inverter and Layout scenes. `verify.py` fails the build if a callout ever disagrees
  with the geometry it points at.
- Vertically, layer thicknesses in the Layout scenes are exaggerated. Drawn to scale, a
  1 nm interfacial oxide would be sub-pixel on a phone. The Device scenes keep the real
  film thicknesses in all three axes.

## Releases

Version history and what changed in each release: [CHANGELOG.md](CHANGELOG.md).
Builds are on the [releases page](../../releases).

## Contributing

Issues and pull requests welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
Bug reports go to the [issue tracker](../../issues).

## Licence

[MIT](LICENSE) © 2026 Khandaker Ehsanul Karim
Third-party notices in [THIRD_PARTY.md](THIRD_PARTY.md) · Privacy policy in [PRIVACY.md](PRIVACY.md)

---

<div align="center">
<sub>Built by <b>Khandaker Ehsanul Karim</b> · <a href="mailto:ehsan.pappu.99@gmail.com">ehsan.pappu.99@gmail.com</a></sub>
</div>
