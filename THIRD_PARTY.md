# Third-party notices

## Fonts

**IBM Plex Sans** and **IBM Plex Mono**
Copyright © 2017 IBM Corp.
Licensed under the SIL Open Font License, Version 1.1.
<https://github.com/IBM/plex> · <https://scripts.sil.org/OFL>

The font files in `android/app/src/main/res/font/` are redistributed unmodified under
that licence. The OFL permits bundling in an application, including a commercial one,
provided the fonts are not sold on their own.

## Libraries

| Library | Licence |
|---|---|
| AndroidX (Core, Activity, Lifecycle, Compose) | Apache License 2.0 |
| Jetpack Compose Material 3 | Apache License 2.0 |
| Kotlin standard library and coroutines | Apache License 2.0 |
| `trimesh`, `numpy` (build scripts only, not shipped) | MIT / BSD-3-Clause |

No third-party 3D engine is used. The renderer is hand-written OpenGL ES 2.0.

## Geometry and technical sources

The models are original parametric geometry written for this project. They are informed
by published descriptions, not derived from anyone's files:

- S. Rathore et al., *Semiconductor Science and Technology* (2021) — nanosheet FET
  schematic that the device layer stack follows.
- imec published articles and press material on forksheet and CFET device architectures.

All dimensions are representative teaching values. Nothing here is any foundry's process
data, and nothing in this repository is confidential to any company.
