# FET Lab — native Android app

Kotlin + Jetpack Compose, with a hand-written OpenGL ES 2.0 renderer. No third-party 3D
library: the geometry, shaders, section capping, picking and the exploded view are all in
`Renderer.kt`, ported from the web viewer.

## Build it

1. **Android Studio** (Ladybug 2024.2.1 or newer) → *Open* → pick this `android/` folder.
2. Let it sync. It will fetch AGP 8.7.3, Kotlin 2.0.21, Compose BOM 2024.10.01 and the
   Gradle 8.9 distribution on first run — that download is why the APK could not be built
   for you in advance.
3. Plug in a phone with USB debugging on, or start an emulator, and press **Run**.

Command line, if you prefer, once Android Studio has generated the wrapper
(or with your own Gradle 8.9+ and `ANDROID_HOME` set):

```bash
./gradlew assembleDebug      # app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug       # straight onto a connected device
```

minSdk 26 (Android 8.0), targetSdk 35. Requires OpenGL ES 2.0, which every Android phone
since 2011 has.

## What the app does

Ten scenes, loaded from `app/src/main/assets/devices.json` — the same file the web viewer
reads, so regenerating the geometry updates both.

- **Device mode** — FinFET, nanosheet, forksheet, CFET (monolithic / sequential) and the
  four-way footprint comparison.
- **Inverter mode** — a full CMOS inverter standard cell in each architecture, with an
  input toggle that lights the conducting path and dims the transistor that is off.
- Per-layer visibility grouped by process module, three section planes with solid capped
  cut faces, an exploded view, and tap-to-identify on any layer.

Gestures: one finger orbits, two fingers pan and pinch-zoom, a tap identifies the layer
under your finger.

## Layout of the code

```
Scene.kt      data model + the devices.json parser (org.json, no dependency)
Renderer.kt   GLSurfaceView.Renderer — shaders, VBOs, section caps, ray picking, logic shading
AppUi.kt      all Compose UI: header, chips, GL stage, overlays, control panel tabs
Theme.kt      Material 3 colour schemes and type
MainActivity.kt
```

`Renderer` exposes its state as `@Volatile` fields written from the UI thread and read on
the GL thread; the surface is set to `RENDERMODE_WHEN_DIRTY` so it only redraws when
something actually changes, which keeps it off the battery.

## Things you might want to change

- **Geometry**: edit `scripts/build_devices.py` / `build_inverters.py` in the parent folder,
  re-run them, and copy the new `devices.json` over `app/src/main/assets/devices.json`.
- **Package name**: `namespace` and `applicationId` in `app/build.gradle.kts`, plus the
  `package` line at the top of each `.kt` file.
- **App name / icon**: `res/values/strings.xml` and `res/drawable/ic_launcher_foreground.xml`.

## Known gaps

- Callout labels are positioned by projecting their anchor each frame but are not
  de-overlapped the way the web version does it, so on a small screen a couple of them can
  sit on top of each other. Turning callouts off in the Section tab is the workaround.
- No state is persisted across process death; the app reopens on the FinFET scene.
