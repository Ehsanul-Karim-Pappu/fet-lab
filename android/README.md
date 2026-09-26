# FET Lab — native Android app

Kotlin + Jetpack Compose, with a hand-written OpenGL ES 2.0 renderer. No third-party 3D
library: the geometry, shaders, section capping, picking and the exploded view are all in
`Renderer.kt`, ported from the web viewer.

## Build it

1. **Android Studio** (Ladybug 2024.2.1 or newer) → *Open* → pick this `android/` folder.
2. Let it sync. It will fetch AGP 8.7.3, Kotlin 2.0.21, Compose BOM 2024.10.01 and the
   Gradle 8.9 distribution on first run if they are not already cached.
3. Plug in a phone with USB debugging on, or start an emulator, and press **Run**.

Command line, from this directory with JDK 17 and the Android SDK configured:

```bash
./gradlew assembleDebug      # app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug       # straight onto a connected device
```

On the phone itself, in Termux, from the repository root:

```bash
bash build_android_termux.sh             # e.g. fet-lab-finfet-process-20260926-6595236-debug.apk
bash build_android_termux.sh --install   # then opens Android's installer on it
```

It needs `pkg install openjdk-17 aapt2 rsync` (plus `apksigner` to verify the signature)
and an SDK in `~/android-sdk` with `platforms;android-35` and `build-tools;34.0.0`; it says
exactly what is missing. It builds in a private copy under `~/.cache/fet-lab-build`, which
it keeps so later builds are incremental (`--clean` starts over), holds a wake lock while
Gradle runs, and explains the usual Termux failures. `--help` lists the options.

minSdk 26 (Android 8.0), targetSdk 35. Requires OpenGL ES 2.0.

## What the app does

Sixteen scenes, loaded from `app/src/main/assets/devices.json` — the same file the web viewer
reads, so regenerating the geometry updates both.

- **Channel design** — the nanosheet scenes' CMOS design, Si/SiGe (the default) or Si/Si, on a pill
  at the top of the stage and kept across Device, Inverter and Process; an **Exploded gate view**
  switch in Device and Inverter enlarges the gaps and films (not to scale).
- **Device mode** — FinFET, nanosheet, forksheet, CFET (monolithic / sequential) and the
  four-way footprint comparison.
- **Inverter mode** — an illustrative CMOS inverter in each architecture, with an
  input toggle that lights the conducting path and dims the transistor that is off.
- **Layout mode** — schematic inverter layouts with simplified stacks and exaggerated
  vertical dimensions.
- Five tabs in a sheet that floats over the model on phones (drag it between peek, open
  and expanded; its see-through is adjustable): **Views** presets, **Section** planes with
  solid capped cut faces plus the exploded view and display switches, **Layers** grouped
  by process module with per-group and master switches, **Specs** dimensions and
  geometry-only capacitance estimates that highlight the coupling they model, and
  **Story** background. Tap any layer in 3D to identify it.
- Each scene remembers its camera, cuts, view and hidden layers for the session.
- **Process mode** — a representative fabrication flow as real geometry, one scene per
  step, read from `app/src/main/assets/process.json` (built by `scripts/build_process.py`).
  So far the nanosheet (18 core steps) and the FinFET (15), plus operation substeps
  (resist, exposure, etch, fill...) that zoom out to a 2 × 2 tile of sites; forksheet and
  CFET are listed as coming. A route switch in the Steps tab patterns the nanosheet's stack
  lines or the FinFET's fins by direct print, SADP or SAQP, the spacer routes on a field of
  lines around the tile; **SADP** and **SAQP** chips show the nanosheet's routes on their
  own, and **Pitch walk** lets the FinFET's SAQP dimensions vary (`PitchWalk.kt`). A site
  selector switches each technology between its nFET, pFET and both-sites flows; both sites
  end in a gate cut or a shared gate. Each step carries its source figures (where mapped),
  match level, substitutions and omissions, and, per section plane, what its source's text
  describes against what the model cuts (`Section.kt` draws the 2D section and the locator
  from the scene's own boxes), shown in the Steps and Section tabs and audited in
  `docs/PROCESS_AUDIT.md`.
- A first-launch **guided tour** (spotlight plus an animated hand that performs each
  gesture) and a searchable feature list, both under **?** in the header, with a second
  tour for Process mode, a "learn in order" path and a glossary.
- Light or dark follows the system setting.

Gestures: one finger orbits, two fingers pan and pinch-zoom, a tap identifies the layer
under your finger.

## Layout of the code

```
Scene.kt      data model + the devices.json parser (org.json, no dependency)
Renderer.kt   GLSurfaceView.Renderer — shaders, VBOs, section caps, ray picking, logic shading
AppUi.kt      all Compose UI: header, chips, GL stage, overlays, control panel tabs
Guide.kt      guided tours (spotlight, hand, card), feature list, glossary, learning path,
              tour targets, guide.json parser
Story.kt      the Story tab's text blocks
Theme.kt      Material 3 colour schemes and type
AppInfo.kt    name, developer, links and attributions in one place
MainActivity.kt
```

`Renderer` exposes its state as `@Volatile` fields written from the UI thread and read on
the GL thread; the surface is set to `RENDERMODE_WHEN_DIRTY` so it only redraws when
something actually changes, which keeps it off the battery.

## Things you might want to change

- **Geometry/content**: edit the builders in the parent folder, then run
  `python3 scripts/build.py` from the repository root. This regenerates stories and
  capacitance estimates and synchronizes Android, web and PWA assets.
- **Package name**: `namespace` and `applicationId` in `app/build.gradle.kts`, plus the
  `package` line at the top of each `.kt` file.
- **App name / icon**: `res/values/strings.xml`; the launcher icon is generated by `scripts/mkicon.py` from `scripts/icon_src.png`.

## Known gaps

- Callout labels are positioned by projecting their anchor each frame but are not
  de-overlapped the way the web version does it, so on a small screen a couple of them can
  sit on top of each other. Turning callouts off in the Section tab is the workaround.
- Tour completion and the sheet's see-through are saved locally. Per-scene state lasts
  for the session only; other scene controls are not durable user preferences. See the
  root privacy policy.

Technical references are bundled in `references.json` and linked from About. These
educational models do not reproduce a foundry recipe or simulate electrical performance.
