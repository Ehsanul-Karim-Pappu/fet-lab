# Contributing

Thanks for taking a look. Issues and pull requests are both welcome.

## Reporting a problem

Open an issue and pick the right template. The two things that make a report actionable:

- **For a rendering bug:** your device model, Android version, and a screenshot.
- **For a geometry bug:** which scene, and what you expected instead. If you can point at
  a published figure or a paper, that settles it fastest.

## Building

```bash
git clone <this repo>
cd fet-lab/android
# open in Android Studio Ladybug or newer, or:
./gradlew assembleDebug
```

Requires JDK 17 and Android SDK 35. First sync downloads AGP 8.7.3, Kotlin 2.0.21 and the
Compose BOM.

## Changing the geometry

Do not hand-edit `data/devices.json` — it is generated. Edit the builders and re-run:

```bash
pip install trimesh numpy
python scripts/build_devices.py      # device scenes
python scripts/build_inverters.py    # inverter cells
python scripts/build_showcase.py     # layout figures
python scripts/export_all.py         # GLB / STL / OBJ
cp data/devices.json android/app/src/main/assets/devices.json
```

**Every scene must tile exactly** — no overlapping solids, no gaps. The build prints
`max/voxel=1` when it does. If it prints 2, `scripts/findlap.py` names the offending pair.
A PR that breaks this will not be merged, because overlapping solids ruin the section
planes and the exported meshes.

## Code style

- Kotlin: official style, 4 spaces, ~110 column soft limit.
- Python: 4 spaces, keep the builders declarative and readable over clever.
- Comments explain *why*, not *what*. The geometry files are full of decisions that are
  not obvious six months later — write those down.

## Scope

This is a teaching tool. Additions should make a device or a trade-off easier to see.
Features that only add configurability, without making anything clearer, are usually a no.
