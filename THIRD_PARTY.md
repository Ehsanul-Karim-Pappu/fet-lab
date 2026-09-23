# Third-party notices

## Fonts

**IBM Plex Sans** and **IBM Plex Mono**
Copyright © 2017 IBM Corp.
Licensed under the SIL Open Font License, Version 1.1.
<https://github.com/IBM/plex> · <https://scripts.sil.org/OFL>

The font files in `android/app/src/main/res/font/` are redistributed unmodified under
that licence. The OFL permits bundling in an application, including a commercial one,
provided the fonts are not sold on their own.

## Images

The guided tour's hand (`android/app/src/main/res/drawable-nodpi/tour_hand.png`) was
supplied by the developer, cropped and with its tap rings removed. Its source and licence
must be confirmed before a public release.

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

- Verified concept references and links: [Technical references](docs/TECHNICAL_REFERENCES.md).
- Reference data shared with the app and website: `data/references.json`.
- The old incomplete Rathore (2021) credit is retained as unverified provenance in that
  catalog. Its exact paper/figure remains unresolved; it is not used to substantiate claims.

All dimensions are representative teaching values. Nothing here is any foundry's process
data, and nothing in this repository is confidential to any company.

Material colors and the complete contact/gate recipe are illustrative. A cited paper
supports only the concept identified in its reference entry, not all model details.
